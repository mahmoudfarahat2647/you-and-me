"""Core domain entity for project-isolated assets."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional, Tuple

from src.core.entities.preset import StageParamScalar

VALID_ASSET_TYPES: Tuple[str, ...] = ("script", "scene", "audio", "export")


class AssetValidationError(Exception):
    """Raised when project asset domain validation fails."""
    pass


@dataclass
class ProjectAsset:
    """Domain entity representing an asset strictly owned by one project."""
    id: str
    project_id: str
    asset_type: str
    name: str
    content: str
    created_at: datetime
    updated_at: datetime
    file_path: Optional[str] = None
    metadata: Dict[str, StageParamScalar] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id or not self.id.strip():
            raise AssetValidationError("Asset ID cannot be empty.")
        if not self.project_id or not self.project_id.strip():
            raise AssetValidationError("Project ID cannot be empty.")
        if self.asset_type not in VALID_ASSET_TYPES:
            raise AssetValidationError(
                f"Invalid asset type '{self.asset_type}'. Must be one of: {', '.join(VALID_ASSET_TYPES)}."
            )
        if not self.name or not self.name.strip():
            raise AssetValidationError("Asset name cannot be empty.")

        self.id = self.id.strip()
        self.project_id = self.project_id.strip()
        self.name = self.name.strip()
        self.file_path = self.file_path.strip() if self.file_path else None
        self.metadata = dict(self.metadata)
