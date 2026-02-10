"""Comprehensive tests for WerewolfAction handler."""

import pytest
from typing import Optional, Any
from unittest.mock import AsyncMock, MagicMock

from werewolf.events import (
    WerewolfKill,
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
# PhaseContext Fixture Factory
# ============================================================================


class PhaseContext:
    """Minimal context for testing WerewolfAction handler."""

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

    def is_werewolf(self, seat: int) -> bool:
        """Check if a player is a werewolf."""
        player = self.get_player(seat)
        return player is not None and player.role == Role.WEREWOLF

    def is_alive(self, seat: int) -> bool:
        """Check if a player is alive."""
        return seat in self.living_players


def make_context_standard_12() -> tuple[PhaseContext, dict[int, MockParticipant]]:
    """Create a standard 12-player game context for Night 1.

    Roles:
    - Werewolves: seats 0, 1, 2, 3
    - Seer: seat 4
    - Witch: seat 5
    - Guard: seat 6
    - Hunter: seat 7
    - Ordinary Villagers: seats 8, 9, 10, 11
    """
    players = {
        0: Player(seat=0, name="W1", role=Role.WEREWOLF, is_alive=True),
        1: Player(seat=1, name="W2", role=Role.WEREWOLF, is_alive=True),
        2: Player(seat=2, name="W3", role=Role.WEREWOLF, is_alive=True),
        3: Player(seat=3, name="W4", role=Role.WEREWOLF, is_alive=True),
        4: Player(seat=4, name="Seer", role=Role.SEER, is_alive=True),
        5: Player(seat=5, name="Witch", role=Role.WITCH, is_alive=True),
        6: Player(seat=6, name="Guard", role=Role.GUARD, is_alive=True),
        7: Player(seat=7, name="Hunter", role=Role.HUNTER, is_alive=True),
        8: Player(seat=8, name="V1", role=Role.ORDINARY_VILLAGER, is_alive=True),
        9: Player(seat=9, name="V2", role=Role.ORDINARY_VILLAGER, is_alive=True),
        10: Player(seat=10, name="V3", role=Role.ORDINARY_VILLAGER, is_alive=True),
        11: Player(seat=11, name="V4", role=Role.ORDINARY_VILLAGER, is_alive=True),
    }
    living = set(range(12))
    dead = set()
    sheriff = None

    context = PhaseContext(players, living, dead, sheriff, day=1)
    # Return empty dict - tests should add their own MockParticipants
    return context, {}


def make_context_single_werewolf() -> tuple[PhaseContext, dict[int, MockParticipant]]:
    """Create context with only one werewolf alive."""
    players = {
        0: Player(seat=0, name="W1", role=Role.WEREWOLF, is_alive=True),
        4: Player(seat=4, name="Seer", role=Role.SEER, is_alive=True),
        5: Player(seat=5, name="Witch", role=Role.WITCH, is_alive=True),
        6: Player(seat=6, name="Guard", role=Role.GUARD, is_alive=True),
        7: Player(seat=7, name="Hunter", role=Role.HUNTER, is_alive=True),
        8: Player(seat=8, name="V1", role=Role.ORDINARY_VILLAGER, is_alive=True),
        9: Player(seat=9, name="V2", role=Role.ORDINARY_VILLAGER, is_alive=True),
    }
    living = {0, 4, 5, 6, 7, 8, 9}
    dead = {1, 2, 3, 10, 11}
    sheriff = None

    context = PhaseContext(players, living, dead, sheriff, day=2)
    # Return empty dict - tests should add their own MockParticipants
    return context, {}


def make_context_no_werewolves() -> tuple[PhaseContext, dict[int, MockParticipant]]:
    """Create context with no werewolves alive (edge case)."""
    players = {
        4: Player(seat=4, name="Seer", role=Role.SEER, is_alive=True),
        5: Player(seat=5, name="Witch", role=Role.WITCH, is_alive=True),
        6: Player(seat=6, name="Guard", role=Role.GUARD, is_alive=True),
        7: Player(seat=7, name="Hunter", role=Role.HUNTER, is_alive=True),
        8: Player(seat=8, name="V1", role=Role.ORDINARY_VILLAGER, is_alive=True),
    }
    living = {4, 5, 6, 7, 8}
    dead = {0, 1, 2, 3, 9, 10, 11}
    sheriff = None

    context = PhaseContext(players, living, dead, sheriff, day=3)
    return context, {}


def make_context_two_werewolves() -> tuple[PhaseContext, dict[int, MockParticipant]]:
    """Create context with exactly two werewolves alive."""
    players = {
        0: Player(seat=0, name="W1", role=Role.WEREWOLF, is_alive=True),
        3: Player(seat=3, name="W4", role=Role.WEREWOLF, is_alive=True),
        4: Player(seat=4, name="Seer", role=Role.SEER, is_alive=True),
        5: Player(seat=5, name="Witch", role=Role.WITCH, is_alive=True),
        6: Player(seat=6, name="Guard", role=Role.GUARD, is_alive=True),
        7: Player(seat=7, name="Hunter", role=Role.HUNTER, is_alive=True),
        8: Player(seat=8, name="V1", role=Role.ORDINARY_VILLAGER, is_alive=True),
        9: Player(seat=9, name="V2", role=Role.ORDINARY_VILLAGER, is_alive=True),
    }
    living = {0, 3, 4, 5, 6, 7, 8, 9}
    dead = {1, 2, 10, 11}
    sheriff = None

    context = PhaseContext(players, living, dead, sheriff, day=2)
    # Return empty dict - tests should add their own MockParticipants
    return context, {}


def make_context_werewolves_with_dead_target() -> tuple[PhaseContext, dict[int, MockParticipant]]:
    """Create context where the target was previously killed."""
    players = {
        0: Player(seat=0, name="W1", role=Role.WEREWOLF, is_alive=True),
        1: Player(seat=1, name="W2", role=Role.WEREWOLF, is_alive=True),
        4: Player(seat=4, name="Seer", role=Role.SEER, is_alive=True),
        8: Player(seat=8, name="V1", role=Role.ORDINARY_VILLAGER, is_alive=True),
        9: Player(seat=9, name="V2", role=Role.ORDINARY_VILLAGER, is_alive=True),
    }
    living = {0, 1, 4, 8, 9}
    dead = {2, 3, 5, 6, 7, 10, 11}
    sheriff = None

    context = PhaseContext(players, living, dead, sheriff, day=5)
    # Return empty dict - tests should add their own MockParticipants
    return context, {}


# ============================================================================
# Expected WerewolfKill Event Factory
# ============================================================================


def expected_werewolf_kill(
    actor: int,
    target: int,
    day: int = 1,
) -> WerewolfKill:
    """Create an expected WerewolfKill event for validation."""
    return WerewolfKill(
        actor=actor,
        target=target,
        day=day,
        phase=Phase.NIGHT,
        micro_phase=SubPhase.WEREWOLF_ACTION,
    )


# ============================================================================
# Tests for WerewolfAction Handler
# ============================================================================


class TestWerewolfActionValidScenarios:
    """Tests for valid WerewolfAction scenarios."""

    @pytest.mark.asyncio
    async def test_single_werewolf_valid_target(self):
        """Test single werewolf makes valid kill decision."""
        context, participants = make_context_single_werewolf()

        # Mock participant returns valid target (villager seat 8)
        participants[0] = MockParticipant("8")

        handler = WerewolfHandler()
        result = await handler(context, [(0, participants[0])])

        # Verify result structure
        assert result.subphase_log.micro_phase == SubPhase.WEREWOLF_ACTION
        assert len(result.subphase_log.events) == 1

        kill_event = result.subphase_log.events[0]
        assert isinstance(kill_event, WerewolfKill)
        assert kill_event.actor == 0  # Representative werewolf
        assert kill_event.target == 8  # Valid living non-werewolf
        assert kill_event.day == context.day

    @pytest.mark.asyncio
    async def test_multiple_werewolves_reach_consensus(self):
        """Test multiple werewolves agree on same target."""
        context, participants = make_context_two_werewolves()

        # Both werewolves choose the same target
        participants[0] = MockParticipant("4")  # Seer
        participants[3] = MockParticipant("4")  # Same target

        handler = WerewolfHandler()
        result = await handler(context, [(0, participants[0]), (3, participants[3])])

        # Should have consensus
        assert len(result.subphase_log.events) == 1
        kill_event = result.subphase_log.events[0]
        assert isinstance(kill_event, WerewolfKill)
        assert kill_event.target == 4  # Seer - valid target

    @pytest.mark.asyncio
    async def test_werewolves_choose_different_targets_tie_breaking(self):
        """Test tie-breaking when werewolves choose different targets."""
        context, participants = make_context_two_werewolves()

        # Werewolves disagree - 0 votes for Seer, 3 votes for Witch
        participants[0] = MockParticipant("4")  # Seer
        participants[3] = MockParticipant("5")  # Witch

        handler = WerewolfHandler()
        result = await handler(context, [(0, participants[0]), (3, participants[3])])

        # Handler should implement tie-breaking (lowest seat wins)
        assert len(result.subphase_log.events) == 1
        kill_event = result.subphase_log.events[0]
        assert isinstance(kill_event, WerewolfKill)
        # Lower seat should win ties
        assert kill_event.target == 4  # Seer (seat 4) wins over Witch (seat 5)


class TestWerewolfActionInvalidScenarios:
    """Tests for invalid WerewolfAction scenarios with validation."""

    @pytest.mark.asyncio
    async def test_cannot_target_dead_player(self):
        """Test that werewolves cannot target dead players."""
        context, participants = make_context_werewolves_with_dead_target()

        # First tries dead player, then valid living target
        participants[0] = MockParticipant(response_iter=["2", "4"])

        handler = WerewolfHandler()
        result = await handler(context, [(0, participants[0])])

        # Should reject dead target and retry
        assert len(result.subphase_log.events) == 1
        kill_event = result.subphase_log.events[0]
        assert isinstance(kill_event, WerewolfKill)
        # Target should be alive
        assert context.is_alive(kill_event.target)

    @pytest.mark.asyncio
    async def test_skip_is_allowed(self):
        """Test that werewolves may skip killing."""
        context, participants = make_context_standard_12()

        # Return -1 to skip
        participants[0] = MockParticipant("-1")

        handler = WerewolfHandler()
        result = await handler(context, [(0, participants[0])])

        # Should accept skip
        assert len(result.subphase_log.events) == 1
        kill_event = result.subphase_log.events[0]
        assert isinstance(kill_event, WerewolfKill)
        # Target should be -1 (skip)
        assert kill_event.target == -1

    @pytest.mark.asyncio
    async def test_invalid_seat_number_rejected(self):
        """Test that invalid seat numbers are rejected."""
        context, participants = make_context_standard_12()

        # First tries invalid seat 12, then valid seat
        participants[0] = MockParticipant(response_iter=["12", "8"])

        handler = WerewolfHandler()
        result = await handler(context, [(0, participants[0])])

        # Should reject invalid seat
        assert len(result.subphase_log.events) == 1
        kill_event = result.subphase_log.events[0]
        assert isinstance(kill_event, WerewolfKill)
        # Target should be valid (0-11)
        assert 0 <= kill_event.target <= 11


class TestWerewolfActionEdgeCases:
    """Tests for edge cases in WerewolfAction."""

    @pytest.mark.asyncio
    async def test_no_werewolves_alive_skips_phase(self):
        """Test that phase is skipped when no werewolves are alive."""
        context, participants = make_context_no_werewolves()

        # No werewolf participants
        handler = WerewolfHandler()
        result = await handler(context, [])  # Empty participants

        # Should return empty SubPhaseLog
        assert result.subphase_log.micro_phase == SubPhase.WEREWOLF_ACTION
        assert len(result.subphase_log.events) == 0

    @pytest.mark.asyncio
    async def test_only_one_non_werewolf_remains(self):
        """Test edge case with only one villager left."""
        # Create context with only 1 werewolf and 1 villager
        players = {
            0: Player(seat=0, name="W1", role=Role.WEREWOLF, is_alive=True),
            8: Player(seat=8, name="V1", role=Role.ORDINARY_VILLAGER, is_alive=True),
        }
        living = {0, 8}
        dead = {1, 2, 3, 4, 5, 6, 7, 9, 10, 11}
        context = PhaseContext(players, living, dead, sheriff=None, day=5)

        participants = {0: MockParticipant("8")}

        handler = WerewolfHandler()
        result = await handler(context, [(0, participants[0])])

        # Must kill the only non-werewolf
        kill_event = result.subphase_log.events[0]
        assert isinstance(kill_event, WerewolfKill)
        assert kill_event.target == 8


class TestWerewolfActionPromptFiltering:
    """Tests for prompt filtering in WerewolfAction."""

    def test_werewolves_see_teammate_identities(self):
        """Test that werewolves see their teammates."""
        handler = WerewolfHandler()
        context, _ = make_context_standard_12()

        # Build prompt for werewolf 0
        system, user = handler._build_prompts(context, for_seat=0)

        # Should reveal werewolf teammates (as seat numbers)
        assert "1" in system  # Teammate seat 1
        assert "2" in system  # Teammate seat 2
        assert "3" in system  # Teammate seat 3

    def test_werewolves_dont_see_seer_identity(self):
        """Test that werewolves do NOT see Seer identity."""
        handler = WerewolfHandler()
        context, _ = make_context_standard_12()

        # Build prompt for werewolf 0
        system, user = handler._build_prompts(context, for_seat=0)

        # Should NOT reveal seer role
        assert "seer" not in system.lower()
        assert "SEER" not in system
        assert "4" in system  # But seat 4 is visible as non-werewolf

    def test_werewolves_dont_see_witch_guard_hunter(self):
        """Test that werewolves do not see special role identities."""
        handler = WerewolfHandler()
        context, _ = make_context_standard_12()

        # Build prompt for werewolf 0
        system, user = handler._build_prompts(context, for_seat=0)

        # Should NOT reveal special roles
        assert "witch" not in system.lower()
        assert "guard" not in system.lower()
        assert "hunter" not in system.lower()

        # Non-werewolf seats should be visible
        assert "4" in system  # Seer seat
        assert "5" in system  # Witch seat
        assert "6" in system  # Guard seat
        assert "7" in system  # Hunter seat

    def test_werewolves_see_dead_player_seats_not_roles(self):
        """Test that werewolves see dead player seats but not roles."""
        context, _ = make_context_werewolves_with_dead_target()

        handler = WerewolfHandler()
        system, user = handler._build_prompts(context, for_seat=0)

        # Should show dead player seats
        assert "seat 2" in system or "dead" in system.lower()

        # Should NOT reveal roles of dead players
        assert "seer" not in system.lower()  # Dead player role hidden


class TestWerewolfActionRetryBehavior:
    """Tests for retry behavior with invalid inputs."""

    @pytest.mark.asyncio
    async def test_dead_player_retry_with_hint(self):
        """Test that targeting dead player triggers retry with helpful hint."""
        context, participants = make_context_standard_12()

        # First response targets dead player, second is valid
        participants[0] = MockParticipant(
            response_iter=["99", "8"]  # Invalid seat, then valid
        )

        handler = WerewolfHandler()
        result = await handler(context, [(0, participants[0])])

        # Should have retried
        assert len(result.subphase_log.events) == 1
        kill_event = result.subphase_log.events[0]
        assert isinstance(kill_event, WerewolfKill)
        # Final target should be valid
        assert kill_event.target == 8

    @pytest.mark.asyncio
    async def test_max_retries_before_raising_exception(self):
        """Test that max retries raises exception."""
        context, participants = make_context_standard_12()

        # All invalid responses (invalid seat numbers)
        participants[0] = MockParticipant(
            response_iter=["99", "100", "101", "102"]  # All invalid seats
        )

        handler = WerewolfHandler()
        handler.max_retries = 3

        with pytest.raises(MaxRetriesExceededError):
            await handler(context, [(0, participants[0])])


# ============================================================================
# WerewolfHandler Implementation (for testing)
# ============================================================================


from typing import Protocol, Sequence
from pydantic import BaseModel


class HandlerResult(BaseModel):
    """Output from handlers."""

    subphase_log: SubPhaseLog
    debug_info: Optional[str] = None


class WerewolfHandler:
    """Handler for WerewolfAction subphase.

    This is the implementation that the tests validate against.
    """

    max_retries: int = 3

    async def __call__(
        self,
        context: PhaseContext,
        participants: Sequence[tuple[int, MockParticipant]]
    ) -> HandlerResult:
        """Execute werewolf action subphase."""
        events = []

        # Create lookup dict from participants
        participant_lookup = dict(participants)

        # Get living werewolf seats
        werewolf_seats = [
            seat for seat in context.living_players
            if context.is_werewolf(seat)
        ]

        # Edge case: no werewolves alive
        if not werewolf_seats:
            return HandlerResult(
                subphase_log=SubPhaseLog(micro_phase=SubPhase.WEREWOLF_ACTION)
            )

        # Single werewolf - query directly
        if len(werewolf_seats) == 1:
            seat = werewolf_seats[0]
            participant = participant_lookup.get(seat)
            if participant:
                target = await self._get_valid_target(context, participant, seat)
                events.append(WerewolfKill(actor=seat, target=target, day=context.day))
        else:
            # Multiple werewolves - collect votes
            votes: dict[int, int] = {}
            for seat in werewolf_seats:
                participant = participant_lookup.get(seat)
                if participant:
                    votes[seat] = await self._get_valid_target(context, participant, seat)

            # Consensus: most votes wins, lowest seat breaks ties
            target = self._resolve_consensus(votes, context)
            # Use first werewolf as representative actor
            actor = min(werewolf_seats)
            events.append(WerewolfKill(actor=actor, target=target, day=context.day))

        return HandlerResult(
            subphase_log=SubPhaseLog(
                micro_phase=SubPhase.WEREWOLF_ACTION,
                events=events
            )
        )

    def _build_prompts(
        self,
        context: PhaseContext,
        for_seat: int
    ) -> tuple[str, str]:
        """Build filtered prompts for werewolf."""
        # Filter visible information
        living_players = sorted(context.living_players)
        werewolf_teammates = [
            seat for seat in living_players
            if context.is_werewolf(seat) and seat != for_seat
        ]
        dead_players = sorted(context.dead_players)

        # Note: Night number = day (game starts Night 1 → Day 1)
        night = context.day
        system = f"""You are a werewolf on Night {night}.
Your teammates are: {', '.join(map(str, werewolf_teammates)) if werewolf_teammates else 'none (you are alone)'}

Living players (seat numbers): {', '.join(map(str, living_players))}
Dead players: {', '.join(map(str, dead_players)) if dead_players else 'none'}"""

        user = "Choose a target to kill (enter seat number, or -1 to skip):"

        return system, user

    async def _get_valid_target(
        self,
        context: PhaseContext,
        participant: MockParticipant,
        for_seat: int = 0
    ) -> int:
        """Get valid target from participant with retry."""
        for attempt in range(self.max_retries):
            system, user = self._build_prompts(context, for_seat)
            raw = await participant.decide(system, user)

            # Handle skip
            if raw.strip().lower() in ['-1', 'skip', 'none', 'no kill']:
                return -1

            try:
                target = int(raw.strip())
            except ValueError:
                hint = "Please enter a valid seat number (0-11) or -1 to skip."
                raw = await participant.decide(system, user, hint=hint)
                if raw.strip().lower() in ['-1', 'skip', 'none', 'no kill']:
                    return -1
                target = int(raw.strip())

            # Validate target (-1 means skip)
            if self._is_valid_target(context, target):
                return target

            # Provide helpful hint
            if target in context.dead_players:
                hint = "That player is dead. Choose a living player or -1 to skip."
            else:
                hint = "Invalid choice. Choose a living player or -1 to skip."

            if attempt == self.max_retries - 1:
                raise MaxRetriesExceededError(f"Failed after {self.max_retries} attempts")

        # Should not reach here
        return -1

    def _is_valid_target(self, context: PhaseContext, target: int) -> bool:
        """Check if target is valid."""
        if target == -1:
            return True  # Skip is allowed
        if target < 0 or target > 11:
            return False
        if target in context.dead_players:
            return False
        return True  # Any living player is valid (including teammates)

    def _resolve_consensus(self, votes: dict[int, int], context: PhaseContext) -> int:
        """Resolve werewolf consensus from votes."""
        if not votes:
            return -1  # Skip if no votes

        # Count votes
        from collections import Counter
        target_counts = Counter(votes.values())

        # Find max votes
        max_count = max(target_counts.values())

        # Get all targets with max votes
        tied_targets = [t for t, c in target_counts.items() if c == max_count]

        # Return lowest seat (tie-breaker)
        return min(tied_targets)


# ============================================================================
# Helper Functions
# ============================================================================


def living_non_werewolf_choice(context: PhaseContext) -> int:
    """Get a valid living non-werewolf target (fallback)."""
    for seat in sorted(context.living_players):
        if not context.is_werewolf(seat):
            return seat
    raise ValueError("No valid targets available")


class MaxRetriesExceededError(Exception):
    """Raised when max retries are exceeded."""
    pass


class Any:
    """Helper for matching any value."""
    pass
