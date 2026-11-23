"""Health check route for desktop application readiness probe."""
from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict:
    """Readiness probe endpoint for desktop host to verify local backend startup."""
    return {
        "status": "ok",
        "app": "AI Video Studio Backend",
        "version": "0.1.0",
    }
