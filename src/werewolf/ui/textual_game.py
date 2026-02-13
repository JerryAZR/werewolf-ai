"""Textual-based full game UI for Werewolf.

A proper terminal UI with persistent game log and interactive menus.
"""

from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.widgets import ListView, ListItem, Static, RichLog, Input
from textual import on
from textual.binding import Binding
from textual.message import Message

import asyncio
from typing import Optional

# Import for role descriptions
from enum import Enum


class Role(Enum):
    WEREWOLF = "WEREWOLF"
    SEER = "SEER"
    WITCH = "WITCH"
    HUNTER = "HUNTER"
    GUARD = "GUARD"
    ORDINARY_VILLAGER = "ORDINARY_VILLAGER"
    VILLAGER = "VILLAGER"


def reveal_role_text(seat: int, role) -> str:
    """Generate role reveal text."""
    role_descriptions = {
        "WEREWOLF": "WEREWOLF - Kill all villagers to win!",
        "SEER": "SEER - Check one player's identity each night",
        "WITCH": "WITCH - One antidote (save someone) and one poison (kill someone)",
        "HUNTER": "HUNTER - Shoot someone when you die",
        "GUARD": "GUARD - Protect one player from werewolves each night",
        "ORDINARY_VILLAGER": "ORDINARY VILLAGER - Help find and banish werewolves",
        "VILLAGER": "VILLAGER - Help find and banish werewolves",
    }
    description = role_descriptions.get(role.value, role.value)
    return f"""[bold green]Your Role:[/bold green] [bold]{role.value}[/bold]

{description}

Seat: {seat}"""


class ChoiceRequest(Message):
    """Request for player to make a choice."""
    def __init__(
        self,
        prompt: str,
        options: list[tuple[str, str]] | None = None,
        allow_none: bool = False,
        text_input: bool = False,
        stage: Optional[str] = None,
        total_stages: Optional[int] = None,
    ):
        super().__init__()
        self.prompt = prompt
        self.options = options
        self.allow_none = allow_none
        self.text_input = text_input  # If True, show text input instead of menu
        self.stage = stage  # e.g., "Step 1 of 2: Choose action"
        self.total_stages = total_stages  # Total number of stages
        self.result: Optional[str] = None
        self.ready = asyncio.Event()


class MenuItem(ListItem):
    """A selectable menu item."""
    def __init__(self, label: str, value: str):
        super().__init__()
        self.value = value
        self._label = Static(label)

    def compose(self) -> ComposeResult:
        yield self._label


class WerewolfUI(App):
    """Main game UI for Werewolf."""

    CSS = """
    WerewolfUI {
        layout: vertical;
    }

    #header {
        height: auto;
        border: solid cyan;
        padding: 1;
    }

    #game_log {
        height: 1fr;
        border: solid green;
        padding: 1;
    }

    #menu_section {
        height: auto;
        border: solid yellow;
        padding: 1;
    }

    #menu_section ListView {
        height: auto;
    }

    #menu_section ListItem {
        height: auto;
    }

    #menu_section ListItem.-highlight {
        background: $accent;
        color: $text;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", show=False),
        Binding("escape", "quit", "Quit", show=False),
    ]

    def __init__(self, seed: int, human_seat: int):
        super().__init__()
        self.seed = seed
        self.seat = human_seat
        self._choice_request: Optional[ChoiceRequest] = None
        self._current_list_view: Optional[ListView] = None
        self._current_input: Optional[Input] = None
        self._game_task: Optional[asyncio.Task] = None

    def compose(self) -> ComposeResult:
        yield Static(f"WEREWOLF - Your Seat: {self.seat} (Seed: {self.seed})", id="header")
        yield RichLog(id="game_log", highlight=True, markup=True)
        yield Vertical(id="menu_section")

    def on_mount(self) -> None:
        """Start the game."""
        # Show initial state in log
        self._write("Welcome to Werewolf!")
        self._write(f"Your seat: {self.seat}")
        self._write("")
        self._write("Game starting...")
        self._write("-" * 40)

        # Show initial waiting message
        self.show_waiting("Game in progress. Your turn will appear here.")

        # Start the game
        self._game_task = asyncio.create_task(self._run_game())

    def _write(self, text: str) -> None:
        """Write to game log."""
        try:
            log = self.query_one("#game_log", RichLog)
            log.write(text)
        except Exception:
            pass

    def clear_menu(self) -> None:
        """Clear the menu section."""
        try:
            menu = self.query_one("#menu_section", Vertical)
            menu.remove_children()
        except Exception:
            pass
        self._current_list_view = None
        self._choice_request = None

    def show_choices(self, prompt: str, options: list[tuple[str, str]], allow_none: bool = False, stage: Optional[str] = None, total_stages: Optional[int] = None) -> None:
        """Display a choice menu."""
        self.clear_menu()

        menu = self.query_one("#menu_section", Vertical)

        # Create ListView first and mount it
        list_view = ListView()
        self._current_list_view = list_view

        # Add progress indicator for multi-stage queries
        if stage or total_stages:
            if stage and total_stages:
                progress = f"[bold reverse]Step {stage}/{total_stages}: {prompt}[/bold reverse]"
            elif stage:
                progress = f"[bold reverse]{stage}: {prompt}[/bold reverse]"
            else:
                progress = f"[bold reverse]{prompt}[/bold reverse]"
            menu.mount(Static(progress))
        else:
            menu.mount(Static(f"[bold reverse]{prompt}[/bold reverse]"))

        menu.mount(Static("UP/DOWN: navigate | ENTER: select | Q: quit"))
        menu.mount(list_view)

        # Now mount items after ListView is attached
        for display, value in options:
            list_view.mount(MenuItem(display, value))

        list_view.focus()

    def show_text_input(self, prompt: str, placeholder: str = "Type your response...", default: str = "", stage: Optional[str] = None, total_stages: Optional[int] = None) -> None:
        """Display a text input prompt."""
        self.clear_menu()

        menu = self.query_one("#menu_section", Vertical)

        # Add progress indicator for multi-stage queries
        if stage or total_stages:
            if stage and total_stages:
                progress = f"[bold reverse]Step {stage}/{total_stages}: {prompt}[/bold reverse]"
            elif stage:
                progress = f"[bold reverse]{stage}: {prompt}[/bold reverse]"
            else:
                progress = f"[bold reverse]{prompt}[/bold reverse]"
            menu.mount(Static(progress))
        else:
            menu.mount(Static(f"[bold reverse]{prompt}[/bold reverse]"))

        menu.mount(Static(f"[dim]Enter text below.[/dim]"))
        menu.mount(Static(f"[dim]Press ENTER to submit. Press Q to quit.[/dim]"))

        # Mount a placeholder Static that will be replaced by input
        self._text_input_placeholder = Static(f"[yellow]{placeholder}[/yellow]")
        menu.mount(self._text_input_placeholder)

    def show_waiting(self, message: str = "Waiting for your turn...") -> None:
        """Show waiting state."""
        self.clear_menu()
        menu = self.query_one("#menu_section", Vertical)
        menu.mount(Static(f"[yellow]{message}[/yellow]"))

    def action_quit_with_confirm(self) -> None:
        """Quit the app."""
        if self._game_task:
            self._game_task.cancel()
        self.exit()

    @on(ChoiceRequest)
    def on_choice_request(self, request: ChoiceRequest) -> None:
        """Handle choice request from participant."""
        self._choice_request = request

        # Check if this is a text input request
        if request.text_input:
            self._show_text_input(request)
        else:
            self.show_choices(request.prompt, request.options, request.allow_none, request.stage, request.total_stages)

    def _show_text_input(self, request: ChoiceRequest) -> None:
        """Show text input UI."""
        self.clear_menu()

        menu = self.query_one("#menu_section", Vertical)

        # Add progress indicator for multi-stage queries
        if request.stage or request.total_stages:
            if request.stage and request.total_stages:
                progress = f"[bold reverse]Step {request.stage}/{request.total_stages}: {request.prompt}[/bold reverse]"
            elif request.stage:
                progress = f"[bold reverse]{request.stage}: {request.prompt}[/bold reverse]"
            else:
                progress = f"[bold reverse]{request.prompt}[/bold reverse]"
            menu.mount(Static(progress))
        else:
            menu.mount(Static(f"[bold reverse]{request.prompt}[/bold reverse]"))

        menu.mount(Static("[dim]Type your response and press ENTER.[/dim]"))

        # Create and mount Input widget
        input_widget = Input(
            placeholder="Type here...",
            id="text_input"
        )
        self._current_input = input_widget
        menu.mount(input_widget)
        input_widget.focus()

    @on(ListView.Selected)
    def on_select(self, event: ListView.Selected) -> None:
        """Handle selection."""
        if event.list_view is not self._current_list_view:
            return
        if self._choice_request:
            self._choice_request.result = event.item.value
            self._choice_request.ready.set()
            self.clear_menu()

    @on(Input.Submitted)
    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle text input submission."""
        if self._current_input is not event.input:
            return
        if self._choice_request:
            self._choice_request.result = event.value
            self._choice_request.ready.set()
            self.clear_menu()
            self._current_input = None
            self._current_input = None

    async def _run_game(self) -> None:
        """Run the game."""
        try:
            from werewolf.models import Player, create_players_from_config
            from werewolf.engine import WerewolfGame
            from werewolf.ai.stub_ai import create_stub_player

            # Create players
            rng = __import__('random').Random(self.seed)
            role_assignments = create_players_from_config(rng=rng)

            players = {}
            for seat, role in role_assignments:
                players[seat] = Player(
                    seat=seat,
                    name=f"Player {seat}",
                    role=role,
                )

            # Show role in the log
            self._write(f"\n{reveal_role_text(self.seat, players[self.seat].role)}")

            # Create human participant
            human_participant = TextualParticipant(self.seat, self)

            # Create all participants (human + AI)
            participants = {}
            for seat in players:
                if seat == self.seat:
                    participants[seat] = human_participant
                else:
                    participants[seat] = create_stub_player(seed=self.seed + seat)

            # Run game
            game = WerewolfGame(
                players=players,
                participants=participants,
                seed=self.seed,
            )

            event_log, winner = await game.run()

            # Show result
            self._write("")
            self._write("=" * 50)
            self._write("GAME OVER")
            self._write(f"Winner: {winner}")
            self._write("=" * 50)
        except asyncio.CancelledError:
            self._write("\n[yellow]Game cancelled.[/yellow]")
        except Exception as e:
            self._write(f"\n[red]Game error: {e}[/red]")
        finally:
            # Exit after a moment
            await asyncio.sleep(3)
            self.exit()


class TextualParticipant:
    """Async participant using Textual UI."""

    def __init__(self, seat: int, app: WerewolfUI):
        self.seat = seat
        self._app = app

    async def decide(
        self,
        system_prompt: str,
        user_prompt: str,
        hint: Optional[str] = None,
        choices: Optional = None,
        session: Optional = None,
    ) -> str:
        """Make a decision."""
        # Log what's happening
        self._app._write(f"\n[bold cyan]>>> YOUR TURN (Seat {self.seat})[/bold cyan]")

        # Build context
        parts = []
        if system_prompt:
            parts.append(f"INSTRUCTIONS:\n{system_prompt}")
        if user_prompt:
            parts.append(f"SITUATION:\n{user_prompt}")
        if hint:
            parts.append(f"HINT:\n{hint}")

        context = "\n\n".join(parts)
        self._app._write(context)

        # Parse choices
        options = []
        if choices and hasattr(choices, 'options'):
            for opt in choices.options:
                display = opt.display
                if opt.seat_hint and hasattr(choices, 'seat_info') and choices.seat_info:
                    display = choices.seat_info.get(opt.seat_hint, opt.display)
                options.append((display, opt.value))
            allow_none = getattr(choices, 'allow_none', False)
            prompt_text = getattr(choices, 'prompt', 'Make your choice')

            # Post message to trigger menu and wait for result
            request = ChoiceRequest(prompt_text, options, allow_none)
        else:
            # No choices provided - use text input mode for free-form responses
            # This handles nomination ("run"/"not running") and campaign speeches
            prompt_text = user_prompt.split('\n')[-1] if user_prompt else "Enter your response"
            request = ChoiceRequest(prompt_text, text_input=True)
        self._app.post_message(request)

        # Wait for user to make a choice
        await request.ready.wait()

        result = request.result
        if result is None:
            if request.text_input:
                # For text input, empty response is valid
                result = ""
            else:
                result = "-1"
        self._app._write(f"[dim]You chose: {result}[/dim]")
        return result


async def run(seed: int, human_seat: int) -> None:
    """Run the game with Textual UI."""
    app = WerewolfUI(seed, human_seat)
    await app.run_async()


if __name__ == "__main__":
    import random
    seat = random.randint(0, 11)
    seed = random.randint(1, 1000000)
    asyncio.run(run(seed, seat))
