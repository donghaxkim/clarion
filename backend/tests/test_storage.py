import sys
from types import ModuleType

import pytest
import google.auth
from google.auth import credentials as google_auth_credentials
from google.auth import iam as iam_module
from google.oauth2 import service_account as service_account_module

from app.utils import storage as storage_module


def _install_google_cloud_storage(monkeypatch, client_cls):
    google_module = ModuleType("google")
    cloud_module = ModuleType("google.cloud")
    cloud_module.storage = type("StorageModule", (), {"Client": client_cls})()
    google_module.cloud = cloud_module
    monkeypatch.setitem(sys.modules, "google", google_module)
    monkeypatch.setitem(sys.modules, "google.cloud", cloud_module)


class _SigningCredentials(google_auth_credentials.Signing):
    def __init__(self, signer_email: str):
        super().__init__()
        self._signer_email = signer_email

    @property
    def signer(self):
        return object()

    @property
    def signer_email(self):
        return self._signer_email

    @property
    def service_account_email(self):
        return self._signer_email

    def sign_bytes(self, message):
        del message
        return b"signed"

    def refresh(self, request):
        del request

    def apply(self, headers, token=None):
        del headers, token


class _NonSigningCredentials:
    requires_scopes = False

    def before_request(self, request, method, url, headers):
        del request, method, url, headers


def test_upload_bytes_requires_bucket(monkeypatch):
    monkeypatch.setattr(storage_module, "GCS_BUCKET", "")

    with pytest.raises(RuntimeError, match="GCS_BUCKET must be configured"):
        storage_module.upload_bytes(b"payload", "reports/demo/report.json")


def test_upload_bytes_uses_storage_client(monkeypatch):
    captured: dict[str, object] = {}

    class _Blob:
        def __init__(self, key: str):
            self.key = key

        def upload_from_string(self, data, content_type):
            captured["data"] = data
            captured["content_type"] = content_type

    class _Bucket:
        def blob(self, key: str):
            captured["key"] = key
            return _Blob(key)

    class _Client:
        def bucket(self, bucket_name: str):
            captured["bucket"] = bucket_name
            return _Bucket()

    monkeypatch.setattr(storage_module, "GCS_BUCKET", "test-bucket")
    _install_google_cloud_storage(monkeypatch, _Client)

    uri = storage_module.upload_bytes(
        b"payload",
        "reports/demo/report.json",
        "application/json",
    )

    assert uri == "gs://test-bucket/reports/demo/report.json"
    assert captured["bucket"] == "test-bucket"
    assert captured["key"] == "reports/demo/report.json"
    assert captured["data"] == b"payload"
    assert captured["content_type"] == "application/json"


def test_download_bytes_raises_when_storage_client_fails(monkeypatch):
    class _Client:
        def bucket(self, bucket_name: str):
            raise RuntimeError(f"unable to access {bucket_name}")

    _install_google_cloud_storage(monkeypatch, _Client)

    with pytest.raises(RuntimeError, match="GCS download failed"):
        storage_module.download_bytes("gs://test-bucket/reconstructions/job/video.mp4")


def test_download_file_writes_downloaded_bytes(monkeypatch, tmp_path):
    payload = b"video-bytes"
    monkeypatch.setattr(storage_module, "download_bytes", lambda gcs_uri: payload)

    target = tmp_path / "downloads/out.mp4"
    storage_module.download_file("gs://test-bucket/reconstructions/job/video.mp4", str(target))
    assert target.read_bytes() == payload


def test_resolve_signer_email_prefers_explicit_config(monkeypatch):
    monkeypatch.setattr(
        storage_module,
        "SIGNED_URL_SERVICE_ACCOUNT_EMAIL",
        "configured@test-project.iam.gserviceaccount.com",
    )
    source_credentials = _SigningCredentials("runtime@test-project.iam.gserviceaccount.com")

    assert (
        storage_module._resolve_signer_email(source_credentials)
        == "configured@test-project.iam.gserviceaccount.com"
    )


def test_resolve_signer_email_falls_back_to_runtime_credentials(monkeypatch):
    monkeypatch.setattr(storage_module, "SIGNED_URL_SERVICE_ACCOUNT_EMAIL", "")
    source_credentials = _SigningCredentials("runtime@test-project.iam.gserviceaccount.com")

    assert (
        storage_module._resolve_signer_email(source_credentials)
        == "runtime@test-project.iam.gserviceaccount.com"
    )


def test_resolve_signer_email_raises_clear_error_when_missing(monkeypatch):
    monkeypatch.setattr(storage_module, "SIGNED_URL_SERVICE_ACCOUNT_EMAIL", "")

    with pytest.raises(storage_module.SignedUrlConfigurationError, match="SIGNED_URL_SERVICE_ACCOUNT_EMAIL"):
        storage_module._resolve_signer_email(object())


def test_load_signing_source_credentials_requests_cloud_platform_scope(monkeypatch):
    captured: dict[str, object] = {}

    def _default(*, scopes):
        captured["scopes"] = list(scopes)
        return _NonSigningCredentials(), "test-project"

    monkeypatch.setattr(google.auth, "default", _default)

    credentials = storage_module._load_signing_source_credentials()

    assert isinstance(credentials, _NonSigningCredentials)
    assert captured["scopes"] == ["https://www.googleapis.com/auth/cloud-platform"]


def test_prepare_source_credentials_adds_cloud_platform_scope_when_needed():
    class _ScopedCredentials:
        requires_scopes = True

        def __init__(self):
            self.scopes: list[str] | None = None

        def with_scopes(self, scopes):
            self.scopes = list(scopes)
            return self

    credentials = _ScopedCredentials()

    prepared = storage_module._prepare_source_credentials(credentials)

    assert prepared is credentials
    assert credentials.scopes == ["https://www.googleapis.com/auth/cloud-platform"]


def test_build_signing_credentials_reuses_matching_signing_credentials(monkeypatch):
    monkeypatch.setattr(storage_module, "SIGNED_URL_SERVICE_ACCOUNT_EMAIL", "")
    source_credentials = _SigningCredentials("runtime@test-project.iam.gserviceaccount.com")

    signing_credentials = storage_module._build_signing_credentials(
        source_credentials=source_credentials,
        signer_email="runtime@test-project.iam.gserviceaccount.com",
    )

    assert signing_credentials is source_credentials


def test_build_signing_credentials_wraps_runtime_credentials_with_iam_signer(monkeypatch):
    captured: dict[str, object] = {}

    class _PreparedCredentials(_NonSigningCredentials):
        pass

    class _Signer:
        def __init__(self, *, request, credentials, service_account_email):
            captured["request"] = request
            captured["source_credentials"] = credentials
            captured["service_account_email"] = service_account_email

    class _ServiceAccountCredentials:
        def __init__(self, *, signer, service_account_email, token_uri):
            captured["signer"] = signer
            captured["wrapped_service_account_email"] = service_account_email
            captured["token_uri"] = token_uri

    prepared_credentials = _PreparedCredentials()
    monkeypatch.setattr(
        storage_module,
        "_prepare_source_credentials",
        lambda source_credentials: prepared_credentials,
    )
    monkeypatch.setattr(iam_module, "Signer", _Signer)
    monkeypatch.setattr(service_account_module, "Credentials", _ServiceAccountCredentials)

    signing_credentials = storage_module._build_signing_credentials(
        source_credentials=_NonSigningCredentials(),
        signer_email="configured@test-project.iam.gserviceaccount.com",
    )

    assert isinstance(signing_credentials, _ServiceAccountCredentials)
    assert captured["source_credentials"] is prepared_credentials
    assert captured["service_account_email"] == "configured@test-project.iam.gserviceaccount.com"
    assert captured["wrapped_service_account_email"] == "configured@test-project.iam.gserviceaccount.com"
    assert captured["token_uri"] == "https://oauth2.googleapis.com/token"


def test_build_signing_credentials_requires_google_credentials():
    with pytest.raises(storage_module.SignedUrlConfigurationError, match="Google application credentials"):
        storage_module._build_signing_credentials(
            source_credentials=None,
            signer_email="configured@test-project.iam.gserviceaccount.com",
        )


def test_gcs_uri_to_signed_url_uses_resolved_signing_credentials(monkeypatch):
    captured: dict[str, object] = {}

    class _Blob:
        def generate_signed_url(self, **kwargs):
            captured.update(kwargs)
            return "https://signed.test/report.png?X-Goog-Signature=abc123"

    class _Bucket:
        def blob(self, key: str):
            captured["key"] = key
            return _Blob()

    class _Client:
        def __init__(self):
            self._credentials = _NonSigningCredentials()

        def bucket(self, bucket_name: str):
            captured["bucket"] = bucket_name
            return _Bucket()

    _install_google_cloud_storage(monkeypatch, _Client)
    monkeypatch.setattr(storage_module, "GCS_SIGNED_URL_TTL_SECONDS", 900)
    monkeypatch.setattr(
        storage_module,
        "_load_signing_source_credentials",
        lambda: _NonSigningCredentials(),
    )
    monkeypatch.setattr(
        storage_module,
        "_resolve_signed_url_signer",
        lambda source_credentials: storage_module._ResolvedSignedUrlSigner(
            credentials="signing-credentials",
            signer_email="configured@test-project.iam.gserviceaccount.com",
        ),
    )

    signed_url = storage_module.gcs_uri_to_signed_url("gs://test-bucket/reports/demo/report.png")

    assert signed_url == "https://signed.test/report.png?X-Goog-Signature=abc123"
    assert captured["bucket"] == "test-bucket"
    assert captured["key"] == "reports/demo/report.png"
    assert captured["credentials"] == "signing-credentials"
    assert captured["version"] == "v4"
    assert captured["method"] == "GET"
    assert captured["expiration"].total_seconds() == 900


def test_gcs_uri_to_signed_url_raises_clear_error_for_missing_signer(monkeypatch):
    class _Blob:
        def generate_signed_url(self, **kwargs):
            del kwargs
            raise AssertionError("generate_signed_url should not be called")

    class _Bucket:
        def blob(self, key: str):
            del key
            return _Blob()

    class _Client:
        def __init__(self):
            self._credentials = object()

        def bucket(self, bucket_name: str):
            del bucket_name
            return _Bucket()

    _install_google_cloud_storage(monkeypatch, _Client)
    monkeypatch.setattr(storage_module, "SIGNED_URL_SERVICE_ACCOUNT_EMAIL", "")
    monkeypatch.setattr(storage_module, "_load_signing_source_credentials", lambda: object())

    with pytest.raises(storage_module.SignedUrlConfigurationError, match="Artifact URL signing is not configured"):
        storage_module.gcs_uri_to_signed_url("gs://test-bucket/reports/demo/report.png")


def test_gcs_uri_to_signed_url_raises_clear_error_when_generation_fails(monkeypatch):
    class _Blob:
        def generate_signed_url(self, **kwargs):
            del kwargs
            raise RuntimeError("signBlob denied")

    class _Bucket:
        def blob(self, key: str):
            del key
            return _Blob()

    class _Client:
        def __init__(self):
            self._credentials = _NonSigningCredentials()

        def bucket(self, bucket_name: str):
            del bucket_name
            return _Bucket()

    _install_google_cloud_storage(monkeypatch, _Client)
    monkeypatch.setattr(
        storage_module,
        "_load_signing_source_credentials",
        lambda: _NonSigningCredentials(),
    )
    monkeypatch.setattr(
        storage_module,
        "_resolve_signed_url_signer",
        lambda source_credentials: storage_module._ResolvedSignedUrlSigner(
            credentials="signing-credentials",
            signer_email="configured@test-project.iam.gserviceaccount.com",
        ),
    )

    with pytest.raises(
        storage_module.SignedUrlConfigurationError,
        match="configured@test-project.iam.gserviceaccount.com",
    ):
        storage_module.gcs_uri_to_signed_url("gs://test-bucket/reports/demo/report.png")


def test_materialize_browser_uri_raises_when_signing_fails(monkeypatch):
    def _fail_signing(uri: str, *, expiration_seconds: int = 3600) -> str:
        del uri, expiration_seconds
        raise storage_module.SignedUrlConfigurationError("signing unavailable")

    monkeypatch.setattr(storage_module, "gcs_uri_to_signed_url", _fail_signing)

    with pytest.raises(storage_module.SignedUrlConfigurationError, match="signing unavailable"):
        storage_module.materialize_browser_uri(
            "gs://test-bucket/reports/demo/image.png",
            base_url="http://127.0.0.1:8000",
        )
