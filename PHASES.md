# Phase Definitions

## Macro Phases

| Phase | Description |
|-------|-------------|
| NIGHT | Night actions, resolves into deaths |
| DAY | Day activities, may resolve into banishments |
| GAME_OVER | Victory/defeat reached |

## Micro Phases

### Night Sub-Phases

| Sub-Phase | Description |
|-----------|-------------|
| Werewolf Action | Werewolves choose kill target (single AI decision) |
| Witch Action | Witch chooses antidote/poison/pass (knows werewolf target) |
| Guard Action | Guard chooses player to protect (may skip) |
| Seer Action | Seer chooses player to check |
| Resolution | Calculate deaths, update state |

### Day Sub-Phases

| Sub-Phase | Description |
|-----------|-------------|
| Campaign | Day 1 only: Candidates give speeches |
| Opt-Out | Day 1 only: Candidates may drop out |
| Sheriff Election | Day 1 only: Vote for Sheriff |
| Death Resolution | Handle all deaths (last words, hunter shoot, badge transfer) |
| Discussion | Players speak in order |
| Voting | Vote to banish |

**Note:** Last Words, Banished Last Words, Hunter Shoot, and Badge Transfer are now consolidated into the Death Resolution sub-phase.

---

## Night Phase Flow

| Step | Actor | Action |
|------|-------|--------|
| 1 | Werewolves | Choose kill target (single AI call) |
| 2 | Witch | Choose: antidote, poison, or pass |
| 3 | Guard | Choose player to protect (may skip) |
| 4 | Seer | Choose player to check |
| 5 | Resolve | Calculate deaths, update state |

**Notes:**
- Werewolves act first, then Witch
- Guard and Seer can act in parallel (any order)
- Witch sees werewolf's target before deciding
- All night deaths announced together at next day start

---

## Day Phase Flow (Day 1)

| Step | Description |
|------|-------------|
| 1. Campaign | Candidates give speeches |
| 2. Opt-Out | Candidates may drop out of the race |
| 3. Sheriff Election | Vote for Sheriff (no abstention) |
| 4. Death Resolution | Handle all deaths (announce, last words, hunter shoot, badge transfer) |
| 5. Discussion | Players speak in order |
| 6. Voting | Vote to banish |

**Note:** Victory check happens automatically after Death Resolution and after voting. If game ends, no further events occur.

---

## Day Phase Flow (Day 2+)

| Step | Description |
|------|-------------|
| 1. Death Resolution | Handle all deaths (announce, last words, hunter shoot, badge transfer) |
| 2. Discussion | Players speak in order |
| 3. Voting | Vote to banish |

**Note:** Victory check happens automatically after Death Resolution and after voting. If game ends, no further events occur.

---

## State Diagrams

### Night Phase Flow

```mermaid
stateDiagram-v2
    [*] --> WerewolfAction
    WerewolfAction --> WitchAction
    WitchAction --> GuardAction
    GuardAction --> SeerAction: Guard & Seer parallel
    SeerAction --> NightResolution
    NightResolution --> [*]: To Day phase
```

### Day 1 Flow

```mermaid
stateDiagram-v2
    [*] --> Campaign
    Campaign --> OptOut
    OptOut --> SheriffElection
    SheriffElection --> DeathResolution
    DeathResolution --> Discussion
    Discussion --> Voting
    Voting --> VictoryCheck
    VictoryCheck --> WerewolfAction: Continue to Night
    VictoryCheck --> [*]: Game Over
```

### Day 2+ Flow

```mermaid
stateDiagram-v2
    [*] --> DeathResolution
    DeathResolution --> Discussion
    Discussion --> Voting
    Voting --> VictoryCheck
    VictoryCheck --> WerewolfAction: Continue to Night
    VictoryCheck --> [*]: Game Over
```

---

## Victory Check

Victory conditions are checked:
- After Death Resolution (if all werewolves killed, villagers win)
- After banishment (if all werewolves banished, villagers win)
- After deaths (if all gods killed or all ordinary villagers killed, werewolves win)

**Note:** Night deaths include cause information (WEREWOLF_KILL or POISON), which affects whether Hunter can shoot.

---

## Sheriff Election (Day 1)

1. Candidates give campaign speeches
2. Candidates may opt-out (drop out of the race)
3. Remaining candidates are locked in
4. Players vote (no abstention, Sheriff vote = 1.5)
5. Majority wins
6. If tie: no Sheriff elected

---

## Vote Resolution

### Normal Voting

1. All living players vote (abstention allowed, except Sheriff election)
2. Count votes (Sheriff's vote = 1.5)
3. If tied, no one is banished

---

## Special Rules

### Werewolf Night Decision

- One AI API call for the werewolf group as a whole
- Werewolves act as a single entity (no internal "discussion")

### Speaker Order

- Sheriff speaks LAST
- Others speak in alternating clockwise/counter-clockwise order

### Death Events

- Night deaths: Announced and resolved together in Death Resolution phase
- Day deaths: Occur after vote-out or Hunter shoot (during Death Resolution)
- Hunter shoot: Included in DeathEvent when Hunter dies (only if killed by werewolves)
- Sheriff badge: Transfer included in DeathEvent when Sheriff dies
- Last words: Included in DeathEvent (Night 1 only for night deaths, always for day deaths)
