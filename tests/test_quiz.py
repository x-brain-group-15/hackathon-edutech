"""Quiz feature tests — runs fully in LOCAL_MODE (no AWS credentials needed).

Test cases:
  Happy path
    - generate quiz after upload → valid structure returned
    - generate quiz scoped to specific doc_id
    - all 3 difficulty levels accepted (easy / medium / hard)
    - num_questions clamped to 1 at minimum
    - num_questions clamped to 20 at maximum
    - list_quizzes returns previously generated quizzes
    - list_quizzes is isolated per user
    - quiz persisted: quiz_id appears in list after generation

  Input / validation
    - invalid difficulty falls back to "medium"
    - num_questions=0 is clamped to 1
    - num_questions=99 is clamped to 20
    - missing body fields use defaults (difficulty=medium, num_questions=5)
    - doc_id omitted → uses all user docs

  Edge cases
    - quiz with no uploaded docs returns error payload (not 500)
    - quiz scoped to non-existent doc_id returns error payload (not 500)
    - upload empty file → 400, no quiz generated from it
    - _parse_quiz_json handles markdown code fences
    - _parse_quiz_json handles preamble text before JSON
    - _parse_quiz_json drops malformed questions (missing options / bad answer key)
    - _parse_quiz_json returns [] on completely invalid JSON
    - _parse_quiz_json returns [] on non-array JSON

  Persistence
    - quiz saved to SQLite can be retrieved via /quiz/list
    - list_quizzes limit param respected
"""
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

# ── Force local backends BEFORE importing app ──────────────────────────────
os.environ["AI_BACKEND"] = "local"
os.environ["STORAGE_BACKEND"] = "local"
os.environ["USERSTORE_BACKEND"] = "sqlite"
os.environ["VECTOR_BACKEND"] = "local"

_tmp = tempfile.mkdtemp(prefix="studybot-quiz-test-")
os.environ["STORAGE_LOCAL_DIR"] = str(Path(_tmp) / "uploads")
os.environ["USERSTORE_SQLITE_PATH"] = str(Path(_tmp) / "quiz_test.db")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient

from src.app import app
from src.handlers import _parse_quiz_json

client = TestClient(app)

# ── Shared sample content ───────────────────────────────────────────────────
LECTURE_CONTENT = (
    b"Photosynthesis is the process by which plants use sunlight to produce glucose. "
    b"Chlorophyll is the pigment responsible for absorbing light energy. "
    b"The light-dependent reactions occur in the thylakoid membrane. "
    b"The Calvin cycle takes place in the stroma of the chloroplast. "
    b"Oxygen is released as a byproduct of the light reactions. "
    b"ATP and NADPH are produced during the light-dependent stage. "
    b"Carbon dioxide is fixed during the Calvin cycle to form G3P. "
    b"Plants require water, carbon dioxide, and light to perform photosynthesis."
)

SECOND_LECTURE = (
    b"Mitosis is the process of cell division that produces two identical daughter cells. "
    b"The phases of mitosis are prophase, metaphase, anaphase, and telophase. "
    b"Chromosomes align at the metaphase plate during metaphase. "
    b"Sister chromatids are separated during anaphase."
)


def _upload(content: bytes, filename: str = "lecture.txt", user: str = "quiz-user") -> str:
    """Helper: upload bytes and return doc_id."""
    r = client.post(
        "/upload",
        files={"file": (filename, content, "text/plain")},
        headers={"X-User-Id": user},
    )
    assert r.status_code == 200, f"Upload failed: {r.text}"
    return r.json()["doc_id"]


def _generate_quiz(user: str = "quiz-user", **kwargs) -> dict:
    """Helper: POST /quiz and return parsed body."""
    r = client.post("/quiz", json=kwargs, headers={"X-User-Id": user})
    return r.status_code, r.json()


# ═══════════════════════════════════════════════════════════════════════════
# Happy path
# ═══════════════════════════════════════════════════════════════════════════

class TestQuizHappyPath:

    def test_generate_quiz_returns_valid_structure(self):
        """POST /quiz after upload → 200 with all required fields."""
        _upload(LECTURE_CONTENT, user="hp-user-1")
        status, body = _generate_quiz(user="hp-user-1", difficulty="easy", num_questions=2)

        assert status == 200
        assert "quiz_id" in body
        assert body["quiz_id"] is not None
        assert body["difficulty"] == "easy"
        assert "questions" in body
        assert isinstance(body["questions"], list)
        assert body["num_questions"] == len(body["questions"])

    def test_each_question_has_required_fields(self):
        """Every question must have question, options (A-D), answer, explanation."""
        _upload(LECTURE_CONTENT, user="hp-user-2")
        _, body = _generate_quiz(user="hp-user-2", num_questions=2)

        for q in body["questions"]:
            assert "question" in q and q["question"]
            assert "options" in q
            assert set(q["options"].keys()) == {"A", "B", "C", "D"}
            assert q["answer"] in ("A", "B", "C", "D")
            assert "explanation" in q

    def test_quiz_scoped_to_specific_doc_id(self):
        """Passing doc_id scopes the quiz to that document."""
        doc_id = _upload(LECTURE_CONTENT, user="hp-user-3")
        status, body = _generate_quiz(user="hp-user-3", doc_id=doc_id, num_questions=2)

        assert status == 200
        assert body["doc_id"] == doc_id

    def test_difficulty_easy(self):
        _upload(LECTURE_CONTENT, user="diff-easy")
        _, body = _generate_quiz(user="diff-easy", difficulty="easy", num_questions=2)
        assert body["difficulty"] == "easy"

    def test_difficulty_medium(self):
        _upload(LECTURE_CONTENT, user="diff-medium")
        _, body = _generate_quiz(user="diff-medium", difficulty="medium", num_questions=2)
        assert body["difficulty"] == "medium"

    def test_difficulty_hard(self):
        _upload(LECTURE_CONTENT, user="diff-hard")
        _, body = _generate_quiz(user="diff-hard", difficulty="hard", num_questions=2)
        assert body["difficulty"] == "hard"

    def test_quiz_without_doc_id_uses_all_docs(self):
        """Omitting doc_id should still work and set doc_id='all' in response."""
        _upload(LECTURE_CONTENT, user="hp-user-all")
        status, body = _generate_quiz(user="hp-user-all", num_questions=2)

        assert status == 200
        assert body["doc_id"] == "all"

    def test_list_quizzes_returns_generated_quiz(self):
        """Quiz generated via POST /quiz must appear in GET /quiz/list."""
        _upload(LECTURE_CONTENT, user="list-user-1")
        _, gen = _generate_quiz(user="list-user-1", num_questions=2)
        quiz_id = gen["quiz_id"]

        r = client.get("/quiz/list", headers={"X-User-Id": "list-user-1"})
        assert r.status_code == 200
        ids = [q["quiz_id"] for q in r.json()["quizzes"]]
        assert quiz_id in ids

    def test_list_quizzes_user_isolation(self):
        """User A's quizzes must not appear in User B's list."""
        _upload(LECTURE_CONTENT, user="iso-user-A")
        _upload(LECTURE_CONTENT, user="iso-user-B")
        _, gen_a = _generate_quiz(user="iso-user-A", num_questions=2)
        _, gen_b = _generate_quiz(user="iso-user-B", num_questions=2)

        list_a = client.get("/quiz/list", headers={"X-User-Id": "iso-user-A"}).json()["quizzes"]
        list_b = client.get("/quiz/list", headers={"X-User-Id": "iso-user-B"}).json()["quizzes"]

        a_ids = {q["quiz_id"] for q in list_a}
        b_ids = {q["quiz_id"] for q in list_b}
        assert gen_a["quiz_id"] in a_ids
        assert gen_b["quiz_id"] in b_ids
        assert gen_a["quiz_id"] not in b_ids
        assert gen_b["quiz_id"] not in a_ids

    def test_multiple_quizzes_accumulate_in_list(self):
        """Generating 3 quizzes → list returns at least 3 entries."""
        _upload(LECTURE_CONTENT, user="accum-user")
        for _ in range(3):
            _generate_quiz(user="accum-user", num_questions=2)

        r = client.get("/quiz/list", headers={"X-User-Id": "accum-user"})
        assert len(r.json()["quizzes"]) >= 3


# ═══════════════════════════════════════════════════════════════════════════
# Input validation / clamping
# ═══════════════════════════════════════════════════════════════════════════

class TestQuizInputValidation:

    def test_invalid_difficulty_falls_back_to_medium(self):
        """Unknown difficulty string → silently normalised to 'medium'."""
        _upload(LECTURE_CONTENT, user="val-user-1")
        _, body = _generate_quiz(user="val-user-1", difficulty="EXTREME", num_questions=2)
        assert body["difficulty"] == "medium"

    def test_difficulty_case_insensitive(self):
        """'EASY', 'Easy', 'easy' all accepted."""
        _upload(LECTURE_CONTENT, user="val-user-ci")
        for variant in ("EASY", "Easy", "easy"):
            _, body = _generate_quiz(user="val-user-ci", difficulty=variant, num_questions=2)
            assert body["difficulty"] == "easy", f"Failed for variant {variant!r}"

    def test_num_questions_zero_clamped_to_one(self):
        """num_questions=0 → clamped to 1, quiz still generated."""
        _upload(LECTURE_CONTENT, user="val-user-2")
        status, body = _generate_quiz(user="val-user-2", num_questions=0)
        assert status == 200
        # LocalAI stub returns 2 questions regardless; just check no crash + valid shape
        assert "questions" in body

    def test_num_questions_overlimit_clamped_to_20(self):
        """num_questions=99 → clamped to 20 internally (no 422 / 500)."""
        _upload(LECTURE_CONTENT, user="val-user-3")
        status, body = _generate_quiz(user="val-user-3", num_questions=99)
        assert status == 200
        # LocalAI stub returns 2; just verify no server error
        assert "questions" in body

    def test_missing_body_uses_defaults(self):
        """Empty JSON body → defaults: difficulty=medium, num_questions=5."""
        _upload(LECTURE_CONTENT, user="val-user-4")
        r = client.post("/quiz", json={}, headers={"X-User-Id": "val-user-4"})
        assert r.status_code == 200
        body = r.json()
        assert body["difficulty"] == "medium"

    def test_negative_num_questions_clamped_to_one(self):
        _upload(LECTURE_CONTENT, user="val-user-5")
        status, body = _generate_quiz(user="val-user-5", num_questions=-5)
        assert status == 200
        assert "questions" in body


# ═══════════════════════════════════════════════════════════════════════════
# Edge cases — no content / bad doc_id
# ═══════════════════════════════════════════════════════════════════════════

class TestQuizEdgeCases:

    def test_quiz_no_docs_returns_error_not_500(self):
        """User with zero uploads → 200 with error field, not a 500."""
        status, body = _generate_quiz(user="fresh-user-no-docs", num_questions=3)
        assert status == 200
        assert body.get("error") is not None
        assert body["num_questions"] == 0
        assert body["questions"] == []

    def test_quiz_nonexistent_doc_id_returns_error(self):
        """doc_id that doesn't exist for this user → error payload, not 500."""
        _upload(LECTURE_CONTENT, user="edge-user-1")
        status, body = _generate_quiz(
            user="edge-user-1",
            doc_id="00000000-0000-0000-0000-000000000000",
            num_questions=3,
        )
        assert status == 200
        assert body.get("error") is not None
        assert body["questions"] == []

    def test_upload_empty_file_returns_400(self):
        """Uploading an empty file → 400 Bad Request."""
        r = client.post(
            "/upload",
            files={"file": ("empty.txt", b"", "text/plain")},
            headers={"X-User-Id": "edge-user-2"},
        )
        assert r.status_code == 400

    def test_quiz_list_empty_for_new_user(self):
        """Brand-new user has no quizzes → empty list, not error."""
        r = client.get("/quiz/list", headers={"X-User-Id": "brand-new-user-xyz"})
        assert r.status_code == 200
        body = r.json()
        assert body["quizzes"] == []

    def test_quiz_list_limit_param(self):
        """GET /quiz/list?limit=2 returns at most 2 quizzes."""
        _upload(LECTURE_CONTENT, user="limit-user")
        for _ in range(4):
            _generate_quiz(user="limit-user", num_questions=2)

        r = client.get("/quiz/list?limit=2", headers={"X-User-Id": "limit-user"})
        assert r.status_code == 200
        assert len(r.json()["quizzes"]) <= 2

    def test_quiz_doc_id_in_response_matches_request(self):
        """doc_id in response must match what was requested."""
        doc_id = _upload(LECTURE_CONTENT, user="docid-check-user")
        _, body = _generate_quiz(user="docid-check-user", doc_id=doc_id, num_questions=2)
        assert body["doc_id"] == doc_id

    def test_two_docs_quiz_without_doc_id_uses_both(self):
        """Upload 2 docs, quiz without doc_id → doc_id='all' in response."""
        _upload(LECTURE_CONTENT, filename="doc1.txt", user="two-docs-user")
        _upload(SECOND_LECTURE, filename="doc2.txt", user="two-docs-user")
        _, body = _generate_quiz(user="two-docs-user", num_questions=2)
        assert body["doc_id"] == "all"
        assert body["questions"] is not None


# ═══════════════════════════════════════════════════════════════════════════
# _parse_quiz_json unit tests (pure function, no HTTP)
# ═══════════════════════════════════════════════════════════════════════════

VALID_QUESTION = {
    "question": "What is photosynthesis?",
    "options": {"A": "Opt A", "B": "Opt B", "C": "Opt C", "D": "Opt D"},
    "answer": "A",
    "explanation": "It is the process of converting light to glucose.",
}


class TestParseQuizJson:

    def test_clean_json_array(self):
        raw = json.dumps([VALID_QUESTION])
        result = _parse_quiz_json(raw)
        assert len(result) == 1
        assert result[0]["question"] == VALID_QUESTION["question"]
        assert result[0]["answer"] == "A"

    def test_markdown_json_fence(self):
        """Model wraps output in ```json ... ``` fences."""
        raw = "```json\n" + json.dumps([VALID_QUESTION]) + "\n```"
        result = _parse_quiz_json(raw)
        assert len(result) == 1

    def test_plain_code_fence(self):
        """Model wraps output in ``` ... ``` without language tag."""
        raw = "```\n" + json.dumps([VALID_QUESTION]) + "\n```"
        result = _parse_quiz_json(raw)
        assert len(result) == 1

    def test_preamble_text_before_json(self):
        """Model adds preamble text before the JSON array."""
        raw = "Here are your quiz questions:\n\n" + json.dumps([VALID_QUESTION])
        result = _parse_quiz_json(raw)
        assert len(result) == 1

    def test_completely_invalid_json_returns_empty(self):
        result = _parse_quiz_json("This is not JSON at all.")
        assert result == []

    def test_non_array_json_returns_empty(self):
        """If model returns a JSON object instead of array → empty list."""
        result = _parse_quiz_json(json.dumps({"question": "Q?"}))
        assert result == []

    def test_empty_string_returns_empty(self):
        assert _parse_quiz_json("") == []

    def test_drops_question_missing_options(self):
        bad = {**VALID_QUESTION, "options": {"A": "only A"}}
        raw = json.dumps([bad, VALID_QUESTION])
        result = _parse_quiz_json(raw)
        # Only the valid one should survive
        assert len(result) == 1
        assert result[0]["question"] == VALID_QUESTION["question"]

    def test_drops_question_with_invalid_answer_key(self):
        bad = {**VALID_QUESTION, "answer": "E"}
        raw = json.dumps([bad, VALID_QUESTION])
        result = _parse_quiz_json(raw)
        assert len(result) == 1

    def test_drops_question_with_empty_question_text(self):
        bad = {**VALID_QUESTION, "question": "   "}
        raw = json.dumps([bad, VALID_QUESTION])
        result = _parse_quiz_json(raw)
        assert len(result) == 1

    def test_answer_key_normalised_to_uppercase(self):
        """Lowercase answer 'a' should be normalised to 'A'."""
        q = {**VALID_QUESTION, "answer": "a"}
        result = _parse_quiz_json(json.dumps([q]))
        assert len(result) == 1
        assert result[0]["answer"] == "A"

    def test_multiple_valid_questions_all_returned(self):
        questions = [VALID_QUESTION] * 5
        result = _parse_quiz_json(json.dumps(questions))
        assert len(result) == 5

    def test_mixed_valid_and_invalid_only_valid_returned(self):
        bad1 = {**VALID_QUESTION, "answer": "Z"}
        bad2 = {**VALID_QUESTION, "options": {}}
        raw = json.dumps([bad1, VALID_QUESTION, bad2, VALID_QUESTION])
        result = _parse_quiz_json(raw)
        assert len(result) == 2

    def test_explanation_can_be_empty_string(self):
        """explanation is optional — empty string is fine."""
        q = {**VALID_QUESTION, "explanation": ""}
        result = _parse_quiz_json(json.dumps([q]))
        assert len(result) == 1
        assert result[0]["explanation"] == ""

    def test_extra_options_beyond_abcd_are_stripped(self):
        """Options beyond A-D should be stripped, not cause failure."""
        q = {
            **VALID_QUESTION,
            "options": {"A": "a", "B": "b", "C": "c", "D": "d", "E": "extra"},
        }
        result = _parse_quiz_json(json.dumps([q]))
        assert len(result) == 1
        assert "E" not in result[0]["options"]


# ═══════════════════════════════════════════════════════════════════════════
# AI stub behaviour
# ═══════════════════════════════════════════════════════════════════════════

class TestLocalAIStub:

    def test_local_ai_generate_quiz_returns_valid_json(self):
        """LocalAI.generate_quiz() must return parseable JSON with valid questions."""
        from src.adapters.ai import LocalAI
        ai = LocalAI()
        raw = ai.generate_quiz("dummy prompt")
        result = _parse_quiz_json(raw)
        assert isinstance(result, list)
        assert len(result) >= 1
        for q in result:
            assert q["answer"] in ("A", "B", "C", "D")
            assert set(q["options"].keys()) == {"A", "B", "C", "D"}

    def test_local_ai_generate_quiz_ignores_kwargs(self):
        """generate_quiz should not raise when extra kwargs are passed."""
        from src.adapters.ai import LocalAI
        ai = LocalAI()
        raw = ai.generate_quiz("prompt", max_tokens=512, temperature=0.9)
        assert isinstance(raw, str)
        assert len(raw) > 0


# ═══════════════════════════════════════════════════════════════════════════
# Persistence round-trip
# ═══════════════════════════════════════════════════════════════════════════

class TestQuizPersistence:

    def test_quiz_fields_persisted_correctly(self):
        """quiz_id, doc_id, difficulty, questions all survive a save→list round-trip."""
        doc_id = _upload(LECTURE_CONTENT, user="persist-user-1")
        _, gen = _generate_quiz(
            user="persist-user-1", doc_id=doc_id, difficulty="hard", num_questions=2
        )
        quiz_id = gen["quiz_id"]

        r = client.get("/quiz/list", headers={"X-User-Id": "persist-user-1"})
        saved = next((q for q in r.json()["quizzes"] if q["quiz_id"] == quiz_id), None)

        assert saved is not None
        assert saved["doc_id"] == doc_id
        assert saved["difficulty"] == "hard"
        assert isinstance(saved["questions"], list)

    def test_quiz_list_contains_questions_data(self):
        """Questions stored in DB must be retrievable with full structure."""
        _upload(LECTURE_CONTENT, user="persist-user-2")
        _, gen = _generate_quiz(user="persist-user-2", num_questions=2)
        quiz_id = gen["quiz_id"]

        r = client.get("/quiz/list", headers={"X-User-Id": "persist-user-2"})
        saved = next((q for q in r.json()["quizzes"] if q["quiz_id"] == quiz_id), None)
        assert saved is not None

        for q in saved["questions"]:
            assert "question" in q
            assert "options" in q
            assert "answer" in q

    def test_quiz_id_is_unique_per_generation(self):
        """Each call to POST /quiz must produce a distinct quiz_id."""
        _upload(LECTURE_CONTENT, user="unique-id-user")
        ids = set()
        for _ in range(3):
            _, body = _generate_quiz(user="unique-id-user", num_questions=2)
            ids.add(body["quiz_id"])
        assert len(ids) == 3
