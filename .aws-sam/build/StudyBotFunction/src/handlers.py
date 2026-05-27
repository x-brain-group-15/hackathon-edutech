"""Endpoint handlers. Pure business logic — knows nothing about FastAPI or AWS specifics."""
import io
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
