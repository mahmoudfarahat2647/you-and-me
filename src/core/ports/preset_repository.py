"""Port interface for workflow preset persistence."""
from abc import ABC, abstractmethod
from typing import List, Optional
from src.core.dto.preset_dto import WorkflowPresetResult


class PresetRepository(ABC):
    """Abstract port for persisting and querying workflow presets."""

    @abstractmethod
    def save(self, preset: WorkflowPresetResult) -> None:
        """Persist a plain workflow preset record."""
        pass

    @abstractmethod
    def get_by_id(self, preset_id: str) -> Optional[WorkflowPresetResult]:
        """Retrieve a workflow preset by its identifier."""
        pass

    @abstractmethod
    def list_all(self) -> List[WorkflowPresetResult]:
        """List all available workflow presets."""
        pass
