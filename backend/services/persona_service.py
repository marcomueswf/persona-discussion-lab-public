from __future__ import annotations
"""Application service for persona CRUD operations."""

from typing import Any

from backend.models import Persona, PersonaUpdate
from backend.persistence.local_persona_persistence import LocalPersonaPersistence


class PersonaService:
    """Encapsulates persona business rules over persistence adapters."""

    def __init__(self, persistence: LocalPersonaPersistence | None = None) -> None:
        self.persistence = persistence or LocalPersonaPersistence()

    def list(self) -> list[dict[str, Any]]:
        """Return all personas."""
        return [Persona.model_validate(item).model_dump() for item in self.persistence.load_all()]

    def create(self, persona: Persona) -> dict[str, Any]:
        """Create one persona and enforce unique ``personaId``."""
        payload = persona.model_dump()
        try:
            return self.persistence.create(payload)
        except ValueError as error:
            raise ValueError(f"Persona '{persona.personaId}' already exists") from error

    def update(self, persona_id: str, changes: PersonaUpdate) -> dict[str, Any] | None:
        """Merge partial updates into an existing persona."""
        payload = changes.model_dump(exclude_unset=True)

        def merge(entity: dict[str, Any]) -> None:
            entity.update(payload)

        updated = self.persistence.update_by_id(persona_id, merge)
        if updated is None:
            return None
        return Persona.model_validate(updated).model_dump()

    def delete(self, persona_id: str) -> bool:
        """Delete a persona by id and report whether it existed."""
        return self.persistence.delete_by_id(persona_id)
