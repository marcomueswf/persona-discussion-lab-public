from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from backend.persistence.local_discussion_persistence import LocalDiscussionPersistence
from backend.persistence.local_discussion_template_persistence import LocalDiscussionTemplatePersistence
from backend.services.discussion_service import DiscussionService
from backend.services.discussion_template_service import DiscussionTemplateService


class DiscussionTemplateServiceTests(unittest.TestCase):
    def test_completed_discussion_is_saved_with_setup_snapshot(self):
        """Checks that a completed discussion is saved as a template with its setup."""
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            discussions = LocalDiscussionPersistence(root / "discussions.json")
            templates = LocalDiscussionTemplatePersistence(root / "templates.json")
            discussions.create(
                {
                    "discussionId": "d1",
                    "status": "completed",
                    "topic": "Should we ship?",
                    "strategy": "delphi",
                    "personaIds": ["p1", "p2"],
                    "configuration": {
                        "temperature": 0.7,
                        "delphiItems": [{"itemId": "equity", "statement": "Learning should be equitable."}],
                    },
                }
            )

            saved = DiscussionTemplateService(templates, discussions).create_from_discussion("d1", "Release review")

            self.assertEqual(saved["templateName"], "Release review")
            self.assertEqual(saved["topic"], "Should we ship?")
            self.assertEqual(saved["strategy"], "delphi")
            self.assertEqual(saved["personaIds"], ["p1", "p2"])
            self.assertEqual(
                saved["configuration"],
                {
                    "temperature": 0.7,
                    "delphiItems": [{"itemId": "equity", "statement": "Learning should be equitable."}],
                },
            )

    def test_running_discussion_cannot_be_saved(self):
        """Checks that a running discussion cannot be saved as a template."""
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            discussions = LocalDiscussionPersistence(root / "discussions.json")
            discussions.create({"discussionId": "d1", "status": "running"})

            with self.assertRaises(ValueError):
                DiscussionTemplateService(
                    LocalDiscussionTemplatePersistence(root / "templates.json"),
                    discussions,
                ).create_from_discussion("d1", "Not ready")

    def test_completed_discussion_can_be_deleted_from_history(self):
        """Checks that a completed discussion can be deleted from history."""
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            discussions = LocalDiscussionPersistence(root / "discussions.json")
            discussions.create({"discussionId": "d1", "status": "completed"})
            service = DiscussionService(discussion_persistence=discussions)

            self.assertTrue(service.delete("d1"))
            self.assertIsNone(discussions.load_by_id("d1"))


if __name__ == "__main__":
    unittest.main()
