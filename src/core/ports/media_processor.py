"""Port interface for probing and assembling video/audio media."""
from abc import ABC, abstractmethod
from typing import List, Optional
from src.core.dto.media_dto import MediaProbeInfo


class MediaProcessor(ABC):
    """Abstract port for media probing and MP4 export."""

    @abstractmethod
    def probe(self, file_path: str, display_name: Optional[str] = None) -> MediaProbeInfo:
        """Probe a media file for decodable streams and metadata.

        Raises MediaValidationError naming the offending input if missing,
        unreadable, or corrupt.
        """
        pass

    @abstractmethod
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
        """Combine ordered video clips with narration audio into output_path.

        Must write to a temporary file first, probe the temporary output to
        verify decodable video and audio streams, and atomically replace
        output_path only on success. Raises MediaExportError on failure.
        """
        pass
