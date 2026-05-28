"""Endpoint handlers. Pure business logic — knows nothing about FastAPI or AWS specifics."""
import uuid
import json
import time
import logging
import re
import hashlib
import random
import traceback
from typing import Optional

from src.config import config
from src.pdf_extractor import extract_pdf

logger = logging.getLogger()
logger.setLevel(getattr(logging, config.log_level.upper(), logging.INFO))


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


FLASHCARD_PROMPT = """You are a study assistant. Generate {limit} flashcards for the topic: "{topic}".
Base the flashcards ONLY on the provided context if available. 
Return the output STRICTLY as a JSON array of objects, where each object has "front" (the question) and "back" (the answer). Do NOT include any markdown code blocks, text, or explanation before or after the JSON array.

CONTEXT:
{context}
"""

SOCRATIC_PROMPT = """You are a Socratic tutor assisting a student based on their lecture notes.
Your goal is to guide the student to discover the answer themselves through thought-provoking leading questions, rather than giving the answer directly.

Guidelines:
1. NEVER give the direct answer to the student's question.
2. Formulate your response as a gentle, encouraging question or series of short prompts that guide their logic based ONLY on the provided context.
3. Be supportive, friendly, and act like a wise professor.
4. Keep your responses relatively short (under 4 sentences).

Context from lecture notes:
{context}

Student's Question: {question}

Response:"""

MINDMAP_PROMPT = """You are a study assistant. Analyze the provided lecture notes and generate an interactive mind-map of the core concepts in the Mermaid.js `mindmap` diagram format.

Guidelines:
1. Start your response EXACTLY with `mindmap` (no header, no other text).
2. Use valid Mermaid.js `mindmap` syntax. Example syntax:
mindmap
  root((Photosynthesis))
    Light Reactions
      Inputs
        Water
        Light
      Outputs
        Oxygen
        ATP
        NADPH
    Calvin Cycle
      Inputs
        CO2
        ATP
        NADPH
      Outputs
        G3P Sugar
3. Do NOT use any special characters like parentheses, brackets, or quotes in node names unless escaped. Keep node names short (1-4 words).
4. Focus on the most important testable concepts and structural connections in the lecture notes.
5. Return ONLY the raw code block starting with `mindmap` and ending with the final node. Do NOT wrap it in markdown code blocks like ```mermaid. Just output the raw mermaid code directly.

LECTURE NOTES:
{context}
"""

CORNELL_PROMPT = """You are a study assistant. Analyze the provided lecture notes and generate a highly structured study guide in the prestigious Cornell Note-taking format.

Your response must be returned strictly as a JSON object with the following three fields:
1. "cues": a list of objects, each containing "keyword" (a key question, formula, or cue term) and "association" (what section or concept it points to). Generate at least 5 cues.
2. "notes": a list of detailed, structured study points (bullet points, structured facts, definitions, or equations) matching the cues on the left. Generate at least 5 points.
3. "summary": a concise, 2-3 sentence summary summarizing the absolute core takeaway of the entire lecture.

Return the output STRICTLY as a raw JSON object. Do NOT wrap it in markdown code blocks or add any text before or after the JSON.

LECTURE NOTES:
{context}
"""

QUIZ_PROMPT = """You are a practice quiz generator for a student.
Create exactly {num_questions} multiple-choice questions from ONLY the lecture-note context below.

Return STRICTLY a raw JSON array. Do not include markdown fences, labels, commentary, or text before or after the JSON.
Each array item must match this schema:
{{
  "id": "short-stable-id",
  "question": "question text",
  "options": ["option A", "option B", "option C", "option D"],
  "correct_answer": "the exact option text that is correct",
  "explanation": "brief explanation grounded in the context"
}}

Rules:
- Use 4 options per question.
- Exactly one option must match correct_answer.
- Do not invent facts outside the context.
- Keep questions clear and testable.

LECTURE-NOTE CONTEXT:
{context}
"""

CHUNK_SUMMARY_PROMPT = """You are a study assistant. Read the following excerpt from a lecture document and extract the key knowledge points.

Return a concise bullet-point summary of the most important facts, definitions, and concepts in this excerpt. Be specific and factual. Do not add information not present in the text.

EXCERPT:
{chunk}

KEY POINTS:"""

QUIZ_FROM_SUMMARY_PROMPT = """You are a practice quiz generator for a student.
Create exactly {num_questions} multiple-choice questions based ONLY on the summarized lecture notes below.

Return STRICTLY a raw JSON array. Do not include markdown fences, labels, commentary, or text before or after the JSON.
Each array item must match this schema:
{{
  "id": "short-stable-id",
  "question": "question text",
  "options": ["option A", "option B", "option C", "option D"],
  "correct_answer": "the exact option text that is correct",
  "explanation": "brief explanation grounded in the notes"
}}

Rules:
- Use 4 options per question.
- Exactly one option must match correct_answer.
- Do not invent facts outside the notes.
- Keep questions clear and testable.
- Spread questions across different topics in the notes.

SUMMARIZED LECTURE NOTES:
{context}
"""

def _put_cloudwatch_metric(metric_name: str, value: float, unit: str, aws_region: str, status: str = "Success"):
    """Real-world scenario: Put custom metrics to CloudWatch to monitor AI operations."""
    try:
        import boto3
        cw = boto3.client("cloudwatch", region_name=aws_region)
        cw.put_metric_data(
            Namespace="StudyBot",
            MetricData=[
                {
                    "MetricName": metric_name,
                    "Value": value,
                    "Unit": unit,
                    "Dimensions": [
                        {"Name": "Feature", "Value": "FlashcardGeneration"},
                        {"Name": "Status", "Value": status}
                    ]
                }
            ]
        )
    except Exception as e:
        # Never fail the user request just because metrics failed to publish
        print(f"Failed to put CloudWatch metric: {e}")



def _extract_text(filename: str, data: bytes) -> str:
    """Extract plain text from PDF or .txt upload."""
    if filename.lower().endswith(".pdf"):
        try:
            return extract_pdf(data).text
        except RuntimeError as exc:
            return f"({exc})"
    try:
        return data.decode("utf-8", errors="replace")
    except Exception:
        return ""


def _get_document_text(user_id: str, doc_id: str, filename: str, storage) -> str:
    """Helper to fetch document text. First attempts to read pre-extracted plain text
    from S3 (highly optimized, low-memory), falling back to raw PDF/txt parsing if absent.
    """
    # 1. Try to fetch already-extracted plain text from S3 (highly optimized)
    try:
        txt_key = f"{user_id}/{doc_id}/extracted_text.txt"
        txt_data = storage.get(txt_key)
        return txt_data.decode("utf-8", errors="replace")
    except Exception:
        pass

    # 2. Fall back to parsing the raw file if extracted_text.txt doesn't exist
    try:
        key = f"{user_id}/{doc_id}/{filename}"
        data = storage.get(key)
        return _extract_text(filename, data)
    except Exception as e:
        print(f"Error getting document text for doc_id {doc_id}: {e}")
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
    start_time = time.time()
    doc_id = str(uuid.uuid4())
    key = f"{user_id}/{doc_id}/{filename}"

    log_step("upload", "upload_start", user_id=user_id, doc_id=doc_id, filename=filename, size=len(data))

    try:
        log_step("upload", "store_file_start", user_id=user_id, doc_id=doc_id, filename=filename)
        location = storage.put(key, data)
        log_step("upload", "store_file_done", user_id=user_id, doc_id=doc_id, filename=filename, location=location)

        # Write companion metadata.json for Bedrock KB multi-tenant filtering
        try:
            import json
            metadata_json = {
                "metadataAttributes": {
                    "user_id": user_id,
                    "doc_id": doc_id,
                    "filename": filename,
                }
            }
            storage.put(key + ".metadata.json", json.dumps(metadata_json).encode("utf-8"))
        except Exception:
            pass

        extraction_metadata = {}
        log_step("upload", "extract_text_start", user_id=user_id, doc_id=doc_id, filename=filename)
        if filename.lower().endswith(".pdf"):
            asset_prefix = f"{user_id}/{doc_id}/extracted-assets"

            def write_image_asset(asset_filename: str, asset_data: bytes) -> str:
                return storage.put(f"{asset_prefix}/{asset_filename}", asset_data)

            extracted = extract_pdf(data, image_writer=write_image_asset)
            text = extracted.text
            extraction_metadata = extracted.metadata
            extraction_metadata["asset_prefix"] = asset_prefix
        else:
            text = _extract_text(filename, data)
        log_step("upload", "extract_text_done", user_id=user_id, doc_id=doc_id, filename=filename, chars_extracted=len(text))

        # Save pre-extracted plain text to S3 for lightning-fast, OOM-free future retrieval by other features
        try:
            storage.put(f"{user_id}/{doc_id}/extracted_text.txt", text.encode("utf-8"))
        except Exception as text_save_err:
            log_step("upload", "save_extracted_text_failed", error=str(text_save_err))

        if text.strip():
            log_step("upload", "vector_ingest_start", user_id=user_id, doc_id=doc_id, filename=filename, strategy=strategy or "default")
            vector_store.ingest(
                doc_id=doc_id,
                text=text,
                metadata={
                    "user_id": user_id,
                    "filename": filename,
                    "extraction_strategy": extraction_metadata.get("strategy", "plain_text"),
                    "asset_prefix": extraction_metadata.get("asset_prefix", ""),
                },
                strategy=strategy,
                size=size,
                overlap=overlap,
                threshold=threshold,
            )
            log_step("upload", "vector_ingest_done", user_id=user_id, doc_id=doc_id, filename=filename, strategy=strategy or "default")
        else:
            log_step("upload", "vector_ingest_skipped", user_id=user_id, doc_id=doc_id, filename=filename, message="No text extracted from document")

        log_step("upload", "save_metadata_start", user_id=user_id, doc_id=doc_id, filename=filename)
        userstore.add_doc(
            user_id=user_id,
            doc_id=doc_id,
            metadata={
                "filename": filename,
                "size": len(data),
                "location": location,
                "chars": len(text),
                "extraction": extraction_metadata,
            },
        )
        log_step("upload", "save_metadata_done", user_id=user_id, doc_id=doc_id, filename=filename)

        latency_ms = int((time.time() - start_time) * 1000)

        log_event(
            "DOCUMENT_UPLOAD",
            user_id=user_id,
            doc_id=doc_id,
            filename=filename,
            size=len(data),
            chars_extracted=len(text),
            images_extracted=extraction_metadata.get("images_extracted", 0),
            pages_requiring_ocr=extraction_metadata.get("pages_requiring_ocr", []),
            location=location,
            status="success",
        )

        log_step("upload", "upload_completed", user_id=user_id, doc_id=doc_id, filename=filename, latency_ms=latency_ms, status="success")

        return {
            "doc_id": doc_id,
            "filename": filename,
            "size": len(data),
            "chars_extracted": len(text),
            "location": location,
            "extraction": extraction_metadata,
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
            status="error",
        )

        log_step(
            "upload",
            "upload_failed",
            user_id=user_id,
            doc_id=doc_id,
            filename=filename,
            latency_ms=latency_ms,
            error_type=type(e).__name__,
            message=str(e),
            status="error",
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
    socratic: bool = False,
) -> dict:
    """RAG flow: retrieve user's relevant chunks → call AI with context → log + return."""

    start_time = time.time()

    log_step(
        "rag_query",
        "query_received",
        user_id=user_id,
        question=question,
        vector_backend=vector_backend,
        socratic=socratic
    )

    try:
        if socratic:
            log_step(
                "rag_query",
                "socratic_mode_start",
                user_id=user_id
            )
            
            # Retrieve chunks
            chunks = []
            if vector_backend == "bedrock_kb":
                log_step(
                    "rag_query",
                    "bedrock_retrieve_start",
                    user_id=user_id,
                    kb_id=bedrock_kb_id
                )
                try:
                    ret_res = ai_client.agent_runtime.retrieve(
                        knowledgeBaseId=bedrock_kb_id,
                        retrievalQuery={"text": question},
                        retrievalConfiguration={
                            "vectorSearchConfiguration": {
                                "numberOfResults": 5
                            }
                        }
                    )
                    for i, r in enumerate(ret_res.get("retrievalResults", [])):
                        chunks.append({
                            "text": r["content"]["text"],
                            "chunk": i + 1,
                            "score": r.get("score", 0),
                        })
                except Exception as e:
                    logger.warning(f"Bedrock KB retrieve failed, falling back to local vector: {e}")
                    try:
                        from src.adapters.factory import _local_vector_singleton
                        if _local_vector_singleton:
                            chunks = _local_vector_singleton.search(
                                question,
                                top_k=5,
                                filter={"user_id": user_id}
                            )
                    except Exception as le:
                        logger.warning(f"Local vector fallback failed: {le}")
            else:
                try:
                    chunks = vector_store.search(
                        question,
                        top_k=5,
                        filter={"user_id": user_id}
                    )
                except Exception as e:
                    logger.warning(f"Local vector search failed: {e}")

            if not chunks:
                prompt = SOCRATIC_PROMPT.format(
                    context="",
                    question=question
                )
                answer = ai_client.invoke(prompt, max_tokens=512)
                citations = []
            else:
                context = "\n\n".join(
                    f"[chunk {c.get('chunk', i+1)}] {c['text']}"
                    for i, c in enumerate(chunks)
                )
                prompt = SOCRATIC_PROMPT.format(
                    context=context,
                    question=question
                )
                answer = ai_client.invoke(prompt, max_tokens=512)
                
                citations = []
                for c in chunks:
                    citations.append({
                        "chunk": c.get("chunk", 1),
                        "score": c.get("score", 1.0),
                        "text": c["text"],
                    })

            latency_ms = int((time.time() - start_time) * 1000)
            _put_cloudwatch_metric("SocraticQueryLatency", latency_ms, "Milliseconds", "ap-southeast-1", "Success")
            
            try:
                userstore.log_query(user_id, question, answer, doc_id=None)
            except Exception:
                pass

            return {"answer": answer, "citations": citations}

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
                prompt = PROMPT_TEMPLATE.format(
                    context="",
                    question=question
                )
                answer = ai_client.invoke(prompt, max_tokens=512)
                citations = []
                input_tokens = len(prompt.split())
                output_tokens = len(answer.split())

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


def _clean_json_response(response: str) -> str:
    clean_json = response.strip()
    if clean_json.startswith("```json"):
        clean_json = clean_json[7:]
    elif clean_json.startswith("```"):
        clean_json = clean_json[3:]
    if clean_json.endswith("```"):
        clean_json = clean_json[:-3]
    return clean_json.strip()


def _normalize_quiz_items(raw_items, num_questions: int) -> list[dict]:
    if not isinstance(raw_items, list):
        raise ValueError("Quiz model response must be a JSON array")

    normalized = []
    for index, item in enumerate(raw_items[:num_questions], start=1):
        if not isinstance(item, dict):
            continue

        options = item.get("options") or []
        if not isinstance(options, list):
            continue
        options = [str(option).strip() for option in options if str(option).strip()]
        if len(options) < 2:
            continue

        correct_answer = item.get("correct_answer", item.get("answer"))
        if isinstance(correct_answer, int):
            correct_answer = options[correct_answer] if 0 <= correct_answer < len(options) else ""
        correct_answer = str(correct_answer or "").strip()
        if correct_answer not in options:
            continue

        options = _randomize_options(options, correct_answer)

        normalized.append({
            "id": str(item.get("id") or f"q{index}"),
            "question": str(item.get("question") or "").strip(),
            "options": options,
            "correct_answer": correct_answer,
            "explanation": str(item.get("explanation") or "").strip(),
        })

    if not normalized:
        raise ValueError("Quiz model response did not contain valid quiz items")
    return _avoid_all_correct_answers_at_a(normalized)


def _is_bedrock_fallback_error(exc: Exception) -> bool:
    message = str(exc)
    return (
        "ThrottlingException" in message
        or "Too many tokens per day" in message
        or "Too many requests" in message
        or "rate exceeded" in message.lower()
        or "NoCredentialsError" in message
        or "Unable to locate credentials" in message
        or "ExpiredToken" in message
        or "UnrecognizedClientException" in message
    )


def _hash_int(value: str) -> int:
    return int(hashlib.sha256(value.encode("utf-8")).hexdigest()[:12], 16)


def _randomize_options(options: list[str], correct_answer: str) -> list[str]:
    clean_options = _dedupe_preserve_order(options)
    distractors = [option for option in clean_options if option != correct_answer]
    selected = [correct_answer, *distractors[:3]]
    random.SystemRandom().shuffle(selected)
    return selected


def _avoid_all_correct_answers_at_a(quiz_items: list[dict]) -> list[dict]:
    if len(quiz_items) < 2:
        return quiz_items
    if any(item["options"].index(item["correct_answer"]) != 0 for item in quiz_items):
        return quiz_items

    for offset, item in enumerate(quiz_items[1:], start=1):
        options = item["options"]
        if len(options) > 1:
            target_index = offset % len(options)
            options[0], options[target_index] = options[target_index], options[0]
    return quiz_items


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        clean = re.sub(r"\s+", " ", item).strip()
        if not clean:
            continue
        key = clean.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(clean)
    return result


def _is_clean_quiz_text(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    blocked_patterns = ("{|", "|-", "||", "cellspacing=", "style=", "_url:", "_source:")
    if any(pattern in stripped.lower() for pattern in blocked_patterns):
        return False
    if sum(1 for char in stripped if char == "|") >= 2:
        return False
    return True


def _deterministic_shuffle(items: list[str], seed: str) -> list[str]:
    return sorted(items, key=lambda item: _hash_int(f"{seed}:{item}"))


def _spread_select(items: list, limit: int) -> list:
    if len(items) <= limit:
        return items
    selected = []
    for i in range(limit):
        idx = round(i * (len(items) - 1) / max(limit - 1, 1))
        selected.append(items[idx])
    return selected


def _make_options(correct: str, distractor_pool: list[str], seed: str) -> list[str]:
    distractors = [
        item for item in _dedupe_preserve_order(distractor_pool)
        if item.lower() != correct.lower() and _is_clean_quiz_text(item)
    ]
    distractors = _deterministic_shuffle(distractors, seed)[:3]
    generic_distractors = [
        "It is not the best match for the selected notes.",
        "It describes an unrelated concept.",
        "It reverses the relationship described in the notes.",
        "It is only a formatting detail, not the core idea.",
    ]
    for item in generic_distractors:
        if len(distractors) >= 3:
            break
        if item.lower() != correct.lower() and item not in distractors:
            distractors.append(item)

    return _randomize_options([correct, *distractors[:3]], correct)


def _extract_quiz_facts(chunks: list[dict]) -> tuple[list[dict], list[str]]:
    raw_text = "\n".join(chunk.get("text", "") for chunk in chunks)
    lines = [re.sub(r"\s+", " ", line).strip() for line in raw_text.splitlines()]
    lines = [line for line in lines if line and _is_clean_quiz_text(line)]
    sentences = [
        re.sub(r"\s+", " ", sentence).strip()
        for sentence in re.split(r"(?<=[.!?])\s+", raw_text)
        if 35 <= len(sentence.strip()) <= 260 and _is_clean_quiz_text(sentence)
    ]

    facts = []

    for line in lines:
        match = re.match(r"^[-*]?\s*([^:|]{2,60}):\s+(.{12,220})$", line)
        if match:
            term = match.group(1).strip(" -_*")
            description = match.group(2).strip(" -_*")
            if not term.lower().startswith(("http", "source", "url")):
                facts.append({
                    "kind": "definition",
                    "topic": term,
                    "answer": description,
                    "question": f"In the selected notes, what does '{term}' refer to?",
                    "source": line,
                })

    for sentence in sentences:
        match = re.match(r"^([A-Z][A-Za-z0-9 /()'\\-]{2,70})\s+(is|are|means|refers to)\s+(.{15,180})$", sentence)
        if match:
            topic = match.group(1).strip()
            answer = sentence.rstrip(".")
            facts.append({
                "kind": "concept",
                "topic": topic,
                "answer": answer,
                "question": f"What is the best description of {topic}?",
                "source": sentence,
            })

    for sentence in sentences:
        lowered = sentence.lower()
        if any(marker in lowered for marker in (" used ", " uses ", " occurs ", " includes ", " produces ", " converts ", " solves ")):
            topic_match = re.match(r"^(.{3,70}?)(?:\s+is|\s+are|\s+uses|\s+used|\s+occurs|\s+includes|\s+produces|\s+converts|\s+solves)\b", sentence)
            topic = topic_match.group(1).strip(" .:-") if topic_match else "this concept"
            facts.append({
                "kind": "relationship",
                "topic": topic,
                "answer": sentence.rstrip("."),
                "question": f"Which statement best matches the notes about {topic}?",
                "source": sentence,
            })

    for sentence in sentences:
        if sentence not in [fact["answer"] for fact in facts]:
            keyword = sentence.split(" ", 5)[:5]
            topic = " ".join(keyword).strip(" .:-")
            facts.append({
                "kind": "fact",
                "topic": topic or "the selected notes",
                "answer": sentence.rstrip("."),
                "question": f"Which statement is supported by the selected notes about {topic}?",
                "source": sentence,
            })

    facts = [
        fact for fact in facts
        if 10 <= len(fact["answer"]) <= 220
        and len(fact["question"]) <= 180
        and _is_clean_quiz_text(fact["answer"])
    ]
    seen_answers = set()
    unique_facts = []
    for fact in facts:
        key = fact["answer"].lower()
        if key in seen_answers:
            continue
        seen_answers.add(key)
        unique_facts.append(fact)

    distractor_pool = [fact["answer"] for fact in unique_facts] + sentences
    return unique_facts, _dedupe_preserve_order(distractor_pool)


def _fallback_quiz_from_chunks(chunks: list[dict], num_questions: int) -> list[dict]:
    facts, distractor_pool = _extract_quiz_facts(chunks)
    selected_facts = _spread_select(facts, num_questions)

    fallback_items = []
    for index, fact in enumerate(selected_facts, start=1):
        correct_answer = fact["answer"][:180].rstrip()
        seed = f"{index}:{fact['question']}:{correct_answer}"
        options = _make_options(correct_answer, distractor_pool, seed)

        fallback_items.append({
            "id": f"fallback-q{index}",
            "question": fact["question"],
            "options": options,
            "correct_answer": correct_answer,
            "explanation": f"Based on the selected notes: {fact['source'][:220]}",
        })

    if not fallback_items:
        raise ValueError("Quiz fallback could not find enough document text to generate questions")
    return _avoid_all_correct_answers_at_a(fallback_items)


def handle_generate_quiz(
    user_id: str,
    num_questions: int,
    doc_id: Optional[str],
    vector_store,
    ai_client,
    userstore,
    storage=None,
) -> list[dict]:
    start_time = time.time()
    num_questions = max(1, min(num_questions, 20))

    # Resolve filename from userstore when doc_id is provided
    filename = None
    if doc_id and userstore:
        docs = userstore.list_docs(user_id)
        doc = next((d for d in docs if d.get("doc_id") == doc_id), None)
        if doc:
            filename = doc.get("filename", "unknown")

    # Step 1: Fetch document text from S3
    context = ""
    if doc_id and storage is not None and filename:
        log_step("generate_quiz", "s3_fetch_start", user_id=user_id, doc_id=doc_id, filename=filename)
        try:
            context = _get_document_text(user_id, doc_id, filename, storage)
            log_step("generate_quiz", "s3_fetch_done", user_id=user_id, doc_id=doc_id, chars=len(context))
        except Exception as e:
            log_step("generate_quiz", "s3_fetch_failed", user_id=user_id, doc_id=doc_id, error=str(e))
            logger.warning(f"Quiz S3 fetch failed for {doc_id}: {e}")

    if not context.strip():
        log_step("generate_quiz", "no_content", user_id=user_id, doc_id=doc_id)
        raise ValueError("No document content found. Upload a document before generating a quiz.")

    # Step 2: Chunk the document using semantic chunking (best for topic-aware splitting)
    from src.chunker import chunk_semantic, chunk_fixed
    log_step("generate_quiz", "chunking_start", user_id=user_id, doc_id=doc_id, chars=len(context))
    chunks = chunk_semantic(context, threshold=0.25)
    # If semantic chunking produces too few or too many chunks, fall back to fixed
    if len(chunks) < 2 or len(chunks) > 50:
        chunks = chunk_fixed(context, size=800, overlap=100)
    log_step("generate_quiz", "chunking_done", user_id=user_id, doc_id=doc_id, num_chunks=len(chunks))

    # Step 3 (Map): Summarize each chunk into bullet-point key knowledge
    log_step("generate_quiz", "map_summarize_start", user_id=user_id, doc_id=doc_id, num_chunks=len(chunks))
    summaries = []
    for i, chunk in enumerate(chunks):
        if not chunk.strip():
            continue
        try:
            prompt = CHUNK_SUMMARY_PROMPT.format(chunk=chunk)
            summary = ai_client.invoke(prompt, max_tokens=512, temperature=0.1)
            summaries.append(summary.strip())
            log_step("generate_quiz", "chunk_summarized", user_id=user_id, chunk_index=i, summary_chars=len(summary))
        except Exception as e:
            logger.warning(f"Quiz map: chunk {i} summarization failed: {e}")
            log_step("generate_quiz", "chunk_summarize_fallback", user_id=user_id, chunk_index=i, error=str(e))
            # Fall back to using the raw chunk text
            summaries.append(chunk.strip())

    if not summaries:
        raise ValueError("Failed to summarize document content for quiz generation.")

    log_step("generate_quiz", "map_summarize_done", user_id=user_id, doc_id=doc_id, num_summaries=len(summaries))

    # Step 4 (Reduce): Combine all summaries and generate quiz
    combined_summary = "\n\n".join(
        f"--- Section {i+1} ---\n{s}" for i, s in enumerate(summaries)
    )
    log_step(
        "generate_quiz",
        "reduce_quiz_start",
        user_id=user_id,
        doc_id=doc_id,
        summary_chars=len(combined_summary),
    )

    prompt = QUIZ_FROM_SUMMARY_PROMPT.format(
        num_questions=num_questions,
        context=combined_summary,
    )

    try:
        if hasattr(ai_client, "generate_quiz_from_kb"):
            response = ai_client.generate_quiz_from_kb(prompt, max_tokens=2048, temperature=0.1)
        else:
            response = ai_client.invoke(prompt, max_tokens=2048, temperature=0.1)
    except Exception as e:
        if not _is_bedrock_fallback_error(e):
            raise
        logger.warning(f"Bedrock unavailable during quiz generation; using rule-based fallback: {e}")
        fallback_chunks = [{"text": s} for s in summaries]
        quiz_items = _fallback_quiz_from_chunks(fallback_chunks, num_questions)
        latency_ms = int((time.time() - start_time) * 1000)
        log_event(
            "QUIZ_GENERATED",
            user_id=user_id,
            doc_id=doc_id,
            requested_questions=num_questions,
            returned_questions=len(quiz_items),
            latency_ms=latency_ms,
            status="fallback_throttled",
        )
        return {"quiz": quiz_items, "saved": False}

    raw_items = json.loads(_clean_json_response(response))
    quiz_items = _normalize_quiz_items(raw_items, num_questions)
    log_step("generate_quiz", "reduce_quiz_done", user_id=user_id, doc_id=doc_id, num_questions=len(quiz_items))

    latency_ms = int((time.time() - start_time) * 1000)
    try:
        userstore.log_query(
            user_id=user_id,
            query=f"Generate practice quiz ({len(quiz_items)} questions)",
            answer=json.dumps(quiz_items, ensure_ascii=False),
        )
    except Exception:
        pass

    log_event(
        "QUIZ_GENERATED",
        user_id=user_id,
        doc_id=doc_id,
        requested_questions=num_questions,
        returned_questions=len(quiz_items),
        context_chars=len(context),
        num_chunks=len(chunks),
        latency_ms=latency_ms,
        status="success",
    )

    # Save quiz to S3 if bucket is configured and doc_id is provided
    saved = False
    if doc_id and config.flashcard_bucket:
        try:
            import boto3
            s3 = boto3.client("s3", region_name=config.aws_region)
            key = f"{user_id}/quiz/{doc_id}.json"
            s3.put_object(
                Bucket=config.flashcard_bucket,
                Key=key,
                Body=json.dumps(quiz_items, ensure_ascii=False).encode("utf-8"),
                ContentType="application/json",
            )
            saved = True
            log_step("generate_quiz", "s3_save_done", user_id=user_id, doc_id=doc_id, key=key)
        except Exception as e:
            logger.warning(f"Quiz S3 save failed for {doc_id}: {e}")

    log_step("generate_quiz", "quiz_completed", user_id=user_id, doc_id=doc_id, latency_ms=latency_ms, status="success")
    return {"quiz": quiz_items, "saved": saved}


def handle_get_quiz(user_id: str, doc_id: str) -> dict:
    """Load a previously saved quiz from S3. Returns empty list if not found or bucket not configured."""
    if not config.flashcard_bucket:
        return {"doc_id": doc_id, "quiz": []}
    try:
        import boto3
        s3 = boto3.client("s3", region_name=config.aws_region)
        key = f"{user_id}/quiz/{doc_id}.json"
        resp = s3.get_object(Bucket=config.flashcard_bucket, Key=key)
        quiz_items = json.loads(resp["Body"].read().decode("utf-8"))
        log_step("get_quiz", "s3_load_done", user_id=user_id, doc_id=doc_id, count=len(quiz_items))
        return {"doc_id": doc_id, "quiz": quiz_items}
    except Exception as e:
        if "NoSuchKey" in str(type(e).__name__) or "NoSuchKey" in str(e):
            return {"doc_id": doc_id, "quiz": []}
        logger.warning(f"Quiz S3 load failed for {doc_id}: {e}")
        return {"doc_id": doc_id, "quiz": []}


def handle_delete_doc(
    user_id: str,
    doc_id: str,
    storage,
    userstore,
    vector_store,
) -> dict:
    """Delete a document: remove from storage, vector store, and userstore."""

    start_time = time.time()

    log_step(
        "delete_doc",
        "delete_doc_start",
        user_id=user_id,
        doc_id=doc_id,
    )

    try:
        # 1. Find the document metadata to get the filename / S3 key
        docs = userstore.list_docs(user_id)
        doc = next((d for d in docs if d["doc_id"] == doc_id), None)

        if not doc:
            raise ValueError(f"Document {doc_id} not found for user {user_id}")

        filename = doc.get("filename", "unknown")
        key = f"{user_id}/{doc_id}/{filename}"

        log_step(
            "delete_doc",
            "found_document",
            user_id=user_id,
            doc_id=doc_id,
            filename=filename,
        )

        # 2. Delete from object storage (best-effort — don't crash if missing)
        try:
            storage.delete(key)
            log_step("delete_doc", "storage_deleted", user_id=user_id, doc_id=doc_id, key=key)
        except Exception as e:
            logger.warning(f"Storage delete failed for {key}: {e}")

        # 3. Delete chunks from vector store (best-effort)
        try:
            if hasattr(vector_store, "clear_doc"):
                vector_store.clear_doc(doc_id)
                log_step("delete_doc", "vector_cleared", user_id=user_id, doc_id=doc_id)
        except Exception as e:
            logger.warning(f"Vector store clear_doc failed for {doc_id}: {e}")

        # 4. Remove from userstore
        userstore.delete_doc(user_id=user_id, doc_id=doc_id)

        latency_ms = int((time.time() - start_time) * 1000)

        log_event(
            "DOCUMENT_DELETE",
            user_id=user_id,
            doc_id=doc_id,
            filename=filename,
            latency_ms=latency_ms,
            status="success",
        )

        log_step(
            "delete_doc",
            "delete_doc_done",
            user_id=user_id,
            doc_id=doc_id,
            latency_ms=latency_ms,
            status="success",
        )

        return {"doc_id": doc_id, "deleted": True}

    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)

        log_event(
            "DELETE_ERROR",
            user_id=user_id,
            doc_id=doc_id,
            latency_ms=latency_ms,
            error_type=type(e).__name__,
            error_message=str(e),
            stack_trace=traceback.format_exc(),
            status="error",
        )

        raise


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

        text = _get_document_text(user_id, doc_id, filename, storage)

        log_step(
            "evaluate",
            "retrieve_document_done",
            user_id=user_id,
            doc_id=doc_id,
            chars_extracted=len(text)
        )

        # ── Always use a local in-memory index for evaluation ───────────────────
        # Bedrock KB is async (ingestion may not have completed) and has no
        # per-document isolation when metadata sidecars are missing.
        # We build a fresh LocalVector from the doc text so results are
        # deterministic and isolated to this exact document + strategy.
        from src.adapters.vector import LocalVector
        eval_store = LocalVector()
        if text.strip():
            eval_store.ingest(
                doc_id=doc_id,
                text=text,
                metadata={"user_id": user_id, "doc_id": doc_id, "filename": filename},
                strategy=strategy,
                size=size,
                overlap=overlap,
                threshold=threshold,
            )

        num_chunks_total = len(eval_store.docs)

        # Also trigger Bedrock KB sync in the background (best-effort, fire-and-forget)
        if text.strip() and hasattr(vector_store, "kb_id"):
            try:
                vector_store.ingest(
                    doc_id=doc_id,
                    text=text,
                    metadata={"user_id": user_id, "doc_id": doc_id, "filename": filename},
                    strategy=strategy,
                    size=size,
                    overlap=overlap,
                    threshold=threshold,
                )
            except Exception:
                pass

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

            # Search the temporary local eval store — always accurate & isolated
            chunks = eval_store.search(q, top_k=5, filter={"doc_id": doc_id})

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

        # Use the count from our local eval_store (always accurate)
        total_chunks = num_chunks_total


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

        raise


def handle_generate_flashcards(
    user_id: str,
    topic: str,
    limit: int,
    doc_id: Optional[str],
    vector_store,
    ai_client,
    aws_region: str
) -> dict:
    start_time = time.time()
    try:
        context = ""
        if doc_id:
            results = vector_store.search(query=topic, top_k=10, filter={"doc_id": doc_id})
            context = "\n\n".join(r["text"] for r in results)
        
        prompt = FLASHCARD_PROMPT.format(limit=limit, topic=topic, context=context)
        response = ai_client.invoke(prompt, max_tokens=1024)
        
        # Clean JSON markdown
        clean_json = response.strip()
        if clean_json.startswith("```json"):
            clean_json = clean_json[7:]
        elif clean_json.startswith("```"):
            clean_json = clean_json[3:]
        if clean_json.endswith("```"):
            clean_json = clean_json[:-3]
        clean_json = clean_json.strip()
        
        flashcards = json.loads(clean_json)
        
        latency_ms = int((time.time() - start_time) * 1000)
        _put_cloudwatch_metric("FlashcardGenerationLatency", latency_ms, "Milliseconds", "ap-southeast-1", "Success")
        _put_cloudwatch_metric("FlashcardGenerationSuccess", 1, "Count", "ap-southeast-1", "Success")
        
        return {"flashcards": flashcards}
    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)
        _put_cloudwatch_metric("FlashcardGenerationFailure", 1, "Count", "ap-southeast-1", "Failed")
        print(f"Error generating flashcards: {e}")
        traceback.print_exc()
        raise


def handle_generate_mindmap(
    user_id: str,
    doc_id: str,
    storage,
    userstore,
    ai_client,
) -> dict:
    """Read document text -> invoke Bedrock to generate Mermaid mindmap."""
    start_time = time.time()
    try:
        docs = userstore.list_docs(user_id)
        doc = next((d for d in docs if d["doc_id"] == doc_id), None)
        if not doc:
            raise ValueError(f"Document {doc_id} not found for user {user_id}")
            
        filename = doc.get("filename", "unknown")
        text = _get_document_text(user_id, doc_id, filename, storage)
        
        if not text.strip():
            raise ValueError("Document has no text content to build a mind-map.")
            
        prompt = MINDMAP_PROMPT.format(context=text[:6000])
        response = ai_client.invoke(prompt, max_tokens=1024)
        
        mindmap_code = response.strip()
        # Clean any accidental wrapping codeblocks
        if mindmap_code.startswith("```mermaid"):
            mindmap_code = mindmap_code[10:]
        elif mindmap_code.startswith("```"):
            mindmap_code = mindmap_code[3:]
        if mindmap_code.endswith("```"):
            mindmap_code = mindmap_code[:-3]
        mindmap_code = mindmap_code.strip()
        
        latency_ms = int((time.time() - start_time) * 1000)
        _put_cloudwatch_metric("MindMapGenerationLatency", latency_ms, "Milliseconds", "ap-southeast-1", "Success")
        
        return {
            "doc_id": doc_id,
            "filename": filename,
            "mindmap": mindmap_code
        }
    except Exception as e:
        print(f"Error generating mindmap: {e}")
        traceback.print_exc()
        raise


def handle_generate_cornell(
    user_id: str,
    doc_id: str,
    storage,
    userstore,
    ai_client,
) -> dict:
    """Read document text -> invoke Bedrock to generate Cornell Notes structured JSON."""
    start_time = time.time()
    try:
        docs = userstore.list_docs(user_id)
        doc = next((d for d in docs if d["doc_id"] == doc_id), None)
        if not doc:
            raise ValueError(f"Document {doc_id} not found for user {user_id}")
            
        filename = doc.get("filename", "unknown")
        text = _get_document_text(user_id, doc_id, filename, storage)
        
        if not text.strip():
            raise ValueError("Document has no text content to build Cornell notes.")
            
        prompt = CORNELL_PROMPT.format(context=text[:6000])
        response = ai_client.invoke(prompt, max_tokens=1500)
        
        clean_json = response.strip()
        if clean_json.startswith("```json"):
            clean_json = clean_json[7:]
        elif clean_json.startswith("```"):
            clean_json = clean_json[3:]
        if clean_json.endswith("```"):
            clean_json = clean_json[:-3]
        clean_json = clean_json.strip()
        
        cornell_data = json.loads(clean_json)
        
        latency_ms = int((time.time() - start_time) * 1000)
        _put_cloudwatch_metric("CornellGenerationLatency", latency_ms, "Milliseconds", "ap-southeast-1", "Success")
        
        return {
            "doc_id": doc_id,
            "filename": filename,
            "cornell": cornell_data
        }
    except Exception as e:
        print(f"Error generating Cornell notes: {e}")
        traceback.print_exc()
        raise
