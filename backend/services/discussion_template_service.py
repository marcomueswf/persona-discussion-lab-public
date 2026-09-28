from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from backend.persistence.local_discussion_persistence import LocalDiscussionPersistence
from backend.persistence.local_discussion_template_persistence import LocalDiscussionTemplatePersistence


class DiscussionTemplateService:
    """Create and manage reusable templates from persisted discussion runs."""

    def __init__(
        self,
        template_persistence: LocalDiscussionTemplatePersistence | None = None,
        discussion_persistence: LocalDiscussionPersistence | None = None,
    ) -> None:
        self.template_persistence = template_persistence or LocalDiscussionTemplatePersistence()
        self.discussion_persistence = discussion_persistence or LocalDiscussionPersistence()

    def list(self) -> list[dict[str, Any]]:
        """Return templates newest first."""
        return sorted(
            self.template_persistence.load_all(),
            key=lambda item: item.get("createdAt", ""),
            reverse=True,
        )

    def get(self, template_id: str) -> dict[str, Any] | None:
        """Return one template by id."""
        return self.template_persistence.load_by_id(template_id)

    def create_from_discussion(self, discussion_id: str, template_name: str) -> dict[str, Any]:
        """Persist an editable setup snapshot from a completed or stopped run."""
        discussion = self.discussion_persistence.load_by_id(discussion_id)
        if discussion is None:
            raise LookupError("Discussion not found")
        if discussion.get("status") not in {"completed", "stopped"}:
            raise ValueError("Only completed or stopped discussions can be saved as templates.")

        normalized_name = template_name.strip()
        if not normalized_name:
            raise ValueError("Template name must not be empty.")

        timestamp = self._timestamp()
        template = {
            "templateId": str(uuid4()),
            "templateName": normalized_name,
            "sourceDiscussionId": discussion_id,
            "topic": discussion["topic"],
            "strategy": discussion["strategy"],
            "personaIds": list(discussion.get("personaIds", [])),
            "configuration": deepcopy(discussion.get("configuration")),
            "createdAt": timestamp,
            "updatedAt": timestamp,
        }
        return self.template_persistence.create(template)

    def delete(self, template_id: str) -> bool:
        """Delete a saved template."""
        return self.template_persistence.delete_by_id(template_id)

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(timezone.utc).isoformat()