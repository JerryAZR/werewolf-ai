#!/usr/bin/env python
"""Run a single complete game and print the full event log."""

import asyncio
import random

from werewolf.models import Player, Role, STANDARD_12_PLAYER_CONFIG, create_players_from_config
from werewolf.engine import WerewolfGame
from werewolf.ai.stub_ai import create_stub_player


def create_players_shuffled(seed: int) -> dict[int, Player]:
    """Create shuffled 12-player config."""
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
    """Deep copy players dict."""
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
    """Create stub participants."""
    return {seat: create_stub_player(seed=seed + seat) for seat in players.keys()}


async def main():
    seed = random.randint(1, 1000000)
    print(f"Running single game with seed: {seed}...")

    players = create_players_shuffled(seed=seed)
    players_copy = deep_copy_players(players)
    participants = create_participants(players_copy, seed=seed)

    game = WerewolfGame(
        players=players_copy,
        participants=participants,
        seed=seed,
    )

    event_log, winner = await game.run()

    # Print YAML-formatted event log
    print("\n" + "=" * 70)
    print("GAME EVENT LOG (seed={})".format(seed))
    print("=" * 70)

    # Get the YAML output
    yaml_output = event_log.to_yaml(include_roles=False)

    # Print the YAML (truncated for display if too long)
    lines = yaml_output.split('\n')
    if len(lines) > 100:
        print('\n'.join(lines[:100]))
        print(f"\n... ({len(lines) - 100} more lines)")
        print(f"\nFull log saved to: game_log_{seed}.yaml")
        with open(f"game_log_{seed}.yaml", "w") as f:
            f.write(yaml_output)
    else:
        print(yaml_output)

    # Print quick summary
    print("\n" + "=" * 70)
    print("QUICK SUMMARY")
    print("=" * 70)

    # Count events by type
    event_counts = {}
    for phase in event_log.phases:
        for sp in phase.subphases:
            for event in sp.events:
                etype = type(event).__name__
                event_counts[etype] = event_counts.get(etype, 0) + 1

    print(f"\nEvent counts:")
    for etype, count in sorted(event_counts.items()):
        print(f"  {etype}: {count}")

    if event_log.game_over:
        print(f"\nWinner: {event_log.game_over.winner}")
        print(f"Condition: {event_log.game_over.condition.value}")
        print(f"Final Turn: Day {event_log.game_over.final_turn_count}")


if __name__ == "__main__":
    asyncio.run(main())
