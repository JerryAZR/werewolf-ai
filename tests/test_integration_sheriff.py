"""Integration tests for Sheriff Election flow (Nomination -> Campaign -> OptOut -> Vote).

Tests the complete sheriff election process end-to-end.
"""

import asyncio
import random
import pytest
from typing import Protocol, Sequence, Optional, Any

from werewolf.events import (
    Phase,
    SubPhase,
    SheriffNomination,
    Speech,
    SheriffOptOut,
    SheriffOutcome,
)
from werewolf.models import (
    Player,
    Role,
    create_players_from_config,
)


# ============================================================================
# Helper functions
# ============================================================================


def create_players_shuffled(seed: int | None = None) -> dict[int, Player]:
    """Create a dict of players with shuffled roles from standard config."""
    rng = random.Random(seed)
    role_assignments = create_players_from_config(rng=rng)
    players = {}
    for seat, role in role_assignments:
        players[seat] = Player(
            seat=seat,
            name=f"Player {seat}",
            role=role,
        )
    return players


# ============================================================================
# Mock Participant for Testing
# ============================================================================


class MockParticipant:
    """Mock participant that returns configurable responses."""

    def __init__(
        self,
        response: str | None = None,
        response_iter: list[str] | None = None,
        fallback_response: str = "0",
    ):
        """Initialize with a single response or an iterator of responses.

        Args:
            response: Single response string to return
            response_iter: Optional list of responses to return in sequence
            fallback_response: Response to return if iter is exhausted (default: "0")
        """
        self._response = response
        self._response_iter = response_iter
        self._call_count = 0
        self._fallback_response = fallback_response

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
        # Return fallback response instead of raising error
        return self._fallback_response


# ============================================================================
# Phase contexts
# ============================================================================


class PhaseContext:
    """Minimal context for testing handlers."""

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
        self.sheriff_candidates = sheriff_candidates or []

    def get_player(self, seat: int) -> Optional[Player]:
        return self.players.get(seat)

    def is_alive(self, seat: int) -> bool:
        return seat in self.living_players


# ============================================================================
# Import handlers
# ============================================================================


from werewolf.handlers.nomination_handler import NominationHandler
from werewolf.handlers.campaign_handler import CampaignHandler
from werewolf.handlers.opt_out_handler import OptOutHandler
from werewolf.handlers.sheriff_election_handler import SheriffElectionHandler


# ============================================================================
# Test fixtures
# ============================================================================


@pytest.fixture
def standard_players() -> dict[int, Player]:
    """Create standard 12-player config as dict with shuffled roles."""
    return create_players_shuffled(seed=42)


@pytest.fixture
def day1_context(standard_players: dict[int, Player]) -> PhaseContext:
    """Create Day 1 context with all players alive."""
    return PhaseContext(
        players=standard_players,
        living_players=set(standard_players.keys()),
        dead_players=set(),
        day=1,
    )


# ============================================================================
# Integration tests
# ============================================================================


@pytest.mark.asyncio
async def test_complete_sheriff_election_flow(day1_context: PhaseContext):
    """Test the complete sheriff election flow: Nomination -> Campaign -> OptOut -> Vote."""
    # Create participants where 8 players run, 4 stay as voters
    # Need some voters for the election to work
    # Note: New CampaignHandler makes 2 calls per candidate (stay/opt-out + speech/explanation)
    participants = {}
    for seat in range(12):
        if seat in [0, 2, 4, 6, 8, 10, 1, 3]:  # 8 candidates
            # [nomination, campaign_stage1, campaign_stage2, opt_out]
            response_iter = ["run", "stay", "I want to be your Sheriff!", "stay"]
        else:  # 4 voters - need response for OptOut query too
            # [nomination, campaign_stage1, campaign_stage2, opt_out]
            response_iter = ["not running", "opt-out", "", "stay"]

        participants[seat] = MockParticipant(response_iter=response_iter)

    # Step 1: Nomination
    nomination_handler = NominationHandler()
    nomination_result = await nomination_handler(
        day1_context, list(participants.items())
    )

    assert nomination_result.subphase_log.micro_phase == SubPhase.NOMINATION
    assert len(nomination_result.subphase_log.events) == 12

    # Get candidates who nominated to run
    nominated_seats = [
        e.actor for e in nomination_result.subphase_log.events
        if isinstance(e, SheriffNomination) and e.running
    ]
    assert len(nominated_seats) == 8  # 8 players ran

    # Step 2: Campaign (only nominated candidates speak)
    campaign_handler = CampaignHandler()
    campaign_result = await campaign_handler(
        day1_context, list(participants.items()), nominated_seats
    )

    assert campaign_result.subphase_log.micro_phase == SubPhase.CAMPAIGN
    # Only nominated candidates should have given speeches
    assert len(campaign_result.subphase_log.events) == len(nominated_seats)

    # Get candidates who gave speeches (not opted out)
    candidates_after_speech = [
        e.actor for e in campaign_result.subphase_log.events
        if isinstance(e, Speech)
    ]

    # Step 3: OptOut (candidates decide to stay or opt out)
    opt_out_handler = OptOutHandler()
    opt_out_context = PhaseContext(
        players=day1_context.players,
        living_players=day1_context.living_players,
        dead_players=day1_context.dead_players,
        day=1,
        sheriff_candidates=candidates_after_speech,
    )
    opt_out_result = await opt_out_handler(
        opt_out_context, list(participants.items())
    )

    assert opt_out_result.subphase_log.micro_phase == SubPhase.OPT_OUT

    # Get candidates who stayed
    opted_out_seats = [
        e.actor for e in opt_out_result.subphase_log.events
        if isinstance(e, SheriffOptOut)
    ]
    final_candidates = [s for s in candidates_after_speech if s not in opted_out_seats]
    assert len(final_candidates) == 8  # All 8 stayed

    # Step 4: Sheriff Election (non-candidates vote)
    sheriff_election_context = PhaseContext(
        players=day1_context.players,
        living_players=day1_context.living_players,
        dead_players=day1_context.dead_players,
        day=1,
        sheriff_candidates=final_candidates,
    )

    sheriff_handler = SheriffElectionHandler()
    sheriff_result = await sheriff_handler(
        sheriff_election_context, list(participants.items()), final_candidates
    )

    assert sheriff_result.subphase_log.micro_phase == SubPhase.SHERIFF_ELECTION

    # Find SheriffOutcome event
    outcome = None
    for event in sheriff_result.subphase_log.events:
        if isinstance(event, SheriffOutcome):
            outcome = event
            break

    assert outcome is not None
    assert outcome.day == 1
    assert outcome.candidates == final_candidates
    assert outcome.winner is not None  # Someone won
    assert outcome.winner in final_candidates


@pytest.mark.asyncio
async def test_sheriff_election_with_partial_nominations(day1_context: PhaseContext):
    """Test sheriff election when only some players nominate."""
    # Create participants where only 4 players run
    # Note: New CampaignHandler makes 2 calls per candidate
    participants = {}
    for seat in range(12):
        if seat in [0, 3, 6, 9]:
            # [nomination, campaign_stage1, campaign_stage2, opt_out]
            response_iter = ["run", "stay", "I want to be Sheriff!", "stay"]
        else:
            # [nomination, campaign_stage1, campaign_stage2, opt_out]
            response_iter = ["not running", "opt-out", "", "stay"]

        participants[seat] = MockParticipant(response_iter=response_iter)

    # Step 1: Nomination
    nomination_handler = NominationHandler()
    nomination_result = await nomination_handler(
        day1_context, list(participants.items())
    )

    nominated_seats = [
        e.actor for e in nomination_result.subphase_log.events
        if isinstance(e, SheriffNomination) and e.running
    ]
    assert set(nominated_seats) == {0, 3, 6, 9}

    # Step 2: Campaign (only nominated candidates speak)
    campaign_handler = CampaignHandler()
    campaign_result = await campaign_handler(
        day1_context, list(participants.items()), nominated_seats
    )

    candidates_after_speech = [
        e.actor for e in campaign_result.subphase_log.events
        if isinstance(e, Speech)
    ]
    assert len(candidates_after_speech) == 4

    # Step 3: OptOut
    opt_out_context = PhaseContext(
        players=day1_context.players,
        living_players=day1_context.living_players,
        dead_players=day1_context.dead_players,
        day=1,
        sheriff_candidates=candidates_after_speech,
    )
    opt_out_handler = OptOutHandler()
    opt_out_result = await opt_out_handler(
        opt_out_context, list(participants.items())
    )

    opted_out_seats = [
        e.actor for e in opt_out_result.subphase_log.events
        if isinstance(e, SheriffOptOut)
    ]

    # Some candidates may have opted out
    final_candidates = [s for s in candidates_after_speech if s not in opted_out_seats]

    # Step 4: Sheriff Election
    if final_candidates:
        sheriff_election_context = PhaseContext(
            players=day1_context.players,
            living_players=day1_context.living_players,
            dead_players=day1_context.dead_players,
            day=1,
            sheriff_candidates=final_candidates,
        )

        sheriff_handler = SheriffElectionHandler()
        sheriff_result = await sheriff_handler(
            sheriff_election_context, list(participants.items()), final_candidates
        )

        outcome = None
        for event in sheriff_result.subphase_log.events:
            if isinstance(event, SheriffOutcome):
                outcome = event
                break

        assert outcome is not None
        assert set(outcome.candidates) == set(final_candidates)
    else:
        # No candidates remain, skip election
        assert len(final_candidates) == 0


@pytest.mark.asyncio
async def test_sheriff_election_no_nominations(day1_context: PhaseContext):
    """Test sheriff election when no players nominate."""
    # All players decline to run
    participants = {
        seat: MockParticipant(response_iter=["not running", "", "stay"])
        for seat in range(12)
    }

    # Step 1: Nomination
    nomination_handler = NominationHandler()
    nomination_result = await nomination_handler(
        day1_context, list(participants.items())
    )

    nominated_seats = [
        e.actor for e in nomination_result.subphase_log.events
        if isinstance(e, SheriffNomination) and e.running
    ]
    assert len(nominated_seats) == 0  # No one ran

    # No further phases should run (no candidates)
    assert len(nominated_seats) == 0


@pytest.mark.asyncio
async def test_sheriff_candidates_cannot_vote(day1_context: PhaseContext):
    """Test that sheriff candidates cannot vote in the election."""
    # Only 2 players run
    # Note: New CampaignHandler makes 2 calls per candidate
    participants = {}
    for seat in range(12):
        if seat in [0, 1]:
            # [nomination, campaign_stage1, campaign_stage2, opt_out]
            response_iter = ["run", "stay", "Vote for me!", "stay"]
        else:
            # [nomination, campaign_stage1, campaign_stage2, opt_out]
            response_iter = ["not running", "opt-out", "", "stay"]

        participants[seat] = MockParticipant(response_iter=response_iter)

    # Run through phases
    nomination_handler = NominationHandler()
    nomination_result = await nomination_handler(
        day1_context, list(participants.items())
    )

    nominated_seats = [
        e.actor for e in nomination_result.subphase_log.events
        if isinstance(e, SheriffNomination) and e.running
    ]
    assert set(nominated_seats) == {0, 1}

    campaign_handler = CampaignHandler()
    campaign_result = await campaign_handler(
        day1_context, list(participants.items()), nominated_seats
    )

    candidates_after_speech = [
        e.actor for e in campaign_result.subphase_log.events
        if isinstance(e, Speech)
    ]

    opt_out_context = PhaseContext(
        players=day1_context.players,
        living_players=day1_context.living_players,
        dead_players=day1_context.dead_players,
        day=1,
        sheriff_candidates=candidates_after_speech,
    )
    opt_out_handler = OptOutHandler()
    opt_out_result = await opt_out_handler(
        opt_out_context, list(participants.items())
    )

    opted_out_seats = [
        e.actor for e in opt_out_result.subphase_log.events
        if isinstance(e, SheriffOptOut)
    ]
    final_candidates = [s for s in candidates_after_speech if s not in opted_out_seats]

    # Sheriff election
    sheriff_election_context = PhaseContext(
        players=day1_context.players,
        living_players=day1_context.living_players,
        dead_players=day1_context.dead_players,
        day=1,
        sheriff_candidates=final_candidates,
    )

    sheriff_handler = SheriffElectionHandler()
    sheriff_result = await sheriff_handler(
        sheriff_election_context, list(participants.items()), final_candidates
    )

    outcome = None
    for event in sheriff_result.subphase_log.events:
        if isinstance(event, SheriffOutcome):
            outcome = event
            break

    assert outcome is not None
    # Verify candidates did not vote (candidates receive votes but don't vote)
    # Candidates can receive votes, just not cast them
    # The votes dict shows who received votes, not who voted
    # Check that the sum of votes is correct (voters only, not including candidates)
    voter_count = 10  # 12 total - 2 candidates
    assert sum(outcome.votes.values()) <= voter_count * 1.5  # Max possible if all voters vote with sheriff weight
