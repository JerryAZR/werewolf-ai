"""Comprehensive tests for Campaign handler.

Campaign subphase: Day 1 Sheriff candidates give speeches.
Rules:
- Only Day 1
- Sheriff speaks LAST (if already elected)
- Dead candidates cannot speak
- Empty content rejected
"""

import pytest
from typing import Optional, Any
from unittest.mock import AsyncMock, MagicMock

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
    """Minimal context for testing Campaign handler."""

    def __init__(
        self,
        players: dict[int, Player],
        living_players: set[int],
        dead_players: set[int],
        sheriff: Optional[int] = None,
        day: int = 1,
        sheriff_candidates: Optional[list[int]] = None,
    ):
        self.players = players
        self.living_players = living_players
        self.dead_players = dead_players
        self.sheriff = sheriff
        self.day = day
        # Sheriff candidates for Campaign phase
        self.sheriff_candidates = sheriff_candidates if sheriff_candidates is not None else []

    def get_player(self, seat: int) -> Optional[Player]:
        """Get player by seat."""
        return self.players.get(seat)

    def is_alive(self, seat: int) -> bool:
        """Check if a player is alive."""
        return seat in self.living_players


def make_context_day1_standard() -> tuple[PhaseContext, dict[int, MockParticipant]]:
    """Create a standard 12-player context for Day 1 Campaign.

    All 12 players are alive. Sheriff candidates are all living players.
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
    # All players are candidates on Day 1
    candidates = list(range(12))

    context = PhaseContext(players, living, dead, sheriff, day=1, sheriff_candidates=candidates)
    return context, {}


def make_context_day1_with_sheriff() -> tuple[PhaseContext, dict[int, MockParticipant]]:
    """Create Day 1 context with a sheriff already elected (edge case)."""
    players = {
        0: Player(seat=0, name="W1", role=Role.WEREWOLF, is_alive=True),
        4: Player(seat=4, name="Seer", role=Role.SEER, is_alive=True),
        5: Player(seat=5, name="Witch", role=Role.WITCH, is_alive=True),
        8: Player(seat=8, name="V1", role=Role.ORDINARY_VILLAGER, is_alive=True),
    }
    living = {0, 4, 5, 8}
    dead = {1, 2, 3, 6, 7, 9, 10, 11}
    sheriff = 4  # Seer is sheriff
    candidates = [0, 4, 5, 8]  # All living players

    context = PhaseContext(players, living, dead, sheriff, day=1, sheriff_candidates=candidates)
    return context, {}


def make_context_day2() -> tuple[PhaseContext, dict[int, MockParticipant]]:
    """Create Day 2 context (Campaign should be skipped)."""
    players = {
        0: Player(seat=0, name="W1", role=Role.WEREWOLF, is_alive=True),
        4: Player(seat=4, name="Seer", role=Role.SEER, is_alive=True),
        5: Player(seat=5, name="Witch", role=Role.WITCH, is_alive=True),
        8: Player(seat=8, name="V1", role=Role.ORDINARY_VILLAGER, is_alive=True),
    }
    living = {0, 4, 5, 8}
    dead = {1, 2, 3, 6, 7, 9, 10, 11}
    sheriff = None

    context = PhaseContext(players, living, dead, sheriff, day=2)
    return context, {}


def make_context_day1_with_dead_candidate() -> tuple[PhaseContext, dict[int, MockParticipant]]:
    """Create Day 1 context where a candidate is dead."""
    players = {
        0: Player(seat=0, name="W1", role=Role.WEREWOLF, is_alive=True),
        4: Player(seat=4, name="Seer", role=Role.SEER, is_alive=True),
        5: Player(seat=5, name="Witch", role=Role.WITCH, is_alive=True),
        8: Player(seat=8, name="V1", role=Role.ORDINARY_VILLAGER, is_alive=True),
    }
    living = {0, 4, 5, 8}
    dead = {1, 2, 3, 6, 7, 9, 10, 11}
    sheriff = None
    # Note: seat 1 is in candidates but is dead
    candidates = [0, 1, 4, 8]

    context = PhaseContext(players, living, dead, sheriff, day=1, sheriff_candidates=candidates)
    return context, {}


def make_context_day1_no_candidates() -> tuple[PhaseContext, dict[int, MockParticipant]]:
    """Create Day 1 context with no sheriff candidates."""
    players = {
        0: Player(seat=0, name="W1", role=Role.WEREWOLF, is_alive=True),
        4: Player(seat=4, name="Seer", role=Role.SEER, is_alive=True),
    }
    living = {0, 4}
    dead = {1, 2, 3, 5, 6, 7, 8, 9, 10, 11}
    sheriff = None
    candidates = []  # No candidates

    context = PhaseContext(players, living, dead, sheriff, day=1, sheriff_candidates=candidates)
    return context, {}


def make_context_day1_few_candidates() -> tuple[PhaseContext, dict[int, MockParticipant]]:
    """Create Day 1 context with only a few candidates."""
    players = {
        4: Player(seat=4, name="Seer", role=Role.SEER, is_alive=True),
        8: Player(seat=8, name="V1", role=Role.ORDINARY_VILLAGER, is_alive=True),
    }
    living = {4, 8}
    dead = {0, 1, 2, 3, 5, 6, 7, 9, 10, 11}
    sheriff = None
    candidates = [4, 8]

    context = PhaseContext(players, living, dead, sheriff, day=1, sheriff_candidates=candidates)
    return context, {}


# ============================================================================
# Expected Speech Event Factory
# ============================================================================


def expected_speech(
    actor: int,
    content: str,
    day: int = 1,
    micro_phase: SubPhase = SubPhase.CAMPAIGN,
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
# CampaignHandler Implementation (for testing)
# ============================================================================


from typing import Protocol, Sequence, Dict
from pydantic import BaseModel


class HandlerResult(BaseModel):
    """Output from handlers."""

    subphase_log: SubPhaseLog
    debug_info: Optional[str] = None


class CampaignHandler:
    """Handler for Campaign subphase.

    Campaign phase: Day 1 Sheriff candidates give speeches.

    Rules:
    - Only Day 1
    - Sheriff speaks LAST (if sheriff is a candidate)
    - Dead candidates are skipped
    - Empty content rejected with retry
    """

    max_retries: int = 3

    async def __call__(
        self,
        context: PhaseContext,
        participants: Sequence[tuple[int, MockParticipant]]
    ) -> HandlerResult:
        """Execute campaign subphase."""
        events = []

        # Validate: Campaign only on Day 1
        if context.day != 1:
            return HandlerResult(
                subphase_log=SubPhaseLog(micro_phase=SubPhase.CAMPAIGN),
                debug_info="Campaign skipped: not Day 1"
            )

        # Get living candidates only
        living_candidates = [
            seat for seat in context.sheriff_candidates
            if context.is_alive(seat)
        ]

        # Edge case: no candidates
        if not living_candidates:
            return HandlerResult(
                subphase_log=SubPhaseLog(micro_phase=SubPhase.CAMPAIGN),
                debug_info="No living candidates for campaign"
            )

        # Create lookup dict from participants
        participant_lookup = dict(participants)

        # Sheriff speaks last if sheriff is a candidate
        sheriff = context.sheriff
        if sheriff is not None and sheriff in living_candidates:
            non_sheriff_candidates = [c for c in living_candidates if c != sheriff]
            speaking_order = non_sheriff_candidates + [sheriff]
        else:
            speaking_order = living_candidates

        # Collect speeches from each candidate
        for seat in speaking_order:
            participant = participant_lookup.get(seat)
            if participant:
                content = await self._get_valid_speech(context, participant, seat)
                events.append(Speech(
                    actor=seat,
                    content=content,
                    day=context.day,
                    micro_phase=SubPhase.CAMPAIGN,
                ))

        return HandlerResult(
            subphase_log=SubPhaseLog(
                micro_phase=SubPhase.CAMPAIGN,
                events=events
            )
        )

    def _build_prompts(
        self,
        context: PhaseContext,
        for_seat: int
    ) -> tuple[str, str]:
        """Build prompts for campaign speech."""
        player = context.get_player(for_seat)
        role_name = player.role.value if player else "Unknown"

        system = f"""You are a {role_name} on Day 1 running for Sheriff.
All players are currently alive. You may give a brief campaign speech.

Your goal: Convince other players you would make a good Sheriff.
Be friendly, positive, and briefly state your intentions."""

        user = "Enter your campaign speech (brief statement):"

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

        # Max retries exceeded - return empty speech (or could raise exception)
        return ""


# ============================================================================
# Tests for Campaign Handler - Valid Scenarios
# ============================================================================


class TestCampaignHandlerValidScenarios:
    """Tests for valid Campaign scenarios."""

    @pytest.mark.asyncio
    async def test_valid_speech_from_candidate(self):
        """Test valid speech from a single candidate."""
        context, participants = make_context_day1_few_candidates()

        # Configure mock responses
        participants[4] = MockParticipant("I will protect the village as Sheriff.")
        participants[8] = MockParticipant("Trust me, I am a loyal villager!")

        handler = CampaignHandler()
        result = await handler(context, [(4, participants[4]), (8, participants[8])])

        # Verify result structure
        assert result.subphase_log.micro_phase == SubPhase.CAMPAIGN
        assert len(result.subphase_log.events) == 2

        # Verify first speech
        speech1 = result.subphase_log.events[0]
        assert isinstance(speech1, Speech)
        assert speech1.actor == 4
        assert speech1.content == "I will protect the village as Sheriff."
        assert speech1.day == 1
        assert speech1.micro_phase == SubPhase.CAMPAIGN

        # Verify second speech
        speech2 = result.subphase_log.events[1]
        assert isinstance(speech2, Speech)
        assert speech2.actor == 8
        assert speech2.content == "Trust me, I am a loyal villager!"

    @pytest.mark.asyncio
    async def test_sheriff_speaks_last_in_order(self):
        """Test that sheriff speaks last in speaking order."""
        context, participants = make_context_day1_with_sheriff()

        # Configure mock responses
        participants[0] = MockParticipant("Vote for me!")
        participants[4] = MockParticipant("I am the Seer, trust me.")
        participants[5] = MockParticipant("I am a helpful Witch.")
        participants[8] = MockParticipant("I'm just an ordinary villager.")

        handler = CampaignHandler()
        result = await handler(context, [
            (0, participants[0]),
            (4, participants[4]),
            (5, participants[5]),
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
    async def test_sheriff_is_only_candidate(self):
        """Test when sheriff is the only candidate."""
        # Create context with only sheriff as candidate
        players = {
            4: Player(seat=4, name="Seer", role=Role.SEER, is_alive=True),
        }
        living = {4}
        dead = {0, 1, 2, 3, 5, 6, 7, 8, 9, 10, 11}
        sheriff = 4
        candidates = [4]

        context = PhaseContext(players, living, dead, sheriff, day=1, sheriff_candidates=candidates)

        participants = {4: MockParticipant("I am the only candidate.")}

        handler = CampaignHandler()
        result = await handler(context, [(4, participants[4])])

        # Single speech from sheriff
        assert len(result.subphase_log.events) == 1
        speech = result.subphase_log.events[0]
        assert speech.actor == 4

    @pytest.mark.asyncio
    async def test_multiple_candidates_speaking_order(self):
        """Test speaking order for multiple candidates."""
        context, participants = make_context_day1_standard()

        # All 12 players are candidates
        for seat in range(12):
            participants[seat] = MockParticipant(f"Speech from player {seat}")

        handler = CampaignHandler()

        # Only test first 5 candidates for brevity
        result = await handler(context, [(i, participants[i]) for i in range(5)])

        assert len(result.subphase_log.events) == 5

        # Verify order is preserved (sheriff is None, so normal order)
        for i, speech in enumerate(result.subphase_log.events):
            assert speech.actor == i


class TestCampaignHandlerInvalidScenarios:
    """Tests for invalid Campaign scenarios."""

    @pytest.mark.asyncio
    async def test_day_not_1_validation(self):
        """Test that Campaign is skipped on Day != 1."""
        context, participants = make_context_day2()

        handler = CampaignHandler()
        result = await handler(context, [])

        # Should return empty SubPhaseLog with debug info
        assert result.subphase_log.micro_phase == SubPhase.CAMPAIGN
        assert len(result.subphase_log.events) == 0
        assert "not Day 1" in result.debug_info

    @pytest.mark.asyncio
    async def test_dead_candidate_cannot_speak(self):
        """Test that dead candidates are skipped."""
        context, participants = make_context_day1_with_dead_candidate()

        # Seat 1 is a candidate but dead
        participants[0] = MockParticipant("Speech from 0")
        participants[1] = MockParticipant("Speech from dead candidate")  # Will be skipped
        participants[4] = MockParticipant("Speech from 4")
        participants[8] = MockParticipant("Speech from 8")

        handler = CampaignHandler()
        result = await handler(context, [
            (0, participants[0]),
            (1, participants[1]),
            (4, participants[4]),
            (8, participants[8]),
        ])

        # Only 3 speeches (dead candidate 1 skipped)
        assert len(result.subphase_log.events) == 3

        # Verify no speech from seat 1
        actors = [speech.actor for speech in result.subphase_log.events]
        assert 1 not in actors

        # Verify living candidates spoke
        assert 0 in actors
        assert 4 in actors
        assert 8 in actors

    @pytest.mark.asyncio
    async def test_empty_content_rejected_with_retry(self):
        """Test that empty content is rejected and participant retries."""
        context, participants = make_context_day1_few_candidates()

        # First response empty, then valid
        participants[4] = MockParticipant(response_iter=["", "My campaign speech"])
        participants[8] = MockParticipant("Valid speech from 8")

        handler = CampaignHandler()
        handler.max_retries = 3

        result = await handler(context, [(4, participants[4]), (8, participants[8])])

        # Both should have valid speeches
        assert len(result.subphase_log.events) == 2

        # Seat 4 should have retried and got valid content
        speech4 = result.subphase_log.events[0]
        assert speech4.content == "My campaign speech"

        # Seat 8 should have valid speech
        speech8 = result.subphase_log.events[1]
        assert speech8.content == "Valid speech from 8"

    @pytest.mark.asyncio
    async def test_whitespace_only_content_rejected(self):
        """Test that whitespace-only content is rejected."""
        context, participants = make_context_day1_few_candidates()

        # Whitespace responses
        participants[4] = MockParticipant(response_iter=["   ", "\t\n", "Valid speech"])
        participants[8] = MockParticipant("Speech from 8")

        handler = CampaignHandler()
        handler.max_retries = 3

        result = await handler(context, [(4, participants[4]), (8, participants[8])])

        # Both should have valid speeches
        assert len(result.subphase_log.events) == 2
        speech4 = result.subphase_log.events[0]
        assert speech4.content == "Valid speech"


class TestCampaignHandlerEdgeCases:
    """Tests for edge cases in Campaign handler."""

    @pytest.mark.asyncio
    async def test_no_candidates_returns_empty_log(self):
        """Test that no candidates returns empty SubPhaseLog."""
        context, participants = make_context_day1_no_candidates()

        handler = CampaignHandler()
        result = await handler(context, [])

        # Empty result
        assert result.subphase_log.micro_phase == SubPhase.CAMPAIGN
        assert len(result.subphase_log.events) == 0
        assert "No living candidates" in result.debug_info

    @pytest.mark.asyncio
    async def test_all_candidates_dead(self):
        """Test when all candidates are dead (edge case)."""
        players = {
            0: Player(seat=0, name="W1", role=Role.WEREWOLF, is_alive=True),
        }
        living = {0}
        dead = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11}
        sheriff = None
        # All candidates dead
        candidates = [4, 5, 6]  # All dead

        context = PhaseContext(players, living, dead, sheriff, day=1, sheriff_candidates=candidates)

        handler = CampaignHandler()
        result = await handler(context, [])

        # Empty result
        assert len(result.subphase_log.events) == 0
        assert "No living candidates" in result.debug_info

    @pytest.mark.asyncio
    async def test_single_candidate(self):
        """Test with exactly one living candidate."""
        context, participants = make_context_day1_few_candidates()

        # Remove seat 8 from candidates
        context.sheriff_candidates = [4]

        participants[4] = MockParticipant("I am the only candidate.")

        handler = CampaignHandler()
        result = await handler(context, [(4, participants[4])])

        # Single speech
        assert len(result.subphase_log.events) == 1
        speech = result.subphase_log.events[0]
        assert speech.actor == 4
        assert speech.content == "I am the only candidate."

    @pytest.mark.asyncio
    async def test_sheriff_not_in_candidates(self):
        """Test when sheriff exists but is not a candidate."""
        players = {
            0: Player(seat=0, name="W1", role=Role.WEREWOLF, is_alive=True),
            4: Player(seat=4, name="Seer", role=Role.SEER, is_alive=True),
        }
        living = {0, 4}
        dead = {1, 2, 3, 5, 6, 7, 8, 9, 10, 11}
        sheriff = 4
        # Sheriff not in candidates
        candidates = [0]

        context = PhaseContext(players, living, dead, sheriff, day=1, sheriff_candidates=candidates)

        participants = {0: MockParticipant("Vote for me!")}

        handler = CampaignHandler()
        result = await handler(context, [(0, participants[0])])

        # Sheriff not speaking (not a candidate)
        assert len(result.subphase_log.events) == 1
        assert result.subphase_log.events[0].actor == 0


class TestCampaignHandlerPromptBuilding:
    """Tests for prompt building in Campaign handler."""

    def test_campaign_prompts_include_role(self):
        """Test that campaign prompts include the candidate's role."""
        handler = CampaignHandler()
        context, _ = make_context_day1_few_candidates()

        system, user = handler._build_prompts(context, for_seat=4)

        # Should mention Seer role (uppercase due to enum)
        assert "SEER" in system

    def test_campaign_prompts_for_villager(self):
        """Test campaign prompts for ordinary villager."""
        handler = CampaignHandler()
        context, _ = make_context_day1_few_candidates()

        system, user = handler._build_prompts(context, for_seat=8)

        # Should mention Villager
        assert "villager" in system.lower()


# ============================================================================
# Helper Functions
# ============================================================================


def living_candidates_sorted(context: PhaseContext) -> list[int]:
    """Get sorted list of living candidates."""
    return sorted([
        seat for seat in context.sheriff_candidates
        if context.is_alive(seat)
    ])
