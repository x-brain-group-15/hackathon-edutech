"""Endpoint handlers. Pure business logic — knows nothing about FastAPI or AWS specifics."""
import re
import uuid
import json
import time
import logging
import traceback
from pathlib import Path
from typing import Optional

from src.config import config
from src.pdf_extractor import extract_pdf

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def log_event(event_type: str, **kwargs):
    logger.info(json.dumps({
        "event_type": event_type,
        **kwargs
    }, ensure_ascii=False))


def log_step(operation: str, step: str, **kwargs):
    log_event(
        "PROCESS_STEP",
        operation=operation,
        step=step,
        **kwargs
    )


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
    if filename.lower().endswith(".pdf"):
        try:
            return extract_pdf(data).text
        except RuntimeError as exc:
            return f"({exc})"
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
    strategy: Optional[str] = None,
    size: Optional[int] = None,
    overlap: Optional[int] = None,
    threshold: Optional[float] = None,
) -> dict:
    """Store the file, extract text, ingest into vector store, record in userstore."""
    try:
        start_time = time.time()
        doc_id = str(uuid.uuid4())
        key = f"{user_id}/{doc_id}/{filename}"
        location = storage.put(key, data)
        
        # Write companion metadata.json for Bedrock KB multi-tenant filtering
        try:
            import json
            metadata_json = {
                "metadataAttributes": {
                    "user_id": user_id,
                    "doc_id": doc_id,
                    "filename": filename
                }
            }
            storage.put(key + ".metadata.json", json.dumps(metadata_json).encode("utf-8"))
        except Exception:
            pass
            
        text = _extract_text(filename, data)
        if text.strip():
            vector_store.ingest(
                doc_id=doc_id,
                text=text,
                metadata={"user_id": user_id, "filename": filename},
                strategy=strategy,
                size=size,
                overlap=overlap,
                threshold=threshold,
            )
        userstore.add_doc(
            user_id=user_id,
            doc_id=doc_id,
            metadata={"filename": filename, "size": len(data), "location": location, "chars": len(text)},
        )
        log_event(
            "DOCUMENT_UPLOAD",
            user_id=user_id,
            doc_id=doc_id,
            filename=filename,
            size=len(data),
            chars_extracted=len(text),
            location=location,
            status="success"
        )
        return {
            "doc_id": doc_id,
            "filename": filename,
            "size": len(data),
            "chars_extracted": len(text),
            "location": location,
        }
    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)

        log_event(
            "UPLOAD_ERROR",
            user_id=user_id,
            doc_id=doc_id,
            filename=filename,
            latency_ms=latency_ms,
            error_type=type(e).__name__,
            error_message=str(e),
            stack_trace=traceback.format_exc(),
            status="error"
        )

        raise


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

    start_time = time.time()

    log_step(
        "rag_query",
        "query_received",
        user_id=user_id,
        question=question,
        vector_backend=vector_backend
    )

    try:
        if vector_backend == "bedrock_kb":
            log_step(
                "rag_query",
                "bedrock_retrieve_generate_start",
                user_id=user_id,
                kb_id=bedrock_kb_id
            )

            result = ai_client.retrieve_and_generate(
                query=question,
                kb_id=bedrock_kb_id
            )

            answer = result["answer"]
            citations = result.get("citations", [])

            input_tokens = result.get("input_tokens", 0)
            output_tokens = result.get("output_tokens", 0)

            log_step(
                "rag_query",
                "bedrock_retrieve_generate_done",
                user_id=user_id,
                citations_count=len(citations)
            )

        else:
            log_step(
                "rag_query",
                "vector_search_start",
                user_id=user_id,
                top_k=5
            )

            chunks = vector_store.search(
                question,
                top_k=5,
                filter={"user_id": user_id}
            )

            log_step(
                "rag_query",
                "vector_search_done",
                user_id=user_id,
                chunks_found=len(chunks)
            )

            if not chunks:
                answer = "No relevant content found in your uploaded documents. Upload some first."
                citations = []
                input_tokens = 0
                output_tokens = 0

                log_step(
                    "rag_query",
                    "no_relevant_chunks",
                    user_id=user_id
                )

            else:
                log_step(
                    "rag_query",
                    "build_prompt_start",
                    user_id=user_id
                )

                context = "\n\n".join(
                    f"[chunk {i+1}] {c['text']}"
                    for i, c in enumerate(chunks)
                )

                prompt = PROMPT_TEMPLATE.format(
                    context=context,
                    question=question
                )

                log_step(
                    "rag_query",
                    "build_prompt_done",
                    user_id=user_id,
                    prompt_chars=len(prompt)
                )

                log_step(
                    "rag_query",
                    "ai_invoke_start",
                    user_id=user_id
                )

                answer = ai_client.invoke(prompt, max_tokens=512)

                log_step(
                    "rag_query",
                    "ai_invoke_done",
                    user_id=user_id,
                    answer_chars=len(answer)
                )

                citations = [
                    {
                        "chunk": i + 1,
                        "doc_id": c["doc_id"],
                        "score": c["score"],
                        "text": c["text"][:200]
                    }
                    for i, c in enumerate(chunks)
                ]

                input_tokens = len(prompt.split())
                output_tokens = len(answer.split())

        latency_ms = int((time.time() - start_time) * 1000)
        total_tokens = input_tokens + output_tokens

        log_step(
            "rag_query",
            "save_query_history_start",
            user_id=user_id
        )

        userstore.log_query(user_id=user_id, query=question, answer=answer)

        log_step(
            "rag_query",
            "save_query_history_done",
            user_id=user_id
        )

        log_event(
            "RAG_QUERY",
            user_id=user_id,
            question=question,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            citations_count=len(citations),
            vector_backend=vector_backend,
            status="success"
        )

        log_step(
            "rag_query",
            "query_completed",
            user_id=user_id,
            latency_ms=latency_ms,
            status="success"
        )

        return {
            "question": question,
            "answer": answer,
            "citations": citations
        }

    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)

        log_event(
            "RAG_ERROR",
            user_id=user_id,
            question=question,
            latency_ms=latency_ms,
            error_type=type(e).__name__,
            error_message=str(e),
            stack_trace=traceback.format_exc(),
            status="error"
        )

        log_step(
            "rag_query",
            "query_failed",
            user_id=user_id,
            question=question,
            latency_ms=latency_ms,
            error_type=type(e).__name__,
            status="error"
        )

        raise


def handle_list_docs(user_id: str, userstore) -> dict:
    log_step(
        "list_docs",
        "list_docs_start",
        user_id=user_id
    )

    docs = userstore.list_docs(user_id)

    log_step(
        "list_docs",
        "list_docs_done",
        user_id=user_id,
        docs_count=len(docs)
    )

    return {"user_id": user_id, "docs": docs}


def handle_recent_queries(user_id: str, userstore, limit: int = 10) -> dict:
    log_step(
        "recent_queries",
        "recent_queries_start",
        user_id=user_id,
        limit=limit
    )

    queries = userstore.recent_queries(user_id, limit=limit)

    log_step(
        "recent_queries",
        "recent_queries_done",
        user_id=user_id,
        queries_count=len(queries)
    )

    return {"user_id": user_id, "queries": queries}


# ── Teammate feature: chunking strategy evaluation ────────────────────────

def handle_evaluate(
    user_id: str,
    doc_id: str,
    storage,
    userstore,
    vector_store,
    strategy: Optional[str] = None,
    size: Optional[int] = None,
    overlap: Optional[int] = None,
    threshold: Optional[float] = None,
) -> dict:
    start_time = time.time()

    log_step(
        "evaluate",
        "evaluate_start",
        user_id=user_id,
        doc_id=doc_id,
        strategy=strategy or "default"
    )

    try:
        log_step(
            "evaluate",
            "find_document_start",
            user_id=user_id,
            doc_id=doc_id
        )

        docs = userstore.list_docs(user_id)
        doc = next((d for d in docs if d["doc_id"] == doc_id), None)

        if not doc:
            raise ValueError(f"Document {doc_id} not found for user {user_id}")

        filename = doc.get("filename", "unknown")

        log_step(
            "evaluate",
            "find_document_done",
            user_id=user_id,
            doc_id=doc_id,
            filename=filename
        )

        key = f"{user_id}/{doc_id}/{filename}"

        log_step(
            "evaluate",
            "retrieve_document_start",
            user_id=user_id,
            doc_id=doc_id,
            key=key
        )

        data = storage.get(key)
        text = _extract_text(filename, data)

        log_step(
            "evaluate",
            "retrieve_document_done",
            user_id=user_id,
            doc_id=doc_id,
            chars_extracted=len(text)
        )

        if strategy:
            log_step(
                "evaluate",
                "reingest_start",
                user_id=user_id,
                doc_id=doc_id,
                strategy=strategy,
                size=size,
                overlap=overlap,
                threshold=threshold
            )

            if hasattr(vector_store, "clear_doc"):
                vector_store.clear_doc(doc_id)

            if text.strip():
                vector_store.ingest(
                    doc_id=doc_id,
                    text=text,
                    metadata={"user_id": user_id, "filename": filename},
                    strategy=strategy,
                    size=size,
                    overlap=overlap,
                    threshold=threshold,
                )

            log_step(
                "evaluate",
                "reingest_done",
                user_id=user_id,
                doc_id=doc_id
            )

        probe_questions = [
            {
                "query": "What is the chemical equation for photosynthesis?",
                "keywords": ["6 co2", "6 h2o", "c6h12o6", "light energy"],
            },
            {
                "query": "Where does photosynthesis occur in leaves?",
                "keywords": ["chloroplasts", "chlorophyll", "pigment", "palisade"],
            },
            {
                "query": "What happens during the light-dependent phase?",
                "keywords": ["split water", "photolysis", "nadp", "nadph", "grana"],
            },
            {
                "query": "What are the three main factors affecting photosynthesis?",
                "keywords": ["light intensity", "carbon dioxide", "temperature"],
            },
            {
                "query": "What is the global average rate of energy capture by photosynthesis today?",
                "keywords": ["130 terawatts", "six times", "human civilization", "civilisation"],
            },
        ]

        queries_results = []
        rr_scores = []

        p_at_1_list = []
        p_at_3_list = []
        p_at_5_list = []

        r_at_1_list = []
        r_at_3_list = []
        r_at_5_list = []

        log_step(
            "evaluate",
            "probe_questions_start",
            user_id=user_id,
            doc_id=doc_id,
            total_probe_questions=len(probe_questions)
        )

        for index, item in enumerate(probe_questions, start=1):
            q = item["query"]
            keywords = item["keywords"]

            log_step(
                "evaluate",
                "probe_question_search_start",
                user_id=user_id,
                doc_id=doc_id,
                probe_index=index,
                query=q
            )

            chunks = vector_store.search(q, top_k=5, filter={"user_id": user_id})
            if not chunks and hasattr(vector_store, "kb_id"):
                # Fallback for legacy Bedrock KB files that don't have metadata sidecars
                chunks = vector_store.search(q, top_k=5, filter=None)

            log_step(
                "evaluate",
                "probe_question_search_done",
                user_id=user_id,
                doc_id=doc_id,
                probe_index=index,
                chunks_found=len(chunks)
            )

            retrieved_items = []
            rr = 0.0

            for idx, c in enumerate(chunks):
                text_lower = c["text"].lower()
                is_relevant = any(kw in text_lower for kw in keywords)

                retrieved_items.append({
                    "chunk": idx + 1,
                    "text": c["text"],
                    "score": c["score"],
                    "relevant": is_relevant,
                })

                if is_relevant and rr == 0.0:
                    rr = 1.0 / (idx + 1)

            rr_scores.append(rr)

            def calc_metrics(k: int):
                sub = retrieved_items[:k]
                relevant_count = sum(1 for x in sub if x["relevant"])
                precision = relevant_count / k
                recall = 1.0 if relevant_count > 0 else 0.0
                return precision, recall

            p1, r1 = calc_metrics(1)
            p3, r3 = calc_metrics(3)
            p5, r5 = calc_metrics(5)

            p_at_1_list.append(p1)
            p_at_3_list.append(p3)
            p_at_5_list.append(p5)

            r_at_1_list.append(r1)
            r_at_3_list.append(r3)
            r_at_5_list.append(r5)

            queries_results.append({
                "query": q,
                "keywords": keywords,
                "retrieved": retrieved_items,
                "metrics": {
                    "precision_at_1": p1,
                    "precision_at_3": p3,
                    "precision_at_5": p5,
                    "recall_at_1": r1,
                    "recall_at_3": r3,
                    "recall_at_5": r5,
                    "mrr": rr,
                },
            })

        avg_p_at_1 = sum(p_at_1_list) / len(p_at_1_list)
        avg_p_at_3 = sum(p_at_3_list) / len(p_at_3_list)
        avg_p_at_5 = sum(p_at_5_list) / len(p_at_5_list)

        avg_r_at_1 = sum(r_at_1_list) / len(r_at_1_list)
        avg_r_at_3 = sum(r_at_3_list) / len(r_at_3_list)
        avg_r_at_5 = sum(r_at_5_list) / len(r_at_5_list)

        avg_mrr = sum(rr_scores) / len(rr_scores)

        total_chunks = -1
        if hasattr(vector_store, "docs"):
            total_chunks = len([
                d for d in vector_store.docs
                if d[2].get("doc_id") == doc_id
            ])

        latency_ms = int((time.time() - start_time) * 1000)

        log_event(
            "EVALUATE_RESULT",
            user_id=user_id,
            doc_id=doc_id,
            filename=filename,
            strategy_used=strategy or "default",
            num_chunks_total=total_chunks,
            precision_at_1=avg_p_at_1,
            precision_at_3=avg_p_at_3,
            precision_at_5=avg_p_at_5,
            recall_at_1=avg_r_at_1,
            recall_at_3=avg_r_at_3,
            recall_at_5=avg_r_at_5,
            mrr=avg_mrr,
            latency_ms=latency_ms,
            status="success"
        )

        log_step(
            "evaluate",
            "evaluate_done",
            user_id=user_id,
            doc_id=doc_id,
            latency_ms=latency_ms,
            status="success"
        )

        return {
            "doc_id": doc_id,
            "filename": filename,
            "strategy_used": strategy or "default",
            "num_chunks_total": total_chunks,
            "metrics": {
                "precision_at_1": avg_p_at_1,
                "precision_at_3": avg_p_at_3,
                "precision_at_5": avg_p_at_5,
                "recall_at_1": avg_r_at_1,
                "recall_at_3": avg_r_at_3,
                "recall_at_5": avg_r_at_5,
                "mrr": avg_mrr,
            },
            "queries": queries_results,
        }
    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)

        log_event(
            "EVALUATE_ERROR",
            user_id=user_id,
            doc_id=doc_id,
            latency_ms=latency_ms,
            error_type=type(e).__name__,
            error_message=str(e),
            stack_trace=traceback.format_exc(),
            status="error"
        )

        log_step(
            "evaluate",
            "evaluate_failed",
            user_id=user_id,
            doc_id=doc_id,
            latency_ms=latency_ms,
            error_type=type(e).__name__,
            status="error"
        )

        raise


def handle_delete_doc(
    user_id: str,
    doc_id: str,
    storage,
    userstore,
    vector_store,
) -> dict:
    """Delete a document from userstore, storage, and clear it from vector store."""
    docs = userstore.list_docs(user_id)
    doc = next((d for d in docs if d["doc_id"] == doc_id), None)
    if not doc:
        raise ValueError(f"Document {doc_id} not found for user {user_id}")

    filename = doc.get("filename", "unknown")
    key = f"{user_id}/{doc_id}/{filename}"

    # 1. Delete from storage
    try:
        storage.delete(key)
    except Exception:
        pass
    try:
        storage.delete(key + ".metadata.json")
    except Exception:
        pass

    # 2. Delete from UserStore
    userstore.delete_doc(user_id, doc_id)

    # 3. Clear from Vector store
    if hasattr(vector_store, "clear_doc"):
        vector_store.clear_doc(doc_id)

    # 4. If using Bedrock KB, trigger a sync so Bedrock deletes embeddings of the deleted S3 file
    if hasattr(vector_store, "kb_id"):
        try:
            import boto3
            from botocore.config import Config
            # Use a fast timeout (2.0s) so the Lambda doesn't hang if the bedrock-agent control plane endpoint
            # is unreachable from the isolated private subnet VPC (since there is no VPC endpoint for bedrock-agent)
            config = Config(connect_timeout=2.0, read_timeout=2.0, retries={"max_attempts": 0})
            client = boto3.client("bedrock-agent", region_name=vector_store.agent_runtime.meta.region_name, config=config)
            ds_resp = client.list_data_sources(knowledgeBaseId=vector_store.kb_id)
            ds_summaries = ds_resp.get("dataSourceSummaries", [])
            if ds_summaries:
                ds_id = ds_summaries[0]["dataSourceId"]
                client.start_ingestion_job(
                    knowledgeBaseId=vector_store.kb_id,
                    dataSourceId=ds_id
                )
        except Exception:
            pass

    return {"status": "success", "message": f"Document {filename} deleted successfully"}


# ── Quiz feature ───────────────────────────────────────────────────────────

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
    storage=None,
) -> dict:
    """Generate a multiple-choice quiz from the user's uploaded documents.

    Flow:
      1. If doc_id given → fetch full text from storage for that source (precise).
         If no doc_id → retrieve chunks from vector store across all user docs.
      2. Build a quiz-generation prompt with the retrieved context.
      3. Call AI to produce a JSON array of questions.
      4. Parse + validate the response.
      5. Persist the quiz in userstore and return it.
    """
    start_time = time.time()

    difficulty = difficulty.lower()
    if difficulty not in _VALID_DIFFICULTIES:
        difficulty = "medium"
    num_questions = max(1, min(num_questions, 20))  # clamp 1-20

    log_step("quiz", "quiz_start", user_id=user_id, doc_id=doc_id,
             difficulty=difficulty, num_questions=num_questions)

    # --- 1. Retrieve context ---
    context = ""
    resolved_doc_id = doc_id or "all"

    if doc_id and storage:
        # Scoped to a specific doc: pull full text directly from storage
        # so the quiz covers the entire source, not just indexed chunks.
        docs = userstore.list_docs(user_id)
        doc_meta = next((d for d in docs if d["doc_id"] == doc_id), None)

        if not doc_meta:
            return {
                "quiz_id": None,
                "doc_id": doc_id,
                "difficulty": difficulty,
                "num_questions": 0,
                "questions": [],
                "error": f"Document {doc_id} not found.",
            }

        filename = doc_meta.get("filename", "unknown")
        key = f"{user_id}/{doc_id}/{filename}"
        try:
            data = storage.get(key)
            text = _extract_text(filename, data)
            if text.strip():
                # Chunk the text to stay within token limits
                from src import chunker as _chunker
                chunks_text = _chunker.chunk_fixed(text, size=500, overlap=100)
                # Take up to 10 chunks for context
                context = "\n\n".join(
                    f"[chunk {i+1}] {c}" for i, c in enumerate(chunks_text[:10])
                )
        except Exception as e:
            log_event("QUIZ_STORAGE_FALLBACK", user_id=user_id, doc_id=doc_id,
                      error=str(e))
            # Fall through to vector search fallback below

    if not context:
        # Fallback: vector search (used when no doc_id, or storage fetch failed)
        search_filter: dict = {"user_id": user_id}
        if doc_id:
            search_filter["doc_id"] = doc_id

        if vector_backend == "bedrock_kb":
            chunks = vector_store.search(
                query="key concepts definitions important facts",
                top_k=10,
                filter=search_filter,
            )
        else:
            chunks = vector_store.search(
                query="key concepts definitions important facts",
                top_k=10,
                filter=search_filter,
            )
            if not chunks:
                chunks = vector_store.search(query="", top_k=10, filter=search_filter)

        if not chunks:
            return {
                "quiz_id": None,
                "doc_id": resolved_doc_id,
                "difficulty": difficulty,
                "num_questions": 0,
                "questions": [],
                "error": "No content found. Upload a document first.",
            }

        context = "\n\n".join(f"[chunk {i+1}] {c['text']}" for i, c in enumerate(chunks))

    log_step("quiz", "context_ready", user_id=user_id, doc_id=resolved_doc_id,
             context_chars=len(context))

    # --- 2. Build prompt ---
    prompt = QUIZ_PROMPT_TEMPLATE.format(
        num_questions=num_questions,
        difficulty=difficulty,
        context=context,
    )

    # --- 3. Call AI ---
    log_step("quiz", "ai_invoke_start", user_id=user_id)
    raw = ai_client.generate_quiz(prompt, max_tokens=2048, temperature=0.4)
    log_step("quiz", "ai_invoke_done", user_id=user_id, raw_chars=len(raw))

    # --- 4. Parse JSON ---
    questions = _parse_quiz_json(raw)

    # --- 5. Persist + return ---
    quiz_id = str(uuid.uuid4())
    userstore.save_quiz(
        user_id=user_id,
        quiz_id=quiz_id,
        doc_id=resolved_doc_id,
        difficulty=difficulty,
        questions=questions,
    )

    latency_ms = int((time.time() - start_time) * 1000)
    log_event("QUIZ_GENERATED", user_id=user_id, quiz_id=quiz_id,
              doc_id=resolved_doc_id, difficulty=difficulty,
              num_questions=len(questions), latency_ms=latency_ms, status="success")

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
