from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from backend.services.environment_service import EnvironmentService
from backend.models import DiscussionConfigurationUpdate, StrategySpecificationUpdate
from backend.services.configuration_service import ConfigurationService
from backend.persistence.local_configuration_persistence import LocalConfigurationPersistence


class EnvironmentServiceTests(unittest.TestCase):
    def test_builtin_strategies_cannot_be_deleted_from_configuration(self):
        """Checks that built-in strategies cannot be removed from the configuration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            service = ConfigurationService(
                LocalConfigurationPersistence(Path(temp_dir) / "configuration.json")
            )
            specifications = [
                StrategySpecificationUpdate(
                    strategyKey="free",
                    displayName="Free discussion",
                    baseStrategy="free",
                ),
                StrategySpecificationUpdate(
                    strategyKey="delphi",
                    displayName="Delphi",
                    baseStrategy="delphi",
                ),
            ]

            with self.assertRaisesRegex(ValueError, "moderated"):
                service.update(
                    DiscussionConfigurationUpdate(strategySpecifications=specifications)
                )

    def test_environment_service_reads_and_updates_file(self):
        """Checks reading, updating, and masking sensitive environment values."""
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text(
                "OPENAI_API_KEY=old-key\nOPENAI_BASE_URL=https://old.example/v1\nOPENAI_MODEL=gpt-4.1-mini\n",
                encoding="utf-8",
            )

            service = EnvironmentService(env_path)
            payload = service.get()
            self.assertTrue(payload["OPENAI_API_KEY_SET"])
            self.assertNotIn("OPENAI_API_KEY", payload)
            self.assertEqual(payload["OPENAI_BASE_URL"], "https://old.example/v1")

            updated = service.update({
                "OPENAI_BASE_URL": "https://api.example/v1",
                "OPENAI_MODEL": "gpt-4o-mini",
            })

            self.assertEqual(updated["OPENAI_BASE_URL"], "https://api.example/v1")
            self.assertEqual(updated["OPENAI_MODEL"], "gpt-4o-mini")
            self.assertTrue(updated["OPENAI_API_KEY_SET"])
            self.assertNotIn("OPENAI_API_KEY", updated)
            self.assertEqual(os.environ["OPENAI_MODEL"], "gpt-4o-mini")

            written = env_path.read_text(encoding="utf-8")
            self.assertIn("OPENAI_BASE_URL=https://api.example/v1", written)
            self.assertIn("OPENAI_MODEL=gpt-4o-mini", written)


if __name__ == "__main__":
    unittest.main()
