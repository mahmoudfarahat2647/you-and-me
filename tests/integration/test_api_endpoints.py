"""Integration tests for FastAPI endpoints verifying HTTP contracts and SQLite persistence."""
import pytest
from httpx import ASGITransport, AsyncClient
from src.adapters.api.app import create_app
from src.adapters.storage.sqlite_project_repository import SQLiteProjectRepository


@pytest.fixture
def test_app(tmp_path):
    db_file = tmp_path / "test_api.db"
    repo = SQLiteProjectRepository(db_path=db_file)
    return create_app(repository=repo)


@pytest.mark.asyncio
async def test_health_check(test_app) -> None:
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ok"
        assert "AI Video Studio" in data["app"]


@pytest.mark.asyncio
async def test_create_and_reopen_project(test_app) -> None:
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create
        create_payload = {
            "name": "The Pyramids Mystery",
            "description": "Documentary about Giza",
        }
        create_res = await client.post("/api/projects", json=create_payload)
        assert create_res.status_code == 201
        project_data = create_res.json()
        project_id = project_data["id"]
        assert project_id is not None
        assert project_data["name"] == "The Pyramids Mystery"
        assert project_data["description"] == "Documentary about Giza"

        # Reopen by ID
        get_res = await client.get(f"/api/projects/{project_id}")
        assert get_res.status_code == 200
        reopened = get_res.json()
        assert reopened["id"] == project_id
        assert reopened["name"] == "The Pyramids Mystery"

        # List
        list_res = await client.get("/api/projects")
        assert list_res.status_code == 200
        projects = list_res.json()
        assert len(projects) == 1
        assert projects[0]["id"] == project_id


@pytest.mark.asyncio
async def test_create_empty_name_returns_422(test_app) -> None:
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post("/api/projects", json={"name": ""})
        assert res.status_code == 422


@pytest.mark.asyncio
async def test_get_nonexistent_project_returns_404(test_app) -> None:
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/projects/unknown-uuid")
        assert res.status_code == 404
