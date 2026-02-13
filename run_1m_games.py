"""Run 1M games in parallel and collect errors."""

import asyncio
import random
import statistics
import sys
from collections import Counter
from typing import Optional

from werewolf.models import Player, Role, create_players_from_config
from werewolf.engine import WerewolfGame, CollectingValidator
from werewolf.ai.stub_ai import create_stub_player
from werewolf.events import GameOver
from werewolf.post_game_validator import PostGameValidator


def create_players_from_config_shuffled(seed: int | None = None) -> dict[int, Player]:
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


def deep_copy_players(players: dict[int, Player]) -> dict[int, Player]:
    """Create a deep copy of players dict to avoid shared state."""
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


async def run_single_game(seed: int, players_template: dict[int, Player]) -> dict:
    """Run a single game and return results."""
    players_copy = deep_copy_players(players_template)
    participants = create_participants(players_copy, seed=seed)
    validator = CollectingValidator()

    game = WerewolfGame(
        players=players_copy,
        participants=participants,
        validator=validator,
        seed=seed,
    )

    try:
        event_log, winner = await game.run()
        in_game_violations = validator.get_violations()

        post_game_validator = PostGameValidator(event_log)
        post_game_result = post_game_validator.validate()
        post_game_violations = post_game_result.violations

        game_over = event_log.game_over
        days = game_over.final_turn_count if game_over else 0

        return {
            "seed": seed,
            "winner": winner,
            "in_game_violations": in_game_violations,
            "post_game_violations": post_game_violations,
            "days": days,
            "error": None,
        }
    except Exception as e:
        return {
            "seed": seed,
            "winner": None,
            "in_game_violations": [],
            "post_game_violations": [],
            "days": 0,
            "error": str(e),
            "exc": e,
        }


async def run_stress_test(num_games: int, batch_size: int = 1000):
    """Run stress test with specified number of games."""
    print(f"\n{'=' * 60}")
    print(f"RUNNING {num_games:,} GAMES IN PARALLEL")
    print(f"Batch size: {batch_size:,}")
    print(f"{'=' * 60}\n")

    # Create player template once
    players_template = create_players_from_config_shuffled(seed=42)
    seed_base = random.randint(1, 10000000)

    # Track results
    winners = []
    in_game_violations_by_rule = Counter()
    post_game_violations_by_rule = Counter()
    games_completed = 0
    games_failed = 0
    errors = []

    total_batches = (num_games + batch_size - 1) // batch_size

    for batch_num in range(total_batches):
        batch_start = batch_num * batch_size
        batch_end = min(batch_start + batch_size, num_games)
        batch_games = batch_end - batch_start

        print(f"Batch {batch_num + 1}/{total_batches} ({batch_games:,} games)...", end=" ", flush=True)

        # Run batch in parallel
        tasks = []
        for i in range(batch_games):
            seed = seed_base + batch_start + i
            tasks.append(run_single_game(seed, players_template))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        for result in results:
            if isinstance(result, Exception):
                games_failed += 1
                errors.append({"type": "exception", "error": str(result)})
            else:
                if result["error"]:
                    games_failed += 1
                    errors.append({"type": "error", "seed": result["seed"], "error": result["error"], "exc": result.get("exc")})
                else:
                    games_completed += 1
                    winners.append(result["winner"])

                    # Track in-game violations by rule
                    for v in result["in_game_violations"]:
                        in_game_violations_by_rule[v.rule_id] += 1

                    # Track post-game violations by rule
                    for v in result["post_game_violations"]:
                        post_game_violations_by_rule[v.rule_id] += 1

        print(f"Done! {games_completed:,}/{num_games:,} completed, {games_failed:,} failed")

    # Generate report
    print(f"\n{'=' * 60}")
    print("STRESS TEST REPORT")
    print(f"{'=' * 60}")
    print(f"\nGames Run: {num_games:,}")
    print(f"Completed: {games_completed:,}")
    print(f"Failed: {games_failed:,}")

    # Winner distribution
    winner_counts = Counter(winners)
    print(f"\nWinner Distribution:")
    for winner, count in sorted(winner_counts.items(), key=lambda x: (x[0] is None, x[0])):
        pct = (count / num_games) * 100
        print(f"  {winner}: {count:,} ({pct:.1f}%)")

    # In-game validation violations
    print(f"\nIn-Game Validation Violations:")
    if in_game_violations_by_rule:
        for rule_id, count in sorted(in_game_violations_by_rule.items()):
            print(f"  {rule_id}: {count:,}")
    else:
        print("  None (all games valid)")

    # Post-game validation violations
    print(f"\nPost-Game Validation Violations:")
    if post_game_violations_by_rule:
        for rule_id, count in sorted(post_game_violations_by_rule.items())[:20]:  # Top 20
            print(f"  {rule_id}: {count:,}")
        if len(post_game_violations_by_rule) > 20:
            print(f"  ... and {len(post_game_violations_by_rule) - 20} more rule violations")
    else:
        print("  None (all games valid)")

    # Errors
    if errors:
        print(f"\nERRORS ({len(errors)} total):")
        error_types = Counter(e["type"] for e in errors)
        for err_type, count in error_types.items():
            print(f"  {err_type}: {count:,}")

        # Save errors to file
        print(f"\nSaving errors to errors.txt...")
        with open("errors.txt", "w") as f:
            f.write(f"Total errors: {len(errors)}\n\n")
            for i, err in enumerate(errors[:100]):  # Save first 100
                f.write(f"\n--- Error {i+1} ---\n")
                f.write(f"Type: {err['type']}\n")
                if err.get("seed"):
                    f.write(f"Seed: {err['seed']}\n")
                f.write(f"Error: {err['error']}\n")
                if err.get("exc"):
                    import traceback
                    f.write("Traceback:\n")
                    f.write(traceback.format_exc())
            if len(errors) > 100:
                f.write(f"\n... and {len(errors) - 100} more errors\n")

    print(f"\n{'=' * 60}")
    if games_failed == 0 and not in_game_violations_by_rule:
        print("SUCCESS: All games completed with no violations!")
    else:
        print(f"ISSUES FOUND: {games_failed} failures, {sum(in_game_violations_by_rule.values())} violations")
    print(f"{'=' * 60}\n")

    return {
        "games_completed": games_completed,
        "games_failed": games_failed,
        "winners": winner_counts,
        "in_game_violations": in_game_violations_by_rule,
        "post_game_violations": post_game_violations_by_rule,
        "errors": errors,
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run 1M stress tests")
    parser.add_argument("--games", type=int, default=1000000, help="Number of games to run")
    parser.add_argument("--batch", type=int, default=500, help="Batch size for parallel execution")
    args = parser.parse_args()

    print(f"\nStarting stress test: {args.games:,} games, batch size {args.batch:,}")
    results = asyncio.run(run_stress_test(args.games, args.batch))
