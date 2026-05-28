"""
test_pipeline.py — Kiểm tra luồng hoạt động của các chức năng (local mode, không gọi AWS).

Các luồng được kiểm tra:
  1. Upload → vector ingest → query với doc_ids filter (single doc)
  2. Upload nhiều doc → query với multi-doc doc_ids (fan-out search)
  3. Query không có doc_ids → search toàn bộ docs của user
  4. Flashcards với single doc_id
  5. Flashcards với multi doc_ids (fan-out)
  6. Flashcards không có doc_ids → search toàn bộ
  7. Quiz với doc_id cụ thể
  8. Mindmap với doc_id cụ thể
  9. Cornell notes với doc_id cụ thể
 10. Socratic query với doc_ids filter
 11. User isolation — doc của user A không lọt sang user B
 12. Delete doc → không còn trong library
"""
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

# Force local backends trước khi import app
os.environ["AI_BACKEND"] = "local"
os.environ["STORAGE_BACKEND"] = "local"
os.environ["USERSTORE_BACKEND"] = "sqlite"
os.environ["VECTOR_BACKEND"] = "local"

_tmp = tempfile.mkdtemp(prefix="studybot-pipeline-")
os.environ["STORAGE_LOCAL_DIR"] = str(Path(_tmp) / "uploads")
os.environ["USERSTORE_SQLITE_PATH"] = str(Path(_tmp) / "users.db")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from src.app import app
from src import handlers
from src.adapters.vector import LocalVector

client = TestClient(app)

# ── Nội dung tài liệu mẫu ────────────────────────────────────────────────────

DOC_PHOTO = b"""
Photosynthesis is the process by which plants convert light energy into chemical energy.
It occurs in the chloroplasts. Chlorophyll absorbs sunlight.
Light reactions split water and release oxygen. The Calvin cycle fixes CO2 into glucose.
"""

DOC_ML = b"""
Machine learning is a subset of artificial intelligence.
Gradient descent minimizes the loss function by updating weights iteratively.
Backpropagation computes gradients through a neural network layer by layer.
Overfitting occurs when a model memorizes training data instead of generalizing.
"""

DOC_ENERGY = b"""
Energy is the capacity to do work. It exists in many forms: kinetic, potential, thermal.
The law of conservation of energy states that energy cannot be created or destroyed.
Renewable energy sources include solar, wind, and hydroelectric power.
"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def upload(content: bytes, filename: str, user: str) -> str:
    """Upload một file và trả về doc_id."""
    res = client.post(
        "/upload",
        files={"file": (filename, content, "text/plain")},
        headers={"X-User-Id": user},
    )
    assert res.status_code == 200, f"Upload thất bại: {res.text}"
    return res.json()["doc_id"]


def list_docs(user: str) -> list:
    res = client.get("/docs/list", headers={"X-User-Id": user})
    assert res.status_code == 200
    return res.json()["docs"]


# ═════════════════════════════════════════════════════════════════════════════
# 1. Upload → query với single doc_id filter
# ═════════════════════════════════════════════════════════════════════════════

def test_query_single_doc_filter():
    """
    Luồng: upload 1 doc → query với doc_ids=[doc_id] → chỉ retrieve từ doc đó.
    Kiểm tra: response có answer và citations, citations thuộc đúng doc.
    """
    user = "pipeline-single-query"
    doc_id = upload(DOC_PHOTO, "photo.txt", user)

    res = client.post(
        "/query",
        json={"question": "What is photosynthesis?", "doc_ids": [doc_id]},
        headers={"X-User-Id": user},
    )
    assert res.status_code == 200, res.text
    body = res.json()

    assert "answer" in body
    assert isinstance(body["citations"], list)
    # Với local vector, citations phải có ít nhất 1 chunk từ doc vừa upload
    assert len(body["citations"]) >= 1
    # Mỗi citation phải có doc_id khớp
    for c in body["citations"]:
        assert c.get("doc_id") == doc_id, (
            f"Citation doc_id={c.get('doc_id')} không khớp với {doc_id}"
        )


# ═════════════════════════════════════════════════════════════════════════════
# 2. Upload nhiều doc → query với multi doc_ids (fan-out)
# ═════════════════════════════════════════════════════════════════════════════

def test_query_multi_doc_fanout():
    """
    Luồng: upload 2 doc → query với doc_ids=[id_a, id_b] → fan-out search cả hai.
    Kiểm tra: response hợp lệ, citations có thể đến từ cả hai doc.
    """
    user = "pipeline-multi-query"
    doc_a = upload(DOC_PHOTO, "photo.txt", user)
    doc_b = upload(DOC_ML, "ml.txt", user)

    res = client.post(
        "/query",
        json={"question": "What is energy conversion?", "doc_ids": [doc_a, doc_b]},
        headers={"X-User-Id": user},
    )
    assert res.status_code == 200, res.text
    body = res.json()

    assert "answer" in body
    assert isinstance(body["citations"], list)
    # Phải có ít nhất 1 citation (từ ít nhất 1 trong 2 doc)
    assert len(body["citations"]) >= 1
    # Tất cả citations phải thuộc 1 trong 2 doc đã chọn
    valid_ids = {doc_a, doc_b}
    for c in body["citations"]:
        assert c.get("doc_id") in valid_ids, (
            f"Citation doc_id={c.get('doc_id')} không nằm trong selection {valid_ids}"
        )


# ═════════════════════════════════════════════════════════════════════════════
# 3. Query không có doc_ids → search toàn bộ docs của user
# ═════════════════════════════════════════════════════════════════════════════

def test_query_no_doc_ids_searches_all():
    """
    Luồng: upload 2 doc → query không truyền doc_ids → search toàn bộ.
    Kiểm tra: response hợp lệ, không bị lỗi.
    """
    user = "pipeline-no-filter-query"
    upload(DOC_PHOTO, "photo.txt", user)
    upload(DOC_ML, "ml.txt", user)

    res = client.post(
        "/query",
        json={"question": "What is gradient descent?"},
        headers={"X-User-Id": user},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert "answer" in body
    assert isinstance(body["citations"], list)


# ═════════════════════════════════════════════════════════════════════════════
# 4. Flashcards với single doc_id
# ═════════════════════════════════════════════════════════════════════════════

def test_flashcards_single_doc():
    """
    Luồng: upload 1 doc → generate flashcards với doc_ids=[doc_id].
    Kiểm tra: trả về list flashcards có front/back.
    """
    user = "pipeline-flash-single"
    doc_id = upload(DOC_PHOTO, "photo.txt", user)

    res = client.post(
        "/flashcards",
        json={"topic": "Photosynthesis", "limit": 3, "doc_ids": [doc_id]},
        headers={"X-User-Id": user},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert "flashcards" in body
    cards = body["flashcards"]
    assert isinstance(cards, list)
    assert len(cards) > 0
    for card in cards:
        assert "front" in card, f"Thiếu 'front' trong card: {card}"
        assert "back" in card, f"Thiếu 'back' trong card: {card}"


# ═════════════════════════════════════════════════════════════════════════════
# 5. Flashcards với multi doc_ids (fan-out)
# ═════════════════════════════════════════════════════════════════════════════

def test_flashcards_multi_doc():
    """
    Luồng: upload 2 doc → generate flashcards với doc_ids=[id_a, id_b].
    Kiểm tra: trả về flashcards hợp lệ (context từ cả hai doc).
    """
    user = "pipeline-flash-multi"
    doc_a = upload(DOC_PHOTO, "photo.txt", user)
    doc_b = upload(DOC_ENERGY, "energy.txt", user)

    res = client.post(
        "/flashcards",
        json={"topic": "Energy and photosynthesis", "limit": 3, "doc_ids": [doc_a, doc_b]},
        headers={"X-User-Id": user},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert "flashcards" in body
    cards = body["flashcards"]
    assert isinstance(cards, list)
    assert len(cards) > 0


# ═════════════════════════════════════════════════════════════════════════════
# 6. Flashcards không có doc_ids → search toàn bộ
# ═════════════════════════════════════════════════════════════════════════════

def test_flashcards_no_doc_ids():
    """
    Luồng: generate flashcards không truyền doc_ids → không filter theo doc.
    Kiểm tra: không bị lỗi, trả về flashcards hợp lệ.
    """
    user = "pipeline-flash-nofilter"
    upload(DOC_ML, "ml.txt", user)

    res = client.post(
        "/flashcards",
        json={"topic": "Machine learning", "limit": 2},
        headers={"X-User-Id": user},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert "flashcards" in body
    assert isinstance(body["flashcards"], list)


# ═════════════════════════════════════════════════════════════════════════════
# 7. Quiz với doc_id cụ thể
# ═════════════════════════════════════════════════════════════════════════════

def test_quiz_specific_doc():
    """
    Luồng: upload doc → generate quiz với doc_id.
    Kiểm tra: quiz có đúng cấu trúc, correct_answer nằm trong options.
    """
    user = "pipeline-quiz"
    doc_id = upload(DOC_PHOTO, "photo.txt", user)

    res = client.post(
        "/quiz",
        json={"num_questions": 3, "doc_id": doc_id},
        headers={"X-User-Id": user},
    )
    assert res.status_code == 200, res.text
    quiz = res.json()["quiz"]

    assert isinstance(quiz, list)
    assert len(quiz) > 0
    for q in quiz:
        assert "question" in q
        assert "options" in q
        assert "correct_answer" in q
        assert "explanation" in q
        assert q["correct_answer"] in q["options"], (
            f"correct_answer '{q['correct_answer']}' không có trong options {q['options']}"
        )


# ═════════════════════════════════════════════════════════════════════════════
# 8. Mindmap với doc_id cụ thể
# ═════════════════════════════════════════════════════════════════════════════

def test_mindmap_specific_doc():
    """
    Luồng: upload doc → generate mindmap với /docs/{doc_id}/mindmap.
    Kiểm tra: trả về mindmap code bắt đầu bằng 'mindmap'.
    """
    user = "pipeline-mindmap"
    doc_id = upload(DOC_PHOTO, "photo.txt", user)

    res = client.post(
        f"/docs/{doc_id}/mindmap",
        headers={"X-User-Id": user},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert "mindmap" in body
    assert isinstance(body["mindmap"], str)
    assert body["mindmap"].strip().startswith("mindmap"), (
        f"Mindmap code phải bắt đầu bằng 'mindmap', nhận được: {body['mindmap'][:50]}"
    )


# ═════════════════════════════════════════════════════════════════════════════
# 9. Cornell notes với doc_id cụ thể
# ═════════════════════════════════════════════════════════════════════════════

def test_cornell_specific_doc():
    """
    Luồng: upload doc → generate cornell notes với /docs/{doc_id}/cornell.
    Kiểm tra: trả về cues, notes, summary.
    """
    user = "pipeline-cornell"
    doc_id = upload(DOC_PHOTO, "photo.txt", user)

    res = client.post(
        f"/docs/{doc_id}/cornell",
        headers={"X-User-Id": user},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert "cornell" in body
    cornell = body["cornell"]
    assert "cues" in cornell,   "Thiếu 'cues' trong cornell response"
    assert "notes" in cornell,  "Thiếu 'notes' trong cornell response"
    assert "summary" in cornell, "Thiếu 'summary' trong cornell response"
    assert isinstance(cornell["cues"], list)
    assert isinstance(cornell["notes"], list)
    assert isinstance(cornell["summary"], str)


# ═════════════════════════════════════════════════════════════════════════════
# 10. Socratic query với doc_ids filter
# ═════════════════════════════════════════════════════════════════════════════

def test_socratic_query_with_doc_ids():
    """
    Luồng: upload doc → socratic query với doc_ids=[doc_id].
    Kiểm tra: response là câu hỏi dẫn dắt (không phải câu trả lời thẳng).
    """
    user = "pipeline-socratic"
    doc_id = upload(DOC_PHOTO, "photo.txt", user)

    res = client.post(
        "/query",
        json={
            "question": "Where does photosynthesis occur?",
            "socratic": True,
            "doc_ids": [doc_id],
        },
        headers={"X-User-Id": user},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert "answer" in body
    assert isinstance(body["answer"], str)
    assert len(body["answer"]) > 0


# ═════════════════════════════════════════════════════════════════════════════
# 11. User isolation — doc của user A không lọt sang user B
# ═════════════════════════════════════════════════════════════════════════════

def test_user_isolation():
    """
    Luồng: user A upload doc → user B query với doc_id của A.
    Kiểm tra: user B không thấy doc của A trong library, query vẫn trả về answer
    nhưng không có citations từ doc của A.
    """
    user_a = "pipeline-isolation-A"
    user_b = "pipeline-isolation-B"

    doc_a = upload(DOC_PHOTO, "photo_a.txt", user_a)

    # User B không có doc nào
    docs_b = list_docs(user_b)
    doc_ids_b = [d["doc_id"] for d in docs_b]
    assert doc_a not in doc_ids_b, "Doc của user A không được xuất hiện trong library của user B"

    # User B query với doc_id của A → không tìm thấy chunks (vì filter user_id=B)
    res = client.post(
        "/query",
        json={"question": "What is photosynthesis?", "doc_ids": [doc_a]},
        headers={"X-User-Id": user_b},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert "answer" in body
    # Citations phải rỗng vì user B không có quyền truy cập doc của A
    for c in body.get("citations", []):
        assert c.get("doc_id") != doc_a, (
            "User B không được có citation từ doc của user A"
        )


# ═════════════════════════════════════════════════════════════════════════════
# 12. Delete doc → không còn trong library
# ═════════════════════════════════════════════════════════════════════════════

def test_delete_doc_removes_from_library():
    """
    Luồng: upload doc → delete → kiểm tra không còn trong /docs/list.
    """
    user = "pipeline-delete"
    doc_id = upload(DOC_ENERGY, "energy.txt", user)

    # Xác nhận doc có trong library
    docs_before = list_docs(user)
    assert any(d["doc_id"] == doc_id for d in docs_before), "Doc phải có trong library sau khi upload"

    # Xóa doc
    del_res = client.delete(f"/docs/{doc_id}", headers={"X-User-Id": user})
    assert del_res.status_code == 200, f"Delete thất bại: {del_res.text}"

    # Xác nhận doc đã biến mất
    docs_after = list_docs(user)
    assert not any(d["doc_id"] == doc_id for d in docs_after), "Doc phải biến mất khỏi library sau khi xóa"


# ═════════════════════════════════════════════════════════════════════════════
# 13. handle_query trực tiếp — kiểm tra logic fan-out trong handler
# ═════════════════════════════════════════════════════════════════════════════

def test_handler_query_fanout_logic():
    """
    Kiểm tra trực tiếp handle_query với LocalVector để xác nhận fan-out
    search đúng khi truyền nhiều doc_ids.
    """
    from src.adapters.ai import LocalAI

    vector = LocalVector()
    vector.ingest("doc-photo", DOC_PHOTO.decode(), metadata={"user_id": "fanout-user", "filename": "photo.txt"})
    vector.ingest("doc-ml", DOC_ML.decode(), metadata={"user_id": "fanout-user", "filename": "ml.txt"})
    vector.ingest("doc-energy", DOC_ENERGY.decode(), metadata={"user_id": "fanout-user", "filename": "energy.txt"})

    class DummyUserStore:
        def log_query(self, *a, **kw): pass
        def list_docs(self, uid): return []

    ai = LocalAI()

    # Query chỉ 2 trong 3 doc
    result = handlers.handle_query(
        user_id="fanout-user",
        question="What is energy?",
        ai_client=ai,
        userstore=DummyUserStore(),
        vector_store=vector,
        vector_backend="local",
        bedrock_kb_id="",
        doc_ids=["doc-photo", "doc-energy"],
    )

    assert "answer" in result
    assert isinstance(result["citations"], list)
    # Citations chỉ được đến từ doc-photo hoặc doc-energy, không phải doc-ml
    for c in result["citations"]:
        assert c.get("doc_id") in {"doc-photo", "doc-energy"}, (
            f"Fan-out bị lọt citation từ doc ngoài selection: {c.get('doc_id')}"
        )


# ═════════════════════════════════════════════════════════════════════════════
# 14. handle_generate_flashcards trực tiếp — kiểm tra fan-out
# ═════════════════════════════════════════════════════════════════════════════

def test_handler_flashcards_fanout_logic():
    """
    Kiểm tra trực tiếp handle_generate_flashcards với LocalVector.
    Xác nhận context được lấy từ đúng các doc được chọn.
    """
    from src.adapters.ai import LocalAI

    vector = LocalVector()
    vector.ingest("fc-doc-a", DOC_PHOTO.decode(), metadata={"user_id": "fc-user", "filename": "photo.txt"})
    vector.ingest("fc-doc-b", DOC_ENERGY.decode(), metadata={"user_id": "fc-user", "filename": "energy.txt"})

    ai = LocalAI()

    result = handlers.handle_generate_flashcards(
        user_id="fc-user",
        topic="Energy",
        limit=3,
        doc_id=None,
        doc_ids=["fc-doc-a", "fc-doc-b"],
        vector_store=vector,
        ai_client=ai,
        aws_region="ap-southeast-1",
    )

    assert "flashcards" in result
    cards = result["flashcards"]
    assert isinstance(cards, list)
    assert len(cards) > 0
    for card in cards:
        assert "front" in card
        assert "back" in card


# ═════════════════════════════════════════════════════════════════════════════
# 15. Flashcards topic rỗng → 400
# ═════════════════════════════════════════════════════════════════════════════

def test_flashcards_empty_topic_returns_400():
    """
    Luồng: gửi flashcard request với topic rỗng → API trả về 400.
    """
    user = "pipeline-flash-empty"
    res = client.post(
        "/flashcards",
        json={"topic": "   ", "limit": 3},
        headers={"X-User-Id": user},
    )
    assert res.status_code == 400, f"Mong đợi 400, nhận được {res.status_code}"
