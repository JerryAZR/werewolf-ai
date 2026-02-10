"""Tests for NightActionResolver component."""

import pytest
from werewolf.engine import GameState, NightActionStore, NightActionResolver
from werewolf.events.game_events import DeathCause
from werewolf.models.player import Player, Role, PlayerType


def make_test_state(
    living: list[int],
    dead: list[int] | None = None
) -> GameState:
    """Create a test GameState with specified living and dead players."""
    players: dict[int, Player] = {}
    living_set = set(living)
    dead_set = set(dead) if dead else set()

    all_seats = living_set | dead_set
    for seat in all_seats:
        players[seat] = Player(
            seat=seat,
            name=f"Player{seat}",
            role=Role.VILLAGER,
            player_type=PlayerType.AI,
            is_alive=seat in living_set,
        )

    return GameState(
        players=players,
        living_players=living_set,
        dead_players=dead_set,
    )


class TestNightActionResolver:
    """Tests for NightActionResolver functionality."""

    def test_poison_kills_ignores_guard(self) -> None:
        """Test that poison kills regardless of guard protection."""
        state = make_test_state(living=[0, 1, 2, 3])
        actions = NightActionStore(
            kill_target=2,
            poison_target=2,
            guard_target=2,
        )

        resolver = NightActionResolver()
        result = resolver.resolve(state, actions)

        # Poison should kill even though guarded
        assert result == {2: DeathCause.POISON}

    def test_werewolf_kill_saved_by_antidote(self) -> None:
        """Test that werewolf kill is saved by antidote."""
        state = make_test_state(living=[0, 1, 2, 3])
        actions = NightActionStore(
            kill_target=2,
            antidote_target=2,
            guard_target=None,
        )

        resolver = NightActionResolver()
        result = resolver.resolve(state, actions)

        # Antidote should save the kill
        assert result == {}

    def test_werewolf_kill_saved_by_guard(self) -> None:
        """Test that werewolf kill is saved by guard protection."""
        state = make_test_state(living=[0, 1, 2, 3])
        actions = NightActionStore(
            kill_target=2,
            antidote_target=None,
            guard_target=2,
        )

        resolver = NightActionResolver()
        result = resolver.resolve(state, actions)

        # Guard should save the kill
        assert result == {}

    def test_werewolf_kill_not_saved_no_antidote_no_guard(self) -> None:
        """Test that werewolf kill happens when neither antidote nor guard protects."""
        state = make_test_state(living=[0, 1, 2, 3])
        actions = NightActionStore(
            kill_target=2,
            antidote_target=None,
            guard_target=1,  # Guarding someone else
        )

        resolver = NightActionResolver()
        result = resolver.resolve(state, actions)

        # Kill should happen
        assert result == {2: DeathCause.WEREWOLF_KILL}

    def test_both_poison_and_werewolf_kill_poison_takes_precedence(self) -> None:
        """Test that poison takes precedence over werewolf kill (different targets)."""
        state = make_test_state(living=[0, 1, 2, 3])
        actions = NightActionStore(
            kill_target=2,
            poison_target=3,
            antidote_target=None,
            guard_target=None,
        )

        resolver = NightActionResolver()
        result = resolver.resolve(state, actions)

        # Both targets should die, poison by POISON
        assert result == {2: DeathCause.WEREWOLF_KILL, 3: DeathCause.POISON}

    def test_no_deaths_no_kill_no_poison(self) -> None:
        """Test that no deaths occur when there's no kill and no poison."""
        state = make_test_state(living=[0, 1, 2, 3])
        actions = NightActionStore(
            kill_target=None,
            poison_target=None,
            antidote_target=None,
            guard_target=None,
        )

        resolver = NightActionResolver()
        result = resolver.resolve(state, actions)

        assert result == {}

    def test_no_death_if_target_already_dead(self) -> None:
        """Test that already-dead players don't die again."""
        state = make_test_state(living=[0, 1], dead=[2, 3])
        actions = NightActionStore(
            kill_target=2,
            poison_target=3,
        )

        resolver = NightActionResolver()
        result = resolver.resolve(state, actions)

        # Already dead players shouldn't be added to deaths
        assert result == {}

    def test_kill_saved_by_guard_not_antidote(self) -> None:
        """Test that guard saves kill even when antidote targets different player."""
        state = make_test_state(living=[0, 1, 2, 3])
        actions = NightActionStore(
            kill_target=2,
            antidote_target=1,  # Antidoting someone else
            guard_target=2,
        )

        resolver = NightActionResolver()
        result = resolver.resolve(state, actions)

        # Guard saves the kill, antidote on wrong target doesn't help
        assert result == {}

    def test_antidote_saves_kill_not_guard(self) -> None:
        """Test that antidote saves kill even when guard targets different player."""
        state = make_test_state(living=[0, 1, 2, 3])
        actions = NightActionStore(
            kill_target=2,
            antidote_target=2,
            guard_target=1,  # Guarding someone else
        )

        resolver = NightActionResolver()
        result = resolver.resolve(state, actions)

        # Antidote saves the kill
        assert result == {}

    def test_empty_living_players(self) -> None:
        """Test resolution with no living players."""
        state = make_test_state(living=[], dead=[0, 1, 2, 3])
        actions = NightActionStore(
            kill_target=0,
            poison_target=1,
        )

        resolver = NightActionResolver()
        result = resolver.resolve(state, actions)

        # No deaths since all are already dead
        assert result == {}

    def test_guard_prev_target_not_used_in_resolution(self) -> None:
        """Test that guard_prev_target (for next night) is not used in resolution."""
        # This test verifies that guard_prev_target doesn't affect current night
        state = make_test_state(living=[0, 1, 2])
        actions = NightActionStore(
            kill_target=2,
            antidote_target=None,
            guard_target=2,
            guard_prev_target=2,  # Restricted from guarding same person
        )

        resolver = NightActionResolver()
        result = resolver.resolve(state, actions)

        # guard_prev_target should not affect resolution - guard should still save
        assert result == {}

    def test_multiple_nights_snapshot_integration(self) -> None:
        """Test resolution with persistent state that would come from snapshot."""
        # Simulate state after night 1 where potions were used
        state = make_test_state(living=[0, 1, 2, 3])

        # Night 2 actions with persistent state from previous night
        actions = NightActionStore(
            antidote_used=True,  # From snapshot
            poison_used=True,    # From snapshot
            guard_prev_target=1, # From snapshot
            kill_target=2,
            poison_target=3,
        )

        resolver = NightActionResolver()
        result = resolver.resolve(state, actions)

        # Poison and kill should happen regardless of usage flags
        # The usage flags are set by the witch handler when actions are taken
        assert result == {2: DeathCause.WEREWOLF_KILL, 3: DeathCause.POISON}

    def test_only_kill_no_poison_no_antidote_no_guard(self) -> None:
        """Test simple case: kill with no protection."""
        state = make_test_state(living=[0, 1, 2])
        actions = NightActionStore(
            kill_target=0,
            poison_target=None,
            antidote_target=None,
            guard_target=None,
        )

        resolver = NightActionResolver()
        result = resolver.resolve(state, actions)

        assert result == {0: DeathCause.WEREWOLF_KILL}

    def test_only_poison_no_kill(self) -> None:
        """Test simple case: poison only."""
        state = make_test_state(living=[0, 1, 2])
        actions = NightActionStore(
            kill_target=None,
            poison_target=1,
            antidote_target=None,
            guard_target=None,
        )

        resolver = NightActionResolver()
        result = resolver.resolve(state, actions)

        assert result == {1: DeathCause.POISON}

    def test_both_protections_both_save(self) -> None:
        """Test that having both antidote and guard still saves the kill."""
        state = make_test_state(living=[0, 1, 2])
        actions = NightActionStore(
            kill_target=2,
            antidote_target=2,
            guard_target=2,
        )

        resolver = NightActionResolver()
        result = resolver.resolve(state, actions)

        # Both protections - kill still saved
        assert result == {}
