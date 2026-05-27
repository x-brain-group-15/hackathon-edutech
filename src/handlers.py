"""Endpoint handlers. Pure business logic — knows nothing about FastAPI or AWS specifics."""
import io
import uuid
import json
import time
import logging
import traceback
from typing import Optional

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def log_event(event_type: str, **kwargs):
    logger.info(json.dumps({
        "event_type": event_type,
        **kwargs
    }, ensure_ascii=False))

PROMPT_TEMPLATE = """You are a study assistant. Answer the student's question using ONLY the
context retrieved from their uploaded lecture notes. Cite the source by chunk
number where possible. If the context does not contain the answer, say so
plainly. Do not invent information.

CONTEXT:
{context}

QUESTION: {question}

ANSWER:"""


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

    try:
        if vector_backend == "bedrock_kb":
            result = ai_client.retrieve_and_generate(
                query=question,
                kb_id=bedrock_kb_id
            )

            answer = result["answer"]
            citations = result.get("citations", [])

            input_tokens = result.get("input_tokens", 0)
            output_tokens = result.get("output_tokens", 0)

        else:
            chunks = vector_store.search(
                question,
                top_k=5,
                filter={"user_id": user_id}
            )

            if not chunks:
                answer = "No relevant content found in your uploaded documents. Upload some first."
                citations = []
                input_tokens = 0
                output_tokens = 0

            else:
                context = "\n\n".join(
                    f"[chunk {i+1}] {c['text']}"
                    for i, c in enumerate(chunks)
                )

                prompt = PROMPT_TEMPLATE.format(
                    context=context,
                    question=question
                )

                answer = ai_client.invoke(prompt, max_tokens=512)

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

        userstore.log_query(user_id=user_id, query=question, answer=answer)

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

        raise


def handle_list_docs(user_id: str, userstore) -> dict:
    return {"user_id": user_id, "docs": userstore.list_docs(user_id)}


def handle_recent_queries(user_id: str, userstore, limit: int = 10) -> dict:
    return {"user_id": user_id, "queries": userstore.recent_queries(user_id, limit=limit)}
