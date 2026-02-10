# Handler Specifications

Comprehensive specifications for all micro-phase handlers. Each handler is defined by:
1. **Context Filtering** - What information participants see
2. **Input/Output** - Handler interface
3. **Validation Rules** - What makes responses valid
4. **Invariant Rules** - Hard rules that must never be violated

---

## PhaseContext Fields

The engine passes a `PhaseContext` to each handler with the following fields:

```python
class PhaseContext(BaseModel):
    """Context passed to handlers by the engine."""

    # Current phase identification
    phase: Phase              # NIGHT, DAY, or GAME_OVER
    sub_phase: SubPhase       # Specific subphase

    # Game state
    day: int                  # Current day (1, 2, ...)
                               # Night number = day (game starts Night 1 → Day 1)

    # Player state
    players: dict[int, Player]  # Full player state with roles
    living_players: set[int]     # Set of living player seats
    dead_players: set[int]      # Set of dead player seats

    # Night actions accumulated so far (for night phases)
    night_actions: Optional[NightActionAccumulator] = None

    # Current Sheriff (for vote weight and speaking order)
    sheriff: Optional[int] = None
```

### Engine-Provided Fields

These fields are computed by the engine and passed to handlers:

| Field | Type | Provided By | Used In |
|-------|------|------------|---------|
| `sheriff_candidates` | `list[int]` | Engine (before Campaign) | Campaign, OptOut, SheriffElection |
| `deaths` | `dict[int, DeathCause]` | NightResolution | DeathResolution |
| `events_so_far` | `list[GameEvent]` | Event Log | Discussion, Voting |
| `banished` | `int \| None` | Voting Handler | BanishmentResolution |

### NightActionAccumulator

```python
class NightActionAccumulator(BaseModel):
    """Accumulates night actions for resolution (fresh each night)."""

    # From WerewolfAction
    kill_target: Optional[int] = None

    # From WitchAction
    antidote_target: Optional[int] = None
    poison_target: Optional[int] = None
    antidote_used: bool = False
    poison_used: bool = False

    # From GuardAction
    guard_target: Optional[int] = None

    # Persistent guard state
    guard_prev_target: Optional[int] = None
```

---

## Night Phases

### 1. WerewolfAction

#### Context Filtering

**Included Information:**
- `day`: Current day/night number (night = day)
- `players` + `living_players`: List of living players (derived)
- `players`: Fellow werewolf seats (werewolves know teammates)
- `dead_players`: Dead player seats (roles unknown)
- `sheriff`: Sheriff identity (if elected)

**Excluded Information:**
- Seer, Witch, Guard, Hunter identities (not visible in `players[seat].role` for werewolves)

**Per-Role Filtering:**
- All werewolves receive identical filtered context
- Werewolves see teammates as "werewolf teammates"
- Non-werewolves appear as "Unknown Role"

#### Input/Output

**Input:**
```
- day: int - Game day (night = day for prompt display)
- players: dict[int, Player] - Full state with roles
- living_players: set[int] - All living players
- dead_players: set[int] - Dead players (excluded)
- sheriff: Optional[int] - Current Sheriff
```

**Participants:** All living werewolves (typically 1-4 seats)

**Output:**
```python
WerewolfKill(
    actor: int,           # Representative werewolf seat
    target: Optional[int], # Kill target or None (skip allowed per RULES.md line 201)
    phase: Phase.NIGHT,
    sub_phase: SubPhase.WEREWOLF_ACTION,
    day: int
)
```

**Edge Cases:**
- No werewolves alive → Skip phase, return empty SubPhaseLog
- Single werewolf → Query that werewolf
- Multiple werewolves → Handler aggregates consensus

#### Validation Rules

**Valid Response Criteria:**
- `target` must be a living player OR `None` (no kill)
- `target` must be valid seat (0-11) or `None`
- `actor` must be a living werewolf

**Invalid Examples:**
- `target=dead_player` → Target must be living
- `target=12` → Invalid seat number

**Error Hints:**
- "Player X has been eliminated. Choose a living player."

#### Invariant Rules

1. **Werewolf Presence Rule**: Phase only executes when at least one werewolf is alive
2. **Living Target Rule**: Target must be in `living_players` (or `None` for skip)
3. **Single Kill Rule**: At most one kill target per night
4. **Actor Must Be Werewolf**: `actor` field must be a living werewolf seat
5. **Phase Sequencing**: WerewolfAction MUST precede WitchAction (RULES.md line 56-57)
6. **Single Decision Rule**: One collective decision, not per-werewolf (RULES.md line 180)

---

### 2. WitchAction

#### Context Filtering

**Included Information:**
- `players[witch_seat].role`: Witch's own role
- `night_actions.kill_target`: Werewolf kill target (critical for antidote decision)
- `night_actions.antidote_used`, `night_actions.poison_used`: Remaining potions
- `living_players`: All living player seats

**Excluded Information:**
- Other players' roles (not visible in `players[seat].role`)
- `night_actions.guard_target`: Guard protection target
- Werewolf team composition beyond kill target

**Special Considerations:**
- If witch is the werewolf target → Antidote option disabled/hidden
- Poison can target anyone (including werewolves, witch self)

#### Input/Output

**Input:**
```
- day: int
- players: dict[int, Player]
- living_players: set[int]
- night_actions: NightActionAccumulator (kill_target, antidote_used, poison_used)
```

**Participants:** Living Witch (single seat)

**Output:**
```python
WitchAction(
    actor: int,                    # Witch seat
    action_type: WitchActionType,  # ANTIDOTE, POISON, PASS
    target: int | None,           # Target seat or None
    phase: Phase.NIGHT,
    sub_phase: SubPhase.WITCH_ACTION,
    day: int
)
```

**Action Types:**
| Type | Target Required | Description |
|------|-----------------|-------------|
| ANTIDOTE | Yes (must be kill_target) | Saves werewolf target |
| POISON | Yes (any living) | Kills target, ignores guard |
| PASS | No | No action |

#### Validation Rules

**Valid Response Criteria:**

| Action | Requirements |
|--------|--------------|
| ANTIDOTE | `target == kill_target`, `antidote_used=False`, `target != actor` |
| POISON | `target` living, `poison_used=False` |
| PASS | `target == None` |

**Invalid Examples:**
- Antidote on wrong target → "Target must be werewolf kill target"
- Poison on dead player → "Target must be alive"
- Pass with target → "PASS cannot have a target"

#### Invariant Rules

1. **Single Potion Per Night**: At most one of antidote/poison (RULES.md line 146)
2. **Antidote Requires Target**: Only usable when werewolves killed someone
3. **Antidote Cannot Target Self**: Witch cannot antidote self (RULES.md line 148)
4. **Poison Ignores Guard**: Poison kills regardless of guard (RULES.md line 150)
5. **Poison Hunter Disables Shoot**: Poisoned Hunter cannot shoot (RULES.md line 156)
6. **Witch Must Be Alive**: Dead witch cannot act

---

### 3. GuardAction

#### Context Filtering

**Included Information:**
- `players[guard_seat].role`: Guard's own role
- `living_players`: All living players (seat numbers)
- `night_actions.guard_prev_target`: Previous night's guard target (for consecutive night check)

**Excluded Information:**
- Other players' roles (not visible in `players[seat].role`)
- `night_actions.kill_target`: Werewolf target
- `night_actions.antidote_target`, `night_actions.poison_target`: Witch actions

**Special Considerations:**
- Cannot guard same person two consecutive nights
- Guard CAN guard themselves

#### Input/Output

**Input:**
```
- day: int
- players: dict[int, Player]
- living_players: set[int]
- night_actions: NightActionAccumulator (guard_prev_target)
```

**Participants:** Living Guard (single seat)

**Output:**
```python
GuardAction(
    actor: int,           # Guard seat
    target: int | None,   # Protected seat or None (skip allowed)
    phase: Phase.NIGHT,
    sub_phase: SubPhase.GUARD_ACTION,
    day: int
)
```

#### Validation Rules

**Valid Response Criteria:**
- `target` in `living_players`
- `target != guard_prev_target` (consecutive night restriction - RULES.md line 163)
- `target=None` allowed (skip)

**Invalid Examples:**
- Target already guarded last night → "Cannot guard same person consecutively"
- Target dead → "Cannot guard eliminated player"

#### Invariant Rules

1. **Unique Target**: Cannot guard same person two nights in row (RULES.md line 163)
2. **Self-Protection Allowed**: Guard can guard themselves (RULES.md line 212)
3. **Target Must Be Living**: Only living players can be protected
4. **One Target Per Night**: Exactly one or None (no skip required)

---

### 4. SeerAction

#### Context Filtering

**Included Information:**
- `players[seer_seat].role`: Seer's own role
- `living_players`: All living players (seat numbers)
- `sheriff`: Sheriff identity (for game state awareness)

**Excluded Information:**
- Other players' roles (not visible in `players[seat].role`)
- `night_actions.kill_target`: Werewolf target
- `night_actions.antidote_target`, `night_actions.poison_target`: Witch actions
- `night_actions.guard_target`: Guard protection

**Role Result Presentation:**
- `WEREWOLF` → Target is a werewolf
- `GOOD` → Target is NOT a werewolf (Seer, Witch, Guard, Hunter, Villager)
- Specific "good" role never revealed

#### Input/Output

**Input:**
```
- day: int
- players: dict[int, Player]
- living_players: set[int]
- sheriff: Optional[int]
```

**Participants:** Living Seer (single seat)

**Output:**
```python
SeerAction(
    actor: int,           # Seer seat
    target: int,          # Checked player seat
    result: SeerResult,   # GOOD or WEREWOLF (engine computes)
    phase: Phase.NIGHT,
    sub_phase: SubPhase.SEER_ACTION,
    day: int
)
```

**Result Computation (Engine):**
- `WEREWOLF` if `players[target].role == WEREWOLF`
- `GOOD` otherwise

#### Validation Rules

**Valid Response Criteria:**
- `target` in `living_players`
- `target != actor` (cannot check self)
- No skip allowed (must choose someone)

**Invalid Examples:**
- Target self → "You cannot check your own identity"
- Target dead → "Cannot query dead players"

#### Invariant Rules

1. **Seer Must Be Alive**: Dead seer cannot act
2. **Target Must Be Living**: Only living players can be checked
3. **No Self-Check**: Seer cannot target themselves
4. **Engine Computes Result**: Handler returns target, engine fills result
5. **Hidden Identity**: Seer's identity must remain secret

---

### 5. NightResolution

#### Context Filtering

**Included Information:**
- `night_actions`: All night action data from accumulator:
  - `kill_target`: Werewolf target
  - `antidote_target`: Witch antidote target
  - `poison_target`: Witch poison target
  - `antidote_used`, `poison_used`
  - `guard_target`: Guard protected target

**Output Structure:**
```python
NightOutcome(
    phase: Phase.NIGHT,
    sub_phase: SubPhase.NIGHT_RESOLUTION,
    day: int,
    deaths: dict[int, DeathCause]  # {seat: WEREWOLF_KILL | POISON}
)
```

**Death Calculation Logic:**
1. Start with `kill_target` → WEREWOLF_KILL
2. If `antidote_target == kill_target`: remove (target saved)
3. If `guard_target == kill_target`: remove (target saved)
4. If `poison_target` exists: add {poison_target: POISON}
5. Return deaths dict

#### Validation Rules

**Valid Outcome Criteria:**
- All targets in `deaths` are living players
- Death causes match actions (WEREWOLF_KILL requires no save, POISON always kills)
- No duplicate death entries per seat

**Death Cause Assignment:**
- WEREWOLF_KILL: Werewolf target not saved by antidote/guard
- POISON: Witch poison target (ignores guard - RULES.md line 150)

#### Invariant Rules

1. **Antidote Only On Werewolf Target**: Saves only if targeting same player
2. **Poison Ignores Guard**: Guard protection does not save poisoned players (RULES.md line 150)
3. **Double Protection OK**: Both antidote + guard still means target survives
4. **Death Cause Records Truth**: Must match actual cause for Hunter logic
5. **No Duplicate Deaths**: Each seat appears at most once
6. **Guard Can Be Poisoned**: If guard dies, their protection still applies (RULES.md line 151)

---

## Day Phases

### 6. Campaign (Day 1 Only)

#### Context Filtering

**Included Information:**
- `day`: Current day (must be 1)
- `sheriff_candidates`: List of Sheriff candidates (engine-provided field)
- `players[seat].role`: Player's own role (to know if running)
- Game rule knowledge: Sheriff speaks LAST among candidates

**Excluded Information:**
- Who died (death announcements come AFTER Campaign)
- Campaign speeches content (private until all given)
- Any game events from previous phases

**Special Considerations:**
- Sheriff speaks LAST among candidates
- Each candidate speaks once

#### Input/Output

**Input:**
```
- day: int (must be 1)
- sheriff: Optional[int] - None on Day 1
- sheriff_candidates: list[int] - Engine-provided field
- players: dict[int, Player]
```

**Participants:** All Sheriff candidates (living)

**Output:**
```python
Speech(
    actor: int,           # Candidate seat
    content: str,         # Campaign speech
    phase: Phase.DAY,
    sub_phase: SubPhase.CAMPAIGN,
    day: int
)
```

#### Validation Rules

**Valid Response Criteria:**
- Actor is living Sheriff candidate
- `day == 1`
- `content` is non-empty string
- `micro_phase == CAMPAIGN`

**Invalid Examples:**
- Wrong micro_phase (e.g., DISCUSSION)
- Dead player speaking
- Empty content

#### Invariant Rules

1. **Day 1 Only**: Campaign only occurs on Day 1
2. **Candidates Only**: Only registered candidates speak
3. **Sheriff Speaks Last**: If incumbent Sheriff is running
4. **Campaign Before OptOut**: All speeches before opt-out decisions
5. **No State Changes**: Only records speeches

---

### 7. OptOut (Day 1 Only)

#### Context Filtering

**Included Information:**
- `day`: Current day (must be 1)
- `sheriff_candidates`: List of candidates (player can check own status)
- Game rule knowledge: Opt-out is final (one decision)

**Excluded Information:**
- Other players' roles (not visible in `players[seat].role`)
- Campaign speeches content
- Other candidates' opt-out intentions

#### Input/Output

**Input:**
```
- day: int (must be 1)
- sheriff_candidates: list[int]
- sheriff: Optional[int]
```

**Participants:** All current candidates (living)

**Output:**
```python
SheriffOptOut(
    actor: int,           # Candidate seat
    phase: Phase.DAY,
    sub_phase: SubPhase.OPT_OUT,
    day: int
)
```

#### Validation Rules

**Valid Response Criteria:**
- Actor in `sheriff_candidates`
- Actor is living
- Day == 1
- One decision per candidate

**Invalid Examples:**
- Non-candidate opting out
- Duplicate opt-out

#### Invariant Rules

1. **Day 1 Only**: Only on Day 1
2. **Candidates Only**: Only candidates can opt out
3. **Single Decision**: Each candidate opts out at most once
4. **Cannot Rejoin**: Once out, cannot re-enter
5. **Precedes SheriffElection**: All opt-outs before voting

---

### 8. SheriffElection (Day 1 Only)

#### Context Filtering

**Included Information:**
- `sheriff_candidates`: Remaining candidates (after OptOut)
- `living_players`: All living players (must vote)
- Game rule knowledge: Sheriff vote weight = 1.5, no abstention

**Excluded Information:**
- Other players' votes (until resolution)
- Role information (not visible in `players[seat].role`)
- Vote intentions

#### Input/Output

**Input:**
```
- day: int (must be 1)
- sheriff_candidates: list[int]  # After OptOut
- living_players: set[int]
- sheriff: Optional[int] - None on Day 1
- players: dict[int, Player]
```

**Participants:** All living players (must vote)

**Output:**
```python
SheriffOutcome(
    candidates: list[int],    # Eligible candidates
    votes: dict[int, float],  # {candidate: weighted vote total}
    winner: Optional[int],   # Winning seat or None (tie)
    phase: Phase.DAY,
    sub_phase: SubPhase.SHERIFF_ELECTION,
    day: int
)
```

**Vote Calculation:**
- Sheriff's vote = 1.5
- Others = 1.0

#### Validation Rules

**Valid Response Criteria:**
- Voter is living
- Target is in `sheriff_candidates`
- No abstention (all must vote - RULES.md line 209)

**Tie-Breaking:**
- Tie → `winner = None` (no Sheriff elected - RULES.md line 210)

#### Invariant Rules

1. **Day 1 Only**: Only on Day 1 (RULES.md line 170)
2. **No Abstention**: All living must vote (RULES.md line 209)
3. **Majority Required**: Without tie, highest votes wins
4. **Tie = No Sheriff**: Multiple with max votes → no election (RULES.md line 210)
5. **Candidates Locked**: Those who opted out cannot receive votes

---

### 9. DeathResolution

**Scope:** Handles NIGHT deaths only (from NightOutcome). For banishment deaths, see BanishmentResolution.

#### Context Filtering

**Input Context:**
```
- day: int - Current day
- deaths: dict[int, DeathCause] - From NightOutcome (engine-provided, WEREWOLF_KILL or POISON)
- players: dict[int, Player] - Full state (role, sheriff status)
- living_players: set[int] - Living players BEFORE deaths
- sheriff: Optional[int]
```

**Note:** `deaths` is computed by NightResolution handler and passed as engine state.

**Output:**
```python
DeathEvent(
    actor: int,                   # Dead player seat
    cause: DeathCause,            # WEREWOLF_KILL | POISON (not BANISHMENT)
    last_words: str | None,       # AI speech or None
    hunter_shoot_target: int | None,  # None = skipped
    badge_transfer_to: int | None,    # None or new sheriff
    phase: Phase.DAY,
    sub_phase: SubPhase.DEATH_RESOLUTION,
    day: int
)
```

**Processing per Night Death:**
1. **Last Words**: Night 1 only (Night 2+ night deaths have no last words)
2. **Hunter Shoot**: If Hunter + WEREWOLF_KILL → AI chooses target or None
3. **Badge Transfer**: If Sheriff → designate heir or None

#### Validation Rules

**Valid DeathEvent Criteria:**
- `actor` is a confirmed dead player
- `cause` matches death source
- `last_words`: None for Night 2+ night deaths, str for day deaths
- `hunter_shoot_target`: None if not applicable or skipped, else living player
- `badge_transfer_to`: None if not sheriff, else living player

**Hunter Shoot Rules:**
| Cause | Can Shoot? |
|-------|------------|
| WEREWOLF_KILL | Yes (RULES.md line 154) |
| POISON | No (RULES.md line 156) |

#### Invariant Rules

1. **Night Deaths Only**: DeathResolution handles WEREWOLF_KILL and POISON deaths
2. **Last Words Night 1 Only**: Night 2+ night deaths have no last words (RULES.md line 84)
3. **Hunter Shoot Only on Werewolf Kill**: Poisoned hunter cannot shoot (RULES.md line 156)
4. **Hunter Target Must Be Living**: Cannot shoot dead player
5. **Badge Transfer Only Sheriff**: Only sheriff can transfer badge
6. **Transfer Target Must Be Living**: Badge goes to living player
7. **Cause Matches Context**: WEREWOLF_KILL or POISON only (see BanishmentResolution for BANISHMENT)

---

### 10. Discussion

#### Context Filtering

**Included Information:**
- `day`: Current day number
- `living_players`: Living player seats
- `sheriff`: Sheriff identity (speaks last)
- Game events: Previous speakers' speeches (in order)
- Game events: Last words from morning deaths

**Excluded Information:**
- Role information (not visible in `players[seat].role`)
- Night action details (`night_actions` fields)
- Seer check results (unless voluntarily revealed)

**Speaking Order:**
- Sheriff speaks LAST
- Others alternate clockwise/counter-clockwise

#### Input/Output

**Input:**
```
- day: int
- living_players: set[int]
- sheriff: Optional[int]
- players: dict[int, Player]
```

**Participants:** All living players

**Output:**
```python
Speech(
    actor: int,           # Speaker seat
    content: str,         # Speech text
    phase: Phase.DAY,
    sub_phase: SubPhase.DISCUSSION,
    day: int
)
```

#### Validation Rules

**Valid Response Criteria:**
- Actor is living and scheduled to speak
- Content is non-empty string
- Correct speaking order (Sheriff last)
- Correct phase/micro_phase

**Invalid Examples:**
- Sheriff speaking before others
- Dead player speaking
- Empty content

#### Invariant Rules

1. **Sheriff Speaks Last**: All others before sheriff
2. **Only Living Players**: Dead cannot speak
3. **After Death Resolution**: Deaths processed before discussion
4. **Before Voting**: No voting during discussion
5. **Alternating Order**: Clockwise/counter-clockwise pattern
6. **One Speech Each**: Per living player per discussion

---

### 11. Voting

#### Context Filtering

**Included Information:**
- `living_players`: All living players
- `sheriff`: Sheriff identity (vote weight = 1.5)
- Game events: Discussion transcripts
- Game events: Morning death announcements

**Excluded Information:**
- Other players' votes (until resolution)
- Role information (not visible in `players[seat].role`)
- Night action details (`night_actions` fields)

#### Input/Output

**Input:**
```
- day: int
- living_players: set[int]
- sheriff: Optional[int]
- players: dict[int, Player]
```

**Participants:** All living players (abstention allowed)

**Output:**
```python
Vote(
    actor: int,            # Voter seat
    target: Optional[int],  # Target seat or None (abstain)
    phase: Phase.DAY,
    sub_phase: SubPhase.VOTING,
    day: int
)

Banishment(
    votes: dict[int, float],      # {target: weighted total}
    tied_players: list[int],       # Max vote recipients
    banished: Optional[int],       # Winner or None (tie)
    phase: Phase.DAY,
    sub_phase: SubPhase.VOTING,
    day: int
)
```

#### Validation Rules

**Valid Response Criteria:**
- Voter is living
- Target is living OR None (abstention - RULES.md line 218)
- Target can be self

**Tie-Breaking:**
- Tie → `tied_players` populated, `banished = None` (RULES.md line 219)

#### Invariant Rules

1. **Only Living Vote**: Dead cannot vote
2. **Sheriff Weight = 1.5**: Affects vote tally
3. **Tie = No Banishment**: Multiple with max votes → no one banished (RULES.md line 219)
4. **Abstention Valid**: Can vote for None (RULES.md line 218)
5. **No Dead Targets**: Target must be living
6. **One Vote Per Living**: Vote count equals living count
7. **Banished Must Have Max Votes**: Only top vote-getter banished

---

### 12. BanishmentResolution

After Voting, if someone is banished, their death must be resolved (last words, hunter shoot, badge transfer).

#### Context Filtering

**Input Context:**
```
- day: int - Current day
- players: dict[int, Player] - Full state (role, sheriff status)
- living_players: set[int] - Living players BEFORE banishment
- sheriff: Optional[int]
```

**Note:** `banished` target comes from the Voting handler's Banishment event (not stored in PhaseContext).

**Note:** If `banished is None`, phase returns empty SubPhaseLog (nothing to resolve).

**Output:**
```python
DeathEvent(
    actor: int,                   # Banished player seat
    cause: DeathCause.BANISHMENT,
    last_words: str | None,       # Always present for banishment
    hunter_shoot_target: int | None,  # If Hunter, can shoot
    badge_transfer_to: int | None,    # If Sheriff, transfers badge
    phase: Phase.DAY,
    sub_phase: SubPhase.BANISHMENT_RESOLUTION,
    day: int
)
```

**Processing:**
1. If `banished is None`: Return empty SubPhaseLog
2. Generate last_words for banished player (always required)
3. If banished player is Hunter: Query for shoot target (or None to skip)
4. If banished player is Sheriff: Designate badge heir (or None)

#### Validation Rules

**Valid DeathEvent Criteria:**
- `actor == banished` (the player who was voted out)
- `cause == BANISHMENT`
- `last_words` is non-empty string (always required for banishment - RULES.md line 85)
- `hunter_shoot_target`: None if not Hunter, or living player if Hunter
- `badge_transfer_to`: None if not Sheriff, or living player if Sheriff

**Hunter Shoot Rules:**
| Role | Can Shoot? |
|-------|------------|
| Hunter (banished) | Yes - one final shot (RULES.md line 155) |
| Non-Hunter | N/A - `hunter_shoot_target = None` |

#### Invariant Rules

1. **Last Words Always Required**: Banished players always have last words (RULES.md line 85)
2. **Hunter Can Shoot**: If banished Hunter, they may shoot one living player (RULES.md line 155)
3. **Hunter Shoot Target Must Be Living**: Cannot shoot dead player
4. **Sheriff Can Transfer Badge**: If Sheriff is banished, can designate heir (RULES.md line 176)
5. **Badge Heir Must Be Living**: Cannot transfer to dead player
6. **Phase Only Runs If Banished**: Empty result if `banished is None`
7. **Processing Order**: Last words → Hunter shoot → Badge transfer

---

## Day Phase Flow

### Day 1
```
Campaign → OptOut → SheriffElection → DeathResolution → Discussion → Voting → BanishmentResolution → VictoryCheck
```

### Day 2+
```
DeathResolution → Discussion → Voting → BanishmentResolution → VictoryCheck
```

**Note:** DeathResolution handles NIGHT deaths at start of day. BanishmentResolution handles banishment deaths after voting.

---

## Summary Table

| Phase | Participants | Output Event | Special Rules |
|-------|--------------|--------------|---------------|
| WerewolfAction | Living werewolves | WerewolfKill | Single collective decision |
| WitchAction | Living Witch | WitchAction | Antidote only on target, poison ignores guard |
| GuardAction | Living Guard | GuardAction | Cannot guard same person consecutively |
| SeerAction | Living Seer | SeerAction | Engine computes result, no skip |
| NightResolution | Engine | NightOutcome | Death calculation |
| Campaign | Sheriff candidates | Speech | Sheriff speaks last |
| OptOut | Sheriff candidates | SheriffOptOut | Final decision |
| SheriffElection | All living | SheriffOutcome | Tie = no sheriff |
| DeathResolution | Engine | DeathEvent | Handles NIGHT deaths only (Hunter shoot, badge transfer) |
| Discussion | Living players | Speech | Sheriff speaks last |
| Voting | Living players | Vote + Banishment | Tie = no banishment |
| BanishmentResolution | Engine | DeathEvent | Handles BANISHMENT deaths (last words, Hunter shoot, badge transfer) |
