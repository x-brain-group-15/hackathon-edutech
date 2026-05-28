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
    assert isinstance(body, list)
    assert body
    assert {"id", "question", "options", "correct_answer", "explanation"} <= set(body[0])


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
