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
Machine learning is a sub