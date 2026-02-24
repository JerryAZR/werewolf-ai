#!/usr/bin/env python
"""Run N games stress test.

Usage:
    python scripts/run_stress_test.py 100
    python scripts/run_stress_test.py 1000
    python scripts/run_stress_test.py 1111111
"""

import asyncio
import random
import sys
from collections import Counter

from werewolf.models import Player, create_players_from_config
from werewolf.engine import WerewolfGame, CollectingValidator
from werewolf.ai.stub_ai import create_stub_player
from werewolf.post_game_validator import PostGameValidator


def create_players_shuffled(seed: int) -> dict[int, Player]:
    """Create a dict of players with shuffled roles from standard config."""
    rng = random.Random(seed)
    role_assignments = create_players_from_config(rng=rng)
    players = {}
    for seat, role in role_assignments:
        players[seat] = Player(seat=seat, name=f"Player {seat}", role=role)
    return players


async def run_games(num_games: int, seed_base: int | None = None):
    """Run N games and report results."""
    if seed_base is None:
        seed_base = random.randint(1, 1000000)

    print(f"\n{'=' * 60}")
    print(f"RUNNING {num_games:,} GAMES")
    print(f"Seed base: {seed_base}")
    print(f"{'=' * 60}\n")

    winners = Counter()
    violations = Counter()
    errors = []
    games_completed = 0
    games_failed = 0

    # Run in batches to avoid memory issues
    batch_size = min(100, num_games)
    total_batches = (num_games + batch_size - 1) // batch_size

    for batch in range(total_batches):
        batch_start = batch * batch_size
        batch_end = min(batch_start + batch_size, num_games)
        batch_games = batch_end - batch_start

        print(f"Batch {batch + 1}/{total_batches} ({batch_games:,} games)...", end=" ", flush=True)

        tasks = []
        for i in range(batch_games):
            seed = seed_base + batch_start + i
            players = create_players_shuffled(seed)
            participants = {seat: create_stub_player(seed=seed + seat) for seat in players}
            validator = CollectingValidator()

            game = WerewolfGame(
                players=players,
                participants=participants,
                validator=validator,
                seed=seed,
            )
            tasks.append(game.run())

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                games_failed += 1
                errors.append(str(result))
            else:
                event_log, winner = result
                games_completed += 1
                winners[winner] += 1

                # Check for violations
                for v in validator.get_violations():
                    violations[v.rule_id] += 1

        print(f"done ({games_completed:,} completed)")

    # Report
    print(f"\n{'=' * 60}")
    print("RESULTS")
    print(f"{'=' * 60}")
    print(f"Games completed: {games_completed:,}")
    print(f"Games failed:    {games_failed:,}")

    if winners:
        print(f"\nWinner distribution:")
        for team, count in sorted(winners.items()):
            pct = (count / games_completed) * 100
            print(f"  {team}: {count:,} ({pct:.1f}%)")

    if violations:
        print(f"\nValidation violations:")
        for rule_id, count in sorted(violations.items(), key=lambda x: -x[1])[:10]:
            print(f"  {rule_id}: {count}")
        if len(violations) > 10:
            print(f"  ... and {len(violations) - 10} more")

    if errors:
        print(f"\nErrors ({len(errors)}):")
        for err in errors[:5]:
            print(f"  {err}")
        if len(errors) > 5:
            print(f"  ... and {len(errors) - 5} more")

    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/run_stress_test.py <num_games> [seed_base]")
        sys.exit(1)

    num_games = int(sys.argv[1])
    seed_base = int(sys.argv[2]) if len(sys.argv) > 2 else None

    asyncio.run(run_games(num_games, seed_base))
