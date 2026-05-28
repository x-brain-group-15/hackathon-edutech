"""Lambda handler — Upload & Document management.

Routes: /upload, DELETE /docs/{doc_id}, /docs/{doc_id}/evaluate
Timeout: 120s | Memory: 1024MB
"""
from mangum import Mangum
from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from src.config import config
from src.adapters import factory
from src import handlers
from src.handlers import logger

_allowed = ["*"] if config.cors_origins == "*" else [o.strip() for o in config.cors_origins.split(",") if o.strip()]

app = FastAPI(title="StudyBot — Upload")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

storage = factory.make_storage()
userstore = factory.make_userstore()
vector_store = factory.make_vector()


def _uid(x_user_id):
    return x_user_id or config.default_user_id


class EvaluateRequest(BaseModel):
    strategy: Optional[str] = None
    size: Optional[int] = None
    overlap: Optional[int] = None
    threshold: Optional[float] = None


@app.post("/upload")
async def upload(
    file: UploadFile = File(...),
    strategy: str | None = None,
    size: int | None = None,
    overlap: int | None = None,
    threshold: float | None = None,
    x_user_id: str | None = Header(default=None),
) -> dict:
    user_id = _uid(x_user_id)
    data = await file.read()
    if not data:
        logger.warning(f"[/upload] Empty file user={user_id} filename={file.filename}")
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


@app.post("/docs/{doc_id}/evaluate")
def evaluate(
    doc_id: str,
    req: EvaluateRequest,
    x_user_id: str | None = Header(default=None),
) -> dict:
    user_id = _uid(x_user_id)
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
        logger.warning(f"[/docs/{doc_id}/evaluate] Not found user={user_id}: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"[/docs/{doc_id}/evaluate] Unexpected error user={user_id}: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/docs/{doc_id}")
def delete_doc(doc_id: str, x_user_id: str | None = Header(default=None)) -> dict:
    user_id = _uid(x_user_id)
    try:
        return handlers.handle_delete_doc(
            user_id=user_id,
            doc_id=doc_id,
            storage=storage,
            userstore=userstore,
            vector_store=vector_store,
        )
    except ValueError as e:
        logger.warning(f"[/docs/{doc_id} DELETE] Not found user={user_id}: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"[/docs/{doc_id} DELETE] Unexpected error user={user_id}: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


handler = Mangum(app, lifespan="off")
