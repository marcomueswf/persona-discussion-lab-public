import json
import unittest

from backend.models import DiscussionTraceEntry
from backend.services.discussion_service import DiscussionService
from backend.services.result_service import ResultService


class InMemoryDiscussionPersistence:
    def __init__(self, discussion):
        self.discussion = discussion

    def load_by_id(self, discussion_id):
        return self.discussion

    def update_by_id(self, discussion_id, update):
        update(self.discussion)
        return self.discussion


class DiscussionTraceTests(unittest.TestCase):
    def test_persists_delphi_analyzer_output_as_trace_entry(self):
        """Checks that analysis results, inputs, and metrics are stored in the trace."""
        discussion = {
            "strategy": "delphi",
            "summary": "Test summary",
            "delphiItems": [{"itemId": "item-1", "statement": "Test item"}],
            "messages": [
                {
                    "role": "participant",
                    "roundIndex": 1,
                    "personaId": "persona-1",
                    "position": "support",
                    "itemId": "item-1",
                    "rating": 3,
                    "validStructuredResponse": True,
                },
                {
                    "role": "participant",
                    "roundIndex": 2,
                    "personaId": "persona-1",
                    "position": "support",
                    "itemId": "item-1",
                    "rating": 4,
                    "validStructuredResponse": True,
                },
            ],
            "trace": [],
        }
        persistence = InMemoryDiscussionPersistence(discussion)
        service = DiscussionService.__new__(DiscussionService)
        service.discussion_persistence = persistence
        service.result_service = ResultService()

        def append_trace(entry):
            entry["sequence"] = len(discussion["trace"]) + 1
            discussion["trace"].append(entry)

        service._persist_result("discussion-1", append_trace)

        trace_entry = DiscussionTraceEntry.model_validate(discussion["trace"][0])
        output = trace_entry.analysisOutput
        self.assertEqual(trace_entry.callType, "analysis")
        self.assertEqual(trace_entry.analysisBasis["participantResponses"], 2)
        self.assertEqual(trace_entry.analysisBasis["configuredItemIds"], ["item-1"])
        self.assertEqual(
            trace_entry.analysisBasis["positionCountsByRound"],
            {"1": {"support": 1}, "2": {"support": 1}},
        )
        self.assertEqual(output["positions"]["consensusLevel"], 1.0)
        self.assertEqual(output["items"]["item-1"]["ratingDistribution"], {4: 1})
        self.assertEqual(json.loads(json.dumps(output))["items"]["item-1"]["changedCount"], 1)


if __name__ == "__main__":
    unittest.main()