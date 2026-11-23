"""FastAPI application factory for the local desktop backend adapter."""
import os
from pathlib import Path
from typing import Optional
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.adapters.api.routes import health, projects
from src.adapters.storage.sqlite_project_repository import SQLiteProjectRepository
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

    # Configure repository dependency
    if repository is None:
        target_db = Path(db_path) if db_path else get_default_db_path()
        repository = SQLiteProjectRepository(db_path=target_db)

    app.dependency_overrides[projects.get_repository] = lambda: repository

    # Mount API routers
    app.include_router(health.router, prefix="/api")
    app.include_router(projects.router, prefix="/api")

    return app
