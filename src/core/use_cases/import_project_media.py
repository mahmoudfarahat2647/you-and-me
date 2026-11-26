"""Use case for importing and validating project video clips and narration audio."""
import uuid
from datetime import datetime, timezone
from typing import Optional

from src.core.dto.media_dto import MediaClipInput, NarrationInput, ProjectMediaItem
from src.core.entities.media import (
    MEDIA_KIND_AUDIO,
    MEDIA_KIND_CLIP,
    MediaAsset,
    MediaValidationError,
)
from src.core.ports.media_processor import MediaProcessor
from src.core.ports.project_media_repository import ProjectMediaRepository
from src.core.ports.project_repository import ProjectRepository


def _extract_filename(source_path: str, original_filename: Optional[str]) -> str:
    if original_filename and original_filename.strip():
        return original_filename.strip()
    normalized = source_path.replace("\\", "/").rstrip("/")
    name = normalized.rsplit("/", 1)[-1]
    return name or source_path


class ImportProjectMediaUseCase:
    """Validates via MediaProcessor and persists clips or narration audio for a project."""

    def __init__(
        self,
        media_repo: ProjectMediaRepository,
        media_processor: MediaProcessor,
        project_repo: Optional[ProjectRepository] = None,
    ) -> None:
        self._media_repo = media_repo
        self._media_processor = media_processor
        self._project_repo = project_repo

    def _ensure_project_exists(self, project_id: str) -> None:
        if not project_id or not project_id.strip():
            raise MediaValidationError("Project ID cannot be empty.")
        if self._project_repo is not None and self._project_repo.get_by_id(project_id) is None:
            raise MediaValidationError(f"Project '{project_id}' was not found.")

    def import_clip(self, input_data: MediaClipInput) -> ProjectMediaItem:
        self._ensure_project_exists(input_data.project_id)
        if not input_data.source_path or not input_data.source_path.strip():
            raise MediaValidationError("Clip source path cannot be empty.")

        display_name = _extract_filename(input_data.source_path, input_data.original_filename)
        probe = self._media_processor.probe(input_data.source_path, display_name=display_name)
        if not probe.has_video or (probe.width or 0) <= 0 or (probe.height or 0) <= 0:
            raise MediaValidationError(
                f"Clip '{display_name}' ({input_data.source_path}) does not contain a valid decodable video stream."
            )
        if probe.duration_seconds <= 0:
            raise MediaValidationError(
                f"Clip '{display_name}' ({input_data.source_path}) has non-positive duration ({probe.duration_seconds}s)."
            )

        existing_clips = self._media_repo.list_clips(input_data.project_id)
        item_id = str(uuid.uuid4())
        asset = MediaAsset(
            id=item_id,
            project_id=input_data.project_id,
            kind=MEDIA_KIND_CLIP,
            file_path=probe.path,
            original_filename=display_name,
            position=len(existing_clips),
            duration_seconds=probe.duration_seconds,
            has_video=probe.has_video,
            has_audio=probe.has_audio,
            width=probe.width,
            height=probe.height,
            fps=probe.fps,
            video_codec=probe.video_codec,
            audio_codec=probe.audio_codec,
        )

        record = ProjectMediaItem(
            id=asset.id,
            project_id=asset.project_id,
            kind=asset.kind,
            file_path=asset.file_path,
            original_filename=asset.original_filename,
            position=asset.position,
            duration_seconds=asset.duration_seconds,
            has_video=asset.has_video,
            has_audio=asset.has_audio,
            created_at=datetime.now(timezone.utc).isoformat(),
            width=asset.width,
            height=asset.height,
            fps=asset.fps,
            video_codec=asset.video_codec,
            audio_codec=asset.audio_codec,
        )
        return self._media_repo.add_clip(record)

    def import_audio(self, input_data: NarrationInput) -> ProjectMediaItem:
        self._ensure_project_exists(input_data.project_id)
        if not input_data.source_path or not input_data.source_path.strip():
            raise MediaValidationError("Narration audio source path cannot be empty.")

        display_name = _extract_filename(input_data.source_path, input_data.original_filename)
        probe = self._media_processor.probe(input_data.source_path, display_name=display_name)
        if not probe.has_audio:
            raise MediaValidationError(
                f"Narration audio '{display_name}' ({input_data.source_path}) does not contain a valid decodable audio stream."
            )
        if probe.duration_seconds <= 0:
            raise MediaValidationError(
                f"Narration audio '{display_name}' ({input_data.source_path}) has non-positive duration ({probe.duration_seconds}s)."
            )

        item_id = str(uuid.uuid4())
        asset = MediaAsset(
            id=item_id,
            project_id=input_data.project_id,
            kind=MEDIA_KIND_AUDIO,
            file_path=probe.path,
            original_filename=display_name,
            position=0,
            duration_seconds=probe.duration_seconds,
            has_video=probe.has_video,
            has_audio=probe.has_audio,
            width=probe.width,
            height=probe.height,
            fps=probe.fps,
            video_codec=probe.video_codec,
            audio_codec=probe.audio_codec,
        )

        record = ProjectMediaItem(
            id=asset.id,
            project_id=asset.project_id,
            kind=asset.kind,
            file_path=asset.file_path,
            original_filename=asset.original_filename,
            position=0,
            duration_seconds=asset.duration_seconds,
            has_video=asset.has_video,
            has_audio=asset.has_audio,
            created_at=datetime.now(timezone.utc).isoformat(),
            width=asset.width,
            height=asset.height,
            fps=asset.fps,
            video_codec=asset.video_codec,
            audio_codec=asset.audio_codec,
        )
        return self._media_repo.set_audio(record)
