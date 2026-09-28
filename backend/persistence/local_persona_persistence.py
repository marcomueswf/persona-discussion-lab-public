from __future__ import annotations

from pathlib import Path

from backend.persistence.abstract_local_persistence import AbstractLocalPersistence
from backend.runtime_paths import get_runtime_file


class LocalPersonaPersistence(AbstractLocalPersistence):
    """File-backed persistence for persona entities."""

    def __init__(self, file_path: Path | None = None) -> None:
        data_file = file_path or get_runtime_file("personas.json")
        super().__init__(data_file, "personaId", use_reentrant_lock=False)

    def _default_entities(self) -> list[dict[str, object]]:
        return []
