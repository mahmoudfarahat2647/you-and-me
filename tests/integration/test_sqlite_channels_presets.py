"""SQLite integration tests for channels, presets, project settings, and project assets."""
from src.adapters.storage.sqlite_channel_repository import SQLiteChannelRepository
from src.adapters.storage.sqlite_preset_repository import SQLitePresetRepository
from src.adapters.storage.sqlite_project_asset_repository import SQLiteProjectAssetRepository
from src.adapters.storage.sqlite_project_repository import SQLiteProjectRepository
from src.adapters.storage.sqlite_project_settings_repository import SQLiteProjectSettingsRepository
from src.core.dto.asset_dto import CreateProjectAssetInput, ListProjectAssetsInput
from src.core.dto.channel_dto import CreateChannelInput
from src.core.dto.project_dto import CreateProjectInput
from src.core.dto.project_settings_dto import GetProjectSettingsInput, UpdateProjectSettingsInput
from src.core.use_cases.asset_use_cases import CreateProjectAssetUseCase, ListProjectAssetsUseCase
from src.core.use_cases.channel_use_cases import CreateChannelUseCase
from src.core.use_cases.create_project import CreateProjectUseCase
from src.core.use_cases.project_settings_use_cases import (
    GetProjectSettingsUseCase,
    UpdateProjectSettingsUseCase,
)


def test_sqlite_seeds_builtin_presets_and_persists_across_reopen(tmp_path) -> None:
    db_file = tmp_path / "studio.db"
    preset_repo1 = SQLitePresetRepository(db_file)
    presets = preset_repo1.list_all()
    assert len(presets) >= 3
    assert {p.name for p in presets} >= {"Full Auto", "Review Before Publish", "Manual Studio"}

    # Reopen repository
    preset_repo2 = SQLitePresetRepository(db_file)
    assert len(preset_repo2.list_all()) == len(presets)


def test_sqlite_channel_preset_inheritance_and_asset_isolation(tmp_path) -> None:
    db_file = tmp_path / "studio.db"
    proj_repo = SQLiteProjectRepository(db_file)
    chan_repo = SQLiteChannelRepository(db_file)
    preset_repo = SQLitePresetRepository(db_file)
    settings_repo = SQLiteProjectSettingsRepository(db_file)
    asset_repo = SQLiteProjectAssetRepository(db_file)

    channel = CreateChannelUseCase(chan_repo).execute(
        CreateChannelInput(
            name="Science Channel",
            topic_focus="Physics",
            language="Arabic",
            default_narrator="science-ar-v1",
            visual_style="3D Explainer",
            video_format="16:9",
            budget_limit_usd=20.0,
            upload_destination="YouTube",
        )
    )

    create_project = CreateProjectUseCase(proj_repo, chan_repo, preset_repo, settings_repo)
    p1 = create_project.execute(
        CreateProjectInput(
            name="Quantum Entanglement",
            channel_profile_id=channel.id,
            preset_id="preset-manual-studio",
        )
    )
    p2 = create_project.execute(
        CreateProjectInput(
            name="Dark Matter",
            channel_profile_id=channel.id,
            preset_id="preset-full-auto",
        )
    )

    # Override p1 settings
    UpdateProjectSettingsUseCase(settings_repo, proj_repo, chan_repo, preset_repo).execute(
        UpdateProjectSettingsInput(
            project_id=p1.id,
            language="French",
            narrator="fr-narrator",
            stage_modes={"script": "approval"},
        )
    )

    # Create assets in both projects
    create_asset = CreateProjectAssetUseCase(asset_repo, proj_repo)
    create_asset.execute(
        CreateProjectAssetInput(project_id=p1.id, asset_type="script", name="P1 Script", content="Bonjour")
    )
    create_asset.execute(
        CreateProjectAssetInput(project_id=p2.id, asset_type="export", name="P2 Export", file_path="/out/p2.mp4")
    )

    # Reopen fresh repository instances against the same DB
    proj_repo2 = SQLiteProjectRepository(db_file)
    chan_repo2 = SQLiteChannelRepository(db_file)
    preset_repo2 = SQLitePresetRepository(db_file)
    settings_repo2 = SQLiteProjectSettingsRepository(db_file)
    asset_repo2 = SQLiteProjectAssetRepository(db_file)

    get_settings = GetProjectSettingsUseCase(settings_repo2, proj_repo2, chan_repo2, preset_repo2)
    s1 = get_settings.execute(GetProjectSettingsInput(project_id=p1.id))
    s2 = get_settings.execute(GetProjectSettingsInput(project_id=p2.id))

    assert s1.language == "French"
    assert s1.narrator == "fr-narrator"
    assert s1.stage_modes["script"] == "approval"
    assert s2.language == "Arabic"
    assert s2.narrator == "science-ar-v1"
    assert s2.stage_modes["script"] == "auto"

    list_assets = ListProjectAssetsUseCase(asset_repo2, proj_repo2)
    p1_assets = list_assets.execute(ListProjectAssetsInput(project_id=p1.id))
    p2_assets = list_assets.execute(ListProjectAssetsInput(project_id=p2.id))
    assert [a.name for a in p1_assets] == ["P1 Script"]
    assert [a.name for a in p2_assets] == ["P2 Export"]
