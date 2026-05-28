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

app = FastAPI(title="StudyBot — Upload")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
):
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    return handlers.handle_upload(
        user_id=_uid(x_user_id),
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


@app.delete("/docs/{doc_id}")
def delete_doc(doc_id: str, x_user_id: str | None = Header(default=None)):
    try:
        return handlers.handle_delete_doc(
            user_id=_uid(x_user_id),
            doc_id=doc_id,
            storage=storage,
            userstore=userstore,
            vector_store=vector_store,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/docs/{doc_id}/evaluate")
def evaluate(doc_id: str, req: EvaluateRequest, x_user_id: str | None = Header(default=None)):
    try:
        return handlers.handle_evaluate(
            user_id=_uid(x_user_id),
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


handler = Mangum(app, lifespan="off")
