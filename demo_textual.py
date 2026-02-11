#!/usr/bin/env python
"""Textual ListView demo - context visible above menu."""

from textual.app import App, ComposeResult
from textual.widgets import ListView, ListItem, Static
from textual import on


class MenuItem(ListItem):
    """A selectable menu item."""

    def __init__(self, label: str, value: str):
        super().__init__()
        self.value = value
        self._label = Static(label)

    def compose(self) -> ComposeResult:
        yield self._label


class MenuApp(App):
    """Simple menu app."""

    CSS = """
    ListView {
        height: auto;
        border: solid green;
        padding: 0;
    }
    ListItem {
        height: auto;
        padding: 0 1;
    }
    ListItem.-highlight {
        background: $accent;
        color: $text;
    }
    """

    def __init__(self):
        super().__init__()
        self.selected: str | None = None

    def compose(self) -> ComposeResult:
        yield Static("Who do you want to banish?", id="title")
        yield ListView(
            MenuItem("Player 0 [Ordinary Villager]", "0"),
            MenuItem("Player 1 [Ordinary Villager]", "1"),
            MenuItem("Player 3 [Seer]", "3"),
            MenuItem("Player 7 [Werewolf]", "7"),
            MenuItem("Player 9 [Ordinary Villager]", "9"),
            MenuItem("Skip / Abstain", "-1"),
            id="menu",
        )

    @on(ListView.Selected)
    def on_list_selected(self, event: ListView.Selected) -> None:
        """Handle selection."""
        self.selected = event.item.value
        self.exit()


# ============================================================================
# TESTS
# ============================================================================

import pytest


class TestMenuApp:
    """Test cases for the menu app."""

    @pytest.mark.asyncio
    async def test_select_first_item(self):
        """Test selecting the first menu item."""
        app = MenuApp()
        async with app.run_test() as pilot:
            await pilot.press("enter")
            assert app.selected == "0"

    @pytest.mark.asyncio
    async def test_navigate_down(self):
        """Test navigating down to second item."""
        app = MenuApp()
        async with app.run_test() as pilot:
            await pilot.press("down", "enter")
            assert app.selected == "1"

    @pytest.mark.asyncio
    async def test_key_sequence(self):
        """Test complex key sequence."""
        app = MenuApp()
        async with app.run_test() as pilot:
            await pilot.press("down", "down", "down", "enter")
            assert app.selected == "7"

    @pytest.mark.asyncio
    async def test_check_widget_count(self):
        """Test that all menu items are rendered."""
        app = MenuApp()
        async with app.run_test() as pilot:
            menu = app.query_one("#menu", ListView)
            assert len(menu.children) == 6


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
            print("Usage: python demo_textual.py [--test|-t]")
            print("  Run without args for interactive mode")
            print("  --test / -t : Run automated tests")
            sys.exit(0)

    print("=" * 50)
    print("WEREWOLF - Night 3")
    print("=" * 50)
    print()
    print("Living: 0, 1, 3, 4, 5, 7, 8, 9, 10, 11")
    print("Dead: 2 (Werewolf)")
    print("Sheriff: Player 5 (1.5x vote)")
    print()
    print("-" * 50)
    print("UP/DOWN to navigate, ENTER to select")
    print("-" * 50)
    print()

    app = MenuApp()
    app.run()

    print("-" * 50)
    if app.selected is None:
        print("You quit (no selection)")
    else:
        print(f"You selected: Player {app.selected}")
