"""Port interface for persisting project media items and export artifacts."""
from abc import ABC, abstractmethod
from typing import List, Optional
from src.core.dto.media_dto import ExportMp4Result, ProjectMediaItem


class ProjectMediaRepository(ABC):
    """Abstract port for project clips, narration audio, and export metadata."""

    @abstractmethod
    def add_clip(self, item: ProjectMediaItem) -> ProjectMediaItem:
        """Persist a new video clip for a project."""
        pass

    @abstractmethod
    def set_audio(self, item: ProjectMediaItem) -> ProjectMediaItem:
        """Persist or replace the narration audio for a project."""
        pass

    @abstractmethod
    def list_clips(self, project_id: str) -> List[ProjectMediaItem]:
        """List ordered video clips for a project."""
        pass

    @abstractmethod
    def get_audio(self, project_id: str) -> Optional[ProjectMediaItem]:
        """Retrieve the current narration audio for a project."""
        pass

    @abstractmethod
    def get_item(self, project_id: str, item_id: str) -> Optional[ProjectMediaItem]:
        """Retrieve a specific media item belonging to a project."""
        pass

    @abstractmethod
    def reorder_clips(self, project_id: str, clip_ids: List[str]) -> List[ProjectMediaItem]:
        """Persist a new order for a project's video clips."""
        pass

    @abstractmethod
    def delete_item(self, project_id: str, item_id: str) -> Optional[ProjectMediaItem]:
        """Delete a media item from a project and return the removed record if found."""
        pass

    @abstractmethod
    def save_export(self, export_result: ExportMp4Result) -> None:
        """Persist metadata for a verified exported MP4 artifact."""
        pass

    @abstractmethod
    def get_latest_export(self, project_id: str) -> Optional[ExportMp4Result]:
        """Retrieve the latest valid exported MP4 record for a project."""
        pass
