#!/usr/bin/env python
"""Run 1000 complete game simulations in parallel with validators.

This stress tests:
- Game engine stability under heavy load
- Validator rule coverage
- No crashes or validation violations
- Victory condition handling
"""

import asyncio
import random
import statistics
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
import multiprocessing

from werewolf.models import Player, Role, STANDARD_12_PLAYER_CONFIG, create_players_from_config
from werewolf.engine import WerewolfGame, CollectingValidator
from werewolf.ai.stub_ai import create_stub_player


def create_players_shuffled(seed: int) -> dict[int, Player]:
    """Create shuffled 12-player config with reproducible shuffling."""
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


def deep_copy_players(players: dict[int, Player]) -> dict[int, Player]:
    """Deep copy players dict to avoid shared state."""
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


def run_single_game(seed: int) -> dict:
    """Run a single game and return results."""
    players = create_players_shuffled(seed=seed)
    players_copy = deep_copy_players(players)
    participants = create_participants(players_copy, seed=seed)
    validator = CollectingValidator()

    game = WerewolfGame(
        players=players_copy,
        participants=participants,
        validator=validator,
        seed=seed,
    )

    event_log, winner = asyncio.run(game.run())
    violations = validator.get_violations()

    return {
        "seed": seed,
        "winner": winner,
        "violations": [(v.rule_id, v.message) for v in violations],
        "game_over": event_log.game_over,
        "days": event_log.game_over.final_turn_count if event_log.game_over else 0,
    }


def run_games_parallel(num_games: int, max_workers: int = None) -> dict:
    """Run games in parallel using ProcessPoolExecutor."""
    if max_workers is None:
        max_workers = max(1, multiprocessing.cpu_count() // 2)

    seed_base = random.randint(1, 1000000)
    seeds = [seed_base + i for i in range(num_games)]

    print(f"Running {num_games} games with {max_workers} workers...")
    print(f"Seed base: {seed_base}")
    print("-" * 60)

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(run_single_game, seeds))

    return results


def print_report(results: list[dict], num_games: int):
    """Print formatted stress test report."""
    print("\n" + "=" * 60)
    print("STRESS TEST REPORT - 1000 GAMES")
    print("=" * 60)

    # Count results
    winners = []
    violations_by_rule = defaultdict(list)
    games_completed = 0
    games_failed = 0
    victory_conditions = Counter()
    days_distribution = []

    for result in results:
        if isinstance(result, Exception):
            games_failed += 1
            print(f"Game failed: {result}")
        else:
            games_completed += 1
            winners.append(result["winner"])

            for rule_id, msg in result["violations"]:
                violations_by_rule[rule_id].append(msg)

            if result["game_over"] and result["game_over"].condition:
                victory_conditions[result["game_over"].condition.value] += 1
            else:
                victory_conditions["unknown"] += 1

            days_distribution.append(result["days"])

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
    total_violations = sum(len(v) for v in violations_by_rule.values())
    if violations_by_rule:
        for rule_id, msgs in sorted(violations_by_rule.items()):
            unique_msgs = len(set(msgs))
            print(f"  {rule_id}: {len(msgs)} occurrences ({unique_msgs} unique messages)")
        print(f"\n  Total: {total_violations} violations")
    else:
        print("  None (all games valid)")

    print("=" * 60)

    # Final status
    if games_failed == 0 and total_violations == 0:
        print(f"\n SUCCESS: {num_games}/1000 games completed with no violations!")
    elif games_failed == 0:
        print(f"\n WARNING: {num_games} completed but {total_violations} violations found")
    else:
        print(f"\n FAILED: {games_failed} games failed, {total_violations} violations")

    return {
        "games_completed": games_completed,
        "games_failed": games_failed,
        "total_violations": total_violations,
        "violations_by_rule": dict(violations_by_rule),
    }


if __name__ == "__main__":
    import sys

    num_games = 1000
    max_workers = max(1, multiprocessing.cpu_count() // 2)

    print(f"Starting 1000-game stress test with {max_workers} parallel workers...")

    results = run_games_parallel(num_games, max_workers=max_workers)
    report = print_report(results, num_games)

    # Exit with error code if there were failures
    if report["games_failed"] > 0 or report["total_violations"] > 0:
        sys.exit(1)
