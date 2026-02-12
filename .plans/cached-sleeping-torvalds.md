# Consolidate Game Runners - Single Entry Point

## User Requirements

1. One "play" file and one "test" file
2. Single place where a full game is initialized, started, and finished
3. Entry point must support optional parameters for play/watch/test purposes

## Files to Keep

| File | Purpose | Why |
|------|---------|-----|
| `src/werewolf/play.py` | SINGLE ENTRY POINT | Already pyproject.toml entry point |
| `tests/test_stress_test.py` | Pytest stress tests | Already has BOTH in-game + post-game validators |
| `scripts/find_post_game_violations.py` | Violation analysis tool | Different purpose - debugging/analysis |

## Verification: `tests/test_stress_test.py` Already Has Post-Game Validation

```python
# Line 1-3: Module docstring confirms
"""Stress test: Parallel game simulation with in-game and post-game validators...
Runs multiple complete games with CollectingValidator and PostGameValidator..."""

# Line 25-28: Imports both validators
from werewolf.engine import WerewolfGame, CollectingValidator
from werewolf.post_game_validator import PostGameValidator

# Lines 466-468: Post-game validation is run for each game
post_game_validator = PostGameValidator(event_log)
post_game_result = post_game_validator.validate()
post_game_violations = post_game_result.violations
```

## Why Keep `scripts/find_post_game_violations.py`?

They serve **different purposes**:

| Aspect | Pytest (`tests/test_stress_test.py`) | Script (`scripts/find_post_game_violations.py`) |
|--------|--------------------------------------|------------------------------------------------|
| Purpose | CI validation | Debug violations |
| Behavior | Fail if violations | Report by rule |
| Output | pytest assertions | JSON + detailed analysis |
| Key feature | Parallel execution | `--seed` reproduction, `--output` JSON |
| Run scale | 50-2000 games in parallel | 500-2000 sequential games |

**The script provides unique features pytest doesn't:**
- `--seed 12345` - Reproduce a specific failing game
- `--output violations.json` - Save detailed violation data
- Violation counts by rule ID
- Game timeline reconstruction for debugging

## Files to Delete

| File | Reason |
|------|--------|
| `scripts/run_tui_game.py` | Merge into play.py |
| `scripts/stress_test_game.py` | Redundant - pytest has validators |
| `main.py` | Redundant |

## Plan

### Phase 1: Extend `src/werewolf/play.py`

Add CLI modes:

```bash
uv run werewolf                    # Interactive: human chooses seat
uv run werewolf --watch            # AI vs AI simulation
uv run werewolf --human-seats 0,1  # Multi-human
uv run werewolf --validate         # Enable validators
uv run werewolf --games 100        # Stress test N games
```

**New args:**
- `--watch` - AI vs AI simulation
- `--human-seats` - Multi-human (comma-separated)
- `--validate` - Enable validators
- `--games N` - Run N sequential games

### Phase 2: Delete Redundant Files

```bash
rm scripts/run_tui_game.py
rm scripts/stress_test_game.py
rm main.py
```

## Files After Refactoring

```
src/werewolf/play.py                    # SINGLE ENTRY POINT
scripts/find_post_game_violations.py     # Keep - debugging tool
tests/test_stress_test.py                # Single pytest file
```

## Commands

```bash
# Interactive
uv run werewolf

# AI vs AI
uv run werewolf --watch

# Multi-human
uv run werewolf --human-seats 0,1,2

# Stress test
uv run werewolf --games 100 --validate

# Violation analysis (developer tool)
uv run python scripts/find_post_game_violations.py --games 500

# Pytest
uv run pytest tests/test_stress_test.py -v
```
