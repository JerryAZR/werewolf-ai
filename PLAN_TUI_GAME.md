# Playable TUI Game Plan

## Overview
Create a fully playable Werewolf TUI game where:
- Human player chooses their seat at game start
- Human plays alongside AI (StubPlayer) opponents
- Game displayed in Textual TUI with proper menus
- Role revealed to human only (not shown to others)

## Current State
- `InteractiveParticipant` already exists in `src/werewolf/ui/interactive.py`
- `ChoiceSpec` and `PromptSession` exist in `src/werewolf/ui/`
- `WerewolfGame` accepts `participants` dict by seat

## Implementation Steps

### Phase 1: Game Launcher
Create/modify `play_werewolf.py`:

1. **Seat Selection Screen**
   - Display 12 seats as selectable options
   - Human picks one seat (0-11)
   - Generate shuffled roles for all seats

2. **Role Assignment**
   - Store human's role (reveal only to them)
   - Store AI roles (hidden from human)
   - Create players dict with correct roles

3. **Participant Setup**
   - `InteractiveParticipant` for human's seat
   - `StubPlayer` for all AI seats

### Phase 2: Game Display
Enhance `InteractiveParticipant` and TUI:

1. **Game Log Display**
   - Show events as they happen (narrative style)
   - Use Rich Panels/Tables for readability
   - Show deaths, speeches, votes

2. **Player Status**
   - Show living/dead players
   - Show sheriff badge
   - Hide role identities (standard Werewolf rules)

3. **Night Phase Handling**
   - Werewolves: Collect all werewolf votes, show progress
   - Other roles: Standard single-target choices

### Phase 3: Handler Integration (Optional Enhancement)
Update handlers to pass `ChoiceSpec` for better TUI:

1. `VotingHandler` - pass living players as choices
2. `WerewolfHandler` - pass living non-werewolves as choices
3. `WitchHandler` - pass action + target choices
4. etc.

### Phase 4: Running the Game
```bash
uv run python play_werewolf.py --tui    # Full TUI mode
uv run python play_werewolf.py --seed 42  # Reproducible game
```

## Files to Create/Modify

### New Files
| File | Purpose |
|------|---------|
| `play_werewolf.py` | Main entry point for playable game |

### Modify
| File | Change |
|------|--------|
| `src/werewolf/ui/interactive.py` | Enhance with game log display |
| `src/werewolf/ui/prompt_session.py` | Add game narrative display |

## Key Challenges

### 1. Werewolf Team Coordination
Werewolves need to see who their teammates are but NOT their specific roles (only know they're werewolves).

**Solution**: Custom `WerewolfParticipant` wrapper that:
- Shows human their true role
- Shows human their teammates (seats)
- Hides other roles

### 2. Night Phase Timing
Werewolves act simultaneously in real game.

**Solution**: Collect all werewolf decisions, then reveal result together.

### 3. Spectator Mode
Allow human to spectate after death.

**Solution**: After death, convert to spectator participant that auto-skips.

## Simplified MVP Approach

For v1.0, implement:

1. **Simple CLI launcher** (`play_werewolf.py`)
   - Seat selection via numbered input
   - Use existing `InteractiveParticipant` for human
   - Use `StubPlayer` for AI
   - Minimal game display (just show phase changes)

2. **No handler changes needed** - use existing prompts

3. **After-game summary** - Show full event log

This gets a playable game quickly, then enhance UI later.

## Success Criteria
- [ ] Human can join game as any seat
- [ ] Human sees their role
- [ ] Human can make all decisions (vote, abilities, speeches)
- [ ] AI opponents play alongside
- [ ] Game ends with victory/defeat
- [ ] Replayable with different seeds
