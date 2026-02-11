# In-Game Validator Implementation Plan

## Overview

Implement comprehensive real-time game rule validation for the Werewolf game. The system currently has a `GameValidator` Protocol with 9 hooks, but the `CollectingValidator` (test/dev validator) is a skeleton with unimplemented methods. The goal is to create a working validation system that enforces all 76 assertions from `RULES_INDEX.md` at runtime.

## Current State

| Component | Status |
|-----------|--------|
| `GameValidator` Protocol | ✅ Defined (9 hooks) |
| `NoOpValidator` | ✅ Production-ready |
| `CollectingValidator` | ✅ Fully composed |
| `src/werewolf/validation/` | ✅ Created - 15 rule files |
| Shared `ValidationViolation`, `ValidationError` | ✅ Implemented |
| Rule implementations | ⚠️ Placeholders with TODO comments |

## Created Files

```
src/werewolf/validation/
├── __init__.py              # Exports all validators
├── types.py                 # ValidationViolation, ValidationResult, ValidationSeverity
├── exceptions.py            # ValidationError exception
├── state_consistency.py     # M.1-M.7 state invariant checks
├── initialization.py        # B.1-B.4 game initialization checks
├── victory.py              # A.1-A.5 victory condition checks
├── night_werewolf.py       # D.1-D.2 werewolf action checks
├── night_witch.py          # E.1-E.7 witch action checks
├── night_guard.py          # F.1-F.3 guard action checks
├── night_seer.py           # G.1-G.2 seer action checks
├── day_sheriff.py          # H.1-H.5 sheriff election checks
├── day_death.py            # I.1-I.9 death resolution checks
├── day_voting.py          # J.1-J.2 voting checks
├── hunter.py               # K.1-K.4 hunter action checks
├── badge_transfer.py       # L.1-L.4 badge transfer checks
├── phase_order.py          # C.1-C.15 phase ordering checks
└── event_logging.py        # N.1-N.6 event logging checks

Total: 17 files
```

## Architecture Decision

**Violation Collection Strategy:** Violations are collected silently, reported at game end
- Each validation function returns `list[ValidationViolation]`
- `CollectingValidator` collects all violations in `self._violations`
- At `on_game_over()`, all violations are returned
- `ValidationError` exception can be raised at end for fail-fast behavior
- Production uses `NoOpValidator` (zero overhead)

**Data Types:**
- `GameEvent` from `werewolf.events.game_events`
- `GameState` from `werewolf.engine.game_state`
- Imports use lazy loading in `CollectingValidator` to avoid circular imports

## Router Architecture

```
src/werewolf/validation/
    │
    ├── types.py ──────────────┐
    ├── exceptions.py ─────────┤
    ├── state_consistency.py ──┤
    ├── initialization.py ─────┤
    ├── victory.py ────────────┤
    ├── night_werewolf.py ─────┤
    ├── night_witch.py ────────┤
    ├── night_guard.py ────────┤
    ├── night_seer.py ─────────┤
    ├── day_sheriff.py ────────┤
    ├── day_death.py ──────────┤
    ├── day_voting.py ─────────┤
    ├── hunter.py ─────────────┤
    ├── badge_transfer.py ─────┤
    ├── phase_order.py ────────┤
    └── event_logging.py ──────┘
                                     │
                                     ▼
                      ┌────────────────────────┐
                      │  CollectingValidator   │
                      │  (composes all above) │
                      └───────────┬────────────┘
                                  │
                                  ▼
                      ┌────────────────────────┐
                      │  Game Engine Hooks     │
                      └────────────────────────┘
```

## Agent Work Matrix

All agents (2-15) create their own files - **no merge conflicts possible**.

| Agent | File | Rules Covered | Depends On | Status |
|-------|------|---------------|------------|--------|
| - | `types.py` | Types & exceptions | None | ✅ Done |
| - | `exceptions.py` | ValidationError | None | ✅ Done |
| - | `__init__.py` | Module exports | None | ✅ Done |
| - | `CollectingValidator` | All 9 hooks composed | All validation modules | ✅ Done |
| Agent 2 | `state_consistency.py` | M.1-M.7 | types | ⏳ Todo |
| Agent 3 | `initialization.py` | B.1-B.4 | types | ⏳ Todo |
| Agent 4 | `victory.py` | A.1-A.5 | types | ⏳ Todo |
| Agent 5 | `night_werewolf.py` | D.1-D.2 | types | ⏳ Todo |
| Agent 6 | `night_witch.py` | E.1-E.7 | types | ⏳ Todo |
| Agent 7 | `night_guard.py` | F.1-F.3 | types | ⏳ Todo |
| Agent 8 | `night_seer.py` | G.1-G.2 | types | ⏳ Todo |
| Agent 9 | `day_sheriff.py` | H.1-H.5 | types | ⏳ Todo |
| Agent 10 | `day_death.py` | I.1-I.9 | types | ⏳ Todo |
| Agent 11 | `day_voting.py` | J.1-J.2 | types | ⏳ Todo |
| Agent 12 | `hunter.py` | K.1-K.4 | types | ⏳ Todo |
| Agent 13 | `badge_transfer.py` | L.1-L.4 | types | ⏳ Todo |
| Agent 14 | `phase_order.py` | C.1-C.15 | types | ⏳ Todo |
| Agent 15 | `event_logging.py` | N.1-N.6 | types | ⏳ Todo |

## Validation Function Signature

All validation functions follow this pattern:

```python
def validate_X(event: GameEvent, state: GameState) -> list[ValidationViolation]:
    """Validate rule X. Returns violations if rule is broken."""
    violations = []
    # Check conditions
    if condition_violates_rule:
        violations.append(ValidationViolation(
            rule_id="X.Y",  # e.g., "M.1"
            category="Category Name",
            message="Human-readable description",
            severity=ValidationSeverity.ERROR,
            context={"key": "value"}
        ))
    return violations
```

## File Contents Summary

| File | Lines | Key Functions |
|------|-------|---------------|
| `types.py` | ~40 | `ValidationViolation`, `ValidationResult`, `ValidationSeverity` |
| `exceptions.py` | ~30 | `ValidationError` exception class |
| `__init__.py` | ~95 | Module exports and imports |
| `state_consistency.py` | ~85 | `validate_state_consistency()` - M.1-M.7 |
| `initialization.py` | ~50 | `validate_game_start()` - B.1-B.4 |
| `victory.py` | ~120 | `check_victory()`, `validate_victory()` - A.1-A.5 |
| `night_werewolf.py` | ~30 | `validate_werewolf_action()` - D.1-D.2 |
| `night_witch.py` | ~55 | `validate_witch_action()` - E.1-E.7 |
| `night_guard.py` | ~35 | `validate_guard_action()` - F.1-F.3 |
| `night_seer.py` | ~25 | `validate_seer_action()` - G.1-G.2 |
| `day_sheriff.py` | ~40 | `validate_sheriff_election()` - H.1-H.5 |
| `day_death.py` | ~60 | `validate_death_resolution()` - I.1-I.9 |
| `day_voting.py` | ~55 | `validate_vote()`, `validate_banishment()` - J.1-J.2 |
| `hunter.py` | ~60 | `validate_hunter_action()` - K.1-K.4 |
| `badge_transfer.py` | ~45 | `validate_badge_transfer()` - L.1-L.4 |
| `phase_order.py` | ~120 | `validate_phase_order()` - C.1-C.15 |
| `event_logging.py` | ~70 | `validate_event_logging()` - N.1-N.6 |

## Task Tool Commands

Each agent runs with this pattern:

```bash
# Example for Agent 2 (state_consistency.py)
uv run claude-code task run \
  --name "agent-state-consistency" \
  --prompt "Implement the validation rules in src/werewolf/validation/state_consistency.py.
  Refer to RULES_INDEX.md for rules M.1-M.7.
  The file already exists with a placeholder function.
  Each validation function must:
  - Take (event, state) as parameters
  - Return list[ValidationViolation]
  - Use ValidationViolation with rule_id, category, message, severity, context
  Import from: from .types import ValidationViolation, ValidationSeverity
  Import GameState from: werewolf.engine.game_state
  Import GameEvent from: werewolf.events.game_events
  Do NOT modify any other files. Write only to state_consistency.py." \
  --model haiku
```

**Agent Commands (copy-paste each):**

| Agent | Command |
|-------|---------|
| 2 | `uv run claude-code task run --name "agent-state-consistency" --prompt "Implement M.1-M.7 in state_consistency.py. Rules: M.1 living|dead union=players, M.2 living&dead disjoint, M.3 Player.is_alive matches living_players, M.4 Player.is_sheriff matches sheriff, M.6 event day valid, M.7 event actor valid. Return list[ValidationViolation]." --model haiku` |
| 3 | `uv run claude-code task run --name "agent-initialization" --prompt "Implement B.1-B.4 in initialization.py. Rules: B.1 werewolf_count > 0, B.2 villager_count > 0, B.3 god_count > 0, B.4 unique god roles." --model haiku` |
| 4 | `uv run claude-code task run --name "agent-victory" --prompt "Implement A.1-A.5 in victory.py. Rules: A.1 game ends when victory, A.2 villagers win when werewolves dead, A.3 werewolves win when villagers dead, A.4 werewolves win when gods dead, A.5 tie if both." --model haiku` |
| 5 | `uv run claude-code task run --name "agent-night-werewolf" --prompt "Implement D.1-D.2 in night_werewolf.py. Rules: D.1 werewolves cannot target dead, D.2 dead werewolves cannot act." --model haiku` |
| 6 | `uv run claude-code task run --name "agent-night-witch" --prompt "Implement E.1-E.7 in night_witch.py. Rules: E.2 max one potion, E.3 no antidote on self, E.4 no antidote if used, E.5 no poison if used, E.6 antidote overrides kill, E.7 poison ignores guard." --model haiku` |
| 7 | `uv run claude-code task run --name "agent-night-guard" --prompt "Implement F.1-F.3 in night_guard.py. Rules: F.1 cannot guard same player consecutively, F.2 guard not overridden by poison, F.3 guard works even if guard dies." --model haiku` |
| 8 | `uv run claude-code task run --name "agent-night-seer" --prompt "Implement G.1-G.2 in night_seer.py. Rules: G.1 cannot check more than one, G.2 result GOOD or WEREWOLF." --model haiku` |
| 9 | `uv run claude-code task run --name "agent-day-sheriff" --prompt "Implement H.1-H.5 in day_sheriff.py. Rules: H.1-H.2 sheriff only Day 1, H.3 Night 1 deaths eligible, H.4 candidates cannot vote, H.5 vote weight 1.5." --model haiku` |
| 10 | `uv run claude-code task run --name "agent-day-death" --prompt "Implement I.1-I.9 in day_death.py. Rules: I.1 night deaths after Sheriff, I.2 cause hidden, I.3 role/camp hidden, I.4 Night 1 last words, I.5 Night 2+ no last words, I.6 banished last words, I.7 seat order, I.8 dead no Discussion, I.9 dead no voting." --model haiku` |
| 11 | `uv run claude-code task run --name "agent-day-voting" --prompt "Implement J.1-J.2 in day_voting.py. Rules: J.1 vote target living, J.2 tie = no banishment." --model haiku` |
| 12 | `uv run claude-code task run --name "agent-hunter" --prompt "Implement K.1-K.4 in hunter.py. Rules: K.1 no activate when poisoned, K.2 cannot target dead, K.3 must shoot or SKIP, K.4 target dies immediately." --model haiku` |
| 13 | `uv run claude-code task run --name "agent-badge-transfer" --prompt "Implement L.1-L.4 in badge_transfer.py. Rules: L.1 target living, L.2 single badge, L.3 werewolf sheriff still wins, L.4 sheriff queried on death." --model haiku` |
| 14 | `uv run claude-code task run --name "agent-phase-order" --prompt "Implement C.1-C.15 in phase_order.py. Rules: C.1 Night 1 start, C.2 no consecutive Night, C.3 Sheriff before DeathResolution, C.4 Werewolf->Witch->Guard/Seer, C.5 NightResolution last, C.6 Night has Werewolf+Resolution, C.7 Campaign first Day 1, C.8 no Campaign Day 2+, C.9 OptOut after Campaign, C.10 Sheriff after OptOut, C.11 Death before Discussion, C.12 Discussion before Voting, C.13 Banishment after Voting, C.14 no Banishment on tie, C.15 max 20 days." --model haiku` |
| 15 | `uv run claude-code task run --name "agent-event-logging" --prompt "Implement N.1-N.6 in event_logging.py. Rules: N.1 every subphase SubPhaseLog, N.2 every phase PhaseLog, N.3 GameStart recorded, N.4 GameOver recorded, N.5 NightOutcome records deaths, N.6 all actions logged." --model haiku` |

**All agents can run in parallel after Phase 1 is complete.**

## Test Strategy

**Framework:** pytest (already configured in pyproject.toml)

**Test Pattern for each validator:**
```python
# tests/test_validation_<category>.py
import pytest
from werewolf.validation import validate_X
from werewolf.engine.game_state import GameState
from werewolf.events.game_events import SomeEvent

def test_rule_Y_valid():
    """Test that valid actions pass."""
    state = create_valid_state()
    event = create_valid_event()
    violations = validate_X(event, state)
    assert violations == []

def test_rule_Y_invalid():
    """Test that invalid actions are caught."""
    state = create_invalid_state()
    event = create_invalid_event()
    violations = validate_X(event, state)
    assert len(violations) > 0
    assert violations[0].rule_id == "Y.Z"
```

**Fixtures needed:**
- `create_test_game_state()` - creates GameState with specific configurations
- `create_test_event()` - creates events for testing
- Stub players for integration tests

**Integration test:**
- Run a full game with `CollectingValidator`
- Verify no violations are collected

## Key Principles

1. **No merge conflicts**: Each agent creates their own file
2. **True parallelism**: 14 agents can work simultaneously after Phase 1
3. **Single responsibility**: One file per rule category
4. **Easy testing**: Test each validator in isolation
5. **Easy debugging**: Violations include rule_id for file lookup

## Dependencies

**Validation files (Agents 2-15):** Each only imports from:
- `from .types import ValidationViolation, ValidationSeverity`
- `from werewolf.engine.game_state import GameState`
- `from werewolf.events.game_events import GameEvent`

**CollectingValidator:** Uses lazy imports to avoid circular imports - imports validation modules inside each method.

**No inter-dependencies between validation files** - each agent works on their own file independently.

## Current Status

- ✅ Base types and exceptions created
- ✅ Module exports configured
- ✅ CollectingValidator fully composed with all validators
- ⏳ Rule implementations need to be completed (currently placeholders)
- ⏳ Tests need to be written

---

Generated: 2026-02-11
Updated: 2026-02-11
