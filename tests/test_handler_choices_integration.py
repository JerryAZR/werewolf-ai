"""Tests: Handler-Choices-StubPlayer integration.

Tests that verify:
1. Handlers supply valid choice lists to participant.decide()
2. Handlers don't reject valid choices when provided
3. Stub AIs return valid choices when instructed

These tests expose the bug where handlers don't pass `choices` parameter
even though the Participant Protocol defines it.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Optional

from werewolf.models import Player, Role, create_players_from_config
from werewolf.handlers.seer_handler import SeerHandler, PhaseContext as SeerContext
from werewolf.handlers.guard_handler import GuardHandler, PhaseContext as GuardContext
from werewolf.handlers.witch_handler import WitchHandler
from werewolf.handlers.werewolf_handler import WerewolfHandler
from werewolf.ai.stub_ai import StubPlayer, create_stub_player
from werewolf.ui.choices import ChoiceSpec, ChoiceOption, make_seat_choice


def create_players_shuffled(seed: Optional[int] = None) -> dict[int, Player]:
    """Create standard 12-player config."""
    import random
    rng = random.Random(seed)
    role_assignments = create_players_from_config(rng=rng)
    players = {}
    for seat, role in role_assignments:
        players[seat] = Player(seat=seat, name=f"Player {seat}", role=role)
    return players


# ============================================================================
# Test 1: Verify handlers pass choices parameter to participant.decide()
# ============================================================================

class TestHandlerPassesChoices:
    """Tests: Verify handlers pass choices parameter."""

    @pytest.mark.asyncio
    async def test_seer_handler_should_pass_choices(self):
        """SeerHandler MUST pass choices parameter to avoid invalid self-targets."""
        players = create_players_shuffled(seed=42)
        living = set(players.keys())

        # Find seer seat
        seer_seat = None
        for seat, player in players.items():
            if player.role == Role.SEER and seat in living:
                seer_seat = seat
                break

        assert seer_seat is not None, "Seer not found in config"

        # Create mock participant that records calls
        mock_participant = AsyncMock()
        mock_participant.decide = AsyncMock(return_value="0")

        context = SeerContext(
            players=players,
            living_players=living,
            dead_players=set(),
            sheriff=None,
            day=1,
        )

        handler = SeerHandler()
        await handler(context, [(seer_seat, mock_participant)])

        # Verify that choices WAS PASSED (not None)
        # This test FAILS if handler doesn't pass choices
        call_args = mock_participant.decide.call_args
        assert call_args is not None, "participant.decide() was not called"

        # Get the 'choices' keyword argument
        choices_passed = call_args.kwargs.get('choices')

        # FAILURE: If choices is None, the handler is not doing its job
        assert choices_passed is not None, (
            "BUG: SeerHandler did not pass 'choices' parameter to participant.decide(). "
            "This causes StubPlayer to pick invalid targets (including self)."
        )

        # Verify choices contains valid options (not self)
        if hasattr(choices_passed, 'options'):
            values = [opt.value for opt in choices_passed.options]
        elif isinstance(choices_passed, list):
            values = [str(v) if not isinstance(v, str) else v for v in choices_passed]
        else:
            values = []

        assert str(seer_seat) not in values, (
            f"BUG: Choices included self-target (seat {seer_seat}). "
            "Handler should filter out own seat from choices."
        )

    @pytest.mark.asyncio
    async def test_guard_handler_should_pass_choices(self):
        """GuardHandler MUST pass choices parameter."""
        players = create_players_shuffled(seed=42)
        living = set(players.keys())

        # Find guard seat
        guard_seat = None
        for seat, player in players.items():
            if player.role == Role.GUARD and seat in living:
                guard_seat = seat
                break

        assert guard_seat is not None, "Guard not found in config"

        mock_participant = AsyncMock()
        mock_participant.decide = AsyncMock(return_value="0")

        context = GuardContext(
            players=players,
            living_players=living,
            dead_players=set(),
            sheriff=None,
            day=1,
        )

        handler = GuardHandler()
        await handler(context, [(guard_seat, mock_participant)], guard_prev_target=None)

        # Verify choices was passed
        call_args = mock_participant.decide.call_args
        assert call_args is not None

        choices_passed = call_args.kwargs.get('choices')
        assert choices_passed is not None, (
            "BUG: GuardHandler did not pass 'choices' parameter to participant.decide(). "
            "This causes StubPlayer to pick invalid targets."
        )

    @pytest.mark.asyncio
    async def test_werewolf_handler_should_pass_choices(self):
        """WerewolfHandler MUST pass choices parameter."""
        players = create_players_shuffled(seed=42)
        living = set(players.keys())

        # Find werewolf seats
        ww_seats = [s for s, p in players.items() if p.role == Role.WEREWOLF and s in living]
        assert ww_seats, "No werewolves found"

        mock_participant = AsyncMock()
        mock_participant.decide = AsyncMock(return_value="5")

        # Create context with is_werewolf method (WerewolfHandler requires it)
        class WerewolfContext:
            def __init__(self, players, living_players, dead_players, sheriff, day):
                self.players = players
                self.living_players = living_players
                self.dead_players = dead_players
                self.sheriff = sheriff
                self.day = day

            def is_werewolf(self, seat):
                player = self.players.get(seat)
                return player is not None and player.role == Role.WEREWOLF

        context = WerewolfContext(
            players=players,
            living_players=living,
            dead_players=set(),
            sheriff=None,
            day=1,
        )

        handler = WerewolfHandler()
        await handler(context, [(ww_seats[0], mock_participant)])

        call_args = mock_participant.decide.call_args
        choices_passed = call_args.kwargs.get('choices') if call_args else None
        assert choices_passed is not None, (
            "BUG: WerewolfHandler did not pass 'choices' parameter to participant.decide()."
        )


# ============================================================================
# Test 2: StubPlayer correctly uses choices when provided
# ============================================================================

class TestStubPlayerChoices:
    """Tests: StubPlayer properly respects choices parameter."""

    @pytest.mark.asyncio
    async def test_stub_returns_valid_choice_when_choices_provided(self):
        """When choices are provided, StubPlayer MUST return one of them."""
        stub = StubPlayer(seed=123)

        # Provide specific choices as list of tuples (label, value)
        choices = [
            ("Player 2", "2"),
            ("Player 4", "4"),
            ("Player 6", "6"),
            ("Player 8", "8"),
        ]

        # Run multiple times to ensure consistency
        responses = []
        for _ in range(10):
            response = await stub.decide("", "", choices=choices)
            responses.append(response)

        # All responses should be from the valid choices
        valid_values = {"2", "4", "6", "8"}
        for response in responses:
            assert response in valid_values, (
                f"BUG: StubPlayer returned '{response}' which is not in valid choices {valid_values}"
            )

    @pytest.mark.asyncio
    async def test_stub_respects_exclude_self_in_choices(self):
        """When choices exclude self, StubPlayer should respect that."""
        stub = StubPlayer(seed=456)

        # Choices that don't include seat 5
        choices = make_seat_choice(
            prompt="Check a player",
            seats=[0, 1, 2, 3, 4, 6, 7, 8, 9, 10, 11],  # All except 5
            allow_none=False,
        )

        responses = [await stub.decide("", "", choices=choices) for _ in range(20)]

        # Should never pick 5
        assert "5" not in responses, (
            "BUG: StubPlayer returned '5' which was not in the valid choices"
        )

    @pytest.mark.asyncio
    async def test_stub_with_choice_spec_options(self):
        """StubPlayer handles ChoiceSpec.options correctly.

        This test uses ACTUAL ChoiceSpec with ChoiceOption objects.
        BUG: _choose_from_spec returns the full ChoiceOption object
        instead of just the value when options are ChoiceOption objects.
        """
        stub = StubPlayer(seed=789)

        # Use actual ChoiceSpec with ChoiceOption objects - THIS EXPOSES THE BUG
        choices = ChoiceSpec(
            choice_type="seat",
            prompt="Choose target",
            options=[
                ChoiceOption(value="3", display="Player 3"),
                ChoiceOption(value="7", display="Player 7"),
                ChoiceOption(value="9", display="Player 9"),
            ],
            allow_none=False,
        )

        responses = [await stub.decide("", "", choices=choices) for _ in range(10)]

        valid = {"3", "7", "9"}
        for response in responses:
            # This assertion will FAIL if StubPlayer returns ChoiceOption instead of value
            assert response in valid, (
                f"BUG: StubPlayer returned '{response}' (type: {type(response).__name__}), "
                f"expected one of {valid}"
            )


# ============================================================================
# Test 3: Handler accepts valid choices without rejection
# ============================================================================

class TestHandlerAcceptsChoices:
    """Tests: Handlers should accept valid choices when provided."""

    @pytest.mark.asyncio
    async def test_seer_accepts_valid_target_from_choices(self):
        """SeerHandler should accept a valid target from choices without hinting."""
        players = create_players_shuffled(seed=42)
        living = set(players.keys())

        # Find seer
        seer_seat = None
        for seat, player in players.items():
            if player.role == Role.SEER and seat in living:
                seer_seat = seat
                break

        # Find a valid target (not self)
        valid_target = next((s for s in living if s != seer_seat), None)

        # Create mock that always returns valid target
        mock_participant = AsyncMock()
        mock_participant.decide = AsyncMock(return_value=str(valid_target))

        context = SeerContext(
            players=players,
            living_players=living,
            dead_players=set(),
            sheriff=None,
            day=1,
        )

        handler = SeerHandler()

        # Call with a mock that records if hints are sent
        hints_sent = []
        original_decide = mock_participant.decide

        async def capture_hint(*args, **kwargs):
            hint = kwargs.get('hint')
            hints_sent.append(hint)
            return str(valid_target)

        mock_participant.decide = AsyncMock(side_effect=capture_hint)

        result = await handler(context, [(seer_seat, mock_participant)])

        # Get any hints sent
        hints_with_content = [h for h in hints_sent if h]

        # If handler properly provided choices, no hints should be needed
        # But if choices weren't provided and we got lucky, that's still a bug
        # This test documents expected behavior

        # The real test: did handler pass choices?
        call_args = mock_participant.decide.call_args
        choices_passed = call_args.kwargs.get('choices') if call_args else None

        # FAILURE POINT: If choices not passed, handler relies on luck
        assert choices_passed is not None, (
            "FAIL: Handler didn't pass choices - valid response was luck, not design"
        )


# ============================================================================
# Test 4: End-to-end with real StubPlayer (this should pass after fix)
# ============================================================================

class TestEndToEndChoices:
    """End-to-end tests: Full handler + StubPlayer with choices."""

    @pytest.mark.asyncio
    async def test_seer_with_mock_self_target(self):
        """SeerHandler should pass choices to prevent self-target failures.

        This test uses a Mock that ALWAYS returns self-target to deterministically
        expose the bug. Without choices parameter, handler relies on retries,
        which can still fail (0.06% chance per attempt).
        """
        players = create_players_shuffled(seed=999)
        living = set(players.keys())

        seer_seat = None
        for seat, player in players.items():
            if player.role == Role.SEER and seat in living:
                seer_seat = seat
                break

        # Create mock that ALWAYS returns self
        mock_self_participant = AsyncMock()
        mock_self_participant.decide = AsyncMock(return_value=str(seer_seat))

        context = SeerContext(
            players=players,
            living_players=living,
            dead_players=set(),
            sheriff=None,
            day=1,
        )

        handler = SeerHandler()

        # Call should fail because handler doesn't filter self from prompt
        # and mock returns self (which is a valid digit but invalid target)
        with pytest.raises(Exception) as exc_info:
            await handler(context, [(seer_seat, mock_self_participant)])

        # This exposes the bug: handler should have passed choices
        # so that StubPlayer (or any participant) knows not to pick self
        assert "MaxRetriesExceededError" in str(exc_info.value) or "cannot check yourself" in str(exc_info.value), (
            f"Unexpected exception: {exc_info.value}"
        )

    @pytest.mark.asyncio
    async def test_seer_with_stub_always_gets_valid_target(self):
        """SeerHandler + StubPlayer should NEVER produce MaxRetriesExceededError.

        This test runs many iterations with actual StubPlayer to catch the bug.
        With 12 players, ~8% chance of self-target per iteration.
        """
        players = create_players_shuffled(seed=999)
        living = set(players.keys())

        seer_seat = None
        for seat, player in players.items():
            if player.role == Role.SEER and seat in living:
                seer_seat = seat
                break

        context = SeerContext(
            players=players,
            living_players=living,
            dead_players=set(),
            sheriff=None,
            day=1,
        )

        handler = SeerHandler()

        # Run 1000 iterations - any failure exposes the bug
        failures = 0
        for i in range(1000):
            # Create fresh stub each time (different seed each iteration)
            stub = create_stub_player(seed=555 + i)
            try:
                result = await handler(context, [(seer_seat, stub)])
                event = result.subphase_log.events[0]
                # Verify valid target
                assert event.target in living, f"Invalid target {event.target}"
                assert event.target != seer_seat, (
                    f"BUG: Handler allowed self-target. "
                    f"Handler must pass 'choices' to prevent this."
                )
            except Exception as e:
                failures += 1

        assert failures == 0, (
            f"BUG: {failures}/1000 iterations raised exceptions. "
            f"Handler must pass 'choices' to guarantee valid responses."
        )


# ============================================================================
# Run tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
