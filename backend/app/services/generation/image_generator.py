from __future__ import annotations

import asyncio
import hashlib
import json
from typing import Any

from app.config import GEMINI_API_KEY, REPORT_IMAGE_MODEL, VEO_ALLOW_FAKE, VERTEX_LOCATION, VERTEX_PROJECT_ID
from app.models import MediaAsset, MediaAssetKind, ReportBlockState
from app.utils.storage import upload_bytes


def _identity_uri(uri: str) -> str:
    return uri


class GeminiImageGenerator:
    def __init__(
        self,
        *,
        model: str = REPORT_IMAGE_MODEL,
        allow_fake: bool = VEO_ALLOW_FAKE,
        upload_bytes_fn=upload_bytes,
        storage_uri_fn=_identity_uri,
    ):
        self.model = model
        self.allow_fake = allow_fake
        self.upload_bytes_fn = upload_bytes_fn
        self.storage_uri_fn = storage_uri_fn

    async def generate(
        self,
        *,
        case_id: str,
        report_id: str,
        block_id: str,
        prompt: str,
    ) -> MediaAsset:
        image_bytes, model_used = await asyncio.to_thread(
            self._generate_sync,
            prompt=prompt,
        )

        base_key = f"reports/{case_id}/{report_id}/media/{block_id}"
        image_gcs_uri = self.upload_bytes_fn(
            image_bytes,
            gcs_key=f"{base_key}.png",
            content_type="image/png",
        )
        manifest_gcs_uri = self.upload_bytes_fn(
            json.dumps(
                {
                    "report_id": report_id,
                    "block_id": block_id,
                    "model_used": model_used,
                    "prompt": prompt,
                    "image_gcs_uri": image_gcs_uri,
                },
                indent=2,
            ).encode("utf-8"),
            gcs_key=f"{base_key}.manifest.json",
            content_type="application/json",
        )

        return MediaAsset(
            kind=MediaAssetKind.image,
            uri=self.storage_uri_fn(image_gcs_uri),
            generator=model_used,
            manifest_uri=manifest_gcs_uri,
            state=ReportBlockState.ready,
        )

    def _generate_sync(self, *, prompt: str) -> tuple[bytes, str]:
        if not GEMINI_API_KEY and not VERTEX_PROJECT_ID:
            if self.allow_fake:
                return _fake_image_bytes(prompt), self.model
            raise RuntimeError("Neither GEMINI_API_KEY nor VERTEX_PROJECT_ID is configured")

        try:
            from google import genai  # type: ignore
            from google.genai import types  # type: ignore
        except Exception as exc:
            if self.allow_fake:
                return _fake_image_bytes(prompt), self.model
            raise RuntimeError(
                "google-genai SDK is required for image generation. Install `google-genai`."
            ) from exc

        client = _build_client(genai_module=genai)
        try:
            response = client.models.generate_images(
                model=self.model,
                prompt=prompt,
                config=types.GenerateImagesConfig(
                    numberOfImages=1,
                    outputMimeType="image/png",
                    aspectRatio="16:9",
                ),
            )
        except Exception as exc:
            raise RuntimeError(f"Gemini image generation failed: {type(exc).__name__}: {exc}") from exc

        generated_images = getattr(response, "generated_images", None) or []
        if not generated_images:
            raise RuntimeError("Gemini image generation returned no images")

        image = getattr(generated_images[0], "image", None) or generated_images[0]
        image_bytes = getattr(image, "image_bytes", None)
        if isinstance(image_bytes, (bytes, bytearray)):
            return bytes(image_bytes), self.model
        raise RuntimeError("Generated image did not include inline bytes")


def _build_client(*, genai_module: Any) -> Any:
    if VERTEX_PROJECT_ID:
        return genai_module.Client(
            vertexai=True,
            project=VERTEX_PROJECT_ID,
            location=VERTEX_LOCATION,
        )
    return genai_module.Client(api_key=GEMINI_API_KEY)


def _fake_image_bytes(prompt: str) -> bytes:
    digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:24]
    return f"FAKE_PNG::{digest}".encode("utf-8")
