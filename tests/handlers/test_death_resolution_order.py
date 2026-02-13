"""Tests: DeathResolutionHandler query order for Sheriff+Hunter.

When a player is BOTH Sheriff and Hunter and dies (Night 1):
- Query order MUST be: hunter_shoot → badge_transfer → last_words

These tests verify the correct query order.
"""

import pytest
from unittest.mock import AsyncMock
from typing import Optional

from werewolf.models import Player, Role, PlayerType
from werewolf.events.game_events import DeathCause
from werewolf.handlers.death_resolution_handler import NightOutcomeInput


class PhaseContext:
    """Minimal context for testing DeathResolution handler."""

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

    def is_alive(self, seat: int) -> bool:
        return seat in self.living_players

    def is_werewolf(self, seat: int) -> bool:
        player = self.get_player(seat)
        return player is not None and player.role == Role.WEREWOLF


class TestDeathResolutionQueryOrder:
    """Tests: Verify correct query order for dying players."""

    @pytest.mark.asyncio
    async def test_sheriff_hunter_query_order(self):
        """Sheriff+Hunter death: verify hunter_shoot → badge_transfer → last_words.

        This is the critical edge case - player is both Sheriff and Hunter.
        Query order MUST be:
        1. Hunter shoot target (first action)
        2. Badge transfer (second action)
        3. Last words (final statement)
        """
        from werewolf.handlers.death_resolution_handler import DeathResolutionHandler

        # Create scenario: Player 0 is Sheriff AND Hunter, killed Night 1
        players = {
            0: Player(seat=0, name="Player_0", role=Role.HUNTER, player_type=PlayerType.AI),
            1: Player(seat=1, name="Player_1", role=Role.WEREWOLF, player_type=PlayerType.AI),
            2: Player(seat=2, name="Player_2", role=Role.VILLAGER, player_type=PlayerType.AI),
        }
        players[0].is_sheriff = True  # Player 0 is Sheriff

        context = PhaseContext(
            players=players,
            living_players={1, 2},  # Only 1 and 2 survive
            dead_players={0},
            sheriff=0,  # Sheriff is dying
            day=1,
        )

        # Track call order
        call_log = []

        async def mock_decide(system, user, hint=None, choices=None):
            # Extract query type from system prompt (more specific)
            # Note: Hunter queries have "Hunter Final Shot" in user, badge has "Badge Transfer", last_words has "Final Words"
            if "Hunter Final Shot" in user or "Hunter's Final Shot" in user:
                call_log.append("hunter_shoot")
                return "1"  # Shoot player 1
            elif "Badge Transfer" in user:
                call_log.append("badge_transfer")
                return "2"  # Transfer badge to player 2
            elif "Final Words" in user:
                call_log.append("last_words")
                return "I am the Hunter and Sheriff, trust player 2!"
            elif "Hunter" in system or "Hunter" in user:
                call_log.append("hunter_shoot")
                return "1"
            elif "Sheriff" in system or "Sheriff" in user:
                call_log.append("badge_transfer")
                return "2"
            else:
                call_log.append("unknown")
                return "Goodbye!"

        mock_participant = AsyncMock()
        mock_participant.decide = mock_decide

        night_outcome = NightOutcomeInput(day=1, deaths={0: DeathCause.WEREWOLF_KILL})

        handler = DeathResolutionHandler()
        result = await handler(
            context,
            night_outcome,
            participants=[(0, mock_participant)],
        )

        # Verify correct order
        expected_order = ["hunter_shoot", "badge_transfer", "last_words"]
        assert call_log == expected_order, (
            f"FAIL: Query order is {call_log}, expected {expected_order}. "
            f"Order must be: hunter_shoot → badge_transfer → last_words"
        )

    @pytest.mark.asyncio
    async def test_hunter_only_query_order(self):
        """Hunter (not Sheriff) death: only hunter_shoot and last_words."""
        from werewolf.handlers.death_resolution_handler import DeathResolutionHandler

        # Player 0 is Hunter only (not Sheriff)
        players = {
            0: Player(seat=0, name="Player_0", role=Role.HUNTER, player_type=PlayerType.AI),
            1: Player(seat=1, name="Player_1", role=Role.WEREWOLF, player_type=PlayerType.AI),
        }
        # Not sheriff
        players[0].is_sheriff = False

        context = PhaseContext(
            players=players,
            living_players={1},
            dead_players={0},
            sheriff=None,
            day=1,
        )

        call_log = []

        async def mock_decide(system, user, hint=None, choices=None):
            # More specific detection
            if "Hunter Final Shot" in user or "Hunter's Final Shot" in user:
                call_log.append("hunter_shoot")
                return "1"
            elif "Final Words" in user:
                call_log.append("last_words")
                return "Goodbye village!"
            elif "Hunter" in system or "Hunter" in user:
                call_log.append("hunter_shoot")
                return "1"
            else:
                call_log.append("unknown")
                return "Goodbye!"

        mock_participant = AsyncMock()
        mock_participant.decide = mock_decide

        night_outcome = NightOutcomeInput(day=1, deaths={0: DeathCause.WEREWOLF_KILL})

        handler = DeathResolutionHandler()
        result = await handler(
            context,
            night_outcome,
            participants=[(0, mock_participant)],
        )

        # Hunter only: hunter_shoot → last_words
        expected_order = ["hunter_shoot", "last_words"]
        assert call_log == expected_order, (
            f"FAIL: Query order is {call_log}, expected {expected_order}"
        )

    @pytest.mark.asyncio
    async def test_sheriff_only_not_hunter_query_order(self):
        """Sheriff (not Hunter) death: only badge_transfer and last_words."""
        from werewolf.handlers.death_resolution_handler import DeathResolutionHandler

        # Player 0 is Sheriff only (not Hunter)
        players = {
            0: Player(seat=0, name="Player_0", role=Role.VILLAGER, player_type=PlayerType.AI),
            1: Player(seat=1, name="Player_1", role=Role.WEREWOLF, player_type=PlayerType.AI),
        }
        players[0].is_sheriff = True  # Sheriff

        context = PhaseContext(
            players=players,
            living_players={1},
            dead_players={0},
            sheriff=0,  # Sheriff is dying
            day=1,
        )

        call_log = []

        async def mock_decide(system, user, hint=None, choices=None):
            if "Sheriff" in system or "Sheriff" in user:
                call_log.append("badge_transfer")
            elif "final words" in system or "Final Words" in user:
                call_log.append("last_words")
            return "1" if "Sheriff" in user else "Goodbye!"

        mock_participant = AsyncMock()
        mock_participant.decide = mock_decide

        night_outcome = NightOutcomeInput(day=1, deaths={0: DeathCause.WEREWOLF_KILL})

        handler = DeathResolutionHandler()
        result = await handler(
            context,
            night_outcome,
            participants=[(0, mock_participant)],
        )

        # Sheriff only: badge_transfer → last_words
        expected_order = ["badge_transfer", "last_words"]
        assert call_log == expected_order, (
            f"FAIL: Query order is {call_log}, expected {expected_order}"
        )

    @pytest.mark.asyncio
    async def test_no_special_role_just_last_words(self):
        """Ordinary death: only last_words query."""
        from werewolf.handlers.death_resolution_handler import DeathResolutionHandler

        players = {
            0: Player(seat=0, name="Player_0", role=Role.VILLAGER, player_type=PlayerType.AI),
            1: Player(seat=1, name="Player_1", role=Role.WEREWOLF, player_type=PlayerType.AI),
        }
        players[0].is_sheriff = False

        context = PhaseContext(
            players=players,
            living_players={1},
            dead_players={0},
            sheriff=None,
            day=1,
        )

        call_log = []

        async def mock_decide(system, user, hint=None, choices=None):
            if "final words" in system or "Final Words" in user:
                call_log.append("last_words")
            return "Goodbye village!"

        mock_participant = AsyncMock()
        mock_participant.decide = mock_decide

        night_outcome = NightOutcomeInput(day=1, deaths={0: DeathCause.WEREWOLF_KILL})

        handler = DeathResolutionHandler()
        result = await handler(
            context,
            night_outcome,
            participants=[(0, mock_participant)],
        )

        # Ordinary death: only last_words
        assert call_log == ["last_words"], (
            f"FAIL: Expected only ['last_words'], got {call_log}"
        )

    @pytest.mark.asyncio
    async def test_night2_no_last_words(self):
        """Night 2+ death: no last words query."""
        from werewolf.handlers.death_resolution_handler import DeathResolutionHandler

        players = {
            0: Player(seat=0, name="Player_0", role=Role.HUNTER, player_type=PlayerType.AI),
            1: Player(seat=1, name="Player_1", role=Role.WEREWOLF, player_type=PlayerType.AI),
        }
        players[0].is_sheriff = False

        context = PhaseContext(
            players=players,
            living_players={1},
            dead_players={0},
            sheriff=None,
            day=2,  # Night 2!
        )

        call_log = []

        async def mock_decide(system, user, hint=None, choices=None):
            if "Hunter" in system or "Hunter" in user:
                call_log.append("hunter_shoot")
            elif "final words" in system or "Final Words" in user:
                call_log.append("last_words")
            return "1" if "Hunter" in user else "Should not be called"

        mock_participant = AsyncMock()
        mock_participant.decide = mock_decide

        night_outcome = NightOutcomeInput(day=2, deaths={0: DeathCause.WEREWOLF_KILL})

        handler = DeathResolutionHandler()
        result = await handler(
            context,
            night_outcome,
            participants=[(0, mock_participant)],
        )

        # Night 2+: no last words for night deaths
        # But hunter still gets to shoot
        assert call_log == ["hunter_shoot"], (
            f"FAIL: Night 2 should not query for last_words. Got: {call_log}"
        )


class TestDeathResolutionEventFields:
    """Tests: Verify DeathEvent has correct fields filled."""

    @pytest.mark.asyncio
    async def test_sheriff_hunter_all_fields_filled(self):
        """Sheriff+Hunter death: all three fields should be populated."""
        from werewolf.handlers.death_resolution_handler import DeathResolutionHandler

        players = {
            0: Player(seat=0, name="Player_0", role=Role.HUNTER, player_type=PlayerType.AI),
            1: Player(seat=1, name="Player_1", role=Role.WEREWOLF, player_type=PlayerType.AI),
            2: Player(seat=2, name="Player_2", role=Role.VILLAGER, player_type=PlayerType.AI),
        }
        players[0].is_sheriff = True

        context = PhaseContext(
            players=players,
            living_players={1, 2},
            dead_players={0},
            sheriff=0,
            day=1,
        )

        async def mock_decide(system, user, hint=None, choices=None):
            # More specific detection
            if "Hunter Final Shot" in user or "Hunter's Final Shot" in user:
                return "1"
            elif "Badge Transfer" in user:
                return "2"
            elif "Final Words" in user:
                return "My final words"
            elif "Hunter" in user:
                return "1"
            elif "Sheriff" in user:
                return "2"
            else:
                return "My final words"

        mock_participant = AsyncMock()
        mock_participant.decide = mock_decide

        night_outcome = NightOutcomeInput(day=1, deaths={0: DeathCause.WEREWOLF_KILL})

        handler = DeathResolutionHandler()
        result = await handler(
            context,
            night_outcome,
            participants=[(0, mock_participant)],
        )

        event = result.subphase_log.events[0]

        # All fields should be populated
        assert event.hunter_shoot_target == 1, (
            f"FAIL: hunter_shoot_target should be 1, got {event.hunter_shoot_target}"
        )
        assert event.badge_transfer_to == 2, (
            f"FAIL: badge_transfer_to should be 2, got {event.badge_transfer_to}"
        )
        assert event.last_words == "My final words", (
            f"FAIL: last_words should be set, got {event.last_words}"
        )


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
