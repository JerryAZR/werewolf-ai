# Event Log Module

## Purpose

The `event_log` module provides a hierarchical, event-sourced data structure for recording Werewolf game progression. It captures the complete game state as structured events organized by time.

## Architecture

```
GameEventLog
├── game_id: str                    # Unique game identifier
├── created_at: str                 # ISO timestamp
├── player_count: int               # Number of players
├── roles_secret: dict[int, str]    # Seat → Role mapping (hidden)
├── game_start: GameStart | None    # Initial game setup
├── phases: list[PhaseLog]          # Chronological phases
│   └── subphases: list[SubPhaseLog]
└── game_over: GameOver | None      # Final result
```

## Indexing Rules

| Field           | Valid Range              | Notes                                |
|-----------------|--------------------------|--------------------------------------|
| `seat`          | 0 to (player_count - 1)  | 0-indexed                            |
| `phase.number`  | 1, 2, 3, ...             | Night or Day number                  |
| `phase.kind`    | NIGHT or DAY             | Which type of phase                  |

**Rationale:**

- **Seats**: 0-indexed aligns with Python conventions
- **Phase number**: 1-indexed because "Day 1" and "Night 1" are canonical first occurrences
- **Phase kind**: Distinguishes nights from days

**Validation**: `PhaseLog` rejects `number < 1` at construction time.

## Core Abstractions

### SubPhaseLog (Generic Container)

`SubPhaseLog` is a generic container for events within a sub-phase:

```python
SubPhaseLog(
    micro_phase: SubPhase,          # Which sub-phase (WEREWOLF_ACTION, CAMPAIGN, etc.)
    events: list[GameEvent] = []   # Zero or more events
)
```

Examples:

```python
# Empty subphase (pending action)
SubPhaseLog(micro_phase=SubPhase.WEREWOLF_ACTION)

# With events
SubPhaseLog(micro_phase=SubPhase.WEREWOLF_ACTION, events=[WerewolfKill(...)])
SubPhaseLog(micro_phase=SubPhase.CAMPAIGN, events=[Speech(...), Speech(...)])
```

### PhaseLog (Unified Night/Day)

`PhaseLog` is a unified container for both nights and days:

```python
PhaseLog(
    number: int,                    # 1, 2, 3... (night or day number)
    kind: Phase,                    # NIGHT or DAY
    subphases: list[SubPhaseLog] = []  # Sub-phases
)
```

**Note**: `is_day1` can be checked via `phase.kind == Phase.DAY and phase.number == 1`.

### GameEventLog (Main Entry Point)

**Construction:**

```python
log = GameEventLog(player_count=12)
```

**Mutation:**

```python
log.add_phase(phase: PhaseLog)  # Adds phase to chronology
```

Only `add_phase()` mutates the log. SubPhaseLogs and PhaseLogs are data containers only.

## Usage Pattern

```python
from src.werewolf.events.event_log import (
    GameEventLog, PhaseLog, SubPhaseLog
)
from src.werewolf.events.game_events import (
    GameStart, WerewolfKill, Speech, SubPhase, Phase
)

# Initialize
log = GameEventLog(player_count=12)
log.game_start = GameStart(player_count=12, roles={0: "Werewolf", ...})

# Build Night 1
night1 = PhaseLog(number=1, kind=Phase.NIGHT)
night1.subphases.append(
    SubPhaseLog(
        micro_phase=SubPhase.WEREWOLF_ACTION,
        events=[WerewolfKill(actor=0, day=1, target=5)]
    )
)
log.add_phase(night1)

# Build Day 1
day1 = PhaseLog(number=1, kind=Phase.DAY)
campaign = SubPhaseLog(
    micro_phase=SubPhase.CAMPAIGN,
    events=[
        Speech(actor=0, day=1, content="I am the Sheriff!", micro_phase=SubPhase.CAMPAIGN)
    ]
)
day1.subphases.append(campaign)
log.add_phase(day1)
```

## Query API

| Method | Returns |
|--------|---------|
| `current_night` | int - Night number (0 if no night yet) |
| `current_day` | int - Day number (0 if no day yet) |
| `get_night(n)` | PhaseLog \| None - Night n |
| `get_day(n)` | PhaseLog \| None - Day n |
| `get_all_deaths()` | list[int] - All death seats |
| `get_all_speeches()` | list[tuple[int, str]] - (day, content) pairs |
| `get_sheriffs()` | dict[int, int] - day → sheriff seat |

## Serialization

```python
# To YAML (excludes roles_secret by default)
yaml_str = log.to_yaml(include_roles=False)

# Save to file
log.save_to_file("game.yaml", include_roles=False)

# Load from file
log2 = GameEventLog.load_from_file("game.yaml")
```

YAML output uses enum values (e.g., `"WEREWOLF"`, `"DAY"`) not Python objects.

## Invariants

1. **No duplicate phases** - Adding Night 1 twice raises `ValueError`
2. **No skipping levels** - Must create subphase → add to phase → add phase to log
3. **Chronological order** - Phases must be added in game order (Night 1, Day 1, Night 2, ...)
4. **Subphases are unordered** - Within a phase, subphases can be in any order
