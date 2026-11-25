"""Core domain entities."""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


class ProjectValidationError(Exception):
    """Raised when project domain validation fails."""
    pass


@dataclass
class Project:
    """Project domain entity."""
    id: str
    name: str
    description: str
    created_at: datetime
    updated_at: datetime
    channel_profile_id: Optional[str] = None
    preset_id: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.id or not self.id.strip():
            raise ProjectValidationError("Project ID cannot be empty.")
        if not self.name or not self.name.strip():
            raise ProjectValidationError("Project name cannot be empty.")
        self.name = self.name.strip()
