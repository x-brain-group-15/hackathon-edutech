"""Endpoint handlers. Pure business logic — knows nothing about FastAPI or AWS specifics."""
import io
import json
import re
import uuid
from typing import Optional


PROMPT_TEMPLATE = """You are a study assistant. Answer the student's question using ONLY the
context retrieved from their uploaded lecture notes. Cite the source by chunk
number where possible. If the context does not contain the answer, say so
plainly. Do not invent information.

CONTEXT:
{context}

QUESTION: {question}

ANSWER:"""


QUIZ_PROMPT_TEMPLATE = """You are an expert educator. Generate {num_questions} multiple-choice quiz questions
based ONLY on the content below. Difficulty level: {difficulty}.

Difficulty guidelines:
- easy: factual recall, definitions, straightforward concepts
- medium: application of concepts, cause-and-effect, comparisons
- hard: analysis, synthesis, edge cases, nuanced understanding

CONTENT:
{context}

Return ONLY a valid JSON array (no markdown, no extra text) with this exact structure:
[
  {{
    "question": "Question text here?",
    "options": {{
      "A": "First option",
      "B": "Second option",
      "C": "Third option",
      "D": "Fourth option"
    }},
    "answer": "A",
    "explanation": "Brief explanation of why this answer is correct."
  }}
]

Rules:
- Each question must have exactly 4 options (A, B, C, D)
- The "answer" field must be one of: A, B, C, D
- Questions must be grounded in the provided content only
- Do not repeat questions
- Output ONLY the JSON array, nothing else
"""


def _extract_text(filename: str, data: bytes) -> str:
    """Extract plain text from PDF or .txt upload."""
    name = filename.lower()
    if name.endswith(".pdf"):
        try:
            from pypdf import PdfReader
        except ImportError:
            return "(pypdf not installed — install requirements.txt)"
        reader = PdfReader(io.BytesIO(data))
        return "\n\n".join(page.extract_text() or "" for page in reader.pages)
    # Default: assume UTF-8 text
    try:
        return data.decode("utf-8", errors="replace")
    except Exception:
        return ""


def handle_upload(
    user_id: str,
    filename: str,
    data: bytes,
    storage,
    userstore,
    vector_store,
) -> dict:
    """Store the file, extract text, ingest into vector store, record in userstore."""
    doc_id = str(uuid.uuid4())
    key = f"{user_id}/{doc_id}/{filename}"
    location = storage.put(key, data)
    text = _extract_text(filename, data)
    if text.strip():
        vector_store.ingest(doc_id=doc_id, text=text, metadata={"user_id": user_id, "filename": filename})
    userstore.add_doc(
        user_id=user_id,
        doc_id=doc_id,
        metadata={"filename": filename, "size": len(data), "location": location, "chars": len(text)},
    )
    return {
        "doc_id": doc_id,
        "filename": filename,
        "size": len(data),
        "chars_extracted": len(text),
        "location": location,
    }


def handle_query(
    user_id: str,
    question: str,
    ai_client,
    userstore,
    vector_store,
    vector_backend: str,
    bedrock_kb_id: str,
) -> dict:
    """RAG flow: retrieve user's relevant chunks → call AI with context → log + return."""
    if vector_backend == "bedrock_kb":
        # Production path: let Bedrock do retrieve + generate in one call
        result = ai_client.retrieve_and_generate(query=question, kb_id=bedrock_kb_id)
        answer = result["answer"]
        citations = result["citations"]
    else:
        # Local path: do our own retrieve then prompt
        chunks = vector_store.search(question, top_k=5, filter={"user_id": user_id})
        if not chunks:
            answer = "No relevant content found in your uploaded documents. Upload some first."
            citations = []
        else:
            context = "\n\n".join(f"[chunk {i+1}] {c['text']}" for i, c in enumerate(chunks))
            prompt = PROMPT_TEMPLATE.format(context=context, question=question)
            answer = ai_client.invoke(prompt, max_tokens=512)
            citations = [
                {"chunk": i + 1, "doc_id": c["doc_id"], "score": c["score"], "text": c["text"][:200]}
                for i, c in enumerate(chunks)
            ]

    userstore.log_query(user_id=user_id, query=question, answer=answer)
    return {"question": question, "answer": answer, "citations": citations}


def handle_list_docs(user_id: str, userstore) -> dict:
    return {"user_id": user_id, "docs": userstore.list_docs(user_id)}


def handle_recent_queries(user_id: str, userstore, limit: int = 10) -> dict:
    return {"user_id": user_id, "queries": userstore.recent_queries(user_id, limit=limit)}


_VALID_DIFFICULTIES = {"easy", "medium", "hard"}


def handle_quiz(
    user_id: str,
    doc_id: Optional[str],
    difficulty: str,
    num_questions: int,
    ai_client,
    userstore,
    vector_store,
    vector_backend: str,
    bedrock_kb_id: str,
) -> dict:
    """Generate a multiple-choice quiz from the user's uploaded documents.

    Flow:
      1. Retrieve relevant chunks from the vector store (filtered to this user / doc).
      2. Build a quiz-generation prompt with the retrieved context.
      3. Call AI to produce a JSON array of questions.
      4. Parse + validate the response.
      5. Persist the quiz in userstore and return it.
    """
    difficulty = difficulty.lower()
    if difficulty not in _VALID_DIFFICULTIES:
        difficulty = "medium"
    num_questions = max(1, min(num_questions, 20))  # clamp 1-20

    # --- 1. Retrieve context ---
    search_filter: dict = {"user_id": user_id}
    if doc_id:
        search_filter["doc_id"] = doc_id

    if vector_backend == "bedrock_kb":
        # For Bedrock KB, retrieve chunks via the retrieve API (not retrieve_and_generate)
        chunks = vector_store.search(
            query="key concepts definitions important facts",
            top_k=10,
            filter=search_filter,
        )
    else:
        # Local keyword index: try a broad query first; if nothing matches (no
        # shared tokens), fall back to scanning all chunks for this user/doc.
        chunks = vector_store.search(
            query="key concepts definitions important facts",
            top_k=10,
            filter=search_filter,
        )
        if not chunks:
            # Fallback: retrieve all stored chunks for this user (no keyword filter)
            chunks = vector_store.search(
                query="",
                top_k=10,
                filter=search_filter,
            )

    if not chunks:
        return {
            "quiz_id": None,
            "doc_id": doc_id,
            "difficulty": difficulty,
            "num_questions": 0,
            "questions": [],
            "error": "No content found. Upload a document first.",
        }

    context = "\n\n".join(f"[chunk {i+1}] {c['text']}" for i, c in enumerate(chunks))

    # --- 2. Build prompt ---
    prompt = QUIZ_PROMPT_TEMPLATE.format(
        num_questions=num_questions,
        difficulty=difficulty,
        context=context,
    )

    # --- 3. Call AI ---
    raw = ai_client.generate_quiz(prompt, max_tokens=2048, temperature=0.4)

    # --- 4. Parse JSON ---
    questions = _parse_quiz_json(raw)

    # --- 5. Persist + return ---
    quiz_id = str(uuid.uuid4())
    resolved_doc_id = doc_id or "all"
    userstore.save_quiz(
        user_id=user_id,
        quiz_id=quiz_id,
        doc_id=resolved_doc_id,
        difficulty=difficulty,
        questions=questions,
    )

    return {
        "quiz_id": quiz_id,
        "doc_id": resolved_doc_id,
        "difficulty": difficulty,
        "num_questions": len(questions),
        "questions": questions,
    }


def handle_list_quizzes(user_id: str, userstore, limit: int = 20) -> dict:
    return {"user_id": user_id, "quizzes": userstore.list_quizzes(user_id, limit=limit)}


def _parse_quiz_json(raw: str) -> list:
    """Extract and validate a JSON array of quiz questions from the AI response.

    Handles cases where the model wraps the JSON in markdown code fences.
    Returns an empty list if parsing fails rather than raising.
    """
    # Strip markdown code fences if present
    text = raw.strip()
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence_match:
        text = fence_match.group(1).strip()

    # Find the first '[' ... ']' block in case there's preamble text
    bracket_match = re.search(r"\[[\s\S]*\]", text)
    if bracket_match:
        text = bracket_match.group(0)

    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return []

    if not isinstance(data, list):
        return []

    validated = []
    for item in data:
        if not isinstance(item, dict):
            continue
        question = item.get("question", "").strip()
        options = item.get("options", {})
        answer = str(item.get("answer", "")).strip().upper()
        explanation = item.get("explanation", "").strip()

        # Basic validation
        if not question:
            continue
        if not isinstance(options, dict) or not all(k in options for k in ("A", "B", "C", "D")):
            continue
        if answer not in ("A", "B", "C", "D"):
            continue

        validated.append({
            "question": question,
            "options": {k: str(v) for k, v in options.items() if k in ("A", "B", "C", "D")},
            "answer": answer,
            "explanation": explanation,
        })

    return validated
