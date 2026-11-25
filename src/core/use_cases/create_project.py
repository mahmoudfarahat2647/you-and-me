"""Use case for creating a new project with channel/preset default inheritance."""
import uuid
from datetime import datetime, timezone
from typing import Optional

from src.core.dto.project_dto import CreateProjectInput, ProjectResult
from src.core.entities.project import Project, ProjectValidationError
from src.core.ports.channel_repository import ChannelRepository
from src.core.ports.preset_repository import PresetRepository
from src.core.ports.project_repository import ProjectRepository
from src.core.ports.project_settings_repository import ProjectSettingsRepository
from src.core.use_cases.channel_use_cases import ChannelNotFoundError
from src.core.use_cases.preset_use_cases import PresetNotFoundError
from src.core.use_cases.project_settings_use_cases import build_initial_project_settings


class CreateProjectUseCase:
    """Creates and persists a new project using plain input and result records."""

    def __init__(
        self,
        repository: ProjectRepository,
        channel_repository: Optional[ChannelRepository] = None,
        preset_repository: Optional[PresetRepository] = None,
        settings_repository: Optional[ProjectSettingsRepository] = None,
    ) -> None:
        self._repository = repository
        self._channel_repository = channel_repository
        self._preset_repository = preset_repository
        self._settings_repository = settings_repository

    def execute(self, input_data: CreateProjectInput) -> ProjectResult:
        if not input_data.name or not input_data.name.strip():
            raise ProjectValidationError("Project name cannot be empty.")

        channel = None
        if input_data.channel_profile_id and self._channel_repository is not None:
            channel = self._channel_repository.get_by_id(input_data.channel_profile_id)
            if channel is None:
                raise ChannelNotFoundError(
                    f"Channel profile '{input_data.channel_profile_id}' not found."
                )

        preset = None
        if input_data.preset_id and self._preset_repository is not None:
            preset = self._preset_repository.get_by_id(input_data.preset_id)
            if preset is None:
                raise PresetNotFoundError(
                    f"Workflow preset '{input_data.preset_id}' not found."
                )

        now = datetime.now(timezone.utc)
        project_id = str(uuid.uuid4())

        project = Project(
            id=project_id,
            name=input_data.name.strip(),
            description=input_data.description.strip(),
            created_at=now,
            updated_at=now,
            channel_profile_id=input_data.channel_profile_id,
            preset_id=input_data.preset_id,
        )

        result = ProjectResult(
            id=project.id,
            name=project.name,
            description=project.description,
            created_at=project.created_at.isoformat(),
            updated_at=project.updated_at.isoformat(),
            channel_profile_id=project.channel_profile_id,
            preset_id=project.preset_id,
        )
        self._repository.save(result)

        if self._settings_repository is not None:
            initial_settings = build_initial_project_settings(
                project_id=project.id,
                channel=channel,
                preset=preset,
                now=now,
            )
            self._settings_repository.save(initial_settings)

        return result
