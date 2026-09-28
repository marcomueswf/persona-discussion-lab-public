from __future__ import annotations


IMPLEMENTED_STRATEGIES: dict[str, dict[str, str | bool]] = {
    "free": {
        "displayName": "Free discussion",
        "useModeratorSelection": False,
        "contextMode": "all",
    },
    "delphi": {
        "displayName": "Delphi",
        "useModeratorSelection": False,
        "contextMode": "previous_round",
    },
    "moderated": {
        "displayName": "Moderated discussion",
        "useModeratorSelection": True,
        "contextMode": "all",
    },
}


DEFAULT_PROMPT_TEMPLATES: dict[str, dict[str, str]] = {
    "global": {
        "moderatorSystemPrompt": "You are a neutral moderator. Focus the next discussion round on one unresolved issue.",
        "moderatorUserPrompt": "Topic: {topic}\nCurrent thesis: {thesis}\nTranscript:\n{transcript}",
        "selectionSystemPrompt": "Select exactly one eligible persona name. Return no explanation.",
        "selectionUserPrompt": "Topic: {topic}\nModerator instruction: {instruction}\nEligible personas: {eligible_names}",
        "participantSystemPrompt": "You are {persona_name}, acting as {persona_role}.\n\nYour persona profile is background context, not a script:\n{persona_profile}\n\nProfile guidance:\n{persona_profile_directives}\n\nUse the profile goals, constraints, and communication style to shape your response.",
        "participantUserPrompt": "Topic: {topic}\nRound: {round_index}\nDiscussion strategy: {strategy}\n{strategy_instruction}\nModerator focus: {moderator_instruction}\n\nDiscussion context:\n{context}\n\nProvide a concise analysis, one risk or critique, and one concrete recommendation.",
        "roundSummarySystemPrompt": "You synthesize a discussion round into a concise working thesis.",
        "roundSummaryUserPrompt": "Topic: {topic}\nRound contributions:\n{transcript}",
        "finalSummarySystemPrompt": "You synthesize a multi-persona discussion into a concise, actionable result.",
        "finalSummaryUserPrompt": "Topic: {topic}\nWorking thesis: {working_thesis}\n\nTranscript:\n{transcript}\n\nWrite a concise conclusion with the strongest recommendation and remaining uncertainty.",
    },
}


DEFAULT_STRATEGY_SPECIFICATIONS: list[dict[str, object]] = [
    {
        "strategyKey": "free",
        "displayName": "Free discussion",
        "baseStrategy": "free",
        "isolatedRounds": 0,
        "peerVisibility": "named",
        "promptTemplates": {
            "moderatorInstruction": "State your own position and build on relevant earlier contributions.",
            "participantInstruction": "Build directly on useful earlier points and state your own position.",
        },
    },
    {
        "strategyKey": "delphi",
        "displayName": "Delphi",
        "baseStrategy": "delphi",
        "isolatedRounds": 1,
        "peerVisibility": "anonymous",
        "promptTemplates": {
            "moderatorInstruction": "State your own position and build on relevant earlier contributions.",
            "participantInstruction": "State an independent position, then explicitly reconsider the prior-round consensus.",
        },
    },
    {
        "strategyKey": "moderated",
        "displayName": "Moderated discussion",
        "baseStrategy": "moderated",
        "isolatedRounds": 0,
        "peerVisibility": "named",
        "promptTemplates": {
            "moderatorInstruction": "Address the most important unresolved point identified by the discussion.",
            "participantInstruction": "Address the most important unresolved point identified by the discussion.",
        },
    },
]
