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
├── phases: list[GamePhase]         # Chronological phases
│   ├── NightPhase (night_number >= 1)
│   │   └── subphases: list[NightSubPhase]
│   └── DayPhase (day_number >= 1)
│       └── subphases: list[DaySubPhase]
└── game_over: GameOver | None      # Final result
```

## Indexing Rules

| Field          | Valid Range              | Notes                                |
|----------------|--------------------------|--------------------------------------|
| `seat`         | 0 to (player_count - 1)  | 0-indexed                            |
| `night_number` | 1, 2, 3, ...             | First night is Night 1, no Night 0   |
| `day_number`   | 1, 2, 3, ...             | First day is Day 1, no Day 0         |

**Rationale:**

- **Seats**: 0-indexed aligns with Python conventions and array/list indexing
- **Days/Nights**: 1-indexed because "Day 1" and "Night 1" are the canonical first occurrences in game rules. A sentinel value of 0 in query results (`current_night`, `current_day`) means "no phase recorded yet"

**Validation**: `NightPhase` and `DayPhase` reject values < 1 at construction time.

## Core Abstractions

### SubPhases (Data Containers Only)

Subphases are **immutable data containers** - they hold events but do not manage them.

| SubPhase | Purpose |
|----------|---------|
| `WerewolfActionSubPhase` | Werewolves' kill target |
| `WitchActionSubPhase` | Witch's antidote/poison/pass |
| `GuardActionSubPhase` | Guard's protection target |
| `SeerActionSubPhase` | Seer's investigation result |
| `NightResolutionSubPhase` | Calculated deaths |
| `CampaignSubPhase` | Day 1 sheriff candidate speeches |
| `OptOutSubPhase` | Candidates dropping out |
| `SheriffElectionSubPhase` | Sheriff vote result |
| `DeathAnnouncementSubPhase` | Night death reveal |
| `LastWordsSubPhase` | Night 1 death final statements |
| `DiscussionSubPhase` | Day phase player discussion |
| `VotingSubPhase` | Banishment vote |
| `BanishedLastWordsSubPhase` | Day death final statement |
| `VictoryCheckSubPhase` | Victory condition check |

### Phases (Data Containers Only)

Phases aggregate subphases for a complete night or day.

- **`NightPhase(night_number: int, subphases: list)`**
  - `deaths: list[int]` - Extract deaths from NightResolutionSubPhase

- **`DayPhase(day_number: int, subphases: list)`**
  - `is_day1: bool` - True if Day 1
  - `all_speeches: list[Speech]` - Collect speeches from Campaign/LastWords/Discussion

### GameEventLog (Main Entry Point)

**Construction:**

```python
log = GameEventLog(player_count=12)
```

**Mutation:**

```python
log.add_phase(phase: NightPhase | DayPhase)  # Adds phase to chronology
```

Only `add_phase()` mutates the log. Subphases and phases are data containers only.

## Usage Pattern

```python
from src.werewolf.events.event_log import (
    GameEventLog, NightPhase, DayPhase,
    WerewolfActionSubPhase, CampaignSubPhase
)
from src.werewolf.events.game_events import (
    GameStart, WerewolfKill, Speech, MicroPhase
)

# Initialize
log = GameEventLog(player_count=12)
log.game_start = GameStart(player_count=12, roles={0: "Werewolf", ...})

# Build Night 1
night1 = NightPhase(night_number=1)
night1.subphases.append(
    WerewolfActionSubPhase(kill=WerewolfKill(actor=0, day=1, target=5))
)
log.add_phase(night1)

# Build Day 1
day1 = DayPhase(day_number=1)
campaign = CampaignSubPhase()
campaign.speeches.append(
    Speech(actor=0, day=1, content="I am the Sheriff!", micro_phase=MicroPhase.CAMPAIGN)
)
day1.subphases.append(campaign)
log.add_phase(day1)
```

## Query API

| Method | Returns |
|--------|---------|
| `current_night` | int - Night number (0 if no night yet) |
| `current_day` | int - Day number (0 if no day yet) |
| `get_night(n)` | NightPhase \| None |
| `get_day(n)` | DayPhase \| None |
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
