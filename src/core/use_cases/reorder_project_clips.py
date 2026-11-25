"""Use case for reordering imported video clips in a project."""
from typing import List

from src.core.dto.media_dto import ProjectMediaItem, ReorderClipsInput
from src.core.entities.media import MediaValidationError
from src.core.ports.project_media_repository import ProjectMediaRepository


class ReorderProjectClipsUseCase:
    """Validates clip IDs and updates their playback order."""

    def __init__(self, media_repo: ProjectMediaRepository) -> None:
        self._media_repo = media_repo

    def execute(self, input_data: ReorderClipsInput) -> List[ProjectMediaItem]:
        if not input_data.project_id or not input_data.project_id.strip():
            raise MediaValidationError("Project ID cannot be empty.")

        existing = self._media_repo.list_clips(input_data.project_id)
        existing_ids = [item.id for item in existing]
        requested_ids = list(input_data.clip_ids)

        if len(requested_ids) != len(set(requested_ids)):
            raise MediaValidationError("Clip order contains duplicate clip IDs.")

        unknown = [cid for cid in requested_ids if cid not in existing_ids]
        if unknown:
            raise MediaValidationError(f"Unknown clip ID(s) in order request: {', '.join(unknown)}.")

        missing = [cid for cid in existing_ids if cid not in requested_ids]
        if missing:
            raise MediaValidationError(f"Missing clip ID(s) in order request: {', '.join(missing)}.")

        return self._media_repo.reorder_clips(input_data.project_id, requested_ids)
