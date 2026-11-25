"""FFmpeg and ffprobe adapter implementing the MediaProcessor port."""
import json
import os
import subprocess
import uuid
from fractions import Fraction
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.core.dto.media_dto import MediaProbeInfo
from src.core.entities.media import MediaExportError, MediaValidationError
from src.core.ports.media_processor import MediaProcessor


def _format_input_label(file_path: str, display_name: Optional[str]) -> str:
    if display_name and display_name.strip() and display_name.strip() != file_path:
        return f"'{display_name.strip()}' ({file_path})"
    return f"'{file_path}'"


def _parse_fps(stream: Dict[str, Any]) -> Optional[float]:
    for key in ("avg_frame_rate", "r_frame_rate"):
        raw = stream.get(key)
        if not raw or raw in ("0/0", "0"):
            continue
        try:
            value = float(Fraction(str(raw)))
            if value > 0:
                return round(value, 3)
        except (ValueError, ZeroDivisionError):
            continue
    return None


def _parse_duration(fmt: Dict[str, Any], streams: List[Dict[str, Any]]) -> float:
    candidates: List[Optional[str]] = [fmt.get("duration")]
    for stream in streams:
        candidates.append(stream.get("duration"))
    for raw in candidates:
        if raw is None:
            continue
        try:
            val = float(raw)
            if val > 0:
                return round(val, 4)
        except (TypeError, ValueError):
            continue
    return 0.0


class FFmpegMediaAdapter(MediaProcessor):
    """MediaProcessor backed by local ffmpeg and ffprobe executables."""

    def __init__(self, ffmpeg_bin: str = "ffmpeg", ffprobe_bin: str = "ffprobe") -> None:
        self._ffmpeg_bin = ffmpeg_bin
        self._ffprobe_bin = ffprobe_bin

    def probe(self, file_path: str, display_name: Optional[str] = None) -> MediaProbeInfo:
        label = _format_input_label(file_path, display_name)
        path = Path(file_path)
        if not path.exists() or not path.is_file():
            raise MediaValidationError(f"Media file {label} was not found or is missing.")
        file_size = path.stat().st_size
        if file_size <= 0:
            raise MediaValidationError(f"Media file {label} is empty or unreadable.")

        cmd = [
            self._ffprobe_bin,
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(path),
        ]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
        except OSError as err:
            raise MediaValidationError(
                f"Failed to run ffprobe for {label}: {err}"
            ) from err

        if proc.returncode != 0:
            detail = proc.stderr.strip() or proc.stdout.strip() or f"exit code {proc.returncode}"
            raise MediaValidationError(
                f"Media file {label} is unreadable or corrupt: {detail}"
            )

        try:
            payload = json.loads(proc.stdout or "{}")
        except json.JSONDecodeError as err:
            raise MediaValidationError(
                f"Media file {label} returned invalid ffprobe metadata: {err}"
            ) from err

        streams = payload.get("streams") or []
        fmt = payload.get("format") or {}
        if not streams:
            raise MediaValidationError(f"Media file {label} contains no decodable streams.")

        video_stream: Optional[Dict[str, Any]] = None
        audio_stream: Optional[Dict[str, Any]] = None
        for stream in streams:
            codec_type = stream.get("codec_type")
            disposition = stream.get("disposition") or {}
            if codec_type == "video" and disposition.get("attached_pic", 0) != 1 and video_stream is None:
                video_stream = stream
            elif codec_type == "audio" and audio_stream is None:
                audio_stream = stream

        duration = _parse_duration(fmt, streams)
        width = int(video_stream["width"]) if video_stream and video_stream.get("width") else None
        height = int(video_stream["height"]) if video_stream and video_stream.get("height") else None
        fps = _parse_fps(video_stream) if video_stream else None

        return MediaProbeInfo(
            path=str(path),
            has_video=video_stream is not None,
            has_audio=audio_stream is not None,
            duration_seconds=duration,
            width=width,
            height=height,
            fps=fps,
            video_codec=video_stream.get("codec_name") if video_stream else None,
            audio_codec=audio_stream.get("codec_name") if audio_stream else None,
            format_name=fmt.get("format_name"),
            file_size_bytes=file_size,
        )

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
        if not clip_paths:
            raise MediaExportError("Cannot export MP4: at least one video clip is required.")

        # Validate every clip and narration input upfront before creating temp files.
        for idx, clip_path in enumerate(clip_paths):
            label = clip_labels[idx] if clip_labels and idx < len(clip_labels) else None
            try:
                clip_probe = self.probe(clip_path, display_name=label)
            except MediaValidationError as err:
                raise MediaExportError(str(err)) from err
            if not clip_probe.has_video or (clip_probe.width or 0) <= 0 or (clip_probe.height or 0) <= 0:
                formatted = _format_input_label(clip_path, label)
                raise MediaExportError(
                    f"Clip {formatted} does not contain a valid decodable video stream."
                )

        try:
            audio_probe = self.probe(audio_path, display_name=audio_label)
        except MediaValidationError as err:
            raise MediaExportError(str(err)) from err
        if not audio_probe.has_audio:
            formatted = _format_input_label(audio_path, audio_label)
            raise MediaExportError(
                f"Narration audio {formatted} does not contain a valid decodable audio stream."
            )

        out_path = Path(output_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = out_path.parent / f".{out_path.stem}.{uuid.uuid4().hex}.tmp.mp4"

        n = len(clip_paths)
        filter_parts: List[str] = []
        concat_inputs: List[str] = []
        for idx in range(n):
            filter_parts.append(
                f"[{idx}:v]scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,"
                f"pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2:black,"
                f"setsar=1,fps={target_fps},format=yuv420p[v{idx}]"
            )
            concat_inputs.append(f"[v{idx}]")

        filter_parts.append(f"{''.join(concat_inputs)}concat=n={n}:v=1:a=0[vout]")
        filter_complex = ";".join(filter_parts)

        cmd: List[str] = [self._ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error"]
        for clip_path in clip_paths:
            cmd.extend(["-i", clip_path])
        cmd.extend(["-i", audio_path])
        cmd.extend([
            "-filter_complex",
            filter_complex,
            "-map",
            "[vout]",
            "-map",
            f"{n}:a:0",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-preset",
            "ultrafast",
            "-crf",
            "23",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-ar",
            "44100",
            "-ac",
            "2",
            "-movflags",
            "+faststart",
            str(tmp_path),
        ])

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
            if proc.returncode != 0:
                detail = proc.stderr.strip() or proc.stdout.strip() or f"exit code {proc.returncode}"
                raise MediaExportError(f"FFmpeg export failed: {detail}")

            try:
                verified = self.probe(str(tmp_path), display_name=out_path.name)
            except MediaValidationError as err:
                raise MediaExportError(f"Exported MP4 failed verification: {err}") from err

            if not verified.has_video or not verified.has_audio or verified.duration_seconds <= 0:
                raise MediaExportError(
                    f"Exported MP4 '{out_path.name}' is missing required decodable video or audio streams."
                )

            os.replace(tmp_path, out_path)
            return MediaProbeInfo(
                path=str(out_path),
                has_video=verified.has_video,
                has_audio=verified.has_audio,
                duration_seconds=verified.duration_seconds,
                width=verified.width,
                height=verified.height,
                fps=verified.fps,
                video_codec=verified.video_codec,
                audio_codec=verified.audio_codec,
                format_name=verified.format_name,
                file_size_bytes=out_path.stat().st_size,
            )
        except OSError as err:
            raise MediaExportError(f"Failed during MP4 export: {err}") from err
        finally:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass
