"""Tests for BanishmentResolution handler.

Tests cover:
1. No banished (tie) -> empty SubPhaseLog
2. Banished player with last words
3. Hunter banished -> can shoot
4. Sheriff banished -> badge transfer (player choice)
5. Hunter+Sheriff banished -> both shoot and badge
6. Various roles with appropriate last words
7. Edge cases (no living players, etc.)
8. StubPlayer integration - handler passes choices correctly
"""

import pytest
from typing import Optional, Any
from unittest.mock import patch
import random

from werewolf.events.game_events import (
    DeathEvent,
    DeathCause,
    Phase,
    SubPhase,
)
from werewolf.handlers.banishment_resolution_handler import (
    BanishmentResolutionHandler,
    BanishmentInput,
    SubPhaseLog,
    HandlerResult,
)
from werewolf.models.player import Player, Role
from werewolf.ai.stub_ai import StubPlayer


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
        hint: Optional[str] = None,
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
    """Minimal context for testing BanishmentResolution handler."""

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
        return self.players.get(seat)

    def is_hunter(self, seat: int) -> bool:
        player = self.get_player(seat)
        return player is not None and player.role == Role.HUNTER

    def is_sheriff(self, seat: int) -> bool:
        return self.sheriff == seat

    def is_alive(self, seat: int) -> bool:
        return seat in self.living_players

    def is_werewolf(self, seat: int) -> bool:
        player = self.get_player(seat)
        return player is not None and player.role == Role.WEREWOLF


def make_context_standard_12() -> PhaseContext:
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

    return PhaseContext(players, living, dead, sheriff=None, day=1)


def make_context_day_3() -> PhaseContext:
    """Create context for Day 3."""
    players = {
        0: Player(seat=0, name="W1", role=Role.WEREWOLF, is_alive=True),
        1: Player(seat=1, name="W2", role=Role.WEREWOLF, is_alive=True),
        4: Player(seat=4, name="Seer", role=Role.SEER, is_alive=True),
        7: Player(seat=7, name="Hunter", role=Role.HUNTER, is_alive=True),
        8: Player(seat=8, name="V1", role=Role.ORDINARY_VILLAGER, is_alive=True),
    }
    living = {0, 1, 4, 7, 8}
    dead = {2, 3, 5, 6, 9, 10, 11}

    return PhaseContext(players, living, dead, sheriff=None, day=3)


def make_context_with_sheriff() -> PhaseContext:
    """Create context where sheriff is seat 4 (Seer)."""
    players = {
        0: Player(seat=0, name="W1", role=Role.WEREWOLF, is_alive=True),
        1: Player(seat=1, name="W2", role=Role.WEREWOLF, is_alive=True),
        4: Player(seat=4, name="Seer", role=Role.SEER, is_alive=True, is_sheriff=True),
        7: Player(seat=7, name="Hunter", role=Role.HUNTER, is_alive=True),
        8: Player(seat=8, name="V1", role=Role.ORDINARY_VILLAGER, is_alive=True),
    }
    living = {0, 1, 4, 7, 8}
    dead = {2, 3, 5, 6, 9, 10, 11}
    sheriff = 4

    return PhaseContext(players, living, dead, sheriff=sheriff, day=2)


# ============================================================================
# Tests for No Banishment (Tie)
# ============================================================================


class TestBanishmentResolutionNoBanishment:
    """Tests for scenarios with no banishment (tie in voting)."""

    @pytest.mark.asyncio
    async def test_no_banished_empty_subphase_log(self):
        """Test that no banishment results in empty SubPhaseLog."""
        context = make_context_standard_12()
        banishment_input = BanishmentInput(day=1, banished=None)

        handler = BanishmentResolutionHandler()
        result = await handler(context, banishment_input)

        assert result.subphase_log.micro_phase == SubPhase.BANISHMENT_RESOLUTION
        assert len(result.subphase_log.events) == 0
        assert result.debug_info == "No banishment (tie or no votes)"

    @pytest.mark.asyncio
    async def test_no_banished_tie_voting(self):
        """Test tie voting results in no banishment."""
        context = make_context_standard_12()
        # Day 5 with a tie
        banishment_input = BanishmentInput(day=5, banished=None)

        handler = BanishmentResolutionHandler()
        result = await handler(context, banishment_input)

        assert len(result.subphase_log.events) == 0
        assert "tie" in result.debug_info.lower() or "no votes" in result.debug_info.lower()


# ============================================================================
# Tests for Last Words
# ============================================================================


class TestBanishmentResolutionLastWords:
    """Tests for last words on banishment (always required unlike night deaths)."""

    @pytest.mark.asyncio
    async def test_banished_player_with_last_words(self):
        """Test banished player always has last words (Day 1)."""
        context = make_context_standard_12()
        banishment_input = BanishmentInput(day=1, banished=8)  # Villager

        handler = BanishmentResolutionHandler()
        result = await handler(context, banishment_input)

        assert len(result.subphase_log.events) == 1

        death_event = result.subphase_log.events[0]
        assert isinstance(death_event, DeathEvent)
        assert death_event.actor == 8
        assert death_event.cause == DeathCause.BANISHMENT
        assert death_event.last_words is not None
        assert len(death_event.last_words) > 0

    @pytest.mark.asyncio
    async def test_banished_player_last_words_day_3(self):
        """Test banished player has last words on Day 3."""
        context = make_context_day_3()
        banishment_input = BanishmentInput(day=3, banished=8)  # Villager

        handler = BanishmentResolutionHandler()
        result = await handler(context, banishment_input)

        death_event = result.subphase_log.events[0]
        # Unlike night deaths, day deaths ALWAYS have last words
        assert death_event.last_words is not None
        assert death_event.day == 3

    @pytest.mark.asyncio
    async def test_seer_last_words(self):
        """Test Seer has appropriate last words when banished."""
        context = make_context_standard_12()
        banishment_input = BanishmentInput(day=2, banished=4)  # Seer

        handler = BanishmentResolutionHandler()
        result = await handler(context, banishment_input)

        death_event = result.subphase_log.events[0]
        assert "Seer" in death_event.last_words

    @pytest.mark.asyncio
    async def test_werewolf_last_words(self):
        """Test Werewolf has appropriate last words when banished."""
        context = make_context_standard_12()
        banishment_input = BanishmentInput(day=2, banished=0)  # Werewolf

        handler = BanishmentResolutionHandler()
        result = await handler(context, banishment_input)

        death_event = result.subphase_log.events[0]
        assert death_event.last_words is not None
        assert len(death_event.last_words) > 0

    @pytest.mark.asyncio
    async def test_witch_last_words(self):
        """Test Witch has appropriate last words when banished."""
        context = make_context_standard_12()
        banishment_input = BanishmentInput(day=2, banished=5)  # Witch

        handler = BanishmentResolutionHandler()
        result = await handler(context, banishment_input)

        death_event = result.subphase_log.events[0]
        assert "Witch" in death_event.last_words

    @pytest.mark.asyncio
    async def test_guard_last_words(self):
        """Test Guard has appropriate last words when banished."""
        context = make_context_standard_12()
        banishment_input = BanishmentInput(day=2, banished=6)  # Guard

        handler = BanishmentResolutionHandler()
        result = await handler(context, banishment_input)

        death_event = result.subphase_log.events[0]
        assert "Guard" in death_event.last_words


# ============================================================================
# Tests for Hunter Shoot on Banishment
# ============================================================================


class TestBanishmentResolutionHunterShoot:
    """Tests for hunter revenge on banishment."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("random_seed", [0.0, 0.25, 0.75, 1.0])
    async def test_hunter_banished_can_shoot(self, random_seed):
        """Test hunter banished can shoot a target."""
        context = make_context_standard_12()
        banishment_input = BanishmentInput(day=2, banished=7)  # Hunter

        with patch("random.random", return_value=random_seed):
            # Force hunter to shoot a werewolf by setting random to favor shooting
            with patch.object(random, 'random', return_value=0.1):
                handler = BanishmentResolutionHandler()
                result = await handler(context, banishment_input)

        death_event = result.subphase_log.events[0]
        assert death_event.actor == 7
        assert death_event.cause == DeathCause.BANISHMENT

        # Hunter should have a shoot target (either a werewolf or random)
        # The handler prefers werewolves
        assert death_event.hunter_shoot_target is not None
        # The target should be a living player
        assert death_event.hunter_shoot_target in context.living_players

    @pytest.mark.asyncio
    async def test_non_hunter_banished_no_shoot_target(self):
        """Test non-hunter banished does not have shoot target."""
        context = make_context_standard_12()
        banishment_input = BanishmentInput(day=2, banished=8)  # Villager

        handler = BanishmentResolutionHandler()
        result = await handler(context, banishment_input)

        death_event = result.subphase_log.events[0]
        assert death_event.hunter_shoot_target is None

    @pytest.mark.asyncio
    async def test_hunter_banished_prefers_werewolf_target(self):
        """Test hunter prefers to shoot werewolf when banished."""
        players = {
            0: Player(seat=0, name="W1", role=Role.WEREWOLF, is_alive=True),
            1: Player(seat=1, name="W2", role=Role.WEREWOLF, is_alive=True),
            7: Player(seat=7, name="Hunter", role=Role.HUNTER, is_alive=True),
            8: Player(seat=8, name="V1", role=Role.ORDINARY_VILLAGER, is_alive=True),
        }
        living = {0, 1, 7, 8}
        dead = {2, 3, 4, 5, 6, 9, 10, 11}

        context = PhaseContext(players, living, dead, sheriff=None, day=2)
        banishment_input = BanishmentInput(day=2, banished=7)  # Hunter

        with patch.object(random, 'random', return_value=0.0):  # Force shooting
            handler = BanishmentResolutionHandler()
            result = await handler(context, banishment_input)

        death_event = result.subphase_log.events[0]
        # Hunter should shoot a werewolf (lowest seat werewolf is 0)
        assert death_event.hunter_shoot_target in {0, 1}

    @pytest.mark.asyncio
    async def test_hunter_banished_last_words(self):
        """Test hunter has appropriate last words when banished."""
        context = make_context_standard_12()
        banishment_input = BanishmentInput(day=2, banished=7)  # Hunter

        handler = BanishmentResolutionHandler()
        result = await handler(context, banishment_input)

        death_event = result.subphase_log.events[0]
        assert "Hunter" in death_event.last_words


# ============================================================================
# Tests for Sheriff Badge Transfer
# ============================================================================


class TestBanishmentResolutionSheriffBadge:
    """Tests for sheriff badge transfer on banishment (player choice)."""

    @pytest.mark.asyncio
    async def test_sheriff_banished_badge_transfers(self):
        """Test sheriff banishment transfers badge (uses template fallback)."""
        context = make_context_with_sheriff()
        banishment_input = BanishmentInput(day=2, banished=4)  # Seer is sheriff

        handler = BanishmentResolutionHandler()
        result = await handler(context, banishment_input)

        assert len(result.subphase_log.events) == 1

        death_event = result.subphase_log.events[0]
        assert death_event.actor == 4
        assert death_event.cause == DeathCause.BANISHMENT
        # Badge transfers to lowest living non-sheriff player
        assert death_event.badge_transfer_to is not None
        assert death_event.badge_transfer_to in context.living_players
        assert death_event.badge_transfer_to != 4  # Not the dead sheriff

    @pytest.mark.asyncio
    async def test_sheriff_banished_with_participant_chooses(self):
        """Test sheriff with participant can choose badge heir."""
        context = make_context_with_sheriff()
        banishment_input = BanishmentInput(day=2, banished=4)  # Seer is sheriff

        # Sheriff chooses seat 8 (Villager) - a valid living player
        sheriff = MockParticipant(response="8")

        handler = BanishmentResolutionHandler()
        result = await handler(context, banishment_input, participant=sheriff)

        death_event = result.subphase_log.events[0]
        # Sheriff should choose seat 8 (Villager, living)
        assert death_event.badge_transfer_to == 8

    @pytest.mark.asyncio
    async def test_sheriff_can_skip_badge_transfer(self):
        """Test sheriff can choose to skip badge transfer."""
        context = make_context_with_sheriff()
        banishment_input = BanishmentInput(day=2, banished=4)  # Seer is sheriff

        sheriff = MockParticipant(response="SKIP")

        handler = BanishmentResolutionHandler()
        result = await handler(context, banishment_input, participant=sheriff)

        death_event = result.subphase_log.events[0]
        assert death_event.badge_transfer_to is None

    @pytest.mark.asyncio
    async def test_non_sheriff_banished_no_badge_transfer(self):
        """Test non-sheriff banishment does not transfer badge."""
        players = {
            0: Player(seat=0, name="W1", role=Role.WEREWOLF, is_alive=True),
            1: Player(seat=1, name="W2", role=Role.WEREWOLF, is_alive=True),
            4: Player(seat=4, name="Seer", role=Role.SEER, is_alive=True, is_sheriff=True),
            7: Player(seat=7, name="Hunter", role=Role.HUNTER, is_alive=True),
            8: Player(seat=8, name="V1", role=Role.ORDINARY_VILLAGER, is_alive=True),
        }
        living = {0, 1, 4, 7, 8}
        dead = {2, 3, 5, 6, 9, 10, 11}

        context = PhaseContext(players, living, dead, sheriff=4, day=2)
        banishment_input = BanishmentInput(day=2, banished=8)  # Villager

        handler = BanishmentResolutionHandler()
        result = await handler(context, banishment_input)

        death_event = result.subphase_log.events[0]
        assert death_event.badge_transfer_to is None

    @pytest.mark.asyncio
    async def test_sheriff_banished_no_trusted_heir(self):
        """Test sheriff banished when all trusted players are dead."""
        players = {
            0: Player(seat=0, name="W1", role=Role.WEREWOLF, is_alive=True),
            1: Player(seat=1, name="W2", role=Role.WEREWOLF, is_alive=True),
            4: Player(seat=4, name="Sheriff", role=Role.ORDINARY_VILLAGER, is_alive=True, is_sheriff=True),
        }
        living = {0, 1, 4}
        dead = {2, 3, 5, 6, 7, 8, 9, 10, 11}
        sheriff = 4

        context = PhaseContext(players, living, dead, sheriff=sheriff, day=3)
        banishment_input = BanishmentInput(day=3, banished=4)  # Sheriff

        handler = BanishmentResolutionHandler()
        result = await handler(context, banishment_input)

        death_event = result.subphase_log.events[0]
        # All living are werewolves, so badge transfer skipped (template fallback)
        assert death_event.badge_transfer_to is None


# ============================================================================
# Tests for Hunter + Sheriff Combined
# ============================================================================


class TestBanishmentResolutionHunterSheriff:
    """Tests for player who is both Hunter and Sheriff."""

    @pytest.mark.asyncio
    async def test_hunter_sheriff_banished_both_shoot_and_badge(self):
        """Test Hunter+Sheriff banished can shoot AND transfer badge."""
        players = {
            0: Player(seat=0, name="W1", role=Role.WEREWOLF, is_alive=True),
            1: Player(seat=1, name="W2", role=Role.WEREWOLF, is_alive=True),
            5: Player(seat=5, name="HunterSheriff", role=Role.HUNTER, is_alive=True, is_sheriff=True),
            7: Player(seat=7, name="V1", role=Role.ORDINARY_VILLAGER, is_alive=True),
        }
        living = {0, 1, 5, 7}
        dead = {2, 3, 4, 6, 8, 9, 10, 11}
        sheriff = 5  # Hunter is also sheriff

        context = PhaseContext(players, living, dead, sheriff=sheriff, day=2)
        banishment_input = BanishmentInput(day=2, banished=5)

        with patch.object(random, 'random', return_value=0.0):  # Force shooting
            handler = BanishmentResolutionHandler()
            result = await handler(context, banishment_input)

        death_event = result.subphase_log.events[0]
        assert death_event.actor == 5
        assert death_event.cause == DeathCause.BANISHMENT

        # Both actions should be present
        assert death_event.hunter_shoot_target is not None  # Can shoot
        assert death_event.badge_transfer_to is not None  # Badge transfers


# ============================================================================
# Tests for Role-Specific Behaviors
# ============================================================================


class TestBanishmentResolutionRoleBehaviors:
    """Tests for role-specific behaviors on banishment."""

    @pytest.mark.asyncio
    async def test_werewolf_banished(self):
        """Test werewolf banishment."""
        context = make_context_standard_12()
        banishment_input = BanishmentInput(day=2, banished=0)  # Werewolf

        handler = BanishmentResolutionHandler()
        result = await handler(context, banishment_input)

        death_event = result.subphase_log.events[0]
        assert death_event.actor == 0
        assert death_event.cause == DeathCause.BANISHMENT
        assert death_event.last_words is not None
        assert "wolf" in death_event.last_words.lower() or len(death_event.last_words) > 0

    @pytest.mark.asyncio
    async def test_villager_banished(self):
        """Test ordinary villager banishment."""
        context = make_context_standard_12()
        banishment_input = BanishmentInput(day=2, banished=8)  # Villager

        handler = BanishmentResolutionHandler()
        result = await handler(context, banishment_input)

        death_event = result.subphase_log.events[0]
        assert death_event.actor == 8
        assert death_event.cause == DeathCause.BANISHMENT
        assert death_event.last_words is not None

    @pytest.mark.asyncio
    async def test_all_roles_banished_have_last_words(self):
        """Test that all roles have last words when banished."""
        roles_to_test = [
            (4, Role.SEER),
            (5, Role.WITCH),
            (6, Role.GUARD),
            (7, Role.HUNTER),
            (0, Role.WEREWOLF),
            (8, Role.ORDINARY_VILLAGER),
        ]

        context = make_context_standard_12()

        for seat, role in roles_to_test:
            banishment_input = BanishmentInput(day=2, banished=seat)

            handler = BanishmentResolutionHandler()
            result = await handler(context, banishment_input)

            death_event = result.subphase_log.events[0]
            assert death_event.last_words is not None, f"{role} should have last words"


# ============================================================================
# Tests for Debug Info
# ============================================================================


class TestBanishmentResolutionDebugInfo:
    """Tests for debug info generation."""

    @pytest.mark.asyncio
    async def test_debug_info_contains_banished_seat(self):
        """Test debug info contains the banished seat."""
        context = make_context_standard_12()
        banishment_input = BanishmentInput(day=2, banished=8)

        handler = BanishmentResolutionHandler()
        result = await handler(context, banishment_input)

        assert "banished=8" in result.debug_info

    @pytest.mark.asyncio
    async def test_debug_info_contains_last_words_flag(self):
        """Test debug info contains last words flag."""
        context = make_context_standard_12()
        banishment_input = BanishmentInput(day=2, banished=8)

        handler = BanishmentResolutionHandler()
        result = await handler(context, banishment_input)

        assert "last_words=" in result.debug_info

    @pytest.mark.asyncio
    async def test_debug_info_contains_hunter_shoot(self):
        """Test debug info contains hunter shoot info."""
        context = make_context_standard_12()
        banishment_input = BanishmentInput(day=2, banished=7)  # Hunter

        with patch.object(random, 'random', return_value=0.0):
            handler = BanishmentResolutionHandler()
            result = await handler(context, banishment_input)

        assert "hunter_shoot=" in result.debug_info

    @pytest.mark.asyncio
    async def test_debug_info_contains_badge_transfer(self):
        """Test debug info contains badge transfer info."""
        context = make_context_with_sheriff()
        banishment_input = BanishmentInput(day=2, banished=4)  # Sheriff

        handler = BanishmentResolutionHandler()
        result = await handler(context, banishment_input)

        assert "badge_transfer=" in result.debug_info


# ============================================================================
# Edge Cases
# ============================================================================


class TestBanishmentResolutionEdgeCases:
    """Tests for edge cases in banishment resolution."""

    @pytest.mark.asyncio
    async def test_banished_player_not_in_players_dict(self):
        """Test handling of banished player not in players dict."""
        context = make_context_standard_12()
        banishment_input = BanishmentInput(day=2, banished=999)  # Invalid seat

        handler = BanishmentResolutionHandler()
        result = await handler(context, banishment_input)

        # Should still create an event (with empty last words)
        assert len(result.subphase_log.events) == 1
        death_event = result.subphase_log.events[0]
        assert death_event.actor == 999

    @pytest.mark.asyncio
    async def test_banished_last_player(self):
        """Test banishment when only one player is left."""
        players = {
            7: Player(seat=7, name="Hunter", role=Role.HUNTER, is_alive=True),
        }
        living = {7}
        dead = {0, 1, 2, 3, 4, 5, 6, 8, 9, 10, 11}

        context = PhaseContext(players, living, dead, sheriff=None, day=5)
        banishment_input = BanishmentInput(day=5, banished=7)  # Last player

        handler = BanishmentResolutionHandler()
        result = await handler(context, banishment_input)

        death_event = result.subphase_log.events[0]
        # No one to shoot
        assert death_event.hunter_shoot_target is None
        # Has last words
        assert death_event.last_words is not None

    @pytest.mark.asyncio
    async def test_banished_sheriff_last_player(self):
        """Test sheriff banishment when only sheriff is left."""
        players = {
            4: Player(seat=4, name="Sheriff", role=Role.SEER, is_alive=True, is_sheriff=True),
        }
        living = {4}
        dead = {0, 1, 2, 3, 5, 6, 7, 8, 9, 10, 11}

        context = PhaseContext(players, living, dead, sheriff=4, day=5)
        banishment_input = BanishmentInput(day=5, banished=4)

        handler = BanishmentResolutionHandler()
        result = await handler(context, banishment_input)

        death_event = result.subphase_log.events[0]
        # No one to transfer badge to
        assert death_event.badge_transfer_to is None

    @pytest.mark.asyncio
    async def test_banished_hunter_only_werewolf_survives(self):
        """Test hunter banished when only werewolves survive."""
        players = {
            0: Player(seat=0, name="W1", role=Role.WEREWOLF, is_alive=True),
            7: Player(seat=7, name="Hunter", role=Role.HUNTER, is_alive=True),
        }
        living = {0, 7}
        dead = {1, 2, 3, 4, 5, 6, 8, 9, 10, 11}

        context = PhaseContext(players, living, dead, sheriff=None, day=3)
        banishment_input = BanishmentInput(day=3, banished=7)

        with patch.object(random, 'random', return_value=0.0):
            handler = BanishmentResolutionHandler()
            result = await handler(context, banishment_input)

        death_event = result.subphase_log.events[0]
        # Hunter can still shoot even if only werewolves remain
        assert death_event.hunter_shoot_target == 0


# ============================================================================
# Integration Tests
# ============================================================================


class TestBanishmentResolutionIntegration:
    """Integration tests simulating complete banishment scenarios."""

    @pytest.mark.asyncio
    async def test_complete_day_2_banishment(self):
        """Test complete Day 2 banishment scenario."""
        context = make_context_standard_12()
        # Day 2: Werewolf banished
        banishment_input = BanishmentInput(day=2, banished=0)

        handler = BanishmentResolutionHandler()
        result = await handler(context, banishment_input)

        assert len(result.subphase_log.events) == 1
        death_event = result.subphase_log.events[0]

        assert death_event.day == 2
        assert death_event.phase == Phase.DAY
        assert death_event.micro_phase == SubPhase.BANISHMENT_RESOLUTION
        assert death_event.cause == DeathCause.BANISHMENT
        assert death_event.last_words is not None

    @pytest.mark.asyncio
    async def test_sheriff_banished_trust_heir(self):
        """Test sheriff banished chooses trusted heir (template fallback)."""
        players = {
            0: Player(seat=0, name="W1", role=Role.WEREWOLF, is_alive=True),
            4: Player(seat=4, name="Sheriff", role=Role.SEER, is_alive=True, is_sheriff=True),
            5: Player(seat=5, name="Witch", role=Role.WITCH, is_alive=True),
            6: Player(seat=6, name="Guard", role=Role.GUARD, is_alive=True),
        }
        living = {0, 4, 5, 6}
        dead = {1, 2, 3, 7, 8, 9, 10, 11}
        sheriff = 4

        context = PhaseContext(players, living, dead, sheriff=sheriff, day=3)
        banishment_input = BanishmentInput(day=3, banished=4)

        handler = BanishmentResolutionHandler()
        result = await handler(context, banishment_input)

        death_event = result.subphase_log.events[0]
        # Badge should go to lowest trusted player (5 Witch, not 0 Werewolf)
        assert death_event.badge_transfer_to == 5

    @pytest.mark.asyncio
    async def test_day_5_no_last_words_exception(self):
        """Test that Day 5 banishment STILL has last words.

        Unlike night deaths (where only Night 1 has last words),
        day deaths ALWAYS have last words.
        """
        context = make_context_standard_12()
        banishment_input = BanishmentInput(day=5, banished=8)

        handler = BanishmentResolutionHandler()
        result = await handler(context, banishment_input)

        death_event = result.subphase_log.events[0]
        # Day deaths always have last words
        assert death_event.last_words is not None


# ============================================================================
# Tests for Phase/MicroPhase Correctness
# ============================================================================


class TestBanishmentResolutionPhases:
    """Tests for correct phase and microphase settings."""

    @pytest.mark.asyncio
    async def test_microphase_is_banishment_resolution(self):
        """Test microphase is BANISHMENT_RESOLUTION."""
        context = make_context_standard_12()
        banishment_input = BanishmentInput(day=2, banished=8)

        handler = BanishmentResolutionHandler()
        result = await handler(context, banishment_input)

        assert result.subphase_log.micro_phase == SubPhase.BANISHMENT_RESOLUTION

    @pytest.mark.asyncio
    async def test_phase_is_day(self):
        """Test phase is DAY for banishment."""
        context = make_context_standard_12()
        banishment_input = BanishmentInput(day=2, banished=8)

        handler = BanishmentResolutionHandler()
        result = await handler(context, banishment_input)

        death_event = result.subphase_log.events[0]
        assert death_event.phase == Phase.DAY

    @pytest.mark.asyncio
    async def test_day_number_matches_input(self):
        """Test event day matches input day."""
        context = make_context_standard_12()
        banishment_input = BanishmentInput(day=7, banished=8)

        handler = BanishmentResolutionHandler()
        result = await handler(context, banishment_input)

        death_event = result.subphase_log.events[0]
        assert death_event.day == 7


# ============================================================================
# Tests for StubPlayer Integration (Hunter Shoot)
# ============================================================================


class TestBanishmentResolutionHunterStubPlayer:
    """Tests for hunter banishment when handler uses StubPlayer.

    These tests verify that:
    1. Handler correctly passes 'choices' to StubPlayer
    2. StubPlayer uses choices to pick a valid target
    3. Hunter doesn't skip when targets are available

    This catches a bug where handler didn't pass 'choices', causing
    StubPlayer to fall back to regex parsing which failed on the
    multi-line prompt format.
    """

    @pytest.mark.asyncio
    async def test_hunter_shoots_with_stub_player(self):
        """Hunter should shoot (not skip) when StubPlayer is used as participant.

        The handler should pass 'choices' to StubPlayer.decide(), allowing
        StubPlayer to pick a valid target from the provided options.

        This test will FAIL if handler doesn't pass 'choices' parameter.
        """
        # Setup: Day 3, Hunter at seat 7 is being banished
        players = {
            0: Player(seat=0, name="W1", role=Role.WEREWOLF, is_alive=True),
            1: Player(seat=1, name="W2", role=Role.WEREWOLF, is_alive=True),
            4: Player(seat=4, name="Seer", role=Role.SEER, is_alive=True),
            7: Player(seat=7, name="Hunter", role=Role.HUNTER, is_alive=True),
            8: Player(seat=8, name="V1", role=Role.ORDINARY_VILLAGER, is_alive=True),
        }
        living = {0, 1, 4, 7, 8}
        dead = {2, 3, 5, 6, 9, 10, 11}

        context = PhaseContext(players, living, dead, sheriff=None, day=3)
        banishment_input = BanishmentInput(day=3, banished=7)  # Hunter

        # Use StubPlayer as the participant (the banished hunter)
        stub = StubPlayer(seed=42)

        handler = BanishmentResolutionHandler()
        result = await handler(context, banishment_input, participant=stub)

        death_event = result.subphase_log.events[0]
        assert death_event.actor == 7
        assert death_event.cause == DeathCause.BANISHMENT

        # CRITICAL: Hunter should have picked a target (NOT None/SKIP)
        # This will FAIL if handler doesn't pass 'choices' to StubPlayer
        assert death_event.hunter_shoot_target is not None, (
            "Hunter should have shot a target, not skipped. "
            "Handler likely didn't pass 'choices' parameter to StubPlayer."
        )

        # The target should be a living player (not the hunter themselves)
        assert death_event.hunter_shoot_target in living
        assert death_event.hunter_shoot_target != 7  # Can't shoot self

    @pytest.mark.asyncio
    async def test_hunter_shoots_consistently_with_stub_player(self):
        """Verify hunter consistently shoots with StubPlayer across multiple runs.

        Uses different seeds to ensure the fix works regardless of random choice.
        """
        seats_to_test = [4, 5, 6, 8, 9, 10, 11]  # All non-werewolf living seats

        for seed in [1, 42, 123, 999, 2024]:
            players = {
                0: Player(seat=0, name="W1", role=Role.WEREWOLF, is_alive=True),
                1: Player(seat=1, name="W2", role=Role.WEREWOLF, is_alive=True),
                7: Player(seat=7, name="Hunter", role=Role.HUNTER, is_alive=True),
            }
            living = {0, 1, 7}
            living.update(seats_to_test)
            dead = set(range(12)) - living

            context = PhaseContext(players, living, dead, sheriff=None, day=2)
            banishment_input = BanishmentInput(day=2, banished=7)

            stub = StubPlayer(seed=seed)
            handler = BanishmentResolutionHandler()
            result = await handler(context, banishment_input, participant=stub)

            death_event = result.subphase_log.events[0]

            assert death_event.hunter_shoot_target is not None, (
                f"Seed {seed}: Hunter should not skip when using StubPlayer"
            )
            assert death_event.hunter_shoot_target in living
            assert death_event.hunter_shoot_target != 7
