from __future__ import annotations
"""LangGraph-based discussion orchestration.

This module contains the core orchestration engine for multi-persona discussions.
It models the discussion as a stateful graph where each node updates a shared
state object and routing functions decide the next node.
"""

from dataclasses import dataclass
import json
import logging
from typing import Callable, Iterator, TypedDict
from typing import Any

from langgraph.graph import END, START, StateGraph

from backend.core.agent import ChatClient, PersonaAgent
from backend.services.prompt_service import PromptService


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class DiscussionTurn:
    """Canonical domain event emitted by the discussion engine.

    Args:
        round_index: One-based discussion round containing this event.
        persona_id: Identifier of the persona associated with the event.
        persona_name: Display name of the persona.
        role: Role of the speaker, such as persona or moderator.
        content: Text content of the event.
        contribution_type: Kind of contribution represented by the event.
        position: Optional stance expressed in the contribution.
        confidence: Optional confidence in the expressed position, from 0 to 1.
        responds_to: Identifiers of earlier contributions being answered.
        revised_from: Identifier of the contribution this event revises.
        phase: Discussion phase in which the event was emitted.
        item_id: Optional identifier of a Delphi item.
        rating: Optional Delphi rating, from 1 to 5.
        revised: Whether the rating or position was revised.
        valid_structured_response: Whether structured response validation passed.
    """

    round_index: int
    persona_id: str
    persona_name: str
    role: str
    content: str
    contribution_type: str = "contribution"
    position: str | None = None
    confidence: float | None = None
    responds_to: tuple[str, ...] = ()
    revised_from: str | None = None
    phase: str = "discussion"
    item_id: str | None = None
    rating: int | None = None
    revised: bool | None = None
    valid_structured_response: bool = False


class DiscussionState(TypedDict):
    """Runtime state shared between LangGraph nodes.

    Fields represent orchestration state, not persistence DTOs.
    - remaining_persona_ids tracks which personas still need a turn in a round.
    - selected_persona_id is set by selection and consumed by persona_turn.
    - termination_reason controls final graph routing to END.
    """

    topic: str
    strategy: str
    messages: list[DiscussionTurn]
    round_index: int
    remaining_persona_ids: list[str]
    selected_persona_id: str | None
    current_thesis: str
    moderator_instruction: str
    final_summary: str
    termination_reason: str | None
    delphi_items: list[dict[str, Any]]
    delphi_round_plan: dict[int, dict[str, Any]]


class DiscussionEngine:
    """Graph orchestrator for one discussion execution.

    The engine compiles its graph once during construction and emits
    ``DiscussionTurn`` events while ``run`` iterates over streamed graph values.
    Persona turns are generated in round order unless moderator selection is
    enabled. Delphi discussions can instead generate a separate turn for each
    configured item and apply a per-round item/mode plan.
    """

    def __init__(
        self,
        topic: str,
        personas: list[PersonaAgent],
        strategy: str,
        max_rounds: int,
        client: ChatClient,
        base_strategy: str | None = None,
        global_prompt_templates: dict[str, str] | None = None,
        strategy_prompt_templates: dict[str, str] | None = None,
        round_plan: dict[str, str] | None = None,
        isolated_rounds: int = 0,
        peer_visibility: str = "named",
        use_moderator_selection: bool = False,
        should_stop: Callable[[], bool] | None = None,
        trace_sink: Callable[[dict[str, Any]], None] | None = None,
        delphi_items: list[dict[str, Any]] | None = None,
        delphi_round_plan: dict[int, dict[str, Any]] | None = None,
    ) -> None:
        """Create a discussion engine with strategy-specific routing behavior.

        Args:
            topic: Question or subject discussed by the personas.
            personas: Participants; at least two are required and their IDs
                should be unique.
            strategy: Active strategy label passed to prompts.
            max_rounds: Maximum number of discussion rounds.
            client: Chat completion client used for all generated text.
            base_strategy: Strategy used for orchestration rules. Defaults to
                ``strategy``; useful when ``strategy`` is a configured variant.
            global_prompt_templates: Optional global prompt-template overrides.
            strategy_prompt_templates: Optional strategy-specific prompt
                template overrides.
            round_plan: Optional round-specific participant instruction plan.
            isolated_rounds: Number of initial non-Delphi rounds in which each
                persona sees no peer contributions. Negative values become 0.
            peer_visibility: Whether peer contributions are rendered with
                persona names (``"named"``) or stable expert labels
                (``"anonymous"``). Other values raise ``ValueError``.
            use_moderator_selection: If true, ask the model to choose among
                remaining personas; an unrecognized choice falls back to the
                first eligible persona.
            should_stop: Optional predicate checked before moderator work and
                after each persona contribution. Returning true stops the run.
            trace_sink: Enables trace-aware completion calls when provided.
                The client is responsible for delivering trace records.
            delphi_items: Optional item dictionaries used to create separate
                Delphi contributions. Non-dictionary entries are ignored.
            delphi_round_plan: Optional mapping of one-based round numbers to
                Delphi mode/item configuration. Model-like configs are
                normalized with ``model_dump`` when available.
        """
        if len(personas) < 2:
            raise ValueError("At least two personas are required.")
        self.topic = topic
        self.personas = personas
        self.personas_by_id = {persona.persona_id: persona for persona in personas}
        self.strategy = strategy
        self.base_strategy = base_strategy or strategy
        self.isolated_rounds = max(0, isolated_rounds)
        if peer_visibility not in {"named", "anonymous"}:
            raise ValueError("peer_visibility must be 'named' or 'anonymous'.")
        self.peer_visibility = peer_visibility
        self.use_moderator_selection = use_moderator_selection
        self.max_rounds = max_rounds
        self.client = client
        self.should_stop = should_stop or (lambda: False)
        self.trace_sink = trace_sink
        self.delphi_items = [item for item in (delphi_items or []) if isinstance(item, dict)]
        self.delphi_round_plan = {
            int(round_index): config.model_dump() if hasattr(config, "model_dump") else dict(config)
            for round_index, config in (delphi_round_plan or {}).items()
        }
        self.prompt_service = PromptService(global_prompt_templates, strategy_prompt_templates, round_plan)
        self.graph = self._build_graph()

    def run(self) -> Iterator[DiscussionTurn]:
        """Execute the graph and stream newly appended discussion turns.

        The method consumes LangGraph ``stream_mode='values'`` updates and yields
        only turns that were not emitted previously, including the final summary
        as a ``DiscussionTurn``. The recursion limit scales with the number of
        rounds and personas, with a minimum of 100 graph steps.
        """
        initial_state: DiscussionState = {
            "topic": self.topic,
            "strategy": self.strategy,
            "messages": [],
            "round_index": 1,
            "remaining_persona_ids": [persona.persona_id for persona in self.personas],
            "selected_persona_id": None,
            "current_thesis": "",
            "moderator_instruction": "",
            "final_summary": "",
            "termination_reason": None,
            "delphi_items": self.delphi_items,
            "delphi_round_plan": self.delphi_round_plan,
        }
        emitted_messages = 0
        recursion_limit = max(100, self.max_rounds * (len(self.personas) * 3 + 5) + 5)
        for update in self.graph.stream(
            initial_state,
            {"recursion_limit": recursion_limit},
            stream_mode="values",
        ):
            messages = update["messages"]
            while emitted_messages < len(messages):
                yield messages[emitted_messages]
                emitted_messages += 1

    def _build_graph(self):
        """Build and compile the LangGraph workflow.

        Graph shape:
        START -> moderator -> select_persona -> persona_turn -> evaluate
                               |                         |
                               +------> summary <--------+
        summary -> termination -> moderator | END

        An empty persona selection or a stop reason routes to summary. After a
        round summary, termination either ends the graph or resets the eligible
        persona list and starts the next round.
        """
        graph = StateGraph(DiscussionState)
        graph.add_node("moderator", self._moderator_node)
        graph.add_node("select_persona", self._select_persona_node)
        graph.add_node("persona_turn", self._persona_turn_node)
        graph.add_node("evaluate", self._evaluate_node)
        graph.add_node("summary", self._summary_node)
        graph.add_node("termination", self._termination_node)
        graph.add_edge(START, "moderator")
        graph.add_edge("moderator", "select_persona")
        graph.add_conditional_edges(
            "select_persona",
            self._route_after_selection,
            {"persona_turn": "persona_turn", "summary": "summary"},
        )
        graph.add_edge("persona_turn", "evaluate")
        graph.add_conditional_edges(
            "evaluate",
            self._route_after_evaluation,
            {"select_persona": "select_persona", "summary": "summary"},
        )
        graph.add_edge("summary", "termination")
        graph.add_conditional_edges(
            "termination",
            self._route_after_termination,
            {"moderator": "moderator", "end": END},
        )
        compiled_graph = graph.compile()
        return compiled_graph

    def _moderator_node(self, state: DiscussionState) -> dict:
        """Set moderator guidance for the current round.

        Returns a partial state update with ``moderator_instruction`` and can
        also short-circuit by setting ``termination_reason`` when stop is
        requested. Without moderator selection, guidance comes directly from
        the prompt service; otherwise it is generated from the current thesis
        and transcript context.
        """
        if self.should_stop():
            return {"termination_reason": "stopped by user"}
        if not self.use_moderator_selection:
            return {"moderator_instruction": self.prompt_service.moderator_instruction()}
        instruction = self._complete(
            "moderator",
            self.prompt_service.moderator_system_prompt(),
            self.prompt_service.moderator_user_prompt(
                state["topic"],
                state["current_thesis"],
                self._context(state["messages"]),
            ),
            round_index=state["round_index"],
        )
        return {"moderator_instruction": instruction}

    def _select_persona_node(self, state: DiscussionState) -> dict:
        """Pick the next eligible persona for this round.

        Selection is deterministic (the first remaining persona) by default.
        When model selection is enabled, the first eligible name found in the
        response is used; unrecognized responses retain the deterministic
        fallback. No persona is selected after termination or when the round is
        complete.
        """
        remaining = state["remaining_persona_ids"]
        if not remaining or state["termination_reason"]:
            return {"selected_persona_id": None}
        selected_id = remaining[0]
        if self.use_moderator_selection:
            selection = self._complete(
                "selection",
                self.prompt_service.selection_system_prompt(),
                self.prompt_service.selection_user_prompt(
                    state["topic"],
                    state["moderator_instruction"],
                    [self.personas_by_id[item].name for item in remaining],
                ),
                round_index=state["round_index"],
            )
            selected_id = next(
                (item for item in remaining if self.personas_by_id[item].name.lower() in selection.lower()),
                remaining[0],
            )
        return {"selected_persona_id": selected_id}

    def _persona_turn_node(self, state: DiscussionState) -> dict:
        """Generate a participant contribution and update round state.

        Delphi rounds with configured items and a supported mode delegate to
        ``_delphi_persona_turns``. Other rounds create one general contribution;
        structured position/confidence metadata is extracted when present, but
        invalid or absent metadata does not invalidate the text contribution.
        """
        persona_id = state["selected_persona_id"]
        if persona_id is None:
            return {}
        round_config = state["delphi_round_plan"].get(state["round_index"])
        if self.base_strategy == "delphi" and state["delphi_items"]:
            mode = round_config.get("mode") if round_config else None
            if mode in {"rate", "discuss", "most_disputed"} or mode is None:
                return self._delphi_persona_turns(state, persona_id, round_config)
        persona = self.personas_by_id[persona_id]
        context = self._context(
            state["messages"],
            state["round_index"],
            anonymize=self.peer_visibility == "anonymous",
        )
        strategy_instruction = self.prompt_service.participant_instruction(state["round_index"])
        if self.base_strategy == "delphi":
            strategy_instruction = (
                f"{strategy_instruction}\n"
                f"{self.prompt_service.delphi_phase_instruction(state['round_index'])}"
            )
        system_prompt = self.prompt_service.participant_system_prompt(
            persona.name,
            persona.role,
            persona.description,
            persona.background,
            persona.expertise,
            persona.goals,
            persona.constraints,
            persona.communication_style,
        )
        user_prompt = self.prompt_service.participant_user_prompt(
            topic=state["topic"],
            round_index=state["round_index"],
            strategy=state["strategy"],
            strategy_instruction=strategy_instruction,
            moderator_instruction=state["moderator_instruction"],
            context=context,
        )
        response = self._complete(
            "participant",
            system_prompt,
            user_prompt,
            round_index=state["round_index"],
            persona_id=persona.persona_id,
            persona_name=persona.name,
        )
        position, confidence = self._extract_structured_position(response)
        turn = DiscussionTurn(
            round_index=state["round_index"],
            persona_id=persona.persona_id,
            persona_name=persona.name,
            role="participant",
            content=response,
            contribution_type="initial_position" if state["round_index"] == 1 else "contribution",
            position=position,
            confidence=confidence,
            phase=self._phase_for_round(state["round_index"]),
        )
        return {
            "messages": [*state["messages"], turn],
            "remaining_persona_ids": [item for item in state["remaining_persona_ids"] if item != persona_id],
            "selected_persona_id": None,
        }

    def _delphi_persona_turns(
        self,
        state: DiscussionState,
        persona_id: str,
        round_config: dict[str, Any] | None = None,
    ) -> dict:
        """Generate one independently recorded turn for each selected item.

        Args:
            state: Current discussion state.
            persona_id: ID of the selected participant.
            round_config: Optional mode/item configuration for this round.

        The mode defaults to ``rate`` in rounds 1-2 and ``discuss`` afterwards.
        Ratings are required only in ``rate`` mode. For later ratings, the
        ``revised`` flag is derived by comparing with that persona's most recent
        turn for the same item; in other cases the validated model flag is used.
        All item turns are appended together and the persona is then removed
        from the round's remaining participants.
        """
        persona = self.personas_by_id[persona_id]
        turns: list[DiscussionTurn] = []
        items = self._items_for_round(state, round_config)
        mode = (round_config or {}).get("mode") or ("rate" if state["round_index"] <= 2 else "discuss")
        for item in items:
            item_id = str(item["itemId"])
            item_statement = str(item["statement"])
            context = self._context(
                state["messages"],
                state["round_index"],
                anonymize=self.peer_visibility == "anonymous",
                item_id=item_id,
            )
            strategy_instruction = self.prompt_service.participant_instruction(state["round_index"])
            strategy_instruction = (
                f"{strategy_instruction}\n"
                f"{self.prompt_service.delphi_phase_instruction(state['round_index'])}"
            )
            system_prompt = self.prompt_service.participant_system_prompt(
                persona.name,
                persona.role,
                persona.description,
                persona.background,
                persona.expertise,
                persona.goals,
                persona.constraints,
                persona.communication_style,
            )
            user_prompt = self.prompt_service.participant_user_prompt(
                topic=state["topic"],
                round_index=state["round_index"],
                strategy=state["strategy"],
                strategy_instruction=strategy_instruction,
                moderator_instruction=state["moderator_instruction"],
                context=context,
                item_id=item_id,
                item_statement=item_statement,
                item_mode=mode,
            )
            response = self._complete(
                "participant",
                system_prompt,
                user_prompt,
                round_index=state["round_index"],
                persona_id=persona.persona_id,
                persona_name=persona.name,
            )
            position, confidence, rating, revised, valid = self._extract_structured_item_response(
                response,
                rating_required=mode == "rate",
            )
            previous = next(
                (
                    turn
                    for turn in reversed(state["messages"])
                    if turn.role == "participant"
                    and turn.persona_id == persona_id
                    and turn.item_id == item_id
                ),
                None,
            )
            did_revise = mode == "rate" and previous is not None and previous.rating != rating
            turns.append(
                DiscussionTurn(
                    round_index=state["round_index"],
                    persona_id=persona.persona_id,
                    persona_name=persona.name,
                    role="participant",
                    content=response,
                    contribution_type="initial_position" if state["round_index"] == 1 else "revision",
                    position=position,
                    confidence=confidence,
                    revised_from=None,
                    phase=self._phase_for_round(state["round_index"]),
                    item_id=item_id,
                    rating=rating,
                    revised=did_revise if mode == "rate" and previous is not None else revised,
                    valid_structured_response=valid,
                )
            )
        return {
            "messages": [*state["messages"], *turns],
            "remaining_persona_ids": [item for item in state["remaining_persona_ids"] if item != persona_id],
            "selected_persona_id": None,
        }

    @staticmethod
    def _items_for_round(
        state: DiscussionState,
        round_config: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Resolve the items eligible for a round.

        Args:
            state: Current discussion state, including prior item ratings.
            round_config: Optional mode and item-ID filter for this round.

        ``rate`` and ``discuss`` modes use the configured ``itemIds``. A
        ``most_disputed`` round uses its explicit IDs, or considers all items
        when none are supplied, then selects every item tied for the largest
        rating spread in the immediately preceding round. If no prior ratings
        exist, it leaves the candidate set unchanged. Without an explicit
        round plan, the legacy behavior focuses round 3 on the largest spread.
        """
        items = state["delphi_items"]
        if round_config is not None:
            item_ids = round_config.get("itemIds", [])
            if round_config.get("mode") == "most_disputed" and not item_ids:
                item_ids = [item.get("itemId") for item in items]
            if round_config.get("mode") in {"rate", "discuss"} or item_ids:
                items = [item for item in items if item.get("itemId") in item_ids]
            if round_config.get("mode") != "most_disputed":
                return items
        elif state["round_index"] != 3:
            return items
        spreads: list[tuple[int, dict[str, Any]]] = []
        for item in items:
            ratings = [
                turn.rating
                for turn in state["messages"]
                if turn.round_index == state["round_index"] - 1
                and turn.item_id == item.get("itemId")
                and turn.rating is not None
            ]
            if ratings:
                spreads.append((max(ratings) - min(ratings), item))
        if not spreads:
            return items
        largest_spread = max(spread for spread, _ in spreads)
        return [item for spread, item in spreads if spread == largest_spread]

    def _evaluate_node(self, state: DiscussionState) -> dict:
        """Check whether a stop was requested after a participant contribution.

        A positive stop predicate sets the termination reason; graph routing
        then proceeds through summary, whose stop-specific branch avoids making
        another model call.
        """
        if self.should_stop():
            return {"termination_reason": "stopped by user"}
        return {}

    def _summary_node(self, state: DiscussionState) -> dict:
        """Summarize the current round and, on the last round, the whole discussion.

        A user stop skips summary generation. Before the final round, only the
        round thesis is updated; on the final round, a summary turn is appended
        and the termination reason becomes ``"completed"``.
        """
        if state["termination_reason"] == "stopped by user":
            return {}
        round_messages = [turn for turn in state["messages"] if turn.round_index == state["round_index"]]
        round_summary = self._complete(
            "round_summary",
            self.prompt_service.round_summary_system_prompt(),
            self.prompt_service.round_summary_user_prompt(state["topic"], self._context(round_messages)),
            round_index=state["round_index"],
        )
        if state["round_index"] < self.max_rounds:
            return {"current_thesis": round_summary}
        final_summary = self._complete(
            "final_summary",
            self.prompt_service.final_summary_system_prompt(),
            self.prompt_service.final_summary_user_prompt(
                state["topic"],
                round_summary,
                self._context(state["messages"]),
            ),
            round_index=state["round_index"],
        )
        summary_turn = DiscussionTurn(
            round_index=state["round_index"] + 1,
            persona_id="summary",
            persona_name="Discussion summary",
            role="summary",
            content=final_summary,
            contribution_type="summary",
        )
        return {
            "current_thesis": round_summary,
            "final_summary": final_summary,
            "messages": [*state["messages"], summary_turn],
            "termination_reason": "completed",
        }

    def _complete(
        self,
        call_type: str,
        system_prompt: str,
        user_prompt: str,
        round_index: int | None = None,
        persona_id: str | None = None,
        persona_name: str | None = None,
    ) -> str:
        """Complete a prompt, attaching call metadata when tracing is enabled.

        Trace metadata identifies the call type, round, and optional persona.
        It is passed to the client only when ``trace_sink`` was configured;
        the sink itself is invoked by the trace-aware client.
        """
        if self.trace_sink is None:
            return self.client.complete(system_prompt, user_prompt)
        return self.client.complete(
            system_prompt,
            user_prompt,
            trace_context={
                "callType": call_type,
                "roundIndex": round_index,
                "personaId": persona_id,
                "personaName": persona_name,
            },
        )

    def _termination_node(self, state: DiscussionState) -> dict:
        """Advance to the next round or preserve an existing stop reason.

        If no stop reason exists and the maximum has not been reached, the
        round index is incremented and every persona becomes eligible again.
        Otherwise state is left unchanged or marked as having reached the limit.
        """
        if state["termination_reason"]:
            return {}
        if state["round_index"] >= self.max_rounds:
            return {"termination_reason": "maximum rounds reached"}
        return {
            "round_index": state["round_index"] + 1,
            "remaining_persona_ids": [persona.persona_id for persona in self.personas],
        }

    @staticmethod
    def _route_after_selection(state: DiscussionState) -> str:
        """Route to persona generation when a persona was selected."""
        return "persona_turn" if state["selected_persona_id"] else "summary"

    @staticmethod
    def _route_after_evaluation(state: DiscussionState) -> str:
        """Route to next persona in round, otherwise to round summary."""
        return "select_persona" if state["remaining_persona_ids"] and not state["termination_reason"] else "summary"

    @staticmethod
    def _route_after_termination(state: DiscussionState) -> str:
        """Route to END when termination is set, otherwise start next round."""
        return "end" if state["termination_reason"] else "moderator"

    @staticmethod
    def _phase_for_round(round_index: int) -> str:
        """Map Delphi rounds to the study's three conceptual phases."""
        if round_index == 1:
            return "elicitation"
        if round_index == 2:
            return "feedback"
        if round_index == 3:
            return "expert_discussion"
        return "discussion"

    @staticmethod
    def _extract_structured_position(response: str) -> tuple[str | None, float | None]:
        """Extract a recognized position object embedded in a response.

        Args:
            response: Model response that may contain prose around JSON.

        The first object with an allowed position is used. Its confidence is
        returned only when numeric and within [0, 1]; an invalid confidence
        does not discard the position. No stance is inferred from prose.
        """
        decoder = json.JSONDecoder()
        for index, character in enumerate(response):
            if character != "{":
                continue
            try:
                payload, _ = decoder.raw_decode(response[index:])
            except json.JSONDecodeError:
                continue
            position = payload.get("position") if isinstance(payload, dict) else None
            confidence = payload.get("confidence") if isinstance(payload, dict) else None
            if position not in {"support", "oppose", "mixed", "undecided"}:
                continue
            if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
                return position, None
            if 0 <= confidence <= 1:
                return position, float(confidence)
        return None, None

    @staticmethod
    def _extract_structured_item_response(
        response: str,
        rating_required: bool,
    ) -> tuple[str | None, float | None, int | None, bool | None, bool]:
        """Extract a fully valid structured response for one Delphi item.

        Args:
            response: Model response that may contain prose around JSON.
            rating_required: Whether this response must include a rating from
                1 to 5.

        A valid object must include an allowed position, numeric confidence in
        [0, 1], and a boolean ``revised`` value. If a rating is not required, it
        must be absent or null. Booleans are not accepted as numeric ratings or
        confidence values. The last valid object in the response is returned;
        if none passes, all fields are ``None`` and the validity flag is false.
        """
        decoder = json.JSONDecoder()
        parsed_response = None
        for index, character in enumerate(response):
            if character != "{":
                continue
            try:
                payload, _ = decoder.raw_decode(response[index:])
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            position = payload.get("position")
            confidence = payload.get("confidence")
            rating = payload.get("rating")
            revised = payload.get("revised")
            if position not in {"support", "oppose", "mixed", "undecided"}:
                continue
            if not isinstance(confidence, (int, float)) or isinstance(confidence, bool) or not 0 <= confidence <= 1:
                continue
            if not isinstance(revised, bool):
                continue
            if rating_required:
                if not isinstance(rating, int) or isinstance(rating, bool) or not 1 <= rating <= 5:
                    continue
            elif rating is not None:
                continue
            parsed_response = (position, float(confidence), rating, revised, True)
        return parsed_response or (None, None, None, None, False)

    def _context(
        self,
        transcript: list[DiscussionTurn],
        round_index: int | None = None,
        anonymize: bool = False,
        item_id: str | None = None,
    ) -> str:
        """Render transcript context for LLM prompts.

        Args:
            transcript: Turns available to render.
            round_index: Current one-based round, used to select prior context.
            anonymize: Replace persona names with stable expert labels.
            item_id: Restrict context to this Delphi item when available.

        For non-Delphi strategies, ``isolated_rounds`` hides all peer context in
        the configured initial rounds. Delphi rounds after the first include
        only the immediately preceding round. An item-specific request filters
        that context to the same item; in round 2, if no item turns exist, it
        falls back to prior open participant responses and notes that those
        responses have no item ratings. Other empty contexts return a no-data
        message (or anonymous structured feedback for Delphi round 2).

        When ``anonymize`` is true, each persona receives an ``Expert A``,
        ``Expert B``, ... label within this rendered context. Delphi round-2
        feedback aggregates structured positions and ratings without names.
        """
        if not transcript:
            return "No prior contributions."
        relevant_turns = transcript
        open_round_fallback = False
        if round_index and (
            self.base_strategy != "delphi" and round_index <= self.isolated_rounds
            or self.base_strategy == "delphi" and round_index == 1
        ):
            relevant_turns = []
        elif self.base_strategy == "delphi" and round_index and round_index > 1:
            relevant_turns = [turn for turn in transcript if turn.round_index == round_index - 1]
        if item_id is not None:
            item_turns = [turn for turn in relevant_turns if turn.item_id == item_id]
            if item_turns:
                relevant_turns = item_turns
            elif self.base_strategy == "delphi" and round_index == 2:
                relevant_turns = [
                    turn
                    for turn in relevant_turns
                    if turn.role == "participant" and turn.item_id is None
                ]
                open_round_fallback = bool(relevant_turns)
            else:
                relevant_turns = []
        if not relevant_turns:
            if self.base_strategy == "delphi" and round_index == 2:
                return self._delphi_feedback([], item_id)
            return "No prior contributions."
        feedback = ""
        if self.base_strategy == "delphi" and round_index == 2:
            if open_round_fallback:
                feedback = (
                    "Round 1 open responses (anonymous, not item-specific; "
                    "no item ratings were collected)."
                )
            else:
                feedback = self._delphi_feedback(relevant_turns, item_id)
        labels: dict[str, str] = {}
        rendered_turns: list[str] = []
        for turn in relevant_turns:
            if anonymize:
                label = labels.setdefault(
                    turn.persona_id,
                    f"Expert {chr(ord('A') + len(labels))}",
                )
            else:
                label = turn.persona_name
            rendered_turns.append(f"{label}:\n{turn.content}")
        rendered_context = "\n\n".join(rendered_turns)
        return f"{feedback}\n\n{rendered_context}" if feedback else rendered_context

    @staticmethod
    def _delphi_feedback(transcript: list[DiscussionTurn], item_id: str | None = None) -> str:
        """Summarize available positions and ratings without exposing identities.

        Args:
            transcript: Turns whose structured fields should be aggregated.
            item_id: Optional item label for the feedback heading.

        Position and rating distributions use their respective non-``None``
        values, so missing fields do not enter that field's denominator. If no
        positions are available, the result reports that no valid data was
        available.
        """
        positions = [turn.position for turn in transcript if turn.position is not None]
        ratings = [turn.rating for turn in transcript if turn.rating is not None]
        if not positions:
            prefix = f"Item {item_id}" if item_id else "Round 1"
            return f"{prefix} structured feedback (anonymous): no valid data was available."
        counts: dict[str, int] = {}
        for position in positions:
            counts[position] = counts.get(position, 0) + 1
        distribution = ", ".join(
            f"{position}={counts[position]}/{len(positions)}"
            for position in sorted(counts)
        )
        rating_feedback = ""
        if ratings:
            rating_counts: dict[int, int] = {}
            for rating in ratings:
                rating_counts[rating] = rating_counts.get(rating, 0) + 1
            rating_distribution = ", ".join(
                f"{rating}={rating_counts[rating]}/{len(ratings)}"
                for rating in sorted(rating_counts)
            )
            rating_feedback = f"; ratings: {rating_distribution}"
        prefix = f"Item {item_id}" if item_id else "Round 1"
        return f"{prefix} structured feedback (anonymous): {distribution}{rating_feedback}."
