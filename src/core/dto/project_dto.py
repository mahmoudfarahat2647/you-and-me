"""Plain input and result records at the application boundary."""
from dataclasses import dataclass
from typing import Optional, List


@dataclass(frozen=True)
class CreateProjectInput:
    """Plain input record for creating a project."""
    name: str
    description: str = ""
    channel_profile_id: Optional[str] = None


@dataclass(frozen=True)
class ProjectResult:
    """Plain result record representing a project across the application boundary."""
    id: str
    name: str
    description: str
    created_at: str
    updated_at: str
    channel_profile_id: Optional[str] = None


@dataclass(frozen=True)
class GetProjectInput:
    """Plain input record for retrieving a project by ID."""
    id: str


@dataclass(frozen=True)
class ListProjectsResult:
    """Plain result record containing a collection of projects."""
    projects: List[ProjectResult]
