import os
import unittest
from unittest.mock import patch

from backend.core.agent import ChatClient, PersonaAgent
from backend.core.discussion import DiscussionEngine, DiscussionTurn


class FakeChatClient:
    def __init__(self):
        self.calls = []

    def complete(self, system_prompt, user_prompt):
        self.calls.append((system_prompt, user_prompt))
        if "Select exactly one eligible persona name" in system_prompt:
            return "Unknown persona"
        return "Deterministic response"


class TraceAwareChatClient(FakeChatClient):
    def __init__(self, trace_sink):
        super().__init__()
        self.trace_sink = trace_sink

    def complete(self, system_prompt, user_prompt, trace_context=None):
        self.calls.append((system_prompt, user_prompt, trace_context))
        self.trace_sink({**(trace_context or {}), "systemPrompt": system_prompt, "userPrompt": user_prompt})
        if "Select exactly one eligible persona name" in system_prompt:
            return "Unknown persona"
        return "Deterministic response"


class DiscussionEngineTests(unittest.TestCase):
    def setUp(self):
        self.personas = [
            PersonaAgent("analyst", "Analyst", "Analyzes evidence", ""),
            PersonaAgent("critic", "Critic", "Finds risks", ""),
        ]

    def test_each_strategy_emits_participants_and_one_summary(self):
        """Checks that every strategy emits participant turns and one summary."""
        for strategy in ("free", "delphi", "moderated"):
            with self.subTest(strategy=strategy):
                turns = list(
                    DiscussionEngine(
                        "Test topic",
                        self.personas,
                        strategy,
                        1,
                        FakeChatClient(),
                    ).run()
                )
                self.assertEqual([turn.role for turn in turns], ["participant", "participant", "summary"])
                self.assertEqual([turn.persona_id for turn in turns[:2]], ["analyst", "critic"])
                self.assertEqual(
                    [turn.contribution_type for turn in turns],
                    ["initial_position", "initial_position", "summary"],
                )
    def test_multiple_rounds_complete_without_graph_recursion_failure(self):
        """Checks that multiple rounds complete without a recursion failure."""
        turns = list(
            DiscussionEngine(
                "Test topic",
                self.personas,
                "delphi",
                5,
                FakeChatClient(),
            ).run()
        )
        self.assertEqual(len(turns), 11)
        self.assertEqual(turns[-1].role, "summary")

    def test_configured_isolated_rounds_hide_same_round_peer_contributions(self):
        """Checks that isolated rounds hide contributions from peers in the same round."""
        client = TraceAwareChatClient(lambda entry: None)
        list(
            DiscussionEngine(
                "Test topic",
                self.personas,
                "free",
                3,
                client,
                isolated_rounds=2,
            ).run()
        )

        participant_prompts = [
            user_prompt
            for system_prompt, user_prompt, *_ in client.calls
            if "You are " in system_prompt
        ]
        self.assertEqual(len(participant_prompts), 6)
        self.assertNotIn("Analyst", participant_prompts[1])
        self.assertNotIn("Analyst", participant_prompts[3])
        self.assertIn("Analyst", participant_prompts[5])

    def test_delphi_round_two_uses_previous_round_when_not_isolated(self):
        """Checks that Delphi round two can use visible contributions from round one."""
        client = TraceAwareChatClient(lambda entry: None)
        list(
            DiscussionEngine(
                "Test topic",
                self.personas,
                "delphi",
                2,
                client,
                isolated_rounds=0,
                peer_visibility="named",
            ).run()
        )

        participant_prompts = [
            user_prompt
            for system_prompt, user_prompt, *_ in client.calls
            if "You are " in system_prompt
        ]
        self.assertEqual(len(participant_prompts), 4)
        self.assertIn("Analyst", participant_prompts[2])
        self.assertIn("Critic", participant_prompts[2])

    def test_delphi_participant_context_hides_persona_names(self):
        """Checks that anonymous Delphi context does not expose persona names."""
        client = TraceAwareChatClient(lambda entry: None)
        list(
            DiscussionEngine(
                "Test topic",
                self.personas,
                "delphi",
                2,
                client,
                isolated_rounds=0,
                peer_visibility="anonymous",
            ).run()
        )

        participant_prompts = [
            user_prompt
            for system_prompt, user_prompt, *_ in client.calls
            if "You are " in system_prompt
        ]
        self.assertNotIn("Analyst:\nDeterministic response", participant_prompts[2])
        self.assertNotIn("Critic:\nDeterministic response", participant_prompts[2])
        self.assertIn("Expert A:\nDeterministic response", participant_prompts[2])
        self.assertIn("Expert B:\nDeterministic response", participant_prompts[2])

    def test_delphi_round_two_includes_aggregated_feedback(self):
        """Checks that aggregated feedback is included in the second Delphi round."""
        class StructuredClient(TraceAwareChatClient):
            def complete(self, system_prompt, user_prompt, trace_context=None):
                self.calls.append((system_prompt, user_prompt, trace_context))
                if "You are " in system_prompt:
                    return '{"position":"support","confidence":0.8}'
                return "Deterministic response"

        client = StructuredClient(lambda entry: None)
        list(DiscussionEngine("Test topic", self.personas, "delphi", 2, client).run())

        participant_prompts = [
            user_prompt
            for system_prompt, user_prompt, *_ in client.calls
            if "You are " in system_prompt
        ]
        self.assertIn("Round 1 structured feedback (anonymous): support=2/2", participant_prompts[2])
        self.assertIn("keep or revise", participant_prompts[2])

    def test_delphi_third_round_has_expert_discussion_phase(self):
        """Checks that the third Delphi round requests an expert discussion phase."""
        client = TraceAwareChatClient(lambda entry: None)
        list(DiscussionEngine("Test topic", self.personas, "delphi", 3, client).run())

        participant_prompts = [
            user_prompt
            for system_prompt, user_prompt, *_ in client.calls
            if "You are " in system_prompt
        ]
        self.assertIn("strongest remaining disagreement", participant_prompts[4])

    def test_configured_delphi_items_create_item_turns_and_feedback(self):
        """Checks item turns, structured responses, and item feedback in Delphi."""
        class ItemClient(TraceAwareChatClient):
            def complete(self, system_prompt, user_prompt, trace_context=None):
                self.calls.append((system_prompt, user_prompt, trace_context))
                if "You are " in system_prompt:
                    return (
                        '{"itemId":"invented-by-model","rating":4,"position":"support",'
                        '"confidence":0.8,"revised":false}}'
                    )
                return "Deterministic response"

        items = [
            {"itemId": "adaptive-learning", "statement": "Adaptive learning", "status": "active"},
            {"itemId": "teacher-role", "statement": "Teacher role", "status": "active"},
        ]
        client = ItemClient(lambda entry: None)
        turns = list(DiscussionEngine("Test topic", self.personas, "delphi", 2, client, delphi_items=items).run())

        participant_turns = [turn for turn in turns if turn.role == "participant"]
        self.assertEqual(len(participant_turns), 8)
        self.assertTrue(all(turn.valid_structured_response for turn in participant_turns))
        self.assertTrue(
            any("Item adaptive-learning structured feedback" in call[1] for call in client.calls)
        )

    def test_delphi_item_round_two_falls_back_to_open_round_one_responses(self):
        """Checks the fallback to open responses when item-specific data is missing."""
        engine = DiscussionEngine(
            "Test topic",
            self.personas,
            "delphi",
            2,
            FakeChatClient(),
            delphi_items=[{"itemId": "equity", "statement": "AI reduces inequality."}],
        )
        open_turn = DiscussionTurn(
            round_index=1,
            persona_id="analyst",
            persona_name="Analyst",
            role="participant",
            content="Open round-one position on educational equity.",
            position="mixed",
        )

        context = engine._context(
            [open_turn],
            round_index=2,
            anonymize=True,
            item_id="equity",
        )

        self.assertIn("Round 1 open responses", context)
        self.assertIn("not item-specific", context)
        self.assertIn("Open round-one position on educational equity.", context)
        self.assertNotIn("no valid data was available", context)

    def test_delphi_round_plan_scopes_open_ratings_discussion_and_synthesis(self):
        """Checks that the round plan separates open, rating, discussion, and synthesis phases."""
        class RoundPlanClient(TraceAwareChatClient):
            def complete(self, system_prompt, user_prompt, trace_context=None):
                self.calls.append((system_prompt, user_prompt, trace_context))
                if "You are " not in system_prompt:
                    return "Round summary"
                if "Evaluate Delphi item" not in user_prompt:
                    return '{"position":"mixed","confidence":0.7}'
                item_id = "adaptive-learning" if "adaptive-learning" in user_prompt else "teacher-role"
                if "Round: 2" in user_prompt:
                    rating = 1 if item_id == "adaptive-learning" and "You are Analyst" in system_prompt else 5
                    return (
                        f'{{"itemId":"{item_id}","rating":{rating},"position":"mixed",'
                        '"confidence":0.7,"revised":false}'
                    )
                return (
                    f'{{"itemId":"{item_id}","position":"mixed",'
                    '"confidence":0.7,"revised":false}'
                )

        items = [
            {"itemId": "adaptive-learning", "statement": "Adaptive learning", "status": "active"},
            {"itemId": "teacher-role", "statement": "Teacher role", "status": "active"},
        ]
        round_plan = {
            1: {"mode": "open", "itemIds": []},
            2: {"mode": "rate", "itemIds": ["adaptive-learning", "teacher-role"]},
            3: {"mode": "most_disputed", "itemIds": ["adaptive-learning", "teacher-role"]},
            4: {"mode": "synthesize", "itemIds": []},
        }
        client = RoundPlanClient(lambda entry: None)
        turns = list(
            DiscussionEngine(
                "Test topic",
                self.personas,
                "delphi",
                4,
                client,
                delphi_items=items,
                delphi_round_plan=round_plan,
            ).run()
        )

        participant_turns = [turn for turn in turns if turn.role == "participant"]
        round_one = [turn for turn in participant_turns if turn.round_index == 1]
        round_two = [turn for turn in participant_turns if turn.round_index == 2]
        round_three = [turn for turn in participant_turns if turn.round_index == 3]
        round_four = [turn for turn in participant_turns if turn.round_index == 4]
        self.assertTrue(all(turn.item_id is None and turn.rating is None for turn in round_one))
        self.assertEqual(len(round_two), 4)
        self.assertTrue(all(turn.rating is not None and turn.valid_structured_response for turn in round_two))
        self.assertEqual([turn.item_id for turn in round_three], ["adaptive-learning"] * 2)
        self.assertTrue(all(turn.rating is None and not turn.revised for turn in round_three))
        self.assertTrue(all(turn.item_id is None and turn.rating is None for turn in round_four))

    def test_named_peer_visibility_keeps_persona_names(self):
        """Checks that named peer visibility keeps persona names in the context."""
        client = TraceAwareChatClient(lambda entry: None)
        list(
            DiscussionEngine(
                "Test topic",
                self.personas,
                "free",
                2,
                client,
                peer_visibility="named",
            ).run()
        )

        participant_prompts = [
            user_prompt
            for system_prompt, user_prompt, *_ in client.calls
            if "You are " in system_prompt
        ]
        self.assertIn("Analyst:\nDeterministic response", participant_prompts[2])
        self.assertIn("Critic:\nDeterministic response", participant_prompts[2])

    def test_stop_before_the_first_turn_emits_no_messages(self):
        """Checks that stopping before the first turn emits no messages."""
        turns = list(
            DiscussionEngine(
                "Test topic",
                self.personas,
                "free",
                1,
                FakeChatClient(),
                should_stop=lambda: True,
            ).run()
        )
        self.assertEqual(turns, [])

    def test_trace_context_identifies_each_moderated_call(self):
        """Checks call types, round numbers, and persona IDs in the moderation trace."""
        trace_entries = []
        client = TraceAwareChatClient(trace_entries.append)
        list(
            DiscussionEngine(
                "Test topic",
                self.personas,
                "moderated",
                1,
                client,
                use_moderator_selection=True,
                trace_sink=trace_entries.append,
            ).run()
        )

        self.assertEqual(
            [entry["callType"] for entry in trace_entries],
            ["moderator", "selection", "participant", "selection", "participant", "round_summary", "final_summary"],
        )
        self.assertEqual([entry["roundIndex"] for entry in trace_entries], [1] * 7)
        self.assertEqual(trace_entries[2]["personaId"], "analyst")


class ChatClientTests(unittest.TestCase):
    @patch("backend.core.agent.OpenAI")
    def test_empty_base_url_uses_openai_default(self, openai_client):
        """Checks that an empty base URL uses the OpenAI client default."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key", "OPENAI_BASE_URL": ""}, clear=False):
            ChatClient("gpt-4.1-mini", 0.4, 512)

        openai_client.assert_called_once_with(api_key="test-key")

    @patch("backend.core.agent.OpenAI")
    def test_custom_base_url_is_forwarded(self, openai_client):
        """Checks that a custom base URL is forwarded to the OpenAI client."""
        with patch.dict(
            os.environ,
            {"OPENAI_API_KEY": "test-key", "OPENAI_BASE_URL": "https://example.test/v1"},
            clear=False,
        ):
            ChatClient("gpt-4.1-mini", 0.4, 512)

        openai_client.assert_called_once_with(
            api_key="test-key",
            base_url="https://example.test/v1",
        )


if __name__ == "__main__":
    unittest.main()