"""Use cases for workflow presets and built-in seeding."""
import uuid
from typing import List, Optional

from src.core.dto.preset_dto import CreatePresetInput, WorkflowPresetResult
from src.core.entities.preset import (
    WorkflowPreset,
    get_builtin_presets,
)
from src.core.ports.preset_repository import PresetRepository


class PresetNotFoundError(Exception):
    """Raised when a requested workflow preset cannot be found."""
    pass


def _preset_to_result(preset: WorkflowPreset) -> WorkflowPresetResult:
    return WorkflowPresetResult(
        id=preset.id,
        name=preset.name,
        description=preset.description,
        default_stage_modes=dict(preset.default_stage_modes),
        default_stage_params={k: dict(v) for k, v in preset.default_stage_params.items()},
        is_builtin=preset.is_builtin,
    )


class CreatePresetUseCase:
    """Creates and persists a custom workflow preset."""

    def __init__(self, repository: PresetRepository) -> None:
        self._repository = repository

    def execute(self, input_data: CreatePresetInput) -> WorkflowPresetResult:
        preset = WorkflowPreset(
            id=str(uuid.uuid4()),
            name=input_data.name,
            description=input_data.description,
            default_stage_modes=dict(input_data.default_stage_modes or {}),
            default_stage_params={
                k: dict(v) for k, v in (input_data.default_stage_params or {}).items()
            },
            is_builtin=False,
        )
        result = _preset_to_result(preset)
        self._repository.save(result)
        return result


class GetPresetUseCase:
    """Retrieves a workflow preset by ID."""

    def __init__(self, repository: PresetRepository) -> None:
        self._repository = repository

    def execute(self, preset_id: str) -> Optional[WorkflowPresetResult]:
        return self._repository.get_by_id(preset_id)


class ListPresetsUseCase:
    """Lists all presets, seeding built-in presets if the repository is empty."""

    def __init__(self, repository: PresetRepository) -> None:
        self._repository = repository

    def execute(self) -> List[WorkflowPresetResult]:
        existing = self._repository.list_all()
        if not existing:
            for builtin in get_builtin_presets():
                self._repository.save(_preset_to_result(builtin))
            existing = self._repository.list_all()
        return existing
