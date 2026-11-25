"""Use case for deleting a project's media item."""
from typing import Optional

from src.core.dto.media_dto import DeleteMediaInput, ProjectMediaItem
from src.core.entities.media import MediaValidationError
from src.core.ports.project_media_repository import ProjectMediaRepository


class DeleteProjectMediaUseCase:
    """Removes a clip or narration audio item from a project."""

    def __init__(self, media_repo: ProjectMediaRepository) -> None:
        self._media_repo = media_repo

    def execute(self, input_data: DeleteMediaInput) -> Optional[ProjectMediaItem]:
        if not input_data.project_id or not input_data.project_id.strip():
            raise MediaValidationError("Project ID cannot be empty.")
        if not input_data.item_id or not input_data.item_id.strip():
            raise MediaValidationError("Media item ID cannot be empty.")
        return self._media_repo.delete_item(input_data.project_id, input_data.item_id)
