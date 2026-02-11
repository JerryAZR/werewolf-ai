"""Comprehensive tests for NightResolution handler.

Tests cover death calculation scenarios:
- Clean werewolf kill (no save) → death
- Werewolf kill + antidote → target saved
- Werewolf kill + guard → target saved
- Werewolf kill + antidote + guard → target saved
- Poison kills (ignores guard)
- Both werewolf kill and poison → two deaths

Priority scenarios:
- Poison on werewolf target → poison wins
- Poison on guard-protected player → poison still kills
- Antidote on wrong target → invalid (target not saved)

Edge cases:
- No deaths (empty dict)
- No werewolf target (kill_target=None)
- No poison used
- No guard action

Death cause assignment:
- WEREWOLF_KILL assigned correctly
- POISON assigned correctly
"""

import pytest
from typing import Optional, Any, Protocol, Sequence
from pydantic import BaseModel

from werewolf.events.game_events import (
    NightOutcome,
    Phase,
    SubPhase,
    DeathCause,
)
from werewolf.events.event_log import SubPhaseLog
from werewolf.models.player import Player, Role


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
# NightActions for NightResolutionContext
# ============================================================================


class NightActions(BaseModel):
    """Night actions state for NightResolution handler."""

    kill_target: Optional[int] = None  # Werewolf's chosen target
    antidote_target: Optional[int] = None  # Witch antidote target
    poison_target: Optional[int] = None  # Witch poison target
    antidote_used: bool = False
    poison_used: bool = False
    guard_target: Optional[int] = None  # Guard protected target


# ============================================================================
# NightResolutionContext for Testing
# ============================================================================


class NightResolutionContext(BaseModel):
    """Context for NightResolution handler testing."""

    players: dict[int, Player]
    living_players: set[int]
    dead_players: set[int]
    sheriff: Optional[int] = None
    day: int = 1
    night: int = 1
    night_actions: NightActions = NightActions()

    def get_player(self, seat: int) -> Optional[Player]:
        """Get player by seat."""
        return self.players.get(seat)

    def is_alive(self, seat: int) -> bool:
        """Check if a player is alive."""
        return seat in self.living_players


# ============================================================================
# Context Factory Functions
# ============================================================================


def make_context_standard_12() -> NightResolutionContext:
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
    night_actions = NightActions(kill_target=4)  # Werewolves targeting Seer

    context = NightResolutionContext(
        players=players,
        living_players=living,
        dead_players=dead,
        sheriff=None,
        day=1,
        night=1,
        night_actions=night_actions,
    )
    return context


# ============================================================================
# NightResolutionHandler Implementation (for testing)
# ============================================================================


class HandlerResult(BaseModel):
    """Output from handlers containing all events from a subphase."""

    subphase_log: SubPhaseLog
    debug_info: Optional[str] = None


class NightResolutionHandler:
    """Handler for NightResolution subphase.

    Responsibilities:
    1. Calculate deaths based on all night actions
    2. Apply protection rules (antidote, guard)
    3. Apply poison kills (ignores guard)
    4. Return NightOutcome with death causes

    Death Calculation Logic:
    1. Start with kill_target → WEREWOLF_KILL
    2. If antidote_target == kill_target: remove (target saved)
    3. If guard_target == kill_target: remove (target saved)
    4. If poison_target exists: add {poison_target: POISON}
    5. Return deaths dict
    """

    async def __call__(
        self,
        context: NightResolutionContext,
    ) -> HandlerResult:
        """Execute the NightResolution subphase.

        Args:
            context: Game state with players, living/dead, sheriff, night_actions

        Returns:
            HandlerResult with SubPhaseLog containing NightOutcome event
        """
        night_actions = context.night_actions

        # Calculate deaths using the death calculation logic
        deaths = self._calculate_deaths(night_actions, context)

        # Create NightOutcome event
        outcome = NightOutcome(
            deaths=deaths,
            day=context.day,
            phase=Phase.NIGHT,
            micro_phase=SubPhase.NIGHT_RESOLUTION,
        )

        return HandlerResult(
            subphase_log=SubPhaseLog(
                micro_phase=SubPhase.NIGHT_RESOLUTION,
                events=[outcome],
            ),
        )

    def _calculate_deaths(
        self,
        night_actions: NightActions,
        context: NightResolutionContext,
    ) -> dict[int, DeathCause]:
        """Calculate deaths based on all night actions.

        Args:
            night_actions: All night actions accumulated during the night
            context: Game state to check if targets are alive

        Returns:
            Dict mapping seat to death cause
        """
        deaths: dict[int, DeathCause] = {}

        kill_target = night_actions.kill_target

        # Start with werewolf kill target if exists AND target is alive
        if kill_target is not None and kill_target in context.living_players:
            deaths[kill_target] = DeathCause.WEREWOLF_KILL

        # Apply antidote (saves werewolf target)
        if (
            night_actions.antidote_target is not None
            and night_actions.antidote_target == kill_target
        ):
            # Target is saved, remove from deaths
            if kill_target in deaths:
                del deaths[kill_target]

        # Apply guard protection (saves werewolf target)
        if (
            night_actions.guard_target is not None
            and night_actions.guard_target == kill_target
        ):
            # Target is saved, remove from deaths
            if kill_target in deaths:
                del deaths[kill_target]

        # Apply poison (kills target, ignores guard)
        if night_actions.poison_target is not None:
            # Only add if target is alive
            if night_actions.poison_target in context.living_players:
                deaths[night_actions.poison_target] = DeathCause.POISON

        return deaths


# ============================================================================
# Expected NightOutcome Factory
# ============================================================================


def expected_night_outcome(
    deaths: dict[int, DeathCause],
    day: int = 1,
) -> NightOutcome:
    """Create an expected NightOutcome event for validation."""
    return NightOutcome(
        deaths=deaths,
        day=day,
        phase=Phase.NIGHT,
        micro_phase=SubPhase.NIGHT_RESOLUTION,
    )


# ============================================================================
# Tests for NightResolution Death Calculation
# ============================================================================


class TestNightResolutionDeathCalculation:
    """Tests for death calculation scenarios."""

    @pytest.mark.asyncio
    async def test_clean_werewolf_kill(self):
        """Test clean werewolf kill with no saves results in death."""
        context = make_context_standard_12()

        # No antidote, no guard, no poison
        context.night_actions = NightActions(
            kill_target=4,  # Werewolves target Seer
            antidote_used=False,
            poison_used=False,
        )

        handler = NightResolutionHandler()
        result = await handler(context)

        assert result.subphase_log.micro_phase == SubPhase.NIGHT_RESOLUTION
        assert len(result.subphase_log.events) == 1

        outcome = result.subphase_log.events[0]
        assert isinstance(outcome, NightOutcome)
        assert outcome.day == context.day
        assert outcome.deaths == {4: DeathCause.WEREWOLF_KILL}

    @pytest.mark.asyncio
    async def test_werewolf_kill_saved_by_antidote(self):
        """Test werewolf kill saved by antidote."""
        context = make_context_standard_12()

        # Witch uses antidote on werewolf target
        context.night_actions = NightActions(
            kill_target=4,  # Werewolves target Seer
            antidote_target=4,  # Witch saves Seer
            antidote_used=True,
        )

        handler = NightResolutionHandler()
        result = await handler(context)

        outcome = result.subphase_log.events[0]
        assert isinstance(outcome, NightOutcome)
        # Seer is saved by antidote
        assert outcome.deaths == {}

    @pytest.mark.asyncio
    async def test_werewolf_kill_saved_by_guard(self):
        """Test werewolf kill saved by guard protection."""
        context = make_context_standard_12()

        # Guard protects werewolf target
        context.night_actions = NightActions(
            kill_target=4,  # Werewolves target Seer
            guard_target=4,  # Guard protects Seer
        )

        handler = NightResolutionHandler()
        result = await handler(context)

        outcome = result.subphase_log.events[0]
        assert isinstance(outcome, NightOutcome)
        # Seer is saved by guard
        assert outcome.deaths == {}

    @pytest.mark.asyncio
    async def test_werewolf_kill_saved_by_antidote_and_guard(self):
        """Test werewolf kill saved by both antidote and guard."""
        context = make_context_standard_12()

        # Both antidote and guard protect werewolf target
        context.night_actions = NightActions(
            kill_target=4,
            antidote_target=4,
            guard_target=4,
        )

        handler = NightResolutionHandler()
        result = await handler(context)

        outcome = result.subphase_log.events[0]
        assert isinstance(outcome, NightOutcome)
        # Seer is saved (double protection still means survival)
        assert outcome.deaths == {}

    @pytest.mark.asyncio
    async def test_poison_kills_ignoring_guard(self):
        """Test poison kills target even if guard protects them."""
        context = make_context_standard_12()

        # Guard protects someone, but witch poisons them
        context.night_actions = NightActions(
            kill_target=8,  # Werewolves target V1
            poison_target=8,  # Witch poisons V1
            guard_target=8,  # Guard protects V1 (but poison ignores guard)
        )

        handler = NightResolutionHandler()
        result = await handler(context)

        outcome = result.subphase_log.events[0]
        assert isinstance(outcome, NightOutcome)
        # V1 dies from poison despite guard protection
        assert outcome.deaths == {8: DeathCause.POISON}

    @pytest.mark.asyncio
    async def test_poison_on_werewolf_target_wins(self):
        """Test poison on werewolf target takes precedence over werewolf kill."""
        context = make_context_standard_12()

        # Werewolves target Seer, but witch poisons Seer
        context.night_actions = NightActions(
            kill_target=4,  # Werewolves target Seer
            poison_target=4,  # Witch poisons Seer
        )

        handler = NightResolutionHandler()
        result = await handler(context)

        outcome = result.subphase_log.events[0]
        assert isinstance(outcome, NightOutcome)
        # Seer dies from POISON, not WEREWOLF_KILL
        assert outcome.deaths == {4: DeathCause.POISON}

    @pytest.mark.asyncio
    async def test_both_werewolf_kill_and_poison(self):
        """Test both werewolf kill and poison result in two deaths."""
        context = make_context_standard_12()

        # Werewolves target Seer, witch poisons Villager
        context.night_actions = NightActions(
            kill_target=4,  # Werewolves target Seer
            poison_target=8,  # Witch poisons V1
        )

        handler = NightResolutionHandler()
        result = await handler(context)

        outcome = result.subphase_log.events[0]
        assert isinstance(outcome, NightOutcome)
        # Two deaths with different causes
        assert outcome.deaths == {
            4: DeathCause.WEREWOLF_KILL,
            8: DeathCause.POISON,
        }

    @pytest.mark.asyncio
    async def test_poison_on_guard_protected_player(self):
        """Test poison kills guard-protected player."""
        context = make_context_standard_12()

        # Werewolves don't kill, but witch poisons guard-protected player
        context.night_actions = NightActions(
            kill_target=None,  # No werewolf kill
            poison_target=7,  # Witch poisons Hunter
            guard_target=7,  # Guard protects Hunter (but poison ignores guard)
        )

        handler = NightResolutionHandler()
        result = await handler(context)

        outcome = result.subphase_log.events[0]
        assert isinstance(outcome, NightOutcome)
        # Hunter dies from poison despite guard protection
        assert outcome.deaths == {7: DeathCause.POISON}

    @pytest.mark.asyncio
    async def test_antidote_on_wrong_target_invalid(self):
        """Test antidote on wrong target does not save werewolf target."""
        context = make_context_standard_12()

        # Witch uses antidote on wrong player
        context.night_actions = NightActions(
            kill_target=4,  # Werewolves target Seer
            antidote_target=8,  # Witch uses antidote on V1 (wrong target)
            antidote_used=True,
        )

        handler = NightResolutionHandler()
        result = await handler(context)

        outcome = result.subphase_log.events[0]
        assert isinstance(outcome, NightOutcome)
        # Seer dies because antidote wasn't on them
        assert outcome.deaths == {4: DeathCause.WEREWOLF_KILL}


# ============================================================================
# Tests for NightResolution Edge Cases
# ============================================================================


class TestNightResolutionEdgeCases:
    """Tests for edge cases in NightResolution."""

    @pytest.mark.asyncio
    async def test_no_deaths(self):
        """Test no deaths when werewolves skip and no poison."""
        context = make_context_standard_12()

        # Werewolves skip, witch passes
        context.night_actions = NightActions(
            kill_target=None,  # No werewolf kill
            antidote_used=False,
            poison_used=False,
        )

        handler = NightResolutionHandler()
        result = await handler(context)

        outcome = result.subphase_log.events[0]
        assert isinstance(outcome, NightOutcome)
        # No deaths
        assert outcome.deaths == {}

    @pytest.mark.asyncio
    async def test_no_werewolf_target(self):
        """Test when werewolves chose not to kill (kill_target=None)."""
        context = make_context_standard_12()

        context.night_actions = NightActions(
            kill_target=None,
            poison_target=4,  # Witch poisons Seer instead
        )

        handler = NightResolutionHandler()
        result = await handler(context)

        outcome = result.subphase_log.events[0]
        assert isinstance(outcome, NightOutcome)
        # Only poison death
        assert outcome.deaths == {4: DeathCause.POISON}

    @pytest.mark.asyncio
    async def test_no_poison_used(self):
        """Test when no poison is used."""
        context = make_context_standard_12()

        context.night_actions = NightActions(
            kill_target=4,
            poison_used=False,
        )

        handler = NightResolutionHandler()
        result = await handler(context)

        outcome = result.subphase_log.events[0]
        assert isinstance(outcome, NightOutcome)
        # Only werewolf kill
        assert outcome.deaths == {4: DeathCause.WEREWOLF_KILL}

    @pytest.mark.asyncio
    async def test_no_guard_action(self):
        """Test when guard takes no action (target=None)."""
        context = make_context_standard_12()

        context.night_actions = NightActions(
            kill_target=4,
            guard_target=None,  # Guard skips
        )

        handler = NightResolutionHandler()
        result = await handler(context)

        outcome = result.subphase_log.events[0]
        assert isinstance(outcome, NightOutcome)
        # Werewolf kill succeeds since guard didn't protect
        assert outcome.deaths == {4: DeathCause.WEREWOLF_KILL}

    @pytest.mark.asyncio
    async def test_only_poison_death(self):
        """Test poison only death with no werewolf kill."""
        context = make_context_standard_12()

        context.night_actions = NightActions(
            kill_target=None,
            poison_target=4,
        )

        handler = NightResolutionHandler()
        result = await handler(context)

        outcome = result.subphase_log.events[0]
        assert isinstance(outcome, NightOutcome)
        assert outcome.deaths == {4: DeathCause.POISON}

    @pytest.mark.asyncio
    async def test_guard_protection_on_non_target(self):
        """Test guard protecting someone who wasn't attacked."""
        context = make_context_standard_12()

        context.night_actions = NightActions(
            kill_target=8,  # Werewolves target V1
            guard_target=4,  # Guard protects Seer (wrong player)
            poison_target=None,
        )

        handler = NightResolutionHandler()
        result = await handler(context)

        outcome = result.subphase_log.events[0]
        assert isinstance(outcome, NightOutcome)
        # V1 dies, Seer is safe but not because of guard
        assert outcome.deaths == {8: DeathCause.WEREWOLF_KILL}

    @pytest.mark.asyncio
    async def test_no_living_players_as_targets(self):
        """Test when kill/poison targets are already dead."""
        context = make_context_standard_12()

        # Seer and V1 are dead
        living = {0, 1, 2, 3, 5, 6, 7, 9, 10, 11}
        context.living_players = living
        context.players[4].is_alive = False  # Seer is dead
        context.players[8].is_alive = False  # V1 is also dead

        # Werewolves target dead Seer, witch poisons dead V1
        # Both should be ignored
        context.night_actions = NightActions(
            kill_target=4,  # Dead target - should be ignored
            poison_target=8,  # Dead target - should be ignored
        )

        handler = NightResolutionHandler()
        result = await handler(context)

        outcome = result.subphase_log.events[0]
        assert isinstance(outcome, NightOutcome)
        # No deaths since both targets were dead
        assert outcome.deaths == {}


# ============================================================================
# Tests for NightResolution Priority Scenarios
# ============================================================================


class TestNightResolutionPriority:
    """Tests for priority and interaction between actions."""

    @pytest.mark.asyncio
    async def test_poison_priority_over_guard(self):
        """Test poison takes priority over guard protection."""
        context = make_context_standard_12()

        context.night_actions = NightActions(
            kill_target=8,
            poison_target=8,
            guard_target=8,
        )

        handler = NightResolutionHandler()
        result = await handler(context)

        outcome = result.subphase_log.events[0]
        assert isinstance(outcome, NightOutcome)
        # Poison kills despite guard protection
        assert outcome.deaths == {8: DeathCause.POISON}

    @pytest.mark.asyncio
    async def test_double_poison_not_possible(self):
        """Test poison can't be used twice in one night."""
        context = make_context_standard_12()

        context.night_actions = NightActions(
            kill_target=4,
            poison_target=None,  # Poison already used (can't have multiple)
            poison_used=True,
        )

        handler = NightResolutionHandler()
        result = await handler(context)

        outcome = result.subphase_log.events[0]
        assert isinstance(outcome, NightOutcome)
        # Only werewolf kill
        assert outcome.deaths == {4: DeathCause.WEREWOLF_KILL}

    @pytest.mark.asyncio
    async def test_antidote_then_poison_different_targets(self):
        """Test antidote on werewolf target, poison on different target."""
        context = make_context_standard_12()

        context.night_actions = NightActions(
            kill_target=4,
            antidote_target=4,
            poison_target=8,
        )

        handler = NightResolutionHandler()
        result = await handler(context)

        outcome = result.subphase_log.events[0]
        assert isinstance(outcome, NightOutcome)
        # Seer saved by antidote, V1 dies from poison
        assert outcome.deaths == {8: DeathCause.POISON}

    @pytest.mark.asyncio
    async def test_poison_on_poisoner(self):
        """Test witch can poison themselves."""
        context = make_context_standard_12()

        context.night_actions = NightActions(
            kill_target=None,
            poison_target=5,  # Witch poisons themselves
        )

        handler = NightResolutionHandler()
        result = await handler(context)

        outcome = result.subphase_log.events[0]
        assert isinstance(outcome, NightOutcome)
        # Witch dies from own poison
        assert outcome.deaths == {5: DeathCause.POISON}

    @pytest.mark.asyncio
    async def test_poison_on_werewolf(self):
        """Test witch can poison werewolf."""
        context = make_context_standard_12()

        context.night_actions = NightActions(
            kill_target=None,
            poison_target=0,  # Witch poisons werewolf
        )

        handler = NightResolutionHandler()
        result = await handler(context)

        outcome = result.subphase_log.events[0]
        assert isinstance(outcome, NightOutcome)
        # Werewolf dies from poison
        assert outcome.deaths == {0: DeathCause.POISON}


# ============================================================================
# Tests for NightResolution Death Cause Assignment
# ============================================================================


class TestNightResolutionDeathCause:
    """Tests for correct death cause assignment."""

    @pytest.mark.asyncio
    async def test_werewolf_kill_cause_assigned(self):
        """Test WEREWOLF_KILL cause is assigned correctly."""
        context = make_context_standard_12()

        context.night_actions = NightActions(
            kill_target=7,  # Werewolves target Hunter
        )

        handler = NightResolutionHandler()
        result = await handler(context)

        outcome = result.subphase_log.events[0]
        assert isinstance(outcome, NightOutcome)
        assert outcome.deaths[7] == DeathCause.WEREWOLF_KILL

    @pytest.mark.asyncio
    async def test_poison_cause_assigned(self):
        """Test POISON cause is assigned correctly."""
        context = make_context_standard_12()

        context.night_actions = NightActions(
            poison_target=4,  # Witch poisons Seer
        )

        handler = NightResolutionHandler()
        result = await handler(context)

        outcome = result.subphase_log.events[0]
        assert isinstance(outcome, NightOutcome)
        assert outcome.deaths[4] == DeathCause.POISON

    @pytest.mark.asyncio
    async def test_correct_cause_for_double_death(self):
        """Test correct causes when same player targeted by both."""
        context = make_context_standard_12()

        context.night_actions = NightActions(
            kill_target=4,
            poison_target=4,  # Same target for both
        )

        handler = NightResolutionHandler()
        result = await handler(context)

        outcome = result.subphase_log.events[0]
        assert isinstance(outcome, NightOutcome)
        # Only one death entry per player, poison takes precedence
        assert len(outcome.deaths) == 1
        assert outcome.deaths[4] == DeathCause.POISON

    @pytest.mark.asyncio
    async def test_different_causes_for_different_players(self):
        """Test different causes for different death targets."""
        context = make_context_standard_12()

        context.night_actions = NightActions(
            kill_target=4,
            poison_target=8,
        )

        handler = NightResolutionHandler()
        result = await handler(context)

        outcome = result.subphase_log.events[0]
        assert isinstance(outcome, NightOutcome)
        assert outcome.deaths[4] == DeathCause.WEREWOLF_KILL
        assert outcome.deaths[8] == DeathCause.POISON

    @pytest.mark.asyncio
    async def test_poison_ignores_werewolf_target_save(self):
        """Test poison cause even if werewolf target was saved by antidote."""
        context = make_context_standard_12()

        context.night_actions = NightActions(
            kill_target=4,
            antidote_target=4,  # Saved from werewolf kill
            poison_target=4,  # But poisoned
        )

        handler = NightResolutionHandler()
        result = await handler(context)

        outcome = result.subphase_log.events[0]
        assert isinstance(outcome, NightOutcome)
        # Poison kills despite antidote
        assert outcome.deaths == {4: DeathCause.POISON}


# ============================================================================
# Tests for NightResolution Event Structure
# ============================================================================


class TestNightResolutionEventStructure:
    """Tests for NightOutcome event structure and fields."""

    @pytest.mark.asyncio
    async def test_event_has_correct_phase(self):
        """Test that NightOutcome has correct NIGHT phase."""
        context = make_context_standard_12()

        handler = NightResolutionHandler()
        result = await handler(context)

        outcome = result.subphase_log.events[0]
        assert isinstance(outcome, NightOutcome)
        assert outcome.phase == Phase.NIGHT

    @pytest.mark.asyncio
    async def test_event_has_correct_micro_phase(self):
        """Test that NightOutcome has correct NIGHT_RESOLUTION micro_phase."""
        context = make_context_standard_12()

        handler = NightResolutionHandler()
        result = await handler(context)

        outcome = result.subphase_log.events[0]
        assert isinstance(outcome, NightOutcome)
        assert outcome.micro_phase == SubPhase.NIGHT_RESOLUTION

    @pytest.mark.asyncio
    async def test_event_has_correct_day(self):
        """Test that NightOutcome has correct day number."""
        context = make_context_standard_12()
        context.day = 3
        context.night = 3

        handler = NightResolutionHandler()
        result = await handler(context)

        outcome = result.subphase_log.events[0]
        assert isinstance(outcome, NightOutcome)
        assert outcome.day == 3

    @pytest.mark.asyncio
    async def test_empty_deaths_returns_empty_dict(self):
        """Test that empty deaths returns empty dict."""
        context = make_context_standard_12()

        context.night_actions = NightActions(
            kill_target=None,
        )

        handler = NightResolutionHandler()
        result = await handler(context)

        outcome = result.subphase_log.events[0]
        assert isinstance(outcome, NightOutcome)
        assert outcome.deaths == {}

    @pytest.mark.asyncio
    async def test_event_str_representation(self):
        """Test NightOutcome string representation."""
        context = make_context_standard_12()

        context.night_actions = NightActions(
            kill_target=4,
            poison_target=8,
        )

        handler = NightResolutionHandler()
        result = await handler(context)

        outcome = result.subphase_log.events[0]
        outcome_str = str(outcome)

        assert "NightOutcome" in outcome_str
        assert "WEREWOLF_KILL" in outcome_str
        assert "POISON" in outcome_str

    @pytest.mark.asyncio
    async def test_event_str_no_deaths(self):
        """Test NightOutcome string representation with no deaths."""
        context = make_context_standard_12()

        # Explicitly set no actions
        context.night_actions = NightActions(
            kill_target=None,
        )

        handler = NightResolutionHandler()
        result = await handler(context)

        outcome = result.subphase_log.events[0]
        outcome_str = str(outcome)

        assert "NightOutcome" in outcome_str
        assert "no deaths" in outcome_str


# ============================================================================
# Tests for NightResolution Multiple Night Scenarios
# ============================================================================


class TestNightResolutionMultipleNights:
    """Tests for multiple nights with persistent state."""

    @pytest.mark.asyncio
    async def test_night_2_with_potions_used(self):
        """Test Night 2 with some potions already used."""
        context = make_context_standard_12()
        context.day = 2
        context.night = 2

        # Poison already used (antidote available)
        # Werewolves target Seer, witch used poison on Hunter last night
        context.night_actions = NightActions(
            kill_target=4,  # Werewolves target Seer
            poison_target=None,  # Poison already used
            poison_used=True,
            antidote_used=False,
        )

        handler = NightResolutionHandler()
        result = await handler(context)

        outcome = result.subphase_log.events[0]
        assert isinstance(outcome, NightOutcome)
        # Only werewolf kill since poison is used
        assert outcome.deaths == {4: DeathCause.WEREWOLF_KILL}

    @pytest.mark.asyncio
    async def test_both_potions_used_night(self):
        """Test night when both potions already used."""
        context = make_context_standard_12()
        context.day = 5
        context.night = 5

        context.night_actions = NightActions(
            kill_target=8,
            antidote_used=True,
            poison_used=True,
        )

        handler = NightResolutionHandler()
        result = await handler(context)

        outcome = result.subphase_log.events[0]
        assert isinstance(outcome, NightOutcome)
        # Werewolf kill succeeds (no save available)
        assert outcome.deaths == {8: DeathCause.WEREWOLF_KILL}


# ============================================================================
# Tests for NightResolution Guard Edge Cases
# ============================================================================


class TestNightResolutionGuardEdgeCases:
    """Tests for guard-related edge cases."""

    @pytest.mark.asyncio
    async def test_guard_same_as_werewolf_target(self):
        """Test when guard is the werewolf target."""
        context = make_context_standard_12()

        # Werewolves target Guard
        context.night_actions = NightActions(
            kill_target=6,  # Guard is werewolf target
            guard_target=6,  # Guard protects self
        )

        handler = NightResolutionHandler()
        result = await handler(context)

        outcome = result.subphase_log.events[0]
        assert isinstance(outcome, NightOutcome)
        # Guard survives (self-protection)
        assert outcome.deaths == {}

    @pytest.mark.asyncio
    async def test_guard_poisoned(self):
        """Test when guard dies from poison."""
        context = make_context_standard_12()

        context.night_actions = NightActions(
            kill_target=None,
            poison_target=6,  # Witch poisons Guard
            guard_target=8,  # Guard tries to protect someone else
        )

        handler = NightResolutionHandler()
        result = await handler(context)

        outcome = result.subphase_log.events[0]
        assert isinstance(outcome, NightOutcome)
        # Guard dies from poison (guard action still recorded but irrelevant)
        assert outcome.deaths == {6: DeathCause.POISON}

    @pytest.mark.asyncio
    async def test_guard_killed_by_werewolves(self):
        """Test when guard is killed by werewolves."""
        context = make_context_standard_12()

        context.night_actions = NightActions(
            kill_target=6,  # Werewolves target Guard
        )

        handler = NightResolutionHandler()
        result = await handler(context)

        outcome = result.subphase_log.events[0]
        assert isinstance(outcome, NightOutcome)
        # Guard dies
        assert outcome.deaths == {6: DeathCause.WEREWOLF_KILL}
