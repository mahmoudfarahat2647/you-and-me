"""FastAPI application factory for the local desktop backend adapter."""
import os
from pathlib import Path
from typing import Optional, Union
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.adapters.api.routes import health, media, projects
from src.adapters.media.ffmpeg_media_adapter import FFmpegMediaAdapter
from src.adapters.storage.sqlite_project_media_repository import SQLiteProjectMediaRepository
from src.adapters.storage.sqlite_project_repository import SQLiteProjectRepository
from src.core.ports.media_processor import MediaProcessor
from src.core.ports.project_media_repository import ProjectMediaRepository
from src.core.ports.project_repository import ProjectRepository


def get_default_db_path() -> Path:
    """Return standard storage location for AI Video Studio SQLite database."""
    app_data = os.environ.get("APPDATA")
    if app_data:
        base_dir = Path(app_data) / "AI Video Studio"
    else:
        base_dir = Path.home() / ".ai_video_studio"
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir / "studio.db"


def create_app(
    repository: Optional[ProjectRepository] = None,
    db_path: Optional[str] = None,
    media_repository: Optional[ProjectMediaRepository] = None,
    media_processor: Optional[MediaProcessor] = None,
    media_root: Optional[Union[str, Path]] = None,
) -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="AI Video Studio Backend",
        description="Local backend adapter for AI Video Studio desktop application",
        version="0.1.0",
    )

    # Allow CORS from Tauri desktop app and dev server
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    if db_path:
        target_db = Path(db_path)
    elif repository is not None and hasattr(repository, "db_path"):
        target_db = Path(getattr(repository, "db_path"))
    else:
        target_db = get_default_db_path()

    # Configure repository dependency
    if repository is None:
        repository = SQLiteProjectRepository(db_path=target_db)

    if media_repository is None:
        media_repository = SQLiteProjectMediaRepository(db_path=target_db)

    if media_processor is None:
        media_processor = FFmpegMediaAdapter()

    resolved_media_root = Path(media_root) if media_root else (target_db.parent / "media")
    resolved_media_root.mkdir(parents=True, exist_ok=True)

    app.dependency_overrides[projects.get_repository] = lambda: repository
    app.dependency_overrides[media.get_project_repository] = lambda: repository
    app.dependency_overrides[media.get_media_repository] = lambda: media_repository
    app.dependency_overrides[media.get_media_processor] = lambda: media_processor
    app.dependency_overrides[media.get_media_root] = lambda: resolved_media_root

    # Mount API routers
    app.include_router(health.router, prefix="/api")
    app.include_router(projects.router, prefix="/api")
    app.include_router(media.router, prefix="/api")

    return app
