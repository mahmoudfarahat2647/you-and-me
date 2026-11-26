"""Use case for validating inputs and exporting a playable MP4 artifact."""
import uuid
from datetime import datetime, timezone
from typing import Optional

from src.core.dto.media_dto import ExportMp4Input, ExportMp4Result
from src.core.entities.media import MediaExportError, MediaValidationError
from src.core.ports.media_processor import MediaProcessor
from src.core.ports.project_media_repository import ProjectMediaRepository
from src.core.ports.project_repository import ProjectRepository


class ExportProjectMp4UseCase:
    """Combines ordered project clips with narration audio into a verified MP4."""

    def __init__(
        self,
        media_repo: ProjectMediaRepository,
        media_processor: MediaProcessor,
        project_repo: Optional[ProjectRepository] = None,
    ) -> None:
        self._media_repo = media_repo
        self._media_processor = media_processor
        self._project_repo = project_repo

    def execute(self, input_data: ExportMp4Input) -> ExportMp4Result:
        if not input_data.project_id or not input_data.project_id.strip():
            raise MediaExportError("Project ID cannot be empty.")
        if not input_data.output_path or not input_data.output_path.strip():
            raise MediaExportError("Export output path cannot be empty.")
        if self._project_repo is not None and self._project_repo.get_by_id(input_data.project_id) is None:
            raise MediaExportError(f"Project '{input_data.project_id}' was not found.")
        if input_data.target_width <= 0 or input_data.target_height <= 0 or input_data.target_fps <= 0:
            raise MediaExportError("Target width, height, and FPS must be positive numbers.")

        clips = self._media_repo.list_clips(input_data.project_id)
        if not clips:
            raise MediaExportError("Cannot export MP4: at least one video clip is required.")

        audio = self._media_repo.get_audio(input_data.project_id)
        if audio is None:
            raise MediaExportError("Cannot export MP4: narration audio is required.")

        # Validate every input before attempting export so prior valid exports are never disturbed.
        for clip in clips:
            try:
                probe = self._media_processor.probe(clip.file_path, display_name=clip.original_filename)
            except MediaValidationError as err:
                raise MediaExportError(str(err)) from err
            if not probe.has_video or (probe.width or 0) <= 0 or (probe.height or 0) <= 0 or probe.duration_seconds <= 0:
                raise MediaExportError(
                    f"Clip '{clip.original_filename}' ({clip.file_path}) does not contain a valid decodable video stream."
                )

        try:
            audio_probe = self._media_processor.probe(audio.file_path, display_name=audio.original_filename)
        except MediaValidationError as err:
            raise MediaExportError(str(err)) from err
        if not audio_probe.has_audio or audio_probe.duration_seconds <= 0:
            raise MediaExportError(
                f"Narration audio '{audio.original_filename}' ({audio.file_path}) does not contain a valid decodable audio stream."
            )

        output_probe = self._media_processor.export_mp4(
            clip_paths=[clip.file_path for clip in clips],
            audio_path=audio.file_path,
            output_path=input_data.output_path,
            target_width=input_data.target_width,
            target_height=input_data.target_height,
            target_fps=input_data.target_fps,
            clip_labels=[clip.original_filename for clip in clips],
            audio_label=audio.original_filename,
        )

        if not output_probe.has_video or not output_probe.has_audio or output_probe.duration_seconds <= 0:
            raise MediaExportError(
                f"Exported MP4 '{input_data.output_path}' failed verification: missing decodable video or audio stream."
            )

        result = ExportMp4Result(
            id=str(uuid.uuid4()),
            project_id=input_data.project_id,
            output_path=output_probe.path,
            duration_seconds=output_probe.duration_seconds,
            width=output_probe.width or input_data.target_width,
            height=output_probe.height or input_data.target_height,
            fps=output_probe.fps or float(input_data.target_fps),
            has_video=output_probe.has_video,
            has_audio=output_probe.has_audio,
            file_size_bytes=output_probe.file_size_bytes,
            clip_ids=[clip.id for clip in clips],
            created_at=datetime.now(timezone.utc).isoformat(),
            video_codec=output_probe.video_codec,
            audio_codec=output_probe.audio_codec,
            audio_id=audio.id,
        )
        self._media_repo.save_export(result)
        return result
