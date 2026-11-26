"""FastAPI application factory for the local desktop backend adapter."""
import os
from pathlib import Path
from typing import Optional, Union
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.adapters.api.routes import (
    assets,
    channels,
    health,
    media,
    presets,
    project_settings,
    projects,
    providers,
    workflow,
)
from src.adapters.media.ffmpeg_media_adapter import FFmpegMediaAdapter
from src.adapters.providers.http_provider_gateway import HttpProviderGateway
from src.adapters.security.windows_dpapi_vault import WindowsDpapiVault
from src.adapters.storage.sqlite_budget_repository import SQLiteBudgetRepository
from src.adapters.storage.sqlite_channel_repository import SQLiteChannelRepository
from src.adapters.storage.sqlite_preset_repository import SQLitePresetRepository
from src.adapters.storage.sqlite_project_asset_repository import SQLiteProjectAssetRepository
from src.adapters.storage.sqlite_project_media_repository import SQLiteProjectMediaRepository
from src.adapters.storage.sqlite_project_repository import SQLiteProjectRepository
from src.adapters.storage.sqlite_project_settings_repository import SQLiteProjectSettingsRepository
from src.adapters.storage.sqlite_provider_repository import SQLiteProviderRepository
from src.adapters.storage.sqlite_workflow_repository import SQLiteWorkflowRepository
from src.adapters.workflow.local_stage_executor import LocalStageExecutor
from src.core.ports.asset_repository import ProjectAssetRepository
from src.core.ports.budget_repository import BudgetRepository
from src.core.ports.channel_repository import ChannelRepository
from src.core.ports.credential_vault import CredentialVaultPort
from src.core.ports.execution_preflight import (
    AllowAllExecutionPreflight,
    ExecutionPreflightPort,
)
from src.core.ports.media_processor import MediaProcessor
from src.core.ports.preset_repository import PresetRepository
from src.core.ports.project_media_repository import ProjectMediaRepository
from src.core.ports.project_repository import ProjectRepository
from src.core.ports.project_settings_repository import ProjectSettingsRepository
from src.core.ports.provider_gateway import ProviderGateway
from src.core.ports.provider_repository import ProviderRepository
from src.core.ports.stage_executor import StageExecutor
from src.core.ports.workflow_repository import WorkflowRepository


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
    channel_repository: Optional[ChannelRepository] = None,
    preset_repository: Optional[PresetRepository] = None,
    settings_repository: Optional[ProjectSettingsRepository] = None,
    asset_repository: Optional[ProjectAssetRepository] = None,
    media_repository: Optional[ProjectMediaRepository] = None,
    media_processor: Optional[MediaProcessor] = None,
    media_root: Optional[Union[str, Path]] = None,
    workflow_repository: Optional[WorkflowRepository] = None,
    stage_executor: Optional[StageExecutor] = None,
    execution_preflight: Optional[ExecutionPreflightPort] = None,
    provider_repository: Optional[ProviderRepository] = None,
    budget_repository: Optional[BudgetRepository] = None,
    credential_vault: Optional[CredentialVaultPort] = None,
    provider_gateway: Optional[ProviderGateway] = None,
    vault_path: Optional[Union[str, Path]] = None,
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

    if db_path is not None:
        target_db = Path(db_path)
    elif repository is not None and hasattr(repository, "db_path"):
        target_db = Path(getattr(repository, "db_path"))
    else:
        target_db = get_default_db_path()

    # Configure repository dependencies
    if repository is None:
        repository = SQLiteProjectRepository(db_path=target_db)
    if channel_repository is None:
        channel_repository = SQLiteChannelRepository(db_path=target_db)
    if preset_repository is None:
        preset_repository = SQLitePresetRepository(db_path=target_db)
    if settings_repository is None:
        settings_repository = SQLiteProjectSettingsRepository(db_path=target_db)
    if asset_repository is None:
        asset_repository = SQLiteProjectAssetRepository(db_path=target_db)

    if media_repository is None:
        media_repository = SQLiteProjectMediaRepository(db_path=target_db)

    if media_processor is None:
        media_processor = FFmpegMediaAdapter()

    if provider_repository is None:
        provider_repository = SQLiteProviderRepository(db_path=target_db)
    if budget_repository is None:
        budget_repository = SQLiteBudgetRepository(db_path=target_db)
    if credential_vault is None:
        resolved_vault_path = Path(vault_path) if vault_path else (target_db.parent / "secrets.vault.json")
        credential_vault = WindowsDpapiVault(vault_path=resolved_vault_path)
    if provider_gateway is None:
        provider_gateway = HttpProviderGateway()

    resolved_media_root = Path(media_root) if media_root else (target_db.parent / "media")
    resolved_media_root.mkdir(parents=True, exist_ok=True)

    if workflow_repository is None:
        workflow_repository = SQLiteWorkflowRepository(db_path=target_db)

    if stage_executor is None:
        stage_executor = LocalStageExecutor(
            media_repository=media_repository,
            media_processor=media_processor,
            media_root=resolved_media_root,
            settings_repository=settings_repository,
            asset_repository=asset_repository,
        )

    if execution_preflight is None:
        execution_preflight = AllowAllExecutionPreflight()

    app.dependency_overrides[projects.get_repository] = lambda: repository
    app.dependency_overrides[projects.get_settings_repository_for_projects] = lambda: settings_repository
    app.dependency_overrides[channels.get_channel_repository] = lambda: channel_repository
    app.dependency_overrides[presets.get_preset_repository] = lambda: preset_repository
    app.dependency_overrides[project_settings.get_project_settings_repository] = lambda: settings_repository
    app.dependency_overrides[assets.get_asset_repository] = lambda: asset_repository
    app.dependency_overrides[media.get_project_repository] = lambda: repository
    app.dependency_overrides[media.get_media_repository] = lambda: media_repository
    app.dependency_overrides[media.get_media_processor] = lambda: media_processor
    app.dependency_overrides[media.get_media_root] = lambda: resolved_media_root
    app.dependency_overrides[workflow.get_workflow_repository] = lambda: workflow_repository
    app.dependency_overrides[workflow.get_stage_executor] = lambda: stage_executor
    app.dependency_overrides[workflow.get_execution_preflight] = lambda: execution_preflight
    app.dependency_overrides[workflow.get_workflow_project_repository] = lambda: repository
    app.dependency_overrides[workflow.get_workflow_settings_repository] = lambda: settings_repository
    app.dependency_overrides[workflow.get_workflow_channel_repository] = lambda: channel_repository
    app.dependency_overrides[workflow.get_workflow_preset_repository] = lambda: preset_repository
    app.dependency_overrides[providers.get_provider_repository] = lambda: provider_repository
    app.dependency_overrides[providers.get_budget_repository] = lambda: budget_repository
    app.dependency_overrides[providers.get_credential_vault] = lambda: credential_vault
    app.dependency_overrides[providers.get_provider_gateway] = lambda: provider_gateway

    # Mount API routers
    app.include_router(health.router, prefix="/api")
    app.include_router(projects.router, prefix="/api")
    app.include_router(channels.router, prefix="/api")
    app.include_router(presets.router, prefix="/api")
    app.include_router(project_settings.router, prefix="/api")
    app.include_router(assets.router, prefix="/api")
    app.include_router(media.router, prefix="/api")
    app.include_router(workflow.router, prefix="/api")
    app.include_router(providers.router, prefix="/api")

    return app
