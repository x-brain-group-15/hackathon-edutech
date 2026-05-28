"""Environment-driven configuration. Read all settings from env vars — no hardcoded service names."""
import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default)


@dataclass(frozen=True)
class Config:
    # AI
    ai_backend: str = _env("AI_BACKEND", "local")
    ai_model_id: str = _env("AI_MODEL_ID", "apac.anthropic.claude-3-5-sonnet-20240620-v1:0")
    ai_model_fallbacks: str = _env(
        "AI_MODEL_FALLBACKS",
        "anthropic.claude-sonnet-4-5-20250929-v1:0,"
        "amazon.nova-2-lite-v1:0,"
        "amazon.nova-lite-v1:0,"
        "anthropic.claude-haiku-4-5-20251001-v1:0,"
        "anthropic.claude-sonnet-4-6,"
        "amazon.nova-pro-v1:0,"
        "anthropic.claude-3-haiku-20240307-v1:0"
    )
    aws_region: str = _env("AWS_REGION", "ap-southeast-1")

    # Storage
    storage_backend: str = _env("STORAGE_BACKEND", "local")
    storage_bucket: str = _env("STORAGE_BUCKET", "")
    storage_local_dir: str = _env("STORAGE_LOCAL_DIR", "./_data/uploads")
    flashcard_bucket: str = _env("FLASHCARD_BUCKET", "")

    # UserStore
    userstore_backend: str = _env("USERSTORE_BACKEND", "sqlite")
    userstore_table: str = _env("USERSTORE_TABLE", "")
    userstore_postgres_url: str = _env("USERSTORE_POSTGRES_URL", "")
    userstore_sqlite_path: str = _env("USERSTORE_SQLITE_PATH", "./_data/users.db")

    # Vector
    vector_backend: str = _env("VECTOR_BACKEND", "local")
    vector_bedrock_kb_id: str = _env("VECTOR_BEDROCK_KB_ID", "")

    # Chunking
    chunking_strategy: str = _env("CHUNKING_STRATEGY", "fixed")
    chunk_size: int = int(_env("CHUNK_SIZE", "500"))
    chunk_overlap: int = int(_env("CHUNK_OVERLAP", "100"))
    semantic_threshold: float = float(_env("SEMANTIC_THRESHOLD", "0.3"))

    # Identity
    default_user_id: str = _env("DEFAULT_USER_ID", "test-user-001")

    # Logging
    log_level: str = _env("LOG_LEVEL", "INFO")


    # Frontend serving (opt-out so backend can be pure API for split deploys)
    serve_frontend: bool = _env("SERVE_FRONTEND", "true").lower() == "true"
    cors_origins: str = _env("CORS_ORIGINS", "*")

    # Extra DB backends (DocumentDB, MySQL)
    userstore_mongo_url: str = _env("USERSTORE_MONGO_URL", "")
    userstore_mongo_db: str = _env("USERSTORE_MONGO_DB", "studybot")
    userstore_mongo_tls_ca: str = _env("USERSTORE_MONGO_TLS_CA", "")
    userstore_mysql_url: str = _env("USERSTORE_MYSQL_URL", "")

config = Config()
