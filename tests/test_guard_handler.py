"""Comprehensive tests for GuardAction handler.

Tests cover:
- Valid scenarios: valid living player protection, skip, self-protection
- Invalid scenarios: consecutive target rejection, dead player rejection
- Edge cases: guard dead, first night, only guard alive, previously guarded players
- Prompt filtering: what guard sees vs doesn't see
"""

import pytest
from typing import Optional, Any, Protocol, Sequence
from pydantic import BaseModel, Field

from src.werewolf.events.game_events import (
    GuardAction,
    Phase,
    SubPhase,
    GameEvent,
)
from src.werewolf.events.event_log import SubPhaseLog
from src.werewolf.models.player import Player, Role


# ============================================================================
# Mock Participant for Testing
# ============================================================================


class MockParticipant:
    """Mock participant that returns configurable responses."""

    def __init__(
        self,
        response: str | None = None,
        response_iter: list[str] | None = None,
    ):
        """Initialize with a single response or an iterator of responses.

        Args:
            response: Single response string to return
            response_iter: Optional list of responses to return in sequence
        """
        self._response = response
        self._response_iter = response_iter
        self._call_count = 0

    async def decide(
        self,
        system_prompt: str,
        user_prompt: str,
        **extra: Any
    ) -> str:
        """Return configured response."""
        self._call_count += 1
        if self._response_iter and self._call_count <= len(self._response_iter):
            return self._response_iter[self._call_count - 1]
        if self._response is not None:
            return self._response
        raise ValueError("MockParticipant: no response configured")


# ============================================================================
# NightActions for GuardContext
# ============================================================================


class NightActions(BaseModel):
    """Night actions state for GuardAction handler."""

    kill_target: Optional[int] = None  # Werewolf's chosen target
    antidote_used: bool = False
    poison_used: bool = False
    guard_prev_target: Optional[int] = None  # Previous night's guard target


# ============================================================================
# GuardPhaseContext for Testing
# ============================================================================


class GuardPhaseContext(BaseModel):
    """Context for GuardAction handler testing."""

    players: dict[int, Player]
    living_players: set[int]
    dead_players: set[int]
    sheriff: Optional[int] = None
    day: int = 1
    night_actions: NightActions = NightActions()

    def get_player(self, seat: int) -> Optional[Player]:
        """Get player by seat."""
        return self.players.get(seat)

    def is_guard(self, seat: int) -> bool:
        """Check if a player is the guard."""
        player = self.get_player(seat)
        return player is not None and player.role == Role.GUARD

    def is_alive(self, seat: int) -> bool:
        """Check if a player is alive."""
        return seat in self.living_players


# ============================================================================
# Context Factory Functions
# ============================================================================


def make_context_standard_12(
    guard_prev_target: Optional[int] = None
) -> tuple[GuardPhaseContext, dict[int, MockParticipant]]:
    """Create a standard 12-player game context for Night 1.

    Roles:
    - Werewolves: seats 0, 1, 2, 3
    - Seer: seat 4
    - Witch: seat 5
    - Guard: seat 6
    - Hunter: seat 7
    - Ordinary Villagers: seats 8, 9, 10, 11

    Args:
        guard_prev_target: Previous night's guard target (None for first night)
    """
    players = {
        0: Player(seat=0, name="W1", role=Role.WEREWOLF, is_alive=True),
        1: Player(seat=1, name="W2", role=Role.WEREWOLF, is_alive=True),
        2: Player(seat=2, name="W3", role=Role.WEREWOLF, is_alive=True),
        3: Player(seat=3, name="W4", role=Role.WEREWOLF, is_alive=True),
        4: Player(seat=4, name="Seer", role=Role.SEER, is_alive=True),
        5: Player(seat=5, name="Witch", role=Role.WITCH, is_alive=True),
        6: Player(seat=6, name="Guard", role=Role.GUARD, is_alive=True),
        7: Player(seat=7, name="Hunter", role=Role.HUNTER, is_alive=True),
        8: Player(seat=8, name="V1", role=Role.ORDINARY_VILLAGER, is_alive=True),
        9: Player(seat=9, name="V2", role=Role.ORDINARY_VILLAGER, is_alive=True),
        10: Player(seat=10, name="V3", role=Role.ORDINARY_VILLAGER, is_alive=True),
        11: Player(seat=11, name="V4", role=Role.ORDINARY_VILLAGER, is_alive=True),
    }
    living = set(range(12))
    dead = set()
    night_actions = NightActions(
        kill_target=4,  # Werewolves targeting Seer
        guard_prev_target=guard_prev_target,
    )

    context = GuardPhaseContext(
        players=players,
        living_players=living,
        dead_players=dead,
        sheriff=None,
        day=1,
        night_actions=night_actions,
    )
    return context, {}


def make_context_guard_dead() -> tuple[GuardPhaseContext, dict[int, MockParticipant]]:
    """Create context where guard is dead."""
    players = {
        0: Player(seat=0, name="W1", role=Role.WEREWOLF, is_alive=True),
        1: Player(seat=1, name="W2", role=Role.WEREWOLF, is_alive=True),
        4: Player(seat=4, name="Seer", role=Role.SEER, is_alive=True),
        5: Player(seat=5, name="Witch", role=Role.WITCH, is_alive=True),
        6: Player(seat=6, name="Guard", role=Role.GUARD, is_alive=False),  # Dead!
        7: Player(seat=7, name="Hunter", role=Role.HUNTER, is_alive=True),
        8: Player(seat=8, name="V1", role=Role.ORDINARY_VILLAGER, is_alive=True),
    }
    living = {0, 1, 4, 5, 7, 8}
    dead = {2, 3, 6, 9, 10, 11}
    night_actions = NightActions(kill_target=4, guard_prev_target=None)

    context = GuardPhaseContext(
        players=players,
        living_players=living,
        dead_players=dead,
        sheriff=None,
        day=2,
        night_actions=night_actions,
    )
    return context, {}


def make_context_only_guard_alive() -> tuple[GuardPhaseContext, dict[int, MockParticipant]]:
    """Create context where only the guard is alive."""
    players = {
        6: Player(seat=6, name="Guard", role=Role.GUARD, is_alive=True),
    }
    living = {6}
    dead = {0, 1, 2, 3, 4, 5, 7, 8, 9, 10, 11}
    night_actions = NightActions(kill_target=None, guard_prev_target=None)

    context = GuardPhaseContext(
        players=players,
        living_players=living,
        dead_players=dead,
        sheriff=None,
        day=5,
        night_actions=night_actions,
    )
    return context, {}


def make_context_previously_guarded_players(
    prev_targets: set[int],
) -> tuple[GuardPhaseContext, dict[int, MockParticipant]]:
    """Create context where specific players were previously guarded.

    Args:
        prev_targets: Set of player seats that were previously guarded
    """
    players = {
        0: Player(seat=0, name="W1", role=Role.WEREWOLF, is_alive=True),
        1: Player(seat=1, name="W2", role=Role.WEREWOLF, is_alive=True),
        4: Player(seat=4, name="Seer", role=Role.SEER, is_alive=True),
        5: Player(seat=5, name="Witch", role=Role.WITCH, is_alive=True),
        6: Player(seat=6, name="Guard", role=Role.GUARD, is_alive=True),
        7: Player(seat=7, name="Hunter", role=Role.HUNTER, is_alive=True),
        8: Player(seat=8, name="V1", role=Role.ORDINARY_VILLAGER, is_alive=True),
    }
    living = {0, 1, 4, 5, 6, 7, 8}
    dead = {2, 3, 9, 10, 11}
    # Set the last guarded player
    last_prev = max(prev_targets) if prev_targets else None
    night_actions = NightActions(kill_target=4, guard_prev_target=last_prev)

    context = GuardPhaseContext(
        players=players,
        living_players=living,
        dead_players=dead,
        sheriff=None,
        day=4,
        night_actions=night_actions,
    )
    return context, {}


def make_context_first_night() -> tuple[GuardPhaseContext, dict[int, MockParticipant]]:
    """Create context for first night (no previous guard target)."""
    return make_context_standard_12(guard_prev_target=None)


def make_context_second_night() -> tuple[GuardPhaseContext, dict[int, MockParticipant]]:
    """Create context for second night (has previous guard target)."""
    players = {
        0: Player(seat=0, name="W1", role=Role.WEREWOLF, is_alive=True),
        1: Player(seat=1, name="W2", role=Role.WEREWOLF, is_alive=True),
        4: Player(seat=4, name="Seer", role=Role.SEER, is_alive=True),
        5: Player(seat=5, name="Witch", role=Role.WITCH, is_alive=True),
        6: Player(seat=6, name="Guard", role=Role.GUARD, is_alive=True),
        7: Player(seat=7, name="Hunter", role=Role.HUNTER, is_alive=True),
        8: Player(seat=8, name="V1", role=Role.ORDINARY_VILLAGER, is_alive=True),
    }
    living = {0, 1, 4, 5, 6, 7, 8}
    dead = {2, 3, 9, 10, 11}
    night_actions = NightActions(kill_target=4, guard_prev_target=8)  # Guarded seat 8 last night

    context = GuardPhaseContext(
        players=players,
        living_players=living,
        dead_players=dead,
        sheriff=None,
        day=2,
        night_actions=night_actions,
    )
    return context, {}


def make_context_dead_target() -> tuple[GuardPhaseContext, dict[int, MockParticipant]]:
    """Create context where the proposed target is dead."""
    players = {
        0: Player(seat=0, name="W1", role=Role.WEREWOLF, is_alive=True),
        1: Player(seat=1, name="W2", role=Role.WEREWOLF, is_alive=True),
        4: Player(seat=4, name="Seer", role=Role.SEER, is_alive=False),  # Dead!
        5: Player(seat=5, name="Witch", role=Role.WITCH, is_alive=True),
        6: Player(seat=6, name="Guard", role=Role.GUARD, is_alive=True),
        8: Player(seat=8, name="V1", role=Role.ORDINARY_VILLAGER, is_alive=True),
    }
    living = {0, 1, 5, 6, 8}
    dead = {2, 3, 4, 7, 9, 10, 11}
    night_actions = NightActions(kill_target=None, guard_prev_target=None)

    context = GuardPhaseContext(
        players=players,
        living_players=living,
        dead_players=dead,
        sheriff=None,
        day=2,
        night_actions=night_actions,
    )
    return context, {}


# ============================================================================
# HandlerResult and GuardHandler for Testing
# ============================================================================


class HandlerResult(BaseModel):
    """Output from handlers containing all events from a subphase."""

    subphase_log: SubPhaseLog
    debug_info: Optional[str] = None


class GuardHandler:
    """Handler for GuardAction subphase.

    Responsibilities:
    1. Check if guard is alive (return empty log if not)
    2. Build filtered context showing living players and previous target
    3. Query guard participant for their protection target
    4. Parse response into GuardAction event
    5. Validate action against game rules (no consecutive targets)
    6. Retry with hints on invalid input (up to 3 times)
    7. Return HandlerResult with SubPhaseLog containing GuardAction

    Context Filtering (what the guard sees):
    - Guard's own seat and role
    - All living player seats
    - Previous night's guard target (for consecutive night check)

    What the guard does NOT see:
    - Other players' roles (Seer, Witch, Hunter, Villager)
    - Werewolf target
    - Witch actions
    - Any role information
    """

    max_retries: int = 3

    async def __call__(
        self,
        context: GuardPhaseContext,
        participants: Sequence[tuple[int, MockParticipant]]
    ) -> HandlerResult:
        """Execute the GuardAction subphase.

        Args:
            context: Game state with players, living/dead, sheriff
            participants: Sequence of (seat, MockParticipant) tuples
                         Should contain at most one entry (the guard)

        Returns:
            HandlerResult with SubPhaseLog containing GuardAction event
        """
        events = []

        # Find living guard seat
        guard_seat = None
        for seat in context.living_players:
            if context.is_guard(seat):
                guard_seat = seat
                break

        # Edge case: no living guard
        if guard_seat is None:
            return HandlerResult(
                subphase_log=SubPhaseLog(micro_phase=SubPhase.GUARD_ACTION),
                debug_info="Guard is dead, skipping GuardAction",
            )

        # Get the guard participant
        participant = None
        for seat, p in participants:
            if seat == guard_seat:
                participant = p
                break

        # If no participant provided, default to skip
        if participant is None:
            events.append(GuardAction(
                actor=guard_seat,
                target=None,
                phase=Phase.NIGHT,
                micro_phase=SubPhase.GUARD_ACTION,
                day=context.day,
                debug_info="No participant, defaulting to skip",
            ))
            return HandlerResult(
                subphase_log=SubPhaseLog(
                    micro_phase=SubPhase.GUARD_ACTION,
                    events=events,
                ),
            )

        # Query guard for valid target
        action = await self._get_valid_action(
            context=context,
            participant=participant,
            guard_seat=guard_seat,
        )

        events.append(action)

        return HandlerResult(
            subphase_log=SubPhaseLog(
                micro_phase=SubPhase.GUARD_ACTION,
                events=events,
            ),
        )

    def _build_prompts(
        self,
        context: GuardPhaseContext,
        for_seat: int,
    ) -> tuple[str, str]:
        """Build filtered prompts for the guard.

        Args:
            context: Game state
            for_seat: The guard seat to build prompts for

        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        living_players_sorted = sorted(context.living_players)
        prev_target = context.night_actions.guard_prev_target

        # Build system prompt
        system = f"""You are the Guard on Night {context.day}.

YOUR ROLE:
- Each night, you may protect ONE living player
- You CANNOT protect the same person two nights in a row
- You CAN protect yourself
- You may skip (protect no one) if you choose

IMPORTANT RULE:
You CANNOT guard the same player that you protected last night."""

        # Add previous target info if available
        if prev_target is not None:
            system += f"""

LAST NIGHT: You protected player at seat {prev_target}
You CANNOT protect seat {prev_target} again tonight!"""

        # Build user prompt with visible game state
        living_seats_str = ', '.join(map(str, living_players_sorted))

        # List valid targets (excluding previous if applicable)
        if prev_target is not None:
            valid_targets = [str(p) for p in living_players_sorted if p != prev_target]
            invalid_targets = [str(prev_target)]
        else:
            valid_targets = [str(p) for p in living_players_sorted]
            invalid_targets = []

        user = f"""=== Night {context.day} - Guard Action ===

YOUR IDENTITY:
  You are the Guard at seat {for_seat}

LIVING PLAYERS (seat numbers): {living_seats_str}

AVAILABLE ACTIONS:

1. PROTECT <seat>
   Description: Protect a living player from werewolf attack
   Format: PROTECT <seat>
   Example: PROTECT 4
   Rules:
     - Target must be a living player
     - You CANNOT protect the same player two nights in a row
     - You CAN protect yourself

2. SKIP
   Description: Do not protect anyone tonight
   Format: SKIP
   Example: SKIP

Enter your action (e.g., "PROTECT 4" or "SKIP"):"""

        return system, user

    async def _get_valid_action(
        self,
        context: GuardPhaseContext,
        participant: MockParticipant,
        guard_seat: int,
    ) -> GuardAction:
        """Get valid action from guard participant with retry.

        Args:
            context: Game state
            participant: The participant to query
            guard_seat: The guard's seat

        Returns:
            Valid GuardAction event
        """
        prev_target = context.night_actions.guard_prev_target

        for attempt in range(self.max_retries):
            system, user = self._build_prompts(context, guard_seat)

            # Add hint for retry attempts
            hint = None
            if attempt > 0:
                hint = "Previous response was invalid. Please choose a valid action."

            raw = await participant.decide(system, user, hint=hint)

            try:
                target = self._parse_response(raw)
            except ValueError as e:
                hint = str(e)
                raw = await participant.decide(system, user, hint=hint)
                target = self._parse_response(raw)

            # Validate action
            validation_result = self._validate_action(
                context=context,
                target=target,
                guard_seat=guard_seat,
                prev_target=prev_target,
            )

            if validation_result.is_valid:
                return GuardAction(
                    actor=guard_seat,
                    target=target,
                    phase=Phase.NIGHT,
                    micro_phase=SubPhase.GUARD_ACTION,
                    day=context.day,
                    debug_info=validation_result.debug_info,
                )

            # Retry with hint
            hint = validation_result.hint
            if attempt == self.max_retries - 1:
                # Fall back to SKIP on last attempt
                return GuardAction(
                    actor=guard_seat,
                    target=None,
                    phase=Phase.NIGHT,
                    micro_phase=SubPhase.GUARD_ACTION,
                    day=context.day,
                    debug_info="Max retries exceeded, defaulting to SKIP",
                )

            raw = await participant.decide(system, user, hint=hint)
            target = self._parse_response(raw)

            # Validate again after retry
            validation_result = self._validate_action(
                context=context,
                target=target,
                guard_seat=guard_seat,
                prev_target=prev_target,
            )

            if validation_result.is_valid:
                return GuardAction(
                    actor=guard_seat,
                    target=target,
                    phase=Phase.NIGHT,
                    micro_phase=SubPhase.GUARD_ACTION,
                    day=context.day,
                    debug_info=validation_result.debug_info,
                )

        # Fall back to SKIP
        return GuardAction(
            actor=guard_seat,
            target=None,
            phase=Phase.NIGHT,
            micro_phase=SubPhase.GUARD_ACTION,
            day=context.day,
            debug_info="Max retries exceeded, defaulting to SKIP",
        )

    def _parse_response(self, raw_response: str) -> Optional[int]:
        """Parse the raw response into a target.

        Args:
            raw_response: Raw string from participant

        Returns:
            Target seat number or None for SKIP

        Raises:
            ValueError: If response cannot be parsed
        """
        cleaned = raw_response.strip().upper()

        # Parse SKIP
        if cleaned == "SKIP":
            return None

        # Parse PROTECT with target
        import re
        match = re.match(r'PROTECT\s+(\d+)', cleaned)

        if match:
            target = int(match.group(1))
            return target

        # Try alternative format: just "4" -> treat as PROTECT 4
        match = re.match(r'^(\d+)$', cleaned)
        if match:
            target = int(match.group(1))
            return target

        raise ValueError(
            f"Could not parse response: '{raw_response}'. "
            f"Please use format: PROTECT <seat> or SKIP"
        )

    def _validate_action(
        self,
        context: GuardPhaseContext,
        target: Optional[int],
        guard_seat: int,
        prev_target: Optional[int],
    ) -> "ValidationResult":
        """Validate guard action against game rules.

        Args:
            context: Game state
            target: The proposed target seat (None = SKIP)
            guard_seat: The guard's seat
            prev_target: Previous night's guard target

        Returns:
            ValidationResult with is_valid and hint
        """
        # SKIP is always valid
        if target is None:
            return ValidationResult(
                is_valid=True,
                debug_info="action=SKIP, target=None",
            )

        # Check if target is a living player
        if target not in context.living_players:
            return ValidationResult(
                is_valid=False,
                hint="Target must be a living player.",
            )

        # Check consecutive night restriction
        if target == prev_target:
            return ValidationResult(
                is_valid=False,
                hint=f"You cannot protect the same player two nights in a row. "
                     f"You protected seat {prev_target} last night. Choose a different player.",
            )

        return ValidationResult(
            is_valid=True,
            debug_info=f"action=PROTECT, target={target}",
        )


class ValidationResult(BaseModel):
    """Result of action validation."""

    is_valid: bool
    hint: Optional[str] = None
    debug_info: Optional[str] = None


# ============================================================================
# Expected GuardAction Event Factory
# ============================================================================


def expected_guard_action(
    actor: int,
    target: Optional[int] = None,
    day: int = 1,
) -> GuardAction:
    """Create an expected GuardAction event for validation."""
    return GuardAction(
        actor=actor,
        target=target,
        day=day,
        phase=Phase.NIGHT,
        micro_phase=SubPhase.GUARD_ACTION,
    )


# ============================================================================
# Tests for GuardAction Valid Scenarios
# ============================================================================


class TestGuardActionValidScenarios:
    """Tests for valid GuardAction scenarios."""

    @pytest.mark.asyncio
    async def test_guard_protects_valid_player(self):
        """Test guard protects a valid living player."""
        context, participants = make_context_first_night()

        # Guard protects Seer (seat 4)
        participants[6] = MockParticipant("PROTECT 4")

        handler = GuardHandler()
        result = await handler(context, [(6, participants[6])])

        assert result.subphase_log.micro_phase == SubPhase.GUARD_ACTION
        assert len(result.subphase_log.events) == 1

        action_event = result.subphase_log.events[0]
        assert isinstance(action_event, GuardAction)
        assert action_event.actor == 6  # Guard seat
        assert action_event.target == 4  # Seer
        assert action_event.day == context.day

    @pytest.mark.asyncio
    async def test_guard_protects_werewolf(self):
        """Test guard can protect a werewolf."""
        context, participants = make_context_first_night()

        # Guard protects werewolf (seat 0)
        participants[6] = MockParticipant("PROTECT 0")

        handler = GuardHandler()
        result = await handler(context, [(6, participants[6])])

        assert len(result.subphase_log.events) == 1

        action_event = result.subphase_log.events[0]
        assert isinstance(action_event, GuardAction)
        assert action_event.target == 0  # Werewolf

    @pytest.mark.asyncio
    async def test_guard_skips(self):
        """Test guard can skip (protect no one)."""
        context, participants = make_context_first_night()

        # Guard skips
        participants[6] = MockParticipant("SKIP")

        handler = GuardHandler()
        result = await handler(context, [(6, participants[6])])

        assert len(result.subphase_log.events) == 1

        action_event = result.subphase_log.events[0]
        assert isinstance(action_event, GuardAction)
        assert action_event.actor == 6
        assert action_event.target is None  # SKIP means no target

    @pytest.mark.asyncio
    async def test_guard_protects_self(self):
        """Test guard can protect themselves."""
        context, participants = make_context_first_night()

        # Guard protects self (seat 6)
        participants[6] = MockParticipant("PROTECT 6")

        handler = GuardHandler()
        result = await handler(context, [(6, participants[6])])

        assert len(result.subphase_log.events) == 1

        action_event = result.subphase_log.events[0]
        assert isinstance(action_event, GuardAction)
        assert action_event.target == 6  # Self-protection

    @pytest.mark.asyncio
    async def test_guard_protects_using_numeric_only_format(self):
        """Test guard can use numeric-only format (just seat number)."""
        context, participants = make_context_first_night()

        # Guard uses just the seat number
        participants[6] = MockParticipant("4")

        handler = GuardHandler()
        result = await handler(context, [(6, participants[6])])

        assert len(result.subphase_log.events) == 1

        action_event = result.subphase_log.events[0]
        assert isinstance(action_event, GuardAction)
        assert action_event.target == 4

    @pytest.mark.asyncio
    async def test_guard_protects_after_skip_night(self):
        """Test guard can protect someone after skipping previous night."""
        context, participants = make_context_first_night()
        # First night was skipped (guard_prev_target is None)

        # Second night, guard can protect anyone
        participants[6] = MockParticipant("PROTECT 4")

        handler = GuardHandler()
        result = await handler(context, [(6, participants[6])])

        assert len(result.subphase_log.events) == 1
        action_event = result.subphase_log.events[0]
        assert action_event.target == 4


# ============================================================================
# Tests for GuardAction Invalid Scenarios
# ============================================================================


class TestGuardActionInvalidScenarios:
    """Tests for invalid GuardAction scenarios with validation."""

    @pytest.mark.asyncio
    async def test_consecutive_target_rejected(self):
        """Test that protecting same player consecutively is rejected."""
        context, participants = make_context_second_night()
        # Last night: guard protected seat 8

        # Try to protect same player again
        participants[6] = MockParticipant(response_iter=["PROTECT 8", "PROTECT 4"])

        handler = GuardHandler()
        result = await handler(context, [(6, participants[6])])

        # Should eventually get valid action (second attempt)
        assert len(result.subphase_log.events) == 1
        action_event = result.subphase_log.events[0]
        assert isinstance(action_event, GuardAction)
        # Should be the corrected target, not the rejected one
        assert action_event.target == 4

    @pytest.mark.asyncio
    async def test_dead_player_rejected(self):
        """Test that protecting a dead player is rejected."""
        context, participants = make_context_dead_target()
        # Seer (seat 4) is dead

        # Try to protect dead player
        participants[6] = MockParticipant(response_iter=["PROTECT 4", "PROTECT 8"])

        handler = GuardHandler()
        result = await handler(context, [(6, participants[6])])

        # Should eventually get valid action
        assert len(result.subphase_log.events) == 1
        action_event = result.subphase_log.events[0]
        assert isinstance(action_event, GuardAction)
        # Should be the corrected target
        assert action_event.target == 8  # Living player

    @pytest.mark.asyncio
    async def test_invalid_seat_rejected(self):
        """Test that invalid seat number is rejected."""
        context, participants = make_context_first_night()

        # Try to protect invalid seat
        participants[6] = MockParticipant(response_iter=["PROTECT 12", "PROTECT 4"])

        handler = GuardHandler()
        result = await handler(context, [(6, participants[6])])

        # Should retry and eventually get valid action
        assert len(result.subphase_log.events) == 1
        action_event = result.subphase_log.events[0]
        assert isinstance(action_event, GuardAction)
        # Should fall back to valid target
        assert action_event.target == 4


# ============================================================================
# Tests for GuardAction Edge Cases
# ============================================================================


class TestGuardActionEdgeCases:
    """Tests for edge cases in GuardAction."""

    @pytest.mark.asyncio
    async def test_guard_dead_skips_phase(self):
        """Test that phase is skipped when guard is dead."""
        context, participants = make_context_guard_dead()

        # No guard participant
        handler = GuardHandler()
        result = await handler(context, [])  # Empty participants

        # Should return empty SubPhaseLog
        assert result.subphase_log.micro_phase == SubPhase.GUARD_ACTION
        assert len(result.subphase_log.events) == 0
        assert "dead" in (result.debug_info or "").lower()

    @pytest.mark.asyncio
    async def test_first_night_no_previous_target(self):
        """Test first night has no previous target restriction."""
        context, participants = make_context_first_night()

        # First night, no previous target
        # Guard can protect anyone
        participants[6] = MockParticipant("PROTECT 8")

        handler = GuardHandler()
        result = await handler(context, [(6, participants[6])])

        assert len(result.subphase_log.events) == 1
        action_event = result.subphase_log.events[0]
        assert action_event.target == 8

    @pytest.mark.asyncio
    async def test_only_guard_alive_can_skip(self):
        """Test when only guard is alive, they can only skip."""
        context, participants = make_context_only_guard_alive()

        # Guard is the only one alive
        participants[6] = MockParticipant("SKIP")

        handler = GuardHandler()
        result = await handler(context, [(6, participants[6])])

        assert len(result.subphase_log.events) == 1
        action_event = result.subphase_log.events[0]
        assert isinstance(action_event, GuardAction)
        assert action_event.target is None  # Must skip

    @pytest.mark.asyncio
    async def test_all_others_previously_guarded(self):
        """Test when all other players were previously guarded in sequence."""
        # Context where guard has protected 4, 5, 7, 8 in previous nights
        # and now 8 was protected last night
        context, participants = make_context_previously_guarded_players(
            prev_targets={4, 5, 7, 8}
        )
        # Last night: protected 8, so can't protect 8 now
        # But can protect 0, 1, 4, 5, 6 (self), 7

        # Guard protects Seer (seat 4) - was guarded before but not last night
        participants[6] = MockParticipant("PROTECT 4")

        handler = GuardHandler()
        result = await handler(context, [(6, participants[6])])

        assert len(result.subphase_log.events) == 1
        action_event = result.subphase_log.events[0]
        assert action_event.target == 4  # Valid - not consecutive

    @pytest.mark.asyncio
    async def test_guard_can_protect_previous_target_after_one_night(self):
        """Test guard can protect someone who was guarded two nights ago."""
        # Create context where guard protected seat 5 last night (night 2)
        # and protected seat 4 night before last (night 1)
        # Now on night 3, can protect seat 4 again
        players = {
            0: Player(seat=0, name="W1", role=Role.WEREWOLF, is_alive=True),
            1: Player(seat=1, name="W2", role=Role.WEREWOLF, is_alive=True),
            4: Player(seat=4, name="Seer", role=Role.SEER, is_alive=True),
            5: Player(seat=5, name="Witch", role=Role.WITCH, is_alive=True),
            6: Player(seat=6, name="Guard", role=Role.GUARD, is_alive=True),
            7: Player(seat=7, name="Hunter", role=Role.HUNTER, is_alive=True),
            8: Player(seat=8, name="V1", role=Role.ORDINARY_VILLAGER, is_alive=True),
        }
        living = {0, 1, 4, 5, 6, 7, 8}
        dead = {2, 3, 9, 10, 11}
        night_actions = NightActions(kill_target=4, guard_prev_target=5)  # Protected 5 last night

        context = GuardPhaseContext(
            players=players,
            living_players=living,
            dead_players=dead,
            sheriff=None,
            day=3,
            night_actions=night_actions,
        )

        participants: dict[int, MockParticipant] = {}

        # Guard can protect 4 again - was protected on night 1, not consecutive
        # First try invalid, then correct
        participants[6] = MockParticipant(response_iter=["PROTECT 5", "PROTECT 4"])

        handler = GuardHandler()
        result = await handler(context, [(6, participants[6])])

        assert len(result.subphase_log.events) == 1
        action_event = result.subphase_log.events[0]
        # Should be 4 (after retry with correct answer)
        assert action_event.target == 4


# ============================================================================
# Tests for GuardAction Prompt Filtering
# ============================================================================


class TestGuardActionPromptFiltering:
    """Tests for prompt filtering in GuardAction."""

    def test_guard_sees_previous_target(self):
        """Test that guard sees the previous night's guard target."""
        handler = GuardHandler()
        context, _ = make_context_second_night()
        # Last night: protected seat 8

        system, user = handler._build_prompts(context, for_seat=6)

        # Should reveal previous target
        assert "8" in system
        assert "LAST NIGHT" in system.upper() or "previously" in system.lower()

    def test_guard_sees_all_living_players(self):
        """Test that guard sees all living player seats."""
        handler = GuardHandler()
        context, _ = make_context_first_night()

        system, user = handler._build_prompts(context, for_seat=6)

        # Should show all living players
        living_players = sorted(context.living_players)
        for seat in living_players:
            assert str(seat) in user

    def test_guard_does_not_see_other_roles(self):
        """Test that guard does NOT see other players' roles."""
        handler = GuardHandler()
        context, _ = make_context_first_night()

        system, user = handler._build_prompts(context, for_seat=6)

        # Should NOT reveal special roles as identities
        assert "Seer" not in system
        assert "Witch" not in system
        assert "Hunter" not in system
        assert "Werewolf" not in system

    def test_guard_does_not_see_werewolf_target(self):
        """Test that guard does NOT see the werewolf kill target."""
        handler = GuardHandler()
        context, _ = make_context_first_night()
        # Werewolves targeting Seer (seat 4)

        system, user = handler._build_prompts(context, for_seat=6)

        # Should NOT reveal werewolf target
        # The prompt should be about choosing who to protect, not who was targeted
        assert "werewolf" not in system.lower() or "kill" not in system.lower()

    def test_guard_sees_consecutive_rule(self):
        """Test that guard prompt explains the consecutive night rule."""
        handler = GuardHandler()
        context, _ = make_context_second_night()
        # Has previous target

        system, user = handler._build_prompts(context, for_seat=6)

        # Should explain the rule
        assert "cannot" in system.lower() or "consecutive" in system.lower()

    def test_guard_sees_self_protection_allowed(self):
        """Test that guard prompt mentions self-protection is allowed."""
        handler = GuardHandler()
        context, _ = make_context_first_night()

        system, user = handler._build_prompts(context, for_seat=6)

        # Should mention self-protection
        assert "yourself" in system.lower() or "self" in system.lower()

    def test_first_night_no_previous_target_info(self):
        """Test that first night prompt doesn't show specific previous target."""
        handler = GuardHandler()
        context, _ = make_context_first_night()
        # No previous target

        system, user = handler._build_prompts(context, for_seat=6)

        # Should not have specific LAST NIGHT: You protected seat X
        # But the general rule about "cannot protect same person two nights" is still mentioned
        assert "LAST NIGHT: You protected" not in system


# ============================================================================
# Tests for GuardAction Retry Behavior
# ============================================================================


class TestGuardActionRetryBehavior:
    """Tests for retry behavior with invalid inputs."""

    @pytest.mark.asyncio
    async def test_invalid_action_triggers_retry_with_hint(self):
        """Test that invalid action triggers retry with helpful hint."""
        context, participants = make_context_second_night()

        # First response is invalid, second is valid
        participants[6] = MockParticipant(response_iter=["INVALID", "SKIP"])

        handler = GuardHandler()
        result = await handler(context, [(6, participants[6])])

        # Should have retried and succeeded
        assert len(result.subphase_log.events) == 1
        action_event = result.subphase_log.events[0]
        assert isinstance(action_event, GuardAction)
        assert action_event.target is None

    @pytest.mark.asyncio
    async def test_max_retries_falls_back_to_skip(self):
        """Test that after max retries, handler falls back to SKIP."""
        context, participants = make_context_second_night()

        # The handler retries on validation errors (not just parsing)
        # Provide invalid responses that trigger validation errors, then exhaust retries
        # Last night guard protected seat 8, so PROTECT 8 is invalid (consecutive)
        participants[6] = MockParticipant(response_iter=[
            # Round 1: Try to protect the previously guarded player (validation fails)
            "PROTECT 8",  # Invalid - consecutive target
            "PROTECT 8",  # Retry with hint - still invalid
            "PROTECT 8",  # Validation retry - still invalid

            # Round 2
            "PROTECT 8",
            "PROTECT 8",
            "PROTECT 8",

            # Round 3
            "PROTECT 8",
            "PROTECT 8",
            "PROTECT 8",
        ])

        handler = GuardHandler()
        handler.max_retries = 3

        result = await handler(context, [(6, participants[6])])

        # Should fall back to SKIP after all retries fail
        assert len(result.subphase_log.events) == 1
        action_event = result.subphase_log.events[0]
        assert isinstance(action_event, GuardAction)
        assert action_event.target is None


# ============================================================================
# Tests for GuardAction Parsing
# ============================================================================


class TestGuardActionParsing:
    """Tests for action parsing edge cases."""

    def test_parse_protect_case_insensitive(self):
        """Test that PROTECT parsing is case insensitive."""
        handler = GuardHandler()
        context, _ = make_context_first_night()

        # Different cases should all work
        target1 = handler._parse_response("protect 4")
        target2 = handler._parse_response("PROTECT 4")
        target3 = handler._parse_response("Protect 4")

        assert target1 == 4
        assert target2 == 4
        assert target3 == 4

    def test_parse_protect_with_extra_spaces(self):
        """Test parsing PROTECT with extra whitespace."""
        handler = GuardHandler()
        context, _ = make_context_first_night()

        target = handler._parse_response("  PROTECT   4  ")

        assert target == 4

    def test_parse_skip_case_insensitive(self):
        """Test that SKIP parsing is case insensitive."""
        handler = GuardHandler()
        context, _ = make_context_first_night()

        # Different cases
        target1 = handler._parse_response("skip")
        target2 = handler._parse_response("SKIP")
        target3 = handler._parse_response("Skip")

        assert target1 is None
        assert target2 is None
        assert target3 is None

    def test_parse_numeric_only(self):
        """Test parsing numeric-only response as PROTECT."""
        handler = GuardHandler()
        context, _ = make_context_first_night()

        target = handler._parse_response("7")

        assert target == 7

    def test_parse_invalid_format_raises_error(self):
        """Test that invalid format raises ValueError."""
        handler = GuardHandler()
        context, _ = make_context_first_night()

        with pytest.raises(ValueError):
            handler._parse_response("just some text")

    def test_parse_protect_without_target_raises_error(self):
        """Test that PROTECT without target raises ValueError."""
        handler = GuardHandler()
        context, _ = make_context_first_night()

        with pytest.raises(ValueError):
            handler._parse_response("PROTECT")

    def test_parse_skip_with_target_raises_error(self):
        """Test that SKIP with a target raises ValueError."""
        handler = GuardHandler()
        context, _ = make_context_first_night()

        # "SKIP 4" does not match PROTECT pattern and is not a valid format
        with pytest.raises(ValueError):
            handler._parse_response("SKIP 4")


# ============================================================================
# Tests for GuardAction Event Structure
# ============================================================================


class TestGuardActionEventStructure:
    """Tests for GuardAction event structure and fields."""

    @pytest.mark.asyncio
    async def test_event_has_correct_phase(self):
        """Test that GuardAction has correct NIGHT phase."""
        context, participants = make_context_first_night()
        participants[6] = MockParticipant("PROTECT 4")

        handler = GuardHandler()
        result = await handler(context, [(6, participants[6])])

        action_event = result.subphase_log.events[0]
        assert isinstance(action_event, GuardAction)
        assert action_event.phase == Phase.NIGHT

    @pytest.mark.asyncio
    async def test_event_has_correct_micro_phase(self):
        """Test that GuardAction has correct GUARD_ACTION micro_phase."""
        context, participants = make_context_first_night()
        participants[6] = MockParticipant("PROTECT 4")

        handler = GuardHandler()
        result = await handler(context, [(6, participants[6])])

        action_event = result.subphase_log.events[0]
        assert isinstance(action_event, GuardAction)
        assert action_event.micro_phase == SubPhase.GUARD_ACTION

    @pytest.mark.asyncio
    async def test_event_has_correct_day(self):
        """Test that GuardAction has correct day number."""
        context, participants = make_context_standard_12()
        participants[6] = MockParticipant("PROTECT 4")

        handler = GuardHandler()
        result = await handler(context, [(6, participants[6])])

        action_event = result.subphase_log.events[0]
        assert isinstance(action_event, GuardAction)
        assert action_event.day == context.day

    @pytest.mark.asyncio
    async def test_skip_event_has_none_target(self):
        """Test that SKIP action has None target."""
        context, participants = make_context_first_night()
        participants[6] = MockParticipant("SKIP")

        handler = GuardHandler()
        result = await handler(context, [(6, participants[6])])

        action_event = result.subphase_log.events[0]
        assert isinstance(action_event, GuardAction)
        assert action_event.target is None

    @pytest.mark.asyncio
    async def test_event_str_representation(self):
        """Test GuardAction string representation."""
        context, participants = make_context_first_night()
        participants[6] = MockParticipant("PROTECT 4")

        handler = GuardHandler()
        result = await handler(context, [(6, participants[6])])

        action_event = result.subphase_log.events[0]
        action_str = str(action_event)

        assert "GuardAction" in action_str
        assert "target=4" in action_str
