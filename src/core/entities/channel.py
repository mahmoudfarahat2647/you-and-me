"""Core domain entity for channel profiles."""
import math
from dataclasses import dataclass
from datetime import datetime


class ChannelValidationError(Exception):
    """Raised when channel profile domain validation fails."""
    pass


@dataclass
class ChannelProfile:
    """Channel profile domain entity holding channel-level production defaults."""
    id: str
    name: str
    topic_focus: str
    language: str
    default_narrator: str
    visual_style: str
    video_format: str
    budget_limit_usd: float
    upload_destination: str
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        if not self.id or not self.id.strip():
            raise ChannelValidationError("Channel ID cannot be empty.")
        if not self.name or not self.name.strip():
            raise ChannelValidationError("Channel name cannot be empty.")
        if not self.language or not self.language.strip():
            raise ChannelValidationError("Channel language cannot be empty.")
        if math.isnan(self.budget_limit_usd) or math.isinf(self.budget_limit_usd) or self.budget_limit_usd < 0:
            raise ChannelValidationError("Budget limit must be a non-negative finite number.")

        self.id = self.id.strip()
        self.name = self.name.strip()
        self.topic_focus = self.topic_focus.strip()
        self.language = self.language.strip()
        self.default_narrator = self.default_narrator.strip()
        self.visual_style = self.visual_style.strip()
        self.video_format = self.video_format.strip()
        self.upload_destination = self.upload_destination.strip()
