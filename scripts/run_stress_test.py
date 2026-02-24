#!/usr/bin/env python
"""Run N games stress test with Rich UI.

Usage:
    python scripts/run_stress_test.py 100
    python scripts/run_stress_test.py 1000
    python scripts/run_stress_test.py 1111111
"""

import asyncio
import random
import sys
from collections import Counter

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn, TimeRemainingColumn
from rich.table import Table
from rich.live import Live
from rich.panel import Panel
from rich.text import Text
from rich.box import ROUNDED

from werewolf.models import Player, create_players_from_config
from werewolf.engine import WerewolfGame, CollectingValidator
from werewolf.ai.stub_ai import create_stub_player


console = Console()


def create_players_shuffled(seed: int) -> dict[int, Player]:
    """Create a dict of players with shuffled roles from standard config."""
    rng = random.Random(seed)
    role_assignments = create_players_from_config(rng=rng)
    players = {}
    for seat, role in role_assignments:
        players[seat] = Player(seat=seat, name=f"Player {seat}", role=role)
    return players


async def run_games(num_games: int, seed_base: int | None = None):
    """Run N games and report results with Rich UI."""
    if seed_base is None:
        seed_base = random.randint(1, 1000000)

    # Header
    console.print()
    console.print(Panel.fit(
        f"[bold cyan]Werewolf AI Stress Test[/bold cyan]\n"
        f"[dim]Running [yellow]{num_games:,}[/yellow] games[/dim]",
        border_style="cyan",
    ))
    console.print(f"[dim]Seed base: {seed_base:,}[/dim]")
    console.print()

    # Stats tracking
    winners = Counter()
    violations = Counter()
    errors = []
    games_completed = 0
    games_failed = 0

    # Progress bar
    batch_size = min(100, num_games)
    total_batches = (num_games + batch_size - 1) // batch_size

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=40),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(f"[cyan]Running games...", total=num_games)

        for batch in range(total_batches):
            batch_start = batch * batch_size
            batch_end = min(batch_start + batch_size, num_games)
            batch_games = batch_end - batch_start

            tasks = []
            validators = []
            for i in range(batch_games):
                seed = seed_base + batch_start + i
                players = create_players_shuffled(seed)
                participants = {seat: create_stub_player(seed=seed + seat) for seat in players}
                validator = CollectingValidator()
                validators.append(validator)

                game = WerewolfGame(
                    players=players,
                    participants=participants,
                    validator=validator,
                    seed=seed,
                )
                tasks.append(game.run())

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result, validator in zip(results, validators):
                if isinstance(result, Exception):
                    games_failed += 1
                    errors.append(str(result)[:100])
                else:
                    event_log, winner = result
                    games_completed += 1
                    winners[winner] += 1

                    # Check for violations
                    for v in validator.get_violations():
                        violations[v.rule_id] += 1

            progress.update(task, completed=batch_end)

    # Results
    console.print()

    # Summary table
    summary_table = Table(title="[bold]Summary[/bold]", show_header=False, box=None)
    summary_table.add_column("Metric", style="cyan")
    summary_table.add_column("Value", style="white", justify="right")
    summary_table.add_row("Games Completed", f"[green]{games_completed:,}[/green]")
    summary_table.add_row("Games Failed", f"[red]{games_failed:,}[/red]" if games_failed else "[green]0[/green]")
    summary_table.add_row("Total Games", f"[yellow]{num_games:,}[/yellow]")
    console.print(summary_table)

    # Winner distribution
    if winners:
        console.print()
        winner_table = Table(title="[bold]Winner Distribution[/bold]", box=ROUNDED)
        winner_table.add_column("Team", style="cyan", justify="left")
        winner_table.add_column("Count", style="white", justify="right")
        winner_table.add_column("Percentage", style="yellow", justify="right")

        for team, count in sorted(winners.items()):
            pct = (count / games_completed) * 100
            color = "green" if team == "VILLAGER" else "red"
            winner_table.add_row(
                f"[{color}]{team}[/{color}]",
                f"[{color}]{count:,}[/{color}]",
                f"[{color}]{pct:.1f}%[/{color}]",
            )
        console.print(winner_table)

    # Violations
    if violations:
        console.print()
        violation_table = Table(title="[bold red]Validation Violations[/bold red]", box=ROUNDED)
        violation_table.add_column("Rule ID", style="yellow")
        violation_table.add_column("Count", style="white", justify="right")

        sorted_violations = sorted(violations.items(), key=lambda x: -x[1])
        for rule_id, count in sorted_violations[:15]:
            violation_table.add_row(rule_id, f"[red]{count:,}[/red]")
        if len(violations) > 15:
            violation_table.add_row("...", "...")
        console.print(violation_table)

    # Errors
    if errors:
        console.print()
        error_table = Table(title="[bold red]Errors[/bold red]", box=ROUNDED)
        error_table.add_column("Error", style="red")
        for err in errors[:10]:
            error_table.add_row(err[:80])
        if len(errors) > 10:
            error_table.add_row(f"... and {len(errors) - 10} more")
        console.print(error_table)

    # Footer
    console.print()
    if games_failed == 0 and not violations:
        console.print(Panel.fit(
            "[bold green]All tests passed![/bold green]",
            border_style="green",
        ))
    elif games_failed == 0:
        console.print(Panel.fit(
            "[bold yellow]Completed with warnings[/bold yellow]",
            border_style="yellow",
        ))
    else:
        console.print(Panel.fit(
            f"[bold red]Failed: {games_failed} games[/bold red]",
            border_style="red",
        ))
    console.print()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        console.print("[bold]Usage:[/bold] python scripts/run_stress_test.py <num_games> [seed_base]")
        console.print("[dim]Examples:[/dim]")
        console.print("  python scripts/run_stress_test.py 100")
        console.print("  python scripts/run_stress_test.py 1000")
        console.print("  python scripts/run_stress_test.py 1111111")
        console.print("  python scripts/run_stress_test.py 10000 12345")
        sys.exit(1)

    num_games = int(sys.argv[1])
    seed_base = int(sys.argv[2]) if len(sys.argv) > 2 else None

    asyncio.run(run_games(num_games, seed_base))
