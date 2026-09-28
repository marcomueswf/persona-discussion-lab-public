"""Configuration router for global discussion defaults."""

from fastapi import APIRouter

from backend.models import DiscussionConfiguration, DiscussionConfigurationUpdate
from backend.services.configuration_service import ConfigurationService

router = APIRouter()
service = ConfigurationService()


@router.get("/configuration", response_model=DiscussionConfiguration)
def get_configuration():
    """Return the persisted effective discussion configuration."""
    return service.get()


@router.patch("/configuration", response_model=DiscussionConfiguration)
def update_configuration(changes: DiscussionConfigurationUpdate):
    """Patch persisted defaults with provided non-null fields."""
    return service.update(changes)
