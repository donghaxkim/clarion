import sys
from pathlib import Path
from types import ModuleType

import pytest

from app.utils import storage as storage_module


def _install_failing_google_cloud(monkeypatch):
    google_module = ModuleType("google")
    cloud_module = ModuleType("google.cloud")

    class _FailingClient:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("cloud client unavailable")

    cloud_module.storage = type("StorageModule", (), {"Client": _FailingClient})()
    google_module.cloud = cloud_module
    monkeypatch.setitem(sys.modules, "google", google_module)
    monkeypatch.setitem(sys.modules, "google.cloud", cloud_module)


def test_upload_bytes_raises_when_cloud_fails_and_fallback_disabled(monkeypatch, tmp_path):
    _install_failing_google_cloud(monkeypatch)
    monkeypatch.setattr(storage_module, "GCS_ALLOW_LOCAL_FALLBACK", False)
    monkeypatch.setattr(storage_module, "LOCAL_ARTIFACTS_DIR", str(tmp_path))

    with pytest.raises(RuntimeError, match="GCS upload failed"):
        storage_module.upload_bytes(b"payload", "reconstructions/job/video.mp4", "video/mp4")


def test_upload_bytes_uses_local_fallback_when_enabled(monkeypatch, tmp_path):
    _install_failing_google_cloud(monkeypatch)
    monkeypatch.setattr(storage_module, "GCS_ALLOW_LOCAL_FALLBACK", True)
    monkeypatch.setattr(storage_module, "LOCAL_ARTIFACTS_DIR", str(tmp_path))
    monkeypatch.setattr(storage_module, "GCS_BUCKET", "test-bucket")

    uri = storage_module.upload_bytes(b"payload", "reconstructions/job/video.mp4", "video/mp4")
    assert uri == "gs://test-bucket/reconstructions/job/video.mp4"
    assert (tmp_path / "reconstructions/job/video.mp4").read_bytes() == b"payload"


def test_download_file_raises_when_cloud_fails_and_fallback_disabled(monkeypatch, tmp_path):
    _install_failing_google_cloud(monkeypatch)
    monkeypatch.setattr(storage_module, "GCS_ALLOW_LOCAL_FALLBACK", False)
    monkeypatch.setattr(storage_module, "LOCAL_ARTIFACTS_DIR", str(tmp_path))

    with pytest.raises(RuntimeError, match="GCS download failed"):
        storage_module.download_file("gs://test-bucket/reconstructions/job/video.mp4", str(tmp_path / "out.mp4"))


def test_download_file_uses_local_fallback_when_enabled(monkeypatch, tmp_path):
    _install_failing_google_cloud(monkeypatch)
    monkeypatch.setattr(storage_module, "GCS_ALLOW_LOCAL_FALLBACK", True)
    monkeypatch.setattr(storage_module, "LOCAL_ARTIFACTS_DIR", str(tmp_path))

    key = "reconstructions/job/video.mp4"
    source = tmp_path / key
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"payload")

    target = tmp_path / "downloads/out.mp4"
    storage_module.download_file(f"gs://test-bucket/{key}", str(target))
    assert target.read_bytes() == b"payload"


def test_gcs_uri_to_signed_url_uses_storage_client(monkeypatch):
    class _Blob:
        def __init__(self, key: str):
            self.key = key

        def generate_signed_url(self, *, version, expiration, method):
            assert version == "v4"
            assert method == "GET"
            assert expiration.total_seconds() == storage_module.GCS_SIGNED_URL_TTL_SECONDS
            return f"https://signed.test/{self.key}?sig=abc123"

    class _Bucket:
        def blob(self, key: str):
            return _Blob(key)

    class _Client:
        def bucket(self, bucket_name: str):
            assert bucket_name == "test-bucket"
            return _Bucket()

    monkeypatch.setattr(storage_module, "GCS_BUCKET", "test-bucket")
    monkeypatch.setattr(
        storage_module,
        "GCS_SIGNED_URL_TTL_SECONDS",
        900,
    )

    google_module = ModuleType("google")
    cloud_module = ModuleType("google.cloud")
    cloud_module.storage = type("StorageModule", (), {"Client": _Client})()
    google_module.cloud = cloud_module
    monkeypatch.setitem(sys.modules, "google", google_module)
    monkeypatch.setitem(sys.modules, "google.cloud", cloud_module)

    signed_url = storage_module.gcs_uri_to_signed_url("gs://test-bucket/reports/demo/image.png")
    assert signed_url == "https://signed.test/reports/demo/image.png?sig=abc123"


def test_materialize_browser_uri_uses_local_artifact_when_signing_fails(monkeypatch, tmp_path):
    monkeypatch.setattr(storage_module, "GCS_ALLOW_LOCAL_FALLBACK", True)
    monkeypatch.setattr(storage_module, "LOCAL_ARTIFACTS_DIR", str(tmp_path))

    key = "reconstructions/job/video.mp4"
    artifact = tmp_path / key
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_bytes(b"payload")

    def _fail_signing(uri: str, *, expiration_seconds: int = 3600) -> str:
        del uri, expiration_seconds
        raise RuntimeError("signing unavailable")

    monkeypatch.setattr(storage_module, "gcs_uri_to_signed_url", _fail_signing)

    browser_url = storage_module.materialize_browser_uri(
        "gs://test-bucket/reconstructions/job/video.mp4",
        base_url="http://127.0.0.1:8000",
    )
    assert browser_url == "http://127.0.0.1:8000/generate/artifacts/reconstructions/job/video.mp4"


def test_materialize_browser_uri_falls_back_to_public_https_when_signing_fails(monkeypatch):
    monkeypatch.setattr(storage_module, "GCS_ALLOW_LOCAL_FALLBACK", False)

    def _fail_signing(uri: str, *, expiration_seconds: int = 3600) -> str:
        del uri, expiration_seconds
        raise RuntimeError("signing unavailable")

    monkeypatch.setattr(storage_module, "gcs_uri_to_signed_url", _fail_signing)

    browser_url = storage_module.materialize_browser_uri(
        "gs://test-bucket/reports/demo/image.png",
        base_url="http://127.0.0.1:8000",
    )
    assert browser_url == "https://storage.googleapis.com/test-bucket/reports/demo/image.png"


def test_gcs_uri_to_signed_url_uses_service_account_token_overrides(monkeypatch):
    captured: dict[str, object] = {}

    class _Blob:
        def generate_signed_url(self, **kwargs):
            captured.update(kwargs)
            return "https://signed.test/report.png"

    class _Bucket:
        def blob(self, key: str):
            captured["key"] = key
            return _Blob()

    class _Credentials:
        token = "token-123"
        service_account_email = "clarion-signer@test-project.iam.gserviceaccount.com"

    class _Client:
        def __init__(self):
            self._credentials = _Credentials()

        def bucket(self, bucket_name: str):
            captured["bucket"] = bucket_name
            return _Bucket()

    google_module = ModuleType("google")
    cloud_module = ModuleType("google.cloud")
    cloud_module.storage = type("StorageModule", (), {"Client": _Client})()
    google_module.cloud = cloud_module
    monkeypatch.setitem(sys.modules, "google", google_module)
    monkeypatch.setitem(sys.modules, "google.cloud", cloud_module)
    monkeypatch.setattr(
        storage_module,
        "_get_signed_url_generation_kwargs",
        lambda credentials: {
            "service_account_email": credentials.service_account_email,
            "access_token": credentials.token,
        },
    )

    signed_url = storage_module.gcs_uri_to_signed_url(
        "gs://test-bucket/reports/demo/report.png",
    )

    assert signed_url == "https://signed.test/report.png"
    assert captured["bucket"] == "test-bucket"
    assert captured["key"] == "reports/demo/report.png"
    assert captured["service_account_email"] == "clarion-signer@test-project.iam.gserviceaccount.com"
    assert captured["access_token"] == "token-123"


def test_gcs_uri_to_signed_url_raises_clear_error_for_user_adc(monkeypatch):
    class _Blob:
        def generate_signed_url(self, **kwargs):
            del kwargs
            raise AttributeError(
                "you need a private key to sign credentials.the credentials you are currently using "
                "<class 'google.oauth2.credentials.Credentials'> just contains a token."
            )

    class _Bucket:
        def blob(self, key: str):
            del key
            return _Blob()

    class _Client:
        _credentials = object()

        def bucket(self, bucket_name: str):
            del bucket_name
            return _Bucket()

    google_module = ModuleType("google")
    cloud_module = ModuleType("google.cloud")
    cloud_module.storage = type("StorageModule", (), {"Client": _Client})()
    google_module.cloud = cloud_module
    monkeypatch.setitem(sys.modules, "google", google_module)
    monkeypatch.setitem(sys.modules, "google.cloud", cloud_module)
    monkeypatch.setattr(storage_module, "_get_signed_url_generation_kwargs", lambda credentials: {})

    with pytest.raises(RuntimeError, match="service account impersonation"):
        storage_module.gcs_uri_to_signed_url("gs://test-bucket/reports/demo/report.png")
