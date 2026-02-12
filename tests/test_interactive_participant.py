"""Tests: InteractiveParticipant and PromptSession for human TUI players.

Tests verify:
1. PromptSession building and result formatting
2. Builder functions create valid sessions
3. ChoiceSpec creation helpers work correctly

Note: Full InteractiveParticipant tests require Rich console mocking which is complex.
These tests verify the session building and formatting logic that can be tested synchronously.
"""

import pytest
from typing import Optional

from werewolf.ui.choices import ChoiceSpec, ChoiceOption, ChoiceType, make_seat_choice
from werewolf.ui.prompt_session import (
    PromptSession,
    PromptStep,
    PromptOption,
    PromptType,
    witch_action_session,
    guard_action_session,
    voting_session,
    sheriff_vote_session,
    opt_out_session,
)


# ============================================================================
# PromptSession Tests
# ============================================================================

class TestPromptSession:
    """Tests: PromptSession building and result formatting."""

    def test_add_action_step(self):
        """Adding action step should populate steps list."""
        session = PromptSession()
        session.add_action_step(
            "Choose action:",
            [("PASS", "Pass"), ("KILL", "Kill")],
            allow_none=False,
        )

        assert len(session.steps) == 1
        assert session.steps[0].prompt_type == PromptType.ACTION
        assert session.steps[0].options[0].value == "PASS"
        assert session.steps[0].options[1].value == "KILL"

    def test_add_seat_step(self):
        """Adding seat step should create options with seat hints."""
        session = PromptSession()
        session.add_seat_step(
            "Choose target:",
            seats=[0, 3, 7],
            seat_info={3: "Werewolf"},
            allow_none=True,
        )

        assert len(session.steps) == 1
        assert session.steps[0].prompt_type == PromptType.SEAT
        assert len(session.steps[0].options) == 3
        assert session.steps[0].options[1].seat_hint == 3
        assert session.steps[0].seat_info[3] == "Werewolf"

    def test_add_vote_step(self):
        """Adding vote step should create vote-type options."""
        session = PromptSession()
        session.add_vote_step(
            "Who to banish?",
            candidates=[0, 1, 5],
            allow_none=True,
        )

        assert session.steps[0].prompt_type == PromptType.VOTE

    def test_add_text_step(self):
        """Adding text step should create free-form input."""
        session = PromptSession()
        session.add_text_step("Last words:")

        assert len(session.steps) == 1
        assert session.steps[0].prompt_type == PromptType.TEXT

    def test_add_confirm_step(self):
        """Adding confirm step should create yes/no options."""
        session = PromptSession()
        session.add_confirm_step("Confirm?")

        assert session.steps[0].prompt_type == PromptType.CONFIRM
        assert session.steps[0].options[0].value == "yes"
        assert session.steps[0].options[1].value == "no"

    def test_is_complete_empty(self):
        """Empty session with 0 steps has current_step >= len(steps), so is_complete=True.

        Note: An empty session is considered "complete" since there are no steps to answer.
        """
        session = PromptSession()
        assert session.is_complete()  # 0 >= 0 is True

    def test_is_complete_with_steps(self):
        """Session with steps should track completion."""
        session = PromptSession()
        session.add_action_step("Test:", [("A", "A")], allow_none=False)

        assert not session.is_complete()
        session.answer("A")
        assert session.is_complete()

    def test_answer_records_and_advances(self):
        """Answer should record value and advance step."""
        session = PromptSession()
        session.add_seat_step("Choose:", [0, 1], allow_none=False)
        session.add_seat_step("Vote for:", [2, 3], allow_none=False)

        assert session.current_step == 0

        session.answer("0")

        assert session.collected["step_0"] == "0"
        assert session.current_step == 1

    def test_get_result_witch_format(self):
        """Witch format should handle action + target."""
        session = PromptSession()
        session.add_action_step("Action:", [("PASS", "Pass"), ("POISON", "Poison")], allow_none=False)
        session.add_seat_step("Target:", [5], allow_none=False)

        session.answer("POISON")
        session.answer("5")

        result = session.get_result("witch")

        assert result == "POISON 5"

    def test_get_result_witch_pass(self):
        """Witch format with PASS action should return PASS."""
        session = PromptSession()
        session.add_action_step("Action:", [("PASS", "Pass")], allow_none=False)

        session.answer("PASS")

        result = session.get_result("witch")

        assert result == "PASS"

    def test_get_result_vote_format(self):
        """Vote format should return target or abstain."""
        session = PromptSession()
        session.add_vote_step("Vote:", [0, 1], allow_none=True)

        session.answer("0")

        result = session.get_result("vote")

        assert result == "0"

    def test_get_result_vote_abstain(self):
        """Vote format with no answer should return abstain."""
        session = PromptSession()
        session.add_vote_step("Vote:", [0, 1], allow_none=True)

        # No answers
        result = session.get_result("vote")

        assert result == "abstain"

    def test_get_result_simple_format(self):
        """Simple format should return first answer."""
        session = PromptSession()
        session.add_text_step("Speech:")

        session.answer("Hello world")

        result = session.get_result("simple")

        assert result == "Hello world"

    def test_chaining_builders(self):
        """Builder methods should support chaining."""
        session = (
            PromptSession()
            .add_action_step("Action:", [("PASS", "Pass")], allow_none=False)
            .add_seat_step("Target:", [1, 2], allow_none=True)
        )

        assert len(session.steps) == 2

    def test_current_prompt_returns_step(self):
        """current_prompt should return current step or None if complete."""
        session = PromptSession()
        session.add_action_step("Step 1:", [("A", "A")], allow_none=False)
        session.add_action_step("Step 2:", [("B", "B")], allow_none=False)

        assert session.current_prompt() == session.steps[0]
        session.answer("A")
        assert session.current_prompt() == session.steps[1]
        session.answer("B")
        assert session.current_prompt() is None


# ============================================================================
# Builder Function Tests
# ============================================================================

class TestBuilderFunctions:
    """Tests: PromptSession builder functions."""

    def test_witch_action_session_no_potions(self):
        """Witch with no potions should have minimal session."""
        session = witch_action_session(
            living_players=[0, 1, 2, 3],
            witch_seat=0,
            antidote_available=False,
            poison_available=False,
            kill_target=5,
        )

        assert len(session.steps) == 1
        assert session.steps[0].prompt_type == PromptType.ACTION

    def test_witch_action_session_with_antidote(self):
        """Witch with antidote should show antidote option."""
        session = witch_action_session(
            living_players=[0, 1, 2, 3],
            witch_seat=0,
            antidote_available=True,
            poison_available=False,
            kill_target=5,
        )

        action_step = session.steps[0]
        values = [opt.value for opt in action_step.options]
        assert "ANTIDOTE" in values

    def test_witch_action_session_with_poison(self):
        """Witch with poison should show poison option."""
        session = witch_action_session(
            living_players=[0, 1, 2, 3],
            witch_seat=0,
            antidote_available=False,
            poison_available=True,
            kill_target=None,
        )

        action_step = session.steps[0]
        values = [opt.value for opt in action_step.options]
        assert "POISON" in values

    def test_witch_action_session_no_antidote_on_self(self):
        """Antidote should not be offered if kill target is witch self."""
        session = witch_action_session(
            living_players=[0, 1, 2, 3],
            witch_seat=0,
            antidote_available=True,
            poison_available=True,
            kill_target=0,  # Witch self-target (edge case)
        )

        action_step = session.steps[0]
        values = [opt.value for opt in action_step.options]
        assert "ANTIDOTE" not in values  # Can't antidote self

    def test_witch_action_session_both_potions(self):
        """Witch with both potions should show both options."""
        session = witch_action_session(
            living_players=[0, 1, 2, 3],
            witch_seat=0,
            antidote_available=True,
            poison_available=True,
            kill_target=5,
        )

        action_step = session.steps[0]
        values = [opt.value for opt in action_step.options]
        assert "PASS" in values
        assert "ANTIDOTE" in values
        assert "POISON" in values

    def test_guard_action_session(self):
        """Guard session should exclude previous target."""
        session = guard_action_session(
            living_players=[0, 1, 2, 3, 4],
            prev_guarded=2,
        )

        seat_step = session.steps[0]
        seat_values = [opt.value for opt in seat_step.options]

        assert "2" not in seat_values  # Previous target excluded
        assert len(seat_values) == 4  # All except prev

    def test_guard_action_session_no_prev(self):
        """Guard with no prev target should include all living."""
        session = guard_action_session(
            living_players=[0, 1, 2, 3],
            prev_guarded=None,
        )

        seat_values = [opt.value for opt in session.steps[0].options]

        assert set(seat_values) == {"0", "1", "2", "3"}

    def test_guard_action_session_can_protect_self(self):
        """Guard session should allow protecting self."""
        session = guard_action_session(
            living_players=[0, 1, 2],
            prev_guarded=None,
        )

        seat_values = [opt.value for opt in session.steps[0].options]
        assert "0" in seat_values  # Guard can protect self

    def test_voting_session(self):
        """Voting session should filter dead candidates."""
        session = voting_session(
            candidates=[0, 1, 2, 3, 4],
            living_players={0, 2, 4},
        )

        vote_step = session.steps[0]
        # Only living candidates
        values = [opt.value for opt in vote_step.options]
        assert set(values) == {"0", "2", "4"}

    def test_voting_session_all_dead(self):
        """Voting session with all dead should have empty options."""
        session = voting_session(
            candidates=[0, 1],
            living_players=set(),  # All dead
        )

        vote_step = session.steps[0]
        values = [opt.value for opt in vote_step.options]
        assert len(values) == 0

    def test_sheriff_vote_session(self):
        """Sheriff vote should include all candidates."""
        session = sheriff_vote_session(candidates=[0, 1, 3])

        assert session.steps[0].prompt_type == PromptType.VOTE
        values = [opt.value for opt in session.steps[0].options]
        assert set(values) == {"0", "1", "3"}

    def test_opt_out_session(self):
        """Opt-out session should be confirm type."""
        session = opt_out_session()

        assert session.steps[0].prompt_type == PromptType.CONFIRM


# ============================================================================
# ChoiceSpec Tests
# ============================================================================

class TestChoiceSpec:
    """Tests: ChoiceSpec creation and helpers."""

    def test_make_seat_choice_basic(self):
        """make_seat_choice should create valid ChoiceSpec."""
        choices = make_seat_choice(
            prompt="Choose a player:",
            seats=[0, 1, 2],
            allow_none=False,
        )

        assert choices.choice_type == ChoiceType.SEAT
        assert choices.prompt == "Choose a player:"
        assert len(choices.options) == 3
        assert choices.options[0].value == "0"
        assert choices.options[0].seat_hint == 0

    def test_make_seat_choice_with_info(self):
        """make_seat_choice with seat_info should populate display names."""
        choices = make_seat_choice(
            prompt="Check role:",
            seats=[0, 3, 7],
            seat_info={3: "Werewolf", 7: "Seer"},
            allow_none=True,
        )

        assert choices.seat_info[3] == "Werewolf"
        assert choices.seat_info[7] == "Seer"
        assert choices.allow_none is True
        assert choices.none_display == "Skip / Pass"

    def test_make_seat_choice_excludes_none_option(self):
        """allow_none=False should not include skip option in options."""
        choices = make_seat_choice(
            prompt="Choose:",
            seats=[0, 1],
            allow_none=False,
        )

        assert choices.allow_none is False
        # Note: none_display still has default value 'Skip / Pass' in the model
        # but since allow_none=False, no skip option is added to options

    def test_choice_spec_get_option_by_value(self):
        """get_option_by_value should find matching option."""
        choices = ChoiceSpec(
            choice_type=ChoiceType.SEAT,
            prompt="Test",
            options=[
                ChoiceOption(value="0", display="Player 0"),
                ChoiceOption(value="5", display="Player 5"),
            ],
            allow_none=False,
        )

        opt = choices.get_option_by_value("5")
        assert opt is not None
        assert opt.display == "Player 5"

    def test_choice_spec_get_option_by_value_missing(self):
        """get_option_by_value should return None for missing value."""
        choices = ChoiceSpec(
            choice_type=ChoiceType.SEAT,
            prompt="Test",
            options=[
                ChoiceOption(value="0", display="Player 0"),
            ],
            allow_none=False,
        )

        opt = choices.get_option_by_value("999")
        assert opt is None

    def test_choice_spec_get_seat_display(self):
        """get_seat_display should return formatted name."""
        choices = ChoiceSpec(
            choice_type=ChoiceType.SEAT,
            prompt="Test",
            options=[],
            allow_none=False,
            seat_info={5: "Werewolf"},
        )

        assert choices.get_seat_display(5) == "Player 5 (Werewolf)"
        assert choices.get_seat_display(3) == "Player 3"

    def test_choice_spec_format_response_seat(self):
        """format_response should parse seat numbers."""
        choices = ChoiceSpec(
            choice_type=ChoiceType.SEAT,
            prompt="Test",
            options=[],
            allow_none=False,
        )

        assert choices.format_response("7") == "7"

    def test_choice_spec_format_response_boolean(self):
        """format_response should normalize boolean responses."""
        choices = ChoiceSpec(
            choice_type=ChoiceType.BOOLEAN,
            prompt="Test",
            options=[
                ChoiceOption(value="yes", display="Yes"),
                ChoiceOption(value="no", display="No"),
            ],
            allow_none=False,
        )

        assert choices.format_response("Y") == "yes"
        assert choices.format_response("TRUE") == "yes"
        assert choices.format_response("N") == "no"


# ============================================================================
# PromptStep and PromptOption Tests
# ============================================================================

class TestPromptStepAndOption:
    """Tests: PromptStep and PromptOption models."""

    def test_prompt_option_defaults(self):
        """PromptOption should have None seat_hint by default."""
        opt = PromptOption(value="test", display="Test")
        assert opt.seat_hint is None

    def test_prompt_step_defaults(self):
        """PromptStep should have sensible defaults."""
        step = PromptStep(
            prompt_type=PromptType.TEXT,
            prompt_text="Enter text:",
        )
        assert step.options == []
        assert step.allow_none is False
        assert step.none_display == "Skip / Pass"
        assert step.seat_info == {}
        assert step.validator is None

    def test_prompt_session_defaults(self):
        """PromptSession should have empty defaults."""
        session = PromptSession()
        assert session.steps == []
        assert session.current_step == 0
        assert session.collected == {}


# ============================================================================
# PromptType Tests
# ============================================================================

class TestPromptType:
    """Tests: PromptType enum."""

    def test_prompt_type_values(self):
        """PromptType should have expected string values."""
        assert PromptType.ACTION.value == "action"
        assert PromptType.SEAT.value == "seat"
        assert PromptType.VOTE.value == "vote"
        assert PromptType.TEXT.value == "text"
        assert PromptType.CONFIRM.value == "confirm"


# ============================================================================
# Run tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
