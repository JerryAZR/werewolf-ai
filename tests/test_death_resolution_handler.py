"""Tests for DeathResolution handler.

Tests cover:
1. Night death with last words (Day 1)
2. Night death no last words (Day 2+)
3. Hunter killed by werewolf -> can shoot
4. Hunter poisoned -> cannot shoot
5. Sheriff dies -> badge transfer
6. Multiple deaths -> multiple DeathEvents
7. No deaths -> empty SubPhaseLog
"""

import pytest
from typing import Optional, Any
from unittest.mock import AsyncMock, MagicMock
from pydantic import BaseModel, Field

from werewolf.events import (
    DeathEvent,
    DeathCause,
    Phase,
    SubPhase,
    SubPhaseLog,
    NightOutcome,
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
        raise ValueError("MockParticipant: no response configured")


# ============================================================================
# PhaseContext Fixture Factory
# ============================================================================


class PhaseContext:
    """Minimal context for testing DeathResolution handler."""

    def __init__(
        self,
        players: dict[int, Player],
        living_players: set[int],
        dead_players: set[int],
        sheriff: Optional[int] = None,
        day: int = 1,
        night_deaths: Optional[dict[int, DeathCause]] = None,
        previous_day_deaths: Optional[list[int]] = None,
    ):
        self.players = players
        self.living_players = living_players
        self.dead_players = dead_players
        self.sheriff = sheriff
        self.day = day
        self.night_deaths = night_deaths or {}
        self.previous_day_deaths = previous_day_deaths or []

    def get_player(self, seat: int) -> Optional[Player]:
        return self.players.get(seat)

    def is_hunter(self, seat: int) -> bool:
        player = self.get_player(seat)
        return player is not None and player.role == Role.HUNTER

    def is_sheriff(self, seat: int) -> bool:
        return self.sheriff == seat

    def is_alive(self, seat: int) -> bool:
        return seat in self.living_players

    def was_killed_by_werewolf(self, seat: int) -> bool:
        return self.night_deaths.get(seat) == DeathCause.WEREWOLF_KILL

    def was_poisoned(self, seat: int) -> bool:
        return self.night_deaths.get(seat) == DeathCause.POISON


def make_context_standard_12() -> tuple[PhaseContext, dict[int, MockParticipant]]:
    """Create a standard 12-player game context."""
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
    return context, {}


def make_context_day_2() -> tuple[PhaseContext, dict[int, MockParticipant]]:
    """Create context for Day 2 (no last words)."""
    players = {
        0: Player(seat=0, name="W1", role=Role.WEREWOLF, is_alive=True),
        1: Player(seat=1, name="W2", role=Role.WEREWOLF, is_alive=True),
        4: Player(seat=4, name="Seer", role=Role.SEER, is_alive=True),
        5: Player(seat=5, name="Witch", role=Role.WITCH, is_alive=True),
        6: Player(seat=6, name="Guard", role=Role.GUARD, is_alive=True),
        7: Player(seat=7, name="Hunter", role=Role.HUNTER, is_alive=True),
        8: Player(seat=8, name="V1", role=Role.ORDINARY_VILLAGER, is_alive=True),
        9: Player(seat=9, name="V2", role=Role.ORDINARY_VILLAGER, is_alive=True),
    }
    living = {0, 1, 4, 5, 6, 7, 8, 9}
    dead = {2, 3, 10, 11}
    sheriff = None

    context = PhaseContext(players, living, dead, sheriff, day=2)
    return context, {}


def make_context_with_sheriff() -> tuple[PhaseContext, dict[int, MockParticipant]]:
    """Create context where sheriff is alive."""
    players = {
        0: Player(seat=0, name="W1", role=Role.WEREWOLF, is_alive=True),
        1: Player(seat=1, name="Sheriff", role=Role.ORDINARY_VILLAGER, is_alive=True),
        4: Player(seat=4, name="Seer", role=Role.SEER, is_alive=True),
        7: Player(seat=7, name="Hunter", role=Role.HUNTER, is_alive=True),
    }
    living = {0, 1, 4, 7}
    dead = {2, 3, 5, 6, 8, 9, 10, 11}
    sheriff = 1

    context = PhaseContext(players, living, dead, sheriff, day=1)
    return context, {}


# ============================================================================
# Handler Result Types
# ============================================================================


class HandlerResult(BaseModel):
    """Output from handlers."""

    subphase_log: SubPhaseLog
    debug_info: Optional[str] = None


# ============================================================================
# DeathResolution Handler Implementation
# ============================================================================


class DeathResolutionHandler:
    """Handler for DeathResolution subphase.

    Responsibilities:
    1. Process deaths from night phase
    2. Collect last words (Day 1 only)
    3. Handle hunter revenge (if killed by werewolves)
    4. Transfer sheriff badge if sheriff dies
    5. Return DeathEvent for each death

    Special Rules:
    - Night 1 deaths: have last words
    - Day 2+ deaths: no last words
    - Hunter killed by werewolf: can shoot one target
    - Hunter poisoned: cannot shoot (poison ignores revenge)
    - Sheriff dies: badge transfers to next living player by seat order
    """

    async def __call__(
        self,
        context: PhaseContext,
        participants: list[tuple[int, MockParticipant]],
        night_deaths: dict[int, DeathCause],
    ) -> HandlerResult:
        """Execute the DeathResolution subphase.

        Args:
            context: Game state with players, living/dead, sheriff
            participants: List of (seat, MockParticipant) for dying players who may act
            night_deaths: Dict of seat -> DeathCause from NightResolution

        Returns:
            HandlerResult with SubPhaseLog containing DeathEvent(s)
        """
        events = []

        # Sort deaths by seat number for consistent ordering
        sorted_deaths = sorted(night_deaths.items())

        for seat, cause in sorted_deaths:
            player = context.get_player(seat)
            if player is None:
                continue

            # Collect last words if Day 1
            last_words = None
            if context.day == 1:
                participant_lookup = dict(participants)
                participant = participant_lookup.get(seat)
                if participant:
                    last_words = await self._collect_last_words(
                        participant, seat, context
                    )

            # Hunter revenge: only if killed by werewolf (not poison)
            hunter_shoot_target = None
            if context.is_hunter(seat) and cause == DeathCause.WEREWOLF_KILL:
                participant_lookup = dict(participants)
                participant = participant_lookup.get(seat)
                if participant:
                    hunter_shoot_target = await self._get_hunter_shot(
                        participant, seat, context
                    )

            # Sheriff badge transfer
            badge_transfer_to = None
            if context.is_sheriff(seat):
                badge_transfer_to = self._get_badge_heir(context)

            # Create DeathEvent
            death_event = DeathEvent(
                actor=seat,
                cause=cause,
                last_words=last_words,
                hunter_shoot_target=hunter_shoot_target,
                badge_transfer_to=badge_transfer_to,
                day=context.day,
            )
            events.append(death_event)

        # Build debug info
        debug_info = self._build_debug_info(events)

        return HandlerResult(
            subphase_log=SubPhaseLog(
                micro_phase=SubPhase.DEATH_RESOLUTION,
                events=events,
            ),
            debug_info=debug_info,
        )

    async def _collect_last_words(
        self,
        participant: MockParticipant,
        seat: int,
        context: PhaseContext,
    ) -> str:
        """Collect last words from a dying player."""
        system = f"You are about to die on Night {context.day}. You may give your last words."
        user = "Enter your last words (or press Enter for none):"

        response = await participant.decide(system, user)
        return response.strip() if response.strip() else None

    async def _get_hunter_shot(
        self,
        participant: MockParticipant,
        seat: int,
        context: PhaseContext,
    ) -> Optional[int]:
        """Get hunter's revenge target (if any)."""
        # Build list of valid targets (living non-hunter players)
        living_non_hunter = [
            s for s in context.living_players
            if s != seat and not context.get_player(s).role == Role.HUNTER
        ]

        if not living_non_hunter:
            return None  # No one to shoot

        system = f"You are the Hunter and have been killed! You may shoot one player."
        user = f"Choose a target to shoot (seat number, or 'none' to skip):"

        response = await participant.decide(system, user)
        response = response.strip().lower()

        if response == "none" or response == "skip":
            return None

        try:
            target = int(response)
            if target in living_non_hunter:
                return target
        except ValueError:
            pass

        return None  # Invalid choice defaults to skip

    def _get_badge_heir(self, context: PhaseContext) -> Optional[int]:
        """Get next living player to receive sheriff badge (lowest seat wins ties).

        Excludes the dead sheriff from consideration.
        Returns None if no other players are alive.
        """
        living_players = sorted(context.living_players)
        # Filter out the dead sheriff (who is the current actor/dead player)
        other_living = [p for p in living_players if p != context.sheriff]
        if other_living:
            return other_living[0]
        return None  # No one else alive to receive badge

    def _build_debug_info(self, events: list[DeathEvent]) -> str:
        """Build debug info string."""
        if not events:
            return "no_deaths=true"

        death_strs = [f"{e.actor}({e.cause.value})" for e in events]
        return f"deaths={death_strs}"


# ============================================================================
# Tests for DeathResolution Handler
# ============================================================================


class TestDeathResolutionDay1:
    """Tests for Day 1 death resolution (with last words)."""

    @pytest.mark.asyncio
    async def test_night_death_with_last_words_day_1(self):
        """Test that Day 1 deaths have last words."""
        context, participants = make_context_standard_12()
        context.night_deaths = {8: DeathCause.WEREWOLF_KILL}
        participants[8] = MockParticipant("I saw the werewolves!")

        handler = DeathResolutionHandler()
        result = await handler(context, [(8, participants[8])], context.night_deaths)

        # Verify structure
        assert result.subphase_log.micro_phase == SubPhase.DEATH_RESOLUTION
        assert len(result.subphase_log.events) == 1

        death_event = result.subphase_log.events[0]
        assert isinstance(death_event, DeathEvent)
        assert death_event.actor == 8
        assert death_event.cause == DeathCause.WEREWOLF_KILL
        assert death_event.last_words == "I saw the werewolves!"
        assert death_event.day == 1

    @pytest.mark.asyncio
    async def test_night_death_empty_last_words_day_1(self):
        """Test that Day 1 deaths can have empty last words."""
        context, participants = make_context_standard_12()
        context.night_deaths = {4: DeathCause.WEREWOLF_KILL}
        participants[4] = MockParticipant("")  # Empty response

        handler = DeathResolutionHandler()
        result = await handler(context, [(4, participants[4])], context.night_deaths)

        death_event = result.subphase_log.events[0]
        assert death_event.last_words is None


class TestDeathResolutionDay2Plus:
    """Tests for Day 2+ death resolution (no last words)."""

    @pytest.mark.asyncio
    async def test_night_death_no_last_words_day_2(self):
        """Test that Day 2+ deaths do NOT have last words."""
        context, participants = make_context_day_2()
        context.night_deaths = {8: DeathCause.WEREWOLF_KILL}

        handler = DeathResolutionHandler()
        result = await handler(context, list(participants.items()), context.night_deaths)

        # Verify structure
        assert result.subphase_log.micro_phase == SubPhase.DEATH_RESOLUTION
        assert len(result.subphase_log.events) == 1

        death_event = result.subphase_log.events[0]
        assert isinstance(death_event, DeathEvent)
        assert death_event.actor == 8
        assert death_event.cause == DeathCause.WEREWOLF_KILL
        assert death_event.last_words is None  # No last words on Day 2+
        assert death_event.day == 2

    @pytest.mark.asyncio
    async def test_night_death_no_last_words_day_5(self):
        """Test that Day 5 deaths do NOT have last words."""
        context, participants = make_context_day_2()
        context.day = 5
        context.night_deaths = {9: DeathCause.POISON}

        handler = DeathResolutionHandler()
        result = await handler(context, [], context.night_deaths)

        death_event = result.subphase_log.events[0]
        assert death_event.last_words is None
        assert death_event.day == 5


class TestDeathResolutionHunterRevenge:
    """Tests for hunter revenge mechanic."""

    @pytest.mark.asyncio
    async def test_hunter_killed_by_werewolf_can_shoot(self):
        """Test hunter killed by werewolves can shoot revenge target."""
        context, participants = make_context_standard_12()
        context.night_deaths = {7: DeathCause.WEREWOLF_KILL}  # Hunter dies
        participants[7] = MockParticipant("0")  # Shoots werewolf 0

        handler = DeathResolutionHandler()
        result = await handler(context, [(7, participants[7])], context.night_deaths)

        assert len(result.subphase_log.events) == 1
        death_event = result.subphase_log.events[0]
        assert death_event.actor == 7
        assert death_event.cause == DeathCause.WEREWOLF_KILL
        assert death_event.hunter_shoot_target == 0  # Shot werewolf 0

    @pytest.mark.asyncio
    async def test_hunter_poisoned_cannot_shoot(self):
        """Test hunter killed by poison CANNOT shoot (poison ignores revenge)."""
        context, participants = make_context_standard_12()
        context.night_deaths = {7: DeathCause.POISON}  # Hunter poisoned
        participants[7] = MockParticipant("0")  # Tries to shoot

        handler = DeathResolutionHandler()
        result = await handler(context, [(7, participants[7])], context.night_deaths)

        death_event = result.subphase_log.events[0]
        assert death_event.hunter_shoot_target is None  # Cannot shoot when poisoned

    @pytest.mark.asyncio
    async def test_hunter_skips_shot(self):
        """Test hunter can choose to skip revenge shot."""
        context, participants = make_context_standard_12()
        context.night_deaths = {7: DeathCause.WEREWOLF_KILL}
        participants[7] = MockParticipant("none")  # Chooses to skip

        handler = DeathResolutionHandler()
        result = await handler(context, [(7, participants[7])], context.night_deaths)

        death_event = result.subphase_log.events[0]
        assert death_event.hunter_shoot_target is None  # Skipped

    @pytest.mark.asyncio
    async def test_hunter_shot_invalid_target_becomes_none(self):
        """Test hunter shooting invalid target defaults to None."""
        context, participants = make_context_standard_12()
        context.night_deaths = {7: DeathCause.WEREWOLF_KILL}
        participants[7] = MockParticipant("999")  # Invalid seat

        handler = DeathResolutionHandler()
        result = await handler(context, [(7, participants[7])], context.night_deaths)

        death_event = result.subphase_log.events[0]
        assert death_event.hunter_shoot_target is None  # Invalid = skip

    @pytest.mark.asyncio
    async def test_non_hunter_death_no_shoot_target(self):
        """Test non-hunter deaths do not have shoot target."""
        context, participants = make_context_standard_12()
        context.night_deaths = {8: DeathCause.WEREWOLF_KILL}  # Villager dies

        handler = DeathResolutionHandler()
        result = await handler(context, [], context.night_deaths)

        death_event = result.subphase_log.events[0]
        assert death_event.hunter_shoot_target is None


class TestDeathResolutionSheriffBadge:
    """Tests for sheriff badge transfer."""

    @pytest.mark.asyncio
    async def test_sheriff_dies_badge_transfers(self):
        """Test sheriff death transfers badge to next living player."""
        context, participants = make_context_with_sheriff()
        context.night_deaths = {1: DeathCause.WEREWOLF_KILL}  # Sheriff dies

        handler = DeathResolutionHandler()
        result = await handler(context, [], context.night_deaths)

        assert len(result.subphase_log.events) == 1
        death_event = result.subphase_log.events[0]
        assert death_event.actor == 1
        assert death_event.cause == DeathCause.WEREWOLF_KILL
        assert death_event.badge_transfer_to == 0  # Lowest living seat

    @pytest.mark.asyncio
    async def test_sheriff_hunter_dies_badge_and_revenge(self):
        """Test sheriff who is hunter: badge transfer AND revenge."""
        players = {
            0: Player(seat=0, name="W1", role=Role.WEREWOLF, is_alive=True),
            5: Player(seat=5, name="SheriffHunter", role=Role.HUNTER, is_alive=True),
            7: Player(seat=7, name="V1", role=Role.ORDINARY_VILLAGER, is_alive=True),
        }
        living = {0, 5, 7}
        dead = {1, 2, 3, 4, 6, 8, 9, 10, 11}
        sheriff = 5

        context = PhaseContext(players, living, dead, sheriff, day=1)
        context.night_deaths = {5: DeathCause.WEREWOLF_KILL}
        participants = {5: MockParticipant("0")}  # Shoots werewolf 0

        handler = DeathResolutionHandler()
        result = await handler(
            context, [(5, participants[5])], context.night_deaths
        )

        death_event = result.subphase_log.events[0]
        assert death_event.hunter_shoot_target == 0
        assert death_event.badge_transfer_to == 0  # Lowest living player (werewolf in this case)

    @pytest.mark.asyncio
    async def test_non_sheriff_death_no_badge_transfer(self):
        """Test non-sheriff deaths do not transfer badge."""
        context, participants = make_context_standard_12()
        context.sheriff = 4  # Seer is sheriff
        context.night_deaths = {8: DeathCause.WEREWOLF_KILL}  # Villager dies

        handler = DeathResolutionHandler()
        result = await handler(context, [], context.night_deaths)

        death_event = result.subphase_log.events[0]
        assert death_event.badge_transfer_to is None

    @pytest.mark.asyncio
    async def test_last_sheriff_dies_no_badge_transfer(self):
        """Test when sheriff dies and no one else is alive."""
        players = {
            0: Player(seat=0, name="Sheriff", role=Role.ORDINARY_VILLAGER, is_alive=True),
        }
        living = {0}
        dead = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11}
        sheriff = 0

        context = PhaseContext(players, living, dead, sheriff, day=1)
        context.night_deaths = {0: DeathCause.WEREWOLF_KILL}

        handler = DeathResolutionHandler()
        result = await handler(context, [], context.night_deaths)

        death_event = result.subphase_log.events[0]
        assert death_event.badge_transfer_to is None


class TestDeathResolutionMultipleDeaths:
    """Tests for handling multiple deaths."""

    @pytest.mark.asyncio
    async def test_multiple_night_deaths_multiple_events(self):
        """Test multiple deaths create multiple DeathEvents."""
        context, participants = make_context_standard_12()
        context.night_deaths = {
            4: DeathCause.WEREWOLF_KILL,  # Seer
            8: DeathCause.WEREWOLF_KILL,  # Villager
        }

        handler = DeathResolutionHandler()
        result = await handler(context, [], context.night_deaths)

        assert len(result.subphase_log.events) == 2

        # Verify both deaths are recorded
        actors = {e.actor for e in result.subphase_log.events}
        assert actors == {4, 8}

    @pytest.mark.asyncio
    async def test_multiple_deaths_sorted_by_seat(self):
        """Test multiple deaths are sorted by seat number."""
        context, participants = make_context_standard_12()
        context.night_deaths = {
            8: DeathCause.WEREWOLF_KILL,
            4: DeathCause.WEREWOLF_KILL,
            10: DeathCause.WEREWOLF_KILL,
        }

        handler = DeathResolutionHandler()
        result = await handler(context, [], context.night_deaths)

        # Events should be sorted by seat (4, 8, 10)
        actors = [e.actor for e in result.subphase_log.events]
        assert actors == [4, 8, 10]

    @pytest.mark.asyncio
    async def test_mixed_death_causes(self):
        """Test deaths with different causes."""
        context, participants = make_context_standard_12()
        context.night_deaths = {
            4: DeathCause.WEREWOLF_KILL,
            7: DeathCause.POISON,
        }

        handler = DeathResolutionHandler()
        result = await handler(context, [], context.night_deaths)

        causes = {e.cause for e in result.subphase_log.events}
        assert causes == {DeathCause.WEREWOLF_KILL, DeathCause.POISON}


class TestDeathResolutionNoDeaths:
    """Tests for scenarios with no deaths."""

    @pytest.mark.asyncio
    async def test_no_deaths_empty_subphase_log(self):
        """Test that no deaths result in empty SubPhaseLog."""
        context, participants = make_context_standard_12()
        context.night_deaths = {}

        handler = DeathResolutionHandler()
        result = await handler(context, [], context.night_deaths)

        assert result.subphase_log.micro_phase == SubPhase.DEATH_RESOLUTION
        assert len(result.subphase_log.events) == 0
        assert result.debug_info == "no_deaths=true"

    @pytest.mark.asyncio
    async def test_no_night_deaths_with_living_players(self):
        """Test no deaths when all protected successfully."""
        players = {
            0: Player(seat=0, name="W1", role=Role.WEREWOLF, is_alive=True),
            4: Player(seat=4, name="Seer", role=Role.SEER, is_alive=True),
        }
        living = {0, 4}
        dead = {1, 2, 3, 5, 6, 7, 8, 9, 10, 11}

        context = PhaseContext(players, living, dead, sheriff=None, day=2)
        context.night_deaths = {}  # All protected

        handler = DeathResolutionHandler()
        result = await handler(context, [], context.night_deaths)

        assert len(result.subphase_log.events) == 0


class TestDeathResolutionEdgeCases:
    """Tests for edge cases in death resolution."""

    @pytest.mark.asyncio
    async def test_hunter_only_surviving_player(self):
        """Test hunter death when they are the last player."""
        players = {
            7: Player(seat=7, name="Hunter", role=Role.HUNTER, is_alive=True),
        }
        living = {7}
        dead = {0, 1, 2, 3, 4, 5, 6, 8, 9, 10, 11}

        context = PhaseContext(players, living, dead, sheriff=None, day=1)
        context.night_deaths = {7: DeathCause.WEREWOLF_KILL}
        participants = {7: MockParticipant("none")}

        handler = DeathResolutionHandler()
        result = await handler(context, [(7, participants[7])], context.night_deaths)

        death_event = result.subphase_log.events[0]
        assert death_event.hunter_shoot_target is None  # No valid targets

    @pytest.mark.asyncio
    async def test_day_1_with_multiple_hunters_dying(self):
        """Test multiple deaths including hunters on Day 1."""
        players = {
            0: Player(seat=0, name="W1", role=Role.WEREWOLF, is_alive=True),
            7: Player(seat=7, name="Hunter1", role=Role.HUNTER, is_alive=True),
            11: Player(seat=11, name="Hunter2", role=Role.HUNTER, is_alive=True),
        }
        living = {0, 7, 11}
        dead = {1, 2, 3, 4, 5, 6, 8, 9, 10}

        context = PhaseContext(players, living, dead, sheriff=None, day=1)
        context.night_deaths = {
            7: DeathCause.WEREWOLF_KILL,
            11: DeathCause.POISON,
        }
        participants = {
            7: MockParticipant("0"),  # Hunter1 shoots werewolf
            11: MockParticipant("0"),  # Hunter2 cannot shoot (poison)
        }

        handler = DeathResolutionHandler()
        result = await handler(
            context, [(7, participants[7]), (11, participants[11])], context.night_deaths
        )

        assert len(result.subphase_log.events) == 2

        # Find each death event
        hunter1_event = next(e for e in result.subphase_log.events if e.actor == 7)
        hunter2_event = next(e for e in result.subphase_log.events if e.actor == 11)

        assert hunter1_event.hunter_shoot_target == 0  # Can shoot
        assert hunter2_event.hunter_shoot_target is None  # Poisoned

    @pytest.mark.asyncio
    async def test_banishment_death(self):
        """Test death by banishment (day voting)."""
        context, participants = make_context_standard_12()
        context.night_deaths = {5: DeathCause.BANISHMENT}

        handler = DeathResolutionHandler()
        result = await handler(context, [], context.night_deaths)

        death_event = result.subphase_log.events[0]
        assert death_event.cause == DeathCause.BANISHMENT
        # Banishment is always during day, no last words even on Day 1
        # (or maybe yes, depending on rules - typically banishment doesn't give last words)
        assert death_event.last_words is None


# ============================================================================
# Integration Tests
# ============================================================================


class TestDeathResolutionIntegration:
    """Integration tests simulating complete death resolution scenarios."""

    @pytest.mark.asyncio
    async def test_complete_night_1_death_scenario(self):
        """Test complete Night 1 death resolution with all features."""
        players = {
            0: Player(seat=0, name="W1", role=Role.WEREWOLF, is_alive=True),
            1: Player(seat=1, name="W2", role=Role.WEREWOLF, is_alive=True),
            4: Player(seat=4, name="Seer", role=Role.SEER, is_alive=True),
            7: Player(seat=7, name="Hunter", role=Role.HUNTER, is_alive=True),
            8: Player(seat=8, name="V1", role=Role.ORDINARY_VILLAGER, is_alive=True),
        }
        living = {0, 1, 4, 7, 8}
        dead = {2, 3, 5, 6, 9, 10, 11}
        sheriff = None

        context = PhaseContext(players, living, dead, sheriff, day=1)
        context.night_deaths = {
            7: DeathCause.WEREWOLF_KILL,  # Hunter killed
            8: DeathCause.POISON,  # Villager poisoned
        }
        participants = {
            7: MockParticipant("I shoot werewolf 0!"),  # Hunter with last words and shot
            8: MockParticipant(""),  # Empty last words
        }

        handler = DeathResolutionHandler()
        result = await handler(
            context,
            [(7, participants[7]), (8, participants[8])],
            context.night_deaths
        )

        # Verify 2 death events
        assert len(result.subphase_log.events) == 2

        # Hunter event
        hunter_event = next(e for e in result.subphase_log.events if e.actor == 7)
        assert hunter_event.last_words == "I shoot werewolf 0!"
        assert hunter_event.hunter_shoot_target is None  # Invalid seat = skip
        assert hunter_event.cause == DeathCause.WEREWOLF_KILL

        # Poisoned villager event
        villager_event = next(e for e in result.subphase_log.events if e.actor == 8)
        assert villager_event.last_words is None
        assert villager_event.hunter_shoot_target is None
        assert villager_event.cause == DeathCause.POISON

    @pytest.mark.asyncio
    async def test_complete_night_3_scenario(self):
        """Test complete Night 3 death resolution (no last words)."""
        players = {
            0: Player(seat=0, name="W1", role=Role.WEREWOLF, is_alive=True),
            1: Player(seat=1, name="Sheriff", role=Role.ORDINARY_VILLAGER, is_alive=True),
            4: Player(seat=4, name="Seer", role=Role.SEER, is_alive=True),
        }
        living = {0, 1, 4}
        dead = {2, 3, 5, 6, 7, 8, 9, 10, 11}
        sheriff = 1

        context = PhaseContext(players, living, dead, sheriff, day=3)
        context.night_deaths = {
            1: DeathCause.WEREWOLF_KILL,  # Sheriff killed
            4: DeathCause.WEREWOLF_KILL,  # Seer killed
        }

        handler = DeathResolutionHandler()
        result = await handler(context, [], context.night_deaths)

        assert len(result.subphase_log.events) == 2

        # Sheriff event with badge transfer
        sheriff_event = next(e for e in result.subphase_log.events if e.actor == 1)
        assert sheriff_event.last_words is None  # Day 3 = no last words
        assert sheriff_event.badge_transfer_to == 0  # Next living player

        # Seer event
        seer_event = next(e for e in result.subphase_log.events if e.actor == 4)
        assert seer_event.last_words is None
        assert seer_event.badge_transfer_to is None
