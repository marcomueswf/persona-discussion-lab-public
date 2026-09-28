"""Runtime environment configuration API."""

from typing import Any

from fastapi import APIRouter, Body

from backend.services.environment_service import EnvironmentService

router = APIRouter()
service = EnvironmentService()


@router.get("/env")
def get_environment() -> dict[str, Any]:
    """Return non-sensitive runtime environment values and secret status."""
    return service.get()


@router.patch("/env")
def update_environment(updates: dict[str, Any] = Body(default_factory=dict)) -> dict[str, Any]:
    """Persist selected environment variables and refresh the current process environment."""
    return service.update(updates)
