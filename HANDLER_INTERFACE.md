# Handler Interface Proposal

## Overview

This document proposes interfaces for:
1. **Handler ↔ Scheduler** - How handlers integrate with the phase engine
2. **Handler ↔ Participant** - How handlers query players for decisions

## Key Design Goals

- **Async-native** - Supports parallel execution of Guard/Seer phases
- **Protocol-based** - No base class required, handlers are just callables
- **Handler owns parsing & validation** - Participant returns raw strings
- **Structured events** - Uses existing `CharacterAction` subclasses from `game_events.py`

---

## Handler → Scheduler Interface

### Handler Protocol

```python
from typing import Protocol, Awaitable, Sequence

class Handler(Protocol):
    """All handlers implement this protocol.

    Handlers are stateless - they receive participants at call time,
    not constructor time. This makes testing trivial.
    """

    async def __call__(
        self,
        context: PhaseContext,
        participants: Sequence[tuple[int, Participant]]
    ) -> HandlerResult:
        """Execute the subphase and return all events.

        Args:
            context: Game state (players, living/dead, night actions, etc.)
            participants: Sequence of (seat, Participant) tuples for this phase.
                         Order matters for discussion phases.
        """
        ...
```

**Participant Convention:** `participants` is always `Sequence[tuple[int, Participant]]` where:
- `int` = seat number (0-11)
- `Participant` = the player who will make decisions

### HandlerResult

```python
class HandlerResult(BaseModel):
    """Output from handlers."""

    subphase_log: SubPhaseLog  # All events from this subphase
    debug_info: Optional[str] = None
```

---

## Handler → Participant Interface

### Participant Protocol

```python
from typing import Protocol, Any

class Participant(Protocol):
    """A player (AI or human) that can make decisions.

    Implementations:
    - AIPlayer: Calls LLM API, returns raw string
    - HumanPlayer: Reads input, returns raw string

    Note: Participant returns raw strings. Handler handles parsing
    into CharacterAction subclasses.
    """

    async def decide(
        self,
        system_prompt: str,
        user_prompt: str,
        **extra: Any
    ) -> str:
        """Make a decision and return raw response.

        Returns a raw string. Handler parses this into the appropriate
        CharacterAction subclass (WerewolfKill, Vote, etc.).
        """
        ...
```

**Key Point:** Participant returns RAW string. Handler handles:
- Parsing (string → CharacterAction)
- Validation
- Retry with hints

### AI Participant

```python
class AIPlayer:
    """AI participant - uses LLM, returns raw string."""

    def __init__(self, llm_client):
        self.llm = llm_client

    async def decide(
        self,
        system_prompt: str,
        user_prompt: str,
        **extra: Any
    ) -> str:
        """Call LLM and return raw response string."""
        response = await self.llm.complete(
            system=system_prompt,
            user=user_prompt
        )
        return response  # Raw string
```

### Human Participant

```python
class HumanPlayer:
    """Human participant - reads input, returns raw string."""

    async def decide(
        self,
        system_prompt: str,
        user_prompt: str,
        **extra: Any
    ) -> str:
        """Print prompt and return user's raw input."""
        print(f"\n{'='*50}")
        print(f"{user_prompt}")
        if 'hint' in extra:
            print(f"\nHint: {extra['hint']}")

        return input("Your decision: ")  # Raw string
```

---

## Handler Workflow

The Handler protocol defines what handlers must do. Individual handlers implement the strategy.

```python
class Handler(Protocol):
    """Handler protocol - implementations decide on strategy."""

    async def __call__(
        self,
        context: PhaseContext,
        participants: Sequence[tuple[int, Participant]]
    ) -> HandlerResult:
        """Query participants, parse responses, validate, return events."""
        ...

    def _build_prompts(
        self,
        context: PhaseContext,
        for_seat: int
    ) -> tuple[str, str]:
        """Build system and user prompts. Handler decides how to filter info."""
        ...

    def _parse(self, raw: str, expected_type: type) -> CharacterAction:
        """Parse raw string response into CharacterAction."""
        ...

    def _is_valid(self, event: CharacterAction, context: PhaseContext) -> bool:
        """Validate parsed action against game rules."""
        ...
```

**Handler responsibilities:**
1. Build prompts (filtering what info each role can see)
2. Query participants
3. Parse responses
4. Validate actions
5. Retry with hints on invalid input
6. Return HandlerResult with events

---

## Structured Events (from game_events.py)

```python
# Events handlers work with - already defined in game_events.py
class WerewolfKill(TargetAction):
    """Werewolves choose a target to kill."""
    phase: Phase = Phase.NIGHT
    micro_phase: SubPhase = SubPhase.WEREWOLF_ACTION

class WitchAction(CharacterAction):
    """Witch performs an action."""
    phase: Phase = Phase.NIGHT
    micro_phase: SubPhase = SubPhase.WITCH_ACTION
    action_type: WitchActionType  # ANTIDOTE, POISON, PASS
    target: Optional[int] = None

class GuardAction(TargetAction):
    """Guard protects a player."""
    phase: Phase = Phase.NIGHT
    micro_phase: SubPhase = SubPhase.GUARD_ACTION

class SeerAction(CharacterAction):
    """Seer checks a player's identity."""
    phase: Phase = Phase.NIGHT
    micro_phase: SubPhase = SubPhase.SEER_ACTION
    target: int
    result: SeerResult

class Vote(TargetAction):
    """A player casts their vote."""
    phase: Phase = Phase.DAY
    micro_phase: SubPhase = SubPhase.VOTING
    # target=None means abstain

class Speech(CharacterAction):
    """Player speech."""
    phase: Phase = Phase.DAY
    content: str
```

---

## Testing Filtering

```python
async def test_werewolf_does_not_see_seer_identity():
    handler = WerewolfHandler()
    context = make_context(
        werewolves=[0, 3],
        seer=5,
        villager=7
    )

    # Build prompts and inspect
    system, user = handler._build_prompts(context, for_seat=0)

    # Werewolf 0 knows werewolf 3
    assert "seat 3" in system
    assert "werewolf" in system

    # Werewolf 0 does NOT know seer identity
    assert "seat 5" not in system
    assert "seer" not in system.lower()
```

---

## Scheduler Integration

```python
class PhaseScheduler:
    """Executes phases in prescribed order."""

    def __init__(self, handlers: dict[SubPhase, Handler]):
        self.handlers = handlers

    def get_participants(
        self,
        context: PhaseContext,
        role: Role | set[Role],
        living_only: bool = True
    ) -> list[tuple[int, Participant]]:
        """Get (seat, Participant) tuples for a given role."""
        ...

    async def execute_phase(
        self,
        context: PhaseContext,
        subphases: list[SubPhase],
        role_filter: Role | set[Role] | None = None
    ) -> list[HandlerResult]:
        results = []

        for sub_phase in subphases:
            handler = self.handlers[sub_phase]

            if role_filter:
                participants = self.get_participants(context, role_filter)
            else:
                participants = self._get_all_living(context)

            result = await handler(context, participants)
            results.append(result)
            context = self._update_context(context, result)

        return results
```

---

## Summary

| Component | Responsibility |
|-----------|---------------|
| **Handler** | Build prompts, parse strings → CharacterAction, validate, retry |
| **Participant** | Return raw string (AI=LLM response, Human=user input) |
| **Scheduler** | Phase ordering, participant selection, context updates |

| Component | Signature | Async? |
|-----------|-----------|--------|
| `Handler.__call__` | `(context, participants) -> HandlerResult` | Yes |
| `Participant.decide` | `(system, user, **hint) -> str` | Yes |

**Key Points:**
- Handlers are stateless (participants passed at call time)
- Participant returns RAW string (AI→LLM response, Human→input)
- Handler parses raw → CharacterAction, validates, retries
- Scheduler owns participant selection and phase ordering
