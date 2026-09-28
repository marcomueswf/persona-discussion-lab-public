from __future__ import annotations
"""Result projection service.

Builds API-facing result views from persisted discussion records. When an
explicit result snapshot is absent, it derives a fallback heuristic view.
"""

from typing import Any

from backend.models import DiscussionResult
from backend.persistence.local_discussion_persistence import LocalDiscussionPersistence
from backend.services.delphi_analyzer import DelphiAnalyzer


class ResultService:
    """Creates or retrieves structured discussion result projections."""

    def __init__(self, persistence: LocalDiscussionPersistence | None = None) -> None:
        self.persistence = persistence or LocalDiscussionPersistence()
        self.delphi_analyzer = DelphiAnalyzer()

    def get_for_discussion(self, discussion_id: str) -> dict[str, Any] | None:
        """Return result projection for one discussion id."""
        discussion = self.persistence.load_by_id(discussion_id)
        if discussion is None:
            return None
        return self.build_result(discussion)

    def build_result(self, discussion: dict[str, Any]) -> dict[str, Any]:
        """Build a ``DiscussionResult`` snapshot from a persistence payload.

        Fallback behavior (when ``discussion['result']`` is missing) uses
        existing summary and latest participant contributions as heuristic
        placeholders for consensus/disagreement fields.
        """
        result_payload = discussion.get("result")
        if isinstance(result_payload, dict):
            return DiscussionResult(**result_payload).model_dump()

        summary = discussion.get("summary")
        participant_messages = [
            message
            for message in discussion.get("messages", [])
            if message.get("role") == "participant"
        ]

        is_delphi = discussion.get("strategy") == "delphi"
        metrics = self.delphi_analyzer.analyze(participant_messages) if is_delphi else {}
        item_metrics = (
            self.delphi_analyzer.analyze_items(participant_messages, discussion.get("delphiItems", []))
            if is_delphi
            else {}
        )

        recommendations: list[str] = []
        if summary:
            recommendations.append(summary)

        minority_positions = set(metrics.get("minorityPositions", []))
        disagreements = [
            message.get("content", "")
            for message in participant_messages
            if message.get("content") and (
                not minority_positions or message.get("position") in minority_positions
            )
        ][-3:]

        result = DiscussionResult(
            summary=summary,
            consensus=summary,
            disagreements=disagreements,
            recommendations=recommendations,
            consensusLevel=metrics.get("consensusLevel"),
            stabilityLevel=metrics.get("stabilityLevel"),
            disagreementLevel=metrics.get("disagreementLevel"),
            polarizationLevel=metrics.get("polarizationLevel"),
            minorityPositions=metrics.get("minorityPositions", []),
            terminationReason=discussion.get("terminationReason"),
            itemMetrics=item_metrics,
        )
        return result.model_dump()
