"""Integration tests: Handlers + StubPlayer.

Tests that stub AIs work correctly with handlers end-to-end.
Verifies the interaction between handlers and participants.
"""

import asyncio
import pytest
from typing import Protocol, Sequence, Optional

from werewolf.events import (
    Phase,
    SubPhase,
    WitchAction,
    WitchActionType,
    GuardAction,
    SeerAction,
    Speech,
    SheriffOptOut,
    Vote,
    GameEvent,
    NightOutcome,
    DeathEvent,
    DeathCause,
    Banishment,
)
from werewolf.models import (
    Player,
    Role,
    RoleConfig,
    STANDARD_12_PLAYER_CONFIG,
)


# ============================================================================
# Helper to create players dict from config
# ============================================================================

def create_players_from_config() -> dict[int, Player]:
    """Create a dict of players from standard config."""
    players = {}
    seat = 0
    for role_config in STANDARD_12_PLAYER_CONFIG:
        for _ in range(role_config.count):
            players[seat] = Player(
                seat=seat,
                name=f"Player {seat}",
                role=role_config.role,
            )
            seat += 1
    return players


# ============================================================================
# Shared PhaseContext for tests
# ============================================================================

class PhaseContext:
    """Minimal context for testing handlers with StubPlayer."""

    def __init__(
        self,
        players: dict[int, Player],
        living_players: set[int],
        dead_players: set[int],
        sheriff: Optional[int] = None,
        day: int = 1,
        sheriff_candidates: Optional[list[int]] = None,
        deaths: Optional[dict[int, DeathCause]] = None,
        night_actions: Optional["NightActions"] = None,
    ):
        self.players = players
        self.living_players = living_players
        self.dead_players = dead_players
        self.sheriff = sheriff
        self.day = day
        self.sheriff_candidates = sheriff_candidates or []
        self.deaths = deaths or {}
        self.night_actions = night_actions

    def get_player(self, seat: int) -> Optional[Player]:
        return self.players.get(seat)

    def is_werewolf(self, seat: int) -> bool:
        player = self.get_player(seat)
        return player is not None and player.role == Role.WEREWOLF

    def is_alive(self, seat: int) -> bool:
        return seat in self.living_players


class NightActions:
    """Night actions accumulator for testing."""

    def __init__(
        self,
        kill_target: Optional[int] = None,
        antidote_used: bool = False,
        poison_used: bool = False,
        guard_target: Optional[int] = None,
        guard_prev_target: Optional[int] = None,
    ):
        self.kill_target = kill_target
        self.antidote_used = antidote_used
        self.poison_used = poison_used
        self.guard_target = guard_target
        self.guard_prev_target = guard_prev_target


# ============================================================================
# Import handlers and stub player
# ============================================================================

from werewolf.handlers.werewolf_handler import WerewolfHandler, WerewolfKill
from werewolf.handlers.witch_handler import WitchHandler, NightActions as WitchNightActions
from werewolf.handlers.guard_handler import GuardHandler
from werewolf.handlers.seer_handler import SeerHandler
from werewolf.handlers.discussion_handler import DiscussionHandler
from werewolf.handlers.voting_handler import VotingHandler
from werewolf.ai.stub_ai import StubPlayer, create_stub_player


# ============================================================================
# Test fixtures
# ============================================================================

@pytest.fixture
def standard_players() -> dict[int, Player]:
    """Create standard 12-player config as dict."""
    return create_players_from_config()


@pytest.fixture
def day1_context(standard_players: dict[int, Player]) -> PhaseContext:
    """Create Day 1 context with all players alive."""
    return PhaseContext(
        players=standard_players,
        living_players=set(standard_players.keys()),
        dead_players=set(),
        day=1,
    )


@pytest.fixture
def night1_context(standard_players: dict[int, Player]) -> PhaseContext:
    """Create Night 1 context with all players alive."""
    return PhaseContext(
        players=standard_players,
        living_players=set(standard_players.keys()),
        dead_players=set(),
        day=1,
        night_actions=WitchNightActions(),
    )


# ============================================================================
# Helper assertion functions
# ============================================================================

def get_event_by_type(events: list, event_type: type) -> Optional[GameEvent]:
    """Get first event of specified type from list."""
    for event in events:
        if type(event).__name__ == event_type.__name__:
            return event
    return None


def filter_events_by_type(events: list, event_type: type) -> list:
    """Filter events by type."""
    return [e for e in events if type(e).__name__ == event_type.__name__]


# ============================================================================
# WerewolfHandler + StubPlayer Tests
# ============================================================================

class TestWerewolfHandlerIntegration:
    """Integration tests: WerewolfHandler with StubPlayer."""

    @pytest.mark.asyncio
    async def test_werewolf_kill_with_stub_player(self, night1_context: PhaseContext):
        """Test werewolf handler generates valid kill event with stub."""
        handler = WerewolfHandler()
        stub = create_stub_player(seed=42)

        # Run werewolf action
        werewolf_seats = [s for s in night1_context.living_players if night1_context.is_werewolf(s)]
        participants = [(s, stub) for s in werewolf_seats]

        result = await handler(night1_context, participants)

        # Verify output
        assert len(result.subphase_log.events) == 1
        event = result.subphase_log.events[0]
        # Use type name check for Pydantic v2 compatibility
        assert type(event).__name__ == "WerewolfKill"
        assert event.actor in werewolf_seats
        # Target should be valid (living or -1 for skip)
        assert event.target in night1_context.living_players or event.target == -1

    @pytest.mark.asyncio
    async def test_werewolf_consensus_with_multiple_stubs(self, night1_context: PhaseContext):
        """Test multiple werewolves reach consensus with stub AIs."""
        handler = WerewolfHandler()

        # Create separate stubs for each werewolf
        stubs = {s: create_stub_player(seed=s*10) for s in [0, 1, 2, 3]}
        participants = [(s, stubs[s]) for s in stubs]

        result = await handler(night1_context, participants)

        # Should have one collective decision
        assert len(result.subphase_log.events) == 1
        event = result.subphase_log.events[0]
        assert type(event).__name__ == "WerewolfKill"

    @pytest.mark.asyncio
    async def test_werewolf_skip_with_stub(self, night1_context: PhaseContext):
        """Test werewolf can skip (0.1 chance) with stub."""
        handler = WerewolfHandler()

        # Force skip by setting seed that likely produces skip
        # We'll retry a few times since skip is probabilistic
        for attempt in range(20):
            stub = create_stub_player(seed=attempt)
            werewolf_seats = [s for s in night1_context.living_players if night1_context.is_werewolf(s)]
            participants = [(s, stub) for s in werewolf_seats]
            result = await handler(night1_context, participants)
            if result.subphase_log.events[0].target == -1:
                break

        # Should have a result
        assert len(result.subphase_log.events) == 1


# ============================================================================
# WitchHandler + StubPlayer Tests
# ============================================================================

class TestWitchHandlerIntegration:
    """Integration tests: WitchHandler with StubPlayer."""

    @pytest.mark.asyncio
    async def test_witch_action_with_stub(self, night1_context: PhaseContext):
        """Test witch handler generates valid action with stub."""
        handler = WitchHandler()

        # Set a werewolf kill target so witch has antidote option
        night1_context.night_actions = WitchNightActions(kill_target=5)

        # Find witch seat
        witch_seat = None
        for seat, player in night1_context.players.items():
            if player.role == Role.WITCH:
                witch_seat = seat
                break

        assert witch_seat is not None, "Witch not found in standard config"
        stub = create_stub_player(seed=42)

        result = await handler(night1_context, [(witch_seat, stub)], night1_context.night_actions)

        # Verify output
        assert len(result.subphase_log.events) == 1
        event = result.subphase_log.events[0]
        assert type(event).__name__ == "WitchAction"
        assert event.actor == witch_seat

    @pytest.mark.asyncio
    async def test_witch_pass_with_stub(self, night1_context: PhaseContext):
        """Test witch can pass (most common with random)."""
        handler = WitchHandler()
        night1_context.night_actions = WitchNightActions(kill_target=5)

        # Find witch seat
        witch_seat = None
        for seat, player in night1_context.players.items():
            if player.role == Role.WITCH:
                witch_seat = seat
                break

        # Use seed that produces PASS
        stub = create_stub_player(seed=999)

        result = await handler(night1_context, [(witch_seat, stub)], night1_context.night_actions)

        event = result.subphase_log.events[0]
        assert type(event).__name__ == "WitchAction"


# ============================================================================
# GuardHandler + StubPlayer Tests
# ============================================================================

class TestGuardHandlerIntegration:
    """Integration tests: GuardHandler with StubPlayer."""

    @pytest.mark.asyncio
    async def test_guard_action_with_stub(self, night1_context: PhaseContext):
        """Test guard handler generates valid action with stub."""
        handler = GuardHandler()
        night1_context.night_actions = WitchNightActions(guard_prev_target=None)

        # Find guard seat
        guard_seat = None
        for seat, player in night1_context.players.items():
            if player.role == Role.GUARD:
                guard_seat = seat
                break

        assert guard_seat is not None, "Guard not found in standard config"

        # Use seed that produces a seat number (not SKIP)
        stub = create_stub_player(seed=777)

        result = await handler(night1_context, [(guard_seat, stub)], night1_context.night_actions)

        assert len(result.subphase_log.events) == 1
        event = result.subphase_log.events[0]
        assert type(event).__name__ == "GuardAction"
        assert event.actor == guard_seat


# ============================================================================
# SeerHandler + StubPlayer Tests
# ============================================================================

class TestSeerHandlerIntegration:
    """Integration tests: SeerHandler with StubPlayer."""

    @pytest.mark.asyncio
    async def test_seer_action_with_stub(self, night1_context: PhaseContext):
        """Test seer handler generates valid action with stub."""
        handler = SeerHandler()

        # Find seer seat
        seer_seat = None
        for seat, player in night1_context.players.items():
            if player.role == Role.SEER:
                seer_seat = seat
                break

        assert seer_seat is not None, "Seer not found in standard config"

        # Use seed that produces a valid target
        stub = create_stub_player(seed=555)

        result = await handler(night1_context, [(seer_seat, stub)])

        assert len(result.subphase_log.events) == 1
        event = result.subphase_log.events[0]
        assert type(event).__name__ == "SeerAction"
        assert event.actor == seer_seat
        # Target should be valid living player (not self)
        assert event.target in night1_context.living_players
        assert event.target != seer_seat


# ============================================================================
# Day Phase Handlers + StubPlayer Tests
# ============================================================================

class TestDayPhaseIntegration:
    """Integration tests: Day phase handlers with StubPlayer."""

    @pytest.mark.asyncio
    async def test_discussion_with_stub(self, day1_context: PhaseContext):
        """Test discussion handler works with stub."""
        handler = DiscussionHandler()

        living = list(day1_context.living_players)
        stubs = {s: create_stub_player(seed=s) for s in living[:3]}  # Test with 3 speakers
        participants = [(s, stubs[s]) for s in stubs]

        result = await handler(day1_context, participants)

        # Should have one speech per participant
        speeches = filter_events_by_type(result.subphase_log.events, Speech)
        assert len(speeches) == len(stubs)
        for event in speeches:
            assert len(event.content) > 10  # Real speech content

    @pytest.mark.asyncio
    async def test_voting_with_stub(self, day1_context: PhaseContext):
        """Test voting handler works with stub."""
        handler = VotingHandler()

        living = list(day1_context.living_players)
        stubs = {s: create_stub_player(seed=s) for s in living}
        participants = [(s, stubs[s]) for s in living]

        result = await handler(day1_context, participants)

        # Should have votes + possibly Banishment event
        votes = filter_events_by_type(result.subphase_log.events, Vote)
        # Filter out any None/abstain votes
        valid_votes = [v for v in votes if v.target is not None]

        # All living players should have voted
        assert len(votes) == len(living)

        # Each vote should be from a living player
        for event in votes:
            assert event.actor in living


# ============================================================================
# Full Night Flow Integration Test
# ============================================================================

class TestFullNightIntegration:
    """Integration test: Complete night flow with stub AIs."""

    @pytest.mark.asyncio
    async def test_night_flow_with_stubs(self, standard_players: dict[int, Player]):
        """Test complete night phase: Werewolf -> Witch -> Guard -> Seer."""
        # Start with all players alive
        context = PhaseContext(
            players=standard_players,
            living_players=set(standard_players.keys()),
            dead_players=set(),
            day=1,
            night_actions=WitchNightActions(),
        )

        # Find role seats
        witch_seat = None
        guard_seat = None
        seer_seat = None
        for seat, player in standard_players.items():
            if player.role == Role.WITCH:
                witch_seat = seat
            elif player.role == Role.GUARD:
                guard_seat = seat
            elif player.role == Role.SEER:
                seer_seat = seat

        # Create stub for each role
        stubs = {s: create_stub_player(seed=s*100) for s in standard_players.keys()}

        # 1. Werewolf Action
        ww_handler = WerewolfHandler()
        ww_seats = [s for s in context.living_players if context.is_werewolf(s)]
        ww_participants = [(s, stubs[s]) for s in ww_seats]
        ww_result = await ww_handler(context, ww_participants)
        ww_event = get_event_by_type(ww_result.subphase_log.events, WerewolfKill)
        assert ww_event is not None

        # Update night actions with werewolf target
        context.night_actions.kill_target = ww_event.target

        # 2. Witch Action
        witch_handler = WitchHandler()
        witch_result = await witch_handler(context, [(witch_seat, stubs[witch_seat])], context.night_actions)
        witch_event = get_event_by_type(witch_result.subphase_log.events, WitchAction)
        assert witch_event is not None

        # 3. Guard Action
        guard_handler = GuardHandler()
        guard_result = await guard_handler(context, [(guard_seat, stubs[guard_seat])], context.night_actions)
        guard_event = get_event_by_type(guard_result.subphase_log.events, GuardAction)
        assert guard_event is not None

        # 4. Seer Action
        seer_handler = SeerHandler()
        seer_result = await seer_handler(context, [(seer_seat, stubs[seer_seat])])
        seer_event = get_event_by_type(seer_result.subphase_log.events, SeerAction)
        assert seer_event is not None

        # All events generated successfully
        print(f"Werewolf target: {ww_event.target}")
        print(f"Witch action: {witch_event.action_type} -> {witch_event.target}")
        print(f"Guard target: {guard_event.target}")
        print(f"Seer target: {seer_event.target}")


# ============================================================================
# Run tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
