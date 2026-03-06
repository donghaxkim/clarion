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
