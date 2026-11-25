"""API routes for project-isolated settings and overrides."""
from typing import Dict, Optional, Union
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.adapters.api.routes.channels import get_channel_repository
from src.adapters.api.routes.presets import get_preset_repository
from src.adapters.api.routes.projects import get_repository
from src.core.dto.project_settings_dto import (
    GetProjectSettingsInput,
    ProjectSettingsResult,
    UpdateProjectSettingsInput,
)
from src.core.entities.preset import PresetValidationError
from src.core.entities.project_settings import ProjectSettingsValidationError
from src.core.ports.channel_repository import ChannelRepository
from src.core.ports.preset_repository import PresetRepository
from src.core.ports.project_repository import ProjectRepository
from src.core.ports.project_settings_repository import ProjectSettingsRepository
from src.core.use_cases.get_project import ProjectNotFoundError
from src.core.use_cases.project_settings_use_cases import (
    GetProjectSettingsUseCase,
    UpdateProjectSettingsUseCase,
)

StageParamScalar = Union[str, float, int, bool]

router = APIRouter(prefix="/projects/{project_id}/settings", tags=["project-settings"])


class UpdateProjectSettingsRequest(BaseModel):
    topic_focus: Optional[str] = None
    language: Optional[str] = None
    narrator: Optional[str] = None
    visual_style: Optional[str] = None
    video_format: Optional[str] = None
    budget_limit_usd: Optional[float] = Field(None, ge=0.0)
    upload_destination: Optional[str] = None
    stage_modes: Optional[Dict[str, str]] = None
    stage_params: Optional[Dict[str, Dict[str, StageParamScalar]]] = None


class ProjectSettingsResponse(BaseModel):
    project_id: str
    updated_at: str
    channel_profile_id: Optional[str] = None
    preset_id: Optional[str] = None
    topic_focus: str
    language: str
    narrator: str
    visual_style: str
    video_format: str
    budget_limit_usd: float
    upload_destination: str
    stage_modes: Dict[str, str]
    stage_params: Dict[str, Dict[str, StageParamScalar]]

    @classmethod
    def from_result(cls, res: ProjectSettingsResult) -> "ProjectSettingsResponse":
        return cls(
            project_id=res.project_id,
            updated_at=res.updated_at,
            channel_profile_id=res.channel_profile_id,
            preset_id=res.preset_id,
            topic_focus=res.topic_focus,
            language=res.language,
            narrator=res.narrator,
            visual_style=res.visual_style,
            video_format=res.video_format,
            budget_limit_usd=res.budget_limit_usd,
            upload_destination=res.upload_destination,
            stage_modes=dict(res.stage_modes),
            stage_params={k: dict(v) for k, v in res.stage_params.items()},
        )


def get_project_settings_repository() -> ProjectSettingsRepository:
    """Dependency provider placeholder overridden at app startup."""
    raise NotImplementedError("Project settings repository dependency must be configured.")


@router.get("", response_model=ProjectSettingsResponse)
def get_project_settings(
    project_id: str,
    settings_repo: ProjectSettingsRepository = Depends(get_project_settings_repository),
    project_repo: ProjectRepository = Depends(get_repository),
    channel_repo: ChannelRepository = Depends(get_channel_repository),
    preset_repo: PresetRepository = Depends(get_preset_repository),
) -> ProjectSettingsResponse:
    try:
        result = GetProjectSettingsUseCase(
            settings_repository=settings_repo,
            project_repository=project_repo,
            channel_repository=channel_repo,
            preset_repository=preset_repo,
        ).execute(GetProjectSettingsInput(project_id=project_id))
        return ProjectSettingsResponse.from_result(result)
    except ProjectNotFoundError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err))


@router.put("", response_model=ProjectSettingsResponse)
@router.patch("", response_model=ProjectSettingsResponse)
def update_project_settings(
    project_id: str,
    request: UpdateProjectSettingsRequest,
    settings_repo: ProjectSettingsRepository = Depends(get_project_settings_repository),
    project_repo: ProjectRepository = Depends(get_repository),
    channel_repo: ChannelRepository = Depends(get_channel_repository),
    preset_repo: PresetRepository = Depends(get_preset_repository),
) -> ProjectSettingsResponse:
    try:
        result = UpdateProjectSettingsUseCase(
            settings_repository=settings_repo,
            project_repository=project_repo,
            channel_repository=channel_repo,
            preset_repository=preset_repo,
        ).execute(
            UpdateProjectSettingsInput(
                project_id=project_id,
                topic_focus=request.topic_focus,
                language=request.language,
                narrator=request.narrator,
                visual_style=request.visual_style,
                video_format=request.video_format,
                budget_limit_usd=request.budget_limit_usd,
                upload_destination=request.upload_destination,
                stage_modes=request.stage_modes,
                stage_params=request.stage_params,
            )
        )
        return ProjectSettingsResponse.from_result(result)
    except ProjectNotFoundError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err))
    except (ProjectSettingsValidationError, PresetValidationError) as err:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(err))
