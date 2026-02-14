"""Comprehensive tests for Nomination handler.

Nomination subphase: Day 1 all players decide if they want to run for Sheriff.
Rules:
- Only Day 1
- All players (living and dead) can nominate
- Response must be "run" or "not running"
- Default to "not running" on invalid response
"""

import pytest
from typing import Optional, Any
from unittest.mock import AsyncMock, MagicMock

from werewolf.events import (
    SheriffNomination,
    Phase,
    SubPhase,
    SubPhaseLog,
)
from werewolf.models import (
    Player,
    Role,
    PlayerType,
)


# ============================================================================
# Mock Participant for Testing
# ============================================================================


class MockParticipant:
    """Mock participant that returns configurable responses."""

    def __init__(
        self,
        response: str | None = None,
        response_iter: list[str] | None = None,
        is_human: bool = False,
    ):
        """Initialize with a single response or an iterator of responses.

        Args:
            response: Single response string to return
            response_iter: Optional list of responses to return in sequence
            is_human: Whether this mock represents a human player
        """
        self._response = response
        self._response_iter = response_iter
        self._call_count = 0
        self._is_human = is_human

    @property
    def is_human(self) -> bool:
        """Whether this is a human player."""
        return self._is_human

    async def decide(
        self,
        system_prompt: str,
        user_prompt: str,
        **extra: Any
    ) -> str:
        """Return configured response."""
        self._call_count += 1
        if self._response_iter and self._call_count <= len(self._response_iter):
            return self._response_iter[self._call_count - 1]
        if self._response is not None:
            return self._response
        raise ValueError("MockParticipant: no response configured")


# ============================================================================
# PhaseContext Fixture Factory
# ============================================================================


class PhaseContext:
    """Minimal context for testing Nomination handler."""

    def __init__(
        self,
        players: dict[int, Player],
        living_players: set[int],
        dead_players: set[int],
        sheriff: Optional[int] = None,
        day: int = 1,
    ):
        self.players = players
        self.living_players = living_players
        self.dead_players = dead_players
        self.sheriff = sheriff
        self.day = day

    def get_player(self, seat: int) -> Optional[Player]:
        """Get player by seat."""
        return self.players.get(seat)

    def is_alive(self, seat: int) -> bool:
        """Check if a player is alive."""
        return seat in self.living_players


def make_context_day1_standard() -> tuple[PhaseContext, dict[int, MockParticipant]]:
    """Create standard Day 1 context with 12 players (all alive)."""
    players = {
        seat: Player(seat=seat, name=f"Player_{seat}", role=Role.VILLAGER, player_type=PlayerType.AI)
        for seat in range(12)
    }

    living_players = set(range(12))
    dead_players: set[int] = set()

    context = PhaseContext(
        players=players,
        living_players=living_players,
        dead_players=dead_players,
        sheriff=None,
        day=1,
    )

    # All players want to run
    participants = {
        seat: MockParticipant(response="run")
        for seat in range(12)
    }

    return context, participants


def make_context_with_some_nominating() -> tuple[PhaseContext, dict[int, MockParticipant]]:
    """Create context where only some players nominate."""
    players = {
        seat: Player(seat=seat, name=f"Player_{seat}", role=Role.VILLAGER, player_type=PlayerType.AI)
        for seat in range(12)
    }

    living_players = set(range(12))
    dead_players: set[int] = set()

    context = PhaseContext(
        players=players,
        living_players=living_players,
        dead_players=dead_players,
        sheriff=None,
        day=1,
    )

    # Only seats 0, 3, 6, 9 want to run
    participants = {
        seat: MockParticipant(response="run") if seat in [0, 3, 6, 9] else MockParticipant(response="not running")
        for seat in range(12)
    }

    return context, participants


def make_context_with_dead_players() -> tuple[PhaseContext, dict[int, MockParticipant]]:
    """Create context where some players are dead."""
    players = {
        seat: Player(seat=seat, name=f"Player_{seat}", role=Role.VILLAGER, player_type=PlayerType.AI)
        for seat in range(12)
    }

    living_players = {0, 1, 2, 4, 5, 7, 8, 10, 11}
    dead_players = {3, 6, 9}

    context = PhaseContext(
        players=players,
        living_players=living_players,
        dead_players=dead_players,
        sheriff=None,
        day=1,
    )

    # Dead players can still nominate
    participants = {
        seat: MockParticipant(response="run")
        for seat in range(12)
    }

    return context, participants


# ============================================================================
# Tests
# ============================================================================


@pytest.mark.asyncio
async def test_nomination_all_players_run():
    """Test when all players decide to run for Sheriff."""
    from werewolf.handlers.nomination_handler import NominationHandler

    context, participants = make_context_day1_standard()
    handler = NominationHandler()

    result = await handler(context, list(participants.items()))

    assert result.subphase_log.micro_phase == SubPhase.NOMINATION
    assert len(result.subphase_log.events) == 12

    # All should have running=True
    for event in result.subphase_log.events:
        assert isinstance(event, SheriffNomination)
        assert event.running is True
        assert event.phase == Phase.DAY
        assert event.micro_phase == SubPhase.NOMINATION


@pytest.mark.asyncio
async def test_nomination_some_players_run():
    """Test when only some players decide to run."""
    from werewolf.handlers.nomination_handler import NominationHandler

    context, participants = make_context_with_some_nominating()
    handler = NominationHandler()

    result = await handler(context, list(participants.items()))

    assert result.subphase_log.micro_phase == SubPhase.NOMINATION
    assert len(result.subphase_log.events) == 12

    # Check correct running status
    running_seats = {event.actor for event in result.subphase_log.events if event.running}
    assert running_seats == {0, 3, 6, 9}


@pytest.mark.asyncio
async def test_nomination_dead_players_can_nominate():
    """Test that dead players can still nominate."""
    from werewolf.handlers.nomination_handler import NominationHandler

    context, participants = make_context_with_dead_players()
    handler = NominationHandler()

    result = await handler(context, list(participants.items()))

    assert result.subphase_log.micro_phase == SubPhase.NOMINATION
    assert len(result.subphase_log.events) == 12

    # All should have running=True, including dead players
    running_seats = {event.actor for event in result.subphase_log.events if event.running}
    assert running_seats == set(range(12))


@pytest.mark.asyncio
async def test_nomination_response_parsing():
    """Test that responses are parsed correctly (case insensitive)."""
    from werewolf.handlers.nomination_handler import NominationHandler

    players = {
        seat: Player(seat=seat, name=f"Player_{seat}", role=Role.VILLAGER, player_type=PlayerType.AI)
        for seat in range(3)
    }

    context = PhaseContext(
        players=players,
        living_players={0, 1, 2},
        dead_players=set(),
        sheriff=None,
        day=1,
    )

    # Test different case variations
    participants = {
        0: MockParticipant(response="RUN"),  # uppercase
        1: MockParticipant(response="Not Running"),  # mixed case
        2: MockParticipant(response="run"),  # lowercase
    }

    handler = NominationHandler()
    result = await handler(context, list(participants.items()))

    # All should be correctly parsed
    events_by_seat = {event.actor: event for event in result.subphase_log.events}
    assert events_by_seat[0].running is True  # RUN -> True
    assert events_by_seat[1].running is False  # Not Running -> False
    assert events_by_seat[2].running is True  # run -> True


@pytest.mark.asyncio
async def test_nomination_invalid_response_raises_exception():
    """Test that invalid responses raise MaxRetriesExceededError after max retries."""
    from werewolf.handlers.nomination_handler import NominationHandler, MaxRetriesExceededError

    players = {
        seat: Player(seat=seat, name=f"Player_{seat}", role=Role.VILLAGER, player_type=PlayerType.AI)
        for seat in range(3)
    }

    context = PhaseContext(
        players=players,
        living_players={0, 1, 2},
        dead_players=set(),
        sheriff=None,
        day=1,
    )

    # Invalid responses - will fail validation and raise after max_retries
    participants = {
        0: MockParticipant(response="maybe"),
    }

    handler = NominationHandler()
    with pytest.raises(MaxRetriesExceededError):
        await handler(context, list(participants.items()))


@pytest.mark.asyncio
async def test_nomination_only_day1():
    """Test that nomination only occurs on Day 1."""
    from werewolf.handlers.nomination_handler import NominationHandler

    players = {
        seat: Player(seat=seat, name=f"Player_{seat}", role=Role.VILLAGER, player_type=PlayerType.AI)
        for seat in range(12)
    }

    context = PhaseContext(
        players=players,
        living_players=set(range(12)),
        dead_players=set(),
        sheriff=None,
        day=2,  # Day 2, not Day 1
    )

    participants = {
        seat: MockParticipant(response="run")
        for seat in range(12)
    }

    handler = NominationHandler()
    result = await handler(context, list(participants.items()))

    # Should skip on Day 2
    assert result.subphase_log.micro_phase == SubPhase.NOMINATION
    assert len(result.subphase_log.events) == 0
    assert "only occurs on Day 1" in result.debug_info


@pytest.mark.asyncio
async def test_nomination_no_players():
    """Test nomination with no players."""
    from werewolf.handlers.nomination_handler import NominationHandler

    context = PhaseContext(
        players={},
        living_players=set(),
        dead_players=set(),
        sheriff=None,
        day=1,
    )

    handler = NominationHandler()
    result = await handler(context, [])

    assert result.subphase_log.micro_phase == SubPhase.NOMINATION
    assert len(result.subphase_log.events) == 0


@pytest.mark.asyncio
async def test_nomination_event_properties():
    """Test that nomination events have correct properties."""
    from werewolf.handlers.nomination_handler import NominationHandler

    players = {
        0: Player(seat=0, name="Player_0", role=Role.WEREWOLF, player_type=PlayerType.AI),
        1: Player(seat=1, name="Player_1", role=Role.SEER, player_type=PlayerType.AI),
    }

    context = PhaseContext(
        players=players,
        living_players={0, 1},
        dead_players=set(),
        sheriff=None,
        day=1,
    )

    participants = {
        0: MockParticipant(response="run"),
        1: MockParticipant(response="not running"),
    }

    handler = NominationHandler()
    result = await handler(context, list(participants.items()))

    running_event = None
    not_running_event = None
    for event in result.subphase_log.events:
        if event.actor == 0:
            running_event = event
        elif event.actor == 1:
            not_running_event = event

    assert running_event is not None
    assert not_running_event is not None

    assert running_event.day == 1
    assert running_event.phase == Phase.DAY
    assert running_event.micro_phase == SubPhase.NOMINATION
    assert running_event.running is True

    assert not_running_event.day == 1
    assert not_running_event.phase == Phase.DAY
    assert not_running_event.micro_phase == SubPhase.NOMINATION
    assert not_running_event.running is False


# ============================================================================
# Test _parse_nomination method directly
# ============================================================================


def test_parse_nomination():
    """Test the _parse_nomination method."""
    from werewolf.handlers.nomination_handler import NominationHandler

    handler = NominationHandler()

    # Valid responses
    assert handler._parse_nomination("run") is True
    assert handler._parse_nomination("RUN") is True
    assert handler._parse_nomination("Run") is True
    assert handler._parse_nomination("not running") is False
    assert handler._parse_nomination("NOT RUNNING") is False
    assert handler._parse_nomination("Not Running") is False

    # Invalid responses
    assert handler._parse_nomination("maybe") is None
    assert handler._parse_nomination("yes") is None
    assert handler._parse_nomination("") is None
    assert handler._parse_nomination("run for sheriff") is None


# ============================================================================
# Test: Handler MUST pass choices parameter to participant.decide()
# ============================================================================


@pytest.mark.asyncio
async def test_nomination_handler_should_pass_choices():
    """NominationHandler MUST pass choices parameter to participant.decide().

    This test exposes the bug where NominationHandler doesn't provide ChoiceSpec,
    causing TextualParticipant to fall back to a broken "Skip / Abstain" menu.
    """
    from werewolf.handlers.nomination_handler import NominationHandler
    from werewolf.ui.choices import ChoiceSpec, ChoiceOption, ChoiceType

    players = {
        0: Player(seat=0, name="Player_0", role=Role.VILLAGER, player_type=PlayerType.AI),
        1: Player(seat=1, name="Player_1", role=Role.SEER, player_type=PlayerType.AI),
    }

    context = PhaseContext(
        players=players,
        living_players={0, 1},
        dead_players=set(),
        sheriff=None,
        day=1,
    )

    # Create mock participant that records calls
    mock_participant = AsyncMock()
    mock_participant.decide = AsyncMock(return_value="run")

    handler = NominationHandler()
    await handler(context, [(0, mock_participant)])

    # Verify that choices WAS PASSED (not None)
    call_args = mock_participant.decide.call_args
    assert call_args is not None, "participant.decide() was not called"

    # Get the 'choices' keyword argument
    choices_passed = call_args.kwargs.get('choices')

    # FAILURE: If choices is None, the handler is not doing its job
    assert choices_passed is not None, (
        "BUG: NominationHandler did not pass 'choices' parameter to participant.decide(). "
        "This causes TextualParticipant to show broken 'Skip / Abstain' menu instead of "
        "proper 'run' / 'not running' options."
    )

    # Verify choices has correct structure for nomination
    if hasattr(choices_passed, 'options'):
        values = [opt.value for opt in choices_passed.options]
    elif isinstance(choices_passed, list):
        values = [str(v) if not isinstance(v, str) else v for v in choices_passed]
    else:
        values = []

    # Verify "run" and "not running" are in the choices
    assert "run" in values, (
        f"BUG: Choices did not include 'run' option. Got: {values}"
    )
    assert "not running" in values, (
        f"BUG: Choices did not include 'not running' option. Got: {values}"
    )


@pytest.mark.asyncio
async def test_nomination_handler_choices_format():
    """NominationHandler choices should have correct format.

    When choices are provided, they should be a ChoiceSpec with:
    - choice_type: SINGLE (select one option)
    - prompt: Explains the nomination decision
    - options: "run" and "not running" (both required)
    - allow_none: False (must choose one of the two)
    """
    from werewolf.handlers.nomination_handler import NominationHandler
    from werewolf.ui.choices import ChoiceSpec, ChoiceType

    players = {
        0: Player(seat=0, name="Player_0", role=Role.VILLAGER, player_type=PlayerType.AI),
    }

    context = PhaseContext(
        players=players,
        living_players={0},
        dead_players=set(),
        sheriff=None,
        day=1,
    )

    mock_participant = AsyncMock()
    mock_participant.decide = AsyncMock(return_value="run")

    handler = NominationHandler()
    await handler(context, [(0, mock_participant)])

    choices_passed = mock_participant.decide.call_args.kwargs.get('choices')

    # Verify it's a ChoiceSpec
    assert isinstance(choices_passed, ChoiceSpec), (
        f"BUG: choices should be ChoiceSpec, got {type(choices_passed)}"
    )

    # Verify choice_type is SINGLE (not SEAT or other)
    assert choices_passed.choice_type == ChoiceType.SINGLE, (
        f"BUG: choice_type should be SINGLE for nomination, got {choices_passed.choice_type}"
    )

    # Verify prompt is present
    assert choices_passed.prompt, "BUG: prompt should not be empty"

    # Verify both options exist
    values = [opt.value for opt in choices_passed.options]
    assert "run" in values, f"BUG: 'run' option missing. Options: {values}"
    assert "not running" in values, f"BUG: 'not running' option missing. Options: {values}"

    # Verify allow_none is False (must choose one)
    assert choices_passed.allow_none is False, (
        "BUG: allow_none should be False for nomination - player must choose run or not running"
    )
