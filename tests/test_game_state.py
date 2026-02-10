"""Tests for GameState."""

import pytest
from pydantic import ValidationError

from werewolf.models.player import Player, Role, PlayerType
from werewolf.events.game_events import (
    GameEvent, DeathEvent, DeathCause, Phase, SubPhase
)
from werewolf.engine.game_state import GameState


def create_test_player(seat: int, role: Role, is_alive: bool = True) -> Player:
    """Helper to create a test player."""
    return Player(
        seat=seat,
        name=f"Player{seat}",
        role=role,
        player_type=PlayerType.AI,
        is_alive=is_alive,
        is_sheriff=False,
    )


def create_test_players() -> dict[int, Player]:
    """Create standard 12-player setup for testing."""
    return {
        0: create_test_player(0, Role.WEREWOLF),
        1: create_test_player(1, Role.WEREWOLF),
        2: create_test_player(2, Role.WEREWOLF),
        3: create_test_player(3, Role.WEREWOLF),
        4: create_test_player(4, Role.SEER),
        5: create_test_player(5, Role.WITCH),
        6: create_test_player(6, Role.GUARD),
        7: create_test_player(7, Role.HUNTER),
        8: create_test_player(8, Role.ORDINARY_VILLAGER),
        9: create_test_player(9, Role.ORDINARY_VILLAGER),
        10: create_test_player(10, Role.ORDINARY_VILLAGER),
        11: create_test_player(11, Role.ORDINARY_VILLAGER),
    }


class TestGameStateCreation:
    """Tests for GameState initialization."""

    def test_default_values(self):
        """Test default values for optional fields."""
        players = create_test_players()
        state = GameState(
            players=players,
            living_players=set(players.keys()),
            dead_players=set(),
        )
        assert state.day == 1
        assert state.sheriff is None

    def test_custom_values(self):
        """Test custom values for day and sheriff."""
        players = create_test_players()
        state = GameState(
            players=players,
            living_players=set(players.keys()),
            dead_players=set(),
            sheriff=5,
            day=3,
        )
        assert state.day == 3
        assert state.sheriff == 5


class TestApplyEvents:
    """Tests for apply_events method."""

    def test_apply_single_death_event(self):
        """Test applying a single death event."""
        players = create_test_players()
        state = GameState(
            players=players,
            living_players=set(players.keys()),
            dead_players=set(),
        )

        death_event = DeathEvent(
            actor=8,  # Ordinary Villager
            cause=DeathCause.WEREWOLF_KILL,
            day=1,
            phase=Phase.DAY,
            micro_phase=SubPhase.DEATH_RESOLUTION,
        )

        state.apply_events([death_event])

        assert 8 not in state.living_players
        assert 8 in state.dead_players
        assert not players[8].is_alive

    def test_apply_multiple_death_events(self):
        """Test applying multiple death events."""
        players = create_test_players()
        state = GameState(
            players=players,
            living_players=set(players.keys()),
            dead_players=set(),
        )

        deaths = [
            DeathEvent(
                actor=0,
                cause=DeathCause.BANISHMENT,
                day=2,
                phase=Phase.DAY,
                micro_phase=SubPhase.DEATH_RESOLUTION,
            ),
            DeathEvent(
                actor=8,
                cause=DeathCause.POISON,
                day=2,
                phase=Phase.DAY,
                micro_phase=SubPhase.DEATH_RESOLUTION,
            ),
        ]

        state.apply_events(deaths)

        assert 0 not in state.living_players
        assert 8 not in state.living_players
        assert 0 in state.dead_players
        assert 8 in state.dead_players

    def test_apply_death_event_with_badge_transfer(self):
        """Test death with sheriff badge transfer."""
        players = create_test_players()
        state = GameState(
            players=players,
            living_players=set(players.keys()),
            dead_players=set(),
            sheriff=4,  # Seer is sheriff
        )

        death_event = DeathEvent(
            actor=4,
            cause=DeathCause.WEREWOLF_KILL,
            day=1,
            phase=Phase.DAY,
            micro_phase=SubPhase.DEATH_RESOLUTION,
            badge_transfer_to=8,
        )

        state.apply_events([death_event])

        assert state.sheriff == 8
        assert players[8].is_sheriff
        assert not players[4].is_sheriff

    def test_apply_death_event_with_hunter_shot(self):
        """Test hunter's final shot causes additional death."""
        players = create_test_players()
        state = GameState(
            players=players,
            living_players=set(players.keys()),
            dead_players=set(),
        )

        death_event = DeathEvent(
            actor=7,  # Hunter
            cause=DeathCause.WEREWOLF_KILL,
            day=1,
            phase=Phase.DAY,
            micro_phase=SubPhase.DEATH_RESOLUTION,
            hunter_shoot_target=0,  # Hunter shoots werewolf
        )

        state.apply_events([death_event])

        assert 7 not in state.living_players  # Hunter dies
        assert 0 not in state.living_players  # Werewolf dies from hunter shot
        assert 7 in state.dead_players
        assert 0 in state.dead_players

    def test_apply_non_death_events_ignored(self):
        """Test that non-death events are ignored."""
        players = create_test_players()
        state = GameState(
            players=players,
            living_players=set(players.keys()),
            dead_players=set(),
        )

        # Create a non-death event
        event = GameEvent(
            day=1,
            phase=Phase.DAY,
            micro_phase=SubPhase.DISCUSSION,
        )

        state.apply_events([event])

        # All players should still be alive
        assert len(state.living_players) == 12
        assert len(state.dead_players) == 0


class TestIsGameOver:
    """Tests for is_game_over method."""

    def test_game_not_over_initially(self):
        """Test that game is not over at start."""
        players = create_test_players()
        state = GameState(
            players=players,
            living_players=set(players.keys()),
            dead_players=set(),
        )

        is_over, winner = state.is_game_over()
        assert not is_over
        assert winner is None

    def test_villager_win_all_werewolves_dead(self):
        """Test villager win when all werewolves are dead."""
        players = create_test_players()
        # Kill all werewolves (seats 0-3)
        living = {4, 5, 6, 7, 8, 9, 10, 11}
        state = GameState(
            players=players,
            living_players=living,
            dead_players={0, 1, 2, 3},
        )

        is_over, winner = state.is_game_over()
        assert is_over
        assert winner == "VILLAGER"

    def test_werewolf_win_all_gods_dead(self):
        """Test werewolf win when all gods are dead."""
        players = create_test_players()
        # Kill all gods (Seer=4, Witch=5, Guard=6, Hunter=7)
        living = {0, 1, 2, 3, 8, 9, 10, 11}
        state = GameState(
            players=players,
            living_players=living,
            dead_players={4, 5, 6, 7},
        )

        is_over, winner = state.is_game_over()
        assert is_over
        assert winner == "WEREWOLF"

    def test_werewolf_win_all_villagers_dead(self):
        """Test werewolf win when all ordinary villagers are dead."""
        players = create_test_players()
        # Kill all ordinary villagers (seats 8-11)
        living = {0, 1, 2, 3, 4, 5, 6, 7}
        state = GameState(
            players=players,
            living_players=living,
            dead_players={8, 9, 10, 11},
        )

        is_over, winner = state.is_game_over()
        assert is_over
        assert winner == "WEREWOLF"

    def test_game_continues_with_mixed_survivors(self):
        """Test game continues with mixed survivors."""
        players = create_test_players()
        # Some werewolves and some villagers alive
        living = {0, 4, 8, 9}
        state = GameState(
            players=players,
            living_players=living,
            dead_players={1, 2, 3, 5, 6, 7, 10, 11},
        )

        is_over, winner = state.is_game_over()
        assert not is_over


class TestHelperMethods:
    """Tests for helper methods."""

    def test_get_player(self):
        """Test getting a player by seat."""
        players = create_test_players()
        state = GameState(
            players=players,
            living_players=set(players.keys()),
            dead_players=set(),
        )

        player = state.get_player(4)
        assert player is not None
        assert player.seat == 4
        assert player.role == Role.SEER

    def test_get_player_not_found(self):
        """Test getting non-existent player returns None."""
        players = create_test_players()
        state = GameState(
            players=players,
            living_players=set(players.keys()),
            dead_players=set(),
        )

        player = state.get_player(99)
        assert player is None

    def test_is_alive(self):
        """Test checking if player is alive."""
        players = create_test_players()
        living = {4, 5, 6}
        state = GameState(
            players=players,
            living_players=living,
            dead_players=set(players.keys()) - living,
        )

        assert state.is_alive(4)
        assert state.is_alive(5)
        assert not state.is_alive(0)
        assert not state.is_alive(99)  # Non-existent player

    def test_is_werewolf(self):
        """Test checking if player is werewolf."""
        players = create_test_players()
        state = GameState(
            players=players,
            living_players=set(players.keys()),
            dead_players=set(),
        )

        assert state.is_werewolf(0)
        assert state.is_werewolf(1)
        assert state.is_werewolf(3)
        assert not state.is_werewolf(4)  # Seer
        assert not state.is_werewolf(8)  # Ordinary Villager
        assert not state.is_werewolf(99)  # Non-existent

    def test_get_werewolf_count(self):
        """Test counting werewolves."""
        players = create_test_players()
        living = {0, 4, 5, 8, 9}
        state = GameState(
            players=players,
            living_players=living,
            dead_players=set(players.keys()) - living,
        )

        assert state.get_werewolf_count() == 1

    def test_get_god_count(self):
        """Test counting gods (Seer, Witch, Guard, Hunter)."""
        players = create_test_players()
        living = {0, 4, 5, 6, 7, 8}  # All 4 gods + werewolf + villager
        state = GameState(
            players=players,
            living_players=living,
            dead_players=set(players.keys()) - living,
        )

        assert state.get_god_count() == 4

    def test_get_ordinary_villager_count(self):
        """Test counting ordinary villagers."""
        players = create_test_players()
        living = {0, 1, 8, 9}  # 2 werewolves + 2 villagers
        state = GameState(
            players=players,
            living_players=living,
            dead_players=set(players.keys()) - living,
        )

        assert state.get_ordinary_villager_count() == 2

    def test_is_sheriff(self):
        """Test checking if player is sheriff."""
        players = create_test_players()
        state = GameState(
            players=players,
            living_players=set(players.keys()),
            dead_players=set(),
            sheriff=5,
        )

        assert state.is_sheriff(5)
        assert not state.is_sheriff(4)
        assert not state.is_sheriff(99)


class TestEdgeCases:
    """Tests for edge cases."""

    def test_all_players_dead(self):
        """Test game over with all players dead."""
        players = create_test_players()
        state = GameState(
            players=players,
            living_players=set(),
            dead_players=set(players.keys()),
        )

        is_over, winner = state.is_game_over()
        assert is_over
        assert winner == "VILLAGER"  # No werewolves alive

    def test_only_werewolves_alive(self):
        """Test werewolf win when only werewolves remain."""
        players = create_test_players()
        living = {0, 1, 2, 3}
        state = GameState(
            players=players,
            living_players=living,
            dead_players=set(players.keys()) - living,
        )

        is_over, winner = state.is_game_over()
        assert is_over
        assert winner == "WEREWOLF"

    def test_only_gods_alive(self):
        """Test villager win when only gods remain."""
        players = create_test_players()
        living = {4, 5, 6, 7}
        state = GameState(
            players=players,
            living_players=living,
            dead_players=set(players.keys()) - living,
        )

        is_over, winner = state.is_game_over()
        assert is_over
        assert winner == "VILLAGER"

    def test_apply_events_to_empty_state(self):
        """Test applying events to state with no players."""
        state = GameState(
            players={},
            living_players=set(),
            dead_players=set(),
        )

        death_event = DeathEvent(
            actor=0,
            cause=DeathCause.WEREWOLF_KILL,
            day=1,
            phase=Phase.DAY,
            micro_phase=SubPhase.DEATH_RESOLUTION,
        )

        # Should not raise
        state.apply_events([death_event])
