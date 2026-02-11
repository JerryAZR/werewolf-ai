#!/usr/bin/env python
"""Textual demo - multi-phase game flow with confirmations."""

from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.widgets import ListView, ListItem, Static, RichLog
from textual import on
from textual.binding import Binding


class MenuItem(ListItem):
    """A selectable menu item."""

    def __init__(self, label: str, value: str):
        super().__init__()
        self.value = value
        self._label = Static(label)

    def compose(self) -> ComposeResult:
        yield self._label


class WerewolfTUI(App):
    """Werewolf game TUI - multi-phase demo."""

    BINDINGS = [
        Binding("q", "quit_with_confirm", "Quit", show=False),
    ]

    CSS = """
    WerewolfTUI {
        layout: vertical;
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

    def __init__(self):
        super().__init__()
        self.selected: str | None = None
        self.phase = "voting"  # voting, confirm, result
        self._current_list_view: ListView | None = None  # Track current ListView instance

    def compose(self) -> ComposeResult:
        # Top section: Scrollable game log
        yield Static("Game History & Context", classes="header")
        yield RichLog(id="game_log", highlight=True, markup=True)

        # Bottom section: Menu (changes based on phase)
        yield Vertical(id="menu_section")

    def on_mount(self) -> None:
        """Initialize game state."""
        self._write_game_intro()
        self._show_voting_menu()

    # ========================================================================
    # Game Log Writing
    # ========================================================================

    def _write(self, text: str) -> None:
        """Write to game log."""
        log = self.query_one("#game_log", RichLog)
        log.write(text)

    def _write_game_intro(self) -> None:
        """Write initial game state."""
        self._write(
            """[bold green]WEREWOLF - Night 3[/bold green]
[yellow]═══════════════════════════════════════[/yellow]

[bold]Players Alive (10):[/bold] 0, 1, 3, 4, 5, 7, 8, 9, 10, 11
[bold]Players Dead (2):[/bold] 2 (Werewolf), 6 (Ordinary Villager)
[bold]Sheriff:[/bold] Player 5 (1.5x vote weight)

[bold yellow]═══════════════════════════════════════[/bold yellow]
[bold]Night 1 → Day 1[/bold]
  - Player 2 was killed by Werewolves
  - Sheriff elected: Player 5
  - Player 6 was banished (vote: 5-3-2)

[bold yellow]═══════════════════════════════════════[/bold yellow]
[bold]Night 2 → Day 2[/bold]
  - Player 8 was killed by Werewolves
  - Player 10 was banished (vote: unanimous)

[bold yellow]═══════════════════════════════════════[/bold yellow]
[bold]Night 3 → Day 3 (CURRENT)[/bold]
  - Player 7 was killed by Werewolves
  - Player 7's last words: "Player 3 is the Seer!"
"""
        )

    # ========================================================================
    # Menu Phase 1: Voting
    # ========================================================================

    def _show_voting_menu(self) -> None:
        """Show the voting menu."""
        self.phase = "voting"
        menu = self.query_one("#menu_section", Vertical)
        menu.remove_children()

        list_view = ListView(
            MenuItem("Player 0 [Ordinary Villager]", "0"),
            MenuItem("Player 1 [Ordinary Villager]", "1"),
            MenuItem("Player 3 [Seer]", "3"),
            MenuItem("Player 4 [Witch]", "4"),
            MenuItem("Player 11 [Hunter]", "11"),
            MenuItem("Skip / Abstain", "-1"),
        )
        self._current_list_view = list_view  # Track this ListView

        menu.mount(Static("[bold reverse]VOTING PHASE[/bold reverse]\nWho do you want to banish?", classes="prompt"))
        menu.mount(Static("UP/DOWN: navigate | ENTER: select | Q: quit", classes="hint"))
        menu.mount(list_view)

        list_view.focus()

    def _focus_menu(self) -> None:
        """Focus the menu."""
        if self._current_list_view is not None and self._current_list_view.is_attached:
            self._current_list_view.focus()
        else:
            try:
                self.query_one(ListView).focus()
            except:
                pass

    @on(ListView.Selected)
    def on_vote_selected(self, event: ListView.Selected) -> None:
        """Handle voting selection - only processes if this is the active ListView."""
        # Primary check: must be the current ListView
        if event.list_view is not self._current_list_view:
            return

        # Secondary check: must be in voting phase
        if self.phase != "voting":
            return

        self.selected = event.item.value
        self._write(f"\n[bold cyan]You voted for: Player {self.selected}[/bold cyan]")
        self._show_confirm_dialog()

    # ========================================================================
    # Menu Phase 2: Confirmation
    # ========================================================================

    def _show_confirm_dialog(self) -> None:
        """Show confirmation dialog."""
        self.phase = "confirm"
        menu = self.query_one("#menu_section", Vertical)
        menu.remove_children()

        list_view = ListView(
            MenuItem("[CONFIRM] Yes, banish this player", "confirm"),
            MenuItem("[CANCEL] No, let me choose again", "cancel"),
        )
        self._current_list_view = list_view  # Track this ListView

        menu.mount(
            Static(
                f"""[bold red]═══════════════════════════════════════[/bold red]
[bold reverse]CONFIRM YOUR VOTE[/bold reverse]

You selected: Player {self.selected}

Is this your final vote?""",
                classes="prompt",
            )
        )
        menu.mount(Static("UP/DOWN: navigate | ENTER: confirm | Q: cancel", classes="hint"))
        menu.mount(list_view)

        # Focus immediately on Confirm (first item)
        list_view.focus()

    @on(ListView.Selected)
    def on_confirm_selected(self, event: ListView.Selected) -> None:
        """Handle confirmation - only processes if this is the active ListView."""
        # Primary check: must be the current ListView
        if event.list_view is not self._current_list_view:
            return

        # Secondary check: must be in confirm phase
        if self.phase != "confirm":
            return

        choice = event.item.value

        if choice == "confirm":
            self._write(f"\n[bold green]Vote confirmed![/bold green]")
            self._show_result()
        else:  # cancel
            self._write("\n[yellow]Vote cancelled. Returning to voting menu.[/yellow]")
            self._show_voting_menu()

    # ========================================================================
    # Menu Phase 3: Result
    # ========================================================================

    def _show_result(self) -> None:
        """Show voting result."""
        self.phase = "result"

        self._write(
            f"""[bold red]═══════════════════════════════════════[/bold red]
[bold reverse]VOTING RESULTS[/bold reverse]

Player 3: 5 votes (including Sheriff's 1.5x = 7.5 total)
Player 4: 3 votes
Player 0: 1 vote
Player 1: 1 vote
Abstain: 2 votes

[bold green]Player 3 is banished![/bold green]
Player 3's last words: "I AM the Seer! Player 4 is the Witch! They're lying!"


[bold yellow]═══════════════════════════════════════[/bold yellow]
[bold]Player 4 revealed as: WEREWOLF![bold]
[bold]GAME OVER - Villager Camp Wins![/bold]"""
        )

        self._show_goodbye()

    def _show_goodbye(self) -> None:
        """Show goodbye screen."""
        self.phase = "goodbye"
        menu = self.query_one("#menu_section", Vertical)
        menu.remove_children()
        menu.mount(
            Static(
                """[bold reverse]GAME OVER[/bold reverse]

Thanks for playing!

Press Q or Enter to quit.""",
                classes="prompt",
            )
        )
        self.call_after_refresh(self._focus_menu)

    # ========================================================================
    # Quit
    # ========================================================================

    def action_quit_with_confirm(self) -> None:
        """Quit with confirmation."""
        if self.phase in ("voting", "confirm"):
            self._show_quit_confirm()
        else:
            self.exit()

    def _show_quit_confirm(self) -> None:
        """Show quit confirmation dialog."""
        self.phase = "quit_confirm"
        menu = self.query_one("#menu_section", Vertical)
        menu.remove_children()

        list_view = ListView(
            MenuItem("[EXIT] Yes, quit the game", "quit"),
            MenuItem("[STAY] No, continue playing", "stay"),
        )
        self._current_list_view = list_view  # Track this ListView

        menu.mount(
            Static(
                """[bold red]═══════════════════════════════════════[/bold red]
[bold reverse]QUIT GAME?[/bold reverse]

Are you sure you want to quit?""",
                classes="prompt",
            )
        )
        menu.mount(Static("UP/DOWN: navigate | ENTER: select | Q: return", classes="hint"))
        menu.mount(list_view)

        # Focus immediately
        list_view.focus()

    @on(ListView.Selected)
    def on_quit_selected(self, event: ListView.Selected) -> None:
        """Handle quit confirmation - only processes if this is the active ListView."""
        # Primary check: must be the current ListView
        if event.list_view is not self._current_list_view:
            return

        # Secondary check: must be in quit_confirm phase
        if self.phase != "quit_confirm":
            return

        choice = event.item.value

        if choice == "quit":
            self._write("\n[yellow]Thanks for playing! Goodbye![/yellow]")
            self.exit()
        else:  # stay
            self._write("\n[green]Returning to game...[/green]")
            self._show_voting_menu()


# ============================================================================
# TESTS
# ============================================================================

import pytest


class TestWerewolfTUI:
    """Test cases for the Werewolf TUI."""

    @pytest.mark.asyncio
    async def test_initial_phase(self):
        """Test initial voting phase."""
        app = WerewolfTUI()
        async with app.run_test() as pilot:
            await pilot.pause()
            # Verify menu exists with 6 items
            menu = app.query_one(ListView)
            assert len(menu.children) == 6
            # Verify phase is voting
            assert app.phase == "voting"

    @pytest.mark.asyncio
    async def test_phase_transitions(self):
        """Test that phase transitions work."""
        app = WerewolfTUI()
        async with app.run_test() as pilot:
            await pilot.pause()
            # Manually set phase to confirm
            app.selected = "0"
            app._show_confirm_dialog()
            await pilot.pause()
            assert app.phase == "confirm"

    @pytest.mark.asyncio
    async def test_cancel_flow(self):
        """Test cancel and reselect flow."""
        app = WerewolfTUI()
        async with app.run_test() as pilot:
            await pilot.pause()
            # Set up confirm dialog
            app.selected = "0"
            app._show_confirm_dialog()
            await pilot.pause()
            # Simulate cancel
            app._write("\n[yellow]Vote cancelled.[/yellow]")
            app._show_voting_menu()
            await pilot.pause()
            assert app.phase == "voting"

    @pytest.mark.asyncio
    async def test_result_phase(self):
        """Test result display."""
        app = WerewolfTUI()
        async with app.run_test() as pilot:
            await pilot.pause()
            # Go directly to result (shows result then goodbye)
            app._show_result()
            await pilot.pause()
            # Result calls goodbye at end
            assert app.phase == "goodbye"

    @pytest.mark.asyncio
    async def test_vote_to_confirm_flow(self):
        """Test voting → confirm → result flow."""
        app = WerewolfTUI()
        async with app.run_test() as pilot:
            await pilot.pause()

            # Simulate selecting a player
            app.selected = "3"
            app._show_confirm_dialog()
            await pilot.pause()

            # Verify phase is confirm
            assert app.phase == "confirm"
            assert app._current_list_view is not None

            # Verify menu has 2 items (confirm/cancel)
            menu = app._current_list_view
            assert len(menu.children) == 2


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        if arg in ("--test", "-t"):
            sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
        elif arg in ("--help", "-h"):
            print("Usage: python werewolf_tui_demo.py [--test|-t]")
            print("  Run without args for interactive mode")
            sys.exit(0)

    print("Starting Werewolf TUI Demo...")
    print()

    app = WerewolfTUI()
    app.run()

    print("\n" + "=" * 50)
    print("Demo complete!")
