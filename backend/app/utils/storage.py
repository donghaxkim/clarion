# GCS upload/download helpers
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from app.config import (
    GCS_BUCKET,
    GCS_SIGNED_URL_TTL_SECONDS,
    SIGNED_URL_SERVICE_ACCOUNT_EMAIL,
)

logger = logging.getLogger(__name__)

_CLOUD_PLATFORM_SCOPE = "https://www.googleapis.com/auth/cloud-platform"
_GOOGLE_OAUTH_TOKEN_URI = "https://oauth2.googleapis.com/token"


class SignedUrlConfigurationError(RuntimeError):
    """Raised when the runtime cannot produce private signed artifact URLs."""


@dataclass(frozen=True)
class _ResolvedSignedUrlSigner:
    credentials: object
    signer_email: str


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


def _require_bucket() -> str:
    bucket = GCS_BUCKET.strip()
    if not bucket:
        raise RuntimeError("GCS_BUCKET must be configured for cloud-backed storage")
    return bucket


def upload_bytes(
    data: bytes,
    gcs_key: str,
    content_type: str = "application/octet-stream",
) -> str:
    bucket_name = _require_bucket()
    try:
        from google.cloud import storage  # type: ignore
    except Exception as exc:
        raise RuntimeError(
            "google-cloud-storage is required for artifact persistence. "
            "Install `google-cloud-storage`."
        ) from exc

    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(gcs_key)
    blob.upload_from_string(data, content_type=content_type)
    return _build_gcs_uri(bucket_name, gcs_key)


def upload_file(local_path: str, gcs_key: str) -> str:
    data = Path(local_path).read_bytes()
    return upload_bytes(data=data, gcs_key=gcs_key)


def download_bytes(gcs_uri: str) -> bytes:
    try:
        from google.cloud import storage  # type: ignore
    except Exception as exc:
        raise RuntimeError(
            "google-cloud-storage is required for artifact retrieval. "
            "Install `google-cloud-storage`."
        ) from exc

    try:
        bucket, key = _parse_gcs_uri(gcs_uri)
        client = storage.Client()
        blob = client.bucket(bucket).blob(key)
        return bytes(blob.download_as_bytes())
    except Exception as exc:
        raise RuntimeError(f"GCS download failed for {gcs_uri}") from exc


def download_file(gcs_uri: str, local_path: str) -> None:
    Path(local_path).parent.mkdir(parents=True, exist_ok=True)
    Path(local_path).write_bytes(download_bytes(gcs_uri))


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

    try:
        from google.cloud import storage  # type: ignore
    except Exception as exc:
        raise RuntimeError(
            "google-cloud-storage is required for signed URLs. "
            "Install `google-cloud-storage`."
        ) from exc

    bucket, key = _parse_gcs_uri(gcs_uri)
    client = storage.Client()
    blob = client.bucket(bucket).blob(key)
    resolved_signer: _ResolvedSignedUrlSigner | None = None

    try:
        resolved_signer = _resolve_signed_url_signer(_load_signing_source_credentials())
        logger.info(
            "Generating private GCS signed URL for bucket=%s key=%s signer_email=%s",
            bucket,
            key,
            resolved_signer.signer_email,
        )
        return blob.generate_signed_url(
            version="v4",
            expiration=timedelta(seconds=expiration_seconds),
            method="GET",
            credentials=resolved_signer.credentials,
        )
    except SignedUrlConfigurationError:
        logger.exception(
            "GCS signed URL configuration failed for gcs_uri=%s signer_email=%s",
            gcs_uri,
            resolved_signer.signer_email if resolved_signer else "<unresolved>",
        )
        raise
    except AttributeError as exc:
        if "private key" in str(exc):
            logger.exception(
                "GCS signed URL generation hit unsigned credentials for gcs_uri=%s signer_email=%s",
                gcs_uri,
                resolved_signer.signer_email if resolved_signer else "<unresolved>",
            )
            raise SignedUrlConfigurationError(
                _build_signing_configuration_message(
                    gcs_uri,
                    signer_email=resolved_signer.signer_email if resolved_signer else None,
                    reason=(
                        "the runtime credentials could not sign Cloud Storage URLs. "
                        "Ensure SIGNED_URL_SERVICE_ACCOUNT_EMAIL is correct, "
                        "`iamcredentials.googleapis.com` is enabled, and the API runtime "
                        "service account has `roles/iam.serviceAccountTokenCreator` on the signer."
                    ),
                )
            ) from exc
        logger.exception(
            "Unexpected attribute error during GCS signed URL generation for gcs_uri=%s signer_email=%s",
            gcs_uri,
            resolved_signer.signer_email if resolved_signer else "<unresolved>",
        )
        raise SignedUrlConfigurationError(
            _build_signing_configuration_message(
                gcs_uri,
                signer_email=resolved_signer.signer_email if resolved_signer else None,
                reason=str(exc),
            )
        ) from exc
    except Exception as exc:
        logger.exception(
            "GCS signed URL generation failed for gcs_uri=%s signer_email=%s",
            gcs_uri,
            resolved_signer.signer_email if resolved_signer else "<unresolved>",
        )
        raise SignedUrlConfigurationError(
            _build_signing_configuration_message(
                gcs_uri,
                signer_email=resolved_signer.signer_email if resolved_signer else None,
                reason=str(exc),
            )
        ) from exc


def _resolve_signed_url_signer(
    source_credentials: object | None,
) -> _ResolvedSignedUrlSigner:
    signer_email = _resolve_signer_email(source_credentials)
    signing_credentials = _build_signing_credentials(
        source_credentials=source_credentials,
        signer_email=signer_email,
    )
    return _ResolvedSignedUrlSigner(
        credentials=signing_credentials,
        signer_email=signer_email,
    )


def _load_signing_source_credentials() -> object:
    try:
        import google.auth  # type: ignore
    except Exception as exc:
        raise RuntimeError(
            "google-auth is required for signed artifact URLs. "
            "Install the Google authentication dependencies."
        ) from exc

    try:
        credentials, _ = google.auth.default(scopes=[_CLOUD_PLATFORM_SCOPE])
        return credentials
    except Exception as exc:
        raise SignedUrlConfigurationError(
            "Artifact URL signing requires Google application credentials with "
            "cloud-platform scope. Ensure the API runs with ADC and "
            "`iamcredentials.googleapis.com` is enabled."
        ) from exc


def _resolve_signer_email(source_credentials: object | None) -> str:
    configured_email = SIGNED_URL_SERVICE_ACCOUNT_EMAIL.strip()
    if configured_email:
        return configured_email

    runtime_email = getattr(source_credentials, "service_account_email", None) or getattr(
        source_credentials,
        "signer_email",
        None,
    )
    if runtime_email:
        return str(runtime_email)

    raise SignedUrlConfigurationError(
        "Artifact URL signing is not configured. Set SIGNED_URL_SERVICE_ACCOUNT_EMAIL "
        "or run the API with a service account identity that exposes service_account_email."
    )


def _build_signing_credentials(
    *,
    source_credentials: object | None,
    signer_email: str,
) -> object:
    if source_credentials is None:
        raise SignedUrlConfigurationError(
            "Artifact URL signing requires Google application credentials. "
            "Run the API on Cloud Run with a service account or configure "
            "GOOGLE_APPLICATION_CREDENTIALS for local development."
        )

    try:
        from google.auth import credentials as google_auth_credentials  # type: ignore
        from google.auth import iam  # type: ignore
        from google.auth.transport.requests import Request  # type: ignore
        from google.oauth2 import service_account  # type: ignore
    except Exception as exc:
        raise RuntimeError(
            "google-auth is required for signed artifact URLs. "
            "Install the Google authentication dependencies."
        ) from exc

    prepared_source_credentials = _prepare_source_credentials(source_credentials)
    source_signer_email = getattr(
        prepared_source_credentials,
        "signer_email",
        None,
    ) or getattr(prepared_source_credentials, "service_account_email", None)
    if (
        isinstance(prepared_source_credentials, google_auth_credentials.Signing)
        and source_signer_email == signer_email
    ):
        return prepared_source_credentials

    if not hasattr(prepared_source_credentials, "before_request"):
        raise SignedUrlConfigurationError(
            "Artifact URL signing requires runtime credentials that can call the "
            "IAM Credentials API. The active credentials do not support authenticated requests."
        )

    iam_request = Request()
    signer = iam.Signer(
        request=iam_request,
        credentials=prepared_source_credentials,
        service_account_email=signer_email,
    )
    return service_account.Credentials(
        signer=signer,
        service_account_email=signer_email,
        token_uri=_GOOGLE_OAUTH_TOKEN_URI,
    )


def _prepare_source_credentials(source_credentials: object) -> object:
    requires_scopes = bool(getattr(source_credentials, "requires_scopes", False))
    with_scopes = getattr(source_credentials, "with_scopes", None)
    if requires_scopes and callable(with_scopes):
        return with_scopes([_CLOUD_PLATFORM_SCOPE])
    return source_credentials


def _build_signing_configuration_message(
    gcs_uri: str,
    *,
    signer_email: str | None,
    reason: str,
) -> str:
    signer = signer_email or "<unresolved>"
    return (
        f"Artifact URL signing is misconfigured for {gcs_uri} using signer {signer}. "
        f"{reason}"
    )


def materialize_browser_uri(
    uri: str | None,
    *,
    base_url: str | None = None,
) -> str | None:
    del base_url
    if uri is None or not uri.startswith("gs://"):
        return uri
    return gcs_uri_to_signed_url(uri)
