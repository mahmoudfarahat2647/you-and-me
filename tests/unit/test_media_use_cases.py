"""Pure unit tests for media use cases without FFmpeg, SQLite, or FastAPI."""
import ast
from pathlib import Path
from typing import Dict, List, Optional

import pytest

from src.core.dto.media_dto import (
    DeleteMediaInput,
    ExportMp4Input,
    ExportMp4Result,
    GetProjectMediaInput,
    MediaClipInput,
    MediaProbeInfo,
    NarrationInput,
    ProjectMediaItem,
    ReorderClipsInput,
)
from src.core.entities.media import MediaExportError, MediaValidationError
from src.core.ports.media_processor import MediaProcessor
from src.core.ports.project_media_repository import ProjectMediaRepository
from src.core.use_cases.delete_project_media import DeleteProjectMediaUseCase
from src.core.use_cases.export_project_mp4 import ExportProjectMp4UseCase
from src.core.use_cases.get_project_media import GetProjectMediaUseCase
from src.core.use_cases.import_project_media import ImportProjectMediaUseCase
from src.core.use_cases.reorder_project_clips import ReorderProjectClipsUseCase


class InMemoryMediaRepository(ProjectMediaRepository):
    def __init__(self) -> None:
        self._clips: Dict[str, List[ProjectMediaItem]] = {}
        self._audio: Dict[str, ProjectMediaItem] = {}
        self._exports: Dict[str, ExportMp4Result] = {}

    def add_clip(self, item: ProjectMediaItem) -> ProjectMediaItem:
        items = self._clips.setdefault(item.project_id, [])
        items.append(item)
        return item

    def set_audio(self, item: ProjectMediaItem) -> ProjectMediaItem:
        self._audio[item.project_id] = item
        return item

    def list_clips(self, project_id: str) -> List[ProjectMediaItem]:
        return sorted(self._clips.get(project_id, []), key=lambda c: c.position)

    def get_audio(self, project_id: str) -> Optional[ProjectMediaItem]:
        return self._audio.get(project_id)

    def get_item(self, project_id: str, item_id: str) -> Optional[ProjectMediaItem]:
        for c in self._clips.get(project_id, []):
            if c.id == item_id:
                return c
        audio = self._audio.get(project_id)
        if audio and audio.id == item_id:
            return audio
        return None

    def reorder_clips(self, project_id: str, clip_ids: List[str]) -> List[ProjectMediaItem]:
        by_id = {c.id: c for c in self._clips.get(project_id, [])}
        reordered: List[ProjectMediaItem] = []
        for idx, cid in enumerate(clip_ids):
            c = by_id[cid]
            reordered.append(
                ProjectMediaItem(
                    id=c.id,
                    project_id=c.project_id,
                    kind=c.kind,
                    file_path=c.file_path,
                    original_filename=c.original_filename,
                    position=idx,
                    duration_seconds=c.duration_seconds,
                    has_video=c.has_video,
                    has_audio=c.has_audio,
                    created_at=c.created_at,
                    width=c.width,
                    height=c.height,
                    fps=c.fps,
                    video_codec=c.video_codec,
                    audio_codec=c.audio_codec,
                )
            )
        self._clips[project_id] = reordered
        return list(reordered)

    def delete_item(self, project_id: str, item_id: str) -> Optional[ProjectMediaItem]:
        clips = self._clips.get(project_id, [])
        for idx, c in enumerate(clips):
            if c.id == item_id:
                removed = clips.pop(idx)
                self._clips[project_id] = [
                    ProjectMediaItem(
                        id=rem.id,
                        project_id=rem.project_id,
                        kind=rem.kind,
                        file_path=rem.file_path,
                        original_filename=rem.original_filename,
                        position=pos,
                        duration_seconds=rem.duration_seconds,
                        has_video=rem.has_video,
                        has_audio=rem.has_audio,
                        created_at=rem.created_at,
                        width=rem.width,
                        height=rem.height,
                        fps=rem.fps,
                        video_codec=rem.video_codec,
                        audio_codec=rem.audio_codec,
                    )
                    for pos, rem in enumerate(clips)
                ]
                return removed
        audio = self._audio.get(project_id)
        if audio and audio.id == item_id:
            del self._audio[project_id]
            return audio
        return None

    def save_export(self, export_result: ExportMp4Result) -> None:
        self._exports[export_result.project_id] = export_result

    def get_latest_export(self, project_id: str) -> Optional[ExportMp4Result]:
        return self._exports.get(project_id)


class FakeMediaProcessor(MediaProcessor):
    def __init__(self) -> None:
        self.probes: Dict[str, MediaProbeInfo] = {}
        self.probe_errors: Dict[str, str] = {}
        self.export_calls: List[dict] = []
        self.export_error: Optional[str] = None
        self.export_probe: Optional[MediaProbeInfo] = None

    def probe(self, file_path: str, display_name: Optional[str] = None) -> MediaProbeInfo:
        if file_path in self.probe_errors:
            label = display_name or file_path
            raise MediaValidationError(f"{label} ({file_path}): {self.probe_errors[file_path]}")
        if file_path not in self.probes:
            label = display_name or file_path
            raise MediaValidationError(f"Media file '{label}' ({file_path}) was not found.")
        return self.probes[file_path]

    def export_mp4(
        self,
        clip_paths: List[str],
        audio_path: str,
        output_path: str,
        target_width: int = 1280,
        target_height: int = 720,
        target_fps: int = 30,
        clip_labels: Optional[List[str]] = None,
        audio_label: Optional[str] = None,
    ) -> MediaProbeInfo:
        self.export_calls.append(
            {
                "clip_paths": list(clip_paths),
                "audio_path": audio_path,
                "output_path": output_path,
                "target_width": target_width,
                "target_height": target_height,
                "target_fps": target_fps,
            }
        )
        if self.export_error:
            raise MediaExportError(self.export_error)
        if self.export_probe is not None:
            return self.export_probe
        return MediaProbeInfo(
            path=output_path,
            has_video=True,
            has_audio=True,
            duration_seconds=4.0,
            width=target_width,
            height=target_height,
            fps=float(target_fps),
            video_codec="h264",
            audio_codec="aac",
            file_size_bytes=123456,
        )


def test_core_layer_has_no_framework_or_ffmpeg_imports() -> None:
    forbidden = {"fastapi", "pydantic", "sqlite3", "subprocess", "ffmpeg"}
    core_dir = Path("src/core")
    for py_file in core_dir.rglob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    assert top not in forbidden, f"{py_file} imports {top}"
            elif isinstance(node, ast.ImportFrom) and node.module:
                top = node.module.split(".")[0]
                assert top not in forbidden, f"{py_file} imports from {top}"


def test_import_clips_narration_reorder_and_delete() -> None:
    repo = InMemoryMediaRepository()
    proc = FakeMediaProcessor()
    proc.probes["/clips/one.mp4"] = MediaProbeInfo(
        path="/clips/one.mp4",
        has_video=True,
        has_audio=False,
        duration_seconds=2.0,
        width=1280,
        height=720,
        fps=30.0,
        video_codec="h264",
    )
    proc.probes["/clips/two.mp4"] = MediaProbeInfo(
        path="/clips/two.mp4",
        has_video=True,
        has_audio=False,
        duration_seconds=3.0,
        width=1920,
        height=1080,
        fps=24.0,
        video_codec="h264",
    )
    proc.probes["/audio/voice.wav"] = MediaProbeInfo(
        path="/audio/voice.wav",
        has_video=False,
        has_audio=True,
        duration_seconds=5.0,
        audio_codec="pcm_s16le",
    )

    importer = ImportProjectMediaUseCase(repo, proc)
    clip1 = importer.import_clip(MediaClipInput(project_id="p1", source_path="/clips/one.mp4"))
    clip2 = importer.import_clip(MediaClipInput(project_id="p1", source_path="/clips/two.mp4"))
    audio = importer.import_audio(NarrationInput(project_id="p1", source_path="/audio/voice.wav"))

    assert clip1.position == 0
    assert clip2.position == 1
    assert audio.kind == "audio"

    reordered = ReorderProjectClipsUseCase(repo).execute(
        ReorderClipsInput(project_id="p1", clip_ids=[clip2.id, clip1.id])
    )
    assert [c.id for c in reordered] == [clip2.id, clip1.id]
    assert [c.position for c in reordered] == [0, 1]

    bundle = GetProjectMediaUseCase(repo).execute(GetProjectMediaInput(project_id="p1"))
    assert [c.id for c in bundle.clips] == [clip2.id, clip1.id]
    assert bundle.audio is not None and bundle.audio.id == audio.id

    removed = DeleteProjectMediaUseCase(repo).execute(
        DeleteMediaInput(project_id="p1", item_id=clip2.id)
    )
    assert removed is not None and removed.id == clip2.id
    remaining = repo.list_clips("p1")
    assert len(remaining) == 1
    assert remaining[0].id == clip1.id
    assert remaining[0].position == 0


def test_import_rejects_audio_only_as_clip_and_video_only_as_audio() -> None:
    repo = InMemoryMediaRepository()
    proc = FakeMediaProcessor()
    proc.probes["/only_audio.wav"] = MediaProbeInfo(
        path="/only_audio.wav", has_video=False, has_audio=True, duration_seconds=2.0
    )
    proc.probes["/only_video.mp4"] = MediaProbeInfo(
        path="/only_video.mp4",
        has_video=True,
        has_audio=False,
        duration_seconds=2.0,
        width=640,
        height=360,
    )

    importer = ImportProjectMediaUseCase(repo, proc)
    with pytest.raises(MediaValidationError, match="only_audio\\.wav"):
        importer.import_clip(MediaClipInput(project_id="p1", source_path="/only_audio.wav"))

    with pytest.raises(MediaValidationError, match="only_video\\.mp4"):
        importer.import_audio(NarrationInput(project_id="p1", source_path="/only_video.mp4"))


def test_reorder_rejects_invalid_ids() -> None:
    repo = InMemoryMediaRepository()
    proc = FakeMediaProcessor()
    proc.probes["/c1.mp4"] = MediaProbeInfo(
        path="/c1.mp4", has_video=True, has_audio=False, duration_seconds=1.5, width=640, height=360
    )
    clip = ImportProjectMediaUseCase(repo, proc).import_clip(
        MediaClipInput(project_id="p1", source_path="/c1.mp4")
    )

    uc = ReorderProjectClipsUseCase(repo)
    with pytest.raises(MediaValidationError, match="duplicate"):
        uc.execute(ReorderClipsInput(project_id="p1", clip_ids=[clip.id, clip.id]))
    with pytest.raises(MediaValidationError, match="Unknown"):
        uc.execute(ReorderClipsInput(project_id="p1", clip_ids=[clip.id, "bogus"]))
    with pytest.raises(MediaValidationError, match="Missing"):
        uc.execute(ReorderClipsInput(project_id="p1", clip_ids=[]))


def test_export_uses_ordered_clips_and_preserves_prior_output_on_failure() -> None:
    repo = InMemoryMediaRepository()
    proc = FakeMediaProcessor()
    proc.probes["/c1.mp4"] = MediaProbeInfo(
        path="/c1.mp4", has_video=True, has_audio=False, duration_seconds=2.0, width=640, height=360
    )
    proc.probes["/c2.mp4"] = MediaProbeInfo(
        path="/c2.mp4", has_video=True, has_audio=False, duration_seconds=2.0, width=1280, height=720
    )
    proc.probes["/v.wav"] = MediaProbeInfo(
        path="/v.wav", has_video=False, has_audio=True, duration_seconds=4.0
    )

    importer = ImportProjectMediaUseCase(repo, proc)
    c1 = importer.import_clip(MediaClipInput(project_id="p1", source_path="/c1.mp4"))
    c2 = importer.import_clip(MediaClipInput(project_id="p1", source_path="/c2.mp4"))
    importer.import_audio(NarrationInput(project_id="p1", source_path="/v.wav"))
    ReorderProjectClipsUseCase(repo).execute(ReorderClipsInput(project_id="p1", clip_ids=[c2.id, c1.id]))

    exporter = ExportProjectMp4UseCase(repo, proc)
    first_export = exporter.execute(ExportMp4Input(project_id="p1", output_path="/out/final.mp4"))
    assert first_export.clip_ids == [c2.id, c1.id]
    assert proc.export_calls[-1]["clip_paths"] == ["/c2.mp4", "/c1.mp4"]
    assert repo.get_latest_export("p1") == first_export

    # Simulate corrupt/missing input before second export: must name offending input & preserve prior export.
    proc.probe_errors["/c1.mp4"] = "corrupt moov atom"
    with pytest.raises(MediaExportError, match="c1\\.mp4"):
        exporter.execute(ExportMp4Input(project_id="p1", output_path="/out/final.mp4"))
    assert repo.get_latest_export("p1") == first_export

    # Simulate FFmpeg failure mid-export: must still preserve prior export.
    del proc.probe_errors["/c1.mp4"]
    proc.export_error = "ffmpeg crashed"
    with pytest.raises(MediaExportError, match="ffmpeg crashed"):
        exporter.execute(ExportMp4Input(project_id="p1", output_path="/out/final.mp4"))
    assert repo.get_latest_export("p1") == first_export
