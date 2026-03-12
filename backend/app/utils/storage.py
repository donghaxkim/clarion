# GCS upload/download helpers
from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from urllib.parse import quote

from app.config import (
    GCS_ALLOW_LOCAL_FALLBACK,
    GCS_BUCKET,
    GCS_SIGNED_URL_TTL_SECONDS,
    LOCAL_ARTIFACTS_DIR,
)


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


def _local_artifact_path(key: str) -> Path:
    return Path(LOCAL_ARTIFACTS_DIR) / key


def _upload_bytes_local(data: bytes, gcs_key: str) -> str:
    target = _local_artifact_path(gcs_key)
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
        fallback_source = _local_artifact_path(key)
        if not fallback_source.exists():
            raise FileNotFoundError(f"Artifact not found for URI: {gcs_uri}")
        Path(local_path).parent.mkdir(parents=True, exist_ok=True)
        Path(local_path).write_bytes(fallback_source.read_bytes())


def gcs_uri_to_https(gcs_uri: str) -> str:
    bucket, key = _parse_gcs_uri(gcs_uri)
    return f"https://storage.googleapis.com/{bucket}/{key}"


def gcs_uri_to_signed_url(
    gcs_uri: str,
    *,
    expiration_seconds: int | None = None,
) -> str:
    if expiration_seconds is None:
        expiration_seconds = GCS_SIGNED_URL_TTL_SECONDS

    if expiration_seconds <= 0:
        raise ValueError("expiration_seconds must be positive")

    bucket, key = _parse_gcs_uri(gcs_uri)

    try:
        from google.cloud import storage  # type: ignore

        client = storage.Client()
        blob = client.bucket(bucket).blob(key)
        signing_kwargs = _get_signed_url_generation_kwargs(getattr(client, "_credentials", None))
        return blob.generate_signed_url(
            version="v4",
            expiration=timedelta(seconds=expiration_seconds),
            method="GET",
            **signing_kwargs,
        )
    except AttributeError as exc:
        if "private key" in str(exc):
            raise RuntimeError(
                "Failed to generate a signed URL because the active credentials cannot sign "
                "Cloud Storage URLs. Use service account impersonation "
                "(`gcloud auth application-default login --impersonate-service-account=...`) "
                "or set GOOGLE_APPLICATION_CREDENTIALS to a service account key."
            ) from exc
        raise RuntimeError(f"Failed to generate a signed URL for {gcs_uri}") from exc
    except Exception as exc:
        raise RuntimeError(f"Failed to generate a signed URL for {gcs_uri}") from exc


def local_artifact_path_for_gcs_uri(gcs_uri: str) -> Path:
    _bucket, key = _parse_gcs_uri(gcs_uri)
    return _local_artifact_path(key)


def local_artifact_exists(gcs_uri: str) -> bool:
    return local_artifact_path_for_gcs_uri(gcs_uri).exists()


def build_local_artifact_url(gcs_uri: str, *, base_url: str) -> str:
    _bucket, key = _parse_gcs_uri(gcs_uri)
    return f"{base_url.rstrip('/')}/generate/artifacts/{quote(key, safe='/')}"


def _get_signed_url_generation_kwargs(credentials: object | None) -> dict[str, str]:
    if credentials is None:
        return {}

    try:
        from google.auth import credentials as google_auth_credentials  # type: ignore
        from google.auth.transport.requests import Request  # type: ignore
    except Exception:
        return {}

    if isinstance(credentials, google_auth_credentials.Signing):
        return {}

    access_token = getattr(credentials, "token", None)
    if access_token is None and hasattr(credentials, "refresh"):
        credentials.refresh(Request())
        access_token = getattr(credentials, "token", None)

    service_account_email = getattr(credentials, "service_account_email", None)
    if service_account_email and access_token:
        return {
            "service_account_email": service_account_email,
            "access_token": access_token,
        }

    return {}


def materialize_browser_uri(
    uri: str | None,
    *,
    base_url: str | None = None,
) -> str | None:
    if uri is None or not uri.startswith("gs://"):
        return uri

    try:
        return gcs_uri_to_signed_url(uri)
    except Exception:
        if base_url and GCS_ALLOW_LOCAL_FALLBACK and local_artifact_exists(uri):
            return build_local_artifact_url(uri, base_url=base_url)
        return gcs_uri_to_https(uri)
