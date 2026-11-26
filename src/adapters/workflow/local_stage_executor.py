"""Local StageExecutor adapter wiring workflow stages to project settings, assets, and FFmpeg export."""
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from src.core.dto.media_dto import ExportMp4Input, GetProjectMediaInput
from src.core.dto.project_settings_dto import ProjectSettingsResult
from src.core.dto.workflow_dto import (
    StageArtifactDto,
    StageExecutionInput,
    StageExecutionResult,
    StageItemStateDto,
)
from src.core.entities.media import MediaExportError, MediaValidationError
from src.core.entities.workflow import StageStatus
from src.core.ports.asset_repository import ProjectAssetRepository
from src.core.ports.media_processor import MediaProcessor
from src.core.ports.project_media_repository import ProjectMediaRepository
from src.core.ports.project_settings_repository import ProjectSettingsRepository
from src.core.ports.stage_executor import StageExecutor
from src.core.use_cases.export_project_mp4 import ExportProjectMp4UseCase
from src.core.use_cases.get_project_media import GetProjectMediaUseCase


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_dimensions(video_format: str) -> Tuple[int, int]:
    fmt = (video_format or "").strip()
    if fmt == "9:16":
        return (720, 1280)
    if fmt == "1:1":
        return (1080, 1080)
    return (1280, 720)


class LocalStageExecutor(StageExecutor):
    """Executes workflow stages locally using #6 settings/assets and #7 FFmpeg media export."""

    def __init__(
        self,
        media_repository: ProjectMediaRepository,
        media_processor: MediaProcessor,
        media_root: Path,
        settings_repository: Optional[ProjectSettingsRepository] = None,
        asset_repository: Optional[ProjectAssetRepository] = None,
    ) -> None:
        self._media_repository = media_repository
        self._media_processor = media_processor
        self._media_root = media_root
        self._settings_repository = settings_repository
        self._asset_repository = asset_repository

    def execute(self, request: StageExecutionInput) -> StageExecutionResult:
        settings = (
            self._settings_repository.get_by_project_id(request.project_id)
            if self._settings_repository is not None
            else None
        )

        if request.stage_id == "idea":
            return self._execute_idea(request, settings)
        if request.stage_id == "script":
            return self._execute_script(request, settings)
        if request.stage_id == "voice":
            return self._execute_voice(request, settings)
        if request.stage_id == "scenes":
            return self._execute_scenes(request, settings)
        if request.stage_id == "edit":
            return self._execute_edit(request, settings)
        if request.stage_id == "export":
            return self._execute_export(request, settings)

        return StageExecutionResult(
            status="completed",
            artifact=StageArtifactDto(
                artifact_id=f"{request.job_id}-{request.stage_id}-v{request.attempt}",
                stage_id=request.stage_id,
                artifact_type=request.artifact_type,
                data={"stage": request.stage_id, "attempt": request.attempt},
                created_at=_utc_iso(),
            ),
        )

    def _execute_idea(
        self,
        request: StageExecutionInput,
        settings: Optional[ProjectSettingsResult],
    ) -> StageExecutionResult:
        topic = (
            request.params.get("topic_focus")
            or (settings.topic_focus if settings else None)
            or "Documentary Story"
        )
        language = (
            request.params.get("language")
            or (settings.language if settings else None)
            or "Arabic"
        )
        return StageExecutionResult(
            status="completed",
            artifact=StageArtifactDto(
                artifact_id=f"{request.job_id}-idea-v{request.attempt}",
                stage_id="idea",
                artifact_type="topic",
                data={
                    "topic_focus": topic,
                    "language": language,
                    "sources": request.params.get("sources", "Local + Web"),
                },
                created_at=_utc_iso(),
            ),
        )

    def _execute_script(
        self,
        request: StageExecutionInput,
        settings: Optional[ProjectSettingsResult],
    ) -> StageExecutionResult:
        existing_assets = (
            self._asset_repository.list_by_project(request.project_id, asset_type="script")
            if self._asset_repository is not None
            else []
        )
        topic_art = request.dependency_artifacts.get("idea")
        topic_focus = (
            (topic_art.data.get("topic_focus") if topic_art else None)
            or (settings.topic_focus if settings else None)
            or "Project Narrative"
        )
        script_text = (
            existing_assets[-1].content
            if existing_assets and existing_assets[-1].content
            else f"Script draft for {topic_focus}"
        )
        return StageExecutionResult(
            status="completed",
            artifact=StageArtifactDto(
                artifact_id=f"{request.job_id}-script-v{request.attempt}",
                stage_id="script",
                artifact_type="script",
                data={
                    "topic_focus": topic_focus,
                    "text": script_text,
                    "provider": request.params.get("provider", "Local"),
                    "model": request.params.get("model", "local-draft"),
                },
                created_at=_utc_iso(),
            ),
        )

    def _execute_voice(
        self,
        request: StageExecutionInput,
        settings: Optional[ProjectSettingsResult],
    ) -> StageExecutionResult:
        bundle = GetProjectMediaUseCase(self._media_repository).execute(
            GetProjectMediaInput(project_id=request.project_id)
        )
        if bundle.audio is not None:
            audio = bundle.audio
            return StageExecutionResult(
                status="completed",
                artifact=StageArtifactDto(
                    artifact_id=audio.id,
                    stage_id="voice",
                    artifact_type="narration",
                    uri=audio.file_path,
                    data={
                        "media_id": audio.id,
                        "original_filename": audio.original_filename,
                        "duration_seconds": audio.duration_seconds,
                        "audio_codec": audio.audio_codec,
                        "narrator": settings.narrator if settings else "default",
                    },
                    created_at=_utc_iso(),
                ),
            )

        audio_assets = (
            self._asset_repository.list_by_project(request.project_id, asset_type="audio")
            if self._asset_repository is not None
            else []
        )
        if audio_assets:
            latest = audio_assets[-1]
            return StageExecutionResult(
                status="completed",
                artifact=StageArtifactDto(
                    artifact_id=latest.id,
                    stage_id="voice",
                    artifact_type="narration",
                    uri=latest.file_path,
                    data={"asset_id": latest.id, "name": latest.name, "content": latest.content},
                    created_at=_utc_iso(),
                ),
            )

        return StageExecutionResult(
            status="failed",
            error=(
                "No narration audio imported for this project. "
                "Import narration audio in Assets or switch Voice to Manual mode."
            ),
        )

    def _execute_scenes(
        self,
        request: StageExecutionInput,
        settings: Optional[ProjectSettingsResult],
    ) -> StageExecutionResult:
        bundle = GetProjectMediaUseCase(self._media_repository).execute(
            GetProjectMediaInput(project_id=request.project_id)
        )
        clips_by_id = {clip.id: clip for clip in bundle.clips}
        stale_set = set(request.stale_item_ids)
        items: List[StageItemStateDto] = []

        if bundle.clips:
            for clip in bundle.clips:
                preserved = request.preserved_items.get(clip.id)
                if preserved is not None and clip.id not in stale_set:
                    items.append(preserved)
                    continue
                items.append(
                    StageItemStateDto(
                        item_id=clip.id,
                        status=StageStatus.COMPLETED.value,
                        artifact=StageArtifactDto(
                            artifact_id=f"{clip.id}-v{request.attempt}",
                            stage_id="scenes",
                            artifact_type="scene_clip",
                            uri=clip.file_path,
                            data={
                                "clip_id": clip.id,
                                "original_filename": clip.original_filename,
                                "position": clip.position,
                                "duration_seconds": clip.duration_seconds,
                                "attempt": request.attempt,
                            },
                            created_at=_utc_iso(),
                        ),
                        input_data={
                            "filename": clip.original_filename,
                            "file_path": clip.file_path,
                            "position": clip.position,
                        },
                    )
                )
            return StageExecutionResult(
                status="completed",
                artifact=StageArtifactDto(
                    artifact_id=f"{request.job_id}-scenes-v{request.attempt}",
                    stage_id="scenes",
                    artifact_type="scene_clips",
                    data={
                        "clip_ids": [c.id for c in bundle.clips],
                        "clip_count": len(bundle.clips),
                        "visual_style": settings.visual_style if settings else "Cinematic",
                    },
                    created_at=_utc_iso(),
                ),
                items=tuple(items),
            )

        if request.preserved_items or stale_set:
            all_ids = list(dict.fromkeys([*request.preserved_items.keys(), *request.stale_item_ids]))
            for item_id in all_ids:
                if item_id in request.preserved_items and item_id not in stale_set:
                    items.append(request.preserved_items[item_id])
                    continue
                clip = clips_by_id.get(item_id)
                items.append(
                    StageItemStateDto(
                        item_id=item_id,
                        status=StageStatus.COMPLETED.value,
                        artifact=StageArtifactDto(
                            artifact_id=f"{item_id}-v{request.attempt}",
                            stage_id="scenes",
                            artifact_type="scene_clip",
                            uri=clip.file_path if clip else f"scene://{request.project_id}/{item_id}",
                            data={"item_id": item_id, "attempt": request.attempt},
                            created_at=_utc_iso(),
                        ),
                    )
                )
            return StageExecutionResult(
                status="completed",
                artifact=StageArtifactDto(
                    artifact_id=f"{request.job_id}-scenes-v{request.attempt}",
                    stage_id="scenes",
                    artifact_type="scene_clips",
                    data={"item_ids": all_ids, "clip_count": len(all_ids)},
                    created_at=_utc_iso(),
                ),
                items=tuple(items),
            )

        return StageExecutionResult(
            status="failed",
            error=(
                "No moving scene clips imported for this project. "
                "Import video clips in Assets or switch Scenes to Manual mode."
            ),
        )

    def _execute_edit(
        self,
        request: StageExecutionInput,
        settings: Optional[ProjectSettingsResult],
    ) -> StageExecutionResult:
        voice_art = request.dependency_artifacts.get("voice")
        scenes_art = request.dependency_artifacts.get("scenes")
        if voice_art is None or scenes_art is None:
            return StageExecutionResult(
                status="failed",
                error="Edit stage requires both narration ('voice') and scene clips ('scenes') artifacts.",
            )

        width, height = _resolve_dimensions(settings.video_format if settings else "16:9")
        bundle = GetProjectMediaUseCase(self._media_repository).execute(
            GetProjectMediaInput(project_id=request.project_id)
        )
        return StageExecutionResult(
            status="completed",
            artifact=StageArtifactDto(
                artifact_id=f"{request.job_id}-edit-v{request.attempt}",
                stage_id="edit",
                artifact_type="edited_video",
                data={
                    "clip_ids": [c.id for c in bundle.clips],
                    "audio_id": bundle.audio.id if bundle.audio else voice_art.artifact_id,
                    "target_width": width,
                    "target_height": height,
                    "target_fps": 30,
                    "attempt": request.attempt,
                },
                created_at=_utc_iso(),
            ),
        )

    def _execute_export(
        self,
        request: StageExecutionInput,
        settings: Optional[ProjectSettingsResult],
    ) -> StageExecutionResult:
        width, height = _resolve_dimensions(settings.video_format if settings else "16:9")
        output_dir = self._media_root / request.project_id / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "export.mp4"
        try:
            export_result = ExportProjectMp4UseCase(
                media_repo=self._media_repository,
                media_processor=self._media_processor,
            ).execute(
                ExportMp4Input(
                    project_id=request.project_id,
                    output_path=str(output_path),
                    target_width=width,
                    target_height=height,
                    target_fps=30,
                )
            )
        except (MediaValidationError, MediaExportError) as err:
            return StageExecutionResult(status="failed", error=str(err))

        return StageExecutionResult(
            status="completed",
            artifact=StageArtifactDto(
                artifact_id=export_result.id,
                stage_id="export",
                artifact_type="final_video",
                uri=export_result.output_path,
                data={
                    "export_id": export_result.id,
                    "output_path": export_result.output_path,
                    "duration_seconds": export_result.duration_seconds,
                    "width": export_result.width,
                    "height": export_result.height,
                    "fps": export_result.fps,
                    "file_size_bytes": export_result.file_size_bytes,
                    "clip_ids": list(export_result.clip_ids),
                    "audio_id": export_result.audio_id,
                },
                created_at=export_result.created_at,
            ),
        )
