from __future__ import annotations

import json
from typing import Any, Protocol

from app.utils.storage import download_bytes, upload_bytes


class BlobStore(Protocol):
    def upload_bytes(
        self,
        data: bytes,
        gcs_key: str,
        content_type: str = "application/octet-stream",
    ) -> str: ...

    def download_bytes(self, gcs_uri: str) -> bytes: ...

    def upload_json(self, payload: Any, gcs_key: str) -> str: ...

    def download_json(self, gcs_uri: str) -> Any: ...


class GcsBlobStore:
    def upload_bytes(
        self,
        data: bytes,
        gcs_key: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        return upload_bytes(data=data, gcs_key=gcs_key, content_type=content_type)

    def download_bytes(self, gcs_uri: str) -> bytes:
        return download_bytes(gcs_uri)

    def upload_json(self, payload: Any, gcs_key: str) -> str:
        return self.upload_bytes(
            json.dumps(payload, indent=2).encode("utf-8"),
            gcs_key=gcs_key,
            content_type="application/json",
        )

    def download_json(self, gcs_uri: str) -> Any:
        return json.loads(self.download_bytes(gcs_uri).decode("utf-8"))


class InMemoryBlobStore:
    def __init__(self, *, bucket: str = "test-bucket"):
        self.bucket = bucket
        self.objects: dict[str, dict[str, Any]] = {}

    def upload_bytes(
        self,
        data: bytes,
        gcs_key: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        gcs_uri = f"gs://{self.bucket}/{gcs_key}"
        self.objects[gcs_uri] = {
            "data": data,
            "content_type": content_type,
        }
        return gcs_uri

    def download_bytes(self, gcs_uri: str) -> bytes:
        if gcs_uri not in self.objects:
            raise FileNotFoundError(f"Unknown object: {gcs_uri}")
        return self.objects[gcs_uri]["data"]

    def upload_json(self, payload: Any, gcs_key: str) -> str:
        return self.upload_bytes(
            json.dumps(payload, indent=2).encode("utf-8"),
            gcs_key=gcs_key,
            content_type="application/json",
        )

    def download_json(self, gcs_uri: str) -> Any:
        return json.loads(self.download_bytes(gcs_uri).decode("utf-8"))
