"""Plain input and result records for project-isolated assets."""
from dataclasses import dataclass, field
from typing import Dict, Optional
from src.core.entities.preset import StageParamScalar


@dataclass(frozen=True)
class CreateProjectAssetInput:
    """Plain input record for creating a project-scoped asset."""
    project_id: str
    asset_type: str
    name: str
    content: str = ""
    file_path: Optional[str] = None
    metadata: Optional[Dict[str, StageParamScalar]] = None


@dataclass(frozen=True)
class ListProjectAssetsInput:
    """Plain input record for listing assets owned by a project."""
    project_id: str
    asset_type: Optional[str] = None


@dataclass(frozen=True)
class DeleteProjectAssetInput:
    """Plain input record for deleting a project-scoped asset."""
    project_id: str
    asset_id: str


@dataclass(frozen=True)
class ProjectAssetResult:
    """Plain result record representing a project asset across boundaries."""
    id: str
    project_id: str
    asset_type: str
    name: str
    content: str
    created_at: str
    updated_at: str
    file_path: Optional[str] = None
    metadata: Dict[str, StageParamScalar] = field(default_factory=dict)
