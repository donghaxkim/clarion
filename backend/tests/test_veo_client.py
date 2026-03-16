import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from app.services.video.reconstruction import veo_client as veo_module
from app.services.video.reconstruction.veo_client import VeoClient


class _FakeImage:
    def __init__(self, gcs_uri: str | None = None):
        self.gcs_uri = gcs_uri
        self.location = None

    @classmethod
    def from_file(cls, location: str):
        image = cls()
        image.location = location
        return image


class _FakeVideoGenerationReferenceType:
    ASSET = "ASSET"


class _FakeVideoGenerationReferenceImage:
    def __init__(self, *, image, reference_type):
        self.image = image
        self.reference_type = reference_type


class _FakeGenerateVideosConfig:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class _FakeVideo:
    def __init__(self, *, uri: str | None = None, video_bytes: bytes | None = None):
        self.uri = uri
        self.video_bytes = video_bytes


class _FakeGeneratedVideo:
    def __init__(self, video):
        self.video = video


class _FakeGenerateVideosResponse:
    def __init__(self, generated_videos):
        self.generated_videos = generated_videos


class _FakeOperation:
    def __init__(self, *, done: bool, response=None, error=None):
        self.done = done
        self.response = response
        self.error = error
        self.name = "operations/fake-video-op"


def _install_fake_google_module(monkeypatch, client_cls):
    fake_types = SimpleNamespace(
        Image=_FakeImage,
        GenerateVideosConfig=_FakeGenerateVideosConfig,
        VideoGenerationReferenceImage=_FakeVideoGenerationReferenceImage,
        VideoGenerationReferenceType=_FakeVideoGenerationReferenceType,
    )
    google_module = ModuleType("google")
    google_module.genai = SimpleNamespace(Client=client_cls)
    google_genai_module = ModuleType("google.genai")
    google_genai_module.types = fake_types

    monkeypatch.setitem(sys.modules, "google", google_module)
    monkeypatch.setitem(sys.modules, "google.genai", google_genai_module)


def _set_runtime(monkeypatch, *, api_key: str = "test-api-key", project_id: str = ""):
    monkeypatch.setattr(veo_module, "GEMINI_API_KEY", api_key)
    monkeypatch.setattr(veo_module, "VERTEX_PROJECT_ID", project_id)
    monkeypatch.setattr(veo_module.time, "sleep", lambda *_: None)


def _generate_sync(client: VeoClient, **overrides):
    request = {
        "model": "veo-3.1-generate-preview",
        "prompt": "Reconstruct this crash.",
        "duration_sec": 8,
        "aspect_ratio": "16:9",
        "reference_image_uris": [],
        "negative_prompt": None,
        "seed": None,
    }
    request.update(overrides)
    return client._generate_video_sync(**request)


def test_generate_video_polls_operation_and_uses_reference_images(monkeypatch):
    _set_runtime(monkeypatch)

    initial_operation = _FakeOperation(done=False)
    completed_operation = _FakeOperation(
        done=True,
        response=_FakeGenerateVideosResponse(
            [_FakeGeneratedVideo(_FakeVideo(uri="files/abc123"))]
        ),
    )

    state: dict[str, object] = {}

    class _FakeOperations:
        def __init__(self):
            self.calls = 0

        def get(self, _operation):
            self.calls += 1
            return completed_operation

    class _FakeModels:
        def generate_videos(self, *, model, prompt, config):
            state["request"] = {"model": model, "prompt": prompt, "config": config}
            return initial_operation

    class _FakeFiles:
        def __init__(self):
            self.calls = []

        def download(self, *, file):
            self.calls.append(file)
            return b"video-from-files-api"

    class _FakeClient:
        def __init__(self, **kwargs):
            state["client_kwargs"] = kwargs
            self.vertexai = kwargs.get("vertexai", False)
            self.models = _FakeModels()
            self.operations = _FakeOperations()
            self.files = _FakeFiles()
            state["operations"] = self.operations

    _install_fake_google_module(monkeypatch, _FakeClient)

    data = _generate_sync(
        VeoClient(allow_fake=False, poll_interval_sec=1),
        model="veo-3.1-fast-generate-preview",
        reference_image_uris=["gs://clarion-uploads/ref.jpg"],
        negative_prompt="no fire",
        seed=11,
    )

    assert data == b"video-from-files-api"
    assert state["operations"].calls == 1  # type: ignore[index]

    request = state["request"]  # type: ignore[assignment]
    config = request["config"]  # type: ignore[index]
    assert "reference_images" in config.kwargs
    assert "image_uris" not in config.kwargs
    reference = config.kwargs["reference_images"][0]
    assert reference.reference_type == _FakeVideoGenerationReferenceType.ASSET
    assert reference.image.gcs_uri == "gs://clarion-uploads/ref.jpg"


def test_generate_video_handles_operation_done_none_until_completion(monkeypatch):
    _set_runtime(monkeypatch)

    initial_operation = _FakeOperation(done=None)
    completed_operation = _FakeOperation(
        done=True,
        response=_FakeGenerateVideosResponse(
            [_FakeGeneratedVideo(_FakeVideo(video_bytes=b"video-bytes"))]
        ),
    )

    state: dict[str, object] = {}

    class _FakeOperations:
        def __init__(self):
            self.calls = 0

        def get(self, _operation):
            self.calls += 1
            return completed_operation

    class _FakeModels:
        def generate_videos(self, *, model, prompt, config):
            state["request"] = {"model": model, "prompt": prompt, "config": config}
            return initial_operation

    class _FakeClient:
        def __init__(self, **kwargs):
            self.vertexai = kwargs.get("vertexai", False)
            self.models = _FakeModels()
            self.operations = _FakeOperations()
            self.files = None
            state["operations"] = self.operations

    _install_fake_google_module(monkeypatch, _FakeClient)

    data = _generate_sync(
        VeoClient(allow_fake=False, poll_interval_sec=1),
        model="veo-3.1-fast-generate-preview",
    )

    assert data == b"video-bytes"
    assert state["operations"].calls == 1  # type: ignore[index]


def test_vertex_mode_works_without_api_key(monkeypatch):
    _set_runtime(monkeypatch, api_key="", project_id="clarion-project")
    monkeypatch.setattr(veo_module, "VERTEX_LOCATION", "us-central1")

    state: dict[str, object] = {}

    class _FakeModels:
        def generate_videos(self, *, model, prompt, config):
            state["request"] = {"model": model, "prompt": prompt, "config": config}
            return _FakeOperation(
                done=True,
                response=_FakeGenerateVideosResponse(
                    [_FakeGeneratedVideo(_FakeVideo(video_bytes=b"vertex-video-bytes"))]
                ),
            )

    class _FakeClient:
        def __init__(self, **kwargs):
            state["client_kwargs"] = kwargs
            self.vertexai = kwargs.get("vertexai", False)
            self.models = _FakeModels()
            self.operations = SimpleNamespace(get=lambda op: op)
            self.files = None

    _install_fake_google_module(monkeypatch, _FakeClient)

    data = _generate_sync(VeoClient(allow_fake=False))

    assert data == b"vertex-video-bytes"
    assert state["client_kwargs"] == {  # type: ignore[index]
        "vertexai": True,
        "project": "clarion-project",
        "location": "us-central1",
    }


def test_missing_credentials_raises_when_fake_disabled(monkeypatch):
    _set_runtime(monkeypatch, api_key="", project_id="")

    with pytest.raises(RuntimeError, match="Neither GEMINI_API_KEY nor VERTEX_PROJECT_ID"):
        _generate_sync(VeoClient(allow_fake=False))


def test_fake_mode_returns_placeholder_payload(monkeypatch):
    _set_runtime(monkeypatch, api_key="", project_id="")

    data = _generate_sync(VeoClient(allow_fake=True), seed=123)

    assert data.startswith(b"FAKE_MP4::")


def test_gcs_uri_download_path_is_supported(monkeypatch):
    _set_runtime(monkeypatch)

    class _FakeModels:
        def generate_videos(self, *, model, prompt, config):
            return _FakeOperation(
                done=True,
                response=_FakeGenerateVideosResponse(
                    [_FakeGeneratedVideo(_FakeVideo(uri="gs://clarion-uploads/output.mp4"))]
                ),
            )

    class _FakeClient:
        def __init__(self, **kwargs):
            self.vertexai = False
            self.models = _FakeModels()
            self.operations = SimpleNamespace(get=lambda op: op)
            self.files = None

    _install_fake_google_module(monkeypatch, _FakeClient)

    payload = b"video-from-gcs"

    def _fake_download(uri: str, local_path: str):
        assert uri == "gs://clarion-uploads/output.mp4"
        Path(local_path).write_bytes(payload)

    monkeypatch.setattr(veo_module, "download_file", _fake_download)

    data = _generate_sync(VeoClient(allow_fake=False))

    assert data == payload
