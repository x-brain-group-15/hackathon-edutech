"""FastAPI application — runtime-agnostic.

Runs on:
  - Local laptop:        uvicorn src.app:app --reload
  - AWS Lambda:          wrap with Mangum (pip install mangum) → expose `handler`
  - ECS Fargate / EC2:   uvicorn or gunicorn
  - App Runner:          uvicorn

The choice is yours. Code stays the same.
"""
from pathlib import Path

from fastapi import Body, FastAPI, File, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.config import config
from src.adapters import factory
from src import handlers


app = FastAPI(title="StudyBot — W7 Capstone Starter")


# CORS — allow frontend to live on a different origin (CloudFront / Amplify / separate ALB).
# CORS_ORIGINS env var controls this; default '*' is permissive for hackathon.
_allowed = ["*"] if config.cors_origins == "*" else [o.strip() for o in config.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Singletons. In serverless this gets re-initialized per cold start; that's fine.
ai_client = factory.make_ai()
storage = factory.make_storage()
userstore = factory.make_userstore()
vector_store = factory.make_vector()


def _resolve_user_id(x_user_id: str | None) -> str:
    """Auth abstraction: extract user_id from header, fall back to default for local dev.

    In production you populate X-User-Id from:
      - Cognito JWT (decoded by API Gateway authorizer)
      - Signed URL claim
      - Custom auth Lambda
    """
    return x_user_id or config.default_user_id


class QueryRequest(BaseModel):
    question: str
    socratic: bool = False


@app.get("/health")
def health() -> dict:
    import os
    aws_env = {}
    for k, v in os.environ.items():
        if k.startswith("AWS_") or "KEY" in k or "SECRET" in k or "TOKEN" in k:
            if len(v) > 8:
                aws_env[k] = f"{v[:4]}...{v[-4:]} (len={len(v)})"
            else:
                aws_env[k] = f"... (len={len(v)})"
    return {
        "status": "ok",
        "backends": {
            "ai": config.ai_backend,
            "storage": config.storage_backend,
            "userstore": config.userstore_backend,
            "vector": config.vector_backend,
        },
        "debug_aws_env": aws_env,
    }


@app.post("/upload")
async def upload(
    file: UploadFile = File(...),
    strategy: str | None = None,
    size: int | None = None,
    overlap: int | None = None,
    threshold: float | None = None,
    x_user_id: str | None = Header(default=None),
) -> dict:
    user_id = _resolve_user_id(x_user_id)
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    return handlers.handle_upload(
        user_id=user_id,
        filename=file.filename or "untitled",
        data=data,
        storage=storage,
        userstore=userstore,
        vector_store=vector_store,
        strategy=strategy,
        size=size,
        overlap=overlap,
        threshold=threshold,
    )


@app.post("/query")
def query(req: QueryRequest, x_user_id: str | None = Header(default=None)) -> dict:
    user_id = _resolve_user_id(x_user_id)
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Empty question")
    try:
        return handlers.handle_query(
            user_id=user_id,
            question=req.question,
            ai_client=ai_client,
            userstore=userstore,
            vector_store=vector_store,
            vector_backend=config.vector_backend,
            bedrock_kb_id=config.vector_bedrock_kb_id,
            socratic=req.socratic,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


class EvaluateRequest(BaseModel):
    strategy: str | None = None
    size: int | None = None
    overlap: int | None = None
    threshold: float | None = None


@app.post("/docs/{doc_id}/evaluate")
def evaluate(
    doc_id: str,
    req: EvaluateRequest,
    x_user_id: str | None = Header(default=None),
) -> dict:
    user_id = _resolve_user_id(x_user_id)
    try:
        return handlers.handle_evaluate(
            user_id=user_id,
            doc_id=doc_id,
            storage=storage,
            userstore=userstore,
            vector_store=vector_store,
            strategy=req.strategy,
            size=req.size,
            overlap=req.overlap,
            threshold=req.threshold,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/docs/{doc_id}")
def delete_doc(doc_id: str, x_user_id: str | None = Header(default=None)) -> dict:
    user_id = _resolve_user_id(x_user_id)
    try:
        return handlers.handle_delete_doc(
            user_id=user_id,
            doc_id=doc_id,
            storage=storage,
            userstore=userstore,
            vector_store=vector_store,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@app.get("/docs/list")
def list_docs(x_user_id: str | None = Header(default=None)) -> dict:
    return handlers.handle_list_docs(_resolve_user_id(x_user_id), userstore)


class FlashcardRequest(BaseModel):
    topic: str
    limit: int = 5
    doc_id: str | None = None


class QuizRequest(BaseModel):
    num_questions: int = 5
    doc_id: str | None = None


@app.post("/quiz")
def generate_quiz(
    req: QuizRequest | None = Body(default=None),
    x_user_id: str | None = Header(default=None),
    num_questions: int = 5,
    doc_id: str | None = None,
) -> list[dict]:
    user_id = _resolve_user_id(x_user_id)
    requested_count = req.num_questions if req else num_questions
    requested_doc_id = req.doc_id if req and req.doc_id else doc_id
    try:
        return handlers.handle_generate_quiz(
            user_id=user_id,
            num_questions=requested_count,
            doc_id=requested_doc_id,
            vector_store=vector_store,
            ai_client=ai_client,
            userstore=userstore,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")

@app.post("/flashcards")
def generate_flashcards(req: FlashcardRequest, x_user_id: str | None = Header(default=None)) -> dict:
    user_id = _resolve_user_id(x_user_id)
    if not req.topic.strip():
        raise HTTPException(status_code=400, detail="Empty topic")
    return handlers.handle_generate_flashcards(
        user_id=user_id,
        topic=req.topic,
        limit=req.limit,
        doc_id=req.doc_id,
        vector_store=vector_store,
        ai_client=ai_client,
        aws_region=config.aws_region
    )

@app.get("/queries/recent")
def recent(x_user_id: str | None = Header(default=None), limit: int = 10) -> dict:
    return handlers.handle_recent_queries(_resolve_user_id(x_user_id), userstore, limit=limit)


@app.post("/docs/{doc_id}/mindmap")
def generate_mindmap(doc_id: str, x_user_id: str | None = Header(default=None)) -> dict:
    user_id = _resolve_user_id(x_user_id)
    try:
        return handlers.handle_generate_mindmap(
            user_id=user_id,
            doc_id=doc_id,
            storage=storage,
            userstore=userstore,
            ai_client=ai_client,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/docs/{doc_id}/cornell")
def generate_cornell(doc_id: str, x_user_id: str | None = Header(default=None)) -> dict:
    user_id = _resolve_user_id(x_user_id)
    try:
        return handlers.handle_generate_cornell(
            user_id=user_id,
            doc_id=doc_id,
            storage=storage,
            userstore=userstore,
            ai_client=ai_client,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---- Static frontend ----
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


if config.serve_frontend:
    @app.get("/")
    def index() -> FileResponse:
        """Convenience: serves frontend/index.html at /. Set SERVE_FRONTEND=false
        if you deploy the frontend separately (CloudFront+S3, Amplify, ALB)."""
        return FileResponse(FRONTEND_DIR / "index.html")

    @app.get("/global.css")
    def global_css() -> FileResponse:
        return FileResponse(FRONTEND_DIR / "global.css", media_type="text/css")
