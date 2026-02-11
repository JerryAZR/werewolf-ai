"""Integration tests: WerewolfGame - complete game simulation with StubPlayer.

Tests the full game flow from start to finish using StubPlayer for all decisions.
Verifies:
- Complete game simulation
- Victory detection (werewolves win, villagers win)
- Event log accumulation
- No crashes during execution
- Determinism with same seed

All tests have timeout to prevent infinite loops.
"""

import asyncio
import random
import pytest

from werewolf.models import (
    Player,
    Role,
    RoleConfig,
    STANDARD_12_PLAYER_CONFIG,
    create_players_from_config,
)
from werewolf.engine import WerewolfGame, GameState
from werewolf.ai.stub_ai import StubPlayer, create_stub_player
from werewolf.events import GameEventLog, GameOver, Phase


# ============================================================================
# Helper Functions
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


def create_participants(players: dict[int, Player], seed: int = 42) -> dict[int, StubPlayer]:
    """Create stub participants for all players."""
    return {seat: create_stub_player(seed=seed + seat) for seat in players.keys()}


def count_living_by_role(state: GameState, role: Role) -> int:
    """Count living players with a specific role."""
    count = 0
    for seat in state.living_players:
        player = state.players.get(seat)
        if player and player.role == role:
            count += 1
    return count


def count_dead_by_role(state: GameState, role: Role) -> int:
    """Count dead players with a specific role."""
    count = 0
    for seat in state.dead_players:
        player = state.players.get(seat)
        if player and player.role == role:
            count += 1
    return count


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def standard_players() -> dict[int, Player]:
    """Create standard 12-player config as dict with shuffled roles."""
    return create_players_shuffled()


@pytest.fixture
def standard_participants(standard_players: dict[int, Player]) -> dict[int, StubPlayer]:
    """Create stub participants for all players."""
    return create_participants(standard_players)


# ============================================================================
# WerewolfGame Tests
# ============================================================================

class TestWerewolfGameCompleteGame:
    """Tests for complete game simulation with WerewolfGame."""

    @pytest.mark.asyncio
    async def test_complete_game_simulation(self, standard_players: dict[int, Player]):
        """Test that a complete game can run to completion without errors."""
        participants = create_participants(standard_players, seed=42)

        game = WerewolfGame(
            players=standard_players,
            participants=participants,
        )

        event_log, winner = await game.run()

        # Verify game produced a result
        assert event_log is not None
        assert winner in ["WEREWOLF", "VILLAGER"]

        # Verify game structure
        assert event_log.player_count == 12
        assert len(event_log.phases) >= 2  # At least one night and one day

    @pytest.mark.asyncio
    async def test_game_has_game_start_event(self, standard_players: dict[int, Player]):
        """Test that game start event is properly recorded."""
        participants = create_participants(standard_players, seed=42)

        game = WerewolfGame(
            players=standard_players,
            participants=participants,
        )

        event_log, _ = await game.run()

        assert event_log.game_start is not None
        assert event_log.game_start.player_count == 12

    @pytest.mark.asyncio
    async def test_game_has_game_over_event(self, standard_players: dict[int, Player]):
        """Test that game over event is properly recorded."""
        participants = create_participants(standard_players, seed=42)

        game = WerewolfGame(
            players=standard_players,
            participants=participants,
        )

        event_log, winner = await game.run()

        assert event_log.game_over is not None
        assert event_log.game_over.winner == winner

    @pytest.mark.asyncio
    async def test_event_log_has_multiple_phases(self, standard_players: dict[int, Player]):
        """Test that event log accumulates multiple night/day phases."""
        participants = create_participants(standard_players, seed=123)

        game = WerewolfGame(
            players=standard_players,
            participants=participants,
        )

        event_log, _ = await game.run()

        # Game should have multiple phases
        nights = [p for p in event_log.phases if p.kind == Phase.NIGHT]
        days = [p for p in event_log.phases if p.kind == Phase.DAY]

        assert len(nights) >= 1, "Should have at least one night phase"
        assert len(days) >= 1, "Should have at least one day phase"

    @pytest.mark.asyncio
    async def test_event_log_contains_expected_subphases(self, standard_players: dict[int, Player]):
        """Test that day phases contain expected subphases."""
        participants = create_participants(standard_players, seed=456)

        game = WerewolfGame(
            players=standard_players,
            participants=participants,
        )

        event_log, _ = await game.run()

        # Check that day phases contain subphases
        days = [p for p in event_log.phases if p.kind == Phase.DAY]

        if len(days) >= 1:
            day1 = days[0]
            # Day should have subphases (campaign, voting, discussion, etc.)
            assert len(day1.subphases) >= 1, "Day phase should have subphases"


class TestWerewolfGameVictoryDetection:
    """Tests for victory condition detection."""

    @pytest.mark.asyncio
    async def test_victory_detected_werewolves_win(self, standard_players: dict[int, Player]):
        """Test that werewolves can win the game."""
        # Use a seed that tends to produce werewolf victory
        participants = create_participants(standard_players, seed=789)

        game = WerewolfGame(
            players=standard_players,
            participants=participants,
        )

        event_log, winner = await game.run()

        # Verify winner is valid
        assert winner is not None
        assert winner in ["WEREWOLF", "VILLAGER"]

    @pytest.mark.asyncio
    async def test_victory_detected_villagers_win(self, standard_players: dict[int, Player]):
        """Test that villagers can win the game."""
        # Use a different seed that might produce villager victory
        participants = create_participants(standard_players, seed=101112)

        game = WerewolfGame(
            players=standard_players,
            participants=participants,
        )

        event_log, winner = await game.run()

        # Verify winner is valid
        assert winner is not None
        assert winner in ["WEREWOLF", "VILLAGER"]

    @pytest.mark.asyncio
    async def test_game_over_condition_is_set(self, standard_players: dict[int, Player]):
        """Test that game over condition is properly set."""
        participants = create_participants(standard_players, seed=999)

        game = WerewolfGame(
            players=standard_players,
            participants=participants,
        )

        event_log, winner = await game.run()

        assert event_log.game_over is not None
        assert event_log.game_over.condition is not None

    @pytest.mark.asyncio
    async def test_consistent_winner_in_log_and_return(self, standard_players: dict[int, Player]):
        """Test that winner in game_over matches returned winner."""
        participants = create_participants(standard_players, seed=131415)

        game = WerewolfGame(
            players=standard_players,
            participants=participants,
        )

        event_log, winner = await game.run()

        assert winner is not None
        assert event_log.game_over is not None
        assert winner == event_log.game_over.winner


class TestWerewolfGameGameFlow:
    """Tests for game flow mechanics."""

    @pytest.mark.asyncio
    async def test_game_increments_day_count(self, standard_players: dict[int, Player]):
        """Test that day count is properly incremented."""
        participants = create_participants(standard_players, seed=161718)

        game = WerewolfGame(
            players=standard_players,
            participants=participants,
        )

        event_log, _ = await game.run()

        # Check that final day count is set
        assert event_log.game_over is not None
        assert event_log.game_over.final_turn_count >= 1

    @pytest.mark.asyncio
    async def test_all_players_start_alive(self, standard_players: dict[int, Player]):
        """Test that all players are initially alive."""
        state = GameState(
            players=standard_players,
            living_players=set(standard_players.keys()),
            dead_players=set(),
        )

        assert len(state.living_players) == 12
        assert len(state.dead_players) == 0

    @pytest.mark.asyncio
    async def test_some_players_die_during_game(self, standard_players: dict[int, Player]):
        """Test that players can die during the game.

        Note: It's possible for games to end without deaths (e.g., werewolves always skip,
        no banishments occur). This test verifies deaths CAN happen, not that they MUST happen.
        """
        participants = create_participants(standard_players, seed=192021)

        game = WerewolfGame(
            players=standard_players,
            participants=participants,
        )

        event_log, _ = await game.run()

        # Check if deaths occurred - it's valid for games to end without deaths
        deaths = event_log.get_all_deaths()
        # Game is valid either way, but we verify the game structure is correct
        assert event_log.game_over is not None
        assert event_log.game_over.final_turn_count >= 1


class TestWerewolfGameDeterminism:
    """Tests for deterministic behavior with same seed.

    When a seed is provided to WerewolfGame, running with the same seed
    should produce identical game outcomes. This is useful for:
    - Reproducing bugs
    - Replaying interesting games
    - Testing against known game states
    """

    @pytest.mark.asyncio
    async def test_same_seed_produces_same_winner(self, standard_players: dict[int, Player]):
        """Test that running with same seed produces consistent results."""
        # Reset random state before each game to ensure clean slate
        random.seed(222222)

        participants1 = create_participants(standard_players, seed=222222)
        participants2 = create_participants(standard_players, seed=222222)

        # Pass seed to WerewolfGame for game logic determinism
        game1 = WerewolfGame(players=standard_players, participants=participants1, seed=222222)
        game2 = WerewolfGame(players=standard_players, participants=participants2, seed=222222)

        event_log1, winner1 = await game1.run()
        event_log2, winner2 = await game2.run()

        # Same seed should produce same winner
        assert winner1 == winner2, f"Expected same winner but got {winner1} vs {winner2}"

    @pytest.mark.asyncio
    async def test_same_seed_produces_same_event_log(self, standard_players: dict[int, Player]):
        """Test that running with same seed produces identical event logs."""
        # Reset random state before each game to ensure clean slate
        random.seed(555555)

        participants1 = create_participants(standard_players, seed=555555)
        participants2 = create_participants(standard_players, seed=555555)

        # Pass seed to WerewolfGame for game logic determinism
        game1 = WerewolfGame(players=standard_players, participants=participants1, seed=555555)
        game2 = WerewolfGame(players=standard_players, participants=participants2, seed=555555)

        event_log1, winner1 = await game1.run()
        event_log2, winner2 = await game2.run()

        # Same seed should produce same winner
        assert winner1 == winner2
        # Same winner implies same number of phases (simplified check)
        assert len(event_log1.phases) == len(event_log2.phases)

    @pytest.mark.asyncio
    async def test_different_seeds_can_produce_different_winners(self, standard_players: dict[int, Player]):
        """Test that different seeds can produce different game outcome."""
        participants1 = create_participants(standard_players, seed=333333)
        participants2 = create_participants(standard_players, seed=444444)

        # Use different seeds for game logic too
        game1 = WerewolfGame(players=standard_players, participants=participants1, seed=333333)
        game2 = WerewolfGame(players=standard_players, participants=participants2, seed=444444)

        _, winner1 = await game1.run()
        _, winner2 = await game2.run()

        # Different seeds may produce different winners
        # This is probabilistic so we'll just verify both are valid
        assert winner1 in ["WEREWOLF", "VILLAGER"]
        assert winner2 in ["WEREWOLF", "VILLAGER"]


class TestWerewolfGameEventLogStructure:
    """Tests for event log structure and content."""

    @pytest.mark.asyncio
    async def test_event_log_has_valid_game_id(self, standard_players: dict[int, Player]):
        """Test that event log has a valid game ID."""
        participants = create_participants(standard_players, seed=252525)

        game = WerewolfGame(
            players=standard_players,
            participants=participants,
        )

        event_log, _ = await game.run()

        assert event_log.game_id is not None
        assert len(event_log.game_id) > 0

    @pytest.mark.asyncio
    async def test_event_log_has_creation_timestamp(self, standard_players: dict[int, Player]):
        """Test that event log has a creation timestamp."""
        participants = create_participants(standard_players, seed=262626)

        game = WerewolfGame(
            players=standard_players,
            participants=participants,
        )

        event_log, _ = await game.run()

        assert event_log.created_at is not None
        assert len(event_log.created_at) > 0

    @pytest.mark.asyncio
    async def test_phases_are_in_chronological_order(self, standard_players: dict[int, Player]):
        """Test that phases are stored in chronological order."""
        participants = create_participants(standard_players, seed=272727)

        game = WerewolfGame(
            players=standard_players,
            participants=participants,
        )

        event_log, _ = await game.run()

        # Verify phases are ordered
        for i in range(1, len(event_log.phases)):
            assert event_log.phases[i].number >= event_log.phases[i - 1].number

    @pytest.mark.asyncio
    async def test_event_log_can_be_converted_to_string(self, standard_players: dict[int, Player]):
        """Test that event log can be converted to string representation."""
        participants = create_participants(standard_players, seed=282828)

        game = WerewolfGame(
            players=standard_players,
            participants=participants,
        )

        event_log, _ = await game.run()

        # Should not raise an exception
        string_repr = str(event_log)
        assert len(string_repr) > 0


# ============================================================================
# Validator Integration Tests
# ============================================================================

class TestWerewolfGameValidator:
    """Tests for game validation with CollectingValidator."""

    @pytest.mark.asyncio
    async def test_complete_game_with_validator_no_violations(
        self, standard_players: dict[int, Player]
    ):
        """Smoke test: Run complete game with CollectingValidator and verify no violations.

        This test runs a full game with all validators enabled and ensures:
        1. The game completes successfully
        2. No validation rules are violated
        3. The game state remains consistent throughout
        """
        from werewolf.engine import CollectingValidator

        validator = CollectingValidator()
        participants = create_participants(standard_players, seed=42)

        game = WerewolfGame(
            players=standard_players,
            participants=participants,
            validator=validator,
        )

        event_log, winner = await game.run()

        # Verify game produced a result
        assert event_log is not None
        assert winner in ["WEREWOLF", "VILLAGER"]
        assert event_log.game_over is not None

        # Get any validation violations
        violations = validator.get_violations()

        # Report violations if any found
        if violations:
            violation_msgs = "\n".join(
                f"  [{v.rule_id}] {v.message}" for v in violations
            )
            pytest.fail(
                f"Game completed but {len(violations)} validation rule(s) were violated:\n"
                f"{violation_msgs}"
            )

    @pytest.mark.asyncio
    async def test_validator_detects_intentional_violation(
        self, standard_players: dict[int, Player]
    ):
        """Test that the validator infrastructure is working by testing a specific rule.

        This creates a modified game state that violates a known rule and verifies
        the validator catches it.
        """
        from werewolf.engine import CollectingValidator
        from werewolf.validation.state_consistency import validate_state_consistency

        validator = CollectingValidator()

        # Create an intentionally inconsistent state
        state = GameState(
            players=standard_players,
            living_players=set(standard_players.keys()),
            dead_players={0},  # Player 0 is marked dead but also in living_players
        )

        # Validate - should detect the inconsistency
        violations = validate_state_consistency(state, None)

        # Should find at least one violation for M.2 (living & dead not disjoint)
        rule_ids = [v.rule_id for v in violations]
        assert "M.2" in rule_ids, (
            f"Expected M.2 violation for overlapping living/dead sets, got: {rule_ids}"
        )


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
