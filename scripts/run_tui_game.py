#!/usr/bin/env python
"""TUI Game Runner - Play Werewolf with interactive terminal UI.

This script demonstrates how to use InteractiveParticipant for human play.

Usage:
    python scripts/run_tui_game.py                    # You play all roles
    python scripts/run_tui_game.py --human-witch      # Only witch is human
    python scripts/run_tui_game.py --seed 42          # With reproducible seed
"""

import argparse
import asyncio
from typing import Optional

from rich.console import Console
from rich.theme import Theme

from werewolf.models import Player, Role, STANDARD_12_PLAYER_CONFIG
from werewolf.engine import WerewolfGame
from werewolf.ai.stub_ai import create_stub_player
from werewolf.ui import InteractiveParticipant


# Custom rich theme for the game
THEME = Theme({
    "info": "dim cyan",
    "warning": "magenta",
    "danger": "bold red",
    "success": "bold green",
    "highlight": "bold yellow",
})


def create_players() -> dict[int, Player]:
    """Create players from standard config."""
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


def create_participants(
    players: dict[int, Player],
    human_seats: set[int],
    console: Console,
) -> dict[int, Optional[object]]:
    """Create participants - human for specified seats, stub for others.

    Args:
        players: Player dict
        human_seats: Set of seats where humans play
        console: Rich console for TUI

    Returns:
        Dict mapping seat -> participant (InteractiveParticipant or StubPlayer)
    """
    participants = {}

    for seat, player in players.items():
        if seat in human_seats:
            # Human player with interactive TUI
            participants[seat] = InteractiveParticipant(
                console=console,
                show_prompts=True,
            )
        else:
            # AI player (stub)
            participants[seat] = create_stub_player(seed=42 + seat)

    return participants


async def run_game(
    human_seats: set[int],
    seed: Optional[int] = None,
) -> None:
    """Run a complete game with TUI.

    Args:
        human_seats: Seats where humans play
        seed: Optional random seed for reproducibility
    """
    console = Console(theme=THEME)

    console.print("\n[bold yellow]=== WEREWOLF - Terminal Edition ===[/bold yellow]\n")

    # Show role assignments for humans
    players = create_players()
    console.print("[bold cyan]Role Assignments:[/bold cyan]")
    for seat in sorted(human_seats):
        player = players[seat]
        role_emoji = {
            Role.WEREWOLF: "🐺",
            Role.SEER: "🔮",
            Role.WITCH: "🧪",
            Role.GUARD: "🛡️",
            Role.HUNTER: "🏹",
            Role.ORDINARY_VILLAGER: "👤",
        }.get(player.role, "?")

        console.print(f"  Seat {seat}: {role_emoji} {player.role.value}")

    console.print("\n[bold green]Press Enter to start...[/bold green]")
    input()

    # Create participants
    participants = create_participants(players, human_seats, console)

    console.print("\n[bold cyan]Game starting...[/bold cyan]\n")

    # Run the game
    game = WerewolfGame(
        players=players,
        participants=participants,
        seed=seed,
    )

    try:
        event_log, winner = await game.run()

        # Show results
        console.print("\n" + "=" * 50)
        console.print(f"[bold yellow]GAME OVER[/bold yellow]")
        console.print("=" * 50)

        if winner == "WEREWOLF":
            console.print(f"[bold red]🐺 WEREWOLVES WIN! 🐺[/bold red]")
        else:
            console.print(f"[bold green]👥 VILLAGERS WIN! 👥[/bold green]")

        console.print(f"\nDuration: {event_log.game_over.final_turn_count} days")
        console.print(f"Total deaths: {len(event_log.get_all_deaths())}")

        # Show death summary
        deaths = event_log.get_all_deaths()
        if deaths:
            console.print("\n[bold cyan]Deaths:[/bold cyan]")
            for death in deaths:
                console.print(f"  Night {death.get('day', '?')}: Player {death.get('actor', '?')}")

    except KeyboardInterrupt:
        console.print("\n\n[yellow]Game cancelled by user.[/yellow]")
    except Exception as e:
        console.print(f"\n[bold red]Error: {e}[/bold red]")
        raise


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Play Werewolf with interactive terminal UI"
    )
    parser.add_argument(
        "--human-seats",
        type=str,
        default="1",
        help="Comma-separated seats where humans play (default: 1)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducible games",
    )
    parser.add_argument(
        "--all-human",
        action="store_true",
        help="All players are human",
    )

    args = parser.parse_args()

    # Parse human seats
    if args.all_human:
        human_seats = set(range(12))
    else:
        human_seats = {int(s.strip()) for s in args.human_seats.split(",")}

    # Validate seats
    for seat in human_seats:
        if seat < 0 or seat > 11:
            print(f"Error: Invalid seat {seat}. Must be 0-11.")
            return 1

    # Run the game
    asyncio.run(run_game(human_seats, args.seed))
    return 0


if __name__ == "__main__":
    exit(main())
