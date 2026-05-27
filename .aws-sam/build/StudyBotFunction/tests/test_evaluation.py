"""Unit tests for the RAG quality evaluation endpoint (/docs/{doc_id}/evaluate).

Validates that uploading a mock photosynthesis document, running the benchmark,
and calculating Precision@K, Recall@K, and MRR metrics work correctly.
"""
import os
import sys
import tempfile
from pathlib import Path

# Ensure all local backends are set before importing the app
os.environ["AI_BACKEND"] = "local"
os.environ["STORAGE_BACKEND"] = "local"
os.environ["USERSTORE_BACKEND"] = "sqlite"
os.environ["VECTOR_BACKEND"] = "local"

# Set up unique per-test temporary paths to avoid test cross-pollution
_tmp = tempfile.mkdtemp(prefix="studybot-test-eval-")
os.environ["STORAGE_LOCAL_DIR"] = str(Path(_tmp) / "uploads")
os.environ["USERSTORE_SQLITE_PATH"] = str(Path(_tmp) / "users.db")

# Add project root to sys.path so we can import src modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from src.app import app

client = TestClient(app)


def test_evaluation_flow():
    # 1. Prepare a mock photosynthesis document containing all ground-truth answers
    content = (
        "# Photosynthesis\n\n"
        "Photosynthesis is how plants make carbohydrates using light energy.\n\n"
        "## Ways it is done\n"
        "The chemical equation for photosynthesis is: 6 CO2 + 6 H2O + photons -> C6H12O6 + 6 O2.\n\n"
        "## Location\n"
        "Photosynthesis occurs in the chloroplasts in leaves, which contain chlorophyll green pigment.\n\n"
        "## Light-dependent phase\n"
        "During the light-dependent phase, light energy splits water molecules via photolysis in grana.\n\n"
        "## Factors\n"
        "The three main factors affecting photosynthesis are: light intensity, carbon dioxide, and temperature.\n\n"
        "## Effectiveness\n"
        "Today, the average rate of energy capture by photosynthesis globally is about 130 terawatts, "
        "which is six times larger than the power used by human civilization."
    )

    # 2. Upload the file to set up the document record
    upload_resp = client.post(
        "/upload",
        files={"file": ("wiki_04_photosynthesis.txt", content.encode("utf-8"), "text/plain")},
        headers={"X-User-Id": "tester-user"},
    )
    assert upload_resp.status_code == 200, upload_resp.text
    doc_id = upload_resp.json()["doc_id"]

    # 3. Call the evaluation endpoint with 'fixed' strategy
    eval_resp = client.post(
        f"/docs/{doc_id}/evaluate",
        json={
            "strategy": "fixed",
            "size": 300,
            "overlap": 50,
        },
        headers={"X-User-Id": "tester-user"},
    )
    assert eval_resp.status_code == 200, eval_resp.text
    
    data = eval_resp.json()
    assert data["doc_id"] == doc_id
    assert data["filename"] == "wiki_04_photosynthesis.txt"
    assert data["strategy_used"] == "fixed"
    
    # Assert metrics exist and are within correct bounds
    metrics = data["metrics"]
    for key in ["precision_at_1", "precision_at_3", "precision_at_5", "recall_at_1", "recall_at_3", "recall_at_5", "mrr"]:
        assert key in metrics
        assert 0.0 <= metrics[key] <= 1.0

    # Ensure at least some of our queries matched successfully (scores > 0)
    assert metrics["mrr"] > 0.0
    
    # Ensure all 5 queries are evaluated
    assert len(data["queries"]) == 5
    for q in data["queries"]:
        assert "query" in q
        assert "keywords" in q
        assert "retrieved" in q
        assert len(q["retrieved"]) > 0


def test_evaluation_alternative_strategies():
    # Use the same document from another user session to test structural and semantic strategies
    content = (
        "# Photosynthesis\n"
        "The chemical equation is 6 CO2 + 6 H2O + photons -> C6H12O6 + 6 O2.\n"
        "# Chloroplasts\n"
        "Photosynthesis occurs in chloroplasts in leaves using chlorophyll pigments.\n"
        "# Light dependent\n"
        "Split water photolysis creates oxygen, hydrogen, and NADPH.\n"
        "# Factors\n"
        "Factors: light intensity, carbon dioxide, temperature.\n"
        "# Effectiveness\n"
        "Average energy capture is 130 terawatts, six times larger than human civilization."
    )
    
    upload_resp = client.post(
        "/upload",
        files={"file": ("wiki_04_photosynthesis.txt", content.encode("utf-8"), "text/plain")},
        headers={"X-User-Id": "tester-user-2"},
    )
    assert upload_resp.status_code == 200
    doc_id = upload_resp.json()["doc_id"]

    # Test structural strategy
    eval_resp_struct = client.post(
        f"/docs/{doc_id}/evaluate",
        json={"strategy": "structural"},
        headers={"X-User-Id": "tester-user-2"},
    )
    assert eval_resp_struct.status_code == 200
    assert eval_resp_struct.json()["strategy_used"] == "structural"
    assert eval_resp_struct.json()["metrics"]["mrr"] > 0.0

    # Test semantic strategy
    eval_resp_sem = client.post(
        f"/docs/{doc_id}/evaluate",
        json={"strategy": "semantic", "threshold": 0.2},
        headers={"X-User-Id": "tester-user-2"},
    )
    assert eval_resp_sem.status_code == 200
    assert eval_resp_sem.json()["strategy_used"] == "semantic"
    assert eval_resp_sem.json()["metrics"]["mrr"] > 0.0
