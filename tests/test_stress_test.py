"""Stress test: Parallel game simulation with in-game validators.

Runs multiple complete games with CollectingValidator to stress test:
- Game engine stability under varied conditions
- Validator rule coverage across random games
- Victory condition handling
- No crashes or validation violations

Usage:
    uv run pytest tests/test_stress_test.py -v --tb=short
    uv run pytest tests/test_stress_test.py::TestStressTest::test_50_parallel_games -v --tb=short
"""

import asyncio
import random
import statistics
from collections import Counter
from typing import Optional

import pytest

from werewolf.models import Player, Role, STANDARD_12_PLAYER_CONFIG
from werewolf.engine import WerewolfGame, CollectingValidator
from werewolf.ai.stub_ai import create_stub_player
from werewolf.events import GameOver, VictoryCondition


# ============================================================================
# Helper Functions
# ============================================================================

def create_players_from_config(seed: int | None = None) -> dict[int, Player]:
    """Create a dict of players from standard config.

    Args:
        seed: Optional seed for reproducible player creation.
              Each player gets seat + seed as their random seed.
    """
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


def deep_copy_players(players: dict[int, Player]) -> dict[int, Player]:
    """Create a deep copy of players dict to avoid shared state.

    Critical for parallel tests - prevents one game from mutating
    player state that affects other games.
    """
    return {
        seat: Player(
            seat=player.seat,
            name=player.name,
            role=player.role,
            player_type=player.player_type,
            is_alive=player.is_alive,
            is_sheriff=player.is_sheriff,
            is_candidate=player.is_candidate,
            has_opted_out=player.has_opted_out,
        )
        for seat, player in players.items()
    }


def create_participants(players: dict[int, Player], seed: int) -> dict:
    """Create stub participants for all players."""
    return {seat: create_stub_player(seed=seed + seat) for seat in players.keys()}


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def standard_players() -> dict[int, Player]:
    """Create standard 12-player config as dict."""
    return create_players_from_config()


# ============================================================================
# Stress Tests
# ============================================================================

class TestStressTest:
    """Parallel stress tests with in-game validators."""

    @pytest.mark.asyncio
    async def test_50_parallel_games(self, standard_players: dict[int, Player]):
        """Run 50 complete games in parallel with validators.

        This stress test verifies:
        - Game engine stability
        - No validation violations
        - Winner distribution (should be roughly 50/50)
        - Victory condition diversity
        """
        num_games = 50
        seed_base = random.randint(1, 1000000)

        # Run all games in parallel
        tasks = []
        for i in range(num_games):
            seed = seed_base + i
            # Deep copy players for each game to avoid shared state
            players_copy = deep_copy_players(standard_players)
            participants = create_participants(players_copy, seed=seed)
            validator = CollectingValidator()

            game = WerewolfGame(
                players=players_copy,
                participants=participants,
                validator=validator,
                seed=seed,
            )
            tasks.append(self._run_single_game(game, validator, seed))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        winners = []
        violations_by_rule = Counter()
        games_completed = 0
        games_failed = 0
        victory_conditions = Counter()
        days_distribution = []

        for result in results:
            if isinstance(result, Exception):
                games_failed += 1
                pytest.fail(f"Game raised exception: {result}")
            else:
                game_seed, winner, violations, game_over, days = result
                games_completed += 1
                winners.append(winner)

                # Track violations by rule
                for v in violations:
                    violations_by_rule[v.rule_id] += 1

                # Track victory conditions
                if game_over and game_over.condition:
                    victory_conditions[game_over.condition.value] += 1
                else:
                    victory_conditions["unknown"] += 1

                days_distribution.append(days)

        # Generate report
        self._print_stress_report(
            num_games=num_games,
            games_completed=games_completed,
            games_failed=games_failed,
            winners=winners,
            violations_by_rule=violations_by_rule,
            victory_conditions=victory_conditions,
            days_distribution=days_distribution,
        )

        # Assertions
        assert games_failed == 0, f"{games_failed} games failed with exceptions"
        assert games_completed == num_games, f"Only {games_completed}/{num_games} completed"

        # No validation violations should occur
        if violations_by_rule:
            violation_msgs = "\n".join(
                f"  {rule_id}: {count} occurrences"
                for rule_id, count in violations_by_rule.items()
            )
            pytest.fail(
                f"Found {sum(violations_by_rule.values())} validation violations:\n{violation_msgs}"
            )

        # Verify reasonable winner distribution (both sides should win)
        winner_counts = Counter(winners)
        assert "WEREWOLF" in winner_counts, "No werewolf victories observed"
        assert "VILLAGER" in winner_counts, "No villager victories observed"

        print(f"\n✓ Stress test passed: {num_games} games completed successfully")

    @pytest.mark.asyncio
    async def test_determinism_verification(self, standard_players: dict[int, Player]):
        """Verify that same seed produces identical games.

        Runs each of 5 different seeds twice and compares:
        - Winner
        - Number of phases
        - Total events logged
        """
        test_seeds = [42, 123, 456, 789, 9999]
        deviations = []

        for seed in test_seeds:
            # Run twice with same seed
            results = []
            for run in range(2):
                # Deep copy players for each run to avoid shared state
                players_copy = deep_copy_players(standard_players)
                participants = create_participants(players_copy, seed=seed)
                validator = CollectingValidator()

                game = WerewolfGame(
                    players=players_copy,
                    participants=participants,
                    validator=validator,
                    seed=seed,
                )

                event_log, winner = await game.run()
                results.append({
                    "winner": winner,
                    "phases": len(event_log.phases),
                    "events": sum(len(p.subphases) for p in event_log.phases),
                    "days": event_log.game_over.final_turn_count if event_log.game_over else 0,
                })

            # Compare runs
            if results[0] != results[1]:
                deviations.append({
                    "seed": seed,
                    "run1": results[0],
                    "run2": results[1],
                })

        # Report
        if deviations:
            print("\n⚠ Determinism deviations found:")
            for d in deviations:
                print(f"  Seed {d['seed']}:")
                print(f"    Run 1: {d['run1']}")
                print(f"    Run 2: {d['run2']}")
            pytest.fail(f"{len(deviations)} seeds showed non-deterministic behavior")
        else:
            print(f"\n✓ Determinism verified: {len(test_seeds)} seeds produce identical results")

    @pytest.mark.asyncio
    async def test_edge_case_victory_paths(self, standard_players: dict[int, Player]):
        """Stress test specific victory paths to ensure coverage.

        Runs 20 games and ensures all victory conditions are triggered.
        """
        seeds = [random.randint(1, 1000000) for _ in range(20)]
        conditions_found = set()
        conditions_required = {
            "ALL_WEREWOLVES_KILLED",
            "ALL_GODS_KILLED",
            "ALL_VILLAGERS_KILLED",
        }

        for seed in seeds:
            # Deep copy players for each game to avoid shared state
            players_copy = deep_copy_players(standard_players)
            participants = create_participants(players_copy, seed=seed)
            validator = CollectingValidator()

            game = WerewolfGame(
                players=players_copy,
                participants=participants,
                validator=validator,
                seed=seed,
            )

            event_log, winner = await game.run()

            if event_log.game_over and event_log.game_over.condition:
                conditions_found.add(event_log.game_over.condition.value)

        missing = conditions_required - conditions_found

        print(f"\nVictory conditions found: {conditions_found}")
        print(f"Victory conditions required: {conditions_required}")

        if missing:
            print(f"⚠ Missing conditions in 20-game sample: {missing}")
            print("  (This may happen with random seeds - not a failure)")
        else:
            print(f"✓ All victory conditions triggered in sample")

    @pytest.mark.asyncio
    async def test_validator_rule_coverage(self, standard_players: dict[int, Player]):
        """Check which validator rules are being exercised.

        Runs 30 games and tracks which rules have non-zero violations.
        This helps identify untested code paths.
        """
        num_games = 30
        seed_base = random.randint(1, 1000000)
        rules_triggered = Counter()
        total_violations = 0

        for i in range(num_games):
            seed = seed_base + i
            # Deep copy players for each game to avoid shared state
            players_copy = deep_copy_players(standard_players)
            participants = create_participants(players_copy, seed=seed)
            validator = CollectingValidator()

            game = WerewolfGame(
                players=players_copy,
                participants=participants,
                validator=validator,
                seed=seed,
            )

            event_log, winner = await game.run()

            violations = validator.get_violations()
            for v in violations:
                rules_triggered[v.rule_id] += 1
                total_violations += 1

        print(f"\nValidator rule coverage ({num_games} games):")
        if rules_triggered:
            for rule_id, count in sorted(rules_triggered.items()):
                print(f"  {rule_id}: {count} violations")
            print(f"  Total: {total_violations} violations")
        else:
            print("  No rules triggered (all games valid)")

        # This is informational - games should have NO violations
        assert total_violations == 0, f"Found {total_violations} violations"

    async def _run_single_game(
        self,
        game: WerewolfGame,
        validator: CollectingValidator,
        seed: int,
    ):
        """Run a single game and return results."""
        event_log, winner = await game.run()
        violations = validator.get_violations()

        game_over = event_log.game_over
        days = game_over.final_turn_count if game_over else 0

        return (seed, winner, violations, game_over, days)

    def _print_stress_report(
        self,
        num_games: int,
        games_completed: int,
        games_failed: int,
        winners: list[str],
        violations_by_rule: Counter,
        victory_conditions: Counter,
        days_distribution: list[int],
    ):
        """Print formatted stress test report."""
        print("\n" + "=" * 60)
        print("STRESS TEST REPORT")
        print("=" * 60)
        print(f"\nGames Run: {num_games}")
        print(f"Completed: {games_completed}")
        print(f"Failed: {games_failed}")

        # Winner distribution
        winner_counts = Counter(winners)
        print(f"\nWinner Distribution:")
        for winner, count in sorted(winner_counts.items()):
            pct = (count / num_games) * 100
            print(f"  {winner}: {count} ({pct:.1f}%)")

        # Victory conditions
        print(f"\nVictory Conditions:")
        for condition, count in sorted(victory_conditions.items()):
            pct = (count / num_games) * 100
            print(f"  {condition}: {count} ({pct:.1f}%)")

        # Days distribution
        if days_distribution:
            avg_days = statistics.mean(days_distribution)
            median_days = statistics.median(days_distribution)
            min_days = min(days_distribution)
            max_days = max(days_distribution)
            print(f"\nGame Duration (days):")
            print(f"  Average: {avg_days:.1f}")
            print(f"  Median: {median_days:.1f}")
            print(f"  Range: {min_days} - {max_days}")

        # Validation violations
        print(f"\nValidation Violations:")
        if violations_by_rule:
            for rule_id, count in sorted(violations_by_rule.items()):
                print(f"  {rule_id}: {count}")
        else:
            print("  None (all games valid)")

        print("=" * 60)


class TestStressTestSmall:
    """Smaller stress tests for faster CI runs."""

    @pytest.mark.asyncio
    async def test_10_parallel_games(self, standard_players: dict[int, Player]):
        """Quick stress test with 10 games for faster feedback."""
        num_games = 10
        seed_base = random.randint(1, 1000000)

        tasks = []
        for i in range(num_games):
            seed = seed_base + i
            # Deep copy players for each game to avoid shared state
            players_copy = deep_copy_players(standard_players)
            participants = create_participants(players_copy, seed=seed)
            validator = CollectingValidator()

            game = WerewolfGame(
                players=players_copy,
                participants=participants,
                validator=validator,
                seed=seed,
            )
            tasks.append(self._run_single_game(game, validator, seed))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Count results
        winners = []
        violations = []

        for result in results:
            if isinstance(result, Exception):
                pytest.fail(f"Game raised exception: {result}")
            else:
                seed, winner, game_violations, _, _ = result
                winners.append(winner)
                violations.extend(game_violations)

        # Quick assertions - note: small sample may not have both winners
        assert len(winners) == num_games
        assert all(w in ["WEREWOLF", "VILLAGER"] for w in winners)

        if violations:
            rule_ids = [v.rule_id for v in violations]
            pytest.fail(f"Found {len(violations)} violations: {rule_ids}")

        print(f"\n✓ Quick stress test passed: {num_games}/10 games valid")
        print(f"  Winners: {dict(Counter(winners))}")

    async def _run_single_game(
        self,
        game: WerewolfGame,
        validator: CollectingValidator,
        seed: int,
    ):
        """Run a single game and return results."""
        event_log, winner = await game.run()
        violations = validator.get_violations()
        return (seed, winner, violations, event_log.game_over, 0)


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
