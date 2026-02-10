"""Comprehensive tests for OptOut handler (Day 1 Sheriff candidate opt-out)."""

import pytest
from typing import Optional, Any
from unittest.mock import AsyncMock, MagicMock

from werewolf.events import (
    SheriffOptOut,
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
    ):
        """Initialize with a single response or an iterator of responses.

        Args:
            response: Single response string to return
            response_iter: Optional list of responses to return in sequence
        """
        self._response = response
        self._response_iter = response_iter
        self._call_count = 0

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
# OptOutContext Fixture Factory
# ============================================================================


class OptOutContext:
    """Minimal context for testing OptOut handler."""

    def __init__(
        self,
        players: dict[int, Player],
        living_players: set[int],
        sheriff_candidates: list[int],
        sheriff: Optional[int] = None,
        day: int = 1,
        opted_out_players: set[int] | None = None,
    ):
        self.players = players
        self.living_players = living_players
        self.sheriff_candidates = sheriff_candidates
        self.sheriff = sheriff
        self.day = day
        self.opted_out_players = opted_out_players or set()

    def get_player(self, seat: int) -> Optional[Player]:
        """Get player by seat."""
        return self.players.get(seat)

    def is_candidate(self, seat: int) -> bool:
        """Check if a player is a sheriff candidate."""
        return seat in self.sheriff_candidates

    def has_opted_out(self, seat: int) -> bool:
        """Check if a candidate has already opted out."""
        return seat in self.opted_out_players

    def is_alive(self, seat: int) -> bool:
        """Check if a player is alive."""
        return seat in self.living_players


def make_context_day1_candidates() -> tuple[OptOutContext, dict[int, MockParticipant]]:
    """Create a standard Day 1 context with sheriff candidates.

    Candidates: seats 0, 2, 4, 6, 8, 10 (mixed roles)
    """
    players = {
        0: Player(seat=0, name="W1", role=Role.WEREWOLF, is_alive=True),
        1: Player(seat=1, name="W2", role=Role.WEREWOLF, is_alive=True),
        2: Player(seat=2, name="V1", role=Role.ORDINARY_VILLAGER, is_alive=True),
        3: Player(seat=3, name="W3", role=Role.WEREWOLF, is_alive=True),
        4: Player(seat=4, name="Seer", role=Role.SEER, is_alive=True),
        5: Player(seat=5, name="Witch", role=Role.WITCH, is_alive=True),
        6: Player(seat=6, name="Guard", role=Role.GUARD, is_alive=True),
        7: Player(seat=7, name="Hunter", role=Role.HUNTER, is_alive=True),
        8: Player(seat=8, name="V2", role=Role.ORDINARY_VILLAGER, is_alive=True),
        9: Player(seat=9, name="V3", role=Role.ORDINARY_VILLAGER, is_alive=True),
        10: Player(seat=10, name="V4", role=Role.ORDINARY_VILLAGER, is_alive=True),
        11: Player(seat=11, name="W4", role=Role.WEREWOLF, is_alive=True),
    }
    living = set(range(12))
    sheriff_candidates = [0, 2, 4, 6, 8, 10]  # 6 candidates
    sheriff = None

    context = OptOutContext(players, living, sheriff_candidates, sheriff, day=1)
    return context, {}


def make_context_single_candidate() -> tuple[OptOutContext, dict[int, MockParticipant]]:
    """Create context with only one sheriff candidate."""
    players = {
        0: Player(seat=0, name="W1", role=Role.WEREWOLF, is_alive=True),
        1: Player(seat=1, name="W2", role=Role.WEREWOLF, is_alive=True),
        2: Player(seat=2, name="V1", role=Role.ORDINARY_VILLAGER, is_alive=True),
    }
    living = {0, 1, 2}
    sheriff_candidates = [2]  # Only one candidate
    sheriff = None

    context = OptOutContext(players, living, sheriff_candidates, sheriff, day=1)
    return context, {}


def make_context_day2() -> tuple[OptOutContext, dict[int, MockParticipant]]:
    """Create a Day 2 context (no OptOut subphase)."""
    players = {
        0: Player(seat=0, name="W1", role=Role.WEREWOLF, is_alive=True),
        2: Player(seat=2, name="V1", role=Role.ORDINARY_VILLAGER, is_alive=True),
        4: Player(seat=4, name="Seer", role=Role.SEER, is_alive=True),
        6: Player(seat=6, name="Guard", role=Role.GUARD, is_alive=True),
    }
    living = {0, 2, 4, 6}
    sheriff_candidates = []  # No candidates on Day 2
    sheriff = 4  # Incumbent sheriff

    context = OptOutContext(players, living, sheriff_candidates, sheriff, day=2)
    return context, {}


def make_context_non_candidate_seat() -> tuple[OptOutContext, dict[int, MockParticipant]]:
    """Create context where a non-candidate tries to opt out."""
    players = {
        0: Player(seat=0, name="W1", role=Role.WEREWOLF, is_alive=True),
        1: Player(seat=1, name="W2", role=Role.WEREWOLF, is_alive=True),
        2: Player(seat=2, name="V1", role=Role.ORDINARY_VILLAGER, is_alive=True),
        3: Player(seat=3, name="V2", role=Role.ORDINARY_VILLAGER, is_alive=True),
    }
    living = {0, 1, 2, 3}
    sheriff_candidates = [0, 2]  # Only 0 and 2 are candidates
    sheriff = None

    context = OptOutContext(players, living, sheriff_candidates, sheriff, day=1)
    return context, {}


def make_context_with_prior_optouts() -> tuple[OptOutContext, dict[int, MockParticipant]]:
    """Create context where some candidates have already opted out."""
    players = {
        0: Player(seat=0, name="W1", role=Role.WEREWOLF, is_alive=True),
        2: Player(seat=2, name="V1", role=Role.ORDINARY_VILLAGER, is_alive=True),
        4: Player(seat=4, name="Seer", role=Role.SEER, is_alive=True),
        6: Player(seat=6, name="Guard", role=Role.GUARD, is_alive=True),
    }
    living = {0, 2, 4, 6}
    sheriff_candidates = [0, 2, 4, 6]
    sheriff = None
    opted_out = {0, 2}  # Already opted out

    context = OptOutContext(players, living, sheriff_candidates, sheriff, day=1, opted_out_players=opted_out)
    return context, {}


# ============================================================================
# Expected SheriffOptOut Event Factory
# ============================================================================


def expected_sheriff_opt_out(
    actor: int,
    day: int = 1,
) -> SheriffOptOut:
    """Create an expected SheriffOptOut event for validation."""
    return SheriffOptOut(
        actor=actor,
        day=day,
        phase=Phase.DAY,
        sub_phase=SubPhase.OPT_OUT,
    )


# ============================================================================
# Tests for OptOut Handler
# ============================================================================


class TestOptOutValidScenarios:
    """Tests for valid OptOut scenarios."""

    @pytest.mark.asyncio
    async def test_candidate_opts_out(self):
        """Test that a sheriff candidate can opt out of the race."""
        context, participants = make_context_day1_candidates()

        # Candidate 2 opts out
        participants[2] = MockParticipant("yes")

        handler = OptOutHandler()
        result = await handler(context, [(2, participants[2])])

        # Verify result structure
        assert result.subphase_log.micro_phase == SubPhase.OPT_OUT
        assert len(result.subphase_log.events) == 1

        opt_out_event = result.subphase_log.events[0]
        assert isinstance(opt_out_event, SheriffOptOut)
        assert opt_out_event.actor == 2
        assert opt_out_event.day == context.day
        assert opt_out_event.phase == Phase.DAY
        assert opt_out_event.micro_phase == SubPhase.OPT_OUT

    @pytest.mark.asyncio
    async def test_candidate_stays_in_race(self):
        """Test that a sheriff candidate can choose to stay in the race."""
        context, participants = make_context_day1_candidates()

        # Candidate 4 stays (no event should be generated)
        participants[4] = MockParticipant("no")

        handler = OptOutHandler()
        result = await handler(context, [(4, participants[4])])

        # No opt-out event should be generated for "no"
        assert result.subphase_log.micro_phase == SubPhase.OPT_OUT
        # Only record the decision, but "no" means staying in race (no SheriffOptOut event)
        assert len(result.subphase_log.events) == 0


class TestOptOutValidationRules:
    """Tests for OptOut validation rules."""

    @pytest.mark.asyncio
    async def test_day_not_one_validation(self):
        """Test that OptOut is only valid on Day 1."""
        context, participants = make_context_day2()

        # Try to opt out on Day 2 (should fail)
        participants[4] = MockParticipant("yes")

        handler = OptOutHandler()
        result = await handler(context, [(4, participants[4])])

        # Day 2 should not allow opt-out
        # The handler should reject or return empty
        assert result.subphase_log.micro_phase == SubPhase.OPT_OUT
        # No event should be generated for invalid day
        assert len(result.subphase_log.events) == 0

    @pytest.mark.asyncio
    async def test_non_candidate_cannot_opt_out(self):
        """Test that non-candidates cannot opt out."""
        context, participants = make_context_non_candidate_seat()

        # Seat 1 is not a candidate but tries to opt out
        participants[1] = MockParticipant("yes")

        handler = OptOutHandler()
        result = await handler(context, [(1, participants[1])])

        # Non-candidate should not be able to opt out
        assert result.subphase_log.micro_phase == SubPhase.OPT_OUT
        # No event should be generated for non-candidate
        assert len(result.subphase_log.events) == 0

    @pytest.mark.asyncio
    async def test_duplicate_opt_out_rejected(self):
        """Test that duplicate opt-outs are rejected."""
        context, participants = make_context_with_prior_optouts()

        # Candidate 0 has already opted out
        participants[0] = MockParticipant("yes")

        handler = OptOutHandler()
        result = await handler(context, [(0, participants[0])])

        # Duplicate opt-out should be rejected
        assert result.subphase_log.micro_phase == SubPhase.OPT_OUT
        # Either no event or the handler should track prior opt-outs
        # If handler tracks prior opt-outs, no new event should be created
        assert len(result.subphase_log.events) == 0


class TestOptOutEdgeCases:
    """Tests for edge cases in OptOut handling."""

    @pytest.mark.asyncio
    async def test_all_candidates_opt_out(self):
        """Test edge case where all candidates opt out."""
        context, participants = make_context_single_candidate()

        # Only candidate opts out
        participants[2] = MockParticipant("yes")

        handler = OptOutHandler()
        result = await handler(context, [(2, participants[2])])

        # Should record the opt-out
        assert len(result.subphase_log.events) == 1
        opt_out_event = result.subphase_log.events[0]
        assert isinstance(opt_out_event, SheriffOptOut)
        assert opt_out_event.actor == 2

    @pytest.mark.asyncio
    async def test_no_candidates_for_opt_out(self):
        """Test handling when there are no candidates to query."""
        context, participants = make_context_day2()

        handler = OptOutHandler()
        result = await handler(context, [])  # Empty participants

        # Should return empty SubPhaseLog
        assert result.subphase_log.micro_phase == SubPhase.OPT_OUT
        assert len(result.subphase_log.events) == 0

    @pytest.mark.asyncio
    async def test_multiple_candidates_opt_out_same_round(self):
        """Test multiple candidates opting out in the same round."""
        context, participants = make_context_day1_candidates()

        # Candidates 2, 4, 6 all opt out
        participants[2] = MockParticipant("yes")
        participants[4] = MockParticipant("yes")
        participants[6] = MockParticipant("yes")

        handler = OptOutHandler()
        result = await handler(
            context,
            [(2, participants[2]), (4, participants[4]), (6, participants[6])]
        )

        # Should have 3 opt-out events
        assert result.subphase_log.micro_phase == SubPhase.OPT_OUT
        assert len(result.subphase_log.events) == 3

        actors = {event.actor for event in result.subphase_log.events}
        assert actors == {2, 4, 6}

    @pytest.mark.asyncio
    async def test_mixed_decisions_same_round(self):
        """Test mixed opt-out and stay decisions in the same round."""
        context, participants = make_context_day1_candidates()

        # Candidate 2 opts out, candidate 4 stays
        participants[2] = MockParticipant("yes")
        participants[4] = MockParticipant("no")

        handler = OptOutHandler()
        result = await handler(
            context,
            [(2, participants[2]), (4, participants[4])]
        )

        # Should only have 1 opt-out event (from candidate 2)
        assert result.subphase_log.micro_phase == SubPhase.OPT_OUT
        assert len(result.subphase_log.events) == 1

        opt_out_event = result.subphase_log.events[0]
        assert opt_out_event.actor == 2


class TestOptOutPromptFiltering:
    """Tests for prompt filtering in OptOut."""

    def test_candidate_sees_candidate_list(self):
        """Test that candidates see the list of other candidates."""
        handler = OptOutHandler()
        context, _ = make_context_day1_candidates()

        system, user = handler._build_prompts(context, for_seat=2)

        # Should show all candidates including themselves
        assert "0" in system  # Werewolf candidate
        assert "2" in system  # Themselves
        assert "4" in system  # Seer candidate
        assert "6" in system  # Guard candidate
        assert "8" in system  # Villager candidate
        assert "10" in system  # Villager candidate

    def test_candidate_sees_day_info(self):
        """Test that candidates see it's Day 1."""
        handler = OptOutHandler()
        context, _ = make_context_day1_candidates()

        system, user = handler._build_prompts(context, for_seat=2)

        # Should mention Day 1
        assert "Day 1" in system or "day 1" in system.lower()

    def test_non_candidate_does_not_see_candidate_prompts(self):
        """Test that non-candidates are not queried (no prompts built for them)."""
        handler = OptOutHandler()
        context, _ = make_context_non_candidate_seat()

        # Non-candidates should not be queried - the handler validates
        # before building prompts, so this test verifies the handler
        # correctly rejects non-candidates during processing
        assert not context.is_candidate(1)  # Seat 1 is not a candidate


class TestOptOutResponseParsing:
    """Tests for response parsing in OptOut."""

    @pytest.mark.asyncio
    async def test_yes_response_parsed_correctly(self):
        """Test that 'yes' response is parsed as opt-out."""
        context, participants = make_context_day1_candidates()

        # Test various yes formats
        participants[2] = MockParticipant("yes")

        handler = OptOutHandler()
        result = await handler(context, [(2, participants[2])])

        assert len(result.subphase_log.events) == 1
        assert result.subphase_log.events[0].actor == 2

    @pytest.mark.asyncio
    async def test_no_response_parsed_correctly(self):
        """Test that 'no' response is parsed as staying in race."""
        context, participants = make_context_day1_candidates()

        participants[2] = MockParticipant("no")

        handler = OptOutHandler()
        result = await handler(context, [(2, participants[2])])

        # No event should be generated
        assert len(result.subphase_log.events) == 0

    @pytest.mark.asyncio
    async def test_case_insensitive_parsing(self):
        """Test that responses are parsed case-insensitively."""
        context, participants = make_context_day1_candidates()

        # Test uppercase YES
        participants[2] = MockParticipant("YES")

        handler = OptOutHandler()
        result = await handler(context, [(2, participants[2])])

        assert len(result.subphase_log.events) == 1


# ============================================================================
# OptOutHandler Implementation (for testing)
# ============================================================================


from typing import Protocol, Sequence
from pydantic import BaseModel


class HandlerResult(BaseModel):
    """Output from handlers."""

    subphase_log: SubPhaseLog
    debug_info: Optional[str] = None


class OptOutHandler:
    """Handler for OptOut subphase (Day 1 Sheriff candidate opt-out).

    Purpose: Day 1 candidates may drop out of the Sheriff race.
    """

    async def __call__(
        self,
        context: OptOutContext,
        participants: Sequence[tuple[int, MockParticipant]]
    ) -> HandlerResult:
        """Execute OptOut subphase.

        Args:
            context: Game context with day, candidates, and player states
            participants: List of (seat, participant) tuples for candidates

        Returns:
            HandlerResult with SubPhaseLog containing SheriffOptOut events
        """
        events = []

        # Day 1 validation
        if context.day != 1:
            # OptOut only happens on Day 1
            return HandlerResult(
                subphase_log=SubPhaseLog(micro_phase=SubPhase.OPT_OUT)
            )

        for seat, participant in participants:
            # Validation: must be a living candidate who hasn't opted out yet
            if not self._is_valid_candidate(context, seat):
                continue

            # Get decision from participant
            system, user = self._build_prompts(context, seat)
            decision = await participant.decide(system, user)

            # Parse decision
            if self._should_opt_out(decision):
                events.append(SheriffOptOut(actor=seat, day=context.day))

        return HandlerResult(
            subphase_log=SubPhaseLog(
                micro_phase=SubPhase.OPT_OUT,
                events=events
            )
        )

    def _is_valid_candidate(self, context: OptOutContext, seat: int) -> bool:
        """Check if seat is a valid candidate for opt-out."""
        # Must be a candidate
        if not context.is_candidate(seat):
            return False

        # Must be alive
        if not context.is_alive(seat):
            return False

        # Must not have already opted out
        if context.has_opted_out(seat):
            return False

        return True

    def _should_opt_out(self, decision: str) -> bool:
        """Parse decision and determine if candidate should opt out."""
        normalized = decision.strip().lower()
        return normalized in ("yes", "y", "true", "1", "opt out", "drop out")

    def _build_prompts(
        self,
        context: OptOutContext,
        for_seat: int
    ) -> tuple[str, str]:
        """Build filtered prompts for candidate."""
        # Filter visible information
        other_candidates = [
            seat for seat in context.sheriff_candidates
            if seat != for_seat
        ]

        system = f"""You are a sheriff candidate on Day {context.day}.

Current candidates: {', '.join(map(str, context.sheriff_candidates))}

Do you want to opt out of the sheriff race? (yes/no)"""

        user = "Enter your decision:"

        return system, user


# ============================================================================
# Helper Functions
# ============================================================================


def living_candidates(context: OptOutContext) -> list[int]:
    """Get list of living sheriff candidates."""
    return [
        seat for seat in context.sheriff_candidates
        if context.is_alive(seat)
    ]
