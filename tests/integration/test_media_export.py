"""Real FFmpeg/ffprobe, SQLite, and FastAPI integration tests for media import and MP4 export."""
import subprocess
from pathlib import Path
from typing import Tuple

import pytest
from httpx import ASGITransport, AsyncClient

from src.adapters.api.app import create_app
from src.adapters.media.ffmpeg_media_adapter import FFmpegMediaAdapter
from src.adapters.storage.sqlite_project_media_repository import SQLiteProjectMediaRepository
from src.adapters.storage.sqlite_project_repository import SQLiteProjectRepository
from src.core.dto.media_dto import ExportMp4Result, MediaProbeInfo, ProjectMediaItem
from src.core.entities.media import MediaExportError, MediaValidationError


def _generate_moving_clip(
    dest: Path,
    bg_color: str,
    width: int,
    height: int,
    fps: int,
    duration: float = 1.5,
) -> Path:
    """Create a real moving MP4 test clip (moving white square over colored background)."""
    vf = f"drawbox=x='t*{width // 3}':y='{height // 3}':w={width // 5}:h={height // 5}:color=white:t=fill"
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "lavfi",
        "-i",
        f"color=c={bg_color}:s={width}x{height}:r={fps}:d={duration}",
        "-vf",
        vf,
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-preset",
        "ultrafast",
        str(dest),
    ]
    subprocess.run(cmd, check=True)
    return dest


def _generate_tone_wav(dest: Path, frequency: int = 440, duration: float = 3.0) -> Path:
    """Create an audible WAV narration tone."""
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency={frequency}:sample_rate=44100:duration={duration}",
        "-c:a",
        "pcm_s16le",
        str(dest),
    ]
    subprocess.run(cmd, check=True)
    return dest


def _sample_rgb_at(video_path: Path, timestamp: float) -> Tuple[int, int, int]:
    """Decode a single raw RGB24 pixel from the top-left corner at timestamp."""
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        str(timestamp),
        "-i",
        str(video_path),
        "-frames:v",
        "1",
        "-vf",
        "scale=16:16",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "pipe:1",
    ]
    proc = subprocess.run(cmd, capture_output=True, check=True)
    data = proc.stdout
    assert len(data) >= 3
    # Top-left pixel (background color, away from moving white box in middle third)
    return data[0], data[1], data[2]


def test_ffmpeg_adapter_probes_and_reports_offending_inputs(tmp_path: Path) -> None:
    adapter = FFmpegMediaAdapter()
    red_clip = _generate_moving_clip(tmp_path / "red.mp4", "red", 640, 360, 24, duration=1.0)
    tone = _generate_tone_wav(tmp_path / "narration.wav", duration=1.5)

    clip_info = adapter.probe(str(red_clip), display_name="red.mp4")
    assert clip_info.has_video is True
    assert clip_info.width == 640
    assert clip_info.height == 360
    assert clip_info.duration_seconds == pytest.approx(1.0, abs=0.2)

    audio_info = adapter.probe(str(tone), display_name="narration.wav")
    assert audio_info.has_audio is True
    assert audio_info.duration_seconds == pytest.approx(1.5, abs=0.2)

    missing_path = tmp_path / "missing_clip.mp4"
    with pytest.raises(MediaValidationError, match="missing_clip\\.mp4"):
        adapter.probe(str(missing_path), display_name="missing_clip.mp4")

    corrupt_path = tmp_path / "broken_clip.mp4"
    corrupt_path.write_text("not a real video file", encoding="utf-8")
    with pytest.raises(MediaValidationError, match="broken_clip\\.mp4"):
        adapter.probe(str(corrupt_path), display_name="broken_clip.mp4")


def test_sqlite_media_repository_persists_across_reopen(tmp_path: Path) -> None:
    db_file = tmp_path / "media.db"
    repo1 = SQLiteProjectMediaRepository(db_file)
    c1 = ProjectMediaItem(
        id="clip-1",
        project_id="proj-1",
        kind="clip",
        file_path=str(tmp_path / "a.mp4"),
        original_filename="a.mp4",
        position=0,
        duration_seconds=1.5,
        has_video=True,
        has_audio=False,
        created_at="2026-01-01T00:00:00Z",
        width=640,
        height=360,
        fps=24.0,
        video_codec="h264",
    )
    c2 = ProjectMediaItem(
        id="clip-2",
        project_id="proj-1",
        kind="clip",
        file_path=str(tmp_path / "b.mp4"),
        original_filename="b.mp4",
        position=1,
        duration_seconds=1.5,
        has_video=True,
        has_audio=False,
        created_at="2026-01-01T00:00:01Z",
        width=1280,
        height=720,
        fps=30.0,
        video_codec="h264",
    )
    audio = ProjectMediaItem(
        id="audio-1",
        project_id="proj-1",
        kind="audio",
        file_path=str(tmp_path / "voice.wav"),
        original_filename="voice.wav",
        position=0,
        duration_seconds=3.0,
        has_video=False,
        has_audio=True,
        created_at="2026-01-01T00:00:02Z",
        audio_codec="pcm_s16le",
    )
    export = ExportMp4Result(
        id="exp-1",
        project_id="proj-1",
        output_path=str(tmp_path / "out.mp4"),
        duration_seconds=3.0,
        width=1280,
        height=720,
        fps=30.0,
        has_video=True,
        has_audio=True,
        file_size_bytes=2048,
        clip_ids=["clip-2", "clip-1"],
        created_at="2026-01-01T00:00:03Z",
        video_codec="h264",
        audio_codec="aac",
        audio_id="audio-1",
    )

    repo1.add_clip(c1)
    repo1.add_clip(c2)
    repo1.set_audio(audio)
    repo1.reorder_clips("proj-1", ["clip-2", "clip-1"])
    repo1.save_export(export)

    repo2 = SQLiteProjectMediaRepository(db_file)
    clips = repo2.list_clips("proj-1")
    assert [c.id for c in clips] == ["clip-2", "clip-1"]
    assert [c.position for c in clips] == [0, 1]
    assert repo2.get_audio("proj-1") == audio
    assert repo2.get_latest_export("proj-1") == export


@pytest.mark.asyncio
async def test_full_media_import_reorder_export_stream_and_failure_preservation(tmp_path: Path) -> None:
    db_file = tmp_path / "studio.db"
    app = create_app(
        repository=SQLiteProjectRepository(db_file),
        media_repository=SQLiteProjectMediaRepository(db_file),
        media_processor=FFmpegMediaAdapter(),
        media_root=tmp_path / "media",
    )

    red_clip = _generate_moving_clip(tmp_path / "red_clip.mp4", "red", 640, 360, 24, duration=1.5)
    blue_clip = _generate_moving_clip(tmp_path / "blue_clip.mp4", "blue", 1280, 720, 30, duration=1.5)
    narration = _generate_tone_wav(tmp_path / "narration.wav", frequency=440, duration=3.0)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        proj_res = await client.post("/api/projects", json={"name": "Moving Clips Export"})
        assert proj_res.status_code == 201
        project_id = proj_res.json()["id"]

        # 1. Import Clip A via multipart upload
        with red_clip.open("rb") as fh:
            up_res = await client.post(
                f"/api/projects/{project_id}/media/clips",
                files={"file": ("red_clip.mp4", fh, "video/mp4")},
            )
        assert up_res.status_code == 201
        clip_a = up_res.json()
        assert clip_a["original_filename"] == "red_clip.mp4"
        assert clip_a["position"] == 0

        # 2. Import Clip B via local path registration
        reg_res = await client.post(
            f"/api/projects/{project_id}/media/clips",
            json={"source_path": str(blue_clip), "original_filename": "blue_clip.mp4"},
        )
        assert reg_res.status_code == 201
        clip_b = reg_res.json()
        assert clip_b["position"] == 1

        # 3. Reject corrupt upload with explicit filename in error
        bad_res = await client.post(
            f"/api/projects/{project_id}/media/clips",
            files={"file": ("corrupt_upload.mp4", b"not-an-mp4", "video/mp4")},
        )
        assert bad_res.status_code == 422
        assert "corrupt_upload.mp4" in bad_res.json()["detail"]

        # 4. Import narration audio via multipart upload
        with narration.open("rb") as fh:
            aud_res = await client.post(
                f"/api/projects/{project_id}/media/audio",
                files={"file": ("narration.wav", fh, "audio/wav")},
            )
        assert aud_res.status_code == 201
        assert aud_res.json()["has_audio"] is True

        # 5. Reorder clips so blue_clip comes BEFORE red_clip
        order_res = await client.put(
            f"/api/projects/{project_id}/media/clips/order",
            json={"clip_ids": [clip_b["id"], clip_a["id"]]},
        )
        assert order_res.status_code == 200
        assert [c["id"] for c in order_res.json()["clips"]] == [clip_b["id"], clip_a["id"]]

        # 6. Export MP4
        exp_res = await client.post(
            f"/api/projects/{project_id}/export",
            json={"target_width": 640, "target_height": 360, "target_fps": 30},
        )
        assert exp_res.status_code == 200
        export_data = exp_res.json()
        assert export_data["has_video"] is True
        assert export_data["has_audio"] is True
        assert export_data["clip_ids"] == [clip_b["id"], clip_a["id"]]
        out_path = Path(export_data["output_path"])
        assert out_path.is_file()

        # Verify with ffprobe and pixel order check (blue first, red second)
        probed: MediaProbeInfo = FFmpegMediaAdapter().probe(str(out_path))
        assert probed.has_video is True
        assert probed.has_audio is True
        assert probed.video_codec == "h264"
        assert probed.audio_codec == "aac"
        assert probed.duration_seconds == pytest.approx(3.0, abs=0.4)

        r1, _g1, b1 = _sample_rgb_at(out_path, 0.5)
        r2, _g2, b2 = _sample_rgb_at(out_path, 2.0)
        assert b1 > r1 + 100, f"Expected blue frame at 0.5s, got RGB=({r1}, {_g1}, {b1})"
        assert r2 > b2 + 100, f"Expected red frame at 2.0s, got RGB=({r2}, {_g2}, {b2})"

        saved_bytes = out_path.read_bytes()

        # 7. Stream video with byte-range support
        stream_res = await client.get(
            f"/api/projects/{project_id}/output/video",
            headers={"Range": "bytes=0-511"},
        )
        assert stream_res.status_code in (200, 206)
        assert stream_res.headers["content-type"].startswith("video/mp4")
        if stream_res.status_code == 206:
            assert len(stream_res.content) == 512

        # 8. Break clip B on disk, re-export must fail naming blue_clip.mp4 and preserve prior MP4!
        blue_clip.unlink()
        fail_res = await client.post(f"/api/projects/{project_id}/export")
        assert fail_res.status_code == 422
        assert "blue_clip.mp4" in fail_res.json()["detail"]

        assert out_path.is_file()
        assert out_path.read_bytes() == saved_bytes

        media_state = await client.get(f"/api/projects/{project_id}/media")
        assert media_state.status_code == 200
        assert media_state.json()["latest_export"]["id"] == export_data["id"]
