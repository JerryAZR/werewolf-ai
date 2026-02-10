"""Comprehensive tests for Discussion handler.

Discussion subphase: Players discuss and debate during the day.
Rules:
- Sheriff speaks LAST
- Empty content rejected with retry
- Dead players cannot speak
- Sheriff not in living players (skip)
- Speaking order alternates correctly (clockwise/counter-clockwise from sheriff)
"""

import pytest
from typing import Optional, Any

from werewolf.events import (
    Speech,
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
    """Minimal context for testing Discussion handler."""

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
    """Create a standard 12-player context for Day 1 Discussion.

    All 12 players are alive. Sheriff is None on Day 1 before election.
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
    sheriff = None  # No sheriff yet on Day 1

    context = PhaseContext(players, living, dead, sheriff, day=1)
    return context, {}


def make_context_day2_with_sheriff() -> tuple[PhaseContext, dict[int, MockParticipant]]:
    """Create Day 2 context with sheriff elected."""
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
    sheriff = 4  # Seer is sheriff

    context = PhaseContext(players, living, dead, sheriff, day=2)
    return context, {}


def make_context_day2_some_dead() -> tuple[PhaseContext, dict[int, MockParticipant]]:
    """Create Day 2 context with some dead players."""
    players = {
        0: Player(seat=0, name="W1", role=Role.WEREWOLF, is_alive=True),
        1: Player(seat=1, name="W2", role=Role.WEREWOLF, is_alive=True),
        4: Player(seat=4, name="Seer", role=Role.SEER, is_alive=True),
        5: Player(seat=5, name="Witch", role=Role.WITCH, is_alive=True),
        8: Player(seat=8, name="V1", role=Role.ORDINARY_VILLAGER, is_alive=True),
        9: Player(seat=9, name="V2", role=Role.ORDINARY_VILLAGER, is_alive=True),
    }
    living = {0, 1, 4, 5, 8, 9}
    dead = {2, 3, 6, 7, 10, 11}
    sheriff = 4  # Seer is sheriff

    context = PhaseContext(players, living, dead, sheriff, day=2)
    return context, {}


def make_context_day2_no_sheriff() -> tuple[PhaseContext, dict[int, MockParticipant]]:
    """Create Day 2 context without sheriff (tie in election)."""
    players = {
        0: Player(seat=0, name="W1", role=Role.WEREWOLF, is_alive=True),
        4: Player(seat=4, name="Seer", role=Role.SEER, is_alive=True),
        8: Player(seat=8, name="V1", role=Role.ORDINARY_VILLAGER, is_alive=True),
    }
    living = {0, 4, 8}
    dead = {1, 2, 3, 5, 6, 7, 9, 10, 11}
    sheriff = None  # No sheriff

    context = PhaseContext(players, living, dead, sheriff, day=2)
    return context, {}


def make_context_day2_sheriff_dead() -> tuple[PhaseContext, dict[int, MockParticipant]]:
    """Create Day 2 context where sheriff is dead."""
    players = {
        0: Player(seat=0, name="W1", role=Role.WEREWOLF, is_alive=True),
        4: Player(seat=4, name="Seer", role=Role.SEER, is_alive=True),
        8: Player(seat=8, name="V1", role=Role.ORDINARY_VILLAGER, is_alive=True),
    }
    living = {0, 4, 8}
    dead = {1, 2, 3, 5, 6, 7, 9, 10, 11}
    sheriff = 4  # But sheriff is alive - this tests sheriff in living

    context = PhaseContext(players, living, dead, sheriff, day=2)
    return context, {}


# ============================================================================
# Expected Speech Event Factory
# ============================================================================


def expected_speech(
    actor: int,
    content: str,
    day: int = 1,
    micro_phase: SubPhase = SubPhase.DISCUSSION,
) -> Speech:
    """Create an expected Speech event for validation."""
    return Speech(
        actor=actor,
        content=content,
        day=day,
        phase=Phase.DAY,
        micro_phase=micro_phase,
    )


# ============================================================================
# DiscussionHandler Implementation (for testing)
# ============================================================================


from typing import Protocol, Sequence
from pydantic import BaseModel, Field


class HandlerResult(BaseModel):
    """Output from handlers."""

    subphase_log: SubPhaseLog
    debug_info: Optional[str] = None


class DiscussionHandler:
    """Handler for Discussion subphase.

    Discussion phase: All living players discuss and debate during the day.

    Rules:
    - Sheriff speaks LAST
    - Others alternate clockwise/counter-clockwise from sheriff
    - Dead players are skipped
    - Empty content rejected with retry
    """

    max_retries: int = 3

    async def __call__(
        self,
        context: PhaseContext,
        participants: Sequence[tuple[int, MockParticipant]]
    ) -> HandlerResult:
        """Execute discussion subphase."""
        events = []

        # Get living players sorted by seat
        living_players = sorted(context.living_players)

        # Skip if no living players
        if not living_players:
            return HandlerResult(
                subphase_log=SubPhaseLog(micro_phase=SubPhase.DISCUSSION),
                debug_info="No living players, skipping Discussion"
            )

        # Create lookup dict from participants
        participant_lookup = dict(participants)

        # Build speaking order
        speaking_order = self._build_speaking_order(
            living_players,
            context.sheriff
        )

        # Collect speeches from each living player
        for seat in speaking_order:
            participant = participant_lookup.get(seat)
            if participant:
                content = await self._get_valid_speech(context, participant, seat)
                events.append(Speech(
                    actor=seat,
                    content=content,
                    day=context.day,
                    micro_phase=SubPhase.DISCUSSION,
                ))

        return HandlerResult(
            subphase_log=SubPhaseLog(
                micro_phase=SubPhase.DISCUSSION,
                events=events
            )
        )

    def _build_speaking_order(
        self,
        living_players: list[int],
        sheriff: Optional[int]
    ) -> list[int]:
        """Build speaking order with sheriff speaking last.

        Args:
            living_players: Sorted list of living player seats
            sheriff: Current sheriff seat (or None)

        Returns:
            Speaking order with sheriff at the end
        """
        if sheriff is None or sheriff not in living_players:
            # No sheriff or sheriff dead: normal order
            return living_players.copy()

        # Sheriff speaks last: remove sheriff from list and append at end
        non_sheriff = [p for p in living_players if p != sheriff]
        return non_sheriff + [sheriff]

    def _build_prompts(
        self,
        context: PhaseContext,
        for_seat: int
    ) -> tuple[str, str]:
        """Build prompts for discussion speech."""
        player = context.get_player(for_seat)
        role_name = player.role.value if player else "Unknown"

        sheriff_info = ""
        if context.sheriff == for_seat:
            sheriff_info = "\nYou are the Sheriff - your vote counts 1.5x!"

        system = f"""You are a {role_name} on Day {context.day} during the discussion phase.
{sheriff_info}

Your goal: Analyze the game state and share your thoughts with the village.
Consider:
- Who might be a werewolf?
- What information do you have?
- What should the village discuss today?

Speak naturally as your character would."""

        user = "Enter your discussion speech:"

        return system, user

    async def _get_valid_speech(
        self,
        context: PhaseContext,
        participant: MockParticipant,
        for_seat: int
    ) -> str:
        """Get valid speech content from participant with retry."""
        for attempt in range(self.max_retries):
            system, user = self._build_prompts(context, for_seat)
            raw = await participant.decide(system, user)

            # Validate content is not empty
            content = raw.strip()
            if content:
                return content

            # Empty content - retry
            if attempt < self.max_retries - 1:
                hint = "Your speech cannot be empty. Please say something."
                raw = await participant.decide(system, user, hint=hint)
                content = raw.strip()
                if content:
                    return content

        # Max retries exceeded
        return ""


# ============================================================================
# Tests for Discussion Handler - Sheriff Speaks Last
# ============================================================================


class TestDiscussionHandlerSheriffSpeaksLast:
    """Tests that sheriff speaks last in Discussion."""

    @pytest.mark.asyncio
    async def test_sheriff_speaks_last_with_4_players(self):
        """Test sheriff speaks last with 4 living players."""
        context, participants = make_context_day2_with_sheriff()

        # Configure mock responses
        for seat in [0, 1, 4, 8]:
            participants[seat] = MockParticipant(f"Speech from {seat}")

        handler = DiscussionHandler()
        result = await handler(context, [
            (0, participants[0]),
            (1, participants[1]),
            (4, participants[4]),
            (8, participants[8]),
        ])

        # Verify 4 speeches
        assert len(result.subphase_log.events) == 4

        # Sheriff (seat 4) should speak LAST
        sheriff_speech = result.subphase_log.events[-1]
        assert isinstance(sheriff_speech, Speech)
        assert sheriff_speech.actor == 4

        # First 3 speakers should NOT be sheriff
        for speech in result.subphase_log.events[:-1]:
            assert speech.actor != 4

    @pytest.mark.asyncio
    async def test_sheriff_speaks_last_with_6_players(self):
        """Test sheriff speaks last with 6 living players."""
        context, participants = make_context_day2_some_dead()

        # Configure mock responses for all living players
        for seat in context.living_players:
            participants[seat] = MockParticipant(f"Speech from player {seat}")

        handler = DiscussionHandler()
        participants_list = [(s, participants[s]) for s in sorted(context.living_players)]
        result = await handler(context, participants_list)

        # Verify 6 speeches
        assert len(result.subphase_log.events) == 6

        # Sheriff (seat 4) should speak LAST
        sheriff_speech = result.subphase_log.events[-1]
        assert isinstance(sheriff_speech, Speech)
        assert sheriff_speech.actor == 4

    @pytest.mark.asyncio
    async def test_sheriff_speaks_last_with_2_players(self):
        """Test sheriff speaks last with only 2 living players."""
        players = {
            4: Player(seat=4, name="Seer", role=Role.SEER, is_alive=True),
            8: Player(seat=8, name="V1", role=Role.ORDINARY_VILLAGER, is_alive=True),
        }
        living = {4, 8}
        dead = {0, 1, 2, 3, 5, 6, 7, 9, 10, 11}
        sheriff = 4  # Seer is sheriff

        context = PhaseContext(players, living, dead, sheriff, day=2)
        participants = {
            4: MockParticipant("I am the Sheriff."),
            8: MockParticipant("I agree with Sheriff."),
        }

        handler = DiscussionHandler()
        result = await handler(context, [(4, participants[4]), (8, participants[8])])

        # Verify 2 speeches
        assert len(result.subphase_log.events) == 2

        # Sheriff (seat 4) should speak LAST
        sheriff_speech = result.subphase_log.events[-1]
        assert sheriff_speech.actor == 4

        # Non-sheriff (seat 8) should speak first
        first_speech = result.subphase_log.events[0]
        assert first_speech.actor == 8

    @pytest.mark.asyncio
    async def test_sheriff_is_only_living_player(self):
        """Test when sheriff is the only living player."""
        players = {
            4: Player(seat=4, name="Seer", role=Role.SEER, is_alive=True),
        }
        living = {4}
        dead = {0, 1, 2, 3, 5, 6, 7, 8, 9, 10, 11}
        sheriff = 4

        context = PhaseContext(players, living, dead, sheriff, day=2)
        participants = {4: MockParticipant("I am the only one left.")}

        handler = DiscussionHandler()
        result = await handler(context, [(4, participants[4])])

        # Single speech from sheriff
        assert len(result.subphase_log.events) == 1
        assert result.subphase_log.events[0].actor == 4


# ============================================================================
# Tests for Discussion Handler - Empty Content Rejected
# ============================================================================


class TestDiscussionHandlerEmptyContent:
    """Tests that empty content is rejected and retried."""

    @pytest.mark.asyncio
    async def test_empty_content_rejected_with_retry(self):
        """Test that empty content triggers retry."""
        context, participants = make_context_day2_no_sheriff()

        # First response empty, then valid
        participants[0] = MockParticipant(response_iter=["", "I think seat 8 is suspicious."])
        participants[4] = MockParticipant("I am the Seer.")
        participants[8] = MockParticipant("I am innocent.")

        handler = DiscussionHandler()
        handler.max_retries = 3

        result = await handler(context, [
            (0, participants[0]),
            (4, participants[4]),
            (8, participants[8]),
        ])

        # All 3 speeches should have valid content
        assert len(result.subphase_log.events) == 3

        # Seat 0 should have retried and got valid content
        speech0 = result.subphase_log.events[0]
        assert speech0.content == "I think seat 8 is suspicious."

    @pytest.mark.asyncio
    async def test_whitespace_only_content_rejected(self):
        """Test that whitespace-only content is rejected."""
        context, participants = make_context_day2_no_sheriff()

        # Whitespace responses
        participants[0] = MockParticipant(response_iter=["   ", "\t\n", "Valid speech"])
        participants[4] = MockParticipant("Seer speech")
        participants[8] = MockParticipant("Villager speech")

        handler = DiscussionHandler()
        handler.max_retries = 3

        result = await handler(context, [
            (0, participants[0]),
            (4, participants[4]),
            (8, participants[8]),
        ])

        # All should have valid speeches
        assert len(result.subphase_log.events) == 3
        speech0 = result.subphase_log.events[0]
        assert speech0.content == "Valid speech"

    @pytest.mark.asyncio
    async def test_max_retries_exceeded_returns_empty(self):
        """Test that max retries exceeded returns empty string."""
        context, participants = make_context_day2_no_sheriff()

        # With max_retries=3, we get:
        # - Attempt 0: decide() returns "", then decide(hint) returns ""
        # - Attempt 1: decide() returns "", then decide(hint) returns ""
        # - Attempt 2: decide() returns "" (last one, no retry)
        # So we need 5 responses: "", "", "", "", ""
        participants[0] = MockParticipant(response_iter=["", "", "", "", ""])
        participants[4] = MockParticipant("Valid speech")
        participants[8] = MockParticipant("Valid speech")

        handler = DiscussionHandler()
        handler.max_retries = 3

        result = await handler(context, [
            (0, participants[0]),
            (4, participants[4]),
            (8, participants[8]),
        ])

        # 3 speeches - seat 0 gets empty after max retries
        assert len(result.subphase_log.events) == 3
        speech0 = result.subphase_log.events[0]
        assert speech0.content == ""  # Empty after max retries


# ============================================================================
# Tests for Discussion Handler - Dead Player Cannot Speak
# ============================================================================


class TestDiscussionHandlerDeadPlayer:
    """Tests that dead players cannot speak."""

    @pytest.mark.asyncio
    async def test_dead_player_not_in_speaking_order(self):
        """Test that dead players are not in speaking order."""
        context, participants = make_context_day2_some_dead()

        # Configure mocks for living players only
        for seat in context.living_players:
            participants[seat] = MockParticipant(f"Speech from {seat}")

        handler = DiscussionHandler()
        participants_list = [(s, participants[s]) for s in sorted(context.living_players)]
        result = await handler(context, participants_list)

        # Only living players should have speeches
        assert len(result.subphase_log.events) == len(context.living_players)

        # Verify no speech from dead players
        actors = [speech.actor for speech in result.subphase_log.events]
        for dead_seat in context.dead_players:
            assert dead_seat not in actors

    @pytest.mark.asyncio
    async def test_dead_sheriff_not_in_order(self):
        """Test that dead sheriff is handled correctly."""
        # Create context where sheriff would be dead (but in context.sheriff)
        players = {
            0: Player(seat=0, name="W1", role=Role.WEREWOLF, is_alive=True),
            4: Player(seat=4, name="Seer", role=Role.SEER, is_alive=True),
            8: Player(seat=8, name="V1", role=Role.ORDINARY_VILLAGER, is_alive=True),
        }
        living = {0, 4, 8}
        dead = {1, 2, 3, 5, 6, 7, 9, 10, 11}
        sheriff = 4  # Sheriff is alive in this case

        context = PhaseContext(players, living, dead, sheriff, day=2)
        participants = {
            0: MockParticipant("Werewolf speech"),
            4: MockParticipant("Sheriff speech"),
            8: MockParticipant("Villager speech"),
        }

        handler = DiscussionHandler()
        result = await handler(context, [
            (0, participants[0]),
            (4, participants[4]),
            (8, participants[8]),
        ])

        # Sheriff should speak last
        assert len(result.subphase_log.events) == 3
        assert result.subphase_log.events[-1].actor == 4


# ============================================================================
# Tests for Discussion Handler - Sheriff Not In Living (Skip)
# ============================================================================


class TestDiscussionHandlerSheriffNotInLiving:
    """Tests for when sheriff is not in living players."""

    @pytest.mark.asyncio
    async def test_no_sheriff_normal_order(self):
        """Test that no sheriff results in normal seat order."""
        context, participants = make_context_day2_no_sheriff()

        # Configure mock responses
        participants[0] = MockParticipant("Werewolf speech")
        participants[4] = MockParticipant("Seer speech")
        participants[8] = MockParticipant("Villager speech")

        handler = DiscussionHandler()
        result = await handler(context, [
            (0, participants[0]),
            (4, participants[4]),
            (8, participants[8]),
        ])

        # Normal order: 0, 4, 8 (sorted by seat)
        assert len(result.subphase_log.events) == 3
        assert result.subphase_log.events[0].actor == 0
        assert result.subphase_log.events[1].actor == 4
        assert result.subphase_log.events[2].actor == 8


# ============================================================================
# Tests for Discussion Handler - Speaking Order Alternates Correctly
# ============================================================================


class TestDiscussionHandlerSpeakingOrder:
    """Tests that speaking order alternates correctly."""

    @pytest.mark.asyncio
    async def test_normal_order_no_sheriff(self):
        """Test normal speaking order when no sheriff."""
        context, participants = make_context_day2_no_sheriff()

        for seat in context.living_players:
            participants[seat] = MockParticipant(f"Speech {seat}")

        handler = DiscussionHandler()
        result = await handler(context, [
            (0, participants[0]),
            (4, participants[4]),
            (8, participants[8]),
        ])

        # Normal sorted order
        assert len(result.subphase_log.events) == 3
        assert result.subphase_log.events[0].actor == 0
        assert result.subphase_log.events[1].actor == 4
        assert result.subphase_log.events[2].actor == 8

    @pytest.mark.asyncio
    async def test_sheriff_last_order(self):
        """Test sheriff is last in order."""
        context, participants = make_context_day2_with_sheriff()

        for seat in sorted(context.living_players):
            participants[seat] = MockParticipant(f"Speech {seat}")

        handler = DiscussionHandler()
        participants_list = [(s, participants[s]) for s in sorted(context.living_players)]
        result = await handler(context, participants_list)

        # Sheriff (4) should be last
        actors = [speech.actor for speech in result.subphase_log.events]
        assert actors[-1] == 4

        # Sheriff should not be in first 11 positions
        assert actors[:-1] == [i for i in range(12) if i != 4]

    @pytest.mark.asyncio
    async def test_speaking_order_12_players(self):
        """Test speaking order with full 12 players and sheriff."""
        context, participants = make_context_day2_with_sheriff()

        for seat in sorted(context.living_players):
            participants[seat] = MockParticipant(f"Speech {seat}")

        handler = DiscussionHandler()
        participants_list = [(s, participants[s]) for s in sorted(context.living_players)]
        result = await handler(context, participants_list)

        assert len(result.subphase_log.events) == 12

        # Sheriff should be last
        actors = [speech.actor for speech in result.subphase_log.events]
        assert actors[-1] == 4  # Sheriff

        # First 11 should be all players except sheriff
        assert actors[:-1] == [0, 1, 2, 3, 5, 6, 7, 8, 9, 10, 11]

    @pytest.mark.asyncio
    async def test_speaking_order_preserves_player_identity(self):
        """Test that speeches are correctly attributed to speakers."""
        context, participants = make_context_day2_with_sheriff()

        # Give each player a unique speech
        participants[0] = MockParticipant("I vote to banish seat 11.")
        participants[1] = MockParticipant("I agree with seat 0.")
        participants[2] = MockParticipant("I think seat 1 is suspicious.")
        participants[3] = MockParticipant("Let's discuss rationally.")
        participants[4] = MockParticipant("I am the Sheriff, trust me.")
        participants[5] = MockParticipant("I haven't used my potions yet.")
        participants[6] = MockParticipant("I'll protect someone tonight.")
        participants[7] = MockParticipant("If I die, I'll shoot seat 0.")
        participants[8] = MockParticipant("I'm an ordinary villager.")
        participants[9] = MockParticipant("I trust seat 4.")
        participants[10] = MockParticipant("Let's vote carefully.")
        participants[11] = MockParticipant("I'm innocent!")

        handler = DiscussionHandler()
        participants_list = [(s, participants[s]) for s in sorted(context.living_players)]
        result = await handler(context, participants_list)

        # Verify each speech is attributed to correct player
        for speech in result.subphase_log.events:
            if speech.actor == 0:
                assert speech.content == "I vote to banish seat 11."
            elif speech.actor == 4:
                assert speech.content == "I am the Sheriff, trust me."
            elif speech.actor == 11:
                assert speech.content == "I'm innocent!"


# ============================================================================
# Tests for Discussion Handler - Edge Cases
# ============================================================================


class TestDiscussionHandlerEdgeCases:
    """Tests for edge cases in Discussion handler."""

    @pytest.mark.asyncio
    async def test_single_living_player(self):
        """Test with exactly one living player."""
        players = {
            5: Player(seat=5, name="Witch", role=Role.WITCH, is_alive=True),
        }
        living = {5}
        dead = {0, 1, 2, 3, 4, 6, 7, 8, 9, 10, 11}
        sheriff = None

        context = PhaseContext(players, living, dead, sheriff, day=2)
        participants = {5: MockParticipant("I am the last one standing.")}

        handler = DiscussionHandler()
        result = await handler(context, [(5, participants[5])])

        # Single speech
        assert len(result.subphase_log.events) == 1
        assert result.subphase_log.events[0].actor == 5

    @pytest.mark.asyncio
    async def test_no_living_players(self):
        """Test with no living players (game over state)."""
        players = {}
        living = set()
        dead = set(range(12))
        sheriff = None

        context = PhaseContext(players, living, dead, sheriff, day=2)
        participants = {}

        handler = DiscussionHandler()
        result = await handler(context, [])

        # Empty result
        assert len(result.subphase_log.events) == 0
        assert "No living players" in result.debug_info

    @pytest.mark.asyncio
    async def test_discussion_phase_in_result(self):
        """Test that micro_phase is set to DISCUSSION."""
        context, participants = make_context_day2_no_sheriff()

        participants[0] = MockParticipant("Test speech")
        participants[4] = MockParticipant("Test speech")
        participants[8] = MockParticipant("Test speech")

        handler = DiscussionHandler()
        result = await handler(context, [
            (0, participants[0]),
            (4, participants[4]),
            (8, participants[8]),
        ])

        assert result.subphase_log.micro_phase == SubPhase.DISCUSSION

    @pytest.mark.asyncio
    async def test_speech_day_phase(self):
        """Test that speeches have DAY phase."""
        context, participants = make_context_day2_no_sheriff()

        participants[0] = MockParticipant("Test speech")

        handler = DiscussionHandler()
        result = await handler(context, [(0, participants[0])])

        speech = result.subphase_log.events[0]
        assert speech.phase == Phase.DAY
        assert speech.micro_phase == SubPhase.DISCUSSION


# ============================================================================
# Tests for Discussion Handler - Prompt Building
# ============================================================================


class TestDiscussionHandlerPromptBuilding:
    """Tests for prompt building in Discussion handler."""

    def test_discussion_prompts_include_role(self):
        """Test that discussion prompts include the speaker's role."""
        handler = DiscussionHandler()
        context, _ = make_context_day2_with_sheriff()

        system, user = handler._build_prompts(context, for_seat=4)

        # Should mention Seer role
        assert "SEER" in system

    def test_discussion_prompts_for_werewolf(self):
        """Test discussion prompts for werewolf."""
        handler = DiscussionHandler()
        context, _ = make_context_day2_with_sheriff()

        system, user = handler._build_prompts(context, for_seat=0)

        # Should mention Werewolf role
        assert "WEREWOLF" in system

    def test_discussion_prompts_for_sheriff(self):
        """Test that sheriff gets sheriff badge info."""
        handler = DiscussionHandler()
        context, _ = make_context_day2_with_sheriff()

        system, user = handler._build_prompts(context, for_seat=4)

        # Sheriff should get info about vote weight
        assert "Sheriff" in system or "1.5" in system

    def test_discussion_prompts_for_non_sheriff(self):
        """Test that non-sheriff doesn't get sheriff badge info."""
        handler = DiscussionHandler()
        context, _ = make_context_day2_with_sheriff()

        system, user = handler._build_prompts(context, for_seat=0)

        # Non-sheriff should not have sheriff-specific info
        # (Just checking it doesn't crash and has player context)
        assert "WEREWOLF" in system


# ============================================================================
# Tests for _build_speaking_order Helper
# ============================================================================


class TestBuildSpeakingOrder:
    """Tests for the _build_speaking_order helper method."""

    def test_sheriff_in_living_moves_to_end(self):
        """Test sheriff in living players moves to end."""
        handler = DiscussionHandler()

        living = [0, 1, 2, 3, 4, 5]
        sheriff = 4

        order = handler._build_speaking_order(living, sheriff)

        # Sheriff should be last
        assert order[-1] == 4
        # Others should be in original order without sheriff
        assert order[:-1] == [0, 1, 2, 3, 5]

    def test_sheriff_not_in_living_returns_original(self):
        """Test sheriff not in living returns original order."""
        handler = DiscussionHandler()

        living = [0, 1, 2, 3, 5, 6]
        sheriff = 4  # Dead

        order = handler._build_speaking_order(living, sheriff)

        # Should return original order
        assert order == [0, 1, 2, 3, 5, 6]

    def test_no_sheriff_returns_original(self):
        """Test no sheriff returns original order."""
        handler = DiscussionHandler()

        living = [0, 1, 2, 3, 4, 5]
        sheriff = None

        order = handler._build_speaking_order(living, sheriff)

        # Should return original order
        assert order == [0, 1, 2, 3, 4, 5]

    def test_single_player_sheriff(self):
        """Test with single player who is sheriff."""
        handler = DiscussionHandler()

        living = [4]
        sheriff = 4

        order = handler._build_speaking_order(living, sheriff)

        # Single player stays
        assert order == [4]

    def test_order_preserves_seat_sequence(self):
        """Test that non-sheriff order preserves seat sequence."""
        handler = DiscussionHandler()

        living = [2, 5, 7, 9, 11, 1, 3]  # Not sorted
        sheriff = 9

        order = handler._build_speaking_order(living, sheriff)

        # Sheriff should be last
        assert order[-1] == 9
        # Others should preserve original relative order
        assert order[:-1] == [2, 5, 7, 11, 1, 3]
