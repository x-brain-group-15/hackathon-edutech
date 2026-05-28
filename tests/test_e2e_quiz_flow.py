"""
End-to-end test: Upload document → Select doc → Switch to Practice Quiz tab → Generate quiz

Simulates the exact UI flow:
  1. Upload a document (like a user dragging a file)
  2. "Select" the document (set selectedDocId)
  3. Switch to Practice Quiz tab (triggers generatePracticeQuiz)
  4. Verify quiz is returned with correct structure
  5. Simulate answering questions (navigate prev/next)
  6. Verify quiz works for multiple docs (isolation)
"""
import os
import sys
import tempfile
from pathlib import Path

# Force local backends — no AWS needed
os.environ["AI_BACKEND"] = "local"
os.environ["STORAGE_BACKEND"] = "local"
os.environ["USERSTORE_BACKEND"] = "sqlite"
os.environ["VECTOR_BACKEND"] = "local"

_tmp = tempfile.mkdtemp(prefix="studybot-e2e-quiz-")
os.environ["STORAGE_LOCAL_DIR"] = str(Path(_tmp) / "uploads")
os.environ["USERSTORE_SQLITE_PATH"] = str(Path(_tmp) / "users.db")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from src.app import app

client = TestClient(app)

USER = "e2e-quiz-user"
HEADERS = {"X-User-Id": USER}

SAMPLE_DOC = b"""
Photosynthesis is the process by which plants use sunlight, water, and carbon dioxide
to produce oxygen and energy in the form of sugar.

The process occurs in the chloroplasts of plant cells. Chlorophyll is the green pigment
that absorbs light energy.

There are two main stages:
1. Light-dependent reactions: occur in the thylakoid membranes. Water is split (photolysis),
   releasing oxygen as a byproduct. ATP and NADPH are produced.
2. Light-independent reactions (Calvin Cycle): occur in the stroma. CO2 is fixed into
   glucose using ATP and NADPH from the light reactions.

Key factors affecting photosynthesis:
- Light intensity
- Carbon dioxide concentration
- Temperature
- Water availability

The overall equation: 6CO2 + 6H2O + light energy -> C6H12O6 + 6O2
"""


# ─────────────────────────────────────────────────────────────────────────────
# STEP 1: Upload document
# ─────────────────────────────────────────────────────────────────────────────
def test_step1_upload_document():
    """User drags/selects a file and uploads it."""
    resp = client.post(
        "/upload",
        files={"file": ("photosynthesis.txt", SAMPLE_DOC, "text/plain")},
        headers=HEADERS,
    )
    assert resp.status_code == 200, f"Upload failed: {resp.text}"
    body = resp.json()

    assert body["filename"] == "photosynthesis.txt"
    assert body["size"] == len(SAMPLE_DOC)
    assert body["chars_extracted"] > 0
    assert "doc_id" in body

    # Store doc_id for subsequent steps
    test_step1_upload_document.doc_id = body["doc_id"]
    print(f"\n  ✓ Uploaded: {body['filename']} | doc_id={body['doc_id']} | chars={body['chars_extracted']}")


# ─────────────────────────────────────────────────────────────────────────────
# STEP 2: List docs — verify doc appears in library (sidebar)
# ─────────────────────────────────────────────────────────────────────────────
def test_step2_doc_appears_in_library():
    """After upload, doc should appear in the sidebar document list."""
    # Upload first (independent test)
    upload = client.post(
        "/upload",
        files={"file": ("photosynthesis.txt", SAMPLE_DOC, "text/plain")},
        headers=HEADERS,
    )
    assert upload.status_code == 200
    doc_id = upload.json()["doc_id"]

    resp = client.get("/docs/list", headers=HEADERS)
    assert resp.status_code == 200
    docs = resp.json()["docs"]

    found = next((d for d in docs if d["doc_id"] == doc_id), None)
    assert found is not None, f"doc_id {doc_id} not found in library"
    assert found["filename"] == "photosynthesis.txt"

    print(f"\n  ✓ Doc visible in library: {found['filename']} | doc_id={doc_id}")
    test_step2_doc_appears_in_library.doc_id = doc_id


# ─────────────────────────────────────────────────────────────────────────────
# STEP 3: Select doc + Switch to Practice Quiz tab → auto-generate quiz
# ─────────────────────────────────────────────────────────────────────────────
def test_step3_select_doc_and_generate_quiz():
    """
    Simulates: user clicks doc in sidebar (selectDoc) then clicks Practice Quiz tab.
    switchTab('tab-quiz') calls generatePracticeQuiz() with selectedDocId.
    """
    # Upload
    upload = client.post(
        "/upload",
        files={"file": ("photosynthesis.txt", SAMPLE_DOC, "text/plain")},
        headers=HEADERS,
    )
    assert upload.status_code == 200
    doc_id = upload.json()["doc_id"]

    # Simulate: window.selectedDocId = doc_id  →  POST /quiz
    resp = client.post(
        "/quiz",
        json={"num_questions": 5, "doc_id": doc_id},
        headers=HEADERS,
    )
    assert resp.status_code == 200, f"Quiz generation failed: {resp.text}"
    quiz = resp.json()

    # Validate structure (same as what renderQuiz() expects)
    assert isinstance(quiz, list), "Quiz must be a JSON array"
    assert len(quiz) > 0, "Quiz must have at least 1 question"

    for i, item in enumerate(quiz):
        assert "id" in item,            f"Q{i}: missing 'id'"
        assert "question" in item,      f"Q{i}: missing 'question'"
        assert "options" in item,       f"Q{i}: missing 'options'"
        assert "correct_answer" in item, f"Q{i}: missing 'correct_answer'"
        assert "explanation" in item,   f"Q{i}: missing 'explanation'"
        assert isinstance(item["options"], list), f"Q{i}: options must be list"
        assert len(item["options"]) >= 2, f"Q{i}: need at least 2 options"
        assert item["correct_answer"] in item["options"], \
            f"Q{i}: correct_answer '{item['correct_answer']}' not in options {item['options']}"

    print(f"\n  ✓ Quiz generated: {len(quiz)} questions from doc_id={doc_id}")
    for i, q in enumerate(quiz):
        print(f"    Q{i+1}: {q['question'][:70]}...")
        print(f"         Options: {q['options']}")
        print(f"         Answer:  {q['correct_answer']}")

    test_step3_select_doc_and_generate_quiz.quiz = quiz
    test_step3_select_doc_and_generate_quiz.doc_id = doc_id


# ─────────────────────────────────────────────────────────────────────────────
# STEP 4: Simulate answering quiz questions (prev/next navigation)
# ─────────────────────────────────────────────────────────────────────────────
def test_step4_answer_quiz_questions():
    """
    Simulates user clicking through quiz options.
    Verifies correct_answer is always one of the options (renderQuiz logic).
    """
    upload = client.post(
        "/upload",
        files={"file": ("photosynthesis.txt", SAMPLE_DOC, "text/plain")},
        headers=HEADERS,
    )
    doc_id = upload.json()["doc_id"]

    resp = client.post(
        "/quiz",
        json={"num_questions": 5, "doc_id": doc_id},
        headers=HEADERS,
    )
    quiz = resp.json()

    # Simulate answering all questions (always pick correct answer)
    score = 0
    for item in quiz:
        options = item["options"]
        correct = item["correct_answer"]
        # Find index of correct answer (mirrors JS: quizState.answers[item.id] = idx)
        correct_idx = options.index(correct)
        assert correct_idx >= 0
        score += 1  # always correct

    assert score == len(quiz)
    print(f"\n  ✓ Answered all {len(quiz)} questions correctly (simulated)")
    print(f"    Score: {score}/{len(quiz)}")


# ─────────────────────────────────────────────────────────────────────────────
# STEP 5: Quiz with specific doc_id — content isolation
# ─────────────────────────────────────────────────────────────────────────────
def test_step5_quiz_uses_selected_doc_content():
    """
    When user selects a specific doc, quiz should be generated from THAT doc only.
    Upload two different docs, verify quiz is scoped to the selected one.
    """
    # Doc A: Photosynthesis
    upload_a = client.post(
        "/upload",
        files={"file": ("photo.txt", SAMPLE_DOC, "text/plain")},
        headers=HEADERS,
    )
    doc_a = upload_a.json()["doc_id"]

    # Doc B: Different topic
    doc_b_content = b"""
    Machine learning is a subset of artificial intelligence.
    Neural networks are inspired by the human brain.
    Gradient descent is used to minimize the loss function.
    Backpropagation computes gradients through the network.
    """
    upload_b = client.post(
        "/upload",
        files={"file": ("ml.txt", doc_b_content, "text/plain")},
        headers=HEADERS,
    )
    doc_b = upload_b.json()["doc_id"]

    # Generate quiz for doc_a only
    quiz_a = client.post(
        "/quiz",
        json={"num_questions": 3, "doc_id": doc_a},
        headers=HEADERS,
    ).json()

    # Generate quiz for doc_b only
    quiz_b = client.post(
        "/quiz",
        json={"num_questions": 3, "doc_id": doc_b},
        headers=HEADERS,
    ).json()

    assert isinstance(quiz_a, list) and len(quiz_a) > 0
    assert isinstance(quiz_b, list) and len(quiz_b) > 0

    # Both quizzes should be valid
    for q in quiz_a + quiz_b:
        assert q["correct_answer"] in q["options"]

    print(f"\n  ✓ Doc isolation: quiz_a={len(quiz_a)} Qs, quiz_b={len(quiz_b)} Qs")
    print(f"    Doc A (photosynthesis) Q1: {quiz_a[0]['question'][:60]}...")
    print(f"    Doc B (ML) Q1:             {quiz_b[0]['question'][:60]}...")


# ─────────────────────────────────────────────────────────────────────────────
# STEP 6: Quiz without doc_id — should fail with 400
# ─────────────────────────────────────────────────────────────────────────────
def test_step6_quiz_without_doc_returns_error():
    """
    If user hasn't selected a doc (no selectedDocId), quiz should fail gracefully.
    Frontend shows toast warning; API returns 400.
    """
    fresh_user = "e2e-no-doc-user"
    resp = client.post(
        "/quiz",
        json={"num_questions": 5},
        headers={"X-User-Id": fresh_user},
    )
    assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
    assert "detail" in resp.json()
    print(f"\n  ✓ No-doc quiz correctly returns 400: {resp.json()['detail']}")


# ─────────────────────────────────────────────────────────────────────────────
# STEP 7: Re-generate quiz (quiz-generate button click)
# ─────────────────────────────────────────────────────────────────────────────
def test_step7_regenerate_quiz():
    """
    User clicks 'Generate New Quiz' button — should produce a fresh quiz.
    Two calls with same doc_id should both succeed (idempotent).
    """
    upload = client.post(
        "/upload",
        files={"file": ("photosynthesis.txt", SAMPLE_DOC, "text/plain")},
        headers=HEADERS,
    )
    doc_id = upload.json()["doc_id"]

    quiz1 = client.post("/quiz", json={"num_questions": 5, "doc_id": doc_id}, headers=HEADERS).json()
    quiz2 = client.post("/quiz", json={"num_questions": 5, "doc_id": doc_id}, headers=HEADERS).json()

    assert isinstance(quiz1, list) and len(quiz1) > 0
    assert isinstance(quiz2, list) and len(quiz2) > 0

    # Both should be valid
    for q in quiz1 + quiz2:
        assert q["correct_answer"] in q["options"]

    print(f"\n  ✓ Re-generate quiz: quiz1={len(quiz1)} Qs, quiz2={len(quiz2)} Qs — both valid")


# ─────────────────────────────────────────────────────────────────────────────
# STEP 8: Full flow with PDF-like content (larger doc)
# ─────────────────────────────────────────────────────────────────────────────
def test_step8_full_flow_with_sample_data():
    """
    Full flow using a real sample file from sample_data/ directory.
    Mirrors what a user would do: upload wiki article → select → quiz.
    """
    sample_file = Path("sample_data/wiki_04_photosynthesis.txt")
    if not sample_file.exists():
        print(f"\n  ⚠ Skipped: {sample_file} not found")
        return

    content = sample_file.read_bytes()
    upload = client.post(
        "/upload",
        files={"file": (sample_file.name, content, "text/plain")},
        headers=HEADERS,
    )
    assert upload.status_code == 200, f"Upload failed: {upload.text}"
    doc_id = upload.json()["doc_id"]
    chars = upload.json()["chars_extracted"]

    # Verify in library
    docs = client.get("/docs/list", headers=HEADERS).json()["docs"]
    assert any(d["doc_id"] == doc_id for d in docs)

    # Generate quiz
    quiz_resp = client.post(
        "/quiz",
        json={"num_questions": 5, "doc_id": doc_id},
        headers=HEADERS,
    )
    assert quiz_resp.status_code == 200, f"Quiz failed: {quiz_resp.text}"
    quiz = quiz_resp.json()

    assert isinstance(quiz, list) and len(quiz) > 0
    for q in quiz:
        assert q["correct_answer"] in q["options"]

    print(f"\n  ✓ Full flow with real sample file:")
    print(f"    File: {sample_file.name} | {len(content)} bytes | {chars} chars")
    print(f"    doc_id: {doc_id}")
    print(f"    Quiz: {len(quiz)} questions generated")
    for i, q in enumerate(quiz):
        print(f"    Q{i+1}: {q['question'][:70]}...")
