#!/usr/bin/env python
"""Playable Werewolf game with human vs AI opponents.

Usage:
    werewolf           # Start interactive game
    werewolf --seed 42 # Reproducible game with seed
    werewolf --ai      # Watch AI vs AI simulation
"""

import argparse
import asyncio
import random

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from werewolf.models import Player, Role, create_players_from_config
from werewolf.engine import WerewolfGame
from werewolf.ai.stub_ai import create_stub_player
from werewolf.ui.interactive import InteractiveParticipant


def display_seat_selection(console: Console) -> int:
    """Display seat selection screen and return chosen seat."""
    console.print(Panel(
        "[bold yellow]WEREWOLF - Seat Selection[/bold yellow]\n\n"
        "Choose your seat (0-11) to join the game.\n"
        "Your role will be revealed after selection.",
        title="Werewolf AI",
        style="cyan"
    ))

    table = Table(title="Available Seats")
    table.add_column("Seat", justify="center")
    table.add_column("Status", justify="center")

    for seat in range(12):
        table.add_row(str(seat), "AI")

    console.print(table)

    while True:
        try:
            seat = Prompt.ask(
                "\n[bold]Enter your seat number (0-11)[/bold]",
                default="0",
                show_default=True
            )
            seat = int(seat.strip())
            if 0 <= seat <= 11:
                return seat
            console.print(f"[red]Please enter a number between 0 and 11[/red]")
        except (ValueError, KeyboardInterrupt):
            console.print(f"\n[red]Invalid input, please try again[/red]")


def reveal_role(console: Console, seat: int, role: Role) -> None:
    """Reveal the player's role."""
    role_descriptions = {
        Role.WEREWOLF: "WEREWOLF - Kill all villagers to win!",
        Role.SEER: "SEER - Check one player's identity each night",
        Role.WITCH: "WITCH - One antidote (save someone) and one poison (kill someone)",
        Role.HUNTER: "HUNTER - Shoot someone when you die",
        Role.GUARD: "GUARD - Protect one player from werewolves each night",
        Role.ORDINARY_VILLAGER: "ORDINARY VILLAGER - Help find and banish werewolves",
        Role.VILLAGER: "VILLAGER - Help find and banish werewolves",
    }
    description = role_descriptions.get(role, role.value)

    console.print(Panel(
        f"[bold green]Your Role:[/bold green] [bold]{role.value}[/bold]\n\n"
        f"{description}\n\n"
        f"Seat: {seat}\n\n"
        f"[dim]Keep your identity secret! Don't reveal your role during the game.[/dim]",
        title="Role Revealed",
        style="green"
    ))


def display_game_over(console: Console, winner: str, your_role: Role) -> None:
    """Display game over screen."""
    if winner == "WEREWOLF":
        if your_role == Role.WEREWOLF:
            result = "VICTORY! You are the werewolf champion!"
            style = "green"
        else:
            result = "DEFEAT! The werewolves won."
            style = "red"
    else:
        if your_role == Role.WEREWOLF:
            result = "DEFEAT! The villagers won."
            style = "red"
        else:
            result = "VICTORY! You helped save the village!"
            style = "green"

    console.print(Panel(
        f"[bold {style}]{result}[/bold {style}]\n\n"
        f"Winner: {winner}",
        title="Game Over",
        style=style
    ))


def create_players(seed: int, human_seat: int) -> dict[int, Player]:
    """Create players with shuffled roles."""
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


async def run_playable_game(seed: int, human_seat: int) -> None:
    """Run a game with human player."""
    console = Console()

    # Create players
    players = create_players(seed, human_seat)
    human_role = players[human_seat].role

    # Show role
    reveal_role(console, human_seat, human_role)

    # Create participants
    participants = {}

    for seat, player in players.items():
        if seat == human_seat:
            # Human participant
            participants[seat] = InteractiveParticipant()
        else:
            # AI participant
            participants[seat] = create_stub_player(seed=seed + seat)

    # Run game
    console.print(f"\n[bold]Starting game with seed {seed}...[/bold]\n")

    game = WerewolfGame(
        players=players,
        participants=participants,
        seed=seed,
    )

    event_log, winner = await game.run()

    # Show result
    display_game_over(console, winner, human_role)

    # Offer to show full log
    if Prompt.ask("\n[bold]View full game log?[/bold] (y/n)", default="n") in ("y", "Y"):
        console.print("\n" + str(event_log))


async def run_ai_simulation(seed: int) -> None:
    """Run a game with all AI players (for spectators)."""
    console = Console()
    console.print(f"\n[bold]Running AI simulation (seed {seed})...[/bold]\n")

    players = create_players(seed, human_seat=-1)
    participants = {
        seat: create_stub_player(seed=seed + seat)
        for seat in players.keys()
    }

    game = WerewolfGame(
        players=players,
        participants=participants,
        seed=seed,
    )

    event_log, winner = await game.run()

    console.print(Panel(
        f"[bold]Game Over[/bold]\n\n"
        f"Winner: {winner}",
        title="Result"
    ))

    console.print("\n" + str(event_log))


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Werewolf AI - A social deduction game",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducible games"
    )
    parser.add_argument(
        "--ai",
        action="store_true",
        help="Watch AI vs AI simulation (no human player)"
    )

    args = parser.parse_args()

    # Generate seed if not provided
    if args.seed is None:
        args.seed = random.randint(1, 1000000)

    # Run the game
    if args.ai:
        asyncio.run(run_ai_simulation(args.seed))
    else:
        # Interactive mode - get seat selection first
        console = Console()
        human_seat = display_seat_selection(console)
        asyncio.run(run_playable_game(args.seed, human_seat))


if __name__ == "__main__":
    main()
