"""Run a complete Werewolf game with StubPlayers and log output to file."""

import argparse
import asyncio
import json
import sys

from werewolf.models import Player, STANDARD_12_PLAYER_CONFIG
from werewolf.engine import WerewolfGame
from werewolf.ai.stub_ai import create_stub_player


def create_players_from_config() -> dict[int, Player]:
    """Create a dict of players from standard config."""
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


def create_participants(players: dict[int, Player], seed: int) -> dict:
    """Create stub participants for all players."""
    return {seat: create_stub_player(seed=seed + seat) for seat in players.keys()}


def format_event_log(log) -> str:
    """Format event log for readable output."""
    lines = []
    lines.append("=" * 60)
    lines.append("WEREWOLF GAME - COMPLETE EVENT LOG")
    lines.append("=" * 60)
    lines.append(f"\nGame ID: {log.game_id}")
    lines.append(f"Created: {log.created_at}")
    lines.append(f"Players: {log.player_count}")
    lines.append(f"\nWinner: {log.game_over.winner}")
    lines.append(f"Condition: {log.game_over.condition.value}")
    lines.append(f"Days: {log.game_over.final_turn_count}")

    lines.append("\n" + "-" * 60)
    lines.append("PHASES")
    lines.append("-" * 60)

    for phase in log.phases:
        lines.append(f"\n>>> {phase.kind.value.upper()} {phase.number}")
        for subphase in phase.subphases:
            lines.append(f"    [{subphase.micro_phase.value}]")
            for event in subphase.events:
                lines.append(f"        - {event}")

    return "\n".join(lines)


async def main():
    """Run a complete game."""
    parser = argparse.ArgumentParser(
        description="Run a Werewolf AI game simulation"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducible games. Same seed = same game. "
             "If not specified, uses natural randomness."
    )
    parser.add_argument(
        "--output",
        type=str,
        default="game_output.txt",
        help="Output file for event log (default: game_output.txt)"
    )
    args = parser.parse_args()

    print("Creating game with 12 players...")
    if args.seed is not None:
        print(f"Using seed: {args.seed} (reproducible mode)")

    players = create_players_from_config()

    # Use provided seed or generate a random one for stub players
    stub_seed = args.seed if args.seed is not None else 42
    participants = create_participants(players, seed=stub_seed)

    game = WerewolfGame(
        players=players,
        participants=participants,
        seed=args.seed,  # Pass seed to WerewolfGame for game logic determinism
    )

    print("Running game...")
    event_log, winner = await game.run()

    print(f"\nGame Over! Winner: {winner}")
    print(f"Days played: {event_log.game_over.final_turn_count}")
    print(f"Total phases: {len(event_log.phases)}")
    if args.seed is not None:
        print(f"Seed: {args.seed}")

    # Format and save to file
    output = format_event_log(event_log)

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(output)

    print(f"\nFull event log saved to {args.output}")


if __name__ == "__main__":
    asyncio.run(main())
