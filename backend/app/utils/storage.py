# GCS upload/download helpers
from __future__ import annotations

from pathlib import Path

from app.config import GCS_ALLOW_LOCAL_FALLBACK, GCS_BUCKET, LOCAL_ARTIFACTS_DIR


def _parse_gcs_uri(gcs_uri: str) -> tuple[str, str]:
    if not gcs_uri.startswith("gs://"):
        raise ValueError(f"Invalid GCS URI: {gcs_uri}")

    body = gcs_uri.removeprefix("gs://")
    bucket, _, key = body.partition("/")
    if not bucket or not key:
        raise ValueError(f"Invalid GCS URI: {gcs_uri}")
    return bucket, key


def _build_gcs_uri(bucket: str, key: str) -> str:
    return f"gs://{bucket}/{key}"


def _upload_bytes_local(data: bytes, gcs_key: str) -> str:
    target = Path(LOCAL_ARTIFACTS_DIR) / gcs_key
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return _build_gcs_uri(GCS_BUCKET, gcs_key)


def upload_bytes(data: bytes, gcs_key: str, content_type: str = "application/octet-stream") -> str:
    try:
        from google.cloud import storage  # type: ignore

        client = storage.Client()
        bucket = client.bucket(GCS_BUCKET)
        blob = bucket.blob(gcs_key)
        blob.upload_from_string(data, content_type=content_type)
        return _build_gcs_uri(GCS_BUCKET, gcs_key)
    except Exception as exc:
        if not GCS_ALLOW_LOCAL_FALLBACK:
            raise RuntimeError("GCS upload failed") from exc
        # Optional fallback for local development/testing when cloud deps or credentials are unavailable.
        return _upload_bytes_local(data, gcs_key)


def upload_file(local_path: str, gcs_key: str) -> str:
    data = Path(local_path).read_bytes()
    return upload_bytes(data=data, gcs_key=gcs_key)


def download_file(gcs_uri: str, local_path: str) -> None:
    bucket, key = _parse_gcs_uri(gcs_uri)

    try:
        from google.cloud import storage  # type: ignore

        client = storage.Client()
        blob = client.bucket(bucket).blob(key)
        blob.download_to_filename(local_path)
        return
    except Exception as exc:
        if not GCS_ALLOW_LOCAL_FALLBACK:
            raise RuntimeError(f"GCS download failed for {gcs_uri}") from exc
        fallback_source = Path(LOCAL_ARTIFACTS_DIR) / key
        if not fallback_source.exists():
            raise FileNotFoundError(f"Artifact not found for URI: {gcs_uri}")
        Path(local_path).parent.mkdir(parents=True, exist_ok=True)
        Path(local_path).write_bytes(fallback_source.read_bytes())


def gcs_uri_to_https(gcs_uri: str) -> str:
    bucket, key = _parse_gcs_uri(gcs_uri)
    return f"https://storage.googleapis.com/{bucket}/{key}"
