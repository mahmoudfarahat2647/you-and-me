"""Integration tests for channels, presets, project settings, and project assets API routes."""
import pytest
from httpx import ASGITransport, AsyncClient
from src.adapters.api.app import create_app


@pytest.fixture
def api_app(tmp_path):
    return create_app(db_path=str(tmp_path / "api_channels.db"))


@pytest.mark.asyncio
async def test_channels_presets_settings_and_asset_isolation(api_app) -> None:
    transport = ASGITransport(app=api_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Built-in presets are seeded
        presets_res = await client.get("/api/presets")
        assert presets_res.status_code == 200
        presets = presets_res.json()
        assert {p["name"] for p in presets} >= {
            "Full Auto",
            "Review Before Publish",
            "Manual Studio",
        }

        # Custom preset creation
        custom_preset_res = await client.post(
            "/api/presets",
            json={
                "name": "Custom Tight Loop",
                "description": "Custom preset",
                "default_stage_modes": {"script": "approval", "export": "manual"},
            },
        )
        assert custom_preset_res.status_code == 201
        custom_preset_id = custom_preset_res.json()["id"]

        # 2. Create two distinct channels
        ch1_res = await client.post(
            "/api/channels",
            json={
                "name": "Arabic History",
                "topic_focus": "Ancient Egypt",
                "language": "Arabic",
                "default_narrator": "ar-voice-1",
                "visual_style": "Painterly",
                "video_format": "16:9",
                "budget_limit_usd": 25.0,
                "upload_destination": "YouTube",
            },
        )
        assert ch1_res.status_code == 201
        ch1 = ch1_res.json()

        ch2_res = await client.post(
            "/api/channels",
            json={
                "name": "English Shorts",
                "topic_focus": "Quick Facts",
                "language": "English",
                "default_narrator": "en-voice-2",
                "visual_style": "Neon Kinetic",
                "video_format": "9:16",
                "budget_limit_usd": 7.5,
                "upload_destination": "Shorts",
            },
        )
        assert ch2_res.status_code == 201
        ch2 = ch2_res.json()

        # Update channel 1 via PATCH
        patch_ch1 = await client.patch(
            f"/api/channels/{ch1['id']}",
            json={"budget_limit_usd": 35.0},
        )
        assert patch_ch1.status_code == 200
        assert patch_ch1.json()["budget_limit_usd"] == 35.0

        # 3. Create projects inheriting channels and presets
        p1_res = await client.post(
            "/api/projects",
            json={
                "name": "Pyramids Ep 1",
                "channel_profile_id": ch1["id"],
                "preset_id": custom_preset_id,
            },
        )
        assert p1_res.status_code == 201
        p1 = p1_res.json()

        p2_res = await client.post(
            "/api/projects",
            json={
                "name": "Pyramids Ep 2",
                "channel_profile_id": ch1["id"],
                "preset_id": "preset-full-auto",
            },
        )
        assert p2_res.status_code == 201
        p2 = p2_res.json()

        p3_res = await client.post(
            "/api/projects",
            json={
                "name": "Space Fact #1",
                "channel_profile_id": ch2["id"],
                "preset_id": "preset-manual-studio",
            },
        )
        assert p3_res.status_code == 201

        # Filter projects by channel
        ch1_projects = (await client.get(f"/api/projects?channel_profile_id={ch1['id']}")).json()
        assert len(ch1_projects) == 2
        ch2_projects = (await client.get(f"/api/projects?channel_profile_id={ch2['id']}")).json()
        assert len(ch2_projects) == 1

        # 4. Verify inherited settings and override isolation
        s1_res = await client.get(f"/api/projects/{p1['id']}/settings")
        assert s1_res.status_code == 200
        s1 = s1_res.json()
        assert s1["language"] == "Arabic"
        assert s1["narrator"] == "ar-voice-1"
        assert s1["budget_limit_usd"] == 35.0
        assert s1["stage_modes"]["script"] == "approval"
        assert s1["stage_modes"]["export"] == "manual"

        # Override p1 settings
        override_res = await client.put(
            f"/api/projects/{p1['id']}/settings",
            json={
                "language": "Spanish",
                "budget_limit_usd": 120.0,
                "stage_modes": {"script": "auto"},
                "stage_params": {"script": {"model": "Gemini-2.0-Flash"}},
            },
        )
        assert override_res.status_code == 200
        assert override_res.json()["language"] == "Spanish"
        assert override_res.json()["budget_limit_usd"] == 120.0
        assert override_res.json()["stage_modes"]["script"] == "auto"
        assert override_res.json()["stage_params"]["script"]["model"] == "Gemini-2.0-Flash"

        # Verify p2 and channel 1 were NOT mutated
        s2 = (await client.get(f"/api/projects/{p2['id']}/settings")).json()
        assert s2["language"] == "Arabic"
        assert s2["budget_limit_usd"] == 35.0
        ch1_current = (await client.get(f"/api/channels/{ch1['id']}")).json()
        assert ch1_current["language"] == "Arabic"
        assert ch1_current["budget_limit_usd"] == 35.0

        # 5. Verify project-isolated assets (script, scene, audio, export)
        a1 = (
            await client.post(
                f"/api/projects/{p1['id']}/assets",
                json={"asset_type": "script", "name": "Ep1 Script", "content": "Intro text"},
            )
        ).json()
        a2 = (
            await client.post(
                f"/api/projects/{p1['id']}/assets",
                json={"asset_type": "export", "name": "Ep1 Final", "file_path": "/exports/ep1.mp4"},
            )
        ).json()
        b1 = (
            await client.post(
                f"/api/projects/{p2['id']}/assets",
                json={"asset_type": "audio", "name": "Ep2 Voice", "file_path": "/audio/ep2.wav"},
            )
        ).json()

        p1_assets = (await client.get(f"/api/projects/{p1['id']}/assets")).json()
        assert [x["id"] for x in p1_assets] == [a1["id"], a2["id"]]
        p2_assets = (await client.get(f"/api/projects/{p2['id']}/assets")).json()
        assert [x["id"] for x in p2_assets] == [b1["id"]]

        # Cross-project delete must 404
        bad_del = await client.delete(f"/api/projects/{p2['id']}/assets/{a1['id']}")
        assert bad_del.status_code == 404

        # Proper project delete succeeds
        good_del = await client.delete(f"/api/projects/{p1['id']}/assets/{a1['id']}")
        assert good_del.status_code == 200
        p1_assets_after = (await client.get(f"/api/projects/{p1['id']}/assets")).json()
        assert [x["id"] for x in p1_assets_after] == [a2["id"]]
