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

**Handler Pattern**: Each micro-phase has a handler in `src/werewolf/handlers/` that:
1. Receives `PhaseContext` with game state
2. Queries participants (AI or human) for decisions
3. Returns `HandlerResult` with `Subphase_log` containing game events
4. Validates actions against game rules

**Handler Interface** (`src/werewolf/handlers/__init__.py`):
- `PhaseContext`: Contains phase, day, players dict, living/dead sets, night_actions, sheriff
- `HandlerResult`: Contains `subphase_log` (all events from this subphase)
- All handlers are `async` and use the `Participant` Protocol

**Handler Structure** (each handler file):
- Handler class (e.g., `WerewolfHandler`, `WitchHandler`)
- `PhaseContext` class for testing (mirrors engine-provided context)
- `HandlerResult` and `SubPhaseLog` Pydantic models
- `Participant` Protocol defining the `decide()` async method
- Private methods: `_build_prompts()`, `_parse_response()`, `_validate_action()`
- `ValidationResult` model for action validation feedback

**Night Action Accumulator**: Created fresh each night by the engine. Accumulates `kill_target`, `antidote_target`, `poison_target`, `guard_target`. Engine pre-fills persistent state (`antidote_used`, `poison_used`, `guard_prev_target`) each night. Handlers receive read-only accumulator and return events; engine updates accumulator after reading events.

**12-Player Configuration**: Defined in `STANDARD_12_PLAYER_CONFIG` (src/werewolf/models/player.py:81):

- 4 Werewolves, 1 Seer, 1 Witch, 1 Hunter, 1 Guard, 4 Ordinary Villagers

**Testing AI**: `StubPlayer` in `src/werewolf/ai/stub_ai.py` generates valid random actions for testing. Use in tests via `test_handler_stub_integration.py`.

**NOT YET IMPLEMENTED**: Game engine (`src/werewolf/engine/`) orchestrates handlers into game flow.

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

## AI Prompts

**Authoritative source**: [PROMPTS.md](PROMPTS.md) contains all AI prompts organized by phase/subphase.

Prompts are defined as module-level constants in each handler (e.g., `PROMPT_LAST_WORDS_SYSTEM`, `PROMPT_HUNTER_SHOOT_USER`). When editing prompts, edit the constants in the handler code.

**Key Response Formats**:
| Phase | Expected Response |
|-------|-------------------|
| WerewolfAction | `-1` or seat number |
| WitchAction | `PASS`, `ANTIDOTE {seat}`, `POISON {seat}` |
| GuardAction | seat, `SKIP`, `PASS`, or `-1` |
| SeerAction | seat (required, no skip) |
| Voting | seat or `None`/`abstain` |
| SheriffElection | candidate seat (required) |
| OptOut | `opt out` or `stay` |

## Reference Docs

- [RULES.md](RULES.md) - Complete game rules
- [PHASES.md](PHASES.md) - Detailed phase definitions and flows
- [PHASE_HANDLERS.md](PHASE_HANDLERS.md) - Handler input/output specs
- [PROMPTS.md](PROMPTS.md) - AI prompt templates by phase
- [PLAN.md](PLAN.md) - Implementation plan and testing strategy
