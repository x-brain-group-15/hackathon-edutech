"""Endpoint handlers. Pure business logic — knows nothing about FastAPI or AWS specifics."""
import uuid
import json
import time
import logging
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
            if vector_backend == "bedrock_kb":
                log_step(
                    "rag_query",
                    "bedrock_retrieve_start",
                    user_id=user_id,
                    kb_id=bedrock_kb_id
                )
                ret_res = ai_client.agent_runtime.retrieve(
                    knowledgeBaseId=bedrock_kb_id,
                    retrievalQuery={"text": question},
                    retrievalConfiguration={
                        "vectorSearchConfiguration": {
                            "numberOfResults": 5
                        }
                    }
                )
                chunks = []
                for i, r in enumerate(ret_res.get("retrievalResults", [])):
                    chunks.append({
                        "text": r["content"]["text"],
                        "chunk": i + 1,
                        "score": r.get("score", 0),
                    })
            else:
                chunks = vector_store.search(
                    question,
                    top_k=5,
                    filter={"user_id": user_id}
                )

            if not chunks:
                answer = "I could not find any context in your uploaded lecture notes to guide you. Please upload a lecture slide first!"
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

        data = storage.get(key)
        text = _extract_text(filename, data)

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
        key = f"{user_id}/{doc_id}/{filename}"
        data = storage.get(key)
        text = _extract_text(filename, data)
        
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
        key = f"{user_id}/{doc_id}/{filename}"
        data = storage.get(key)
        text = _extract_text(filename, data)
        
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
