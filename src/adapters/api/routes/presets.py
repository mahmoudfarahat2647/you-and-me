"""API routes for managing workflow presets."""
from typing import Dict, List, Optional, Union
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.core.dto.preset_dto import CreatePresetInput, WorkflowPresetResult
from src.core.entities.preset import PresetValidationError
from src.core.ports.preset_repository import PresetRepository
from src.core.use_cases.preset_use_cases import (
    CreatePresetUseCase,
    GetPresetUseCase,
    ListPresetsUseCase,
)

StageParamScalar = Union[str, float, int, bool]

router = APIRouter(prefix="/presets", tags=["presets"])


class CreatePresetRequest(BaseModel):
    name: str = Field(..., min_length=1)
    description: str = Field("")
    default_stage_modes: Optional[Dict[str, str]] = None
    default_stage_params: Optional[Dict[str, Dict[str, StageParamScalar]]] = None


class PresetResponse(BaseModel):
    id: str
    name: str
    description: str
    default_stage_modes: Dict[str, str]
    default_stage_params: Dict[str, Dict[str, StageParamScalar]]
    is_builtin: bool

    @classmethod
    def from_result(cls, res: WorkflowPresetResult) -> "PresetResponse":
        return cls(
            id=res.id,
            name=res.name,
            description=res.description,
            default_stage_modes=dict(res.default_stage_modes),
            default_stage_params={k: dict(v) for k, v in res.default_stage_params.items()},
            is_builtin=res.is_builtin,
        )


def get_preset_repository() -> PresetRepository:
    """Dependency provider placeholder overridden at app startup."""
    raise NotImplementedError("Preset repository dependency must be configured.")


@router.get("", response_model=List[PresetResponse])
def list_presets(
    repo: PresetRepository = Depends(get_preset_repository),
) -> List[PresetResponse]:
    results = ListPresetsUseCase(repo).execute()
    return [PresetResponse.from_result(item) for item in results]


@router.post("", response_model=PresetResponse, status_code=status.HTTP_201_CREATED)
def create_preset(
    request: CreatePresetRequest,
    repo: PresetRepository = Depends(get_preset_repository),
) -> PresetResponse:
    try:
        result = CreatePresetUseCase(repo).execute(
            CreatePresetInput(
                name=request.name,
                description=request.description,
                default_stage_modes=request.default_stage_modes,
                default_stage_params=request.default_stage_params,
            )
        )
        return PresetResponse.from_result(result)
    except PresetValidationError as err:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(err))


@router.get("/{preset_id}", response_model=PresetResponse)
def get_preset(
    preset_id: str,
    repo: PresetRepository = Depends(get_preset_repository),
) -> PresetResponse:
    result = GetPresetUseCase(repo).execute(preset_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow preset '{preset_id}' not found.",
        )
    return PresetResponse.from_result(result)
