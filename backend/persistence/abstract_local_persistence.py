from __future__ import annotations

import json
import threading
from abc import ABC, abstractmethod
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

from backend.persistence.abstract_persistence import AbstractPersistence


class AbstractLocalPersistence(AbstractPersistence, ABC):
    """Abstract local JSON implementation with locking and atomic writes."""

    def __init__(self, file_path: Path, id_field: str, *, use_reentrant_lock: bool = True) -> None:
        """Initialize JSON storage with the entity identifier and file lock."""
        self.file_path = file_path
        self.id_field = id_field
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock() if use_reentrant_lock else threading.Lock()

    @abstractmethod
    def _default_entities(self) -> list[dict[str, Any]]:
        """Return default collection when file is absent or invalid."""

    def _normalize_entities(self, payload: Any) -> list[dict[str, Any]]:
        """Normalize loaded JSON to a list of dictionary entities."""
        if not isinstance(payload, list):
            return self._default_entities()
        normalized: list[dict[str, Any]] = []
        for item in payload:
            if isinstance(item, dict):
                normalized.append(item)
        return normalized

    def _load_unlocked(self) -> list[dict[str, Any]]:
        """Load entities without acquiring the instance lock."""
        if not self.file_path.exists():
            return deepcopy(self._default_entities())
        try:
            with self.file_path.open("r", encoding="utf-8") as file_handle:
                payload = json.load(file_handle)
        except (OSError, json.JSONDecodeError):
            return deepcopy(self._default_entities())
        normalized = self._normalize_entities(payload)
        return deepcopy(normalized)

    def _save_unlocked(self, entities: list[dict[str, Any]]) -> None:
        """Write entities through a temporary file and atomic replacement."""
        temporary_file = self.file_path.with_suffix(".tmp")
        with temporary_file.open("w", encoding="utf-8") as file_handle:
            json.dump(entities, file_handle, ensure_ascii=False, indent=2)
        temporary_file.replace(self.file_path)

    def load_all(self) -> list[dict[str, Any]]:
        """Return a deep copy of all persisted entities."""
        with self._lock:
            return deepcopy(self._load_unlocked())

    def load_by_id(self, entity_id: str) -> dict[str, Any] | None:
        """Return a deep copy of the entity with the requested identifier."""
        with self._lock:
            for entity in self._load_unlocked():
                if entity.get(self.id_field) == entity_id:
                    return deepcopy(entity)
        return None

    def create(self, entity: dict[str, Any]) -> dict[str, Any]:
        """Persist a new entity, rejecting missing or duplicate identifiers."""
        entity_id = entity.get(self.id_field)
        if not entity_id:
            raise ValueError(f"Missing required id field '{self.id_field}'")
        with self._lock:
            entities = self._load_unlocked()
            if any(item.get(self.id_field) == entity_id for item in entities):
                raise ValueError(f"Entity '{entity_id}' already exists")
            entities.append(deepcopy(entity))
            self._save_unlocked(entities)
        return deepcopy(entity)

    def update_by_id(
        self,
        entity_id: str,
        update: Callable[[dict[str, Any]], None],
    ) -> dict[str, Any] | None:
        """Atomically update one entity and return its persisted snapshot."""
        with self._lock:
            entities = self._load_unlocked()
            for entity in entities:
                if entity.get(self.id_field) != entity_id:
                    continue
                update(entity)
                self._save_unlocked(entities)
                return deepcopy(entity)
        return None

    def delete_by_id(self, entity_id: str) -> bool:
        """Delete an entity by identifier and report whether it existed."""
        with self._lock:
            entities = self._load_unlocked()
            index = next((i for i, item in enumerate(entities) if item.get(self.id_field) == entity_id), -1)
            if index == -1:
                return False
            entities.pop(index)
            self._save_unlocked(entities)
            return True

    def save_all(self, entities: list[dict[str, Any]]) -> None:
        """Replace the persisted collection with a deep-copied snapshot."""
        with self._lock:
            self._save_unlocked(deepcopy(entities))
