from __future__ import annotations
"""LLM adapter and persona primitives.

This module isolates provider-specific client calls from orchestration code.
"""

import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Callable
from uuid import uuid4

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class PersonaAgent:
    """Represents a persona agent for discussions.
    
    Attributes:
        persona_id: Unique identifier for the persona.
        name: Display name of the persona.
        role: Role or title of the persona in discussions.
        description: Optional persona description used in prompt templates.
        background: Optional background information about the persona.
        expertise: Areas of expertise relevant to the persona.
        goals: Objectives the persona aims to achieve.
        constraints: Limitations or boundaries for the persona.
        communication_style: Preferred style for the persona's communication.
    """
    persona_id: str
    name: str
    role: str
    description: str
    background: str = ""
    expertise: tuple[str, ...] = ()
    goals: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    communication_style: str = ""


class ChatClient:
    """Adapter around OpenAI-compatible responses API.

    If no provider client can be configured, ``complete`` falls back to a mock
    response so local development can still exercise orchestration paths.
    """

    def __init__(
        self,
        model: str,
        temperature: float,
        token_limit: int,
        trace_sink: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        """Initialize adapter with generation defaults and provider settings.

        Args:
            model: Provider model identifier to use for completions.
            temperature: Sampling temperature for generated responses.
            token_limit: Maximum number of output tokens per completion.
            trace_sink: Optional callback that receives completion trace data.
        """
        self.model = model
        self.temperature = temperature
        self.token_limit = token_limit
        self.trace_sink = trace_sink
        api_key = os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_BASE_URL", "").strip() or None
        if api_key and OpenAI:
            client_options = {"api_key": api_key}
            if base_url is not None:
                client_options["base_url"] = base_url
            else:
                # The SDK falls back to reading this env var itself, so an
                # empty string left in the process environment would still
                # override its default base URL.
                os.environ.pop("OPENAI_BASE_URL", None)
            self._client = OpenAI(**client_options)
        else:
            self._client = None

    @property
    def enabled(self) -> bool:
        """Return whether a real provider client is configured."""
        return self._client is not None

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        trace_context: dict[str, Any] | None = None,
    ) -> str:
        """Generate one model completion for a system/user prompt pair.

        Args:
            system_prompt: Instructions establishing the model's role and behavior.
            user_prompt: The user-facing task or content to respond to.
            trace_context: Optional metadata to include in the completion trace.

        Returns:
            The generated response text.
        """
        started = time.perf_counter()
        trace = {
            "traceId": str(uuid4()),
            "model": self.model,
            "status": "completed",
            "systemPrompt": system_prompt,
            "userPrompt": user_prompt,
            "response": None,
            "durationMs": None,
            "error": None,
            **(trace_context or {}),
        }
        try:
            if self._client is None:
                logger.info("Using the mock chat response because no OpenAI client is configured.")
                result = self._mock_response(system_prompt, user_prompt)
            else:
                logger.info("Sending OpenAI-compatible request with model %s.", self.model)
                response = self._client.responses.create(
                    model=self.model,
                    temperature=self.temperature,
                    max_output_tokens=self.token_limit,
                    input=[
                        {"role": "system", "content": [{"type": "input_text", "text": system_prompt}]},
                        {"role": "user", "content": [{"type": "input_text", "text": user_prompt}]},
                    ],
                )
                result = response.output_text.strip()
            trace["response"] = result
            return result
        except Exception as error:
            trace["status"] = "failed"
            trace["error"] = str(error)
            logger.exception("OpenAI-compatible request failed for model %s.", self.model)
            raise
        finally:
            trace["durationMs"] = round((time.perf_counter() - started) * 1000)
            if self.trace_sink is not None:
                self.trace_sink(trace)

    @staticmethod
    def _mock_response(system_prompt: str, user_prompt: str) -> str:
        """Return deterministic placeholder output for local/offline workflows."""
        task = user_prompt.split("Topic:", 1)[-1].strip().splitlines()[0] if "Topic:" in user_prompt else user_prompt[:160]
        perspective = system_prompt.replace("\n", " ")[:120]
        return (
            "[Mock response - configure OPENAI_API_KEY for provider output]\n"
            f"Perspective: {perspective}\n"
            f"Contribution to '{task}': identify assumptions, a concrete risk, and one actionable next step."
        )
