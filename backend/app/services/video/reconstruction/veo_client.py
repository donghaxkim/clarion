from __future__ import annotations

import asyncio
import hashlib
import tempfile
import time
from pathlib import Path
from typing import Any
from urllib.request import urlopen

from app.config import GEMINI_API_KEY, VERTEX_LOCATION, VERTEX_PROJECT_ID
from app.utils.storage import download_file


class VeoClient:
    def __init__(
        self,
        allow_fake: bool = False,
        poll_interval_sec: int = 20,
        poll_timeout_sec: int = 900,
    ):
        self.allow_fake = allow_fake
        self.poll_interval_sec = max(1, poll_interval_sec)
        self.poll_timeout_sec = max(self.poll_interval_sec, poll_timeout_sec)

    async def generate_video(
        self,
        *,
        model: str,
        prompt: str,
        duration_sec: int,
        aspect_ratio: str,
        reference_image_uris: list[str] | None = None,
        negative_prompt: str | None = None,
        seed: int | None = None,
    ) -> bytes:
        return await asyncio.to_thread(
            self._generate_video_sync,
            model=model,
            prompt=prompt,
            duration_sec=duration_sec,
            aspect_ratio=aspect_ratio,
            reference_image_uris=reference_image_uris or [],
            negative_prompt=negative_prompt,
            seed=seed,
        )

    def _generate_video_sync(
        self,
        *,
        model: str,
        prompt: str,
        duration_sec: int,
        aspect_ratio: str,
        reference_image_uris: list[str],
        negative_prompt: str | None,
        seed: int | None,
    ) -> bytes:
        if not GEMINI_API_KEY and not VERTEX_PROJECT_ID:
            return _fake_or_raise(
                allow_fake=self.allow_fake,
                prompt=prompt,
                model=model,
                seed=seed,
            )

        try:
            from google import genai  # type: ignore
            from google.genai import types  # type: ignore
        except Exception as exc:
            if self.allow_fake:
                return _build_fake_video_bytes(prompt=prompt, model=model, seed=seed)
            raise RuntimeError(
                "google-genai SDK is required for Veo generation. Install `google-genai`."
            ) from exc

        client = _build_client(genai_module=genai)

        try:
            operation = client.models.generate_videos(
                model=model,
                prompt=prompt,
                config=_build_generation_config(
                    types_module=types,
                    duration_sec=duration_sec,
                    aspect_ratio=aspect_ratio,
                    reference_image_uris=reference_image_uris,
                    negative_prompt=negative_prompt,
                    seed=seed,
                ),
            )
        except Exception as exc:
            raise RuntimeError(f"Veo request failed: {type(exc).__name__}: {exc}") from exc

        operation = self._wait_for_completion(client=client, operation=operation)
        response = _extract_operation_response(operation)
        return _extract_video_bytes(client=client, response=response)

    def _wait_for_completion(self, *, client: Any, operation: Any) -> Any:
        get_operation = getattr(getattr(client, "operations", None), "get", None)
        if not callable(get_operation):
            if getattr(operation, "done", None) is True:
                return operation
            raise RuntimeError("Veo client does not support operation polling")

        start_ts = time.monotonic()
        while getattr(operation, "done", None) is not True:
            if time.monotonic() - start_ts >= self.poll_timeout_sec:
                raise RuntimeError("Veo operation polling timed out")
            try:
                operation = _refresh_operation(get_operation=get_operation, operation=operation)
            except Exception as exc:
                raise RuntimeError(f"Veo operation poll failed: {type(exc).__name__}: {exc}") from exc
            if getattr(operation, "done", None) is not True:
                time.sleep(self.poll_interval_sec)
        return operation


def _fake_or_raise(*, allow_fake: bool, prompt: str, model: str, seed: int | None) -> bytes:
    if allow_fake:
        return _build_fake_video_bytes(prompt=prompt, model=model, seed=seed)
    raise RuntimeError("Neither GEMINI_API_KEY nor VERTEX_PROJECT_ID is configured")


def _build_fake_video_bytes(prompt: str, model: str, seed: int | None) -> bytes:
    digest = hashlib.sha256(f"{model}|{seed}|{prompt}".encode("utf-8")).hexdigest()[:24]
    # Deterministic placeholder payload for local/offline development.
    return f"FAKE_MP4::{digest}".encode("utf-8")


def _build_client(*, genai_module: Any) -> Any:
    if VERTEX_PROJECT_ID:
        return genai_module.Client(
            vertexai=True,
            project=VERTEX_PROJECT_ID,
            location=VERTEX_LOCATION,
        )
    return genai_module.Client(api_key=GEMINI_API_KEY)


def _build_generation_config(
    *,
    types_module: Any,
    duration_sec: int,
    aspect_ratio: str,
    reference_image_uris: list[str],
    negative_prompt: str | None,
    seed: int | None,
) -> Any:
    config: dict[str, object] = {
        "duration_seconds": duration_sec,
        "aspect_ratio": aspect_ratio,
    }
    if negative_prompt:
        config["negative_prompt"] = negative_prompt
    if seed is not None:
        config["seed"] = seed
    if reference_image_uris:
        config["reference_images"] = _build_reference_images(
            types_module=types_module,
            uris=reference_image_uris,
        )
    return types_module.GenerateVideosConfig(**config)


def _extract_operation_response(operation: Any) -> Any:
    op_error = getattr(operation, "error", None)
    if op_error:
        raise RuntimeError(f"Veo generation failed: {op_error}")

    response = getattr(operation, "response", None)
    if response is not None:
        return response

    result_attr = getattr(operation, "result", None)
    if callable(result_attr):
        result = result_attr()
        if result is not None:
            return result
    elif result_attr is not None:
        return result_attr

    raise RuntimeError("Veo operation completed without a response payload")


def _extract_video_bytes(*, client: Any, response: Any) -> bytes:
    outputs = getattr(response, "generated_videos", None) or []
    if not outputs:
        raise RuntimeError("Veo returned no generated video artifacts")

    output = outputs[0]
    video = getattr(output, "video", output)

    direct_bytes = _coerce_bytes(
        getattr(video, "video_bytes", None)
        or getattr(video, "bytes", None)
        or getattr(output, "video_bytes", None)
        or getattr(output, "bytes", None)
    )
    if direct_bytes is not None:
        return direct_bytes

    uri = (
        getattr(video, "uri", None)
        or getattr(video, "gcs_uri", None)
        or getattr(output, "uri", None)
        or getattr(output, "gcs_uri", None)
    )

    downloaded = _try_download_with_sdk(client=client, video_obj=video, uri=uri)
    if downloaded is not None:
        return downloaded
    if uri:
        return _download_from_uri(str(uri))
    raise RuntimeError("Veo output did not include downloadable video bytes or URI")


def _coerce_bytes(value: Any) -> bytes | None:
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    return None


def _build_reference_images(*, types_module: Any, uris: list[str]) -> list[Any]:
    refs: list[Any] = []
    for uri in uris:
        if uri.startswith("gs://"):
            image = types_module.Image(gcs_uri=uri)
        else:
            try:
                image = types_module.Image.from_file(location=uri)
            except Exception as exc:
                raise ValueError(
                    "reference_image_uris entries must be gs:// URIs or local file paths"
                ) from exc

        refs.append(
            types_module.VideoGenerationReferenceImage(
                image=image,
                reference_type=types_module.VideoGenerationReferenceType.ASSET,
            )
        )
    return refs


def _try_download_with_sdk(*, client: Any, video_obj: Any, uri: Any) -> bytes | None:
    if getattr(client, "vertexai", False):
        return None

    download = getattr(getattr(client, "files", None), "download", None)
    if not callable(download):
        return None

    for candidate in (video_obj, uri):
        if candidate is None:
            continue
        try:
            payload = download(file=candidate)
        except Exception:
            continue
        if payload:
            if isinstance(payload, (bytes, bytearray)):
                return bytes(payload)
            read_fn = getattr(payload, "read", None)
            if callable(read_fn):
                read_data = read_fn()
                if read_data:
                    return bytes(read_data)
    return None


def _download_from_uri(uri: str) -> bytes:
    if uri.startswith("gs://"):
        with tempfile.TemporaryDirectory(prefix="clarion-veo-") as scratch_dir:
            path = Path(scratch_dir) / "veo_output.mp4"
            download_file(uri, str(path))
            return path.read_bytes()
    if uri.startswith(("http://", "https://")):
        with urlopen(uri, timeout=120) as response:
            return response.read()
    raise RuntimeError("Veo output did not include a downloadable URI")


def _refresh_operation(*, get_operation: Any, operation: Any) -> Any:
    try:
        return get_operation(operation)
    except TypeError as type_error:
        name = getattr(operation, "name", None)
        if not name:
            raise type_error
        return get_operation(name)
