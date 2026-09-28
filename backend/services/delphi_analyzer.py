from __future__ import annotations
"""Deterministic analysis for structured Delphi participant responses."""

from collections import Counter, defaultdict
from typing import Any


_VALID_POSITIONS = {"support", "oppose", "mixed", "undecided"}


class DelphiAnalyzer:
    """Calculate Delphi metrics from validated participant messages."""

    def analyze(self, messages: list[dict[str, Any]]) -> dict[str, Any]:
        """Calculate position consensus metrics for the final discussion round.

        Args:
            messages: Persisted participant messages with round and position data.

        Returns:
            Consensus, disagreement, stability, polarization, and minority metrics.
        """
        responses_by_round: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for message in messages:
            if message.get("role") != "participant":
                continue
            position = message.get("position")
            if position not in _VALID_POSITIONS:
                continue
            round_index = message.get("roundIndex")
            if isinstance(round_index, int) and round_index >= 1:
                responses_by_round[round_index].append(message)

        if not responses_by_round:
            return self._empty_result()

        final_round = max(responses_by_round)
        final_messages = responses_by_round[final_round]
        counts = Counter(message["position"] for message in final_messages)
        total = sum(counts.values())
        consensus_level = max(counts.values()) / total if total else None
        minority_positions = [position for position, count in counts.items() if count < max(counts.values())]

        result = {
            "consensusLevel": consensus_level,
            "disagreementLevel": 1 - consensus_level if consensus_level is not None else None,
            "stabilityLevel": self._stability(responses_by_round, final_round),
            "polarizationLevel": self._polarization(counts, total),
            "minorityPositions": sorted(minority_positions),
        }
        return result

    def analyze_items(
        self,
        messages: list[dict[str, Any]],
        items: list[dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        """Calculate consensus and revision metrics independently per item."""
        item_ids = [str(item["itemId"]) for item in items if item.get("itemId")]
        grouped: dict[str, dict[int, list[dict[str, Any]]]] = {
            item_id: defaultdict(list) for item_id in item_ids
        }
        for message in messages:
            item_id = message.get("itemId")
            rating = message.get("rating")
            round_index = message.get("roundIndex")
            if (
                item_id not in grouped
                or message.get("validStructuredResponse") is not True
                or not isinstance(rating, int)
                or isinstance(rating, bool)
                or not 1 <= rating <= 5
            ):
                continue
            if not isinstance(round_index, int) or round_index < 1:
                continue
            grouped[item_id][round_index].append(message)

        metrics: dict[str, dict[str, Any]] = {}
        for item_id, rounds in grouped.items():
            if not rounds:
                metrics[item_id] = self._empty_item_result()
                continue
            final_round = max(rounds)
            final_messages = rounds[final_round]
            ratings = [message["rating"] for message in final_messages]
            counts = Counter(ratings)
            total = len(ratings)
            mode_count = max(counts.values())
            metrics[item_id] = {
                "statement": next(
                    (item.get("statement", "") for item in items if item.get("itemId") == item_id),
                    "",
                ),
                "consensusLevel": mode_count / total,
                "disagreementLevel": 1 - (mode_count / total),
                "stabilityLevel": self._item_stability(rounds, final_round),
                "polarizationLevel": self._rating_polarization(ratings),
                "minorityRatings": sorted(rating for rating, count in counts.items() if count < mode_count),
                "ratingDistribution": dict(sorted(counts.items())),
                "initialResponses": len(rounds.get(min(rounds), [])),
                "finalResponses": len(final_messages),
                "changedCount": self._changed_count(rounds, final_round),
            }
        return metrics

    @staticmethod
    def position_distribution_by_round(messages: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
        """Count valid participant positions separately for each discussion round.

        Args:
            messages: Persisted messages to group by round and position.

        Returns:
            A mapping from round number to position counts.
        """
        counts_by_round: dict[int, Counter[str]] = defaultdict(Counter)
        for message in messages:
            position = message.get("position")
            round_index = message.get("roundIndex")
            if (
                message.get("role") == "participant"
                and position in _VALID_POSITIONS
                and isinstance(round_index, int)
                and round_index >= 1
            ):
                counts_by_round[round_index][position] += 1
        return {
            str(round_index): dict(sorted(counts.items()))
            for round_index, counts in sorted(counts_by_round.items())
        }

    @staticmethod
    def _item_stability(rounds: dict[int, list[dict[str, Any]]], final_round: int) -> float | None:
        initial_round = min(rounds)
        if final_round <= initial_round:
            return None
        initial = {message.get("personaId"): message.get("rating") for message in rounds[initial_round]}
        final = {message.get("personaId"): message.get("rating") for message in rounds[final_round]}
        comparable_ids = set(initial) & set(final)
        if not comparable_ids:
            return None
        return sum(initial[persona_id] == final[persona_id] for persona_id in comparable_ids) / len(comparable_ids)

    @staticmethod
    def _changed_count(rounds: dict[int, list[dict[str, Any]]], final_round: int) -> int:
        initial_round = min(rounds)
        if final_round <= initial_round:
            return 0
        initial = {message.get("personaId"): message.get("rating") for message in rounds[initial_round]}
        final = {message.get("personaId"): message.get("rating") for message in rounds[final_round]}
        return sum(
            1
            for persona_id in set(initial) & set(final)
            if initial[persona_id] != final[persona_id]
        )

    @staticmethod
    def _rating_polarization(ratings: list[int]) -> float | None:
        if len(ratings) < 2:
            return 0.0 if ratings else None
        return (max(ratings) - min(ratings)) / 4

    @staticmethod
    def _empty_item_result() -> dict[str, Any]:
        return {
            "consensusLevel": None,
            "disagreementLevel": None,
            "stabilityLevel": None,
            "polarizationLevel": None,
            "minorityRatings": [],
            "ratingDistribution": {},
            "initialResponses": 0,
            "finalResponses": 0,
            "changedCount": 0,
        }

    @staticmethod
    def _stability(responses_by_round: dict[int, list[dict[str, Any]]], final_round: int) -> float | None:
        if final_round <= 1:
            return None
        initial = {
            message.get("personaId"): message.get("position")
            for message in responses_by_round.get(1, [])
            if message.get("personaId")
        }
        final = {
            message.get("personaId"): message.get("position")
            for message in responses_by_round[final_round]
            if message.get("personaId")
        }
        comparable_ids = set(initial) & set(final)
        if not comparable_ids:
            return None
        unchanged = sum(initial[persona_id] == final[persona_id] for persona_id in comparable_ids)
        return unchanged / len(comparable_ids)

    @staticmethod
    def _polarization(counts: Counter[str], total: int) -> float | None:
        if total == 0:
            return None
        opposing = counts.get("support", 0) + counts.get("oppose", 0)
        if opposing < 2 or not counts.get("support") or not counts.get("oppose"):
            return 0.0
        return 2 * min(counts["support"], counts["oppose"]) / opposing

    @staticmethod
    def _empty_result() -> dict[str, Any]:
        return {
            "consensusLevel": None,
            "disagreementLevel": None,
            "stabilityLevel": None,
            "polarizationLevel": None,
            "minorityPositions": [],
        }
