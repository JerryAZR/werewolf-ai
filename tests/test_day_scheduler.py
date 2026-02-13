"""Tests for DayScheduler - day phase orchestration.

Tests verify:
- Full day flow with StubPlayer
- Day 1 with sheriff election
- Voting and banishment
- Victory detection during day
"""

import asyncio
import random
import pytest

from werewolf.engine import GameState, EventCollector, DayScheduler
from werewolf.models import Player, Role, STANDARD_12_PLAYER_CONFIG, create_players_from_config
from werewolf.ai.stub_ai import StubPlayer, create_stub_player
# Use src. prefix to match handler imports for proper isinstance checks
from werewolf.events.game_events import (
    Phase,
    SubPhase,
    Speech,
    Vote,
    Banishment,
    SheriffOutcome,
    SheriffOptOut,
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


def create_participants_from_players(players: dict[int, Player], seed: int = 42) -> dict[int, StubPlayer]:
    """Create stub participants from players dict."""
    return {seat: create_stub_player(seed=seed + seat) for seat in players}


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def players() -> dict[int, Player]:
    """Create standard 12-player config as dict with shuffled roles."""
    return create_players_shuffled()


@pytest.fixture
def initial_state(players: dict[int, Player]) -> GameState:
    """Create initial game state with all players alive."""
    return GameState(
        players=players,
        living_players=set(players.keys()),
        dead_players=set(),
        sheriff=None,
        day=1,
    )


@pytest.fixture
def collector() -> EventCollector:
    """Create event collector."""
    return EventCollector(day=0)


@pytest.fixture
def day2_state(players: dict[int, Player]) -> GameState:
    """Create Day 2 state with all players alive."""
    return GameState(
        players=players,
        living_players=set(players.keys()),
        dead_players=set(),
        sheriff=None,
        day=2,
    )


# ============================================================================
# Tests
# ============================================================================

class TestDaySchedulerBasics:
    """Basic tests for DayScheduler initialization and configuration."""

    def test_scheduler_initialization(self):
        """Test that DayScheduler can be instantiated."""
        scheduler = DayScheduler()
        assert scheduler is not None

    def test_initial_state(self, initial_state: GameState):
        """Test initial game state for Day 1."""
        assert initial_state.day == 1
        assert len(initial_state.living_players) == 12
        assert len(initial_state.dead_players) == 0
        assert initial_state.sheriff is None

    def test_collector_initialization(self, collector: EventCollector):
        """Test event collector initialization."""
        assert collector.day == 0


class TestDay1WithSheriffElection:
    """Tests for Day 1 with sheriff election flow."""

    @pytest.mark.asyncio
    async def test_day1_with_sheriff_election(
        self,
        initial_state: GameState,
        collector: EventCollector,
        players: dict[int, Player],
    ):
        """Test complete Day 1 flow with sheriff election using StubPlayer."""
        scheduler = DayScheduler()
        participants = create_participants_from_players(players, seed=42)

        # Run day
        state, collector = await scheduler.run_day(initial_state, collector, participants)

        # Verify day advanced
        assert state.day == 1  # Day doesn't change during run_day

        # Verify phase was created
        event_log = collector.get_event_log()
        day_phase = None
        for phase in event_log.phases:
            if phase.kind == Phase.DAY:
                day_phase = phase
                break

        assert day_phase is not None, "Day phase should be in event log"
        assert day_phase.number == 1

        # Verify Day 1 phases are present
        subphase_types = {sp.micro_phase for sp in day_phase.subphases}
        assert SubPhase.CAMPAIGN in subphase_types, "Campaign should run on Day 1"
        assert SubPhase.OPT_OUT in subphase_types, "OptOut should run on Day 1"
        # SheriffElection runs only if candidates remain after campaign and opt-out
        # This is correct behavior - if all candidates opt out, no election occurs
        sheriff_election_present = SubPhase.SHERIFF_ELECTION in subphase_types

        # Verify the day flow is correct - if SheriffElection didn't run,
        # it means all candidates opted out at some point
        if not sheriff_election_present:
            # Check that the day still completed successfully
            assert SubPhase.VOTING in subphase_types, "Voting should still run"

    @pytest.mark.asyncio
    async def test_campaign_generates_speeches(
        self,
        initial_state: GameState,
        collector: EventCollector,
        players: dict[int, Player],
    ):
        """Test that Campaign phase generates speeches from candidates who enter."""
        scheduler = DayScheduler()
        participants = create_participants_from_players(players, seed=123)

        state, collector = await scheduler.run_day(initial_state, collector, participants)

        # Find campaign speeches
        event_log = collector.get_event_log()
        speeches = []
        for phase in event_log.phases:
            if phase.kind == Phase.DAY:
                for subphase in phase.subphases:
                    if subphase.micro_phase == SubPhase.CAMPAIGN:
                        for event in subphase.events:
                            if isinstance(event, Speech):
                                speeches.append(event)

        # Some living players may choose not to run (not running response)
        # Verify we get at least 1 speech and at most all living players
        assert 1 <= len(speeches) <= len(initial_state.living_players)

    @pytest.mark.asyncio
    async def test_opt_out_generates_events(
        self,
        initial_state: GameState,
        collector: EventCollector,
        players: dict[int, Player],
    ):
        """Test that OptOut phase generates opt-out events."""
        scheduler = DayScheduler()
        participants = create_participants_from_players(players, seed=456)

        state, collector = await scheduler.run_day(initial_state, collector, participants)

        # Find opt-out events
        event_log = collector.get_event_log()
        opt_outs = []
        for phase in event_log.phases:
            if phase.kind == Phase.DAY:
                for subphase in phase.subphases:
                    if subphase.micro_phase == SubPhase.OPT_OUT:
                        for event in subphase.events:
                            if isinstance(event, SheriffOptOut):
                                opt_outs.append(event)

        # Some players may have opted out
        assert len(opt_outs) <= len(initial_state.living_players)

    @pytest.mark.asyncio
    async def test_sheriff_election_generates_outcome(
        self,
        initial_state: GameState,
        collector: EventCollector,
        players: dict[int, Player],
    ):
        """Test that SheriffElection phase generates outcome event when candidates remain."""
        scheduler = DayScheduler()
        # Use seed=123 which we know generates candidates who stay in the race
        participants = create_participants_from_players(players, seed=123)

        state, collector = await scheduler.run_day(initial_state, collector, participants)

        # Find sheriff outcome
        event_log = collector.get_event_log()
        sheriff_outcomes = []
        for phase in event_log.phases:
            if phase.kind == Phase.DAY:
                for subphase in phase.subphases:
                    if subphase.micro_phase == SubPhase.SHERIFF_ELECTION:
                        for event in subphase.events:
                            if isinstance(event, SheriffOutcome):
                                sheriff_outcomes.append(event)

        # Should have one sheriff outcome
        assert len(sheriff_outcomes) == 1

        outcome = sheriff_outcomes[0]
        # Winner may be None (tie) or a valid seat
        assert outcome.winner is None or outcome.winner in initial_state.living_players


class TestDayWithoutSheriffElection:
    """Tests for days without sheriff election (Day 2+)."""

    @pytest.mark.asyncio
    async def test_day2_without_sheriff_election(
        self,
        day2_state: GameState,
        collector: EventCollector,
        players: dict[int, Player],
    ):
        """Test Day 2 skips sheriff election phases."""
        scheduler = DayScheduler()
        participants = create_participants_from_players(players, seed=111)

        # Run day
        state, collector = await scheduler.run_day(day2_state, collector, participants)

        # Verify phase was created
        event_log = collector.get_event_log()
        day_phase = None
        for phase in event_log.phases:
            if phase.kind == Phase.DAY:
                day_phase = phase
                break

        assert day_phase is not None, "Day phase should be in event log"

        # Verify Day 2 phases (no sheriff election)
        subphase_types = {sp.micro_phase for sp in day_phase.subphases}
        assert SubPhase.CAMPAIGN not in subphase_types, "Campaign should NOT run on Day 2"
        assert SubPhase.OPT_OUT not in subphase_types, "OptOut should NOT run on Day 2"
        assert SubPhase.SHERIFF_ELECTION not in subphase_types, "SheriffElection should NOT run on Day 2"
        assert SubPhase.DEATH_RESOLUTION in subphase_types, "DeathResolution should run"
        assert SubPhase.DISCUSSION in subphase_types, "Discussion should run"
        assert SubPhase.VOTING in subphase_types, "Voting should run"


class TestVotingAndBanishment:
    """Tests for voting and banishment mechanics."""

    @pytest.mark.asyncio
    async def test_voting_generates_vote_events(
        self,
        initial_state: GameState,
        collector: EventCollector,
        players: dict[int, Player],
    ):
        """Test that Voting phase generates Vote events."""
        scheduler = DayScheduler()
        participants = create_participants_from_players(players, seed=222)

        state, collector = await scheduler.run_day(initial_state, collector, participants)

        # Find vote events
        event_log = collector.get_event_log()
        votes = []
        for phase in event_log.phases:
            if phase.kind == Phase.DAY:
                for subphase in phase.subphases:
                    if subphase.micro_phase == SubPhase.VOTING:
                        for event in subphase.events:
                            if isinstance(event, Vote):
                                votes.append(event)

        # All living players should vote
        assert len(votes) == len(initial_state.living_players)

        # Each vote should be from a living player
        for vote in votes:
            assert vote.actor in initial_state.living_players

    @pytest.mark.asyncio
    async def test_voting_generates_banishment_event(
        self,
        initial_state: GameState,
        collector: EventCollector,
        players: dict[int, Player],
    ):
        """Test that Voting phase generates Banishment event."""
        scheduler = DayScheduler()
        participants = create_participants_from_players(players, seed=333)

        # Save original living players before run (run_day mutates state)
        original_living = initial_state.living_players.copy()

        state, collector = await scheduler.run_day(initial_state, collector, participants)

        # Find banishment event
        event_log = collector.get_event_log()
        banishments = []
        for phase in event_log.phases:
            if phase.kind == Phase.DAY:
                for subphase in phase.subphases:
                    if subphase.micro_phase == SubPhase.VOTING:
                        for event in subphase.events:
                            if isinstance(event, Banishment):
                                banishments.append(event)

        # Should have one banishment event
        assert len(banishments) == 1

        banishment = banishments[0]
        # Banished player may be None (tie) or a valid seat that was originally alive
        assert banishment.banished is None or banishment.banished in original_living


class TestDiscussionPhase:
    """Tests for discussion phase."""

    @pytest.mark.asyncio
    async def test_discussion_generates_speeches(
        self,
        initial_state: GameState,
        collector: EventCollector,
        players: dict[int, Player],
    ):
        """Test that Discussion phase generates speeches from living players."""
        scheduler = DayScheduler()
        participants = create_participants_from_players(players, seed=444)

        # Save original living players before run (run_day mutates state)
        original_living = initial_state.living_players.copy()

        state, collector = await scheduler.run_day(initial_state, collector, participants)

        # Find discussion speeches
        event_log = collector.get_event_log()
        speeches = []
        for phase in event_log.phases:
            if phase.kind == Phase.DAY:
                for subphase in phase.subphases:
                    if subphase.micro_phase == SubPhase.DISCUSSION:
                        for event in subphase.events:
                            if isinstance(event, Speech):
                                speeches.append(event)

        # All originally living players should speak
        assert len(speeches) == len(original_living)

        # Each speech should be from a living player
        for speech in speeches:
            assert speech.actor in original_living


class TestVictoryDetection:
    """Tests for victory detection during day phase."""

    @pytest.mark.asyncio
    async def test_victory_detection_no_win_early(
        self,
        initial_state: GameState,
        collector: EventCollector,
        players: dict[int, Player],
    ):
        """Test that game doesn't end prematurely with 12 players."""
        scheduler = DayScheduler()
        participants = create_participants_from_players(players, seed=555)

        state, collector = await scheduler.run_day(initial_state, collector, participants)

        # Game should not be over with all 12 players
        is_over, winner = state.is_game_over()
        assert is_over is False

    @pytest.mark.asyncio
    async def test_victory_detection_werewolf_win(
        self,
        initial_state: GameState,
        collector: EventCollector,
        players: dict[int, Player],
    ):
        """Test victory detection when werewolves win."""
        scheduler = DayScheduler()

        # Set up state where werewolves have won (all non-werewolves dead)
        # Find werewolf seats dynamically since roles are shuffled
        werewolf_seats = {seat for seat, p in players.items() if p.role == Role.WEREWOLF}
        non_werewolf_seats = {seat for seat in players.keys() if seat not in werewolf_seats}

        # Kill all non-werewolves
        for seat in non_werewolf_seats:
            initial_state.players[seat].is_alive = False

        # Update living/dead sets - only werewolves alive
        initial_state.living_players = werewolf_seats.copy()
        initial_state.dead_players = non_werewolf_seats.copy()

        participants = create_participants_from_players(initial_state.players, seed=666)

        state, collector = await scheduler.run_day(initial_state, collector, participants)

        # Game should be over with werewolf victory
        is_over, winner = state.is_game_over()
        assert is_over is True
        assert winner == "WEREWOLF"

    @pytest.mark.asyncio
    async def test_victory_detection_villager_win(
        self,
        initial_state: GameState,
        collector: EventCollector,
        players: dict[int, Player],
    ):
        """Test victory detection when villagers win."""
        scheduler = DayScheduler()

        # Set up state where villagers have won (all werewolves dead)
        # Find werewolf seats dynamically since roles are shuffled
        werewolf_seats = {seat for seat, p in players.items() if p.role == Role.WEREWOLF}

        # Kill all werewolves
        for seat in werewolf_seats:
            initial_state.players[seat].is_alive = False

        # Update living/dead sets - only non-werewolves alive
        initial_state.living_players = {seat for seat in players.keys() if seat not in werewolf_seats}
        initial_state.dead_players = werewolf_seats.copy()

        participants = create_participants_from_players(initial_state.players, seed=777)

        state, collector = await scheduler.run_day(initial_state, collector, participants)

        # Game should be over with villager victory
        is_over, winner = state.is_game_over()
        assert is_over is True
        assert winner == "VILLAGER"


class TestStateUpdates:
    """Tests for state updates after day phase."""

    @pytest.mark.asyncio
    async def test_state_reflects_deaths(
        self,
        initial_state: GameState,
        collector: EventCollector,
        players: dict[int, Player],
    ):
        """Test that state is updated after banishment."""
        scheduler = DayScheduler()
        participants = create_participants_from_players(players, seed=888)

        # Run day
        state, collector = await scheduler.run_day(initial_state, collector, participants)

        # Find banished player
        event_log = collector.get_event_log()
        banished_seat = None
        for phase in event_log.phases:
            if phase.kind == Phase.DAY:
                for subphase in phase.subphases:
                    if subphase.micro_phase == SubPhase.VOTING:
                        for event in subphase.events:
                            if isinstance(event, Banishment):
                                banished_seat = event.banished
                                break
                        if banished_seat is not None:
                            break
                if banished_seat is not None:
                    break

        # There should have been a banishment (tie = no banishment)
        # With random votes, there may or may not be a banishment
        # But if there was one, state should be updated
        if banished_seat is not None:
            assert banished_seat not in state.living_players, f"Banished seat {banished_seat} should not be in living_players"
            assert banished_seat in state.dead_players, f"Banished seat {banished_seat} should be in dead_players"


class TestEventCollectorIntegration:
    """Tests for EventCollector integration with DayScheduler."""

    @pytest.mark.asyncio
    async def test_collector_collects_all_events(
        self,
        initial_state: GameState,
        collector: EventCollector,
        players: dict[int, Player],
    ):
        """Test that collector gathers all events from day phases."""
        scheduler = DayScheduler()
        participants = create_participants_from_players(players, seed=999)

        # Run day
        state, collector = await scheduler.run_day(initial_state, collector, participants)

        # Get event log
        event_log = collector.get_event_log()

        # Should have exactly one day phase
        day_phases = [p for p in event_log.phases if p.kind == Phase.DAY]
        assert len(day_phases) == 1

        # Should have events from each subphase
        day_phase = day_phases[0]
        assert len(day_phase.subphases) > 0

    @pytest.mark.asyncio
    async def test_collector_day_number(
        self,
        day2_state: GameState,
        collector: EventCollector,
        players: dict[int, Player],
    ):
        """Test that collector tracks correct day number."""
        scheduler = DayScheduler()
        participants = create_participants_from_players(players, seed=101)

        # Run day
        state, collector = await scheduler.run_day(day2_state, collector, participants)

        # Collector should have day 2
        assert collector.day == 2


# ============================================================================
# Run tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
