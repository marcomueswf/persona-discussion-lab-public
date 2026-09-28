"""Pydantic API and domain transport models for the backend boundary.

These models define request/response contracts shared between FastAPI routers
and the OpenUI5 frontend.
"""

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.prompt_templates import (
    DEFAULT_PROMPT_TEMPLATES,
    DEFAULT_STRATEGY_SPECIFICATIONS,
    IMPLEMENTED_STRATEGIES,
)


class Persona(BaseModel):
    """Persona definition used by API payloads and persistence.

    Attributes:
        personaId: Stable unique identifier of the persona.
        name: Display name shown in UI and transcripts.
        role: Optional short role label.
        description: Optional persona description used by prompt templates.
        model: Optional model override for this persona.
        temperature: Optional temperature override in range [0, 2].
    """

    model_config = ConfigDict(extra="forbid")

    personaId: str = Field(description="Stable unique identifier of the persona.")
    name: str = Field(description="Display name shown in the UI and transcripts.")
    role: Optional[str] = Field(default=None, description="Optional short role label for the persona.")
    description: Optional[str] = Field(
        default=None,
        description="Optional persona description used by prompt templates.",
    )
    background: Optional[str] = Field(
        default=None,
        description="Relevant professional or contextual background.",
    )
    expertise: list[str] = Field(
        default_factory=list,
        description="Knowledge areas this persona should draw on.",
    )
    goals: list[str] = Field(
        default_factory=list,
        description="Goals this persona should pursue during the discussion.",
    )
    constraints: list[str] = Field(
        default_factory=list,
        description="Constraints or principles that should limit the persona's reasoning.",
    )
    communicationStyle: Optional[str] = Field(
        default=None,
        description="Preferred style for communicating contributions.",
    )
    model: Optional[str] = Field(
        default=None,
        description="Optional model override used for this persona.",
    )
    temperature: Optional[float] = Field(
        default=None,
        ge=0,
        le=2,
        description="Optional temperature override for persona-level generation.",
    )


class PersonaUpdate(BaseModel):
    """Validated partial update for an existing persona.

    Attributes:
        name: Optional replacement display name.
        role: Optional replacement role label.
        description: Optional replacement persona description.
        background: Optional replacement professional or contextual background.
        expertise: Optional replacement knowledge areas.
        goals: Optional replacement persona goals.
        constraints: Optional replacement persona constraints.
        communicationStyle: Optional replacement communication style.
        model: Optional replacement model override.
        temperature: Optional replacement temperature from 0 to 2.
    """

    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = None
    role: Optional[str] = None
    description: Optional[str] = None
    background: Optional[str] = None
    expertise: Optional[list[str]] = None
    goals: Optional[list[str]] = None
    constraints: Optional[list[str]] = None
    communicationStyle: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[float] = Field(default=None, ge=0, le=2)




class DiscussionStrategy(str, Enum):
    """Built-in strategy identifiers used as defaults.

    Attributes:
        FREE: Unstructured participant discussion.
        DELPHI: Delphi-style iterative assessment.
        MODERATED: Discussion coordinated by a moderator.
    """

    FREE = "free"
    DELPHI = "delphi"
    MODERATED = "moderated"


class DelphiItem(BaseModel):
    """Configured statement that every Delphi participant evaluates.

    Attributes:
        itemId: Stable identifier for the statement.
        statement: Statement presented for evaluation.
        scaleMin: Minimum allowed rating value.
        scaleMax: Maximum allowed rating value.
        status: Whether the item is active or inactive.
    """

    model_config = ConfigDict(extra="forbid")

    itemId: str = Field(min_length=1, max_length=120)
    statement: str = Field(min_length=1, max_length=2000)
    scaleMin: int = Field(default=1, ge=1, le=1)
    scaleMax: int = Field(default=5, ge=5, le=5)
    status: Literal["active", "inactive"] = "active"


class DelphiRoundConfiguration(BaseModel):
    """Item behavior configured for one Delphi discussion round.

    Attributes:
        mode: Processing mode used for the round.
        itemIds: Delphi item IDs selected for the round.
    """

    mode: Literal["open", "rate", "discuss", "most_disputed", "synthesize"] = "open"
    itemIds: list[str] = Field(default_factory=list)


class StrategySpecification(BaseModel):
    """Configurable strategy subclass specification.

    A strategy specification references one implemented base strategy and may
    override strategy-specific prompt templates.
    """

    strategyKey: str = Field(min_length=1, max_length=120, description="Unique strategy key used by discussion runs.")
    displayName: str = Field(min_length=1, max_length=200, description="Human-readable strategy name shown in UI.")
    baseStrategy: str = Field(min_length=1, max_length=120, description="Implemented backend strategy to extend.")
    isolatedRounds: int = Field(
        default=0,
        ge=0,
        le=5,
        description="Number of initial rounds in which participants do not see peer contributions from the same round.",
    )
    peerVisibility: Literal["named", "anonymous"] = Field(
        default="named",
        description="Whether participants see peer names and roles or anonymous expert labels.",
    )
    promptTemplates: dict[str, str] = Field(
        default_factory=dict,
        description="Strategy-specific prompt template overrides.",
    )


class ImplementedStrategy(BaseModel):
    """Metadata for backend-implemented strategy behavior.

    Attributes:
        key: Stable strategy identifier.
        displayName: Human-readable strategy name.
        useModeratorSelection: Whether a moderator selects participants' inputs.
        contextMode: Context visibility mode used by the strategy.
    """

    key: str
    displayName: str
    useModeratorSelection: bool
    contextMode: str


class DiscussionStartRequest(BaseModel):
    """Input contract for creating a new discussion run.

    Attributes:
        topic: Topic or thesis to analyze.
        personaIds: Ordered list of selected persona IDs.
        strategy: Strategy subclass key selected in UI.
        model: Optional run-level model override.
        temperature: Sampling temperature in range [0, 2].
        maxRounds: Maximum number of rounds.
        tokenLimit: Maximum output tokens per completion.
    """

    topic: str = Field(
        min_length=1,
        max_length=12000,
        description="Discussion topic or thesis to analyze.",
    )
    personaIds: list[str] = Field(
        min_length=2,
        description="Ordered list of selected persona IDs participating in the run.",
    )
    strategy: str = Field(
        default=DiscussionStrategy.FREE.value,
        min_length=1,
        max_length=120,
        description="Strategy key controlling how turns are coordinated.",
    )
    model: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Optional model override for this run.",
    )
    temperature: float = Field(
        default=0.3,
        ge=0.2,
        le=0.8,
        description="Sampling temperature used when generating responses, from 0.2 to 0.8.",
    )
    maxRounds: int = Field(
        default=1,
        ge=1,
        le=5,
        description="Maximum number of discussion rounds before termination.",
    )
    tokenLimit: int = Field(
        default=1200,
        ge=128,
        le=16000,
        description="Maximum output token budget for one model completion.",
    )
    traceEnabled: bool = Field(
        default=False,
        description="Persist full prompts and responses for local debugging.",
    )
    isolatedRounds: Optional[int] = Field(
        default=None,
        ge=0,
        le=5,
        description="Optional per-discussion override for the number of initial isolated rounds.",
    )
    roundPlan: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Optional per-round participant instruction overrides scoped to this topic, "
            "keyed like 'participantInstructionRound1'. Takes precedence over the strategy's "
            "generic participantInstruction for the matching round."
        ),
    )
    delphiItems: list[DelphiItem] | None = Field(
        default=None,
        description=(
            "Configured statements to rate during Delphi rounds. Omitted means use global defaults; "
            "an explicit empty list disables item ratings for this discussion."
        ),
    )
    delphiRoundPlan: dict[int, DelphiRoundConfiguration] | None = Field(
        default=None,
        description="Optional per-round Delphi modes and item selections.",
    )


class DiscussionConfiguration(BaseModel):
    """Effective configuration for one discussion execution.

    Attributes:
        model: Model identifier used for completions.
        temperature: Default sampling temperature.
        maxRounds: Default maximum number of discussion rounds.
        tokenLimit: Default output token budget per completion.
        promptTemplates: Global prompt templates.
        strategySpecifications: Configured strategy subclasses.
        implementedStrategies: Backend-supported base strategies.
        roundPlan: Per-round participant instruction overrides.
        delphiItems: Default Delphi statements.
        delphiRoundPlan: Default Delphi round modes and item selections.
    """

    class PromptTemplates(BaseModel):
        global_templates: dict[str, str] = Field(
            default_factory=lambda: dict(DEFAULT_PROMPT_TEMPLATES["global"]),
            alias="global",
            description="Global templates shared across all strategies.",
        )

    @staticmethod
    def _default_implemented_strategies() -> list[ImplementedStrategy]:
        """Build the default metadata for implemented strategies."""
        return [
            ImplementedStrategy(key=key, **value)
            for key, value in IMPLEMENTED_STRATEGIES.items()
        ]

    @staticmethod
    def _default_strategy_specifications() -> list[StrategySpecification]:
        """Build the default configurable strategy specifications."""
        return [
            StrategySpecification(**item)
            for item in DEFAULT_STRATEGY_SPECIFICATIONS
        ]

    model: str = Field(
        default="gpt-4.1-mini",
        max_length=200,
        description="Model identifier used for completions.",
    )
    temperature: float = Field(
        default=0.3,
        ge=0.2,
        le=0.8,
        description="Global default sampling temperature, from 0.2 to 0.8.",
    )
    maxRounds: int = Field(
        default=1,
        ge=1,
        le=5,
        description="Global default limit for discussion rounds.",
    )
    tokenLimit: int = Field(
        default=1200,
        ge=128,
        le=16000,
        description="Global default token limit per completion.",
    )
    promptTemplates: PromptTemplates = Field(
        default_factory=PromptTemplates,
        description="Global prompt templates used for all LLM calls.",
    )
    strategySpecifications: list[StrategySpecification] = Field(
        default_factory=_default_strategy_specifications,
        description="Configured strategy subclasses that extend implemented strategies.",
    )
    implementedStrategies: list[ImplementedStrategy] = Field(
        default_factory=_default_implemented_strategies,
        description="Backend-implemented base strategies exposed as read-only metadata.",
    )
    roundPlan: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Topic-scoped per-round participant instruction overrides captured for this "
            "discussion or template, keyed like 'participantInstructionRound1'."
        ),
    )
    delphiItems: list[DelphiItem] = Field(
        default_factory=list,
        description="Default configured statements for Delphi discussions.",
    )
    delphiRoundPlan: dict[int, DelphiRoundConfiguration] = Field(
        default_factory=dict,
        description="Default per-round Delphi modes and item selections.",
    )


class DiscussionHistoryConfiguration(DiscussionConfiguration):
    """Configuration snapshot that remains compatible with older discussions.

    Attributes:
        temperature: Historical sampling temperature, allowing the legacy range
            from 0 to 2.
    """

    temperature: float = Field(
        default=0.3,
        ge=0,
        le=2,
        description="Sampling temperature recorded for a historical discussion run.",
    )


class StrategySpecificationUpdate(BaseModel):
    """Replacement payload for one configurable strategy specification.

    Attributes:
        strategyKey: Unique key for the strategy specification.
        displayName: Human-readable strategy name.
        baseStrategy: Implemented strategy extended by this specification.
        isolatedRounds: Number of initial isolated rounds.
        peerVisibility: Whether peer contributions are named or anonymous.
        promptTemplates: Strategy-specific prompt overrides.
    """

    strategyKey: str = Field(min_length=1, max_length=120)
    displayName: str = Field(min_length=1, max_length=200)
    baseStrategy: str = Field(min_length=1, max_length=120)
    isolatedRounds: int = Field(default=0, ge=0, le=5)
    peerVisibility: Literal["named", "anonymous"] = "named"
    promptTemplates: dict[str, str] = Field(default_factory=dict)


class DiscussionConfigurationUpdate(BaseModel):
    """Partial update payload for persisted default configuration.

    Attributes:
        model: Optional replacement default model.
        temperature: Optional replacement default temperature.
        maxRounds: Optional replacement default round limit.
        tokenLimit: Optional replacement default token limit.
        promptTemplates: Optional partial template update.
        strategySpecifications: Optional replacement strategy specifications.
    """

    class PromptTemplatesUpdate(BaseModel):
        global_templates: Optional[dict[str, str]] = Field(
            default=None,
            alias="global",
            description="Optional partial update for global templates.",
        )

    model: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Optional new default model identifier.",
    )
    temperature: Optional[float] = Field(
        default=None,
        ge=0.2,
        le=0.8,
        description="Optional new default sampling temperature, from 0.2 to 0.8.",
    )
    maxRounds: Optional[int] = Field(
        default=None,
        ge=1,
        le=5,
        description="Optional new default maximum rounds value.",
    )
    tokenLimit: Optional[int] = Field(
        default=None,
        ge=128,
        le=16000,
        description="Optional new default token limit per completion.",
    )
    promptTemplates: Optional[PromptTemplatesUpdate] = Field(
        default=None,
        description="Optional partial update of global prompt templates.",
    )
    strategySpecifications: Optional[list[StrategySpecificationUpdate]] = Field(
        default=None,
        description="Optional full replacement of strategy subclasses.",
    )


class DiscussionMessage(BaseModel):
    """Frontend-facing representation of one persisted discussion turn.

    Attributes:
        messageId: Unique message identifier.
        roundIndex: Discussion round that produced the message.
        personaId: ID of the contributing persona.
        personaName: Display name of the contributing persona.
        role: Message role in the discussion lifecycle.
        content: Natural-language message content.
        contributionType: Semantic contribution type.
        position: Structured position when extracted.
        confidence: Reported confidence when available.
        respondsTo: Message IDs directly addressed by this contribution.
        revisedFrom: Earlier message whose position was revised.
        phase: Conceptual Delphi phase of the message.
        itemId: Addressed Delphi item ID, when applicable.
        itemStatement: Addressed Delphi statement, when applicable.
        rating: Validated Delphi rating, when applicable.
        revised: Whether the prior item rating changed.
        validStructuredResponse: Whether the structured response passed validation.
    """

    messageId: str = Field(description="Unique identifier for this message record.")
    roundIndex: int = Field(ge=1, description="Round number in which this message was produced.")
    personaId: str = Field(description="ID of the persona that produced the message.")
    personaName: str = Field(description="Display name of the persona that produced the message.")
    role: Literal["participant", "moderator", "summary"] = Field(
        description="Role of the message within the discussion lifecycle.",
    )
    content: str = Field(description="Natural-language message content.")
    contributionType: Literal["contribution", "initial_position", "critique", "revision", "summary"] = Field(
        default="contribution",
        description="Semantic type of a participant contribution, when known.",
    )
    position: Literal["support", "oppose", "mixed", "undecided"] | None = Field(
        default=None,
        description="Structured position, when it was explicitly extracted.",
    )
    confidence: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description="Reported confidence in the contribution, when available.",
    )
    respondsTo: list[str] = Field(
        default_factory=list,
        description="Message IDs this contribution directly addresses.",
    )
    revisedFrom: str | None = Field(
        default=None,
        description="Earlier message ID whose position was revised.",
    )
    phase: Literal["elicitation", "feedback", "expert_discussion", "discussion"] = Field(
        default="discussion",
        description="Conceptual Delphi phase in which the message was produced.",
    )
    itemId: str | None = Field(
        default=None,
        description="Configured Delphi item addressed by this contribution.",
    )
    itemStatement: str | None = Field(
        default=None,
        description="Human-readable statement for the addressed Delphi item.",
    )
    rating: int | None = Field(
        default=None,
        ge=1,
        le=5,
        description="Validated 1-5 Delphi rating for the addressed item.",
    )
    revised: bool | None = Field(
        default=None,
        description="Whether the participant changed this item's prior rating.",
    )
    validStructuredResponse: bool = Field(
        default=False,
        description="Whether the structured Delphi response passed validation.",
    )


class DiscussionResult(BaseModel):
    """Structured result projection used by result endpoints.

    Attributes:
        summary: Concise final discussion summary.
        consensus: Best-effort consensus statement.
        disagreements: Remaining disagreement points.
        recommendations: Actionable recommendations.
        consensusLevel: Measured consensus level from 0 to 1.
        stabilityLevel: Stability of positions across rounds from 0 to 1.
        disagreementLevel: Measured disagreement level from 0 to 1.
        minorityPositions: Positions remaining in the minority.
        polarizationLevel: Separation between opposing positions from 0 to 1.
        itemMetrics: Per-item consensus and revision metrics.
        terminationReason: Reason the discussion ended.
    """

    summary: Optional[str] = Field(
        default=None,
        description="Concise final summary of the discussion.",
    )
    consensus: Optional[str] = Field(
        default=None,
        description="Best-effort consensus statement distilled from contributions.",
    )
    disagreements: list[str] = Field(
        default_factory=list,
        description="Remaining disagreement points extracted from the discussion.",
    )
    recommendations: list[str] = Field(
        default_factory=list,
        description="Actionable recommendations derived from the result.",
    )
    consensusLevel: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description="Explicitly measured consensus level, when structured positions exist.",
    )
    stabilityLevel: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description="Stability of positions across discussion rounds, when measurable.",
    )
    disagreementLevel: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description="Explicitly measured disagreement level, when structured positions exist.",
    )
    minorityPositions: list[str] = Field(
        default_factory=list,
        description="Positions that remain in the minority after the discussion.",
    )
    polarizationLevel: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description="Degree of separation between opposing positions, when measurable.",
    )
    itemMetrics: dict[str, dict[str, object]] = Field(
        default_factory=dict,
        description="Consensus and revision metrics calculated separately per Delphi item.",
    )
    terminationReason: Optional[str] = Field(
        default=None,
        description="Reason why the discussion ended.",
    )


class DiscussionTraceEntry(BaseModel):
    """One LLM call or post-discussion analysis captured in the trace."""

    traceId: str
    sequence: int = Field(ge=1)
    callType: Literal["moderator", "selection", "participant", "round_summary", "final_summary", "analysis"]
    roundIndex: int | None = Field(default=None, ge=1)
    personaId: str | None = None
    personaName: str | None = None
    model: str | None = None
    status: Literal["completed", "failed"]
    systemPrompt: str | None = None
    userPrompt: str | None = None
    response: str | None = None
    analysisBasis: dict[str, object] | None = None
    analysisOutput: dict[str, object] | None = None
    durationMs: int | None = Field(default=None, ge=0)
    error: str | None = None


class DiscussionTraceResponse(BaseModel):
    """Trace projection loaded separately from a discussion transcript."""

    discussionId: str
    enabled: bool = False
    entries: list[DiscussionTraceEntry] = Field(default_factory=list)


class DiscussionTemplateCreate(BaseModel):
    """Request for saving a completed discussion as a reusable template."""

    templateName: str = Field(min_length=1, max_length=200)
    discussionId: str = Field(min_length=1)


class DiscussionTemplateResponse(BaseModel):
    """Reusable discussion setup captured from one persisted run."""

    templateId: str = Field(description="Stable unique template identifier.")
    templateName: str = Field(description="Human-readable template name.")
    sourceDiscussionId: str = Field(description="Discussion run used to create this template.")
    topic: str = Field(description="Topic or thesis configured for the template.")
    strategy: str = Field(description="Strategy subclass selected for the template.")
    personaIds: list[str] = Field(description="Ordered persona IDs selected for the template.")
    configuration: Optional[DiscussionHistoryConfiguration] = Field(
        default=None,
        description="Configuration and prompt snapshot captured from the source run.",
    )
    createdAt: str = Field(description="Creation timestamp in UTC.")
    updatedAt: str = Field(description="Last update timestamp in UTC.")


class DiscussionResponse(BaseModel):
    """Primary API projection for discussion lifecycle and transcript state."""

    discussionId: str = Field(description="Stable unique discussion run identifier.")
    status: Literal["queued", "running", "completed", "stopped", "failed"] = Field(
        description="Current lifecycle state of the discussion run.",
    )
    topic: str = Field(description="Topic or thesis under discussion.")
    strategy: str = Field(description="Strategy key used to orchestrate turns.")
    personaIds: list[str] = Field(description="Selected persona IDs participating in the run.")
    configuration: Optional[DiscussionHistoryConfiguration] = Field(
        default=None,
        description="Effective configuration applied to this discussion run.",
    )
    messages: list[DiscussionMessage] = Field(
        default_factory=list,
        description="Persisted transcript messages in chronological order.",
    )
    summary: Optional[str] = Field(
        default=None,
        description="Legacy top-level summary kept for backward compatibility.",
    )
    result: Optional[DiscussionResult] = Field(
        default=None,
        description="Structured result projection for this discussion.",
    )
    error: Optional[str] = Field(
        default=None,
        description="Failure message when status is failed.",
    )
