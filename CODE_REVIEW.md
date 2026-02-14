# Code Review Report - Werewolf AI

**Date:** 2026-02-14
**Reviewer:** Claude Code (Multi-Agent Team)
**Scope:** src/werewolf/ (~17,821 LOC), tests/ (~20,176 LOC)

---

## Executive Summary

The werewolf-ai codebase is well-structured with comprehensive testing (1.1:1 test-to-code ratio) and an event-sourced architecture. However, the review identified 4 priority issues requiring attention:

| Priority | Issue | Status |
|----------|-------|--------|
| HIGH | Winner = None bug causing 1.2% flaky tests | FAIL |
| HIGH | Non-deterministic random in handler fallbacks | PARTIAL |
| MEDIUM | Silent exception handling in last words | FAIL |
| MEDIUM | No Python logging module | FAIL |

---

## Detailed Findings by Category

### 1. Correctness & Spec Compliance

**Status:** PARTIAL

**Findings:**
- Known bug in `werewolf_game.py:172-178`: Winner = None when game ends after MAX_GAME_DAYS with no victory condition met (~1.2% flaky test failure rate)
- Victory conditions correctly implemented in `game_state.py:74-111` and validated in `validation/victory.py`
- Night action validations correctly enforce game rules (guard restriction, witch potions)

**Recommendation:** Implement tie-breaking logic when max days reached

---

### 2. Fail-Fast & Error Handling

**Status:** FAIL

**Findings:**
- `death_resolution_handler.py:245-246`: Silent `except Exception: pass` when generating last words
- `banishment_resolution_handler.py:217-218`: Same silent exception handling
- `textual_game.py:173-174, 181-182, 195-196, 285-286`: Silent catches in UI operations
- Response parsing returns None on failure (acceptable for user experience)

**Recommendation:** Replace silent catches with logging + graceful degradation

---

### 3. Determinism & Reproducibility

**Status:** PARTIAL

**Findings:**
- `death_resolution_handler.py:549`: `random.random() < 0.5` for hunter shoot fallback - UNSEEDED
- `banishment_resolution_handler.py:505`: `random.random() < 0.3` for hunter fallback - UNSEEDED
- Positive: `stub_ai.py:41-42` properly seeds RNG when seed provided
- Positive: `play.py:37` properly seeds player creation

**Recommendation:** Pass game RNG to handlers or use deterministic first-item selection

---

### 4. Hidden Coupling

**Status:** PASS

**Findings:**
- No global mutable state
- No singleton patterns
- Proper dependency injection in WerewolfGame constructor
- Clean handler separation through PhaseContext interface

---

### 5. Single Source of Truth

**Status:** PASS

**Findings:**
- `game_state.py`: Central state management (players, living/dead sets, sheriff)
- `night_action_store.py`: Single source for night action state
- `player.py:82-89`: Single STANDARD_12_PLAYER_CONFIG definition
- Event-driven state updates through GameEvent objects

---

### 6. Architectural Pollution

**Status:** PARTIAL

**Findings:**
- Known bug at `werewolf_game.py:176` (winner = None)
- Debug print statements in `stub_ai.py:161-201` instead of logging
- Clean __init__ files, no unused imports
- No obvious dead code

---

### 7. Test Quality

**Status:** PASS

**Findings:**
- Good parametrized tests: `test_human_stub_stress.py:47,74` uses 1000+ seeds
- Stress tests verify properties beyond outcomes (early game ending, validation violations)
- Handler tests check specific properties (event counts, actor)
- Uses deep_copy_players to prevent test state leaks

---

### 8. Liveness & Termination

**Status:** PASS

**Findings:**
- Main loop bounded by MAX_GAME_DAYS = 20 (`werewolf_game.py:115`)
- Handler retry loops bounded by max_retries = 3
- MaxRetriesExceededError properly caught and handled gracefully
- No unbounded recursion or infinite loops

---

### 9. Observability

**Status:** FAIL

**Findings:**
- **No Python logging module used anywhere in src/werewolf/**
- Debug print statements in `stub_ai.py:161-201` used instead of logging
- Event-based logging exists (GameEventLog) but no runtime logging

**Recommendation:** Add logging module, replace prints with logger.debug()

---

### 10. Authority Boundaries

**Status:** PASS

---

### 11. Domain State Representation

**Status:** PASS

---

## Priority Issues

### Issue 1: Winner = None Bug

**Location:** `src/werewolf/engine/werewolf_game.py:172-178`

```python
# BUG: This returns None when all three groups (werewolves, gods, villagers)
# are still alive after MAX_GAME_DAYS. This causes flaky test failures
# (~1.2% failure rate).
winner = None
```

**Fix:** Implement tie-breaking: compare living werewolf count vs villager-camp count when max days reached.

---

### Issue 2: Non-deterministic Random

**Locations:**
- `src/werewolf/handlers/death_resolution_handler.py:549`
- `src/werewolf/handlers/banishment_resolution_handler.py:505`

```python
if random.random() < 0.5:  # UNSEEDED - breaks reproducibility
```

**Fix:** Pass seeded RNG to handlers or use deterministic fallback (first valid target).

---

### Issue 3: Silent Exception Handling

**Locations:**
- `src/werewolf/handlers/death_resolution_handler.py:245-246`
- `src/werewolf/handlers/banishment_resolution_handler.py:217-218`

```python
except Exception:
    pass  # Hides AI failures
```

**Fix:** Add logging: `logger.warning(f"Last words failed: {e}")`

---

### Issue 4: No Logging

**Problem:** No Python logging in src/werewolf/

**Fix:** Add `import logging` and use `logger = logging.getLogger(__name__)` in affected modules.

---

## Files to Modify

| Priority | File | Lines | Issue |
|----------|------|-------|-------|
| HIGH | werewolf_game.py | 172-178 | Winner=None |
| HIGH | death_resolution_handler.py | 549 | Unseeded random |
| HIGH | banishment_resolution_handler.py | 505 | Unseeded random |
| MEDIUM | death_resolution_handler.py | 245-246 | Silent exception |
| MEDIUM | banishment_resolution_handler.py | 217-218 | Silent exception |
| MEDIUM | stub_ai.py | 161-201 | Print statements |
| MEDIUM | Multiple handlers | Various | Add logging |

---

## Verification

```bash
# Stress test winner bug fix
uv run werewolf --validate --games 200

# Deterministic seed test
uv run werewolf --seed 42 --ai
uv run werewolf --seed 42 --ai

# Run tests
uv run pytest tests/ -v
```
