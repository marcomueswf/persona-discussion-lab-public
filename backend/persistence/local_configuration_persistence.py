from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from backend.persistence.abstract_local_persistence import AbstractLocalPersistence
from backend.prompt_templates import DEFAULT_PROMPT_TEMPLATES, DEFAULT_STRATEGY_SPECIFICATIONS
from backend.runtime_paths import get_runtime_file


class LocalConfigurationPersistence(AbstractLocalPersistence):
    """File-backed singleton persistence for global configuration."""

    _DEFAULT_CONFIGURATION: dict[str, Any] = {
        "model": "gpt-4.1-mini",
        "temperature": 0.3,
        "maxRounds": 1,
        "tokenLimit": 1200,
        "promptTemplates": deepcopy(DEFAULT_PROMPT_TEMPLATES),
        "strategySpecifications": deepcopy(DEFAULT_STRATEGY_SPECIFICATIONS),
    }

    def __init__(self, file_path: Path | None = None) -> None:
        data_file = file_path or get_runtime_file("configuration.json")
        super().__init__(data_file, "configurationId", use_reentrant_lock=True)

    def _default_entities(self) -> list[dict[str, Any]]:
        return [{"configurationId": "global", **deepcopy(self._DEFAULT_CONFIGURATION)}]

    def _normalize_entities(self, payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, dict):
            merged = {**self._DEFAULT_CONFIGURATION, **payload}
            return [{"configurationId": "global", **merged}]

        entities = super()._normalize_entities(payload)
        if not entities:
            return self._default_entities()

        entity = entities[0]
        merged = {**self._DEFAULT_CONFIGURATION, **entity}
        merged["configurationId"] = "global"
        return [merged]

    def get_configuration(self) -> dict[str, Any]:
        """Return the global configuration without its persistence identifier."""
        entity = self.load_by_id("global")
        if entity is None:
            entity = self._default_entities()[0]
        return {k: v for k, v in entity.items() if k != "configurationId"}

    def save_configuration(self, configuration: dict[str, Any]) -> dict[str, Any]:
        """Merge and persist the global configuration, applying default values."""
        merged = {**self._DEFAULT_CONFIGURATION, **configuration}

        def apply_update(entity: dict[str, Any]) -> None:
            entity.clear()
            entity.update({"configurationId": "global", **merged})

        updated = self.update_by_id("global", apply_update)
        if updated is None:
            self.save_all([{"configurationId": "global", **merged}])
            return deepcopy(merged)
        return {k: v for k, v in updated.items() if k != "configurationId"}
