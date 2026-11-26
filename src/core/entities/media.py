"""Core media domain entities and domain errors."""
from dataclasses import dataclass
from typing import Optional


class MediaValidationError(Exception):
    """Raised when media input or metadata validation fails."""
    pass


class MediaExportError(Exception):
    """Raised when exporting an MP4 fails."""
    pass


MEDIA_KIND_CLIP = "clip"
MEDIA_KIND_AUDIO = "audio"
VALID_MEDIA_KINDS = frozenset({MEDIA_KIND_CLIP, MEDIA_KIND_AUDIO})


@dataclass
class MediaAsset:
    """Domain entity representing an imported video clip or narration audio asset."""
    id: str
    project_id: str
    kind: str
    file_path: str
    original_filename: str
    position: int
    duration_seconds: float
    has_video: bool
    has_audio: bool
    width: Optional[int] = None
    height: Optional[int] = None
    fps: Optional[float] = None
    video_codec: Optional[str] = None
    audio_codec: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.id or not self.id.strip():
            raise MediaValidationError("Media item ID cannot be empty.")
        if not self.project_id or not self.project_id.strip():
            raise MediaValidationError("Project ID cannot be empty.")
        if self.kind not in VALID_MEDIA_KINDS:
            raise MediaValidationError(f"Invalid media kind '{self.kind}'.")
        if not self.file_path or not self.file_path.strip():
            raise MediaValidationError("Media file path cannot be empty.")
        if not self.original_filename or not self.original_filename.strip():
            raise MediaValidationError("Original filename cannot be empty.")
        if self.position < 0:
            raise MediaValidationError("Media position cannot be negative.")
        if self.duration_seconds <= 0:
            raise MediaValidationError(
                f"Media '{self.original_filename}' ({self.file_path}) has non-positive duration ({self.duration_seconds}s)."
            )
        if self.kind == MEDIA_KIND_CLIP:
            if not self.has_video or (self.width or 0) <= 0 or (self.height or 0) <= 0:
                raise MediaValidationError(
                    f"Video clip '{self.original_filename}' ({self.file_path}) does not contain a valid decodable video stream."
                )
        if self.kind == MEDIA_KIND_AUDIO and not self.has_audio:
            raise MediaValidationError(
                f"Narration audio '{self.original_filename}' ({self.file_path}) does not contain a valid decodable audio stream."
            )
