"""Local poster upload storage helpers."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from app.core.config import get_settings
from app.core.exceptions import ValidationException

POSTER_UPLOAD_SUBDIR = "posters"
POSTER_ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/svg+xml",
}
POSTER_ALLOWED_SUFFIXES = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".svg",
}


class PosterStorage:
    """Persist admin-uploaded movie posters under the local media directory."""

    def __init__(self) -> None:
        settings = get_settings()
        self.media_root = Path(settings.media_root)
        self.media_url = settings.media_url.rstrip("/")
        self.max_bytes = settings.poster_upload_max_bytes
        self.poster_root = self.media_root / POSTER_UPLOAD_SUBDIR

    async def save(self, upload: UploadFile) -> str:
        """Validate and store one poster upload, returning its root-relative media URL."""
        suffix = self._validate_upload_metadata(upload)
        content = await upload.read(self.max_bytes + 1)
        if not content:
            raise ValidationException("Poster upload cannot be empty.")
        if len(content) > self.max_bytes:
            raise ValidationException("Poster upload is too large.")

        self.poster_root.mkdir(parents=True, exist_ok=True)
        filename = f"{uuid4().hex}{suffix}"
        target = self.poster_root / filename
        target.write_bytes(content)
        return f"{self.media_url}/{POSTER_UPLOAD_SUBDIR}/{filename}"

    def delete(self, poster_file_url: str | None) -> None:
        """Delete a previously stored poster file when it belongs to local media storage."""
        if not poster_file_url:
            return

        prefix = f"{self.media_url}/{POSTER_UPLOAD_SUBDIR}/"
        if not poster_file_url.startswith(prefix):
            return

        filename = poster_file_url.removeprefix(prefix)
        if not filename or Path(filename).name != filename:
            return

        target = (self.poster_root / filename).resolve()
        poster_root = self.poster_root.resolve()
        if poster_root not in target.parents:
            return
        target.unlink(missing_ok=True)

    def _validate_upload_metadata(self, upload: UploadFile) -> str:
        filename = upload.filename or ""
        suffix = Path(filename).suffix.lower()
        if suffix not in POSTER_ALLOWED_SUFFIXES:
            raise ValidationException("Poster upload must be a JPG, PNG, WebP, or SVG image.")

        content_type = (upload.content_type or "").lower()
        if content_type not in POSTER_ALLOWED_CONTENT_TYPES:
            raise ValidationException("Poster upload must use an image content type.")

        return suffix
