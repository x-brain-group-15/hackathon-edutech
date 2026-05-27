"""Endpoint handlers. Pure business logic — knows nothing about FastAPI or AWS specifics."""
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
    """Store the file, extract text, ingest into vector store, record in userstore."""
    doc_id = str(uuid.uuid4())
    key = f"{user_id}/{doc_id}/{filename}"
    location = storage.put(key, data)
    extraction_metadata = {}
    if filename.lower().endswith(".pdf"):
        image_output_dir = Path(config.storage_local_dir) / "extracted_assets" / doc_id
        extracted = extract_pdf(data, image_output_dir=image_output_dir)
        text = extracted.text
        extraction_metadata = extracted.metadata
    else:
        text = _extract_text(filename, data)
    if text.strip():
        vector_store.ingest(
            doc_id=doc_id,
            text=text,
            metadata={
                "user_id": user_id,
                "filename": filename,
                "extraction_strategy": extraction_metadata.get("strategy", "plain_text"),
            },
            strategy=strategy,
            size=size,
            overlap=overlap,
            threshold=threshold,
        )
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
        "extraction": extraction_metadata,
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
    # 1. Find document in userstore
    docs = userstore.list_docs(user_id)
    doc = next((d for d in docs if d["doc_id"] == doc_id), None)
    if not doc:
        raise ValueError(f"Document {doc_id} not found for user {user_id}")

    filename = doc.get("filename", "unknown")

    # 2. Retrieve original text from storage
    key = f"{user_id}/{doc_id}/{filename}"
    try:
        data = storage.get(key)
        text = _extract_text(filename, data)
    except Exception as e:
        raise ValueError(f"Failed to retrieve document content: {str(e)}")

    # 3. Dynamic Re-ingestion: Clear vector index and re-ingest if custom strategy parameters are specified
    if strategy:
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

    # 4. Run the 5 probe questions
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

    for item in probe_questions:
        q = item["query"]
        keywords = item["keywords"]

        # Search up to top 5 chunks
        chunks = vector_store.search(q, top_k=5, filter={"user_id": user_id})

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
        total_chunks = len([d for d in vector_store.docs if d[2].get("doc_id") == doc_id])

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


