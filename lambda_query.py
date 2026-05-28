"""Lambda handler — Query & AI features.

Routes: /query, /flashcards, /quiz, /docs/{doc_id}/mindmap, /docs/{doc_id}/cornell
Timeout: 60s | Memory: 512MB
"""
from mangum import Mangum
from fastapi import Body, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.config import config
from src.adapters import factory
from src import handlers
from src.handlers import log_step, log_event, logger

_allowed = ["*"] if config.cors_origins == "*" else [o.strip() for o in config.cors_origins.split(",") if o.strip()]

app = FastAPI(title="StudyBot — Query")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ai_client = factory.make_ai()
userstore = factory.make_userstore()
vector_store = factory.make_vector()
storage = factory.make_storage()


def _uid(x_user_id):
    return x_user_id or config.default_user_id


class QueryRequest(BaseModel):
    question: str
    socratic: bool = False


class FlashcardRequest(BaseModel):
    topic: str
    limit: int = 5
    doc_id: str | None = None


class QuizRequest(BaseModel):
    num_questions: int = 5
    doc_id: str | None = None


@app.post("/query")
def query(req: QueryRequest, x_user_id: str | None = Header(default=None)) -> dict:
    user_id = _uid(x_user_id)
    if not req.question.strip():
        logger.warning(f"[/query] Empty question user={user_id}")
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
        logger.error(f"[/query] Unexpected error user={user_id}: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@app.post("/flashcards")
def generate_flashcards(req: FlashcardRequest, x_user_id: str | None = Header(default=None)) -> dict:
    user_id = _uid(x_user_id)
    if not req.topic.strip():
        logger.warning(f"[/flashcards] Empty topic user={user_id}")
        raise HTTPException(status_code=400, detail="Empty topic")
    return handlers.handle_generate_flashcards(
        user_id=user_id,
        topic=req.topic,
        limit=req.limit,
        doc_id=req.doc_id,
        vector_store=vector_store,
        ai_client=ai_client,
        aws_region=config.aws_region,
    )


@app.post("/quiz")
def generate_quiz(
    req: QuizRequest | None = Body(default=None),
    x_user_id: str | None = Header(default=None),
    num_questions: int = 5,
    doc_id: str | None = None,
) -> dict:
    user_id = _uid(x_user_id)
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
            storage=storage,
        )
    except ValueError as e:
        logger.warning(f"[/quiz] Validation error user={user_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[/quiz] Unexpected error user={user_id}: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@app.get("/quiz/{doc_id}")
def get_quiz(doc_id: str, x_user_id: str | None = Header(default=None)) -> dict:
    user_id = _uid(x_user_id)
    return handlers.handle_get_quiz(user_id=user_id, doc_id=doc_id)


@app.post("/docs/{doc_id}/mindmap")
def generate_mindmap(doc_id: str, x_user_id: str | None = Header(default=None)) -> dict:
    user_id = _uid(x_user_id)
    try:
        return handlers.handle_generate_mindmap(
            user_id=user_id,
            doc_id=doc_id,
            storage=storage,
            userstore=userstore,
            ai_client=ai_client,
        )
    except ValueError as e:
        logger.warning(f"[/docs/{doc_id}/mindmap] Not found user={user_id}: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"[/docs/{doc_id}/mindmap] Unexpected error user={user_id}: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/docs/{doc_id}/cornell")
def generate_cornell(doc_id: str, x_user_id: str | None = Header(default=None)) -> dict:
    user_id = _uid(x_user_id)
    try:
        return handlers.handle_generate_cornell(
            user_id=user_id,
            doc_id=doc_id,
            storage=storage,
            userstore=userstore,
            ai_client=ai_client,
        )
    except ValueError as e:
        logger.warning(f"[/docs/{doc_id}/cornell] Not found user={user_id}: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"[/docs/{doc_id}/cornell] Unexpected error user={user_id}: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


handler = Mangum(app, lifespan="off")
