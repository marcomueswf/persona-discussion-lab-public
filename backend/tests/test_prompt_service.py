import unittest

from backend.services.prompt_service import PromptService


class PromptServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = PromptService()

    def test_delphi_without_configured_item_requests_only_overall_position(self):
        """Checks that Delphi without an item requests only an overall position."""
        prompt = self.service.participant_user_prompt(
            topic="Learning in 2040",
            round_index=1,
            strategy="delphi",
            strategy_instruction="Work independently.",
            moderator_instruction="State your position.",
            context="No prior contributions.",
        )

        self.assertIn('"position":"support|oppose|mixed|undecided"', prompt)
        self.assertIn('"confidence":0.0', prompt)
        self.assertNotIn("Evaluate Delphi item", prompt)
        self.assertNotIn('"rating"', prompt)
        self.assertNotIn('"itemId"', prompt)

    def test_delphi_with_configured_item_requests_item_rating(self):
        """Checks that a configured Delphi item requests a rating."""
        prompt = self.service.participant_user_prompt(
            topic="Learning in 2040",
            round_index=1,
            strategy="delphi",
            strategy_instruction="Work independently.",
            moderator_instruction="State your position.",
            context="No prior contributions.",
            item_id="equity",
            item_statement="AI reduces educational inequality.",
        )

        self.assertIn("Evaluate Delphi item equity", prompt)
        self.assertIn("do not include an item ID", prompt)
        self.assertNotIn('"itemId"', prompt)
        self.assertIn('"rating":1', prompt)

    def test_persona_profile_fields_are_rendered_without_retired_behavior(self):
        """Checks current persona fields without rendering retired instructions."""
        prompt = self.service.participant_system_prompt(
            name="NLP Professor",
            role="professor",
            description="Places claims in theoretical context.",
            goals=("connect arguments to established concepts",),
            constraints=("distinguish evidence from interpretation",),
            communication_style="structured and precise",
        )

        self.assertIn("connect arguments to established concepts", prompt)
        self.assertIn("distinguish evidence from interpretation", prompt)
        self.assertIn("structured and precise", prompt)
        self.assertNotIn("debateBehavior", prompt)
        self.assertNotIn("persona_directives", prompt)


if __name__ == "__main__":
    unittest.main()
