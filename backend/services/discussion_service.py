from __future__ import annotations
"""Discussion application service.

This service is the orchestration facade between API routers and the core
discussion engine. It is responsible for lifecycle transitions, background
execution, and persistence updates.
"""

import logging
from datetime import datetime, timezone
from threading import Thread
from typing import Any, Callable
from uuid import uuid4

from backend.core.agent import ChatClient, PersonaAgent
from backend.core.discussion import DiscussionEngine, DiscussionTurn
from backend.models import DiscussionStartRequest
from backend.persistence.local_discussion_persistence import LocalDiscussionPersistence
from backend.persistence.local_persona_persistence import LocalPersonaPersistence
from backend.services.configuration_service import ConfigurationService
from backend.services.environment_service import EnvironmentService
from backend.services.result_service import ResultService
from backend.prompt_templates import IMPLEMENTED_STRATEGIES


logger = logging.getLogger(__name__)


class DiscussionService:
    """Facade for discussion lifecycle commands.

    Lifecycle states are updated in the persistence layer using these transitions:
    queued -> running -> completed | stopped | failed.
    """

    def __init__(
        self,
        discussion_persistence: LocalDiscussionPersistence | None = None,
        persona_persistence: LocalPersonaPersistence | None = None,
        configuration_service: ConfigurationService | None = None,
        environment_service: EnvironmentService | None = None,
        result_service: ResultService | None = None,
    ) -> None:
        """Create service with injectable persistence dependencies."""
        self.discussion_persistence = discussion_persistence or LocalDiscussionPersistence()
        self.persona_persistence = persona_persistence or LocalPersonaPersistence()
        self.configuration_service = configuration_service or ConfigurationService()
        self.environment_service = environment_service or EnvironmentService()
        self.result_service = result_service or ResultService(self.discussion_persistence)

    def start(self, request: DiscussionStartRequest) -> dict[str, Any]:
        """Create a discussion record and start background execution."""
        selected_personas = self._resolve_personas(request.personaIds)
        configuration = self._build_configuration(request)
        strategy_spec = self._resolve_strategy_specification(configuration, request.strategy)
        discussion_id = str(uuid4())
        discussion = {
            "discussionId": discussion_id,
            "status": "queued",
            "topic": request.topic.strip(),
            "strategy": request.strategy,
            "baseStrategy": strategy_spec["baseStrategy"],
            "personaIds": request.personaIds,
            "personas": selected_personas,
            "delphiItems": configuration.get("delphiItems", []),
            "configuration": configuration,
            "traceEnabled": request.traceEnabled,
            "trace": [],
            "messages": [],
            "summary": None,
            "result": None,
            "error": None,
            "stopRequested": False,
            "createdAt": self._timestamp(),
            "updatedAt": self._timestamp(),
        }
        self.discussion_persistence.create(discussion)
        worker = Thread(target=self._run, args=(discussion_id,), daemon=True)
        worker.start()
        return discussion

    def get(self, discussion_id: str) -> dict[str, Any] | None:
        """Return one discussion by id from persistence."""
        return self.discussion_persistence.load_by_id(discussion_id)

    def list(self) -> list[dict[str, Any]]:
        """List discussions sorted by newest creation timestamp first."""
        return sorted(
            self.discussion_persistence.load_all(),
            key=lambda item: item.get("createdAt", ""),
            reverse=True,
        )

    def stop(self, discussion_id: str) -> dict[str, Any] | None:
        """Request cooperative stop for queued or running discussions."""
        def request_stop(discussion: dict[str, Any]) -> None:
            if discussion["status"] in {"queued", "running"}:
                discussion["stopRequested"] = True
                discussion["updatedAt"] = self._timestamp()

        discussion = self.discussion_persistence.update_by_id(discussion_id, request_stop)
        if discussion is None:
            return None
        return discussion

    def delete(self, discussion_id: str) -> bool:
        """Delete a persisted discussion that is no longer running."""
        discussion = self.discussion_persistence.load_by_id(discussion_id)
        if discussion is None:
            return False
        if discussion.get("status") in {"queued", "running"}:
            raise ValueError("Running discussions cannot be deleted.")
        return self.discussion_persistence.delete_by_id(discussion_id)

    def _run(self, discussion_id: str) -> None:
        """Background worker entry point for one discussion execution.

        Steps:
        1. Mark discussion running.
        2. Build engine dependencies.
        3. Stream turns and persist incrementally.
        4. Finalize status and structured result.
        """
        discussion = self.discussion_persistence.load_by_id(discussion_id)
        if discussion is None:
            return

        try:
            self.discussion_persistence.update_by_id(discussion_id, lambda item: self._set_running(item))
            configuration = discussion["configuration"]
            trace_enabled = bool(discussion.get("traceEnabled"))
            trace_sequence = 0

            def append_trace(entry: dict[str, Any]) -> None:
                nonlocal trace_sequence
                trace_sequence += 1
                entry["sequence"] = trace_sequence
                self.discussion_persistence.update_by_id(
                    discussion_id,
                    lambda item: item.setdefault("trace", []).append(entry),
                )
            personas = [
                PersonaAgent(
                    persona_id=persona["personaId"],
                    name=persona["name"],
                    role=persona.get("role") or "",
                    description=persona.get("description") or persona.get("systemPrompt") or "",
                    background=persona.get("background") or "",
                    expertise=tuple(persona.get("expertise") or []),
                    goals=tuple(persona.get("goals") or []),
                    constraints=tuple(persona.get("constraints") or []),
                    communication_style=persona.get("communicationStyle") or "",
                )
                for persona in discussion["personas"]
            ]
            client = ChatClient(
                model=configuration["runtimeModel"],
                temperature=configuration["temperature"],
                token_limit=configuration["tokenLimit"],
                trace_sink=append_trace if trace_enabled else None,
            )
            strategy_spec = self._resolve_strategy_specification(configuration, discussion["strategy"])
            base_strategy = strategy_spec["baseStrategy"]
            base_behavior = IMPLEMENTED_STRATEGIES[base_strategy]
            isolated_rounds = configuration.get("isolatedRounds", strategy_spec.get("isolatedRounds", 0))
            peer_visibility = strategy_spec.get("peerVisibility", "named")
            engine = DiscussionEngine(
                topic=discussion["topic"],
                personas=personas,
                strategy=discussion["strategy"],
                base_strategy=base_strategy,
                max_rounds=configuration["maxRounds"],
                client=client,
                global_prompt_templates=(configuration.get("promptTemplates") or {}).get("global"),
                strategy_prompt_templates=strategy_spec.get("promptTemplates", {}),
                round_plan=configuration.get("roundPlan", {}),
                delphi_round_plan=configuration.get("delphiRoundPlan", {}),
                isolated_rounds=isolated_rounds,
                peer_visibility=peer_visibility,
                use_moderator_selection=bool(base_behavior.get("useModeratorSelection")),
                should_stop=lambda: self._stop_requested(discussion_id),
                trace_sink=append_trace if trace_enabled else None,
                delphi_items=discussion.get("delphiItems", []),
            )

            for turn in engine.run():
                current = self.discussion_persistence.load_by_id(discussion_id)
                if current is None or current.get("stopRequested"):
                    self._mark_stopped(discussion_id)
                    self._persist_result(discussion_id, append_trace if trace_enabled else None)
                    return
                self._append_turn(discussion_id, turn)

            self.discussion_persistence.update_by_id(discussion_id, lambda item: self._mark_completed(item))
            self._persist_result(discussion_id, append_trace if trace_enabled else None)
        except Exception as error:
            logger.exception("Discussion %s failed during background execution.", discussion_id)
            self.discussion_persistence.update_by_id(
                discussion_id,
                lambda item: self._mark_failed(item, str(error)),
            )

    def _resolve_personas(self, persona_ids: list[str]) -> list[dict[str, Any]]:
        """Resolve and validate selected persona IDs against the configured catalog."""
        personas_by_id = {
            persona.get("personaId"): persona
            for persona in self.persona_persistence.load_all()
        }
        missing_ids = [persona_id for persona_id in persona_ids if persona_id not in personas_by_id]
        if missing_ids:
            raise ValueError(f"Unknown persona IDs: {', '.join(missing_ids)}")
        return [personas_by_id[persona_id] for persona_id in persona_ids]

    def _append_turn(self, discussion_id: str, turn: DiscussionTurn) -> None:
        """Persist one emitted engine turn as an API-facing discussion message."""
        def append(discussion: dict[str, Any]) -> None:
            revised_from = turn.revised_from
            if turn.revised and turn.item_id:
                previous = next(
                    (
                        message
                        for message in reversed(discussion.get("messages", []))
                        if message.get("role") == "participant"
                        and message.get("personaId") == turn.persona_id
                        and message.get("itemId") == turn.item_id
                    ),
                    None,
                )
                revised_from = previous.get("messageId") if previous else None
            message = {
                "messageId": str(uuid4()),
                "roundIndex": turn.round_index,
                "personaId": turn.persona_id,
                "personaName": turn.persona_name,
                "role": turn.role,
                "content": turn.content,
                "contributionType": turn.contribution_type,
                "position": turn.position,
                "confidence": turn.confidence,
                "respondsTo": list(turn.responds_to),
                "revisedFrom": revised_from,
                "phase": turn.phase,
                "itemId": turn.item_id,
                "itemStatement": next(
                    (
                        item.get("statement")
                        for item in discussion.get("delphiItems", [])
                        if item.get("itemId") == turn.item_id
                    ),
                    None,
                ),
                "rating": turn.rating,
                "revised": turn.revised,
                "validStructuredResponse": turn.valid_structured_response,
            }
            discussion["messages"].append(message)
            if turn.role == "summary":
                discussion["summary"] = turn.content
            discussion["updatedAt"] = self._timestamp()

        self.discussion_persistence.update_by_id(discussion_id, append)

    def _persist_result(
        self,
        discussion_id: str,
        trace_sink: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        """Persist the result and, when enabled, append Delphi metrics to the trace."""
        discussion = self.discussion_persistence.load_by_id(discussion_id)
        if discussion is None:
            return
        result = self.result_service.build_result(discussion)

        def set_result(item: dict[str, Any]) -> None:
            item["result"] = result
            item["updatedAt"] = self._timestamp()

        self.discussion_persistence.update_by_id(discussion_id, set_result)

        if trace_sink is None or discussion.get("strategy") != "delphi":
            return
        trace_sink({
            "traceId": str(uuid4()),
            "callType": "analysis",
            "personaName": "DelphiAnalyzer",
            "status": "completed",
            "analysisBasis": {
                "participantResponses": sum(
                    message.get("role") == "participant"
                    for message in discussion.get("messages", [])
                ),
                "configuredItemIds": [
                    str(item["itemId"])
                    for item in discussion.get("delphiItems", [])
                    if item.get("itemId")
                ],
                "positionCountsByRound": self.result_service.delphi_analyzer.position_distribution_by_round(
                    discussion.get("messages", [])
                ),
            },
            "analysisOutput": {
                "positions": {
                    "consensusLevel": result.get("consensusLevel"),
                    "disagreementLevel": result.get("disagreementLevel"),
                    "stabilityLevel": result.get("stabilityLevel"),
                    "polarizationLevel": result.get("polarizationLevel"),
                    "minorityPositions": result.get("minorityPositions", []),
                },
                "items": result.get("itemMetrics", {}),
            },
        })

    def _build_configuration(self, request: DiscussionStartRequest) -> dict[str, Any]:
        """Merge request-specific options over persisted defaults and runtime environment."""
        defaults = self.configuration_service.get()
        environment_model = self.environment_service.get().get("OPENAI_MODEL", "").strip()
        defaults["runtimeModel"] = environment_model or defaults.get("model", "gpt-4.1-mini")
        defaults["temperature"] = request.temperature
        defaults["maxRounds"] = request.maxRounds
        defaults["tokenLimit"] = request.tokenLimit
        defaults["roundPlan"] = dict(request.roundPlan or {})
        if request.delphiItems is None:
            defaults["delphiItems"] = [
                item
                for item in defaults.get("delphiItems", [])
                if item.get("status", "active") == "active"
            ]
        else:
            defaults["delphiItems"] = [item.model_dump() for item in request.delphiItems]
        if request.delphiRoundPlan is not None:
            defaults["delphiRoundPlan"] = {
                round_index: round_config.model_dump()
                for round_index, round_config in request.delphiRoundPlan.items()
            }
        if request.isolatedRounds is not None:
            defaults["isolatedRounds"] = request.isolatedRounds
        return defaults

    @staticmethod
    def _resolve_strategy_specification(configuration: dict[str, Any], strategy_key: str) -> dict[str, Any]:
        specifications = configuration.get("strategySpecifications", [])
        selected = next(
            (
                item
                for item in specifications
                if isinstance(item, dict) and item.get("strategyKey") == strategy_key
            ),
            None,
        )
        if selected is None:
            raise ValueError(f"Unknown strategy '{strategy_key}'.")

        base_strategy = selected.get("baseStrategy")
        if base_strategy not in IMPLEMENTED_STRATEGIES:
            raise ValueError(
                f"Strategy '{strategy_key}' references unknown base strategy '{base_strategy}'."
            )
        return selected

    def _stop_requested(self, discussion_id: str) -> bool:
        """Check whether discussion should stop cooperatively."""
        discussion = self.discussion_persistence.load_by_id(discussion_id)
        return discussion is None or bool(discussion.get("stopRequested"))

    def _set_running(self, discussion: dict[str, Any]) -> None:
        """Transition to running unless a stop was already requested."""
        if discussion.get("stopRequested"):
            discussion["status"] = "stopped"
        else:
            discussion["status"] = "running"
        discussion["updatedAt"] = self._timestamp()

    def _mark_stopped(self, discussion_id: str) -> None:
        """Apply stopped transition by discussion id."""
        self.discussion_persistence.update_by_id(discussion_id, lambda item: self._set_stopped(item))

    def _set_stopped(self, discussion: dict[str, Any]) -> None:
        """Transition to stopped and update modification timestamp."""
        discussion["status"] = "stopped"
        discussion["updatedAt"] = self._timestamp()

    def _mark_completed(self, discussion: dict[str, Any]) -> None:
        """Transition to completed unless stop was requested concurrently."""
        if discussion.get("stopRequested"):
            discussion["status"] = "stopped"
        else:
            discussion["status"] = "completed"
        discussion["updatedAt"] = self._timestamp()

    def _mark_failed(self, discussion: dict[str, Any], error: str) -> None:
        """Transition to failed and persist the surfaced error message."""
        discussion["status"] = "failed"
        discussion["error"] = error
        discussion["updatedAt"] = self._timestamp()

    @staticmethod
    def _timestamp() -> str:
        """Return an RFC 3339 compatible UTC timestamp string."""
        return datetime.now(timezone.utc).isoformat()
