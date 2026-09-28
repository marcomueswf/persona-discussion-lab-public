import unittest

from backend.core.discussion import DiscussionTurn
from backend.models import DiscussionStartRequest
from backend.services.discussion_service import DiscussionService


class StubConfigurationService:
    def get(self):
        return {
            "model": "test-model",
            "delphiItems": [
                {"itemId": "active", "statement": "Active item", "status": "active"},
                {"itemId": "inactive", "statement": "Inactive item", "status": "inactive"},
            ],
        }


class StubEnvironmentService:
    def get(self):
        return {"OPENAI_MODEL": ""}


class InMemoryDiscussionPersistence:
    def __init__(self, discussion):
        self.discussion = discussion

    def update_by_id(self, discussion_id, update):
        update(self.discussion)
        return self.discussion


class DiscussionServiceConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.service = DiscussionService.__new__(DiscussionService)
        self.service.configuration_service = StubConfigurationService()
        self.service.environment_service = StubEnvironmentService()

    def request(self, **changes):
        values = {
            "topic": "A topic",
            "personaIds": ["persona-1", "persona-2"],
            "strategy": "delphi",
        }
        values.update(changes)
        return DiscussionStartRequest(**values)

    def test_omitted_items_use_only_active_global_defaults(self):
        """Checks that omitted items use only active global items."""
        configuration = self.service._build_configuration(self.request())

        self.assertEqual([item["itemId"] for item in configuration["delphiItems"]], ["active"])

    def test_explicit_empty_items_disable_item_ratings(self):
        """Checks that an explicitly empty item list disables item ratings."""
        configuration = self.service._build_configuration(self.request(delphiItems=[]))

        self.assertEqual(configuration["delphiItems"], [])

    def test_delphi_round_plan_is_preserved_in_discussion_configuration(self):
        """Checks that the configured Delphi round plan is preserved."""
        round_plan = {
            "1": {"mode": "open", "itemIds": []},
            "2": {"mode": "rate", "itemIds": ["active"]},
            "3": {"mode": "most_disputed", "itemIds": []},
            "4": {"mode": "synthesize", "itemIds": []},
        }

        configuration = self.service._build_configuration(
            self.request(delphiRoundPlan=round_plan)
        )

        self.assertEqual(configuration["delphiRoundPlan"][1], round_plan["1"])
        self.assertEqual(configuration["delphiRoundPlan"][2], round_plan["2"])
        self.assertEqual(configuration["delphiRoundPlan"][3], round_plan["3"])
        self.assertEqual(configuration["delphiRoundPlan"][4], round_plan["4"])

    def test_persisted_item_response_includes_readable_statement(self):
        """Checks that persisted item responses include the readable item statement."""
        discussion = {
            "delphiItems": [{"itemId": "active", "statement": "Learning should be adaptive."}],
            "messages": [],
        }
        service = DiscussionService.__new__(DiscussionService)
        service.discussion_persistence = InMemoryDiscussionPersistence(discussion)

        service._append_turn(
            "discussion-1",
            DiscussionTurn(
                round_index=1,
                persona_id="persona-1",
                persona_name="Teacher",
                role="participant",
                content="Initial response",
                item_id="active",
                rating=4,
                valid_structured_response=True,
            ),
        )

        self.assertEqual(discussion["messages"][0]["itemStatement"], "Learning should be adaptive.")


if __name__ == "__main__":
    unittest.main()