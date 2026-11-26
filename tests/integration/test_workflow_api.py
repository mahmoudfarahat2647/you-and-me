"""Integration tests for persisted workflow API routes wired with FFmpeg and SQLite."""
import subprocess
from pathlib import Path
import pytest
from httpx import ASGITransport, AsyncClient

from src.adapters.api.app import create_app


@pytest.mark.asyncio
async def test_run_node_runs_prerequisites_and_leaves_unrelated_stages_pending(tmp_path: Path) -> None:
    app = create_app(db_path=str(tmp_path / "studio.db"))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        project = (await client.post("/api/projects", json={"name": "Run a node"})).json()
        node_path = f"/api/projects/{project['id']}/workflow/stages/script/run"
        first = await client.post(node_path)
        assert first.status_code == 200, first.text
        before = first.json()["job"]
        assert before["status"] == "paused"
        assert [stage["status"] for stage in before["stages"]] == [
            "completed", "completed", "pending", "pending", "pending", "pending",
        ]

        repeat = await client.post(node_path)
        assert repeat.status_code == 200, repeat.text
        after = repeat.json()["job"]
        assert after["id"] == before["id"]
        assert [stage["attempt_count"] for stage in after["stages"]] == [1, 2, 0, 0, 0, 0]


def _make_sample_video(path: Path, color: str, duration: float = 0.8) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c={color}:s=320x240:r=24:d={duration}",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(path),
        ],
        check=True,
        capture_output=True,
    )


def _make_sample_audio(path: Path, duration: float = 1.6) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=440:duration={duration}",
            "-c:a",
            "pcm_s16le",
            str(path),
        ],
        check=True,
        capture_output=True,
    )


@pytest.mark.asyncio
async def test_workflow_api_runs_pauses_approves_exports_mp4_and_selectively_invalidates_scene(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "studio.db"
    media_root = tmp_path / "media"
    clip1 = tmp_path / "clip1.mp4"
    clip2 = tmp_path / "clip2.mp4"
    narration = tmp_path / "narration.wav"
    _make_sample_video(clip1, "blue")
    _make_sample_video(clip2, "red")
    _make_sample_audio(narration)

    app = create_app(db_path=str(db_path), media_root=media_root)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Create project
        proj_res = await client.post(
            "/api/projects",
            json={"name": "Workflow E2E", "description": "Real FFmpeg workflow"},
        )
        assert proj_res.status_code == 201
        project_id = proj_res.json()["id"]

        # 2. Import two clips & narration audio via #7 routes
        c1_res = await client.post(
            f"/api/projects/{project_id}/media/clips",
            json={"source_path": str(clip1)},
        )
        c2_res = await client.post(
            f"/api/projects/{project_id}/media/clips",
            json={"source_path": str(clip2)},
        )
        a_res = await client.post(
            f"/api/projects/{project_id}/media/audio",
            json={"source_path": str(narration)},
        )
        assert c1_res.status_code == 201
        assert c2_res.status_code == 201
        assert a_res.status_code == 201
        clip1_id = c1_res.json()["id"]
        clip2_id = c2_res.json()["id"]

        # 3. Attempting to turn off required stage 'voice' without compatible artifact fails 422 before submission
        bad_run = await client.post(
            f"/api/projects/{project_id}/workflow/run",
            json={"stage_modes": {"voice": "off"}},
        )
        assert bad_run.status_code == 422
        assert "narration" in bad_run.json()["detail"]

        # 4. Set script to approval mode, idea to manual mode, and run workflow -> stops at idea waiting_manual
        await client.put(
            f"/api/projects/{project_id}/workflow/stages/idea/mode",
            json={"mode": "manual"},
        )
        await client.put(
            f"/api/projects/{project_id}/workflow/stages/script/mode",
            json={"mode": "approval"},
        )
        run1 = await client.post(f"/api/projects/{project_id}/workflow/run")
        assert run1.status_code == 200
        job1 = run1.json()["job"]
        assert job1["status"] == "paused"
        stages1 = {s["stage_id"]: s for s in job1["stages"]}
        assert stages1["idea"]["status"] == "waiting_manual"
        assert stages1["script"]["status"] == "pending"

        # 5. Supply manual idea -> runs script then pauses in awaiting_approval
        manual_res = await client.post(
            f"/api/projects/{project_id}/workflow/stages/idea/manual",
            json={"content": "History of Alexandria Lighthouse", "auto_resume": True},
        )
        assert manual_res.status_code == 200
        job2 = manual_res.json()["job"]
        assert job2["status"] == "paused"
        stages2 = {s["stage_id"]: s for s in job2["stages"]}
        assert stages2["idea"]["status"] == "completed"
        assert stages2["script"]["status"] == "awaiting_approval"

        # 6. Approve script with edit -> completes voice, scenes, edit, and real FFmpeg export!
        approve_res = await client.post(
            f"/api/projects/{project_id}/workflow/stages/script/approve",
            json={"approved": True, "edited_content": "Approved script text", "auto_resume": True},
        )
        assert approve_res.status_code == 200
        job3 = approve_res.json()["job"]
        assert job3["status"] == "completed"
        stages3 = {s["stage_id"]: s for s in job3["stages"]}
        assert stages3["export"]["status"] == "completed"
        export_path = Path(stages3["export"]["artifact"]["uri"])
        assert export_path.exists()
        assert len(stages3["scenes"]["items"]) == 2

        # 7. Edit single scene item (clip2_id) -> marks ONLY scenes (+ clip2), edit, export stale; idea/script/voice/clip1 stay completed!
        scene_edit_res = await client.put(
            f"/api/projects/{project_id}/workflow/scenes/{clip2_id}",
            json={"prompt": "Tighter zoom on red scene", "reason": "Scene 2 tweak"},
        )
        assert scene_edit_res.status_code == 200
        job4 = scene_edit_res.json()["job"]
        assert job4["status"] == "paused"
        stages4 = {s["stage_id"]: s for s in job4["stages"]}
        assert stages4["idea"]["status"] == "completed"
        assert stages4["script"]["status"] == "completed"
        assert stages4["voice"]["status"] == "completed"
        assert stages4["scenes"]["status"] == "stale"
        assert stages4["edit"]["status"] == "stale"
        assert stages4["export"]["status"] == "stale"

        items4 = {item["item_id"]: item for item in stages4["scenes"]["items"]}
        assert items4[clip1_id]["status"] == "completed"
        assert items4[clip2_id]["status"] == "stale"

        # 8. Rerun -> executes only scenes, edit, export while keeping idea/script/voice attempt_count unchanged
        rerun_res = await client.post(f"/api/projects/{project_id}/workflow/run")
        assert rerun_res.status_code == 200
        job5 = rerun_res.json()["job"]
        assert job5["status"] == "completed"
        stages5 = {s["stage_id"]: s for s in job5["stages"]}
        assert stages5["idea"]["attempt_count"] == stages3["idea"]["attempt_count"]
        assert stages5["script"]["attempt_count"] == stages3["script"]["attempt_count"]
        assert stages5["voice"]["attempt_count"] == stages3["voice"]["attempt_count"]
        assert stages5["scenes"]["attempt_count"] == stages3["scenes"]["attempt_count"] + 1
        assert stages5["edit"]["attempt_count"] == stages3["edit"]["attempt_count"] + 1
        assert stages5["export"]["attempt_count"] == stages3["export"]["attempt_count"] + 1
        items5 = {item["item_id"]: item for item in stages5["scenes"]["items"]}
        assert items5[clip1_id]["artifact"] == items4[clip1_id]["artifact"]
        assert items5[clip2_id]["artifact"]["artifact_id"] != items4[clip2_id]["artifact"]["artifact_id"]
        assert items5[clip2_id]["input_data"]["prompt"] == "Tighter zoom on red scene"

        # 9. Persisted logs exist across app reload
        app_reloaded = create_app(db_path=str(db_path), media_root=media_root)
        async with AsyncClient(
            transport=ASGITransport(app=app_reloaded), base_url="http://test"
        ) as client2:
            get_wf = await client2.get(f"/api/projects/{project_id}/workflow")
            assert get_wf.status_code == 200
            body = get_wf.json()
            assert body["job"]["id"] == job5["id"]
            assert body["job"]["status"] == "completed"
            assert len(body["logs"]) > 0
