#!/usr/bin/env python
"""TUI Demo - Interactive demonstration of TUI choices.

Supports TWO modes:
1. Arrow key navigation (Textual) - requires real terminal
2. Number-based input (Rich fallback) - works everywhere

Run with: uv run python scripts/tui_demo.py
"""

import sys
import io
import os
from typing import Optional

# Force UTF-8 encoding for Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from rich.console import Console
from rich.text import Text
from rich.panel import Panel
from rich.table import Table
from rich.align import Align
from rich.prompt import Prompt


def has_interactive_terminal() -> bool:
    """Check if we have a real interactive terminal."""
    # Check if stdin is a TTY
    if hasattr(sys.stdin, "isatty") and sys.stdin.isatty():
        return True
    # Check for common CI/IDE environments
    if os.environ.get("TERM") == "dumb":
        return False
    if os.environ.get("CI"):
        return False
    return False


def select_with_fallback(
    title: str,
    options: list[tuple[str, str]],
    allow_none: bool = False,
    none_label: str = "Skip / None",
) -> Optional[str]:
    """Select an option, using Textual if available, fallback to number input."""
    if has_interactive_terminal():
        try:
            from werewolf.ui.textual_selector import select_with_arrows
            result = select_with_arrows(
                title=title,
                options=options,
                allow_none=allow_none,
                none_label=none_label,
            )
            if result is not None:
                return result
        except Exception:
            pass  # Fall through to number input

    # Fallback: number input
    print(f"\n{title}\n")
    for i, (display, _) in enumerate(options):
        print(f"  [{i + 1}] {display}")
    if allow_none:
        print(f"  [{len(options) + 1}] {none_label}")

    while True:
        try:
            choice = input(f"\nEnter choice (1-{len(options) + (1 if allow_none else 0)}): ").strip()
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(options):
                    return options[idx][1]
                elif allow_none and idx == len(options):
                    return ""
            except ValueError:
                pass
            print("Invalid choice. Try again.")
        except (EOFError, KeyboardInterrupt):
            return None


def select_seat_fallback(
    title: str,
    seats: list[int],
    seat_info: Optional[dict[int, str]] = None,
    allow_none: bool = True,
) -> Optional[str]:
    """Select a player seat."""
    options = []
    for seat in seats:
        display = f"Player {seat}"
        if seat_info and seat in seat_info:
            display = f"Player {seat} ({seat_info[seat]})"
        options.append((display, str(seat)))

    return select_with_fallback(
        title=title,
        options=options,
        allow_none=allow_none,
        none_label="Skip / Pass",
    )


def confirm_yes_no_fallback(prompt: str) -> bool:
    """Yes/No confirmation with fallback."""
    if has_interactive_terminal():
        try:
            from werewolf.ui.textual_selector import confirm_yes_no
            return confirm_yes_no(prompt)
        except Exception:
            pass

    # Fallback: letter input
    while True:
        choice = input(f"{prompt} (y/n): ").strip().lower()
        if choice in ["y", "yes"]:
            return True
        elif choice in ["n", "no"]:
            return False
        # If empty (piped input), default to No
        if not choice:
            return False


def demo_voting(console: Console) -> None:
    """Demonstrate voting phase."""
    console.print("\n" + "=" * 60)
    console.print("[bold yellow]DEMO: VOTING PHASE[/bold yellow]")
    console.print("=" * 60 + "\n")

    console.print("[cyan]This demo supports:[/cyan]")
    console.print("  - Arrow keys (↑↓) + Enter [bright_green]if interactive terminal[/bright_green]")
    console.print("  - Number input (1-6) [yellow]as fallback[/yellow]\n")

    result = select_seat_fallback(
        title="Who do you want to banish?",
        seats=[1, 3, 5, 7, 9],
        seat_info={1: "Villager", 3: "Villager", 5: "Villager", 7: "Werewolf", 9: "Villager"},
        allow_none=True,
    )

    if result:
        console.print(f"\n[bold green]You voted for:[/bold green] Player {result}")
    else:
        console.print(f"\n[bold yellow]You abstained[/bold yellow]")


def demo_opt_out(console: Console) -> None:
    """Demonstrate opt-out."""
    console.print("\n" + "=" * 60)
    console.print("[bold yellow]DEMO: OPT-OUT PHASE[/bold yellow]")
    console.print("=" * 60 + "\n")

    result = confirm_yes_no_fallback("Do you want to opt out of Sheriff candidacy?")

    if result:
        console.print(f"\n[bold yellow]You chose to OPT OUT[/bold yellow]")
    else:
        console.print(f"\n[bold green]You chose to STAY in the election[/bold green]")


def demo_witch_action(console: Console) -> None:
    """Demonstrate witch action."""
    console.print("\n" + "=" * 60)
    console.print("[bold yellow]DEMO: WITCH ACTION (Multi-Step)[/bold yellow]")
    console.print("=" * 60 + "\n")

    # Step 1: Action
    action_result = select_with_fallback(
        title="Choose your action:",
        options=[
            ("Pass (do nothing)", "PASS"),
            ("Antidote (save Player 7)", "ANTIDOTE"),
            ("Poison (kill a player)", "POISON"),
        ],
        allow_none=False,
    )

    if action_result:
        console.print(f"\n[bold yellow]You chose:[/bold yellow] {action_result}")

        if action_result not in ("PASS", None):
            # Step 2: Target
            target_result = select_seat_fallback(
                title="Select target:",
                seats=[0, 1, 3, 4, 6, 7, 8, 10, 11],
                seat_info={7: "Werewolf"},
                allow_none=False,
            )

            if target_result:
                console.print(f"\n[bold green]Witch action:[/bold green] {action_result} {target_result}")
    else:
        console.print(f"\n[bold green]Witch action:[/bold green] PASS")


def demo_guard_action(console: Console) -> None:
    """Demonstrate guard action."""
    console.print("\n" + "=" * 60)
    console.print("[bold yellow]DEMO: GUARD ACTION[/bold yellow]")
    console.print("=" * 60 + "\n")

    result = select_seat_fallback(
        title="Who do you want to protect?",
        seats=[0, 1, 2, 3, 4, 5, 6, 8, 9, 10, 11],
        allow_none=True,
    )

    if result:
        console.print(f"\n[bold green]You protected:[/bold green] Player {result}")
    else:
        console.print(f"\n[bold yellow]You chose to skip[/bold yellow]")


def main():
    """Run the TUI demo."""
    console = Console()

    mode = "Arrow keys" if has_interactive_terminal() else "Number input"
    console.print(f"""
+--------------------------------------------------------------+
|                                                              |
|              WEREWOLF TUI DEMO                               |
|                                                              |
|         Detection: {mode}                                  |
|                                                              |
|  This demo works in BOTH modes!                              |
|                                                              |
|  * Arrow keys + Enter - Interactive terminal                 |
|  * Number input (1-N) - Always works                         |
|                                                              |
+--------------------------------------------------------------
""")

    try:
        demo_voting(console)
        input("\n[cyan]Press Enter to continue to opt-out phase...[/cyan]\n")

        demo_opt_out(console)
        input("\n[cyan]Press Enter to continue to witch action...[/cyan]\n")

        demo_witch_action(console)
        input("\n[cyan]Press Enter to continue to guard action...[/cyan]\n")

        demo_guard_action(console)

        console.print("""
+--------------------------------------------------------------+
|                                                              |
|                    COMPLETE!                                 |
|                                                              |
|  Try it in a real terminal for ARROW KEY support!           |
|                                                              |
|  Run: python scripts/run_tui_game.py                         |
|       to play a real game!                                  |
|                                                              |
+--------------------------------------------------------------+
""")

    except KeyboardInterrupt:
        console.print("\n\n[yellow]Demo cancelled.[/yellow]")


if __name__ == "__main__":
    main()
