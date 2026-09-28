from __future__ import annotations
"""Application service for discussion default configuration."""

from backend.models import DiscussionConfiguration, DiscussionConfigurationUpdate
from backend.persistence.local_configuration_persistence import LocalConfigurationPersistence
from backend.prompt_templates import IMPLEMENTED_STRATEGIES


class ConfigurationService:
    """Validates and persists global configuration defaults."""

    def __init__(self, persistence: LocalConfigurationPersistence | None = None) -> None:
        self.persistence = persistence or LocalConfigurationPersistence()

    def get(self) -> dict:
        """Return effective configuration with schema validation."""
        configuration = DiscussionConfiguration(**self.persistence.get_configuration())
        payload = configuration.model_dump(by_alias=True)
        payload["implementedStrategies"] = [
            {"key": key, **value}
            for key, value in IMPLEMENTED_STRATEGIES.items()
        ]
        return payload

    def update(self, changes: DiscussionConfigurationUpdate) -> dict:
        """Apply partial updates over current defaults and persist result."""
        current_payload = DiscussionConfiguration(**self.persistence.get_configuration()).model_dump(by_alias=True)
        updates = changes.model_dump(exclude_none=True, by_alias=True)

        if "promptTemplates" in updates:
            current_templates = current_payload.get("promptTemplates", {})
            incoming_templates = updates["promptTemplates"]
            updates["promptTemplates"] = {
                **current_templates,
                **incoming_templates,
                "global": {
                    **current_templates.get("global", {}),
                    **incoming_templates.get("global", {}),
                },
            }

        merged_payload = {**current_payload, **updates}
        if "strategySpecifications" in updates:
            configured_keys = {
                specification["strategyKey"]
                for specification in updates["strategySpecifications"]
            }
            missing_base_strategies = set(IMPLEMENTED_STRATEGIES) - configured_keys
            if missing_base_strategies:
                missing = ", ".join(sorted(missing_base_strategies))
                raise ValueError(f"Built-in strategies cannot be deleted or renamed: {missing}")

        updated = DiscussionConfiguration(**merged_payload)
        persisted = updated.model_dump(by_alias=True, exclude={"implementedStrategies"})
        saved = self.persistence.save_configuration(persisted)
        saved["implementedStrategies"] = [
            {"key": key, **value}
            for key, value in IMPLEMENTED_STRATEGIES.items()
        ]
        return saved
