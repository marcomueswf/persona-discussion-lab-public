import unittest

from backend.services.result_service import ResultService


class ResultServiceTests(unittest.TestCase):
    def test_delphi_result_contains_valid_item_metrics_from_rating_rounds(self):
        """Checks item metrics from rating rounds, including changes and stability."""
        discussion = {
            "strategy": "delphi",
            "summary": "Working thesis",
            "delphiItems": [
                {"itemId": "equity", "statement": "AI reduces educational inequality."}
            ],
            "messages": [
                {
                    "role": "participant",
                    "roundIndex": 1,
                    "personaId": "a",
                    "itemId": "equity",
                    "position": "mixed",
                    "rating": 3,
                    "validStructuredResponse": True,
                    "content": "Initial view",
                },
                {
                    "role": "participant",
                    "roundIndex": 2,
                    "personaId": "a",
                    "itemId": "equity",
                    "position": "mixed",
                    "rating": 4,
                    "validStructuredResponse": True,
                    "content": "Revised view",
                },
                {
                    "role": "participant",
                    "roundIndex": 3,
                    "personaId": "a",
                    "itemId": "equity",
                    "position": "support",
                    "rating": None,
                    "validStructuredResponse": True,
                    "content": "Discussion only",
                },
            ],
        }

        result = ResultService().build_result(discussion)
        metric = result["itemMetrics"]["equity"]

        self.assertEqual(metric["statement"], "AI reduces educational inequality.")
        self.assertEqual(metric["ratingDistribution"], {4: 1})
        self.assertEqual(metric["initialResponses"], 1)
        self.assertEqual(metric["finalResponses"], 1)
        self.assertEqual(metric["changedCount"], 1)
        self.assertEqual(metric["stabilityLevel"], 0.0)


if __name__ == "__main__":
    unittest.main()
