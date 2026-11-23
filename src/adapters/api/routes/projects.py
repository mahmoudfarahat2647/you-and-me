"""API routes for managing projects."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.core.dto.project_dto import CreateProjectInput, GetProjectInput, ProjectResult
from src.core.entities.project import ProjectValidationError
from src.core.ports.project_repository import ProjectRepository
from src.core.use_cases.create_project import CreateProjectUseCase
from src.core.use_cases.get_project import GetProjectUseCase
from src.core.use_cases.list_projects import ListProjectsUseCase

router = APIRouter(prefix="/projects", tags=["projects"])


class CreateProjectRequest(BaseModel):
    name: str = Field(..., min_length=1, description="Name of the project")
    description: Optional[str] = Field("", description="Optional project description")
    channel_profile_id: Optional[str] = Field(None, description="Associated channel profile")


class ProjectResponse(BaseModel):
    id: str
    name: str
    description: str
    created_at: str
    updated_at: str
    channel_profile_id: Optional[str] = None

    @classmethod
    def from_result(cls, res: ProjectResult) -> "ProjectResponse":
        return cls(
            id=res.id,
            name=res.name,
            description=res.description,
            created_at=res.created_at,
            updated_at=res.updated_at,
            channel_profile_id=res.channel_profile_id,
        )


def get_repository() -> ProjectRepository:
    """Dependency provider placeholder overridden at app startup."""
    raise NotImplementedError("Repository dependency must be configured.")


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    request: CreateProjectRequest,
    repo: ProjectRepository = Depends(get_repository),
) -> ProjectResponse:
    try:
        use_case = CreateProjectUseCase(repo)
        input_dto = CreateProjectInput(
            name=request.name,
            description=request.description or "",
            channel_profile_id=request.channel_profile_id,
        )
        result = use_case.execute(input_dto)
        return ProjectResponse.from_result(result)
    except ProjectValidationError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(err),
        )


@router.get("", response_model=List[ProjectResponse])
def list_projects(
    repo: ProjectRepository = Depends(get_repository),
) -> List[ProjectResponse]:
    use_case = ListProjectsUseCase(repo)
    results = use_case.execute()
    return [ProjectResponse.from_result(r) for r in results]


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: str,
    repo: ProjectRepository = Depends(get_repository),
) -> ProjectResponse:
    use_case = GetProjectUseCase(repo)
    result = use_case.execute(GetProjectInput(id=project_id))
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID '{project_id}' not found.",
        )
    return ProjectResponse.from_result(result)
