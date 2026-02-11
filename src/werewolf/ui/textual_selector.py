"""Textual-based selector with arrow key navigation.

Provides rich interactive TUI with:
- Arrow key navigation (Up/Down)
- Enter to confirm
- Visual highlighting of selected option
"""

from typing import Optional
from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widgets import Static, ListView, ListItem, Label


class SelectionItem(ListItem):
    """A selectable item in the list."""

    def __init__(
        self,
        content: str,
        value: str,
    ):
        super().__init__(Static(content))
        self.value = value


class TextualSelectorApp(App):
    """Full-screen app for selection with arrow keys."""

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("escape", "quit", "Quit"),
    ]

    def __init__(
        self,
        title: str,
        options: list[tuple[str, str]],  # (display, value)
        allow_none: bool = False,
        none_label: str = "Skip / None",
    ):
        super().__init__()
        self._title = title
        self._options = options
        self._allow_none = allow_none
        self._none_label = none_label
        self._result: Optional[str] = None

    def compose(self) -> ComposeResult:
        yield Label(self._title)

        items = []
        for display, value in self._options:
            item = SelectionItem(
                content=display,
                value=value,
            )
            items.append(item)

        if self._allow_none:
            none_item = SelectionItem(
                content=self._none_label,
                value="",
            )
            items.append(none_item)

        yield ListView(*items)

        yield Label("Use UP/DOWN to navigate, ENTER to confirm, Q/ESC to quit")

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle selection."""
        item = event.item
        if isinstance(item, SelectionItem):
            self._result = item.value
            self.exit()

    def action_quit(self) -> None:
        """Quit the selector."""
        self._result = None
        self.exit()

    def get_result(self) -> Optional[str]:
        """Get the selected value."""
        return self._result


def select_with_arrows(
    title: str,
    options: list[tuple[str, str]],
    allow_none: bool = False,
    none_label: str = "Skip / None",
) -> Optional[str]:
    """Run a selection dialog with arrow keys.

    Args:
        title: Prompt shown above options
        options: List of (display_name, value) tuples
        allow_none: Whether to include a "None/Skip" option
        none_label: Label for the none option

    Returns:
        Selected value, or None if cancelled
    """
    app = TextualSelectorApp(
        title=title,
        options=options,
        allow_none=allow_none,
        none_label=none_label,
    )
    return app.run()


# ============================================================================
# Convenience functions for common selection patterns
# ============================================================================

def select_seat(
    title: str,
    seats: list[int],
    seat_info: Optional[dict[int, str]] = None,
    allow_none: bool = True,
) -> Optional[str]:
    """Select a player seat.

    Args:
        title: Prompt shown above options
        seats: Available seat numbers
        seat_info: Optional seat -> display info (role, etc.)
        allow_none: Allow skipping

    Returns:
        Selected seat as string, or None
    """
    options = []
    for seat in seats:
        display = f"Player {seat}"
        if seat_info and seat in seat_info:
            display = f"Player {seat} ({seat_info[seat]})"
        options.append((display, str(seat)))

    result = select_with_arrows(
        title=title,
        options=options,
        allow_none=allow_none,
        none_label="Skip / Pass",
    )
    return result


def select_action(
    title: str,
    actions: list[tuple[str, str]],
    allow_none: bool = False,
) -> Optional[str]:
    """Select an action.

    Args:
        title: Prompt shown above options
        actions: List of (display_name, value) tuples
        allow_none: Allow skipping

    Returns:
        Selected action value, or None
    """
    result = select_with_arrows(
        title=title,
        options=actions,
        allow_none=allow_none,
        none_label="Skip / Pass",
    )
    return result


def confirm_yes_no(prompt: str) -> bool:
    """Yes/No confirmation with arrow keys.

    Args:
        prompt: Question to ask

    Returns:
        True for Yes, False for No
    """
    options = [
        ("Yes", "yes"),
        ("No", "no"),
    ]
    result = select_with_arrows(
        title=prompt,
        options=options,
        allow_none=False,
    )
    return result == "yes"


__all__ = [
    "select_with_arrows",
    "select_seat",
    "select_action",
    "confirm_yes_no",
]
