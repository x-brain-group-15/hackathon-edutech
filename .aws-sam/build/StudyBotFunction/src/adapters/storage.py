"""Object storage adapters. Pick via STORAGE_BACKEND env var.

Interface:
    put(key, data) -> str (returns location URI)
    get(key) -> bytes
    list(prefix="") -> list[str]
"""
from pathlib import Path
from typing import Any


class S3Storage:
    def __init__(self, bucket: str, region: str):
        import boto3
        if not bucket:
            raise ValueError("STORAGE_BUCKET must be set for S3 backend")
        self.s3 = boto3.client("s3", region_name=region)
        self.bucket = bucket

    def put(self, key: str, data: bytes) -> str:
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=data)
        return f"s3://{self.bucket}/{key}"

    def get(self, key: str) -> bytes:
        resp = self.s3.get_object(Bucket=self.bucket, Key=key)
        return resp["Body"].read()

    def list(self, prefix: str = "") -> list:
        resp = self.s3.list_objects_v2(Bucket=self.bucket, Prefix=prefix)
        return [obj["Key"] for obj in resp.get("Contents", [])]


class LocalStorage:
    """Filesystem-based storage. Mirrors S3 API for drop-in replacement."""

    def __init__(self, base_dir: str):
        self.base = Path(base_dir)
        self.base.mkdir(parents=True, exist_ok=True)

    def put(self, key: str, data: bytes) -> str:
        path = self.base / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return f"file://{path.resolve()}"

    def get(self, key: str) -> bytes:
        return (self.base / key).read_bytes()

    def list(self, prefix: str = "") -> list:
        results = []
        for p in self.base.rglob("*"):
            if p.is_file():
                rel = str(p.relative_to(self.base))
                if rel.startswith(prefix):
                    results.append(rel)
        return results
