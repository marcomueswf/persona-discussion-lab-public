from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable


class AbstractPersistence(ABC):
    """Contract for id-based persistence over JSON-like payloads."""

    @abstractmethod
    def load_all(self) -> list[dict[str, Any]]:
        """Return all entities as deep copies."""

    @abstractmethod
    def load_by_id(self, entity_id: str) -> dict[str, Any] | None:
        """Return one entity by id or None when not found."""

    @abstractmethod
    def create(self, entity: dict[str, Any]) -> dict[str, Any]:
        """Persist a new entity and return the stored snapshot."""

    @abstractmethod
    def update_by_id(
        self,
        entity_id: str,
        update: Callable[[dict[str, Any]], None],
    ) -> dict[str, Any] | None:
        """Atomically mutate one entity and return the updated snapshot."""

    @abstractmethod
    def delete_by_id(self, entity_id: str) -> bool:
        """Delete an entity and report whether it existed."""

    @abstractmethod
    def save_all(self, entities: list[dict[str, Any]]) -> None:
        """Replace complete entity collection atomically."""
