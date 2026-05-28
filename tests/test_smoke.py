"""End-to-end smoke test against the FastAPI app in LOCAL_MODE.

Verifies the full upload → ingest → query flow works with the local AI stub +
in-memory vector + SQLite. No AWS credentials required.
"""
import os
import sys
import tempfile
from pathlib import Path

# Ensure all local backends BEFORE importing app
os.environ.setdefault("AI_BACKEND", "local")
os.environ.setdefault("STORAGE_BACKEND", "local")
os.environ.setdefault("USERSTORE_BACKEND", "sqlite")
os.environ.setdefault("VECTOR_BACKEND", "local")
# Per-test temp dirs to avoid cross-pollution
_tmp = tempfile.mkdtemp(prefix="studybot-test-")
os.environ["STORAGE_LOCAL_DIR"] = str(Path(_tmp) / "uploads")
os.environ["USERSTORE_SQLITE_PATH"] = str(Path(_tmp) / "users.db")

# Add project root to sys.path so `from src...` imports work
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from src.app import app


client = TestClient(app)


def test_health_returns_ok():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["backends"]["ai"] == "local"


def test_upload_text_file():
    content = b"Gradient descent is an optimization algorithm used in machine learning."
    r = client.post(
        "/upload",
        files={"file": ("lecture.txt", content, "text/plain")},
        headers={"X-User-Id": "alice"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["filename"] == "lecture.txt"
    assert body["size"] == len(content)
    assert body["chars_extracted"] > 0


def test_query_returns_answer_after_upload():
    # Upload first
    client.post(
        "/upload",
        files={"file": ("lec.txt", b"Gradient descent uses a learning rate to update parameters.", "text/plain")},
        headers={"X-User-Id": "bob"},
    )
    r = client.post(
        "/query",
        json={"question": "What is gradient descent?"},
        headers={"X-User-Id": "bob"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "answer" in body
    assert isinstance(body["citations"], list)
    # Local vector index should find at least one hit for the keyword 'gradient'
    assert len(body["citations"]) >= 1


def test_query_without_upload_handles_empty_index():
    r = client.post(
        "/query",
        json={"question": "What is quantum chromodynamics?"},
        headers={"X-User-Id": "carol-fresh"},
    )
    assert r.status_code == 200
    assert "answer" in r.json()


def test_quiz_generated_from_uploaded_document():
    upload_res = client.post(
        "/upload",
        files={
            "file": (
                "quiz_lec.txt",
                b"Photosynthesis occurs in chloroplasts. Light reactions split water and release oxygen.",
                "text/plain",
            )
        },
        headers={"X-User-Id": "quiz-user"},
    )
    assert upload_res.status_code == 200
    doc_id = upload_res.json()["doc_id"]

    quiz_res = client.post(
        "/quiz",
        json={"num_questions": 2, "doc_id": doc_id},
        headers={"X-User-Id": "quiz-user"},
    )

    assert quiz_res.status_code == 200, quiz_res.text
    body = quiz_res.json()
    assert "quiz" in body
    assert isinstance(body["quiz"], list)
    assert body["quiz"]
    assert {"id", "question", "options", "correct_answer", "explanation"} <= set(body["quiz"][0])


def test_quiz_falls_back_when_bedrock_is_throttled():
    from src import handlers
    from src.adapters.vector import LocalVector

    class ThrottledAI:
        def generate_quiz_from_kb(self, prompt, **kwargs):
            raise Exception("ThrottlingException: Too many tokens per day")

    class DummyUserStore:
        def log_query(self, *args, **kwargs):
            return None

    vector = LocalVector()
    vector.ingest(
        doc_id="throttled-doc",
        text=(
            "Photosynthesis occurs in chloroplasts and converts light energy into chemical energy. "
            "Light reactions split water and release oxygen as a byproduct. "
            "The Calvin cycle uses carbon dioxide to build sugars."
        ),
        metadata={"user_id": "throttled-user", "filename": "lecture.txt"},
    )

    quiz = handlers.handle_generate_quiz(
        user_id="throttled-user",
        num_questions=3,
        doc_id="throttled-doc",
        vector_store=vector,
        ai_client=ThrottledAI(),
        userstore=DummyUserStore(),
    )

    assert len(quiz["quiz"]) == 3
    assert quiz["quiz"][0]["correct_answer"] in quiz["quiz"][0]["options"]
    assert len({item["question"] for item in quiz["quiz"]}) == len(quiz["quiz"])
    assert any(item["options"].index(item["correct_answer"]) != 0 for item in quiz["quiz"])
    assert "Based on the selected notes" in quiz["quiz"][0]["explanation"]


def test_quiz_normalization_does_not_leave_all_answers_at_a():
    from src.handlers import _normalize_quiz_items

    raw_items = [
        {
            "id": f"q{i}",
            "question": f"Question {i}",
            "options": ["Correct", "Wrong 1", "Wrong 2", "Wrong 3"],
            "correct_answer": "Correct",
            "explanation": "Explanation",
        }
        for i in range(1, 6)
    ]

    quiz = _normalize_quiz_items(raw_items, 5)
    assert len(quiz) == 5
    assert all(item["correct_answer"] in item["options"] for item in quiz)
    assert any(item["options"].index(item["correct_answer"]) != 0 for item in quiz)


def test_quiz_falls_back_when_bedrock_credentials_are_missing():
    from src import handlers
    from src.adapters.vector import LocalVector

    class MissingCredentialsAI:
        def generate_quiz_from_kb(self, prompt, **kwargs):
            raise Exception("NoCredentialsError: Unable to locate credentials")

    class DummyUserStore:
        def log_query(self, *args, **kwargs):
            return None

    vector = LocalVector()
    vector.ingest(
        doc_id="missing-credentials-doc",
        text=(
            "Machine learning is a subset of artificial intelligence. "
            "Gradient descent is used to minimize a loss function. "
            "Backpropagation computes gradients through a neural network. "
            "Training data is used to fit model parameters. "
            "Evaluation data measures how well a model generalizes."
        ),
        metadata={"user_id": "missing-credentials-user", "filename": "ml.txt"},
    )

    quiz = handlers.handle_generate_quiz(
        user_id="missing-credentials-user",
        num_questions=5,
        doc_id="missing-credentials-doc",
        vector_store=vector,
        ai_client=MissingCredentialsAI(),
        userstore=DummyUserStore(),
    )

    assert len(quiz["quiz"]) == 5
    assert len({item["question"] for item in quiz["quiz"]}) == 5
    assert any(item["options"].index(item["correct_answer"]) != 0 for item in quiz["quiz"])


def test_quiz_fallback_uses_full_local_doc_when_search_returns_partial_chunks():
    from src import handlers
    from src.adapters.vector import LocalVector

    class MissingCredentialsAI:
        def generate_quiz_from_kb(self, prompt, **kwargs):
            raise Exception("NoCredentialsError: Unable to locate credentials")

    class DummyUserStore:
        def log_query(self, *args, **kwargs):
            return None

    vector = LocalVector()
    vector.ingest(
        doc_id="math-doc",
        text=(
            "Mathematics is the study of numbers, shapes, and patterns. "
            "Numbers: including how things can be counted. "
            "Structure: including how things are organized. "
            "Place: where things are and spatial arrangement. "
            "Change: how things become different. "
            "Applied math is useful for solving real-world problems. "
            "Deduction is a way to prove new truths using old truths."
        ),
        metadata={"user_id": "math-user", "filename": "math.txt"},
        size=80,
        overlap=0,
    )

    quiz = handlers.handle_generate_quiz(
        user_id="math-user",
        num_questions=5,
        doc_id="math-doc",
        vector_store=vector,
        ai_client=MissingCredentialsAI(),
        userstore=DummyUserStore(),
    )

    assert len(quiz["quiz"]) == 5
    assert len({item["question"] for item in quiz["quiz"]}) == 5
    assert any(item["options"].index(item["correct_answer"]) != 0 for item in quiz["quiz"])


def test_list_docs_per_user_isolation():
    client.post(
        "/upload",
        files={"file": ("a.txt", b"alice's doc", "text/plain")},
        headers={"X-User-Id": "user-A"},
    )
    client.post(
        "/upload",
        files={"file": ("b.txt", b"bob's doc", "text/plain")},
        headers={"X-User-Id": "user-B"},
    )
    a_docs = client.get("/docs/list", headers={"X-User-Id": "user-A"}).json()["docs"]
    b_docs = client.get("/docs/list", headers={"X-User-Id": "user-B"}).json()["docs"]
    assert any(d["filename"] == "a.txt" for d in a_docs)
    assert all(d["filename"] != "b.txt" for d in a_docs)
    assert any(d["filename"] == "b.txt" for d in b_docs)


def test_creative_features_endpoints():
    # 1. Upload a document first
    upload_res = client.post(
        "/upload",
        files={"file": ("creative_lec.txt", b"Photosynthesis occurs in chloroplasts. The light reactions split water to release oxygen.", "text/plain")},
        headers={"X-User-Id": "creative-user"},
    )
    assert upload_res.status_code == 200
    doc_id = upload_res.json()["doc_id"]

    # 2. Test Socratic query
    query_res = client.post(
        "/query",
        json={"question": "Where does photosynthesis occur?", "socratic": True},
        headers={"X-User-Id": "creative-user"},
    )
    assert query_res.status_code == 200
    assert "answer" in query_res.json()

    # 3. Test Mind-map generation
    mindmap_res = client.post(
        f"/docs/{doc_id}/mindmap",
        headers={"X-User-Id": "creative-user"},
    )
    assert mindmap_res.status_code == 200
    assert "mindmap" in mindmap_res.json()

    # 4. Test Cornell notes generation
    cornell_res = client.post(
        f"/docs/{doc_id}/cornell",
        headers={"X-User-Id": "creative-user"},
    )
    assert cornell_res.status_code == 200
    c_data = cornell_res.json()["cornell"]
    assert "cues" in c_data
    assert "notes" in c_data
    assert "summary" in c_data

    # 5. Test Flashcards generation
    flashcards_res = client.post(
        "/flashcards",
        json={"topic": "Photosynthesis", "limit": 2, "doc_id": doc_id},
        headers={"X-User-Id": "creative-user"},
    )
    assert flashcards_res.status_code == 200
    assert "flashcards" in flashcards_res.json()
    assert len(flashcards_res.json()["flashcards"]) > 0


def test_bedrock_ai_falls_back_to_local_ai():
    from src.adapters.ai import BedrockAI
    
    # Instantiate BedrockAI which will fail to run bedrock due to dummy config / credentials
    ai = BedrockAI(region="us-east-1", model_id="dummy-model")
    
    # Testing invoke fallback
    prompt = "Practice quiz generator for photosynthesis"
    ans = ai.invoke(prompt)
    assert "local-q1" in ans or "chloroplasts" in ans.lower()
    
    # Testing retrieve_and_generate fallback
    res = ai.retrieve_and_generate("What is photosynthesis?", kb_id="dummy-kb")
    assert "answer" in res
    assert "photosynthesis" in res["answer"].lower() or "local" in res["answer"].lower()

