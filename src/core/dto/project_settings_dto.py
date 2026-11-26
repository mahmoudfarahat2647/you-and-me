"""Plain input and result records for project-isolated settings."""
from dataclasses import dataclass, field
from typing import Dict, Optional
from src.core.entities.preset import StageParamDict


@dataclass(frozen=True)
class GetProjectSettingsInput:
    """Plain input record for retrieving project settings."""
    project_id: str


@dataclass(frozen=True)
class UpdateProjectSettingsInput:
    """Plain input record for updating project-specific settings overrides."""
    project_id: str
    topic_focus: Optional[str] = None
    language: Optional[str] = None
    narrator: Optional[str] = None
    visual_style: Optional[str] = None
    video_format: Optional[str] = None
    budget_limit_usd: Optional[float] = None
    upload_destination: Optional[str] = None
    stage_modes: Optional[Dict[str, str]] = None
    stage_params: Optional[StageParamDict] = None


@dataclass(frozen=True)
class ProjectSettingsResult:
    """Plain result record representing a project's isolated settings."""
    project_id: str
    updated_at: str
    channel_profile_id: Optional[str] = None
    preset_id: Optional[str] = None
    topic_focus: str = ""
    language: str = "Arabic"
    narrator: str = "arabic-narrator-v2"
    visual_style: str = "Cinematic Documentary"
    video_format: str = "16:9"
    budget_limit_usd: float = 10.0
    upload_destination: str = "Local MP4"
    stage_modes: Dict[str, str] = field(default_factory=dict)
    stage_params: StageParamDict = field(default_factory=dict)
