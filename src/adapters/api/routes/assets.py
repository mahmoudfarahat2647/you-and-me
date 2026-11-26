"""API routes for project-isolated assets."""
from typing import Dict, List, Optional, Union
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from src.adapters.api.routes.projects import get_repository
from src.core.dto.asset_dto import (
    CreateProjectAssetInput,
    DeleteProjectAssetInput,
    ListProjectAssetsInput,
    ProjectAssetResult,
)
from src.core.entities.project_asset import AssetValidationError
from src.core.ports.asset_repository import ProjectAssetRepository
from src.core.ports.project_repository import ProjectRepository
from src.core.use_cases.asset_use_cases import (
    CreateProjectAssetUseCase,
    DeleteProjectAssetUseCase,
    ListProjectAssetsUseCase,
)
from src.core.use_cases.get_project import ProjectNotFoundError

StageParamScalar = Union[str, float, int, bool]

router = APIRouter(prefix="/projects/{project_id}/assets", tags=["project-assets"])


class CreateProjectAssetRequest(BaseModel):
    asset_type: str = Field(..., description="script, scene, audio, or export")
    name: str = Field(..., min_length=1)
    content: str = Field("")
    file_path: Optional[str] = None
    metadata: Optional[Dict[str, StageParamScalar]] = None


class ProjectAssetResponse(BaseModel):
    id: str
    project_id: str
    asset_type: str
    name: str
    content: str
    file_path: Optional[str] = None
    metadata: Dict[str, StageParamScalar]
    created_at: str
    updated_at: str

    @classmethod
    def from_result(cls, res: ProjectAssetResult) -> "ProjectAssetResponse":
        return cls(
            id=res.id,
            project_id=res.project_id,
            asset_type=res.asset_type,
            name=res.name,
            content=res.content,
            file_path=res.file_path,
            metadata=dict(res.metadata),
            created_at=res.created_at,
            updated_at=res.updated_at,
        )


def get_asset_repository() -> ProjectAssetRepository:
    """Dependency provider placeholder overridden at app startup."""
    raise NotImplementedError("Asset repository dependency must be configured.")


@router.get("", response_model=List[ProjectAssetResponse])
def list_project_assets(
    project_id: str,
    asset_type: Optional[str] = Query(None),
    asset_repo: ProjectAssetRepository = Depends(get_asset_repository),
    project_repo: ProjectRepository = Depends(get_repository),
) -> List[ProjectAssetResponse]:
    try:
        results = ListProjectAssetsUseCase(asset_repo, project_repo).execute(
            ListProjectAssetsInput(project_id=project_id, asset_type=asset_type)
        )
        return [ProjectAssetResponse.from_result(item) for item in results]
    except ProjectNotFoundError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err))
    except AssetValidationError as err:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(err))


@router.post("", response_model=ProjectAssetResponse, status_code=status.HTTP_201_CREATED)
def create_project_asset(
    project_id: str,
    request: CreateProjectAssetRequest,
    asset_repo: ProjectAssetRepository = Depends(get_asset_repository),
    project_repo: ProjectRepository = Depends(get_repository),
) -> ProjectAssetResponse:
    try:
        result = CreateProjectAssetUseCase(asset_repo, project_repo).execute(
            CreateProjectAssetInput(
                project_id=project_id,
                asset_type=request.asset_type,
                name=request.name,
                content=request.content,
                file_path=request.file_path,
                metadata=request.metadata,
            )
        )
        return ProjectAssetResponse.from_result(result)
    except ProjectNotFoundError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err))
    except AssetValidationError as err:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(err))


@router.delete("/{asset_id}")
def delete_project_asset(
    project_id: str,
    asset_id: str,
    asset_repo: ProjectAssetRepository = Depends(get_asset_repository),
    project_repo: ProjectRepository = Depends(get_repository),
) -> Dict[str, bool]:
    try:
        deleted = DeleteProjectAssetUseCase(asset_repo, project_repo).execute(
            DeleteProjectAssetInput(project_id=project_id, asset_id=asset_id)
        )
    except ProjectNotFoundError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err))

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Asset '{asset_id}' not found for project '{project_id}'.",
        )
    return {"deleted": True}
