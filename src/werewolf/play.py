#!/usr/bin/env python
"""Playable Werewolf game with human vs AI opponents.

Usage:
    werewolf                           # Single human player (random seat) with Textual UI
    werewolf --seed 42                 # Reproducible game with seed
    werewolf --ai                      # Watch AI vs AI simulation
    werewolf --validate --games 100    # Stress test with validators
"""

import argparse
import asyncio
import logging
import random
import sys
from typing import Optional

# Enable Windows console colors
if sys.platform == "win32":
    import colorama
    colorama.init()

import statistics
from collections import Counter

from rich.console import Console
from rich.panel import Panel

from werewolf.models import Player, create_players_from_config
from werewolf.engine import WerewolfGame, CollectingValidator
from werewolf.engine.validator import GameValidator
from werewolf.ai.stub_ai import create_stub_player, create_capturing_stub_player, CapturingStubPlayer
from werewolf.post_game_validator import PostGameValidator
from werewolf.ui.textual_game import WerewolfUI


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


# Event callback for real-time display
_event_queue: asyncio.Queue = asyncio.Queue()
_display_task: Optional[asyncio.Task] = None
_display_delay: float = 0.0


def _create_event_callback(delay: float = 0.0):
    """Create an event callback that queues events for display.

    Args:
        delay: Delay in seconds between events (for watching mode)

    Returns:
        Callback function to pass to WerewolfGame
    """
    global _display_delay
    _display_delay = delay

    def callback(event):
        # Queue event for display
        _event_queue.put_nowait(event)

    return callback


async def _display_events_task(console: Console, roles_secret: dict[int, str], stop_event: asyncio.Event):
    """Background task that displays events from queue.

    Args:
        console: Rich console for output
        roles_secret: Mapping of seat to role for formatting
        stop_event: Event to signal when to stop
    """
    from werewolf.events.event_formatter import EventFormatter

    formatter = EventFormatter(roles_secret)

    while True:
        # Check stop event first - if set, drain queue then exit
        if stop_event.is_set():
            # Drain remaining events before exiting
            while not _event_queue.empty():
                try:
                    event = _event_queue.get_nowait()
                    formatted = formatter.format(event)
                    console.print(formatted)
                except asyncio.QueueEmpty:
                    break
            break

        try:
            # Wait for event with timeout to check stop_event
            event = await asyncio.wait_for(_event_queue.get(), timeout=0.1)

            # Format and print event
            formatted = formatter.format(event)
            if formatted.strip():  # Only print non-empty formatted events
                console.print(formatted)

            # Add delay between events if configured
            if _display_delay > 0:
                await asyncio.sleep(_display_delay)

        except asyncio.TimeoutError:
            # No event yet, continue waiting
            continue


async def run_ai_simulation(
    seed: int,
    validator: GameValidator | None = None,
    log_file: str | None = "game_log.txt",
    capture: bool = False,
    watch_mode: bool = False,
    delay: float = 0.0,
) -> tuple[str, list[dict] | None]:
    """Run a game with all AI players (for spectators).

    Args:
        seed: Random seed for the game
        validator: Optional game validator
        log_file: File to save event log (None to disable)
        capture: If True, use CapturingStubPlayer to capture prompts
        watch_mode: If True, display events in real-time
        delay: Delay in seconds between events (for watch mode)

    Returns:
        Tuple of (winner string, captured prompts list or None)
    """
    console = Console()

    players = create_players(seed)

    # Build role secret for event formatter
    roles_secret = {seat: player.role.value for seat, player in players.items()}

    # Set up display task for watch mode
    display_task = None
    stop_event = None
    event_callback = None

    if watch_mode:
        console.print(f"\n[bold cyan]Watching AI simulation (seed {seed})...[/bold cyan]\n")
        console.print(f"[dim]Delay between events: {delay}s[/dim]\n")
        event_callback = _create_event_callback(delay)
        stop_event = asyncio.Event()
        display_task = asyncio.create_task(
            _display_events_task(console, roles_secret, stop_event)
        )
    else:
        console.print(f"\n[bold]Running AI simulation (seed {seed})...[/bold]\n")

    # Create participants - use capturing stubs if requested
    if capture:
        capturing_stubs: dict[int, CapturingStubPlayer] = {}
        for seat in players.keys():
            capturing_stubs[seat] = create_capturing_stub_player(seat=seat, seed=seed + seat)
        participants = capturing_stubs
    else:
        participants = {
            seat: create_stub_player(seed=seed + seat)
            for seat in players.keys()
        }

    game = WerewolfGame(
        players=players,
        participants=participants,
        seed=seed,
        validator=validator,
        event_callback=event_callback,
    )

    event_log, winner = await game.run()

    # Stop display task if running
    if display_task is not None:
        # Stop display task - give a moment for events to queue, then signal stop
        stop_event.set()
        if display_task is not None:
            await display_task

    console.print(Panel(
        f"[bold]Game Over[/bold]\n\n"
        f"Winner: {winner}",
        title="Result"
    ))

    # Save event log to file
    if log_file:
        try:
            with open(log_file, "w", encoding="utf-8") as f:
                f.write(str(event_log))
            console.print(f"Event log saved to {log_file}")
        except Exception as e:
            console.print(f"[red]Failed to save log: {e}[/red]")

    # Print captured prompts if requested
    captured = None
    if capture:
        captured = []
        for seat, stub in capturing_stubs.items():
            calls = stub.get_captured_calls()
            if calls:
                captured.extend(calls)

        # Print summary of captured prompts grouped by seat
        console.print(f"\n[bold]Captured {len(captured)} decision calls:[/bold]")
        last_seat = None
        for call in captured:
            # Add clear separator between seats
            if last_seat is not None and call['seat'] != last_seat:
                console.print(f"\n[bold magenta]{'='*60}[/bold magenta]")
                console.print(f"[bold magenta]  SEAT {call['seat']}[/bold magenta]")
                console.print(f"[bold magenta]{'='*60}[/bold magenta]\n")
            last_seat = call['seat']

            console.print(f"\n--- Call #{call['call_num']} | Seat {call['seat']} ---")
            console.print(f"[cyan]Situation:[/cyan]")
            console.print(call['user_prompt'][:500] if call['user_prompt'] else "(none)")
            if call.get('choices'):
                console.print(f"[cyan]Choices:[/cyan] {len(call['choices'].get('options', []))} options")
            console.print(f"[cyan]Response:[/cyan] {call['response']}")

    return winner, captured


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
    # Configure logging
    logging.basicConfig(
        level=logging.WARNING,
        format="%(name)s: %(message)s",
    )

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
        help="Watch AI vs AI simulation with real-time event display"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.0,
        help="Delay in seconds between events when using --watch (default: 0)"
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
    parser.add_argument(
        "--ai",
        action="store_true",
        help="Run AI vs AI simulation (overrides default human mode)"
    )
    parser.add_argument(
        "--log-file",
        type=str,
        default="game_log.txt",
        help="File to save game event log (default: game_log.txt, use '' to disable)"
    )
    parser.add_argument(
        "--capture",
        action="store_true",
        help="Capture prompts for all players and print after game (for debugging human prompts)"
    )

    args = parser.parse_args()

    # Generate seed if not provided
    if args.seed is None:
        args.seed = random.randint(1, 1000000)

    # Validate args
    if args.games is not None and args.games < 1:
        print("Error: --games must be a positive integer")
        return 1

    # Create validator if requested
    validator: GameValidator | None = None
    if args.validate:
        validator = CollectingValidator()

    # Run the game(s)
    if args.games is not None:
        # Stress test mode
        run_stress_test(args.games, seed_base=args.seed)
    elif args.ai or args.watch:
        # AI vs AI mode (explicit --ai or --watch flag)
        # --watch enables real-time display, --ai runs silently
        watch_mode = args.watch
        asyncio.run(run_ai_simulation(
            args.seed,
            validator=validator,
            log_file=args.log_file,
            capture=args.capture,
            watch_mode=watch_mode,
            delay=args.delay,
        ))
    else:
        # Default: single human player with Textual UI
        random_seat = random.randint(0, 11)
        asyncio.run(WerewolfUI(args.seed, random_seat, args.log_file).run_async())

    return 0


if __name__ == "__main__":
    exit(main())
