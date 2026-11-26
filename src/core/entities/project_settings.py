"""Core domain entity for project-isolated settings and overrides."""
import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional

from src.core.entities.preset import (
    VALID_STAGE_IDS,
    VALID_STAGE_MODES,
    PresetValidationError,
    StageParamDict,
    validate_stage_modes,
)


class ProjectSettingsValidationError(Exception):
    """Raised when project settings domain validation fails."""
    pass


def default_stage_modes() -> Dict[str, str]:
    """Return default stage execution modes."""
    return {stage_id: "auto" for stage_id in VALID_STAGE_IDS}


def default_stage_params() -> StageParamDict:
    """Return default per-stage parameters."""
    return {
        "idea": {"sources": "YouTube + Web", "max_sources": 12},
        "script": {
            "provider": "ChatGPT",
            "model": "GPT-4o",
            "script_length": "~ 8 minutes",
            "tone": "Educational documentary narrative",
            "temperature": 0.7,
        },
        "voice": {"provider": "ElevenLabs", "format": "WAV · 48kHz"},
        "scenes": {"mode": "Full-motion", "clip_length": "5s / scene"},
        "edit": {"engine": "ffmpeg-7", "resolution": "1920x1080", "frame_rate": "30 fps"},
        "export": {"target": "Local MP4", "visibility": "Private", "codec": "H.264 / AAC"},
    }


def merge_stage_params(base: StageParamDict, overrides: StageParamDict) -> StageParamDict:
    """Deep-merge per-stage parameter dictionaries without mutating inputs."""
    merged: StageParamDict = {stage_id: dict(params) for stage_id, params in base.items()}
    for stage_id, params in overrides.items():
        if stage_id not in VALID_STAGE_IDS:
            raise ProjectSettingsValidationError(f"Invalid stage ID '{stage_id}' in stage_params.")
        existing = dict(merged.get(stage_id, {}))
        existing.update(params)
        merged[stage_id] = existing
    return merged


@dataclass
class ProjectSettings:
    """Project-specific settings copied from channel/preset defaults and independently overridable."""
    project_id: str
    updated_at: datetime
    channel_profile_id: Optional[str] = None
    preset_id: Optional[str] = None
    topic_focus: str = ""
    language: str = "Arabic"
    narrator: str = "arabic-narrator-v2"
    visual_style: str = "Cinematic Documentary"
    video_format: str = "16:9"
    budget_limit_usd: float = 10.0
    upload_destination: str = "Local MP4"
    stage_modes: Dict[str, str] = field(default_factory=default_stage_modes)
    stage_params: StageParamDict = field(default_factory=default_stage_params)

    def __post_init__(self) -> None:
        if not self.project_id or not self.project_id.strip():
            raise ProjectSettingsValidationError("Project ID cannot be empty.")
        if not self.language or not self.language.strip():
            raise ProjectSettingsValidationError("Language cannot be empty.")
        if math.isnan(self.budget_limit_usd) or math.isinf(self.budget_limit_usd) or self.budget_limit_usd < 0:
            raise ProjectSettingsValidationError("Budget limit must be a non-negative finite number.")

        self.project_id = self.project_id.strip()
        self.topic_focus = self.topic_focus.strip()
        self.language = self.language.strip()
        self.narrator = self.narrator.strip()
        self.visual_style = self.visual_style.strip()
        self.video_format = self.video_format.strip()
        self.upload_destination = self.upload_destination.strip()

        try:
            validated_modes = validate_stage_modes(self.stage_modes)
        except PresetValidationError as err:
            raise ProjectSettingsValidationError(str(err)) from err

        for stage_id in VALID_STAGE_IDS:
            mode = validated_modes.get(stage_id, "auto")
            if mode not in VALID_STAGE_MODES:
                raise ProjectSettingsValidationError(f"Invalid stage mode '{mode}'.")
            validated_modes[stage_id] = mode
        self.stage_modes = validated_modes

        self.stage_params = merge_stage_params(default_stage_params(), self.stage_params)
