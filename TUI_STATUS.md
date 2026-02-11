# TUI Evaluation Status - 2026-02-11

## Goal
Implement interactive TUI for human players with arrow key navigation AND automated testing support.

## Requirements
1. Arrow key selection + Enter to confirm
2. **IMPORTANT**: Game context/events visible above the menu (not hidden)
3. No screen blinking when pressing keys
4. **Must support automated testing**

## Recommendation: Textual

Textual is the best choice because:
1. Already in project dependencies
2. Native arrow key support with `ListView` widget
3. Built-in testing framework with `run_test()` and `pilot.press()`
4. Context visible above menu (no full-screen takeover)
5. No screen blinking

## Demo Scripts

| File | Description |
|------|-------------|
| [werewolf_tui_demo.py](werewolf_tui_demo.py) | **Main demo** - Multi-phase flow: voting → confirmation → result |
| [demo_textual.py](demo_textual.py) | Simple ListView example |

### Running the Demos

```bash
# Interactive mode
uv run python werewolf_tui_demo.py
uv run python demo_textual.py

# Automated tests
uv run pytest werewolf_tui_demo.py -v
uv run pytest demo_textual.py -v
```

## Textual Key Features

```python
from textual.app import App, ComposeResult
from textual.widgets import ListView, ListItem, Static
from textual import on

class MenuItem(ListItem):
    def __init__(self, label: str, value: str):
        super().__init__()
        self.value = value
        self._label = Static(label)

    def compose(self) -> ComposeResult:
        yield self._label

class MenuApp(App):
    CSS = """
    ListView {
        height: auto;
        border: solid green;
    }
    """

    def compose(self) -> ComposeResult:
        yield ListView(
            MenuItem("Player 0", "0"),
            MenuItem("Player 1", "1"),
        )

    @on(ListView.Selected)
    def on_select(self, event: ListView.Selected) -> None:
        self.exit(event.item.value)
```

## Testing with Textual

```python
import pytest

@pytest.mark.asyncio
async def test_menu_selection():
    app = MenuApp()
    async with app.run_test() as pilot:
        await pilot.press("down", "enter")
        assert app.return_value == "1"
```

## Files Modified

### Created
- [src/werewolf/ui/](src/werewolf/ui/) - TUI module (choices, prompt_session, interactive, textual_selector)
- [werewolf_tui_demo.py](werewolf_tui_demo.py) - Full multi-phase TUI demo with tests
- [demo_textual.py](demo_textual.py) - Simple Textual ListView example

### Updated
- All handlers - Added `choices` parameter to Participant protocol
- `src/werewolf/handlers/witch_handler.py` - Multi-step prompts
- `src/werewolf/engine/night_scheduler.py` - Improved action ordering

## Notes

- Textual works reliably for testing and interactive use
- Stale event handling: Track `self._current_list_view` and compare with `event.list_view is self._current_list_view`
- Fallback number input available as backup in handlers
