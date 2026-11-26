"""Plain input and result records for channel profiles."""
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class CreateChannelInput:
    """Plain input record for creating a channel profile."""
    name: str
    topic_focus: str = ""
    language: str = "Arabic"
    default_narrator: str = "arabic-narrator-v2"
    visual_style: str = "Cinematic Documentary"
    video_format: str = "16:9"
    budget_limit_usd: float = 10.0
    upload_destination: str = "YouTube"


@dataclass(frozen=True)
class UpdateChannelInput:
    """Plain input record for updating an existing channel profile."""
    id: str
    name: Optional[str] = None
    topic_focus: Optional[str] = None
    language: Optional[str] = None
    default_narrator: Optional[str] = None
    visual_style: Optional[str] = None
    video_format: Optional[str] = None
    budget_limit_usd: Optional[float] = None
    upload_destination: Optional[str] = None


@dataclass(frozen=True)
class ChannelProfileResult:
    """Plain result record representing a channel profile across boundaries."""
    id: str
    name: str
    topic_focus: str
    language: str
    default_narrator: str
    visual_style: str
    video_format: str
    budget_limit_usd: float
    upload_destination: str
    created_at: str
    updated_at: str
