# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Python CLI game implementing Werewolf (狼人杀) with AI-powered NPC players. 12-player social deduction game with 4 Werewolves vs 8 Villager-camp players (Seer, Witch, Hunter, Guard, Ordinary Villagers).

## Commands

```bash
# Install dependencies
uv sync              # Install project
uv sync --dev        # Install with dev dependencies (pytest)

# Run tests
uv run pytest tests/                    # All tests
uv run pytest tests/test_file.py        # Single test file
uv run pytest tests/test_file.py::test_name  # Specific test

# Run the game
uv run python main.py
```

## Architecture

**Event-Sourced Design**: Game flow captured as structured events (`src/werewolf/events/game_events.py`) with timestamps and debug_info fields for AI audit trails.

**Player Identification**: Players identified by `seat` (0-11), not by name. This is the canonical identifier throughout the codebase.

**Pydantic Models**: All data models use Pydantic v2 BaseModel with `enum_values=True` for serialization.

**Event Log Hierarchy**: `GameEventLog` → `PhaseLog` (NIGHT/DAY/GAME_OVER) → `SubPhaseLog` → `GameEvent`

**12-Player Configuration**: Defined in `STANDARD_12_PLAYER_CONFIG` (src/werewolf/models/player.py:81):
- 4 Werewolves, 1 Seer, 1 Witch, 1 Hunter, 1 Guard, 4 Ordinary Villagers

## Game Rules (Critical)

- **Victory**: "Slaughter the Side" - Werewolves win if all Gods OR all Villagers die
- **Night Subphases**: WEREWOLF_ACTION → WITCH_ACTION → GUARD/SEER (parallel) → NIGHT_RESOLUTION
- **Day Subphases**: CAMPAIGN → OPT_OUT → SHERIFF_ELECTION → DEATH_RESOLUTION → DISCUSSION → VOTING → VICTORY_CHECK
- **Sheriff**: Elected Day 1 before death announcements; vote weight = 1.5
- **Night Order**: Werewolves → Witch (sees werewolf target) → Guard/Seer (parallel)
- **Guard Restriction**: Cannot guard same person twice consecutively
- **Witch**: One antidote (not usable on self), one poison (ignores guard)
- **Hidden Identity**: Eliminated players' roles are NOT revealed
- **Last Words**: Night 1 deaths only; Day deaths always have last words

## Reference Docs

- [RULES.md](RULES.md) - Complete game rules
- [PHASES.md](PHASES.md) - Detailed phase definitions and flows
- [PHASE_HANDLERS.md](PHASE_HANDLERS.md) - Handler input/output specs
- [PLAN.md](PLAN.md) - Implementation plan and testing strategy
