"""Unit tests for channels, presets, project settings inheritance/isolation, and project assets."""
import ast
from pathlib import Path
from typing import Dict, List, Optional
import pytest

from src.core.dto.asset_dto import (
    CreateProjectAssetInput,
    DeleteProjectAssetInput,
    ListProjectAssetsInput,
    ProjectAssetResult,
)
from src.core.dto.channel_dto import (
    ChannelProfileResult,
    CreateChannelInput,
    UpdateChannelInput,
)
from src.core.dto.preset_dto import CreatePresetInput, WorkflowPresetResult
from src.core.dto.project_dto import CreateProjectInput, ProjectResult
from src.core.dto.project_settings_dto import (
    GetProjectSettingsInput,
    ProjectSettingsResult,
    UpdateProjectSettingsInput,
)
from src.core.entities.channel import ChannelValidationError
from src.core.entities.preset import PresetValidationError
from src.core.entities.project_asset import AssetValidationError
from src.core.ports.asset_repository import ProjectAssetRepository
from src.core.ports.channel_repository import ChannelRepository
from src.core.ports.preset_repository import PresetRepository
from src.core.ports.project_repository import ProjectRepository
from src.core.ports.project_settings_repository import ProjectSettingsRepository
from src.core.use_cases.asset_use_cases import (
    CreateProjectAssetUseCase,
    DeleteProjectAssetUseCase,
    ListProjectAssetsUseCase,
)
from src.core.use_cases.channel_use_cases import (
    ChannelNotFoundError,
    CreateChannelUseCase,
    ListChannelsUseCase,
    UpdateChannelUseCase,
)
from src.core.use_cases.create_project import CreateProjectUseCase
from src.core.use_cases.list_projects import ListProjectsUseCase
from src.core.use_cases.preset_use_cases import (
    CreatePresetUseCase,
    ListPresetsUseCase,
    PresetNotFoundError,
)
from src.core.use_cases.project_settings_use_cases import (
    GetProjectSettingsUseCase,
    UpdateProjectSettingsUseCase,
)


class InMemoryProjectRepo(ProjectRepository):
    def __init__(self) -> None:
        self.items: Dict[str, ProjectResult] = {}

    def save(self, project: ProjectResult) -> None:
        self.items[project.id] = project

    def get_by_id(self, project_id: str) -> Optional[ProjectResult]:
        return self.items.get(project_id)

    def list_all(self) -> List[ProjectResult]:
        return list(self.items.values())

    def delete(self, project_id: str) -> bool:
        return self.items.pop(project_id, None) is not None


class InMemoryChannelRepo(ChannelRepository):
    def __init__(self) -> None:
        self.items: Dict[str, ChannelProfileResult] = {}

    def save(self, channel: ChannelProfileResult) -> None:
        self.items[channel.id] = channel

    def get_by_id(self, channel_id: str) -> Optional[ChannelProfileResult]:
        return self.items.get(channel_id)

    def list_all(self) -> List[ChannelProfileResult]:
        return list(self.items.values())

    def delete(self, channel_id: str) -> bool:
        return self.items.pop(channel_id, None) is not None


class InMemoryPresetRepo(PresetRepository):
    def __init__(self) -> None:
        self.items: Dict[str, WorkflowPresetResult] = {}

    def save(self, preset: WorkflowPresetResult) -> None:
        self.items[preset.id] = preset

    def get_by_id(self, preset_id: str) -> Optional[WorkflowPresetResult]:
        return self.items.get(preset_id)

    def list_all(self) -> List[WorkflowPresetResult]:
        return list(self.items.values())


class InMemorySettingsRepo(ProjectSettingsRepository):
    def __init__(self) -> None:
        self.items: Dict[str, ProjectSettingsResult] = {}

    def save(self, settings: ProjectSettingsResult) -> None:
        self.items[settings.project_id] = settings

    def get_by_project_id(self, project_id: str) -> Optional[ProjectSettingsResult]:
        return self.items.get(project_id)


class InMemoryAssetRepo(ProjectAssetRepository):
    def __init__(self) -> None:
        self.items: Dict[str, ProjectAssetResult] = {}

    def save(self, asset: ProjectAssetResult) -> None:
        self.items[asset.id] = asset

    def get_by_id(self, asset_id: str) -> Optional[ProjectAssetResult]:
        return self.items.get(asset_id)

    def list_by_project(
        self,
        project_id: str,
        asset_type: Optional[str] = None,
    ) -> List[ProjectAssetResult]:
        return [
            asset
            for asset in self.items.values()
            if asset.project_id == project_id
            and (asset_type is None or asset.asset_type == asset_type)
        ]

    def delete(self, project_id: str, asset_id: str) -> bool:
        asset = self.items.get(asset_id)
        if asset is None or asset.project_id != project_id:
            return False
        del self.items[asset_id]
        return True


def test_core_layer_has_no_framework_or_adapter_imports() -> None:
    forbidden = {"fastapi", "pydantic", "sqlite3", "src.adapters"}
    core_root = Path("src/core")
    for py_file in core_root.rglob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not any(alias.name.startswith(mod) for mod in forbidden), (
                        f"{py_file} imports forbidden module {alias.name}"
                    )
            elif isinstance(node, ast.ImportFrom) and node.module:
                assert not any(node.module.startswith(mod) for mod in forbidden), (
                    f"{py_file} imports from forbidden module {node.module}"
                )


def test_create_and_update_channel_profiles() -> None:
    repo = InMemoryChannelRepo()
    create_uc = CreateChannelUseCase(repo)
    update_uc = UpdateChannelUseCase(repo)

    ch1 = create_uc.execute(
        CreateChannelInput(
            name="Arabic History",
            topic_focus="Ancient civilizations",
            language="Arabic",
            default_narrator="arabic-narrator-v2",
            visual_style="Oil Painting Cinematic",
            video_format="16:9",
            budget_limit_usd=25.0,
            upload_destination="YouTube",
        )
    )
    ch2 = create_uc.execute(
        CreateChannelInput(
            name="Tech Shorts",
            topic_focus="AI & Developer Tools",
            language="English",
            default_narrator="en-studio-male",
            visual_style="Clean Motion Graphics",
            video_format="9:16",
            budget_limit_usd=8.5,
            upload_destination="YouTube Shorts",
        )
    )

    assert len(ListChannelsUseCase(repo).execute()) == 2
    updated = update_uc.execute(UpdateChannelInput(id=ch1.id, budget_limit_usd=30.0))
    assert updated.budget_limit_usd == 30.0
    ch2_stored = repo.get_by_id(ch2.id)
    assert ch2_stored is not None
    assert ch2_stored.language == "English"

    with pytest.raises(ChannelValidationError):
        create_uc.execute(CreateChannelInput(name="  ", budget_limit_usd=10.0))
    with pytest.raises(ChannelValidationError):
        create_uc.execute(CreateChannelInput(name="Bad Budget", budget_limit_usd=-1.0))
    with pytest.raises(ChannelNotFoundError):
        update_uc.execute(UpdateChannelInput(id="missing"))


def test_preset_seeding_and_validation() -> None:
    repo = InMemoryPresetRepo()
    presets = ListPresetsUseCase(repo).execute()
    names = {p.name for p in presets}
    assert {"Full Auto", "Review Before Publish", "Manual Studio"}.issubset(names)

    custom = CreatePresetUseCase(repo).execute(
        CreatePresetInput(
            name="Script Approval Only",
            description="Only script needs approval",
            default_stage_modes={"script": "approval", "export": "manual"},
        )
    )
    assert custom.default_stage_modes["script"] == "approval"
    assert custom.default_stage_modes["idea"] == "auto"

    with pytest.raises(PresetValidationError):
        CreatePresetUseCase(repo).execute(
            CreatePresetInput(name="Invalid", default_stage_modes={"unknown": "auto"})
        )


def test_project_inherits_channel_and_preset_with_override_isolation() -> None:
    project_repo = InMemoryProjectRepo()
    channel_repo = InMemoryChannelRepo()
    preset_repo = InMemoryPresetRepo()
    settings_repo = InMemorySettingsRepo()

    ListPresetsUseCase(preset_repo).execute()
    channel = CreateChannelUseCase(channel_repo).execute(
        CreateChannelInput(
            name="Documentary Hub",
            topic_focus="Science & Space",
            language="Arabic",
            default_narrator="narrator-cairo",
            visual_style="Photorealistic 4K",
            video_format="16:9",
            budget_limit_usd=40.0,
            upload_destination="YouTube",
        )
    )

    create_project_uc = CreateProjectUseCase(
        repository=project_repo,
        channel_repository=channel_repo,
        preset_repository=preset_repo,
        settings_repository=settings_repo,
    )
    proj_a = create_project_uc.execute(
        CreateProjectInput(
            name="Black Holes",
            channel_profile_id=channel.id,
            preset_id="preset-review-before-publish",
        )
    )
    proj_b = create_project_uc.execute(
        CreateProjectInput(
            name="Voyager 1",
            channel_profile_id=channel.id,
            preset_id="preset-full-auto",
        )
    )

    assert len(ListProjectsUseCase(project_repo).execute(channel_profile_id=channel.id)) == 2

    get_settings_uc = GetProjectSettingsUseCase(settings_repo, project_repo, channel_repo, preset_repo)
    update_settings_uc = UpdateProjectSettingsUseCase(settings_repo, project_repo, channel_repo, preset_repo)

    settings_a = get_settings_uc.execute(GetProjectSettingsInput(project_id=proj_a.id))
    settings_b = get_settings_uc.execute(GetProjectSettingsInput(project_id=proj_b.id))

    assert settings_a.language == "Arabic"
    assert settings_a.narrator == "narrator-cairo"
    assert settings_a.stage_modes["script"] == "approval"
    assert settings_b.stage_modes["script"] == "auto"

    # Override Project A without mutating Channel or Project B
    overridden_a = update_settings_uc.execute(
        UpdateProjectSettingsInput(
            project_id=proj_a.id,
            language="English",
            budget_limit_usd=99.0,
            stage_modes={"script": "manual"},
            stage_params={"script": {"model": "Claude-3-5-Sonnet"}},
        )
    )
    assert overridden_a.language == "English"
    assert overridden_a.budget_limit_usd == 99.0
    assert overridden_a.stage_modes["script"] == "manual"
    assert overridden_a.stage_params["script"]["model"] == "Claude-3-5-Sonnet"

    # Channel and Project B remain completely untouched
    channel_after = channel_repo.get_by_id(channel.id)
    assert channel_after is not None
    assert channel_after.language == "Arabic"
    assert channel_after.budget_limit_usd == 40.0

    settings_b_after = get_settings_uc.execute(GetProjectSettingsInput(project_id=proj_b.id))
    assert settings_b_after.language == "Arabic"
    assert settings_b_after.budget_limit_usd == 40.0
    assert settings_b_after.stage_modes["script"] == "auto"


def test_project_creation_rejects_unknown_channel_or_preset() -> None:
    project_repo = InMemoryProjectRepo()
    channel_repo = InMemoryChannelRepo()
    preset_repo = InMemoryPresetRepo()
    settings_repo = InMemorySettingsRepo()
    uc = CreateProjectUseCase(project_repo, channel_repo, preset_repo, settings_repo)

    with pytest.raises(ChannelNotFoundError):
        uc.execute(CreateProjectInput(name="P1", channel_profile_id="no-such-channel"))
    with pytest.raises(PresetNotFoundError):
        uc.execute(CreateProjectInput(name="P2", preset_id="no-such-preset"))


def test_project_assets_are_strictly_isolated_per_project() -> None:
    project_repo = InMemoryProjectRepo()
    asset_repo = InMemoryAssetRepo()
    create_project_uc = CreateProjectUseCase(project_repo)

    proj_a = create_project_uc.execute(CreateProjectInput(name="Project A"))
    proj_b = create_project_uc.execute(CreateProjectInput(name="Project B"))

    create_asset_uc = CreateProjectAssetUseCase(asset_repo, project_repo)
    list_asset_uc = ListProjectAssetsUseCase(asset_repo, project_repo)
    delete_asset_uc = DeleteProjectAssetUseCase(asset_repo, project_repo)

    a_script = create_asset_uc.execute(
        CreateProjectAssetInput(project_id=proj_a.id, asset_type="script", name="Script A", content="Alpha")
    )
    a_audio = create_asset_uc.execute(
        CreateProjectAssetInput(project_id=proj_a.id, asset_type="audio", name="Voice A", file_path="/tmp/a.wav")
    )
    b_scene = create_asset_uc.execute(
        CreateProjectAssetInput(project_id=proj_b.id, asset_type="scene", name="Scene B", content="Beta")
    )

    assert [a.id for a in list_asset_uc.execute(ListProjectAssetsInput(project_id=proj_a.id))] == [
        a_script.id,
        a_audio.id,
    ]
    assert [
        a.id
        for a in list_asset_uc.execute(ListProjectAssetsInput(project_id=proj_a.id, asset_type="script"))
    ] == [a_script.id]
    assert [a.id for a in list_asset_uc.execute(ListProjectAssetsInput(project_id=proj_b.id))] == [
        b_scene.id
    ]

    # Cross-project deletion must fail and preserve Project A's asset
    assert delete_asset_uc.execute(DeleteProjectAssetInput(project_id=proj_b.id, asset_id=a_script.id)) is False
    assert len(list_asset_uc.execute(ListProjectAssetsInput(project_id=proj_a.id))) == 2

    # Same-project deletion succeeds
    assert delete_asset_uc.execute(DeleteProjectAssetInput(project_id=proj_a.id, asset_id=a_script.id)) is True
    assert [a.id for a in list_asset_uc.execute(ListProjectAssetsInput(project_id=proj_a.id))] == [a_audio.id]

    with pytest.raises(AssetValidationError):
        create_asset_uc.execute(
            CreateProjectAssetInput(project_id=proj_a.id, asset_type="invalid", name="Bad")
        )
