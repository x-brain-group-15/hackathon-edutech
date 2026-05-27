"""User state DB adapters. Pick via USERSTORE_BACKEND env var.

Interface:
    add_doc(user_id, doc_id, metadata: dict) -> None
    list_docs(user_id) -> list[dict]
    log_query(user_id, query, answer) -> None
    recent_queries(user_id, limit=10) -> list[dict]
"""
import json
from datetime import datetime, timezone
from pathlib import Path


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class DynamoDBUserStore:
    """Single-table design: PK=user_id, SK=DOC#<doc_id> or QUERY#<timestamp>."""

    def __init__(self, table_name: str, region: str):
        import boto3
        if not table_name:
            raise ValueError("USERSTORE_TABLE must be set for DynamoDB backend")
        self.table = boto3.resource("dynamodb", region_name=region).Table(table_name)

    def add_doc(self, user_id: str, doc_id: str, metadata: dict) -> None:
        self.table.put_item(
            Item={
                "user_id": user_id,
                "sk": f"DOC#{doc_id}",
                "doc_id": doc_id,
                "created_at": _now(),
                **metadata,
            }
        )

    def list_docs(self, user_id: str) -> list:
        resp = self.table.query(
            KeyConditionExpression="user_id = :u AND begins_with(sk, :p)",
            ExpressionAttributeValues={":u": user_id, ":p": "DOC#"},
        )
        return resp.get("Items", [])

    def log_query(self, user_id: str, query: str, answer: str) -> None:
        ts = _now()
        self.table.put_item(
            Item={
                "user_id": user_id,
                "sk": f"QUERY#{ts}",
                "query": query,
                "answer": answer[:1000],
                "created_at": ts,
            }
        )

    def recent_queries(self, user_id: str, limit: int = 10) -> list:
        resp = self.table.query(
            KeyConditionExpression="user_id = :u AND begins_with(sk, :p)",
            ExpressionAttributeValues={":u": user_id, ":p": "QUERY#"},
            ScanIndexForward=False,
            Limit=limit,
        )
        return resp.get("Items", [])


class PostgresUserStore:
    def __init__(self, url: str):
        try:
            import psycopg2
        except ImportError:
            raise ImportError(
                "psycopg2 not installed. Run: pip install psycopg2-binary"
            )
        if not url:
            raise ValueError("USERSTORE_POSTGRES_URL must be set for Postgres backend")
        self.conn = psycopg2.connect(url)
        self.conn.autocommit = True
        self._init_schema()

    def _init_schema(self):
        with self.conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_docs (
                    user_id TEXT NOT NULL,
                    doc_id TEXT NOT NULL,
                    metadata JSONB,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    PRIMARY KEY (user_id, doc_id)
                );
                CREATE TABLE IF NOT EXISTS user_queries (
                    id SERIAL PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    query TEXT,
                    answer TEXT,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS user_queries_user_idx ON user_queries(user_id, created_at DESC);
            """)

    def add_doc(self, user_id, doc_id, metadata):
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO user_docs (user_id, doc_id, metadata) VALUES (%s, %s, %s) "
                "ON CONFLICT (user_id, doc_id) DO UPDATE SET metadata = EXCLUDED.metadata",
                (user_id, doc_id, json.dumps(metadata)),
            )

    def list_docs(self, user_id):
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT doc_id, metadata, created_at FROM user_docs WHERE user_id = %s ORDER BY created_at DESC",
                (user_id,),
            )
            return [
                {"doc_id": r[0], **(r[1] or {}), "created_at": r[2].isoformat()}
                for r in cur.fetchall()
            ]

    def log_query(self, user_id, query, answer):
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO user_queries (user_id, query, answer) VALUES (%s, %s, %s)",
                (user_id, query, answer[:1000]),
            )

    def recent_queries(self, user_id, limit=10):
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT query, answer, created_at FROM user_queries WHERE user_id = %s "
                "ORDER BY created_at DESC LIMIT %s",
                (user_id, limit),
            )
            return [
                {"query": r[0], "answer": r[1], "created_at": r[2].isoformat()}
                for r in cur.fetchall()
            ]


class SQLiteUserStore:
    """Local dev store. NOT for production — single-file, no concurrency, no scaling."""

    def __init__(self, db_path: str):
        import sqlite3
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init_schema()

    def _init_schema(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS user_docs (
                user_id TEXT NOT NULL,
                doc_id TEXT NOT NULL,
                metadata TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, doc_id)
            );
            CREATE TABLE IF NOT EXISTS user_queries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                query TEXT,
                answer TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS user_queries_user_idx ON user_queries(user_id, created_at DESC);
        """)
        self.conn.commit()

    def add_doc(self, user_id, doc_id, metadata):
        self.conn.execute(
            "INSERT OR REPLACE INTO user_docs (user_id, doc_id, metadata) VALUES (?, ?, ?)",
            (user_id, doc_id, json.dumps(metadata)),
        )
        self.conn.commit()

    def list_docs(self, user_id):
        cur = self.conn.execute(
            "SELECT doc_id, metadata, created_at FROM user_docs WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        )
        return [
            {"doc_id": r[0], **(json.loads(r[1]) if r[1] else {}), "created_at": r[2]}
            for r in cur.fetchall()
        ]

    def log_query(self, user_id, query, answer):
        self.conn.execute(
            "INSERT INTO user_queries (user_id, query, answer) VALUES (?, ?, ?)",
            (user_id, query, answer[:1000]),
        )
        self.conn.commit()

    def recent_queries(self, user_id, limit=10):
        cur = self.conn.execute(
            "SELECT query, answer, created_at FROM user_queries WHERE user_id = ? "
            "ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        )
        return [
            {"query": r[0], "answer": r[1], "created_at": r[2]}
            for r in cur.fetchall()
        ]


class DocumentDBUserStore:
    """MongoDB-compatible store. Works with AWS DocumentDB and MongoDB Atlas.

    DocumentDB requires TLS. Pass USERSTORE_MONGO_TLS_CA env var pointing at the
    AWS RDS CA bundle file (download from AWS docs once).
    """

    def __init__(self, url: str, db_name: str = "studybot", tls_ca_file: str = ""):
        try:
            from pymongo import MongoClient
        except ImportError:
            raise ImportError(
                "pymongo not installed. Run: pip install -r requirements-optional.txt"
            )
        if not url:
            raise ValueError("USERSTORE_MONGO_URL must be set for DocumentDB backend")
        kwargs: dict = {}
        if "documentdb" in url.lower() or tls_ca_file:
            kwargs["tls"] = True
        if tls_ca_file:
            kwargs["tlsCAFile"] = tls_ca_file
        self.client = MongoClient(url, **kwargs)
        self.db = self.client[db_name]
        self.docs = self.db["user_docs"]
        self.queries = self.db["user_queries"]
        self.docs.create_index([("user_id", 1), ("doc_id", 1)], unique=True)
        self.queries.create_index([("user_id", 1), ("created_at", -1)])

    def add_doc(self, user_id: str, doc_id: str, metadata: dict) -> None:
        self.docs.update_one(
            {"user_id": user_id, "doc_id": doc_id},
            {"$set": {**metadata, "user_id": user_id, "doc_id": doc_id, "created_at": _now()}},
            upsert=True,
        )

    def list_docs(self, user_id: str) -> list:
        return [
            {**{k: v for k, v in d.items() if k != "_id"}}
            for d in self.docs.find({"user_id": user_id}).sort("created_at", -1)
        ]

    def log_query(self, user_id: str, query: str, answer: str) -> None:
        self.queries.insert_one({
            "user_id": user_id, "query": query, "answer": answer[:1000], "created_at": _now(),
        })

    def recent_queries(self, user_id: str, limit: int = 10) -> list:
        return [
            {**{k: v for k, v in q.items() if k != "_id"}}
            for q in self.queries.find({"user_id": user_id}).sort("created_at", -1).limit(limit)
        ]


class MySQLUserStore:
    """RDS MySQL / Aurora MySQL adapter via pymysql. Schema mirrors PostgresUserStore."""

    def __init__(self, url: str):
        try:
            import pymysql
            from urllib.parse import urlparse
        except ImportError:
            raise ImportError("pymysql not installed. Run: pip install -r requirements-optional.txt")
        if not url:
            raise ValueError("USERSTORE_MYSQL_URL must be set for MySQL backend")
        p = urlparse(url)
        self.conn = pymysql.connect(
            host=p.hostname,
            port=p.port or 3306,
            user=p.username,
            password=p.password,
            database=p.path.lstrip("/"),
            charset="utf8mb4",
            autocommit=True,
        )
        self._init_schema()

    def _init_schema(self):
        with self.conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_docs (
                    user_id VARCHAR(255) NOT NULL,
                    doc_id VARCHAR(255) NOT NULL,
                    metadata JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, doc_id)
                ) CHARACTER SET utf8mb4
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_queries (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    user_id VARCHAR(255) NOT NULL,
                    query TEXT,
                    answer TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_user_created (user_id, created_at)
                ) CHARACTER SET utf8mb4
            """)

    def add_doc(self, user_id, doc_id, metadata):
        with self.conn.cursor() as cur:
            cur.execute(
                "REPLACE INTO user_docs (user_id, doc_id, metadata) VALUES (%s, %s, %s)",
                (user_id, doc_id, json.dumps(metadata)),
            )

    def list_docs(self, user_id):
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT doc_id, metadata, created_at FROM user_docs WHERE user_id = %s ORDER BY created_at DESC",
                (user_id,),
            )
            return [
                {"doc_id": r[0], **(json.loads(r[1]) if r[1] else {}), "created_at": str(r[2])}
                for r in cur.fetchall()
            ]

    def log_query(self, user_id, query, answer):
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO user_queries (user_id, query, answer) VALUES (%s, %s, %s)",
                (user_id, query, answer[:1000]),
            )

    def recent_queries(self, user_id, limit=10):
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT query, answer, created_at FROM user_queries WHERE user_id = %s "
                "ORDER BY created_at DESC LIMIT %s",
                (user_id, limit),
            )
            return [
                {"query": r[0], "answer": r[1], "created_at": str(r[2])}
                for r in cur.fetchall()
            ]
