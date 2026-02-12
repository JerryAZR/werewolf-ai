#!/usr/bin/env python
"""Playable Werewolf game with human vs AI opponents.

Usage:
    werewolf                           # Interactive: human chooses seat
    werewolf --seed 42                 # Reproducible game with seed
    werewolf --watch                   # Watch AI vs AI simulation
    werewolf --human-seats 0,1,2       # Multi-human game
    werewolf --validate --games 100    # Stress test with validators
"""

import argparse
import asyncio
import random
import statistics
from collections import Counter

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from werewolf.models import Player, Role, create_players_from_config
from werewolf.engine import WerewolfGame, CollectingValidator
from werewolf.engine.validator import GameValidator
from werewolf.ai.stub_ai import create_stub_player
from werewolf.ui.interactive import InteractiveParticipant
from werewolf.post_game_validator import PostGameValidator


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


def create_players(seed: int) -> dict[int, Player]:
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


async def run_playable_game(
    seed: int,
    human_seats: set[int],
    validator: GameValidator | None = None,
) -> None:
    """Run a game with human player(s)."""
    console = Console()

    # Create players
    players = create_players(seed)

    # Show roles for human players
    for seat in human_seats:
        human_role = players[seat].role
        reveal_role(console, seat, human_role)

    # Create participants
    participants = {}

    for seat, player in players.items():
        if seat in human_seats:
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
        validator=validator,
    )

    event_log, winner = await game.run()

    # Show result (use first human's role)
    first_human = next(iter(human_seats))
    display_game_over(console, winner, players[first_human].role)

    # Offer to show full log
    if Prompt.ask("\n[bold]View full game log?[/bold] (y/n)", default="n") in ("y", "Y"):
        console.print("\n" + str(event_log))


async def run_ai_simulation(
    seed: int,
    validator: GameValidator | None = None,
    show_log: bool = True,
) -> str:
    """Run a game with all AI players (for spectators).

    Returns:
        The winner string.
    """
    console = Console()
    console.print(f"\n[bold]Running AI simulation (seed {seed})...[/bold]\n")

    players = create_players(seed)
    participants = {
        seat: create_stub_player(seed=seed + seat)
        for seat in players.keys()
    }

    game = WerewolfGame(
        players=players,
        participants=participants,
        seed=seed,
        validator=validator,
    )

    event_log, winner = await game.run()

    console.print(Panel(
        f"[bold]Game Over[/bold]\n\n"
        f"Winner: {winner}",
        title="Result"
    ))

    if show_log:
        console.print("\n" + str(event_log))

    return winner


def run_stress_test(
    num_games: int,
    seed_base: int | None = None,
) -> None:
    """Run multiple games with validators and report results.

    Args:
        num_games: Number of games to run
        seed_base: Optional seed base (uses random if not provided)
    """
    console = Console()

    if seed_base is None:
        seed_base = random.randint(1, 1000000)

    console.print(f"\n[bold]Running stress test: {num_games} games...[/bold]")
    console.print(f"Seed base: {seed_base}")
    console.print("-" * 50)

    winners = []
    in_game_violations = []
    post_game_violations = []
    errors = []

    async def run_one(game_num: int) -> dict:
        seed = seed_base + game_num
        players = create_players(seed)
        participants = {
            seat: create_stub_player(seed=seed + seat)
            for seat in players.keys()
        }
        validator = CollectingValidator()

        game = WerewolfGame(
            players=players,
            participants=participants,
            seed=seed,
            validator=validator,
        )

        try:
            event_log, winner = await game.run()

            # Collect in-game violations
            in_violations = validator.get_violations()

            # Collect post-game violations
            pgv = PostGameValidator(event_log)
            pg_result = pgv.validate()
            post_violations = pg_result.violations

            return {
                "seed": seed,
                "winner": winner,
                "in_violations": in_violations,
                "post_violations": post_violations,
                "error": None,
            }
        except Exception as e:
            return {
                "seed": seed,
                "winner": None,
                "in_violations": [],
                "post_violations": [],
                "error": str(e),
            }

    async def run_all():
        tasks = [run_one(i) for i in range(num_games)]
        return await asyncio.gather(*tasks, return_exceptions=True)

    results = asyncio.run(run_all())

    # Process results
    for result in results:
        if isinstance(result, Exception):
            errors.append({"error": str(result)})
            continue

        if result["error"]:
            errors.append(result)
        else:
            winners.append(result["winner"])
            in_game_violations.extend(result["in_violations"])
            post_game_violations.extend(result["post_violations"])

    # Print report
    console.print("=" * 60)
    console.print("STRESS TEST REPORT")
    console.print("=" * 60)
    console.print(f"\nGames run: {num_games}")
    console.print(f"Completed: {len(winners)}")
    console.print(f"Errors: {len(errors)}")

    # Winner distribution
    winner_counts = Counter(winners)
    console.print("\nWinner Distribution:")
    for winner, count in sorted(winner_counts.items(), key=lambda x: (x[0] is None, x[0])):
        pct = (count / num_games) * 100
        console.print(f"  {winner}: {count} ({pct:.1f}%)")

    # In-game violations
    in_by_rule = Counter(v.rule_id for v in in_game_violations)
    console.print("\nIn-Game Violations:")
    if in_by_rule:
        for rule_id, count in sorted(in_by_rule.items()):
            console.print(f"  {rule_id}: {count}")
    else:
        console.print("  None")

    # Post-game violations
    post_by_rule = Counter(v.rule_id for v in post_game_violations)
    console.print("\nPost-Game Violations:")
    if post_by_rule:
        for rule_id, count in sorted(post_by_rule.items()):
            console.print(f"  {rule_id}: {count}")
    else:
        console.print("  None")

    if errors:
        console.print(f"\nErrors ({len(errors)}):")
        for e in errors[:5]:
            console.print(f"  Seed {e.get('seed', '?')}: {e.get('error', 'unknown')}")

    console.print("=" * 60)


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
        "--watch",
        action="store_true",
        help="Watch AI vs AI simulation (no human player)"
    )
    parser.add_argument(
        "--human-seats",
        type=str,
        default=None,
        help="Comma-separated seats where humans play (e.g., '0,1,2')"
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Enable in-game and post-game validators"
    )
    parser.add_argument(
        "--games",
        type=int,
        default=None,
        help="Run N sequential games with validators (stress test mode)"
    )

    args = parser.parse_args()

    # Generate seed if not provided
    if args.seed is None:
        args.seed = random.randint(1, 1000000)

    # Validate args
    if args.games is not None and args.games < 1:
        print("Error: --games must be a positive integer")
        return 1

    # Parse human seats
    human_seats: set[int] = set()
    if args.human_seats:
        try:
            human_seats = {int(s.strip()) for s in args.human_seats.split(",")}
            for seat in human_seats:
                if seat < 0 or seat > 11:
                    print(f"Error: Invalid seat {seat}. Must be 0-11.")
                    return 1
        except ValueError:
            print("Error: --human-seats must be comma-separated integers (e.g., '0,1,2')")
            return 1

    # Create validator if requested
    validator: GameValidator | None = None
    if args.validate:
        validator = CollectingValidator()

    # Run the game(s)
    if args.games is not None:
        # Stress test mode
        run_stress_test(args.games, seed_base=args.seed)
    elif args.watch or len(human_seats) == 0:
        # AI vs AI mode
        asyncio.run(run_ai_simulation(args.seed, validator=validator))
    else:
        # Interactive mode with human(s)
        asyncio.run(run_playable_game(args.seed, human_seats, validator=validator))

    return 0


if __name__ == "__main__":
    exit(main())
