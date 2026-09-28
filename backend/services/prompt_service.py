from __future__ import annotations
"""Prompt template service used by discussion graph nodes.

This module centralizes prompt text so strategy-specific phrasing stays
separate from orchestration logic.
"""

import logging
from copy import deepcopy
import json

from backend.prompt_templates import DEFAULT_PROMPT_TEMPLATES


logger = logging.getLogger(__name__)


class PromptService:
    """Central prompt templates for discussion nodes.

    The service acts as a lightweight Strategy-template holder: graph nodes pick
    templates by strategy while keeping execution flow unchanged.
    """

    def __init__(
        self,
        global_templates: dict[str, str] | None = None,
        strategy_templates: dict[str, str] | None = None,
        round_plan: dict[str, str] | None = None,
    ) -> None:
        merged_global = deepcopy(DEFAULT_PROMPT_TEMPLATES["global"])
        if isinstance(global_templates, dict):
            for key, value in global_templates.items():
                if key in merged_global and isinstance(value, str) and value.strip():
                    merged_global[key] = value.replace("{persona_description}", "{persona_profile}")

        merged_strategy = {
            "moderatorInstruction": "State your own position and build on relevant earlier contributions.",
            "participantInstruction": "Build directly on useful earlier points and state your own position.",
        }
        if isinstance(strategy_templates, dict):
            for key, value in strategy_templates.items():
                if key in merged_strategy and isinstance(value, str) and value.strip():
                    merged_strategy[key] = value

        self.global_templates = merged_global
        self.strategy_templates = merged_strategy
        self.round_plan = round_plan if isinstance(round_plan, dict) else {}

    def _render(self, key: str, **kwargs: str | int) -> str:
        template = self.global_templates[key]
        try:
            return template.format(**kwargs)
        except KeyError:
            logger.exception("Prompt template '%s' references an unknown placeholder.", key)
            return template

    def moderator_system_prompt(self) -> str:
        return self.global_templates["moderatorSystemPrompt"]

    def moderator_user_prompt(self, topic: str, thesis: str, transcript: str) -> str:
        return self._render(
            "moderatorUserPrompt",
            topic=topic,
            thesis=thesis or "None yet.",
            transcript=transcript,
        )

    def moderator_instruction(self) -> str:
        return self.strategy_templates["moderatorInstruction"]

    def selection_system_prompt(self) -> str:
        return self.global_templates["selectionSystemPrompt"]

    def selection_user_prompt(self, topic: str, instruction: str, eligible_names: list[str]) -> str:
        return self._render(
            "selectionUserPrompt",
            topic=topic,
            instruction=instruction,
            eligible_names=", ".join(eligible_names),
        )

    def participant_instruction(self, round_index: int | None = None) -> str:
        """Return the participant instruction, preferring a topic-scoped round-plan override."""
        if round_index is not None:
            round_key = f"participantInstructionRound{round_index}"
            if round_key in self.round_plan and self.round_plan[round_key].strip():
                return self.round_plan[round_key]
        return self.strategy_templates["participantInstruction"]

    def delphi_phase_instruction(self, round_index: int) -> str:
        """Return the methodological instruction for a Delphi phase."""
        if round_index == 1:
            return "Work independently; do not defer to any other expert."
        if round_index == 2:
            return (
                "Review the anonymized group feedback, rate the same position again, "
                "and state clearly whether you keep or revise your position."
            )
        if round_index == 3:
            return (
                "Participate in the expert discussion by addressing the strongest "
                "remaining disagreement and responding to the previous round."
            )
        return "Continue the Delphi discussion while distinguishing agreement from uncertainty."

    def participant_system_prompt(
        self,
        name: str,
        role: str,
        description: str,
        background: str = "",
        expertise: tuple[str, ...] = (),
        goals: tuple[str, ...] = (),
        constraints: tuple[str, ...] = (),
        communication_style: str = "",
    ) -> str:
        profile = {
            "description": description,
            "background": background,
            "expertise": list(expertise),
            "goals": list(goals),
            "constraints": list(constraints),
            "communicationStyle": communication_style,
        }
        directives = self._profile_directives(
            goals=goals,
            constraints=constraints,
            communication_style=communication_style,
        )
        return self._render(
            "participantSystemPrompt",
            persona_name=name,
            persona_role=role,
            persona_profile=json.dumps(profile, ensure_ascii=False, indent=2),
            persona_profile_directives=directives,
        )

    @staticmethod
    def _profile_directives(
        goals: tuple[str, ...],
        constraints: tuple[str, ...],
        communication_style: str,
    ) -> str:
        """Translate ordinary persona profile metadata into response guidance."""
        directives = [
            "State your own position before giving your recommendation.",
            "Make the following persona goals visible in your reasoning: "
            + ("; ".join(goals) if goals else "none specified"),
            "Apply these persona constraints to every claim: "
            + ("; ".join(constraints) if constraints else "none specified"),
            "Use this communication style: "
            + (communication_style or "clear and relevant"),
        ]
        directives.extend(
            [
                "End with these labeled sections: Position, Reasoning and evidence, "
                "Critique or risk, Recommendation, Uncertainty, Open question.",
                "Do not merely paraphrase another participant; add a distinct contribution "
                "from this persona's perspective.",
            ]
        )
        return "\n".join(f"- {directive}" for directive in directives)

    def participant_user_prompt(
        self,
        topic: str,
        round_index: int,
        strategy: str,
        strategy_instruction: str,
        moderator_instruction: str,
        context: str,
        item_id: str | None = None,
        item_statement: str | None = None,
        item_mode: str | None = None,
    ) -> str:
        prompt = self._render(
            "participantUserPrompt",
            topic=topic,
            round_index=round_index,
            strategy=strategy,
            strategy_instruction=strategy_instruction,
            moderator_instruction=moderator_instruction,
            context=context,
        )
        if strategy == "delphi":
            if item_id is None:
                prompt += (
                    "\n\nState your overall Delphi position on the discussion topic. "
                    "Return a JSON object at the end with exactly these fields: "
                    '{"position":"support|oppose|mixed|undecided", "confidence":0.0}'
                    " Confidence must be a number from 0.0 to 1.0."
                )
            else:
                item_context = f"\n\nEvaluate Delphi item {item_id}: {item_statement or topic}.\n"
                if item_mode == "rate" or (item_mode is None and round_index <= 2):
                    prompt += item_context + (
                        "Return a valid JSON object at the end with exactly these fields; "
                        "do not include an item ID because this response is already bound to the item above: "
                        '{"rating":1, "position":"support|oppose|mixed|undecided", '
                        '"confidence":0.0, "revised":false}'
                        " Do not use Markdown fences. Rating must be an integer from 1 to 5 and confidence a number from 0.0 to 1.0."
                    )
                else:
                    prompt += item_context + (
                        "Discuss the remaining disagreement without changing your historical rating. "
                        "Return a valid JSON object at the end with exactly these fields; "
                        "do not include an item ID because this response is already bound to the item above: "
                        '{"position":"support|oppose|mixed|undecided", '
                        '"confidence":0.0, "revised":false}'
                        " Do not use Markdown fences. Confidence must be a number from 0.0 to 1.0."
                    )
        return prompt

    def round_summary_system_prompt(self) -> str:
        return self.global_templates["roundSummarySystemPrompt"]

    def round_summary_user_prompt(self, topic: str, transcript: str) -> str:
        return self._render("roundSummaryUserPrompt", topic=topic, transcript=transcript)

    def final_summary_system_prompt(self) -> str:
        return self.global_templates["finalSummarySystemPrompt"]

    def final_summary_user_prompt(self, topic: str, working_thesis: str, transcript: str) -> str:
        return self._render(
            "finalSummaryUserPrompt",
            topic=topic,
            working_thesis=working_thesis,
            transcript=transcript,
        )
