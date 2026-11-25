"""Plain input and result records for workflow presets."""
from dataclasses import dataclass, field
from typing import Dict, Optional
from src.core.entities.preset import StageParamDict


@dataclass(frozen=True)
class CreatePresetInput:
    """Plain input record for creating a workflow preset."""
    name: str
    description: str = ""
    default_stage_modes: Optional[Dict[str, str]] = None
    default_stage_params: Optional[StageParamDict] = None


@dataclass(frozen=True)
class WorkflowPresetResult:
    """Plain result record representing a workflow preset across boundaries."""
    id: str
    name: str
    description: str
    default_stage_modes: Dict[str, str] = field(default_factory=dict)
    default_stage_params: StageParamDict = field(default_factory=dict)
    is_builtin: bool = False
