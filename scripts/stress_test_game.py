#!/usr/bin/env python3
"""Stress test script for the Werewolf AI game.

Runs multiple full games to verify the sheriff election phases work correctly.
"""

import asyncio
import random
import sys
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from werewolf.engine import WerewolfGame
from werewolf.models import create_players_from_config


def create_players(seed: int = 42) -> dict:
    """Create players with shuffled roles."""
    rng = random.Random(seed)
    role_assignments = create_players_from_config(rng=rng)
    players = {}
    for seat, role in role_assignments:
        from werewolf.models import Player
        players[seat] = Player(
            seat=seat,
            name=f"Player {seat}",
            role=role,
        )
    return players


def create_participants(players: dict, seed: int = 42) -> dict:
    """Create stub participants for all players."""
    from werewolf.ai.stub_ai import create_stub_player
    return {seat: create_stub_player(seed=seed + seat) for seat in players.keys()}


async def run_single_game(game_id: int, seed: int) -> dict:
    """Run a single game and return statistics."""
    players = create_players(seed=seed)
    participants = create_participants(players, seed=seed)

    game = WerewolfGame(players=players, participants=participants)

    winner = None
    turns = 0
    error = None

    try:
        event_log, winner = await game.run()
        turns = event_log.final_turn_count if event_log.final_turn_count else 0
    except Exception as e:
        error = str(e)
        print(f"Game {game_id}: ERROR - {e}")

    return {
        "game_id": game_id,
        "winner": winner,
        "turns": turns,
        "error": error,
    }


async def run_stress_test(games: int = 50) -> dict:
    """Run multiple games to stress test the system."""
    print(f"Starting stress test with {games} games...")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("-" * 50)

    results = []
    errors = []
    winners = {"WEREWOLF": 0, "VILLAGER": 0, None: 0}

    for i in range(games):
        # Use a different seed for each game for variety
        seed = i * 12345 + 42

        result = await run_single_game(i + 1, seed)
        results.append(result)

        if result["error"]:
            errors.append(result)
        else:
            winners[result["winner"]] = winners.get(result["winner"], 0) + 1

        # Print progress every 10 games
        if (i + 1) % 10 == 0:
            print(f"Completed {i + 1}/{games} games...")

    # Summary
    print("-" * 50)
    print(f"Stress test complete!")
    print(f"Total games: {games}")
    print(f"Successful: {games - len(errors)}")
    print(f"Errors: {len(errors)}")
    print(f"Werewolf wins: {winners.get('WEREWOLF', 0)}")
    print(f"Villager wins: {winners.get('VILLAGER', 0)}")
    print(f"No winner: {winners.get(None, 0)}")

    if errors:
        print("\nErrors encountered:")
        for e in errors[:5]:  # Show first 5 errors
            print(f"  Game {e['game_id']}: {e['error']}")

    return {
        "total": games,
        "successful": games - len(errors),
        "errors": len(errors),
        "winners": winners,
        "error_details": errors,
    }


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Stress test the Werewolf AI game")
    parser.add_argument(
        "--games", "-g",
        type=int,
        default=50,
        help="Number of games to run (default: 50)"
    )

    args = parser.parse_args()

    results = asyncio.run(run_stress_test(args.games))

    # Return exit code based on results
    if results["errors"] > 0:
        print(f"\nStress test completed with {results['errors']} errors!")
        sys.exit(1)
    else:
        print("\nAll games completed successfully!")
        sys.exit(0)


if __name__ == "__main__":
    main()
