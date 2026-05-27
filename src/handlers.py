"""Endpoint handlers. Pure business logic — knows nothing about FastAPI or AWS specifics."""
import io
import uuid
import time
import json
from typing import Optional


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


def handle_generate_flashcards(
    user_id: str,
    topic: str,
    limit: int,
    ai_client,
    vector_store,
    aws_region: str
) -> dict:
    """Generate flashcards from user's context and log CloudWatch custom metrics."""
    start_time = time.time()
    
    # 1. Retrieve context based on the topic
    chunks = vector_store.search(topic, top_k=5, filter={"user_id": user_id})
    if not chunks:
        context = "No specific context found. Use general knowledge about the topic."
    else:
        context = "\n\n".join(f"[chunk {i+1}] {c['text']}" for i, c in enumerate(chunks))
        
    prompt = FLASHCARD_PROMPT.format(limit=limit, topic=topic, context=context)
    
    try:
        # 2. Invoke AI model (Bedrock/Local) to generate JSON flashcards
        answer = ai_client.invoke(prompt, max_tokens=2048)
        
        # Simple extraction of JSON from markdown if model returns a code block
        json_str = answer.strip()
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0].strip()
        elif "```" in json_str:
            json_str = json_str.split("```")[1].split("```")[0].strip()
            
        flashcards = json.loads(json_str)
        
        # 3. Put Custom Metrics (Success)
        latency_ms = (time.time() - start_time) * 1000
        _put_cloudwatch_metric("FlashcardGenerationLatency", latency_ms, "Milliseconds", aws_region, "Success")
        _put_cloudwatch_metric("FlashcardsGeneratedCount", len(flashcards), "Count", aws_region, "Success")
        
        return {"topic": topic, "flashcards": flashcards}
        
    except Exception as e:
        # Put Custom Metrics (Failure)
        latency_ms = (time.time() - start_time) * 1000
        _put_cloudwatch_metric("FlashcardGenerationLatency", latency_ms, "Milliseconds", aws_region, "Failure")
        _put_cloudwatch_metric("FlashcardGenerationErrors", 1, "Count", aws_region, "Failure")
        print(f"Error generating flashcards: {e}")
        return {"topic": topic, "error": "Failed to generate flashcards."}
