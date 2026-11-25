"""Use cases for retrieving and overriding project-isolated settings."""
from datetime import datetime, timezone
from typing import Optional

from src.core.dto.channel_dto import ChannelProfileResult
from src.core.dto.preset_dto import WorkflowPresetResult
from src.core.dto.project_settings_dto import (
    GetProjectSettingsInput,
    ProjectSettingsResult,
    UpdateProjectSettingsInput,
)
from src.core.entities.preset import validate_stage_modes
from src.core.entities.project_settings import (
    ProjectSettings,
    default_stage_modes,
    default_stage_params,
    merge_stage_params,
)
from src.core.ports.channel_repository import ChannelRepository
from src.core.ports.preset_repository import PresetRepository
from src.core.ports.project_repository import ProjectRepository
from src.core.ports.project_settings_repository import ProjectSettingsRepository
from src.core.use_cases.get_project import ProjectNotFoundError


def build_initial_project_settings(
    project_id: str,
    channel: Optional[ChannelProfileResult] = None,
    preset: Optional[WorkflowPresetResult] = None,
    now: Optional[datetime] = None,
) -> ProjectSettingsResult:
    """Copy channel and preset defaults into an isolated ProjectSettingsResult."""
    timestamp = now or datetime.now(timezone.utc)
    stage_modes = default_stage_modes()
    stage_params = default_stage_params()

    if preset is not None:
        stage_modes.update(preset.default_stage_modes)
        stage_params = merge_stage_params(stage_params, preset.default_stage_params)

    entity = ProjectSettings(
        project_id=project_id,
        updated_at=timestamp,
        channel_profile_id=channel.id if channel is not None else None,
        preset_id=preset.id if preset is not None else None,
        topic_focus=channel.topic_focus if channel is not None else "",
        language=channel.language if channel is not None else "Arabic",
        narrator=channel.default_narrator if channel is not None else "arabic-narrator-v2",
        visual_style=channel.visual_style if channel is not None else "Cinematic Documentary",
        video_format=channel.video_format if channel is not None else "16:9",
        budget_limit_usd=channel.budget_limit_usd if channel is not None else 10.0,
        upload_destination=channel.upload_destination if channel is not None else "Local MP4",
        stage_modes=stage_modes,
        stage_params=stage_params,
    )
    return _settings_to_result(entity)


def _settings_to_result(settings: ProjectSettings) -> ProjectSettingsResult:
    return ProjectSettingsResult(
        project_id=settings.project_id,
        updated_at=settings.updated_at.isoformat(),
        channel_profile_id=settings.channel_profile_id,
        preset_id=settings.preset_id,
        topic_focus=settings.topic_focus,
        language=settings.language,
        narrator=settings.narrator,
        visual_style=settings.visual_style,
        video_format=settings.video_format,
        budget_limit_usd=settings.budget_limit_usd,
        upload_destination=settings.upload_destination,
        stage_modes=dict(settings.stage_modes),
        stage_params={k: dict(v) for k, v in settings.stage_params.items()},
    )


class GetProjectSettingsUseCase:
    """Retrieves project-specific settings, initializing defaults if none exist yet."""

    def __init__(
        self,
        settings_repository: ProjectSettingsRepository,
        project_repository: ProjectRepository,
        channel_repository: Optional[ChannelRepository] = None,
        preset_repository: Optional[PresetRepository] = None,
    ) -> None:
        self._settings_repository = settings_repository
        self._project_repository = project_repository
        self._channel_repository = channel_repository
        self._preset_repository = preset_repository

    def execute(self, input_data: GetProjectSettingsInput) -> ProjectSettingsResult:
        project = self._project_repository.get_by_id(input_data.project_id)
        if project is None:
            raise ProjectNotFoundError(f"Project with ID '{input_data.project_id}' not found.")

        existing = self._settings_repository.get_by_project_id(input_data.project_id)
        if existing is not None:
            return existing

        channel = (
            self._channel_repository.get_by_id(project.channel_profile_id)
            if self._channel_repository is not None and project.channel_profile_id
            else None
        )
        preset = (
            self._preset_repository.get_by_id(project.preset_id)
            if self._preset_repository is not None and project.preset_id
            else None
        )
        initial = build_initial_project_settings(
            project_id=project.id,
            channel=channel,
            preset=preset,
        )
        self._settings_repository.save(initial)
        return initial


class UpdateProjectSettingsUseCase:
    """Applies project-scoped settings overrides without mutating channels, presets, or other projects."""

    def __init__(
        self,
        settings_repository: ProjectSettingsRepository,
        project_repository: ProjectRepository,
        channel_repository: Optional[ChannelRepository] = None,
        preset_repository: Optional[PresetRepository] = None,
    ) -> None:
        self._settings_repository = settings_repository
        self._project_repository = project_repository
        self._channel_repository = channel_repository
        self._preset_repository = preset_repository

    def execute(self, input_data: UpdateProjectSettingsInput) -> ProjectSettingsResult:
        current = GetProjectSettingsUseCase(
            settings_repository=self._settings_repository,
            project_repository=self._project_repository,
            channel_repository=self._channel_repository,
            preset_repository=self._preset_repository,
        ).execute(GetProjectSettingsInput(project_id=input_data.project_id))

        next_stage_modes = dict(current.stage_modes)
        if input_data.stage_modes is not None:
            next_stage_modes.update(validate_stage_modes(input_data.stage_modes))

        next_stage_params = merge_stage_params(
            current.stage_params,
            input_data.stage_params or {},
        )

        updated = ProjectSettings(
            project_id=current.project_id,
            updated_at=datetime.now(timezone.utc),
            channel_profile_id=current.channel_profile_id,
            preset_id=current.preset_id,
            topic_focus=input_data.topic_focus if input_data.topic_focus is not None else current.topic_focus,
            language=input_data.language if input_data.language is not None else current.language,
            narrator=input_data.narrator if input_data.narrator is not None else current.narrator,
            visual_style=input_data.visual_style if input_data.visual_style is not None else current.visual_style,
            video_format=input_data.video_format if input_data.video_format is not None else current.video_format,
            budget_limit_usd=(
                input_data.budget_limit_usd
                if input_data.budget_limit_usd is not None
                else current.budget_limit_usd
            ),
            upload_destination=(
                input_data.upload_destination
                if input_data.upload_destination is not None
                else current.upload_destination
            ),
            stage_modes=next_stage_modes,
            stage_params=next_stage_params,
        )
        result = _settings_to_result(updated)
        self._settings_repository.save(result)
        return result
