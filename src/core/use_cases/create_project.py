"""Use case for creating a new project."""
import uuid
from datetime import datetime, timezone
from src.core.dto.project_dto import CreateProjectInput, ProjectResult
from src.core.entities.project import Project, ProjectValidationError
from src.core.ports.project_repository import ProjectRepository


class CreateProjectUseCase:
    """Creates and persists a new project using plain input and result records."""

    def __init__(self, repository: ProjectRepository) -> None:
        self._repository = repository

    def execute(self, input_data: CreateProjectInput) -> ProjectResult:
        if not input_data.name or not input_data.name.strip():
            raise ProjectValidationError("Project name cannot be empty.")

        now = datetime.now(timezone.utc)
        project_id = str(uuid.uuid4())

        project = Project(
            id=project_id,
            name=input_data.name.strip(),
            description=input_data.description.strip(),
            created_at=now,
            updated_at=now,
            channel_profile_id=input_data.channel_profile_id,
        )

        result = ProjectResult(
            id=project.id,
            name=project.name,
            description=project.description,
            created_at=project.created_at.isoformat(),
            updated_at=project.updated_at.isoformat(),
            channel_profile_id=project.channel_profile_id,
        )
        self._repository.save(result)
        return result
