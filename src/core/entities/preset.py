"""Core domain entity and built-in definitions for workflow presets."""
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Union

StageParamScalar = Union[str, float, int, bool]
StageParamDict = Dict[str, Dict[str, StageParamScalar]]

VALID_STAGE_IDS: Tuple[str, ...] = ("idea", "script", "voice", "scenes", "edit", "export")
VALID_STAGE_MODES: Tuple[str, ...] = ("auto", "manual", "approval", "off")


class PresetValidationError(Exception):
    """Raised when workflow preset domain validation fails."""
    pass


def validate_stage_modes(stage_modes: Dict[str, str]) -> Dict[str, str]:
    """Validate and normalize a stage -> execution mode mapping."""
    normalized: Dict[str, str] = {}
    for stage_id, mode in stage_modes.items():
        if stage_id not in VALID_STAGE_IDS:
            raise PresetValidationError(f"Invalid stage ID '{stage_id}'.")
        if mode not in VALID_STAGE_MODES:
            raise PresetValidationError(f"Invalid stage mode '{mode}' for stage '{stage_id}'.")
        normalized[stage_id] = mode
    return normalized


@dataclass
class WorkflowPreset:
    """Workflow preset domain entity."""
    id: str
    name: str
    description: str
    default_stage_modes: Dict[str, str] = field(default_factory=dict)
    default_stage_params: StageParamDict = field(default_factory=dict)
    is_builtin: bool = False

    def __post_init__(self) -> None:
        if not self.id or not self.id.strip():
            raise PresetValidationError("Preset ID cannot be empty.")
        if not self.name or not self.name.strip():
            raise PresetValidationError("Preset name cannot be empty.")

        self.id = self.id.strip()
        self.name = self.name.strip()
        self.description = self.description.strip()

        validated_modes = validate_stage_modes(self.default_stage_modes)
        for stage_id in VALID_STAGE_IDS:
            validated_modes.setdefault(stage_id, "auto")
        self.default_stage_modes = validated_modes

        self.default_stage_params = {
            stage_id: dict(params)
            for stage_id, params in self.default_stage_params.items()
            if stage_id in VALID_STAGE_IDS
        }


def get_builtin_presets() -> List[WorkflowPreset]:
    """Return canonical built-in workflow presets."""
    return [
        WorkflowPreset(
            id="preset-full-auto",
            name="Full Auto",
            description="Run every production stage automatically from idea to export.",
            default_stage_modes={stage_id: "auto" for stage_id in VALID_STAGE_IDS},
            default_stage_params={
                "script": {"provider": "ChatGPT", "model": "GPT-4o", "script_length": "~ 8 minutes"},
                "export": {"target": "Local MP4", "visibility": "Private"},
            },
            is_builtin=True,
        ),
        WorkflowPreset(
            id="preset-review-before-publish",
            name="Review Before Publish",
            description="Automate drafts and media, with approval gates before script lock and export.",
            default_stage_modes={
                "idea": "auto",
                "script": "approval",
                "voice": "auto",
                "scenes": "auto",
                "edit": "auto",
                "export": "approval",
            },
            default_stage_params={
                "script": {"provider": "Claude", "model": "Claude-3-5-Sonnet", "script_length": "~ 8 minutes"},
                "export": {"target": "Local MP4", "visibility": "Unlisted"},
            },
            is_builtin=True,
        ),
        WorkflowPreset(
            id="preset-manual-studio",
            name="Manual Studio",
            description="Keep creative decisions manual while preserving studio pipeline structure.",
            default_stage_modes={
                "idea": "manual",
                "script": "manual",
                "voice": "manual",
                "scenes": "manual",
                "edit": "manual",
                "export": "approval",
            },
            default_stage_params={
                "script": {"provider": "ChatGPT", "model": "GPT-4o", "script_length": "~ 5 minutes"},
                "export": {"target": "Local MP4", "visibility": "Private"},
            },
            is_builtin=True,
        ),
    ]
