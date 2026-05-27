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
