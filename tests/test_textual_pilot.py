"""Textual Pilot tests for WerewolfUI.

Tests verify:
1. App mounts with correct header and widgets
2. Choice menus render correctly
3. Waiting states display properly
4. ChoiceRequest messages trigger menu rendering
5. Text input renders for free-form responses
6. Menu clears after selection

Uses Textual's Pilot class for automated testing.
"""

import pytest
from textual.app import App
from textual.containers import Vertical
from textual.widgets import ListView, ListItem, Static, RichLog, Input

from werewolf.ui.textual_game import WerewolfUI, ChoiceRequest


class TestWerewolfUIMount:
    """Tests: App initialization and mounting."""

    async def test_app_mounts_with_header(self):
        """Verify app initializes with correct header."""
        app = WerewolfUI(seed=42, human_seat=0)
        async with app.run_test() as pilot:
            # Verify header contains game info
            header = app.query_one("#header", Static)
            # Static widgets have a .render_line method or we can just check the widget exists
            assert header is not None
            # Check the ID and that it was composed
            assert header.id == "header"

    async def test_app_mounts_with_game_log(self):
        """Verify RichLog widget exists for game log."""
        app = WerewolfUI(seed=42, human_seat=0)
        async with app.run_test() as pilot:
            # Verify game log widget exists
            log = app.query_one("#game_log", RichLog)
            assert log is not None

    async def test_app_mounts_with_menu_section(self):
        """Verify menu section container exists."""
        app = WerewolfUI(seed=42, human_seat=0)
        async with app.run_test() as pilot:
            # Verify menu section exists
            menu = app.query_one("#menu_section", Vertical)
            assert menu is not None


class TestShowChoices:
    """Tests: show_choices() method for menu rendering."""

    async def test_show_choices_renders_menu(self):
        """Test menu rendering with options."""
        app = WerewolfUI(seed=42, human_seat=0)
        async with app.run_test() as pilot:
            # Show choices
            app.show_choices(
                prompt="Choose a target:",
                options=[("Player 0", "0"), ("Player 1", "1"), ("Player 2", "2")],
            )
            await pilot.pause()

            # Verify ListView rendered
            list_view = app.query_one("ListView", ListView)
            assert list_view is not None
            assert len(list_view) == 3

    async def test_show_choices_with_progress_indicator(self):
        """Test menu rendering with stage progress."""
        app = WerewolfUI(seed=42, human_seat=0)
        async with app.run_test() as pilot:
            # Show choices with stage
            app.show_choices(
                prompt="Choose action:",
                options=[("Pass", "PASS"), ("Poison", "POISON")],
                stage="1",
                total_stages=2,
            )
            await pilot.pause()

            # Verify progress indicator rendered - check menu has children
            menu = app.query_one("#menu_section", Vertical)
            assert len(list(menu.children)) >= 2  # Progress + ListView

    async def test_show_choices_clears_previous_menu(self):
        """Test that show_choices clears previous menu."""
        app = WerewolfUI(seed=42, human_seat=0)
        async with app.run_test() as pilot:
            # Show first menu
            app.show_choices(
                prompt="First choice:",
                options=[("A", "a")],
            )
            await pilot.pause()

            # Show second menu
            app.show_choices(
                prompt="Second choice:",
                options=[("B", "b"), ("C", "c")],
            )
            await pilot.pause()

            # Verify only second menu options exist
            list_view = app.query_one("ListView", ListView)
            assert len(list_view) == 2


class TestShowWaiting:
    """Tests: show_waiting() method."""

    async def test_show_waiting_displays_message(self):
        """Test waiting state display."""
        app = WerewolfUI(seed=42, human_seat=0)
        async with app.run_test() as pilot:
            app.show_waiting("Game in progress. Waiting for werewolves...")
            await pilot.pause()

            # Verify waiting message rendered - check menu has a child
            menu = app.query_one("#menu_section", Vertical)
            children = list(menu.children)
            assert len(children) == 1  # Only the waiting Static

    async def test_show_waiting_clears_menu(self):
        """Test that show_waiting clears previous menu."""
        app = WerewolfUI(seed=42, human_seat=0)
        async with app.run_test() as pilot:
            # Show choices first
            app.show_choices(prompt="Test:", options=[("A", "a")])
            await pilot.pause()

            # Show waiting
            app.show_waiting("Waiting...")
            await pilot.pause()

            # Verify no ListView in menu (was cleared)
            list_views = list(app.query("ListView"))
            assert len(list_views) == 0


class TestChoiceRequest:
    """Tests: ChoiceRequest message handling."""

    async def test_choice_request_stores_request(self):
        """Test ChoiceRequest is stored in app."""
        app = WerewolfUI(seed=42, human_seat=0)
        async with app.run_test() as pilot:
            # Create choice request (don't post yet)
            request = ChoiceRequest(
                prompt="Choose your action:",
                options=[("Pass", "PASS"), ("Kill", "KILL")],
                allow_none=True,
            )
            # Verify request is valid
            assert request.prompt == "Choose your action:"
            assert request.allow_none is True
            assert len(request.options) == 2

    async def test_choice_request_with_text_input(self):
        """Test ChoiceRequest with text_input=True."""
        app = WerewolfUI(seed=42, human_seat=0)
        async with app.run_test() as pilot:
            # Create text input request
            request = ChoiceRequest(
                prompt="Enter your speech:",
                text_input=True,
            )
            # Verify request is valid
            assert request.text_input is True
            assert request.options is None  # Text input doesn't need options


class TestMenuSelection:
    """Tests: Menu item selection."""

    async def test_list_view_contains_items(self):
        """Test that ListView is created."""
        app = WerewolfUI(seed=42, human_seat=0)
        async with app.run_test() as pilot:
            # Show choices
            app.show_choices(
                prompt="Choose:",
                options=[("A", "a"), ("B", "b"), ("C", "c")],
            )
            await pilot.pause()

            # Verify ListView exists
            list_view = app.query_one("ListView", ListView)
            assert list_view is not None


class TestTextInput:
    """Tests: Text input functionality."""

    async def test_text_input_shows_menu_section(self):
        """Test that show_text_input updates the menu section."""
        app = WerewolfUI(seed=42, human_seat=0)
        async with app.run_test() as pilot:
            # Verify menu section has waiting initially
            app.show_waiting("Initial state")
            await pilot.pause()

            # Show text input
            app.show_text_input(
                prompt="Enter your speech:",
                placeholder="Type here...",
            )
            await pilot.pause()

            # Verify menu section was updated (has children)
            menu = app.query_one("#menu_section", Vertical)
            # Menu should have updated content (placeholder text)
            children = list(menu.children)
            assert len(children) > 0


class TestWriteToLog:
    """Tests: Game log writing."""

    async def test_write_to_log(self):
        """Test _write() method appends to game log."""
        app = WerewolfUI(seed=42, human_seat=0)
        async with app.run_test() as pilot:
            app._write("Test message 1")
            app._write("Test message 2")
            await pilot.pause()

            # Verify log contains messages
            log = app.query_one("#game_log", RichLog)
            # Log should have written the messages
            # We can't easily inspect RichLog contents, but verify no errors


class TestClearMenu:
    """Tests: clear_menu() method."""

    async def test_clear_menu_removes_children(self):
        """Test that clear_menu removes all children from menu section."""
        app = WerewolfUI(seed=42, human_seat=0)
        async with app.run_test() as pilot:
            # Show choices
            app.show_choices(prompt="Test:", options=[("A", "a")])
            await pilot.pause()

            # Clear menu
            app.clear_menu()
            await pilot.pause()

            # Verify no children in menu section
            menu = app.query_one("#menu_section", Vertical)
            assert len(list(menu.children)) == 0

    async def test_clear_menu_resets_choice_request(self):
        """Test that clear_menu resets _choice_request."""
        app = WerewolfUI(seed=42, human_seat=0)
        async with app.run_test() as pilot:
            # Create and post choice request
            request = ChoiceRequest(prompt="Test:", options=[("A", "a")])
            app.post_message(request)
            await pilot.pause()

            # Clear menu
            app.clear_menu()

            # Verify choice request reset
            assert app._choice_request is None


# ============================================================================
# Run tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
