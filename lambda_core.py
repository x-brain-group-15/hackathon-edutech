"""Lambda handler — Core / lightweight routes.

Routes: /health, /docs/list, /queries/recent
Timeout: 15s | Memory: 256MB
"""
from mangum import Mangum
from fastapi import FastAPI, Header
from fastapi.middleware.cors import CORSMiddleware

from src.config import config
from src.adapters import factory
from src import handlers

app = FastAPI(title="StudyBot — Core")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

userstore = factory.make_userstore()


def _uid(x_user_id):
    return x_user_id or config.default_user_id


@app.get("/health")
def health():
    return {
        "status": "ok",
        "backends": {
            "ai": config.ai_backend,
            "storage": config.storage_backend,
            "userstore": config.userstore_backend,
            "vector": config.vector_backend,
        },
    }


@app.get("/docs/list")
def list_docs(x_user_id: str | None = Header(default=None)):
    return handlers.handle_list_docs(_uid(x_user_id), userstore)


@app.get("/queries/recent")
def recent(x_user_id: str | None = Header(default=None), limit: int = 10):
    return handlers.handle_recent_queries(_uid(x_user_id), userstore, limit=limit)


handler = Mangum(app, lifespan="off")
