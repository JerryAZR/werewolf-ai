# Werewolf AI CLI Game Implementation Plan

## Context
This is a greenfield project to implement a Werewolf (狼人杀) CLI game with AI-powered NPC players. The game rules are fully documented in:
- `RULES.md` (English)
- `RULES_CN.md` (Chinese)

**Technology Stack:**
- Language: Python
- AI: OpenAI-compatible API with configurable endpoint
- 12 players: 4 Werewolves vs 8 Villager-camp (4 Ordinary Villagers, Seer, Witch, Hunter, Guard)
- **Sheriff**: A title that can be given to any player (elected on Day 1)

## Key Game Rules Implementation

### Phase Structure

**Macro Phases**: NIGHT, DAY, GAME_OVER
**Micro Phases** (within DAY): Sheriff Election, Death Announcement, Last Words, Discussion, Voting, Victory Check

See [PHASES.md](PHASES.md) for detailed flow and special rules.

## Implementation Plan

### Phase 1: Project Setup
- Create `pyproject.toml` with dependencies (openai, pydantic, rich for CLI)
- Create config file structure (`config.yaml` or `.env`)
- Set up project structure:
  ```
  src/
    game/
      __init__.py
      engine.py      # Main game loop and state machine
      state.py        # Game state, player state
      roles.py        # Role definitions and abilities
      players.py      # AI player wrapper
      actions.py      # Night actions (kill, check, guard, etc.)
      voting.py       # Voting logic, PK rounds, Sheriff election
    ai/
      __init__.py
      client.py       # OpenAI-compatible API client
      prompts.py      # Role-specific prompts
    cli/
      __init__.py
      main.py         # CLI entry point
      display.py      # Output formatting
  ```

### Phase 2: Core Data Models
- **Player**: id, name, role (hidden), is_alive, is_sheriff, has_used_skill
- **Role Enum**: WEREWOLF, VILLAGER, SEER, WITCH, HUNTER, GUARD, SHERIFF
- **GameState**: day_number, phase (NIGHT/DAY), players, deaths, sheriff
- **NightAction**: action_type, actor, target, results

### Phase 3: Game Engine
- State machine for phase transitions (NIGHT → DAY → NIGHT → ...)
- Night phase orchestration:
  1. Collect werewolf kill target
  2. Query Witch (show target if any, get potion decision)
  3. Query Seer (get check target)
  4. Query Guard (get guard target)
  5. Resolve deaths with priority: Poison > Werewolf Kill (protected by Guard)
- Day phase orchestration:
  1. Sheriff election (Day 1 only)
  2. Announce deaths (count only, no cause/identity)
  3. Last words for First Night deaths
  4. Discussion (collect speeches)
  5. Voting with Sheriff 1.5 vote
  6. PK round if tied
  7. Victory check

### Phase 4: AI Integration
- `AIClient`: OpenAI-compatible API wrapper with configurable base_url
- Role-specific prompts for:
  - Werewolf: Night kill decision (collaborative), Day defense
  - Seer: Check target selection, claim strategy
  - Witch: Potion decisions (antidote target, poison target)
  - Guard: Guard target selection
  - Hunter: Skill usage decision, target selection
  - Sheriff: Leadership, vote timing, badge transfer
- Context: Public game state, role info, chat history, known information

### Phase 5: CLI Interface
- Turn-based output showing:
  - Night actions (anonymized results)
  - Day announcements
  - Discussion speeches
  - Voting results
  - Victory/defeat messages
- Configurable game parameters (player names, roles)

## Critical Files to Create/Modify
| File | Purpose |
|------|---------|
| `pyproject.toml` | Dependencies |
| `config.yaml` | AI endpoint config |
| `src/game/engine.py` | Main game loop |
| `src/game/state.py` | State models |
| `src/game/roles.py` | Role logic |
| `src/game/voting.py` | Sheriff, voting, PK |
| `src/ai/client.py` | API client |
| `src/cli/main.py` | CLI entry |

## Testing Strategy
1. Unit tests for role abilities and interactions
2. Voting logic tests (including Sheriff 1.5 vote)
3. Night resolution tests (poison vs guard, witch antidote)
4. Mock AI client for testing game flow
5. Integration test: Full game simulation with mock AI

## Clarified (answered)
- **Discussion Mode**: Turn-based (sequential speeches)
- **AI Response Format**: Free-form text (no strict JSON)
- **Sheriff Badge Transfer**: Sheriff announces heir when death is revealed (before/at last words)

## Logging and Debugging Strategy

### 1. Event Logging System

The game will maintain structured logs at multiple levels:

#### Game Events (INFO level)
- Phase transitions (Night → Day, Day → Night)
- Player deaths (who died, cause)
- Votes cast and results
- Sheriff elections and badge transfers
- Victory/defeat conditions

Example log entry (YAML format):
```yaml
timestamp: 2024-01-15T10:30:00Z
event: player_died
day: 1
phase: night
player: Player_3
cause: werewolf_kill
guarded: true
saved_by_witch: false
```

#### Debug Events (DEBUG level)
- AI prompt sent (sanitized)
- AI response received
- Action decisions and rationale
- State changes during resolution

#### Rule Validation (DEBUG level)
- Invariant checks before/after actions
- State validation results
- Rule violations caught

### 2. State Snapshots

At each phase boundary, save a complete game state snapshot:
- All players with roles and status
- Sheriff status
- Used potions (antidote/poison used)
- Guard's last target (for consecutive night check)
- AI decisions made

This enables:
- **Replay**: Reproduce any game from logs
- **Debug**: Inspect state at any point
- **Test**: Verify behavior from saved states

### 3. Rule Enforcement Mechanisms

#### Invariant Checks
Define explicit invariants that must always hold:

| Invariant | Check Location |
|-----------|----------------|
| Werewolf count ≤ 4 | Role assignment |
| Sheriff is a living player | Sheriff election |
| Guard cannot guard same person twice | Guard action |
| Witch antidote not used twice | Witch action |
| Hunter skill disabled if poisoned | Hunter death resolution |
| Sheriff vote = 1.5 | Vote counting |
| Victory conditions checked after each death | Death resolution |

#### Validation Functions
```python
def validate_game_state(state: GameState) -> List[RuleViolation]:
    violations = []
    if guard.current_target == guard.last_target:
        violations.append(RuleViolation("Guard consecutive night restriction violated"))
    if state.sheriff and not state.sheriff.is_alive:
        violations.append(RuleViolation("Sheriff must be alive"))
    # ... more checks
    return violations
```

#### Assertions in Critical Paths
```python
def resolve_deaths(state: GameState, actions: NightActions):
    # Before resolution
    assert validate_invariants(state) == [], "State invariants violated before resolution"

    # During resolution
    deaths = calculate_deaths(state, actions)
    for death in deaths:
        assert death.cause in VALID_CAUSES, f"Invalid death cause: {death.cause}"

    # After resolution
    apply_deaths(state, deaths)
    assert validate_invariants(state) == [], "State invariants violated after resolution"
```

### 4. Debugging Tools

#### CLI Debug Commands
```
--verbose, -v    : Show debug logs
--dump-state     : Print current state (JSON format)
--step           : Step through phases manually
--replay <log>   : Replay game from log file
--trace <player> : Trace specific player's AI decisions
```

#### Python API for Debugging
```python
# Save state for debugging
game.save_state("checkpoint_d1_night.yaml")

# Load and continue
game.load_state("checkpoint_d1_night.yaml")

# Validate current state
violations = game.validate_state()
if violations:
    print(f"Rule violations: {violations}")
```

### 5. Testing Strategy for Rule Compliance

#### Unit Tests
Each rule gets explicit unit tests:

```python
def test_guard_consecutive_night():
    state = GameState()
    guard = Player(role=Role.GUARD)
    state.add_player(guard)

    # Guard someone on night 1
    state.guard_action(guard, target="Player_A")
    assert state.guard.last_target == "Player_A"

    # Cannot guard same person night 2
    with pytest.raises(InvalidActionError):
        state.guard_action(guard, target="Player_A")
```

#### Property-Based Testing
Use Hypothesis to verify invariants:
- Total player count always = 12
- Werewolf count + Villager count = 12
- Sheriff is always a living player
- Death count = sum of all deaths

#### Integration Tests
Test complete phase flows:
- Night resolution with poison + guard + antidote interactions
- Sheriff election and badge transfer
- PK voting with Sheriff 1.5 vote
- Victory condition triggers

### 6. AI Decision Audit Trail

For each AI decision, log:
- Context provided to AI (game state, known info)
- Raw AI response
- Parsed decision
- Reasoning (if AI provides it)

This helps debug:
- Why AI made a unexpected decision
- Whether AI understood the rules
- Prompt engineering issues

### 7. Log File Structure

```
logs/
  game_20240115_103000.yaml    # Full game log (YAML)
  debug_20240115_103000.yaml   # Debug snapshot (verbose)
  state_d1_night_start.yaml    # State snapshots
  state_d1_night_end.yaml
```

### 8. Verification Checklist Before Next Step

Before moving to Phase 2+, verify:
- [ ] All unit tests pass (100% rule coverage target)
- [ ] Integration tests pass for all phase transitions
- [ ] Property-based tests find no invariants violations
- [ ] Can replay a game from logs exactly
- [ ] State validation catches all known edge cases
- [ ] AI audit trail is complete and parseable
- [ ] Debug commands work correctly

## Game Log Validation Tool Design

### Overview
A standalone tool that takes a game log (JSONL format) and verifies whether the game followed all rules. It replays the game step-by-step, validating each action against the game state.

### Core Validation Categories

| Category | What it Validates |
|----------|-------------------|
| Phase Sequence | Night→Day→Night transitions |
| Role Actions | Players only perform actions their role allows |
| Action Constraints | e.g., Guard can't guard same person twice |
| Voting Rules | Sheriff 1.5 vote, PK rounds |
| Victory Conditions | Werewolves win when all gods OR all villagers dead |

### Key Design Points

1. **Event-sourced**: Validates log as a sequence of events
2. **State-aware**: Maintains game state to validate context-dependent rules
3. **Composable validators**: Each rule category has its own validator
4. **Detailed reporting**: Line numbers, context, severity (error/warning)

### Usage

```bash
# Validate a game log
python -m werewolf.tools.validate logs/game_20240115.yaml

# Validate and output report
python -m werewolf.tools.validate logs/game.yaml --output report.yaml
```

### Implementation Note
Detailed validator specifications (all assertions, error codes, report formats) will be documented in `src/game/validator_specs.md` during implementation.

## Open Questions
- Should there be a streaming mode for faster gameplay?
