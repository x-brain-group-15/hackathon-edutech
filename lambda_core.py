"""Lambda handler — Core / lightweight routes.

Routes: /health, /docs/list, /queries/recent
Timeout: 15s | Memory: 256MB
"""
import os

from mangum import Mangum
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from src.config import config
from src.adapters import factory
from src import handlers
from src.handlers import logger

_allowed = ["*"] if config.cors_origins == "*" else [o.strip() for o in config.cors_origins.split(",") if o.strip()]

app = FastAPI(title="StudyBot — Core")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

userstore = factory.make_userstore()


def _uid(x_user_id):
    return x_user_id or config.default_user_id


@app.get("/health")
def health() -> dict:
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


@app.get("/docs/list")
def list_docs(x_user_id: str | None = Header(default=None)) -> dict:
    user_id = _uid(x_user_id)
    try:
        return handlers.handle_list_docs(user_id, userstore)
    except Exception as e:
        logger.error(f"[/docs/list] Unexpected error user={user_id}: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/queries/recent")
def recent(x_user_id: str | None = Header(default=None), limit: int = 10) -> dict:
    user_id = _uid(x_user_id)
    try:
        return handlers.handle_recent_queries(user_id, userstore, limit=limit)
    except Exception as e:
        logger.error(f"[/queries/recent] Unexpected error user={user_id}: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


handler = Mangum(app, lifespan="off")
