from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from backend.persistence.local_configuration_persistence import LocalConfigurationPersistence
from backend.persistence.local_discussion_persistence import LocalDiscussionPersistence
from backend.persistence.local_persona_persistence import LocalPersonaPersistence
from backend.models import Persona, PersonaUpdate
from backend.services.persona_service import PersonaService


class PersistenceClassesTests(unittest.TestCase):
    def test_persona_defaults_are_normalized_by_service(self):
        """Checks that missing persona fields are filled with default values."""
        with tempfile.TemporaryDirectory() as temp_dir:
            persistence = LocalPersonaPersistence(Path(temp_dir) / "personas.json")
            persistence.create({"personaId": "p1", "name": "Alice"})

            persona = PersonaService(persistence).list()[0]

            self.assertEqual(persona["expertise"], [])

    def test_persona_update_rejects_unknown_fields_and_validates_payload(self):
        """Checks validation of persona updates and default values in the model."""
        with self.assertRaises(ValueError):
            PersonaUpdate.model_validate({"unknown": "value"})

        persona = Persona.model_validate({"personaId": "p1", "name": "Alice"})
        self.assertEqual(persona.goals, [])

    def test_persona_persistence_crud(self):
        """Checks creating, loading, updating, and deleting a persona."""
        with tempfile.TemporaryDirectory() as temp_dir:
            data_file = Path(temp_dir) / "personas.json"
            persistence = LocalPersonaPersistence(data_file)

            created = persistence.create({"personaId": "p1", "name": "Alice"})
            self.assertEqual(created["personaId"], "p1")

            loaded = persistence.load_by_id("p1")
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded["name"], "Alice")

            updated = persistence.update_by_id("p1", lambda entity: entity.update({"name": "Bob"}))
            self.assertIsNotNone(updated)
            self.assertEqual(updated["name"], "Bob")

            deleted = persistence.delete_by_id("p1")
            self.assertTrue(deleted)
            self.assertIsNone(persistence.load_by_id("p1"))

    def test_discussion_persistence_update_and_load(self):
        """Checks that a discussion can be updated and loaded with its messages."""
        with tempfile.TemporaryDirectory() as temp_dir:
            data_file = Path(temp_dir) / "discussions.json"
            persistence = LocalDiscussionPersistence(data_file)

            persistence.create(
                {
                    "discussionId": "d1",
                    "topic": "T",
                    "status": "queued",
                    "messages": [],
                }
            )

            persistence.update_by_id("d1", lambda entity: entity["messages"].append({"role": "participant"}))
            current = persistence.load_by_id("d1")
            self.assertIsNotNone(current)
            self.assertEqual(len(current["messages"]), 1)

    def test_configuration_persistence_accepts_legacy_dict_file(self):
        """Checks loading legacy configuration files and saving values with defaults."""
        with tempfile.TemporaryDirectory() as temp_dir:
            data_file = Path(temp_dir) / "configuration.json"
            with data_file.open("w", encoding="utf-8") as file_handle:
                json.dump({"model": "gpt-4.1-mini", "maxRounds": 3}, file_handle)

            persistence = LocalConfigurationPersistence(data_file)
            config = persistence.get_configuration()
            self.assertEqual(config["model"], "gpt-4.1-mini")
            self.assertEqual(config["maxRounds"], 3)
            self.assertIn("temperature", config)

            saved = persistence.save_configuration({"temperature": 0.7})
            self.assertEqual(saved["temperature"], 0.7)
            self.assertEqual(saved["model"], "gpt-4.1-mini")


if __name__ == "__main__":
    unittest.main()
