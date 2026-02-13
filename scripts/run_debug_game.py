#!/usr/bin/env python
"""Run a full game with DebugStubPlayer to see all prompts.

Usage:
    python scripts/run_debug_game.py [seed]
"""

import asyncio
import random

from werewolf.models import Player, create_players_from_config
from werewolf.engine import WerewolfGame
from werewolf.ai.stub_ai import DebugStubPlayer, create_debug_stub_player


def create_players_shuffled(seed):
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


async def run_debug_game(seed: int = 42):
    """Run a complete game with debug stub printing all prompts."""
    print(f"\n{'#'*70}")
    print(f"# DEBUG GAME - Seed {seed}")
    print(f"# All prompts will be printed during the game")
    print(f"{'#'*70}\n")

    # Create players
    players = create_players_shuffled(seed=seed)

    # Show role assignment
    print("\n=== ROLE ASSIGNMENTS ===")
    role_by_seat = {seat: player.role.value for seat, player in sorted(players.items())}
    for seat in sorted(players.keys()):
        print(f"  Seat {seat:2d}: {role_by_seat[seat]}")

    # Create participants with debug stubs for a few seats, regular stubs for others
    # Focus on interesting roles: Werewolf, Seer, Witch, Hunter
    # Seat 0 is Hunter, Seat 2/7/9/10 are Werewolves, Seat 1 is Witch, Seat 8 is Seer
    debug_seats = {0, 2, 8}  # Hunter, Werewolf, Seer

    participants = {}
    for seat in players.keys():
        if seat in debug_seats:
            verbose = True  # All debug seats show output
            participants[seat] = DebugStubPlayer(seat=seat, verbose=verbose)
        else:
            # Use regular stub for AI players so game is deterministic
            from werewolf.ai.stub_ai import create_stub_player
            participants[seat] = create_stub_player(seed=seed + seat)

    print("\n=== DEBUG STUB SEATS ===")
    print(f"  Seats with verbose output: {sorted(debug_seats)}")

    # Run the game
    game = WerewolfGame(
        players=players,
        participants=participants,
        seed=seed,
    )

    event_log, winner = await game.run()

    # Summary
    print(f"\n{'='*70}")
    print(f"GAME OVER")
    print(f"{'='*70}")
    print(f"Winner: {winner}")
    print(f"Total phases: {len(event_log.phases)}")
    print(f"Total deaths: {len(event_log.get_all_deaths())}")

    # Show death summary
    deaths = event_log.get_all_deaths()
    if deaths:
        print(f"\nDeaths (in order): {deaths}")

    return event_log, winner


if __name__ == "__main__":
    import sys
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 42
    asyncio.run(run_debug_game(seed))
