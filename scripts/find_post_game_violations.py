#!/usr/bin/env python
"""Script to find and report post-game validator violations.

Usage:
    uv run python scripts/find_post_game_violations.py
    uv run python scripts/find_post_game_violations.py --seed 12345
"""

import asyncio
import random
import argparse
from datetime import datetime
from pathlib import Path

from werewolf.models import create_players_from_config
from werewolf.engine import WerewolfGame, CollectingValidator
from werewolf.ai.stub_ai import create_stub_player
from werewolf.post_game_validator import PostGameValidator
from werewolf.models.player import Player


async def run_game(seed: int) -> dict:
    """Run a single game and return details about any violations."""
    rng = random.Random(seed)
    role_assignments = create_players_from_config(rng=rng)
    players = {}
    for seat, role in role_assignments:
        players[seat] = Player(seat=seat, name=f"Player {seat}", role=role)

    participants = {seat: create_stub_player(seed=seed + seat) for seat in players}
    validator = CollectingValidator()
    game = WerewolfGame(
        players=players,
        participants=participants,
        validator=validator,
        seed=seed
    )

    event_log, winner = await game.run()

    # Run post-game validator
    pgv = PostGameValidator(event_log)
    result = pgv.validate()

    return {
        "seed": seed,
        "winner": winner,
        "condition": event_log.game_over.condition.value if event_log.game_over else None,
        "violations": [
            {
                "rule_id": v.rule_id,
                "message": v.message,
                "event_type": v.event_type,
            }
            for v in result.violations
        ],
        "event_log": event_log,
        "state": pgv.state,
    }


async def find_violations(num_games: int = 2000, output_file: str = None):
    """Find games with post-game validator violations."""
    violations_found = []

    print(f"Running {num_games} games...")
    for seed in range(num_games):
        if seed % 100 == 0:
            print(f"  Seed {seed}...")

        result = await run_game(seed)

        if result["violations"]:
            violations_found.append({
                "seed": result["seed"],
                "winner": result["winner"],
                "condition": result["condition"],
                "violations": result["violations"],
            })

    # Report
    print(f"\n{'='*60}")
    print(f"Found {len(violations_found)} games with violations")
    print(f"{'='*60}")

    # Group by rule
    by_rule: dict[str, list] = {}
    for v in violations_found:
        for violation in v["violations"]:
            rule = violation["rule_id"]
            if rule not in by_rule:
                by_rule[rule] = []
            by_rule[rule].append(v)

    print("\nViolations by rule:")
    for rule, games in sorted(by_rule.items()):
        print(f"  {rule}: {len(games)} games")

    # Detailed output
    print(f"\nDetailed violations:")
    for v in violations_found:
        print(f"\nSeed {v['seed']}:")
        print(f"  Winner: {v['winner']}, Condition: {v['condition']}")
        for violation in v["violations"]:
            print(f"  - {violation['rule_id']}: {violation['message']}")

    # Save to file if requested
    if output_file:
        import json

        # Serialize event log to dict
        def serialize(obj):
            if hasattr(obj, "model_dump"):
                return serialize(obj.model_dump())
            elif isinstance(obj, dict):
                return {k: serialize(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [serialize(i) for i in obj]
            elif hasattr(obj, "value"):  # Enum
                return obj.value
            else:
                return obj

        output = {
            "timestamp": datetime.now().isoformat(),
            "num_games": num_games,
            "violations_count": len(violations_found),
            "by_rule": {rule: len(games) for rule, games in by_rule.items()},
            "details": [
                {
                    "seed": v["seed"],
                    "winner": v["winner"],
                    "condition": v["condition"],
                    "violations": v["violations"],
                }
                for v in violations_found
            ]
        }

        with open(output_file, "w") as f:
            json.dump(output, f, indent=2)

        print(f"\nSaved to: {output_file}")

    return violations_found


async def reproduce_seed(seed: int):
    """Reproduce a specific seed and show detailed analysis."""
    print(f"\n{'='*60}")
    print(f"Reproducing seed {seed}")
    print(f"{'='*60}")

    result = await run_game(seed)

    print(f"\nWinner: {result['winner']}")
    print(f"Game over condition: {result['condition']}")

    if result["violations"]:
        print(f"\nViolations found:")
        for violation in result["violations"]:
            print(f"  - {violation['rule_id']}: {violation['message']}")

    # Show game timeline
    event_log = result["event_log"]
    state = result["state"]

    print(f"\nGame timeline:")
    for phase in event_log.phases:
        print(f"\n{phase.kind} {phase.number}:")
        for sp in phase.subphases:
            if sp.events:
                print(f"  {sp.micro_phase.value}: {len(sp.events)} events")

    print(f"\nFinal state:")
    print(f"  Werewolves alive: {state.get_werewolf_count()}")
    print(f"  Villagers alive: {state.get_ordinary_villager_count()}")
    print(f"  Gods alive: {state.get_god_count()}")
    print(f"  Living players: {sorted(state.living_players)}")


async def main():
    parser = argparse.ArgumentParser(description="Find post-game validator violations")
    parser.add_argument("--games", type=int, default=2000, help="Number of games to run")
    parser.add_argument("--seed", type=int, help="Reproduce a specific seed")
    parser.add_argument("--output", type=str, help="Save violations to JSON file")
    args = parser.parse_args()

    if args.seed:
        await reproduce_seed(args.seed)
    else:
        await find_violations(args.games, args.output)


if __name__ == "__main__":
    asyncio.run(main())
