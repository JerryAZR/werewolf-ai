# TUI Evaluation Status - 2026-02-11

## Goal
Implement interactive TUI for human players with arrow key navigation.

## Requirements
1. Arrow key selection + Enter to confirm
2. **IMPORTANT**: Game context/events visible above the menu (not hidden)
3. No screen blinking when pressing keys

## Libraries Evaluated

### 1. Pick (`pip install pick`)
- ✅ Simple one-function API
- ❌ Screen blinks on keypress (user feedback)
- ❌ Menu takes over full screen, hiding context above

### 2. Prompt Toolkit (`pip install prompt_toolkit`)
- ✅ Feature-rich dialogs
- ✅ Custom styling support
- ❌ Had import error (SelectionType not found in shortcuts)
- Needs: `radiolist_dialog` for menus

### 3. Blessed (`pip install blessed`)
- ✅ Inline menu mode preserves context above!
- ✅ Fullscreen mode for game state display
- ⚠️ Complex API, requires manual cursor management

## Demo Scripts Created

| File | Library | Status |
|------|---------|--------|
| `demo_pick.py` | Pick | Works but user dislikes blinking |
| `demo_prompt_toolkit.py` | Prompt Toolkit | Import error needs fix |
| `demo_blessed.py` | Blessed | Inline mode looks promising |

## Current Issue
Pick library causes screen blinking. Blessed inline mode may be the solution.

## Next Steps

1. **Fix prompt_toolkit import error**:
   ```python
   # Remove: from prompt_toolkit.shortcuts import SelectionType
   ```

2. **Test Blessed inline menu**:
   ```bash
   pip install blessed
   python demo_blessed.py
   ```
   The inline menu (`run_menu_inline`) should show context above the menu.

3. **Choose library** based on:
   - No blinking
   - Context visibility above menu
   - Works on Windows terminal

## Files Modified

### Created
- `src/werewolf/ui/` - TUI module (choices, prompt_session, interactive, textual_selector)
- `demo_pick.py`, `demo_prompt_toolkit.py`, `demo_blessed.py` - Library demos
- `scripts/tui_demo.py`, `scripts/run_tui_game.py` - Werewolf-specific demos
- `src/werewolf/validation/` - Comprehensive game validation

### Updated
- All handlers - Added `choices` parameter to Participant protocol
- `src/werewolf/handlers/witch_handler.py` - Multi-step prompts
- `src/werewolf/engine/night_scheduler.py` - Improved action ordering

## TUI Module Usage

```python
from werewolf.ui import InteractiveParticipant

# Human player with interactive TUI
participant = InteractiveParticipant(
    console=console,
    show_prompts=True,
)

# ChoiceSpec for structured selection
from werewolf.ui import ChoiceSpec, ChoiceType

choice = ChoiceSpec(
    type=ChoiceType.SEAT,
    title="Who do you want to banish?",
    options=[(f"Player {i}", str(i)) for i in living],
    allow_none=True,
)
```

## Notes

- Textual library (already in dependencies) didn't work reliably
- Fallback number input always works as backup
- All handlers validate responses regardless of input method
