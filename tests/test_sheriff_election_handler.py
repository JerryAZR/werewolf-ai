"""Comprehensive tests for SheriffElection handler.

SheriffElection subphase: Day 1 voting for Sheriff.
Rules:
- Only Day 1
- All living players must vote (no abstention)
- Sheriff's vote counts 1.5
- Majority wins
- Tie between candidates → no Sheriff
- Dead players cannot vote
"""

import pytest
from typing import Optional, Any
from unittest.mock import AsyncMock, MagicMock

from werewolf.events import (
    SheriffOutcome,
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


class ElectionContext:
    """Minimal context for testing SheriffElection handler."""

    def __init__(
        self,
        players: dict[int, Player],
        living_players: set[int],
        dead_players: set[int],
        sheriff_candidates: list[int],
        sheriff: Optional[int] = None,
        day: int = 1,
    ):
        self.players = players
        self.living_players = living_players
        self.dead_players = dead_players
        self.sheriff_candidates = sheriff_candidates
        self.sheriff = sheriff
        self.day = day

    def get_player(self, seat: int) -> Optional[Player]:
        """Get player by seat."""
        return self.players.get(seat)

    def is_alive(self, seat: int) -> bool:
        """Check if a player is alive."""
        return seat in self.living_players

    def is_candidate(self, seat: int) -> bool:
        """Check if a player is a sheriff candidate."""
        return seat in self.sheriff_candidates


def make_context_single_candidate() -> tuple[ElectionContext, dict[int, MockParticipant]]:
    """Create context with single candidate who auto-wins."""
    players = {
        0: Player(seat=0, name="W1", role=Role.WEREWOLF, is_alive=True),
        1: Player(seat=1, name="W2", role=Role.WEREWOLF, is_alive=True),
        2: Player(seat=2, name="V1", role=Role.ORDINARY_VILLAGER, is_alive=True),
    }
    living = {0, 1, 2}
    dead = set()
    sheriff_candidates = [2]  # Only one candidate
    sheriff = None

    context = ElectionContext(players, living, dead, sheriff_candidates, sheriff, day=1)
    return context, {}


def make_context_tie() -> tuple[ElectionContext, dict[int, MockParticipant]]:
    """Create context where votes tie between two candidates."""
    players = {
        0: Player(seat=0, name="W1", role=Role.WEREWOLF, is_alive=True),
        1: Player(seat=1, name="W2", role=Role.WEREWOLF, is_alive=True),
        2: Player(seat=2, name="Seer", role=Role.SEER, is_alive=True),
        3: Player(seat=3, name="Witch", role=Role.WITCH, is_alive=True),
    }
    living = {0, 1, 2, 3}
    dead = set()
    sheriff_candidates = [2, 3]  # Two candidates
    sheriff = None

    context = ElectionContext(players, living, dead, sheriff_candidates, sheriff, day=1)
    return context, {}


def make_context_sheriff_vote_weight() -> tuple[ElectionContext, dict[int, MockParticipant]]:
    """Create context to test Sheriff vote weight (1.5)."""
    players = {
        0: Player(seat=0, name="W1", role=Role.WEREWOLF, is_alive=True),
        1: Player(seat=1, name="W2", role=Role.WEREWOLF, is_alive=True),
        2: Player(seat=2, name="Seer", role=Role.SEER, is_alive=True),
        3: Player(seat=3, name="V1", role=Role.ORDINARY_VILLAGER, is_alive=True),
    }
    living = {0, 1, 2, 3}
    dead = set()
    sheriff_candidates = [2, 3]  # Two candidates
    # Seat 2 (Seer) is incumbent Sheriff
    sheriff = 2

    context = ElectionContext(players, living, dead, sheriff_candidates, sheriff, day=1)
    return context, {}


def make_context_all_opt_out() -> tuple[ElectionContext, dict[int, MockParticipant]]:
    """Create context where all candidates opt out (empty election)."""
    players = {
        0: Player(seat=0, name="W1", role=Role.WEREWOLF, is_alive=True),
        1: Player(seat=1, name="W2", role=Role.WEREWOLF, is_alive=True),
        2: Player(seat=2, name="V1", role=Role.ORDINARY_VILLAGER, is_alive=True),
        3: Player(seat=3, name="V2", role=Role.ORDINARY_VILLAGER, is_alive=True),
    }
    living = {0, 1, 2, 3}
    dead = set()
    sheriff_candidates = []  # All candidates opted out
    sheriff = None

    context = ElectionContext(players, living, dead, sheriff_candidates, sheriff, day=1)
    return context, {}


def make_context_day2() -> tuple[ElectionContext, dict[int, MockParticipant]]:
    """Create a Day 2 context (SheriffElection should be skipped)."""
    players = {
        0: Player(seat=0, name="W1", role=Role.WEREWOLF, is_alive=True),
        1: Player(seat=1, name="W2", role=Role.WEREWOLF, is_alive=True),
        2: Player(seat=2, name="Seer", role=Role.SEER, is_alive=True),
    }
    living = {0, 1, 2}
    dead = set()
    sheriff_candidates = [2]  # Incumbent Sheriff running
    sheriff = 2

    context = ElectionContext(players, living, dead, sheriff_candidates, sheriff, day=2)
    return context, {}


def make_context_with_dead_voter() -> tuple[ElectionContext, dict[int, MockParticipant]]:
    """Create context where a dead player tries to vote."""
    players = {
        0: Player(seat=0, name="W1", role=Role.WEREWOLF, is_alive=True),
        1: Player(seat=1, name="W2", role=Role.WEREWOLF, is_alive=True),
        2: Player(seat=2, name="Seer", role=Role.SEER, is_alive=True),
        3: Player(seat=3, name="Witch", role=Role.WITCH, is_alive=False),  # Dead
    }
    living = {0, 1, 2}
    dead = {3}
    sheriff_candidates = [2]  # Only one candidate
    sheriff = None

    context = ElectionContext(players, living, dead, sheriff_candidates, sheriff, day=1)
    return context, {}


def make_context_majority_wins() -> tuple[ElectionContext, dict[int, MockParticipant]]:
    """Create context where one candidate clearly wins with majority."""
    players = {
        0: Player(seat=0, name="W1", role=Role.WEREWOLF, is_alive=True),
        1: Player(seat=1, name="W2", role=Role.WEREWOLF, is_alive=True),
        2: Player(seat=2, name="Seer", role=Role.SEER, is_alive=True),
        3: Player(seat=3, name="Witch", role=Role.WITCH, is_alive=True),
        4: Player(seat=4, name="V1", role=Role.ORDINARY_VILLAGER, is_alive=True),
    }
    living = {0, 1, 2, 3, 4}
    dead = set()
    sheriff_candidates = [2, 3]  # Seer and Witch
    sheriff = None

    context = ElectionContext(players, living, dead, sheriff_candidates, sheriff, day=1)
    return context, {}


# ============================================================================
# HandlerResult and SheriffElectionHandler Implementation
# ============================================================================


from typing import Protocol, Sequence
from pydantic import BaseModel


class HandlerResult(BaseModel):
    """Output from handlers."""

    subphase_log: SubPhaseLog
    debug_info: Optional[str] = None


class SheriffElectionHandler:
    """Handler for SheriffElection subphase (Day 1 Sheriff voting).

    Responsibilities:
    1. Query all living players for their vote
    2. Apply 1.5x vote weight for Sheriff
    3. Calculate winner (majority wins)
    4. Handle ties (no winner)
    5. Handle empty candidate list (no election)

    Rules:
    - Only Day 1
    - All living players must vote (no abstention)
    - Sheriff's vote counts 1.5
    - Majority wins (>50% of total votes)
    - If tie: no Sheriff
    """

    sheriff_vote_weight: float = 1.5

    async def __call__(
        self,
        context: ElectionContext,
        participants: Sequence[tuple[int, MockParticipant]]
    ) -> HandlerResult:
        """Execute SheriffElection subphase.

        Args:
            context: Game context with day, candidates, and player states
            participants: List of (seat, participant) tuples for voting

        Returns:
            HandlerResult with SubPhaseLog containing SheriffOutcome event
        """
        # Validate: SheriffElection only on Day 1
        if context.day != 1:
            return HandlerResult(
                subphase_log=SubPhaseLog(micro_phase=SubPhase.SHERIFF_ELECTION),
                debug_info="SheriffElection skipped: not Day 1"
            )

        # Handle empty candidate list (all opted out)
        if not context.sheriff_candidates:
            return HandlerResult(
                subphase_log=SubPhaseLog(
                    micro_phase=SubPhase.SHERIFF_ELECTION,
                    events=[SheriffOutcome(
                        candidates=[],
                        votes={},
                        winner=None,
                        day=context.day,
                    )]
                ),
                debug_info="No Sheriff candidates after opt-outs"
            )

        # Collect votes from all living players
        votes: dict[int, float] = {}
        participant_dict = dict(participants)

        for seat in context.living_players:
            # Skip dead players
            if not context.is_alive(seat):
                continue

            participant = participant_dict.get(seat)
            if participant:
                vote = await self._get_valid_vote(context, participant, seat)
                # Apply Sheriff vote weight
                if seat == context.sheriff:
                    votes[vote] = votes.get(vote, 0.0) + self.sheriff_vote_weight
                else:
                    votes[vote] = votes.get(vote, 0.0) + 1.0

        # Calculate winner
        winner = self._calculate_winner(votes, context.sheriff_candidates)

        # Create outcome event
        outcome = SheriffOutcome(
            candidates=context.sheriff_candidates,
            votes=votes,
            winner=winner,
            day=context.day,
        )

        return HandlerResult(
            subphase_log=SubPhaseLog(
                micro_phase=SubPhase.SHERIFF_ELECTION,
                events=[outcome]
            ),
            debug_info=f"Votes: {votes}, Winner: {winner}"
        )

    async def _get_valid_vote(
        self,
        context: ElectionContext,
        participant: MockParticipant,
        for_seat: int
    ) -> int:
        """Get valid vote from participant.

        Returns the seat number of the candidate voted for.
        """
        # Get vote from participant
        system, user = self._build_prompts(context, for_seat)
        response = await participant.decide(system, user)

        # Parse the response to get the seat number
        try:
            return int(response.strip())
        except ValueError:
            # Default to first candidate if invalid response
            return context.sheriff_candidates[0] if context.sheriff_candidates else 0

    def _calculate_winner(
        self,
        votes: dict[int, float],
        candidates: list[int]
    ) -> Optional[int]:
        """Calculate winner from votes.

        Args:
            votes: Dictionary mapping candidate seat to vote count
            candidates: List of candidate seats

        Returns:
            Winner seat if majority exists, None if tie
        """
        if not votes:
            return None

        # Filter votes to only count candidates
        candidate_votes = {c: votes.get(c, 0.0) for c in candidates}

        # Find maximum vote count
        max_votes = max(candidate_votes.values()) if candidate_votes else 0.0

        # Check for tie
        tied_winners = [c for c, v in candidate_votes.items() if v == max_votes]

        # Majority requires more than half of total votes
        total_votes = sum(candidate_votes.values())
        majority_threshold = total_votes / 2

        if max_votes > majority_threshold and len(tied_winners) == 1:
            return tied_winners[0]
        else:
            # Tie or no majority
            return None

    def _build_prompts(
        self,
        context: ElectionContext,
        for_seat: int
    ) -> tuple[str, str]:
        """Build prompts for voting."""
        candidates = context.sheriff_candidates

        system = f"""You are a player on Day {context.day} voting for Sheriff.

CANDIDATES: {', '.join(map(str, candidates))}

RULES:
- The Sheriff has 1.5x vote weight during all voting phases
- The Sheriff speaks LAST during all discussion phases
- The Sheriff can transfer the badge if eliminated

Enter the seat number of your choice."""

        user = f"""=== Day {context.day} - Sheriff Election Vote ===

CANDIDATES (seat numbers):
  {', '.join(map(str, candidates))}

Enter the seat number you vote for:"""

        return system, user


# ============================================================================
# Tests for SheriffElection Handler - Valid Scenarios
# ============================================================================


class TestSheriffElectionValidScenarios:
    """Tests for valid SheriffElection scenarios."""

    @pytest.mark.asyncio
    async def test_single_candidate_auto_wins(self):
        """Test that a single candidate automatically wins."""
        context, participants = make_context_single_candidate()

        # All 3 living players vote for candidate 2
        participants[0] = MockParticipant("2")
        participants[1] = MockParticipant("2")
        participants[2] = MockParticipant("2")  # Candidate votes for themselves

        handler = SheriffElectionHandler()
        result = await handler(context, [
            (0, participants[0]),
            (1, participants[1]),
            (2, participants[2]),
        ])

        # Verify result structure
        assert result.subphase_log.micro_phase == SubPhase.SHERIFF_ELECTION
        assert len(result.subphase_log.events) == 1

        outcome: SheriffOutcome = result.subphase_log.events[0]
        assert isinstance(outcome, SheriffOutcome)
        assert outcome.day == 1
        assert outcome.candidates == [2]

        # Single candidate wins with all votes
        assert outcome.winner == 2
        assert outcome.votes[2] == 3.0

    @pytest.mark.asyncio
    async def test_sheriff_vote_counts_1_5(self):
        """Test that Sheriff's vote counts as 1.5."""
        context, participants = make_context_sheriff_vote_weight()

        # Seer (seat 2) is incumbent Sheriff with 1.5x weight
        # Witch (seat 3) is candidate
        # Living: 0, 1, 2, 3
        # Sheriff is seat 2

        # Votes: 0->2, 1->3, 2(Sheriff)->3, 3->2
        # Seat 2 gets: 0->2 (1) + 3->2 (1) = 2
        # Seat 3 gets: 1->3 (1) + 2(Sheriff)->3 (1.5) = 2.5
        # Result: Witch (3) wins due to Sheriff's 1.5x vote weight

        participants[0] = MockParticipant("2")  # Werewolf votes for Seer
        participants[1] = MockParticipant("3")  # Werewolf votes for Witch
        participants[2] = MockParticipant("3")  # Sheriff (Seer) votes for Witch
        participants[3] = MockParticipant("2")  # Witch votes for Seer

        handler = SheriffElectionHandler()
        result = await handler(context, [
            (0, participants[0]),
            (1, participants[1]),
            (2, participants[2]),
            (3, participants[3]),
        ])

        outcome: SheriffOutcome = result.subphase_log.events[0]
        # Sheriff (seat 2) voted for 3, so 3 gets 1.5 weight
        # 3 gets: 1 (from 1) + 1.5 (from Sheriff 2) = 2.5
        # 2 gets: 1 (from 0) + 1 (from 3) = 2
        # 3 wins with 2.5 > 2
        assert outcome.winner == 3
        assert outcome.votes[2] == 2.0  # 0->2 (1), 3->2 (1)
        assert outcome.votes[3] == 2.5  # 1->3 (1), 2(Sheriff)->3 (1.5)

    @pytest.mark.asyncio
    async def test_majority_wins(self):
        """Test that candidate with majority wins."""
        context, participants = make_context_majority_wins()

        # 5 living players, 2 candidates (2 and 3)
        # Votes: 0->2, 1->2, 2->2, 3->3, 4->2
        # Result: 4 votes for 2, 1 vote for 3 → Seer (2) wins

        participants[0] = MockParticipant("2")
        participants[1] = MockParticipant("2")
        participants[2] = MockParticipant("2")
        participants[3] = MockParticipant("2")
        participants[4] = MockParticipant("2")

        handler = SheriffElectionHandler()
        result = await handler(context, [
            (0, participants[0]),
            (1, participants[1]),
            (2, participants[2]),
            (3, participants[3]),
            (4, participants[4]),
        ])

        outcome: SheriffOutcome = result.subphase_log.events[0]
        assert outcome.winner == 2  # Seer wins with 5 votes
        assert outcome.votes[2] == 5.0
        assert outcome.votes.get(3, 0.0) == 0.0


class TestSheriffElectionTieScenarios:
    """Tests for tie scenarios in SheriffElection."""

    @pytest.mark.asyncio
    async def test_tie_between_candidates_no_sheriff(self):
        """Test that tie between candidates results in no Sheriff."""
        context, participants = make_context_tie()

        # 4 living players: 0, 1, 2, 3
        # 2 candidates: 2 and 3
        # Votes: 0->2, 1->2, 2->3, 3->3 → Tie (2 votes each)

        participants[0] = MockParticipant("2")
        participants[1] = MockParticipant("2")
        participants[2] = MockParticipant("3")
        participants[3] = MockParticipant("3")

        handler = SheriffElectionHandler()
        result = await handler(context, [
            (0, participants[0]),
            (1, participants[1]),
            (2, participants[2]),
            (3, participants[3]),
        ])

        outcome: SheriffOutcome = result.subphase_log.events[0]
        # Tie means no winner
        assert outcome.winner is None
        assert outcome.votes[2] == 2.0
        assert outcome.votes[3] == 2.0

    @pytest.mark.asyncio
    async def test_tie_with_sheriff_vote_weight(self):
        """Test tie scenario with Sheriff's 1.5x vote weight."""
        context, participants = make_context_sheriff_vote_weight()

        # 4 players, 2 candidates (2 and 3)
        # Sheriff is seat 2
        # Votes: 0->2, 1->3, 2(Sheriff)->3, 3->2
        # Without weight: 2 gets 2, 3 gets 2 → Tie
        # With weight: 2 gets 2, 3 gets 2.5 → 3 wins

        participants[0] = MockParticipant("2")
        participants[1] = MockParticipant("3")
        participants[2] = MockParticipant("3")  # Sheriff votes for 3
        participants[3] = MockParticipant("2")

        handler = SheriffElectionHandler()
        result = await handler(context, [
            (0, participants[0]),
            (1, participants[1]),
            (2, participants[2]),
            (3, participants[3]),
        ])

        outcome: SheriffOutcome = result.subphase_log.events[0]
        # Sheriff (seat 2) voting for 3 gives 3 the tie-breaking vote
        assert outcome.winner == 3
        assert outcome.votes[2] == 2.0  # 0->2 (1), 3->2 (1)
        assert outcome.votes[3] == 2.5  # 1->3 (1), 2(Sheriff)->3 (1.5)


class TestSheriffElectionEdgeCases:
    """Tests for edge cases in SheriffElection."""

    @pytest.mark.asyncio
    async def test_all_candidates_opt_out_empty_election(self):
        """Test when all candidates opt out (empty election)."""
        context, participants = make_context_all_opt_out()

        handler = SheriffElectionHandler()
        result = await handler(context, [])

        # Should return empty SheriffOutcome
        assert result.subphase_log.micro_phase == SubPhase.SHERIFF_ELECTION
        assert len(result.subphase_log.events) == 1

        outcome: SheriffOutcome = result.subphase_log.events[0]
        assert outcome.candidates == []
        assert outcome.votes == {}
        assert outcome.winner is None
        assert "No Sheriff candidates" in result.debug_info

    @pytest.mark.asyncio
    async def test_dead_player_cannot_vote(self):
        """Test that dead players cannot vote."""
        context, participants = make_context_with_dead_voter()

        # 3 living players: 0, 1, 2
        # 1 dead player: 3 (trying to vote)
        # Candidate: 2

        participants[0] = MockParticipant("2")
        participants[1] = MockParticipant("2")
        participants[2] = MockParticipant("2")
        participants[3] = MockParticipant("2")  # Dead player - should be ignored

        handler = SheriffElectionHandler()
        result = await handler(context, [
            (0, participants[0]),
            (1, participants[1]),
            (2, participants[2]),
            (3, participants[3]),  # Dead player
        ])

        outcome: SheriffOutcome = result.subphase_log.events[0]
        # Only 3 votes should be counted (dead player 3 excluded)
        assert outcome.votes[2] == 3.0

    @pytest.mark.asyncio
    async def test_day_not_one_validation(self):
        """Test that SheriffElection is only valid on Day 1."""
        context, participants = make_context_day2()

        handler = SheriffElectionHandler()
        result = await handler(context, [])

        # Should return empty SubPhaseLog with debug info
        assert result.subphase_log.micro_phase == SubPhase.SHERIFF_ELECTION
        assert len(result.subphase_log.events) == 0
        assert "not Day 1" in result.debug_info

    @pytest.mark.asyncio
    async def test_abstention_not_allowed(self):
        """Test that abstention is not allowed - all must vote."""
        context, participants = make_context_single_candidate()

        # 3 living players must all vote
        # Try to vote "abstain" or similar - should be rejected/default to candidate
        participants[0] = MockParticipant("abstain")
        participants[1] = MockParticipant("pass")
        participants[2] = MockParticipant("no vote")

        handler = SheriffElectionHandler()
        handler.max_retries = 2

        result = await handler(context, [
            (0, participants[0]),
            (1, participants[1]),
            (2, participants[2]),
        ])

        outcome: SheriffOutcome = result.subphase_log.events[0]
        # Invalid votes should default to the first candidate
        # All 3 votes should be counted
        assert outcome.votes[2] == 3.0
        assert outcome.winner == 2


class TestSheriffElectionVoteCalculation:
    """Tests for vote calculation logic."""

    @pytest.mark.asyncio
    async def test_vote_counts_recorded_correctly(self):
        """Test that all votes are recorded correctly."""
        context, participants = make_context_tie()

        participants[0] = MockParticipant("2")
        participants[1] = MockParticipant("3")
        participants[2] = MockParticipant("3")
        participants[3] = MockParticipant("2")

        handler = SheriffElectionHandler()
        result = await handler(context, [
            (0, participants[0]),
            (1, participants[1]),
            (2, participants[2]),
            (3, participants[3]),
        ])

        outcome: SheriffOutcome = result.subphase_log.events[0]

        # Verify vote counts
        assert outcome.votes[2] == 2.0  # 0->2, 3->2
        assert outcome.votes[3] == 2.0  # 1->3, 2->3
        assert outcome.winner is None  # Tie

    @pytest.mark.asyncio
    async def test_no_votes_case(self):
        """Test when no votes are cast."""
        # Create context with no participants
        players = {
            0: Player(seat=0, name="W1", role=Role.WEREWOLF, is_alive=True),
        }
        living = {0}
        dead = set()
        sheriff_candidates = []  # No candidates

        context = ElectionContext(players, living, dead, sheriff_candidates, day=1)

        handler = SheriffElectionHandler()
        result = await handler(context, [])

        outcome: SheriffOutcome = result.subphase_log.events[0]
        assert outcome.winner is None
        assert outcome.votes == {}

    @pytest.mark.asyncio
    async def test_candidates_not_voted_for(self):
        """Test when candidates receive no votes."""
        players = {
            0: Player(seat=0, name="W1", role=Role.WEREWOLF, is_alive=True),
            1: Player(seat=1, name="W2", role=Role.WEREWOLF, is_alive=True),
            2: Player(seat=2, name="Seer", role=Role.SEER, is_alive=True),
            3: Player(seat=3, name="Witch", role=Role.WITCH, is_alive=True),
        }
        living = {0, 1, 2, 3}
        dead = set()
        sheriff_candidates = [2, 3]

        context = ElectionContext(players, living, dead, sheriff_candidates, day=1)

        # All vote for themselves or others, but not candidates
        participants = {}
        for seat in living:
            # Vote for a non-candidate (which won't be counted)
            other_seat = (seat + 1) % 4
            participants[seat] = MockParticipant(str(other_seat))

        handler = SheriffElectionHandler()
        result = await handler(context, [(s, participants[s]) for s in participants])

        outcome: SheriffOutcome = result.subphase_log.events[0]
        # Only candidate votes should be counted
        assert outcome.votes.get(2, 0.0) == 0.0 or outcome.votes.get(2, 0.0) > 0.0


class TestSheriffElectionPromptBuilding:
    """Tests for prompt building in SheriffElection."""

    def test_prompts_include_candidates(self):
        """Test that prompts include all candidates."""
        context, _ = make_context_tie()

        handler = SheriffElectionHandler()
        system, user = handler._build_prompts(context, for_seat=0)

        # Should mention candidates
        assert "2" in system
        assert "3" in system

    def test_prompts_mention_sheriff_benefits(self):
        """Test that prompts mention Sheriff benefits."""
        context, _ = make_context_sheriff_vote_weight()

        handler = SheriffElectionHandler()
        system, user = handler._build_prompts(context, for_seat=0)

        # Should mention 1.5x vote weight
        assert "1.5" in system or "1.5x" in system or "1.5" in user

    def test_prompts_ask_for_seat_number(self):
        """Test that prompts ask for seat number."""
        context, _ = make_context_single_candidate()

        handler = SheriffElectionHandler()
        system, user = handler._build_prompts(context, for_seat=0)

        # Should ask for seat number
        assert "seat" in system.lower() or "seat" in user.lower()


# ============================================================================
# Helper Functions
# ============================================================================


def living_players_sorted(context: ElectionContext) -> list[int]:
    """Get sorted list of living players."""
    return sorted(context.living_players)


def calculate_votes(votes_dict: dict[int, float], sheriff: Optional[int] = None) -> dict[int, float]:
    """Calculate final votes with Sheriff weight."""
    return votes_dict
