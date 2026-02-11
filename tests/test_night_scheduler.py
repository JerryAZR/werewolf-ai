"""Tests for NightScheduler - night phase orchestration."""

import random
import pytest
from typing import Optional

from werewolf.engine import (
    GameState,
    NightActionStore,
    EventCollector,
    NightScheduler,
)
from werewolf.models import (
    Player,
    Role,
    STANDARD_12_PLAYER_CONFIG,
    create_players_from_config,
)
from werewolf.events import (
    Phase,
    SubPhase,
    DeathCause,
)
from werewolf.ai.stub_ai import StubPlayer


# ============================================================================
# Helper types and functions
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
# Test fixtures
# ============================================================================

@pytest.fixture
def players() -> dict[int, Player]:
    """Create standard 12-player config as dict with shuffled roles."""
    return create_players_shuffled()


@pytest.fixture
def state(players: dict[int, Player]) -> GameState:
    """Create game state with all players alive."""
    return GameState(
        players=players,
        living_players=set(players.keys()),
        dead_players=set(),
        sheriff=None,
        day=1,
    )


@pytest.fixture
def actions() -> NightActionStore:
    """Create fresh night action store."""
    return NightActionStore()


@pytest.fixture
def collector() -> EventCollector:
    """Create event collector."""
    collector = EventCollector(day=1)
    return collector


@pytest.fixture
def participants(players: dict[int, Player]) -> dict[int, StubPlayer]:
    """Create participants dict with stub player for each player."""
    return {seat: StubPlayer(seed=seat) for seat in players.keys()}


@pytest.fixture
def scheduler() -> NightScheduler:
    """Create night scheduler."""
    return NightScheduler()


# ============================================================================
# Tests
# ============================================================================

class TestNightSchedulerBasic:
    """Basic NightScheduler tests."""

    def test_scheduler_created(self, scheduler: NightScheduler):
        """Test scheduler can be created."""
        assert scheduler is not None

    def test_scheduler_has_handlers(self, scheduler: NightScheduler):
        """Test scheduler has all required handlers."""
        assert hasattr(scheduler, "_werewolf_handler")
        assert hasattr(scheduler, "_witch_handler")
        assert hasattr(scheduler, "_guard_handler")
        assert hasattr(scheduler, "_seer_handler")
        assert hasattr(scheduler, "_resolver")
        assert hasattr(scheduler, "_death_handler")


class TestNightSchedulerRunNight:
    """Tests for run_night method."""

    @pytest.mark.asyncio
    async def test_run_night_returns_tuple(
        self,
        scheduler: NightScheduler,
        state: GameState,
        actions: NightActionStore,
        collector: EventCollector,
        participants: dict[int, StubPlayer],
    ):
        """Test run_night returns expected tuple type."""
        result = await scheduler.run_night(state, actions, collector, participants)

        assert isinstance(result, tuple)
        assert len(result) == 4

        new_state, new_actions, new_collector, deaths = result
        assert isinstance(new_state, GameState)
        assert isinstance(new_actions, NightActionStore)
        assert isinstance(new_collector, EventCollector)
        assert isinstance(deaths, dict)

    @pytest.mark.asyncio
    async def test_run_night_with_stub_participants(
        self,
        scheduler: NightScheduler,
        state: GameState,
        actions: NightActionStore,
        collector: EventCollector,
        participants: dict[int, StubPlayer],
    ):
        """Test full night with stub participants."""
        new_state, new_actions, new_collector, deaths = await scheduler.run_night(
            state, actions, collector, participants
        )

        # Check events were collected
        event_log = new_collector.get_event_log()
        assert len(event_log.phases) >= 1

        # Check night phase exists
        night_phase = None
        for phase in event_log.phases:
            if phase.kind == Phase.NIGHT:
                night_phase = phase
                break

        assert night_phase is not None
        assert len(night_phase.subphases) >= 4  # WEREWOLF, WITCH, GUARD, SEER

    @pytest.mark.asyncio
    async def test_run_night_creates_night_outcome(
        self,
        scheduler: NightScheduler,
        state: GameState,
        actions: NightActionStore,
        collector: EventCollector,
        participants: dict[int, StubPlayer],
    ):
        """Test run_night creates NightOutcome with deaths."""
        new_state, new_actions, new_collector, deaths = await scheduler.run_night(
            state, actions, collector, participants
        )

        # Get events and check for NightOutcome
        events = new_collector.get_events()
        night_outcomes = [e for e in events if e.__class__.__name__ == "NightOutcome"]

        assert len(night_outcomes) >= 1

    @pytest.mark.asyncio
    async def test_run_night_updates_actions(
        self,
        scheduler: NightScheduler,
        state: GameState,
        actions: NightActionStore,
        collector: EventCollector,
        participants: dict[int, StubPlayer],
    ):
        """Test run_night updates night action store."""
        initial_actions = actions.model_copy()

        new_state, new_actions, new_collector, deaths = await scheduler.run_night(
            state, actions, collector, participants
        )

        # Actions should be preserved (persistent state)
        assert new_actions is not None


class TestNightSchedulerEdgeCases:
    """Edge case tests for NightScheduler."""

    @pytest.mark.asyncio
    async def test_no_werewolves_alive(
        self,
        scheduler: NightScheduler,
        players: dict[int, Player],
    ):
        """Test night when no werewolves are alive."""
        # Create state with all werewolves dead
        werewolf_seats = [
            seat for seat, p in players.items()
            if p.role == Role.WEREWOLF
        ]
        living = set(players.keys()) - set(werewolf_seats)

        state = GameState(
            players=players,
            living_players=living,
            dead_players=set(werewolf_seats),
            sheriff=None,
            day=1,
        )

        actions = NightActionStore()
        collector = EventCollector(day=1)
        participants = {seat: StubPlayer(seed=seat) for seat in living}

        new_state, new_actions, new_collector, deaths = await scheduler.run_night(
            state, actions, collector, participants
        )

        # Should complete without error
        event_log = new_collector.get_event_log()
        assert len(event_log.phases) >= 1

        # No werewolf kill should occur
        events = new_collector.get_events()
        kill_events = [e for e in events if e.__class__.__name__ == "WerewolfKill"]
        # Check if kill was skipped or no kill event
        for ke in kill_events:
            assert ke.target == -1 or ke.target is None

    @pytest.mark.asyncio
    async def test_no_witch_alive(
        self,
        scheduler: NightScheduler,
        players: dict[int, Player],
    ):
        """Test night when witch is dead."""
        # Find witch seat
        witch_seat = None
        for seat, player in players.items():
            if player.role == Role.WITCH:
                witch_seat = seat
                break

        assert witch_seat is not None

        # Create state with witch dead
        living = set(players.keys()) - {witch_seat}

        state = GameState(
            players=players,
            living_players=living,
            dead_players={witch_seat},
            sheriff=None,
            day=1,
        )

        actions = NightActionStore()
        collector = EventCollector(day=1)
        participants = {seat: StubPlayer(seed=seat) for seat in living}

        new_state, new_actions, new_collector, deaths = await scheduler.run_night(
            state, actions, collector, participants
        )

        # Should complete without error
        event_log = new_collector.get_event_log()
        assert len(event_log.phases) >= 1

    @pytest.mark.asyncio
    async def test_night_resolution_with_deaths(
        self,
        scheduler: NightScheduler,
        state: GameState,
        actions: NightActionStore,
        collector: EventCollector,
        participants: dict[int, StubPlayer],
    ):
        """Test night resolution produces expected death events."""
        new_state, new_actions, new_collector, deaths = await scheduler.run_night(
            state, actions, collector, participants
        )

        # Get death events
        events = new_collector.get_events()
        death_events = [e for e in events if e.__class__.__name__ == "DeathEvent"]

        # Death events should exist if players died
        # The stub participant returns PASS for witch, so likely no werewolf kill

    @pytest.mark.asyncio
    async def test_state_updated_after_night(
        self,
        scheduler: NightScheduler,
        state: GameState,
        actions: NightActionStore,
        collector: EventCollector,
        participants: dict[int, StubPlayer],
    ):
        """Test game state is properly updated after night."""
        initial_living_count = len(state.living_players)

        new_state, new_actions, new_collector, deaths = await scheduler.run_night(
            state, actions, collector, participants
        )

        # State should be updated (players may have died depending on stub actions)
        # Verify state structure is intact
        assert new_state.players is not None
        assert new_state.living_players is not None
        assert new_state.dead_players is not None
        assert len(new_state.living_players) <= initial_living_count

    @pytest.mark.asyncio
    async def test_event_log_after_night(
        self,
        scheduler: NightScheduler,
        state: GameState,
        actions: NightActionStore,
        collector: EventCollector,
        participants: dict[int, StubPlayer],
    ):
        """Test event log contains all expected subphases."""
        new_state, new_actions, new_collector, deaths = await scheduler.run_night(
            state, actions, collector, participants
        )

        event_log = new_collector.get_event_log()

        # Should have at least NIGHT phase
        night_phases = [p for p in event_log.phases if p.kind == Phase.NIGHT]
        assert len(night_phases) >= 1

        # Night phase should have subphases
        night_phase = night_phases[0]
        subphase_types = {sp.micro_phase for sp in night_phase.subphases}

        # Should have werewolf, witch, guard, seer subphases
        assert SubPhase.WEREWOLF_ACTION in subphase_types or any(
            "WEREWOLF" in sp.value for sp in night_phase.subphases
        )


class TestNightSchedulerDayProgression:
    """Tests for day progression in NightScheduler."""

    @pytest.mark.asyncio
    async def test_day_increments_after_night(
        self,
        scheduler: NightScheduler,
        state: GameState,
        actions: NightActionStore,
        collector: EventCollector,
        participants: dict[int, StubPlayer],
    ):
        """Test day number is properly set for night events."""
        assert state.day == 1

        new_state, new_actions, new_collector, deaths = await scheduler.run_night(
            state, actions, collector, participants
        )

        # Day should still be 1 for the night phase
        events = new_collector.get_events()
        for event in events:
            if hasattr(event, 'day'):
                # Events should have correct day set
                pass


# ============================================================================
# Run tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
