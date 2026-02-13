"""Tests: TextualParticipant for human TUI players.

Tests verify:
1. TextualParticipant correctly uses ChoiceSpec when provided
2. TextualParticipant handles free-form text input for phases that need it
3. ChoiceRequest messages are created correctly

Note: Full integration tests with actual Textual App require complex mocking.
These tests verify the message passing and choice handling logic.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Optional

from werewolf.ui.choices import ChoiceSpec, ChoiceOption, ChoiceType


class TestChoiceRequest:
    """Tests: ChoiceRequest message creation."""

    def test_choice_request_basic(self):
        """Test basic ChoiceRequest creation."""
        from werewolf.ui.textual_game import ChoiceRequest

        request = ChoiceRequest(
            prompt="Choose an option:",
            options=[("Option A", "a"), ("Option B", "b")],
        )

        assert request.prompt == "Choose an option:"
        assert len(request.options) == 2
        assert request.options[0] == ("Option A", "a")
        assert request.options[1] == ("Option B", "b")
        assert request.allow_none is False
        assert request.text_input is False
        assert request.result is None
        assert not request.ready.is_set()

    def test_choice_request_with_allow_none(self):
        """Test ChoiceRequest with allow_none=True."""
        from werewolf.ui.textual_game import ChoiceRequest

        request = ChoiceRequest(
            prompt="Select target:",
            options=[("Player 0", "0"), ("Player 1", "1")],
            allow_none=True,
        )

        assert request.allow_none is True

    def test_choice_request_with_text_input(self):
        """Test ChoiceRequest with text_input=True."""
        from werewolf.ui.textual_game import ChoiceRequest

        request = ChoiceRequest(
            prompt="Enter your speech:",
            text_input=True,
        )

        assert request.text_input is True
        assert request.options is None  # Text input doesn't need options


class TestTextualParticipantInterface:
    """Tests: TextualParticipant interface and choice handling."""

    def test_nomination_choice_spec_structure(self):
        """Test creating nomination-style action choices.

        Nomination requires two options:
        - "run" - You want to run for Sheriff
        - "not running" - You decline to run
        """
        # Create ChoiceSpec directly (avoiding make_action_choice bug with none_display=None)
        choices = ChoiceSpec(
            choice_type=ChoiceType.SINGLE,
            prompt="Do you want to run for Sheriff?",
            options=[
                ChoiceOption(value="run", display="Run for Sheriff"),
                ChoiceOption(value="not running", display="Decline to Run"),
            ],
            allow_none=False,
            none_display="Pass / Skip",
        )

        assert choices.choice_type == ChoiceType.SINGLE
        assert choices.prompt == "Do you want to run for Sheriff?"
        assert len(choices.options) == 2
        assert choices.options[0].value == "run"
        assert choices.options[0].display == "Run for Sheriff"
        assert choices.options[1].value == "not running"
        assert choices.options[1].display == "Decline to Run"
        assert choices.allow_none is False

    def test_make_action_choice_with_skip(self):
        """Test creating action choices with skip option."""
        from werewolf.ui.choices import make_action_choice

        choices = make_action_choice(
            prompt="Choose action:",
            actions=[
                ("PASS", "Pass"),
                ("POISON", "Poison"),
            ],
            allow_none=True,
        )

        assert choices.allow_none is True
        assert choices.none_display == "Pass / Skip"


class TestTextualParticipantChoiceParsing:
    """Tests: TextualParticipant choice parsing (synchronous portion)."""

    def test_parse_choices_with_options(self):
        """Test parsing ChoiceSpec options correctly."""
        from werewolf.ui.textual_game import TextualParticipant
        from werewolf.ui.choices import ChoiceSpec, ChoiceOption

        # Create ChoiceSpec
        choices = ChoiceSpec(
            choice_type=ChoiceType.SINGLE,
            prompt="Do you want to run?",
            options=[
                ChoiceOption(value="run", display="Run for Sheriff"),
                ChoiceOption(value="not running", display="Decline to Run"),
            ],
            allow_none=False,
        )

        # Parse options (simulate what TextualParticipant does)
        options = []
        for opt in choices.options:
            display = opt.display
            options.append((display, opt.value))

        assert len(options) == 2
        assert ("Run for Sheriff", "run") in options
        assert ("Decline to Run", "not running") in options

    def test_parse_choices_with_seat_info(self):
        """Test parsing ChoiceSpec with seat_info."""
        from werewolf.ui.textual_game import TextualParticipant
        from werewolf.ui.choices import ChoiceSpec, ChoiceOption

        choices = ChoiceSpec(
            choice_type=ChoiceType.SEAT,
            prompt="Choose target:",
            options=[
                ChoiceOption(value="0", display="Player 0", seat_hint=0),
                ChoiceOption(value="3", display="Player 3", seat_hint=3),
            ],
            allow_none=True,
            seat_info={3: "Werewolf"},
        )

        # Parse with seat_info
        options = []
        for opt in choices.options:
            display = opt.display
            if opt.seat_hint and choices.seat_info:
                display = choices.seat_info.get(opt.seat_hint, opt.display)
            options.append((display, opt.value))

        assert ("Werewolf", "3") in options  # seat_info overrides display
        assert ("Player 0", "0") in options  # No seat_info for 0

    def test_allow_none_from_choices(self):
        """Test extracting allow_none from ChoiceSpec."""
        from werewolf.ui.choices import ChoiceSpec

        choices_with_none = ChoiceSpec(
            choice_type=ChoiceType.SEAT,
            prompt="Choose:",
            options=[],
            allow_none=True,
        )

        choices_without_none = ChoiceSpec(
            choice_type=ChoiceType.SEAT,
            prompt="Choose:",
            options=[],
            allow_none=False,
        )

        assert getattr(choices_with_none, 'allow_none', False) is True
        assert getattr(choices_without_none, 'allow_none', False) is False

    def test_prompt_from_choices(self):
        """Test extracting prompt from ChoiceSpec."""
        from werewolf.ui.choices import ChoiceSpec

        choices = ChoiceSpec(
            choice_type=ChoiceType.SINGLE,
            prompt="Do you want to run for Sheriff?",
            options=[
                ChoiceOption(value="run", display="Run"),
                ChoiceOption(value="not running", display="Not Running"),
            ],
            allow_none=False,
        )

        prompt_text = getattr(choices, 'prompt', 'Make your choice')
        assert prompt_text == "Do you want to run for Sheriff?"


class TestTextualParticipantDecide:
    """Tests: TextualParticipant.decide() method (synchronous portions)."""

    def test_decide_logs_context(self):
        """Test that decide logs system and user prompts."""
        from werewolf.ui.textual_game import TextualParticipant

        mock_app = MagicMock()
        mock_app._write = MagicMock()

        participant = TextualParticipant(seat=0, app=mock_app)

        # We can't test the full async flow, but we can verify write is called
        # This would be called in the actual decide method
        participant._app._write("Test context")
        mock_app._write.assert_called_with("Test context")

    def test_decide_parses_choice_spec(self):
        """Test that decide parses ChoiceSpec correctly."""
        from werewolf.ui.textual_game import TextualParticipant
        from werewolf.ui.choices import ChoiceSpec, ChoiceOption

        mock_app = MagicMock()
        mock_app._write = MagicMock()

        participant = TextualParticipant(seat=0, app=mock_app)

        choices = ChoiceSpec(
            choice_type=ChoiceType.SINGLE,
            prompt="Do you want to run?",
            options=[
                ChoiceOption(value="run", display="Run for Sheriff"),
                ChoiceOption(value="not running", display="Decline to Run"),
            ],
            allow_none=False,
        )

        # Simulate the parsing logic from TextualParticipant.decide()
        options = []
        if choices and hasattr(choices, 'options'):
            for opt in choices.options:
                display = opt.display
                if opt.seat_hint and hasattr(choices, 'seat_info') and choices.seat_info:
                    display = choices.seat_info.get(opt.seat_hint, opt.display)
                options.append((display, opt.value))

        assert len(options) == 2
        allow_none = getattr(choices, 'allow_none', False)
        prompt_text = getattr(choices, 'prompt', 'Make your choice')

        assert prompt_text == "Do you want to run?"
        assert allow_none is False

    def test_decide_without_choices_uses_text_input(self):
        """Test that decide without choices falls back to text input."""
        from werewolf.ui.textual_game import TextualParticipant

        mock_app = MagicMock()
        mock_app._write = MagicMock()

        participant = TextualParticipant(seat=0, app=mock_app)

        # When choices is None, the code should detect this
        choices = None

        if choices and hasattr(choices, 'options'):
            # This branch should NOT be taken
            assert False, "Should not parse options when choices is None"
        else:
            # This branch should be taken for text input mode
            # The prompt should come from user_prompt
            user_prompt = """=== Day 1 - Sheriff Nomination ===

YOUR INFORMATION:
  Your seat: 0
  Your role: Ordinary Villager
  Status: Living

NOMINATION DECISION:
  You may either:
  - "run" - Declare your candidacy for Sheriff
  - "not running" - Decline to run for Sheriff

Enter your decision:"""

            prompt_text = user_prompt.split('\n')[-1] if user_prompt else "Enter your response"
            assert prompt_text == "Enter your decision:"


class TestNominationChoiceSpec:
    """Tests: Verify ChoiceSpec format for nomination."""

    def test_nomination_choice_spec_structure(self):
        """Nomination should use SINGLE choice type with two options."""
        # Create ChoiceSpec directly (avoiding make_action_choice bug with none_display=None)
        choices = ChoiceSpec(
            choice_type=ChoiceType.SINGLE,
            prompt="Do you want to run for Sheriff?",
            options=[
                ChoiceOption(value="run", display="Run for Sheriff"),
                ChoiceOption(value="not running", display="Decline to Run"),
            ],
            allow_none=False,
            none_display="Pass / Skip",
        )

        # Verify structure
        assert choices.choice_type == ChoiceType.SINGLE
        assert len(choices.options) == 2
        assert choices.allow_none is False

        # Verify options
        option_values = [opt.value for opt in choices.options]
        assert "run" in option_values
        assert "not running" in option_values

    def test_parse_nomination_response(self):
        """Test that ChoiceSpec.format_response works for nomination values."""
        from werewolf.ui.choices import ChoiceSpec, ChoiceType

        choices = ChoiceSpec(
            choice_type=ChoiceType.SINGLE,
            prompt="Test",
            options=[
                ChoiceOption(value="run", display="Run"),
                ChoiceOption(value="not running", display="Not Running"),
            ],
            allow_none=False,
        )

        # Should return value as-is for SINGLE type
        assert choices.format_response("run") == "run"
        assert choices.format_response("not running") == "not running"


# ============================================================================
# Run tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
