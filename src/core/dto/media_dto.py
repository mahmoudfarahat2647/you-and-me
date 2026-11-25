"""Plain frozen DTO records for media import, ordering, and MP4 export."""
from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class MediaProbeInfo:
    """Plain metadata record produced by probing a media file."""
    path: str
    has_video: bool
    has_audio: bool
    duration_seconds: float
    width: Optional[int] = None
    height: Optional[int] = None
    fps: Optional[float] = None
    video_codec: Optional[str] = None
    audio_codec: Optional[str] = None
    format_name: Optional[str] = None
    file_size_bytes: int = 0


@dataclass(frozen=True)
class MediaClipInput:
    """Plain input record for registering/importing a moving video clip."""
    project_id: str
    source_path: str
    original_filename: Optional[str] = None


@dataclass(frozen=True)
class NarrationInput:
    """Plain input record for registering/importing narration audio."""
    project_id: str
    source_path: str
    original_filename: Optional[str] = None


@dataclass(frozen=True)
class ProjectMediaItem:
    """Plain persisted media item belonging to a project."""
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


@dataclass(frozen=True)
class ReorderClipsInput:
    """Plain input record for reordering project video clips."""
    project_id: str
    clip_ids: List[str]


@dataclass(frozen=True)
class DeleteMediaInput:
    """Plain input record for deleting a project media item."""
    project_id: str
    item_id: str


@dataclass(frozen=True)
class GetProjectMediaInput:
    """Plain input record for retrieving a project's media and export state."""
    project_id: str


@dataclass(frozen=True)
class ExportMp4Input:
    """Plain input record for exporting a project's ordered clips and narration to MP4."""
    project_id: str
    output_path: str
    target_width: int = 1280
    target_height: int = 720
    target_fps: int = 30


@dataclass(frozen=True)
class ExportMp4Result:
    """Plain result record describing a verified exported MP4 artifact."""
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


@dataclass(frozen=True)
class ProjectMediaBundle:
    """Plain aggregate view of a project's clips, narration audio, and latest export."""
    project_id: str
    clips: List[ProjectMediaItem]
    audio: Optional[ProjectMediaItem]
    latest_export: Optional[ExportMp4Result]
