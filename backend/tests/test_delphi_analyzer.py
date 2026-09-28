import unittest

from backend.services.delphi_analyzer import DelphiAnalyzer


class DelphiAnalyzerTests(unittest.TestCase):
    def setUp(self):
        self.analyzer = DelphiAnalyzer()

    def test_analyzes_final_round_and_position_stability(self):
        """Checks consensus, disagreement, stability, and polarization in the final round."""
        messages = [
            {"role": "participant", "roundIndex": 1, "personaId": "a", "position": "support"},
            {"role": "participant", "roundIndex": 1, "personaId": "b", "position": "oppose"},
            {"role": "participant", "roundIndex": 1, "personaId": "c", "position": "support"},
            {"role": "participant", "roundIndex": 2, "personaId": "a", "position": "support"},
            {"role": "participant", "roundIndex": 2, "personaId": "b", "position": "support"},
            {"role": "participant", "roundIndex": 2, "personaId": "c", "position": "oppose"},
        ]

        result = self.analyzer.analyze(messages)

        self.assertEqual(result["consensusLevel"], 2 / 3)
        self.assertAlmostEqual(result["disagreementLevel"], 1 / 3)
        self.assertAlmostEqual(result["stabilityLevel"], 1 / 3)
        self.assertEqual(result["minorityPositions"], ["oppose"])
        self.assertAlmostEqual(result["polarizationLevel"], 2 / 3)

    def test_ignores_unstructured_positions(self):
        """Checks that missing or invalid positions are ignored by the analysis."""
        result = self.analyzer.analyze(
            [{"role": "participant", "roundIndex": 1, "personaId": "a", "position": None}]
        )

        self.assertIsNone(result["consensusLevel"])
        self.assertEqual(result["minorityPositions"], [])

    def test_analyzes_configured_items_and_rating_changes(self):
        """Checks rating distribution, changes, and stability for configured items."""
        items = [{"itemId": "teacher-role", "statement": "Teachers become coaches."}]
        messages = [
            {"role": "participant", "itemId": "teacher-role", "roundIndex": 1, "personaId": "a", "rating": 4, "validStructuredResponse": True},
            {"role": "participant", "itemId": "teacher-role", "roundIndex": 1, "personaId": "b", "rating": 3, "validStructuredResponse": True},
            {"role": "participant", "itemId": "teacher-role", "roundIndex": 2, "personaId": "a", "rating": 5, "validStructuredResponse": True},
            {"role": "participant", "itemId": "teacher-role", "roundIndex": 2, "personaId": "b", "rating": 3, "validStructuredResponse": True},
        ]

        result = self.analyzer.analyze_items(messages, items)["teacher-role"]

        self.assertEqual(result["ratingDistribution"], {3: 1, 5: 1})
        self.assertEqual(result["changedCount"], 1)
        self.assertAlmostEqual(result["stabilityLevel"], 0.5)


if __name__ == "__main__":
    unittest.main()