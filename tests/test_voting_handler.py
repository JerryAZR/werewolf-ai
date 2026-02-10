"""Tests for Voting handler.

Tests cover:
1. Tie → no banishment
2. Sheriff vote counts 1.5
3. Abstention allowed
4. Dead player cannot vote
5. Banished player has max votes
6. No votes → no banishment
"""

import pytest
from typing import Any, Optional
from collections import defaultdict
from pydantic import BaseModel

from src.werewolf.events.game_events import (
    Vote,
    Banishment,
    Phase,
    SubPhase,
)
from src.werewolf.events.event_log import (
    SubPhaseLog,
)
from src.werewolf.handlers.voting_handler import (
    VotingHandler,
    SHERIFF_VOTE_WEIGHT,
    DEFAULT_VOTE_WEIGHT,
)
from src.werewolf.handlers.werewolf_handler import PhaseContext
from src.werewolf.models import (
    Player,
    Role,
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
        self._response = response
        self._response_iter = response_iter
        self._call_count = 0

    async def decide(
        self,
        system_prompt: str,
        user_prompt: str,
        **extra: Any
    ) -> str:
        self._call_count += 1
        if self._response_iter and self._call_count <= len(self._response_iter):
            return self._response_iter[self._call_count - 1]
        if self._response is not None:
            return self._response
        # Default to abstention if no response configured
        return "abstain"


# ============================================================================
# Fixtures
# ============================================================================


def make_context(players: dict[int, Player], living: set[int], sheriff: Optional[int] = None, day: int = 1) -> PhaseContext:
    """Create a PhaseContext from players and living set."""
    all_seats = set(range(12))
    dead = all_seats - living
    return PhaseContext(players, living, dead, sheriff, day)


def make_players(*seat_role_tuples: tuple[int, Role]) -> dict[int, Player]:
    """Create players from seat/role tuples."""
    return {
        seat: Player(seat=seat, name=f"P{seat}", role=role, is_alive=True)
        for seat, role in seat_role_tuples
    }


# ============================================================================
# Tests: Tie → no banishment
# ============================================================================


class TestTieNoBanishment:
    """Tests for tie → no banishment."""

    @pytest.mark.asyncio
    async def test_three_way_tie_all_get_one_vote(self):
        """Test that a 3-way tie results in no banishment."""
        players = make_players(
            (0, Role.WEREWOLF),
            (1, Role.ORDINARY_VILLAGER),
            (2, Role.ORDINARY_VILLAGER),
            (3, Role.ORDINARY_VILLAGER),
        )
        living = {0, 1, 2, 3}
        context = make_context(players, living, day=2)

        participants = {
            0: MockParticipant("1"),  # W1 votes for 1
            1: MockParticipant("2"),  # V1 votes for 2
            2: MockParticipant("0"),  # V2 votes for 0
            3: MockParticipant("0"),  # V3 votes for 0
        }
        # 0 gets 2 votes, 1 gets 1, 2 gets 1 - 0 wins

        handler = VotingHandler()
        result = await handler(context, list(participants.items()))

        banishment = next(e for e in result.subphase_log.events if isinstance(e, Banishment))
        assert banishment.banished == 0
        assert banishment.votes[0] == 2.0

    @pytest.mark.asyncio
    async def test_tie_vote_counts_correct(self):
        """Test that tied players have equal vote counts."""
        players = make_players(
            (0, Role.WEREWOLF),
            (1, Role.ORDINARY_VILLAGER),
            (2, Role.ORDINARY_VILLAGER),
            (3, Role.ORDINARY_VILLAGER),
        )
        living = {0, 1, 2, 3}
        context = make_context(players, living, day=2)

        # Everyone votes for a different person - each gets 1 vote
        participants = {
            0: MockParticipant("1"),
            1: MockParticipant("0"),
            2: MockParticipant("3"),
            3: MockParticipant("2"),
        }
        # All tied with 1 vote each

        handler = VotingHandler()
        result = await handler(context, list(participants.items()))

        banishment = next(e for e in result.subphase_log.events if isinstance(e, Banishment))
        assert banishment.banished is None  # No banishment due to tie
        assert len(banishment.tied_players) == 4  # All tied

    @pytest.mark.asyncio
    async def test_two_way_tie_no_banishment(self):
        """Test that a 2-way tie results in no banishment."""
        players = make_players(
            (0, Role.WEREWOLF),
            (1, Role.ORDINARY_VILLAGER),
            (2, Role.ORDINARY_VILLAGER),
            (3, Role.ORDINARY_VILLAGER),
        )
        living = {0, 1, 2, 3}
        context = make_context(players, living, day=1)

        # Split votes: 0 and 1 each get 2 votes
        participants = {
            0: MockParticipant("1"),
            1: MockParticipant("0"),
            2: MockParticipant("0"),
            3: MockParticipant("1"),
        }
        # 0 gets 2, 1 gets 2 - tie

        handler = VotingHandler()
        result = await handler(context, list(participants.items()))

        banishment = next(e for e in result.subphase_log.events if isinstance(e, Banishment))
        assert banishment.banished is None  # No banishment due to tie
        assert len(banishment.tied_players) == 2


# ============================================================================
# Tests: Sheriff vote counts 1.5
# ============================================================================


class TestSheriffVoteWeight:
    """Tests for sheriff vote counts 1.5."""

    @pytest.mark.asyncio
    async def test_sheriff_vote_counts_one_point_five(self):
        """Test that sheriff's vote counts as 1.5."""
        players = make_players(
            (0, Role.WEREWOLF),
            (1, Role.ORDINARY_VILLAGER),
            (2, Role.ORDINARY_VILLAGER),
        )
        living = {0, 1, 2}
        sheriff = 1
        context = make_context(players, living, sheriff, day=1)

        participants = {
            0: MockParticipant("2"),  # Werewolf votes for 2
            1: MockParticipant("0"),  # Sheriff votes for 0 (1.5 weight)
            2: MockParticipant("0"),  # V1 votes for 0
        }
        # Vote tally: 0 gets 1 + 1.5 = 2.5, 2 gets 1
        # 0 should be banished

        handler = VotingHandler()
        result = await handler(context, list(participants.items()))

        banishment = next(e for e in result.subphase_log.events if isinstance(e, Banishment))
        assert banishment.banished == 0
        assert banishment.votes[0] == 2.5  # Sheriff's 1.5 + regular 1

    @pytest.mark.asyncio
    async def test_sheriff_wins_vote_by_weight(self):
        """Test that sheriff's weighted vote can determine outcome."""
        players = make_players(
            (0, Role.WEREWOLF),
            (1, Role.ORDINARY_VILLAGER),
            (2, Role.ORDINARY_VILLAGER),
            (3, Role.ORDINARY_VILLAGER),
        )
        living = {0, 1, 2, 3}
        sheriff = 1
        context = make_context(players, living, sheriff, day=1)

        participants = {
            0: MockParticipant("2"),  # W1 votes for 2
            1: MockParticipant("3"),  # Sheriff votes for 3 (1.5 weight)
            2: MockParticipant("3"),  # V1 votes for 3
            3: MockParticipant("2"),  # V2 votes for 2
        }
        # Without sheriff: 2 gets 2, 3 gets 2 (tie)
        # With sheriff: 3 gets 1.5 + 1 = 2.5, 2 gets 1 + 1 = 2
        # 3 should win

        handler = VotingHandler()
        result = await handler(context, list(participants.items()))

        banishment = next(e for e in result.subphase_log.events if isinstance(e, Banishment))
        assert banishment.banished == 3

    @pytest.mark.asyncio
    async def test_sheriff_vote_breaks_tie(self):
        """Test that sheriff's weighted vote breaks ties."""
        players = make_players(
            (0, Role.WEREWOLF),
            (1, Role.SEER),
            (2, Role.ORDINARY_VILLAGER),
        )
        living = {0, 1, 2}
        sheriff = 2  # Player 2 is sheriff
        context = make_context(players, living, sheriff, day=1)

        # Without sheriff weight: 0 gets 1, 1 gets 1, 2 gets 1 (3-way tie)
        # Sheriff voting for 0: 0 gets 1 + 1.5 = 2.5
        participants = {
            0: MockParticipant("1"),
            1: MockParticipant("0"),
            2: MockParticipant("0"),  # Sheriff breaks tie by voting for 0
        }

        handler = VotingHandler()
        result = await handler(context, list(participants.items()))

        banishment = next(e for e in result.subphase_log.events if isinstance(e, Banishment))
        assert banishment.banished == 0
        assert banishment.votes[0] == 2.5


# ============================================================================
# Tests: Abstention allowed
# ============================================================================


class TestAbstentionAllowed:
    """Tests for abstention allowed."""

    @pytest.mark.asyncio
    async def test_single_abstention(self):
        """Test that a player can abstain from voting."""
        players = make_players(
            (0, Role.WEREWOLF),
            (1, Role.ORDINARY_VILLAGER),
            (2, Role.ORDINARY_VILLAGER),
            (3, Role.ORDINARY_VILLAGER),
        )
        living = {0, 1, 2, 3}
        context = make_context(players, living, day=1)

        participants = {
            0: MockParticipant("1"),
            1: MockParticipant("abstain"),  # Abstains
            2: MockParticipant("3"),
            3: MockParticipant("3"),
        }
        # Vote tally: 1 gets 1, 3 gets 2
        # 3 should be banished

        handler = VotingHandler()
        result = await handler(context, list(participants.items()))

        vote_events = [e for e in result.subphase_log.events if isinstance(e, Vote)]
        assert len(vote_events) == 4

        # Check abstention
        abstaining_votes = [e for e in vote_events if e.target is None]
        assert len(abstaining_votes) == 1
        assert abstaining_votes[0].actor == 1

        banishment = next(e for e in result.subphase_log.events if isinstance(e, Banishment))
        assert banishment.banished == 3

    @pytest.mark.asyncio
    async def test_multiple_abstentions(self):
        """Test that multiple players can abstain."""
        players = make_players(
            (0, Role.WEREWOLF),
            (1, Role.ORDINARY_VILLAGER),
            (2, Role.ORDINARY_VILLAGER),
            (3, Role.ORDINARY_VILLAGER),
        )
        living = {0, 1, 2, 3}
        context = make_context(players, living, day=1)

        participants = {
            0: MockParticipant("1"),
            1: MockParticipant("none"),
            2: MockParticipant("skip"),
            3: MockParticipant(""),  # Empty = abstain
        }
        # 3 abstain, 1 gets 1 vote

        handler = VotingHandler()
        result = await handler(context, list(participants.items()))

        vote_events = [e for e in result.subphase_log.events if isinstance(e, Vote)]
        abstaining_votes = [e for e in vote_events if e.target is None]
        assert len(abstaining_votes) == 3

        banishment = next(e for e in result.subphase_log.events if isinstance(e, Banishment))
        assert banishment.banished == 1
        assert banishment.votes[1] == 1.0


# ============================================================================
# Tests: Dead player cannot vote
# ============================================================================


class TestDeadPlayerCannotVote:
    """Tests for dead player cannot vote."""

    @pytest.mark.asyncio
    async def test_dead_player_excluded_from_voting(self):
        """Test that dead players cannot vote."""
        players = make_players(
            (0, Role.WEREWOLF),
            (1, Role.ORDINARY_VILLAGER),
            (2, Role.ORDINARY_VILLAGER),
            (3, Role.ORDINARY_VILLAGER),
        )
        living = {0, 1, 3}
        context = make_context(players, living, day=1)

        participants = {
            0: MockParticipant("1"),
            1: MockParticipant("3"),
            3: MockParticipant("0"),
        }

        handler = VotingHandler()
        result = await handler(context, list(participants.items()))

        vote_events = [e for e in result.subphase_log.events if isinstance(e, Vote)]
        assert len(vote_events) == 3  # Only living players vote

        # Check dead player's seat is not in voters
        voter_seats = {e.actor for e in vote_events}
        assert 2 not in voter_seats  # Dead player

    @pytest.mark.asyncio
    async def test_only_living_players_count_for_votes(self):
        """Test that only living players' votes count."""
        players = make_players(
            (0, Role.WEREWOLF),
            (1, Role.ORDINARY_VILLAGER),
            (2, Role.ORDINARY_VILLAGER),
        )
        living = {0, 1}
        context = make_context(players, living, day=1)

        # Even if dead player's participant is included, they shouldn't vote
        participants = {
            0: MockParticipant("1"),
            1: MockParticipant("0"),
            2: MockParticipant("1"),  # Dead player - ignored
        }

        handler = VotingHandler()
        result = await handler(context, list(participants.items()))

        vote_events = [e for e in result.subphase_log.events if isinstance(e, Vote)]
        assert len(vote_events) == 2  # Only living players vote


# ============================================================================
# Tests: Banished player has max votes
# ============================================================================


class TestBanishedPlayerHasMaxVotes:
    """Tests for banished player has max votes."""

    @pytest.mark.asyncio
    async def test_banished_player_has_highest_votes(self):
        """Test that the banished player has the highest vote count."""
        players = make_players(
            (0, Role.WEREWOLF),
            (1, Role.ORDINARY_VILLAGER),
            (2, Role.ORDINARY_VILLAGER),
        )
        living = {0, 1, 2}
        context = make_context(players, living, day=1)

        # All vote for different players - tie
        participants = {
            0: MockParticipant("1"),
            1: MockParticipant("2"),
            2: MockParticipant("0"),
        }

        handler = VotingHandler()
        result = await handler(context, list(participants.items()))

        banishment = next(e for e in result.subphase_log.events if isinstance(e, Banishment))
        assert banishment.banished is None  # Tie = no banishment

    @pytest.mark.asyncio
    async def test_clear_majority_winner(self):
        """Test that a player with clear majority is banished."""
        players = make_players(
            (0, Role.WEREWOLF),
            (1, Role.ORDINARY_VILLAGER),
            (2, Role.ORDINARY_VILLAGER),
            (3, Role.ORDINARY_VILLAGER),
        )
        living = {0, 1, 2, 3}
        context = make_context(players, living, day=1)

        participants = {
            0: MockParticipant("1"),
            1: MockParticipant("0"),
            2: MockParticipant("0"),
            3: MockParticipant("0"),
        }
        # 0 gets 3 votes, 1 gets 1 vote
        # 0 should be banished

        handler = VotingHandler()
        result = await handler(context, list(participants.items()))

        banishment = next(e for e in result.subphase_log.events if isinstance(e, Banishment))
        assert banishment.banished == 0
        assert banishment.votes[0] == 3.0

    @pytest.mark.asyncio
    async def test_banished_always_has_max_votes(self):
        """Test that the banished player always has the maximum votes."""
        players = make_players(
            (0, Role.WEREWOLF),
            (1, Role.SEER),
            (2, Role.ORDINARY_VILLAGER),
            (3, Role.WITCH),
        )
        living = {0, 1, 2, 3}
        context = make_context(players, living, day=1)

        participants = {
            0: MockParticipant("1"),
            1: MockParticipant("0"),
            2: MockParticipant("3"),
            3: MockParticipant("0"),
        }
        # 0 gets 2, 1 gets 1, 3 gets 1
        # 0 wins

        handler = VotingHandler()
        result = await handler(context, list(participants.items()))

        banishment = next(e for e in result.subphase_log.events if isinstance(e, Banishment))
        assert banishment.banished == 0
        assert banishment.votes[0] == 2.0
        # Verify 0 has the max votes
        assert all(v <= banishment.votes[0] for v in banishment.votes.values())


# ============================================================================
# Tests: No votes → no banishment
# ============================================================================


class TestNoVotesNoBanishment:
    """Tests for no votes → no banishment."""

    @pytest.mark.asyncio
    async def test_all_abstain_no_banishment(self):
        """Test that all players abstaining results in no banishment."""
        players = make_players(
            (0, Role.WEREWOLF),
            (1, Role.ORDINARY_VILLAGER),
            (2, Role.ORDINARY_VILLAGER),
        )
        living = {0, 1, 2}
        context = make_context(players, living, day=1)

        participants = {
            0: MockParticipant("none"),
            1: MockParticipant("abstain"),
            2: MockParticipant("skip"),
        }

        handler = VotingHandler()
        result = await handler(context, list(participants.items()))

        banishment = next(e for e in result.subphase_log.events if isinstance(e, Banishment))
        assert banishment.banished is None
        assert banishment.votes == {}

    @pytest.mark.asyncio
    async def test_empty_vote_tally_no_banishment(self):
        """Test that empty vote tally results in no banishment."""
        players = make_players(
            (0, Role.WEREWOLF),
            (1, Role.ORDINARY_VILLAGER),
        )
        living = {0, 1}
        context = make_context(players, living, day=1)

        participants = {
            0: MockParticipant(""),
            1: MockParticipant("None"),
        }

        handler = VotingHandler()
        result = await handler(context, list(participants.items()))

        banishment = next(e for e in result.subphase_log.events if isinstance(e, Banishment))
        assert banishment.banished is None
        assert len(banishment.votes) == 0


# ============================================================================
# Edge Cases
# ============================================================================


class TestVotingEdgeCases:
    """Tests for edge cases in voting."""

    @pytest.mark.asyncio
    async def test_single_player_votes_themselves(self):
        """Test that a player can vote for themselves."""
        players = make_players(
            (0, Role.WEREWOLF),
            (1, Role.ORDINARY_VILLAGER),
        )
        living = {0, 1}
        context = make_context(players, living, day=1)

        participants = {
            0: MockParticipant("0"),  # W1 votes for themselves
            1: MockParticipant("abstain"),  # V1 abstains
        }

        handler = VotingHandler()
        result = await handler(context, list(participants.items()))

        vote_events = [e for e in result.subphase_log.events if isinstance(e, Vote)]
        self_vote = [e for e in vote_events if e.target == e.actor]
        assert len(self_vote) == 1
        assert self_vote[0].actor == 0

    @pytest.mark.asyncio
    async def test_sheriff_abstains(self):
        """Test that sheriff can abstain."""
        players = make_players(
            (0, Role.WEREWOLF),
            (1, Role.ORDINARY_VILLAGER),
        )
        living = {0, 1}
        sheriff = 1
        context = make_context(players, living, sheriff, day=1)

        participants = {
            0: MockParticipant("1"),  # Werewolf votes for 1
            1: MockParticipant("abstain"),  # Sheriff abstains
        }

        handler = VotingHandler()
        result = await handler(context, list(participants.items()))

        vote_events = [e for e in result.subphase_log.events if isinstance(e, Vote)]
        sheriff_vote = [e for e in vote_events if e.actor == sheriff][0]
        assert sheriff_vote.target is None

        banishment = next(e for e in result.subphase_log.events if isinstance(e, Banishment))
        # Player 1 (the sheriff) gets 1 vote from player 0, so they are banished
        assert banishment.banished == 1
        assert banishment.votes[1] == 1.0  # Sheriff abstained, only 1 vote against them

    @pytest.mark.asyncio
    async def test_vote_for_invalid_target_defaults_to_abstain(self):
        """Test that voting for invalid target defaults to abstain."""
        players = make_players(
            (0, Role.WEREWOLF),
            (1, Role.ORDINARY_VILLAGER),
            (2, Role.ORDINARY_VILLAGER),
        )
        living = {0, 1, 2}
        context = make_context(players, living, day=1)

        participants = {
            0: MockParticipant("99"),  # Invalid seat
            1: MockParticipant("999"),  # Invalid seat
            2: MockParticipant("0"),  # Votes for 0
        }

        handler = VotingHandler()
        result = await handler(context, list(participants.items()))

        banishment = next(e for e in result.subphase_log.events if isinstance(e, Banishment))
        assert banishment.votes[0] == 1.0  # Only valid vote
        assert banishment.banished == 0

    @pytest.mark.asyncio
    async def test_tie_with_sheriff_vote(self):
        """Test tie scenario with sheriff's weighted vote."""
        players = make_players(
            (0, Role.WEREWOLF),
            (1, Role.ORDINARY_VILLAGER),
            (2, Role.ORDINARY_VILLAGER),
        )
        living = {0, 1, 2}
        sheriff = 1
        context = make_context(players, living, sheriff, day=1)

        participants = {
            0: MockParticipant("2"),  # Votes for 2
            1: MockParticipant("0"),  # Sheriff votes for 0 (1.5)
            2: MockParticipant("0"),  # Votes for 0
        }
        # Without sheriff: 0 gets 1, 2 gets 1 (tie)
        # With sheriff: 0 gets 1 + 1.5 = 2.5, 2 gets 1
        # 0 should win

        handler = VotingHandler()
        result = await handler(context, list(participants.items()))

        banishment = next(e for e in result.subphase_log.events if isinstance(e, Banishment))
        assert banishment.banished == 0
        assert banishment.votes[0] == 2.5

    @pytest.mark.asyncio
    async def test_all_vote_same_player(self):
        """Test when all players vote for the same person."""
        players = make_players(
            (0, Role.WEREWOLF),
            (1, Role.ORDINARY_VILLAGER),
            (2, Role.ORDINARY_VILLAGER),
        )
        living = {0, 1, 2}
        context = make_context(players, living, day=1)

        participants = {
            0: MockParticipant("1"),
            1: MockParticipant("1"),
            2: MockParticipant("1"),
        }
        # 1 gets 3 votes

        handler = VotingHandler()
        result = await handler(context, list(participants.items()))

        banishment = next(e for e in result.subphase_log.events if isinstance(e, Banishment))
        assert banishment.banished == 1
        assert banishment.votes[1] == 3.0

    @pytest.mark.asyncio
    async def test_vote_counts_are_float(self):
        """Test that vote counts are floats (to support sheriff weight)."""
        players = make_players(
            (0, Role.WEREWOLF),
            (1, Role.ORDINARY_VILLAGER),
        )
        living = {0, 1}
        sheriff = 0
        context = make_context(players, living, sheriff, day=1)

        participants = {
            0: MockParticipant("1"),  # Sheriff votes
            1: MockParticipant("0"),  # Regular vote
        }

        handler = VotingHandler()
        result = await handler(context, list(participants.items()))

        banishment = next(e for e in result.subphase_log.events if isinstance(e, Banishment))
        # Sheriff's vote for 1 = 1.5, regular vote for 0 = 1.0
        assert banishment.votes[1] == 1.5
        assert banishment.votes[0] == 1.0
        # Verify they are floats
        assert isinstance(banishment.votes[0], float)
        assert isinstance(banishment.votes[1], float)
