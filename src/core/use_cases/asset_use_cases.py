"""Use cases for managing project-isolated assets."""
import uuid
from datetime import datetime, timezone
from typing import List

from src.core.dto.asset_dto import (
    CreateProjectAssetInput,
    DeleteProjectAssetInput,
    ListProjectAssetsInput,
    ProjectAssetResult,
)
from src.core.entities.project_asset import (
    VALID_ASSET_TYPES,
    AssetValidationError,
    ProjectAsset,
)
from src.core.ports.asset_repository import ProjectAssetRepository
from src.core.ports.project_repository import ProjectRepository
from src.core.use_cases.get_project import ProjectNotFoundError


class AssetNotFoundError(Exception):
    """Raised when a requested project asset cannot be found for the project."""
    pass


def _asset_to_result(asset: ProjectAsset) -> ProjectAssetResult:
    return ProjectAssetResult(
        id=asset.id,
        project_id=asset.project_id,
        asset_type=asset.asset_type,
        name=asset.name,
        content=asset.content,
        file_path=asset.file_path,
        metadata=dict(asset.metadata),
        created_at=asset.created_at.isoformat(),
        updated_at=asset.updated_at.isoformat(),
    )


class CreateProjectAssetUseCase:
    """Creates and persists an asset strictly scoped to a single project."""

    def __init__(
        self,
        asset_repository: ProjectAssetRepository,
        project_repository: ProjectRepository,
    ) -> None:
        self._asset_repository = asset_repository
        self._project_repository = project_repository

    def execute(self, input_data: CreateProjectAssetInput) -> ProjectAssetResult:
        project = self._project_repository.get_by_id(input_data.project_id)
        if project is None:
            raise ProjectNotFoundError(f"Project with ID '{input_data.project_id}' not found.")

        now = datetime.now(timezone.utc)
        asset = ProjectAsset(
            id=str(uuid.uuid4()),
            project_id=input_data.project_id,
            asset_type=input_data.asset_type,
            name=input_data.name,
            content=input_data.content,
            file_path=input_data.file_path,
            metadata=dict(input_data.metadata or {}),
            created_at=now,
            updated_at=now,
        )
        result = _asset_to_result(asset)
        self._asset_repository.save(result)
        return result


class ListProjectAssetsUseCase:
    """Lists assets owned exclusively by the specified project."""

    def __init__(
        self,
        asset_repository: ProjectAssetRepository,
        project_repository: ProjectRepository,
    ) -> None:
        self._asset_repository = asset_repository
        self._project_repository = project_repository

    def execute(self, input_data: ListProjectAssetsInput) -> List[ProjectAssetResult]:
        project = self._project_repository.get_by_id(input_data.project_id)
        if project is None:
            raise ProjectNotFoundError(f"Project with ID '{input_data.project_id}' not found.")

        if input_data.asset_type is not None and input_data.asset_type not in VALID_ASSET_TYPES:
            raise AssetValidationError(
                f"Invalid asset type '{input_data.asset_type}'. Must be one of: {', '.join(VALID_ASSET_TYPES)}."
            )

        return self._asset_repository.list_by_project(
            project_id=input_data.project_id,
            asset_type=input_data.asset_type,
        )


class DeleteProjectAssetUseCase:
    """Deletes an asset only if it belongs to the specified project."""

    def __init__(
        self,
        asset_repository: ProjectAssetRepository,
        project_repository: ProjectRepository,
    ) -> None:
        self._asset_repository = asset_repository
        self._project_repository = project_repository

    def execute(self, input_data: DeleteProjectAssetInput) -> bool:
        project = self._project_repository.get_by_id(input_data.project_id)
        if project is None:
            raise ProjectNotFoundError(f"Project with ID '{input_data.project_id}' not found.")

        return self._asset_repository.delete(
            project_id=input_data.project_id,
            asset_id=input_data.asset_id,
        )
