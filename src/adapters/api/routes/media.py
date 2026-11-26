"""API routes for project media import, clip ordering, MP4 export, and video streaming."""
import re
import shutil
import uuid
from pathlib import Path
from typing import List, Optional, Tuple
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from starlette.datastructures import UploadFile as StarletteUploadFile

from src.core.dto.media_dto import (
    DeleteMediaInput,
    ExportMp4Input,
    ExportMp4Result,
    GetProjectMediaInput,
    MediaClipInput,
    NarrationInput,
    ProjectMediaBundle,
    ProjectMediaItem,
    ReorderClipsInput,
)
from src.core.entities.media import MediaExportError, MediaValidationError
from src.core.ports.media_processor import MediaProcessor
from src.core.ports.project_media_repository import ProjectMediaRepository
from src.core.ports.project_repository import ProjectRepository
from src.core.use_cases.delete_project_media import DeleteProjectMediaUseCase
from src.core.use_cases.export_project_mp4 import ExportProjectMp4UseCase
from src.core.use_cases.get_project_media import GetProjectMediaUseCase
from src.core.use_cases.import_project_media import ImportProjectMediaUseCase
from src.core.use_cases.reorder_project_clips import ReorderProjectClipsUseCase

router = APIRouter(prefix="/projects/{project_id}", tags=["media"])


class ProjectMediaItemResponse(BaseModel):
    id: str
    project_id: str
    kind: str
    file_path: str
    original_filename: str
    position: int
    duration_seconds: float
    has_video: bool
    has_audio: bool
    created_at: str
    width: Optional[int] = None
    height: Optional[int] = None
    fps: Optional[float] = None
    video_codec: Optional[str] = None
    audio_codec: Optional[str] = None

    @classmethod
    def from_dto(cls, item: ProjectMediaItem) -> "ProjectMediaItemResponse":
        return cls(
            id=item.id,
            project_id=item.project_id,
            kind=item.kind,
            file_path=item.file_path,
            original_filename=item.original_filename,
            position=item.position,
            duration_seconds=item.duration_seconds,
            has_video=item.has_video,
            has_audio=item.has_audio,
            created_at=item.created_at,
            width=item.width,
            height=item.height,
            fps=item.fps,
            video_codec=item.video_codec,
            audio_codec=item.audio_codec,
        )


class ExportMp4Response(BaseModel):
    id: str
    project_id: str
    output_path: str
    duration_seconds: float
    width: int
    height: int
    fps: float
    has_video: bool
    has_audio: bool
    file_size_bytes: int
    clip_ids: List[str]
    created_at: str
    video_codec: Optional[str] = None
    audio_codec: Optional[str] = None
    audio_id: Optional[str] = None

    @classmethod
    def from_dto(cls, result: ExportMp4Result) -> "ExportMp4Response":
        return cls(
            id=result.id,
            project_id=result.project_id,
            output_path=result.output_path,
            duration_seconds=result.duration_seconds,
            width=result.width,
            height=result.height,
            fps=result.fps,
            has_video=result.has_video,
            has_audio=result.has_audio,
            file_size_bytes=result.file_size_bytes,
            clip_ids=list(result.clip_ids),
            created_at=result.created_at,
            video_codec=result.video_codec,
            audio_codec=result.audio_codec,
            audio_id=result.audio_id,
        )


class ProjectMediaBundleResponse(BaseModel):
    project_id: str
    clips: List[ProjectMediaItemResponse]
    audio: Optional[ProjectMediaItemResponse] = None
    latest_export: Optional[ExportMp4Response] = None

    @classmethod
    def from_dto(cls, bundle: ProjectMediaBundle) -> "ProjectMediaBundleResponse":
        return cls(
            project_id=bundle.project_id,
            clips=[ProjectMediaItemResponse.from_dto(c) for c in bundle.clips],
            audio=ProjectMediaItemResponse.from_dto(bundle.audio) if bundle.audio else None,
            latest_export=ExportMp4Response.from_dto(bundle.latest_export)
            if bundle.latest_export
            else None,
        )


class ReorderClipsRequest(BaseModel):
    clip_ids: List[str] = Field(..., description="Ordered list of clip IDs")


class ReorderClipsResponse(BaseModel):
    project_id: str
    clips: List[ProjectMediaItemResponse]


class DeleteMediaResponse(BaseModel):
    deleted: bool
    item_id: str


class ExportMp4Request(BaseModel):
    target_width: int = Field(1280, gt=0)
    target_height: int = Field(720, gt=0)
    target_fps: int = Field(30, gt=0)


def get_project_repository() -> ProjectRepository:
    raise NotImplementedError("ProjectRepository dependency must be configured.")


def get_media_repository() -> ProjectMediaRepository:
    raise NotImplementedError("ProjectMediaRepository dependency must be configured.")


def get_media_processor() -> MediaProcessor:
    raise NotImplementedError("MediaProcessor dependency must be configured.")


def get_media_root() -> Path:
    raise NotImplementedError("Media root directory dependency must be configured.")


def _sanitize_filename(name: str, fallback: str) -> str:
    base = Path(name).name.strip() if name else ""
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", base).strip("._")
    if not cleaned:
        return fallback
    return cleaned


def _require_project(project_id: str, project_repo: ProjectRepository) -> None:
    if project_repo.get_by_id(project_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID '{project_id}' not found.",
        )


async def _resolve_media_source(
    request: Request,
    target_dir: Path,
    default_filename: str,
) -> Tuple[str, Optional[str], Optional[Path]]:
    """Parse either multipart file upload or local source_path registration.

    Returns (source_path, original_filename, uploaded_file_to_cleanup_on_error).
    """
    content_type = (request.headers.get("content-type") or "").lower()

    if "multipart/form-data" in content_type:
        form = await request.form()
        uploaded = form.get("file")
        source_path_val = form.get("source_path")
        original_name_val = form.get("original_filename")

        if uploaded is not None and isinstance(uploaded, StarletteUploadFile):
            orig_name = uploaded.filename or default_filename
            safe_name = _sanitize_filename(orig_name, default_filename)
            target_dir.mkdir(parents=True, exist_ok=True)
            dest = target_dir / f"{uuid.uuid4().hex}_{safe_name}"
            try:
                with dest.open("wb") as out_fh:
                    shutil.copyfileobj(uploaded.file, out_fh)
            finally:
                await uploaded.close()
            return str(dest), orig_name, dest

        if isinstance(source_path_val, str) and source_path_val.strip():
            orig_name = (
                original_name_val.strip()
                if isinstance(original_name_val, str) and original_name_val.strip()
                else None
            )
            return source_path_val.strip(), orig_name, None

        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Expected a 'file' upload or 'source_path' field in multipart form.",
        )

    try:
        body = await request.json()
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Invalid request body: expected JSON with 'source_path' or multipart file upload ({err}).",
        )

    if not isinstance(body, dict) or not isinstance(body.get("source_path"), str) or not body["source_path"].strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Field 'source_path' is required.",
        )

    orig = body.get("original_filename")
    orig_name = orig.strip() if isinstance(orig, str) and orig.strip() else None
    return body["source_path"].strip(), orig_name, None


def _cleanup_file(path: Optional[Path]) -> None:
    if path is not None and path.exists():
        try:
            path.unlink()
        except OSError:
            pass


@router.post("/media/clips", response_model=ProjectMediaItemResponse, status_code=status.HTTP_201_CREATED)
async def import_project_clip(
    project_id: str,
    request: Request,
    project_repo: ProjectRepository = Depends(get_project_repository),
    media_repo: ProjectMediaRepository = Depends(get_media_repository),
    media_processor: MediaProcessor = Depends(get_media_processor),
    media_root: Path = Depends(get_media_root),
) -> ProjectMediaItemResponse:
    _require_project(project_id, project_repo)
    target_dir = media_root / project_id / "clips"
    source_path, original_filename, uploaded_path = await _resolve_media_source(
        request, target_dir, "clip.mp4"
    )
    try:
        use_case = ImportProjectMediaUseCase(media_repo, media_processor, project_repo)
        item = use_case.import_clip(
            MediaClipInput(
                project_id=project_id,
                source_path=source_path,
                original_filename=original_filename,
            )
        )
        return ProjectMediaItemResponse.from_dto(item)
    except MediaValidationError as err:
        _cleanup_file(uploaded_path)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(err),
        )


@router.post("/media/audio", response_model=ProjectMediaItemResponse, status_code=status.HTTP_201_CREATED)
async def import_project_audio(
    project_id: str,
    request: Request,
    project_repo: ProjectRepository = Depends(get_project_repository),
    media_repo: ProjectMediaRepository = Depends(get_media_repository),
    media_processor: MediaProcessor = Depends(get_media_processor),
    media_root: Path = Depends(get_media_root),
) -> ProjectMediaItemResponse:
    _require_project(project_id, project_repo)
    target_dir = media_root / project_id / "audio"
    source_path, original_filename, uploaded_path = await _resolve_media_source(
        request, target_dir, "narration.wav"
    )
    try:
        use_case = ImportProjectMediaUseCase(media_repo, media_processor, project_repo)
        item = use_case.import_audio(
            NarrationInput(
                project_id=project_id,
                source_path=source_path,
                original_filename=original_filename,
            )
        )
        return ProjectMediaItemResponse.from_dto(item)
    except MediaValidationError as err:
        _cleanup_file(uploaded_path)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(err),
        )


@router.get("/media", response_model=ProjectMediaBundleResponse)
def get_project_media(
    project_id: str,
    project_repo: ProjectRepository = Depends(get_project_repository),
    media_repo: ProjectMediaRepository = Depends(get_media_repository),
) -> ProjectMediaBundleResponse:
    _require_project(project_id, project_repo)
    bundle = GetProjectMediaUseCase(media_repo).execute(
        GetProjectMediaInput(project_id=project_id)
    )
    return ProjectMediaBundleResponse.from_dto(bundle)


@router.put("/media/clips/order", response_model=ReorderClipsResponse)
def reorder_project_clips(
    project_id: str,
    request: ReorderClipsRequest,
    project_repo: ProjectRepository = Depends(get_project_repository),
    media_repo: ProjectMediaRepository = Depends(get_media_repository),
) -> ReorderClipsResponse:
    _require_project(project_id, project_repo)
    try:
        clips = ReorderProjectClipsUseCase(media_repo).execute(
            ReorderClipsInput(project_id=project_id, clip_ids=request.clip_ids)
        )
        return ReorderClipsResponse(
            project_id=project_id,
            clips=[ProjectMediaItemResponse.from_dto(c) for c in clips],
        )
    except MediaValidationError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(err),
        )


@router.delete("/media/{item_id}", response_model=DeleteMediaResponse)
def delete_project_media_item(
    project_id: str,
    item_id: str,
    project_repo: ProjectRepository = Depends(get_project_repository),
    media_repo: ProjectMediaRepository = Depends(get_media_repository),
    media_root: Path = Depends(get_media_root),
) -> DeleteMediaResponse:
    _require_project(project_id, project_repo)
    removed = DeleteProjectMediaUseCase(media_repo).execute(
        DeleteMediaInput(project_id=project_id, item_id=item_id)
    )
    if removed is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Media item '{item_id}' not found in project '{project_id}'.",
        )

    # Remove uploaded copy only if it resides inside this project's managed media root.
    project_managed_dir = (media_root / project_id).resolve()
    try:
        removed_path = Path(removed.file_path).resolve()
        if removed_path.is_file() and project_managed_dir in removed_path.parents:
            removed_path.unlink()
    except OSError:
        pass

    return DeleteMediaResponse(deleted=True, item_id=item_id)


@router.post("/export", response_model=ExportMp4Response)
def export_project_mp4(
    project_id: str,
    request: Optional[ExportMp4Request] = None,
    project_repo: ProjectRepository = Depends(get_project_repository),
    media_repo: ProjectMediaRepository = Depends(get_media_repository),
    media_processor: MediaProcessor = Depends(get_media_processor),
    media_root: Path = Depends(get_media_root),
) -> ExportMp4Response:
    _require_project(project_id, project_repo)
    req = request or ExportMp4Request()
    output_path = media_root / project_id / "output" / "export.mp4"
    try:
        result = ExportProjectMp4UseCase(media_repo, media_processor, project_repo).execute(
            ExportMp4Input(
                project_id=project_id,
                output_path=str(output_path),
                target_width=req.target_width,
                target_height=req.target_height,
                target_fps=req.target_fps,
            )
        )
        return ExportMp4Response.from_dto(result)
    except (MediaExportError, MediaValidationError) as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(err),
        )


@router.get("/output/video")
def stream_project_output_video(
    project_id: str,
    project_repo: ProjectRepository = Depends(get_project_repository),
    media_repo: ProjectMediaRepository = Depends(get_media_repository),
) -> FileResponse:
    _require_project(project_id, project_repo)
    latest = media_repo.get_latest_export(project_id)
    if latest is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No exported MP4 output exists yet for project '{project_id}'.",
        )
    out_file = Path(latest.output_path)
    if not out_file.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exported MP4 file '{latest.output_path}' is missing on disk.",
        )
    return FileResponse(
        path=str(out_file),
        media_type="video/mp4",
        filename=out_file.name,
    )
