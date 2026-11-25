"""Use case for retrieving a project's imported clips, narration audio, and latest export."""
from src.core.dto.media_dto import GetProjectMediaInput, ProjectMediaBundle
from src.core.entities.media import MediaValidationError
from src.core.ports.project_media_repository import ProjectMediaRepository


class GetProjectMediaUseCase:
    """Loads persisted clips, narration audio, and latest export metadata for a project."""

    def __init__(self, media_repo: ProjectMediaRepository) -> None:
        self._media_repo = media_repo

    def execute(self, input_data: GetProjectMediaInput) -> ProjectMediaBundle:
        if not input_data.project_id or not input_data.project_id.strip():
            raise MediaValidationError("Project ID cannot be empty.")
        return ProjectMediaBundle(
            project_id=input_data.project_id,
            clips=self._media_repo.list_clips(input_data.project_id),
            audio=self._media_repo.get_audio(input_data.project_id),
            latest_export=self._media_repo.get_latest_export(input_data.project_id),
        )
