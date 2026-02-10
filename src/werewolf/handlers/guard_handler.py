"""GuardAction handler for the Werewolf AI game.

This handler manages the guard subphase where the living Guard can
protect a player for the night.
"""

import re
from typing import Protocol, Sequence, Optional, Any
from pydantic import BaseModel, Field

from src.werewolf.events.game_events import (
    GuardAction,
    Phase,
    SubPhase,
    GameEvent,
)
from src.werewolf.models.player import Player, Role


# ============================================================================
# Handler Result Types
# ============================================================================


class SubPhaseLog(BaseModel):
    """Generic subphase container with events."""

    micro_phase: SubPhase
    events: list[GameEvent] = Field(default_factory=list)


class HandlerResult(BaseModel):
    """Output from handlers containing all events from a subphase."""

    subphase_log: SubPhaseLog
    debug_info: Optional[str] = None


# ============================================================================
# Participant Protocol
# ============================================================================


class Participant(Protocol):
    """A player (AI or human) that can make decisions.

    The handler queries participants for their decisions during subphases.
    Participants return raw strings - handlers are responsible for parsing
    and validation.
    """

    async def decide(
        self,
        system_prompt: str,
        user_prompt: str,
        hint: Optional[str] = None,
    ) -> str:
        """Make a decision and return raw response string.

        Args:
            system_prompt: System instructions defining the role/constraints
            user_prompt: User prompt with current game state
            hint: Optional hint for invalid previous attempts

        Returns:
            Raw response string to be parsed by the handler
        """
        ...


# ============================================================================
# Guard Handler
# ============================================================================


class GuardHandler:
    """Handler for GuardAction subphase.

    Responsibilities:
    1. Check if guard is alive (return empty log if not)
    2. Build filtered context showing living players and previous guard target
    3. Query guard participant for their action
    4. Parse response into GuardAction event
    5. Validate action against consecutive night restriction
    6. Retry with hints on invalid input (up to 3 times)
    7. Return HandlerResult with SubPhaseLog containing GuardAction

    Context Filtering (what the guard sees):
    - Guard's own seat and role
    - All living players (seat numbers only)
    - Previous night's guard target (for consecutive night check)

    What the guard does NOT see:
    - Other players' roles
    - Werewolf target, Witch actions
    - Any role information

    Special Rules:
    - Cannot guard same person two consecutive nights
    - Guard CAN guard themselves
    - Target=None is allowed (skip)
    """

    # Maximum retry attempts for invalid input
    max_retries: int = 3

    async def __call__(
        self,
        context: "PhaseContext",
        participants: Sequence[tuple[int, Participant]],
        guard_prev_target: Optional[int] = None,
    ) -> HandlerResult:
        """Execute the GuardAction subphase.

        Args:
            context: Game state with players, living/dead, sheriff
            participants: Sequence of (seat, Participant) tuples
                         Should contain at most one entry (the guard)
            guard_prev_target: The player guarded previous night (None if Night 1)

        Returns:
            HandlerResult with SubPhaseLog containing GuardAction event
        """
        events = []

        # Find living guard seat
        guard_seat = None
        for seat in context.living_players:
            player = context.get_player(seat)
            if player and player.role == Role.GUARD:
                guard_seat = seat
                break

        # Edge case: no living guard
        if guard_seat is None:
            return HandlerResult(
                subphase_log=SubPhaseLog(micro_phase=SubPhase.GUARD_ACTION),
                debug_info="No living guard, skipping GuardAction",
            )

        # Get the guard participant
        participant = None
        for seat, p in participants:
            if seat == guard_seat:
                participant = p
                break

        # If no participant provided, create skip action
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

        # Query guard for valid action
        action = await self._get_valid_action(
            context=context,
            participant=participant,
            guard_seat=guard_seat,
            guard_prev_target=guard_prev_target,
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
        context: "PhaseContext",
        for_seat: int,
        guard_prev_target: Optional[int],
    ) -> tuple[str, str]:
        """Build filtered prompts for the guard.

        Args:
            context: Game state
            for_seat: The guard seat to build prompts for
            guard_prev_target: The player guarded previous night

        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        living_players_sorted = sorted(context.living_players)

        # Build system prompt
        system = f"""You are the Guard on Night {context.day}.

YOUR ROLE:
- You can protect ONE player each night from werewolf kills
- You CAN protect yourself
- You CANNOT protect the same person two nights in a row
- You may choose to skip (not protect anyone)

IMPORTANT RULES:
1. You cannot see who werewolves targeted - you must predict
2. Protecting yourself is allowed and sometimes wise
3. If you protected someone last night, you must choose a different target

Your response should be in format: TARGET_SEAT or "SKIP"
- Example: "7" (protect player at seat 7)
- Example: "SKIP" (don't protect anyone tonight)"""

        # Build user prompt with visible game state
        prev_target_info = ""
        if guard_prev_target is not None:
            prev_target_info = f"""
IMPORTANT - LAST NIGHT:
- You protected player at seat {guard_prev_target}
- You CANNOT protect seat {guard_prev_target} again tonight!"""

        living_seats_str = ', '.join(map(str, living_players_sorted))

        user = f"""=== Night {context.day} - Guard Action ===

YOUR IDENTITY:
  You are the Guard at seat {for_seat}

LIVING PLAYERS (seat numbers): {living_seats_str}{prev_target_info}

AVAILABLE ACTIONS:

1. PROTECT A PLAYER
   Description: Choose one living player to protect tonight
   Format: <seat_number>
   Example: 7
   Notes:
     - You CAN protect yourself (enter your seat number)
     - You CANNOT protect someone you protected last night

2. SKIP
   Description: Don't protect anyone tonight
   Format: SKIP
   Example: SKIP
   Notes:
     - Use this if all good players were already protected recently

Enter your choice (e.g., "7" or "SKIP"):"""

        return system, user

    async def _get_valid_action(
        self,
        context: "PhaseContext",
        participant: Participant,
        guard_seat: int,
        guard_prev_target: Optional[int],
    ) -> GuardAction:
        """Get valid action from guard participant with retry.

        Args:
            context: Game state
            participant: The participant to query
            guard_seat: The guard's seat
            guard_prev_target: The player guarded previous night

        Returns:
            Valid GuardAction event

        Raises:
            MaxRetriesExceededError: If max retries are exceeded
        """
        for attempt in range(self.max_retries):
            system, user = self._build_prompts(context, guard_seat, guard_prev_target)

            # Add hint for retry attempts
            hint = None
            if attempt > 0:
                hint = "Previous response was invalid. Please enter a seat number or 'SKIP'"

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
                guard_prev_target=guard_prev_target,
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
                raise MaxRetriesExceededError(
                    f"Failed after {self.max_retries} attempts. Last hint: {hint}"
                )

            raw = await participant.decide(system, user, hint=hint)
            target = self._parse_response(raw)

            # Validate again after retry
            validation_result = self._validate_action(
                context=context,
                target=target,
                guard_seat=guard_seat,
                guard_prev_target=guard_prev_target,
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

        # Should not reach here
        return GuardAction(
            actor=guard_seat,
            target=None,
            phase=Phase.NIGHT,
            micro_phase=SubPhase.GUARD_ACTION,
            day=context.day,
            debug_info="Max retries exceeded, defaulting to SKIP",
        )

    def _parse_response(self, raw_response: str) -> Optional[int]:
        """Parse the raw response into target seat.

        Args:
            raw_response: Raw string from participant

        Returns:
            Target seat number or None for skip

        Raises:
            ValueError: If response cannot be parsed
        """
        cleaned = raw_response.strip().upper()

        # Parse SKIP or PASS
        if cleaned in ("SKIP", "PASS", "-1"):
            return None

        # Parse seat number
        match = re.match(r'^(\d+)$', cleaned)
        if match:
            target = int(match.group(1))
            return target

        # Try with "PROTECT" prefix
        match = re.match(r'PROTECT\s+(\d+)', cleaned)
        if match:
            target = int(match.group(1))
            return target

        raise ValueError(
            f"Could not parse response: '{raw_response}'. "
            f"Please enter a seat number (e.g., '7') or 'SKIP'"
        )

    def _validate_action(
        self,
        context: "PhaseContext",
        target: Optional[int],
        guard_seat: int,
        guard_prev_target: Optional[int],
    ) -> "ValidationResult":
        """Validate guard action against game rules.

        Args:
            context: Game state
            target: The proposed target seat (None for skip)
            guard_seat: The guard's seat
            guard_prev_target: The player guarded previous night

        Returns:
            ValidationResult with is_valid and hint
        """
        # SKIP validation
        if target is None:
            return ValidationResult(
                is_valid=True,
                debug_info="action=SKIP, target=None",
            )

        # Target must be in living_players
        if target not in context.living_players:
            return ValidationResult(
                is_valid=False,
                hint="Target must be a living player. Please choose from the living players list.",
            )

        # Target must NOT be the same as previous night (consecutive night restriction)
        if guard_prev_target is not None and target == guard_prev_target:
            return ValidationResult(
                is_valid=False,
                hint=f"You cannot protect seat {target} again - you protected them last night. Please choose a different player.",
            )

        # All validations passed
        return ValidationResult(
            is_valid=True,
            debug_info=f"action=PROTECT, target={target}",
        )


class ValidationResult(BaseModel):
    """Result of action validation."""

    is_valid: bool
    hint: Optional[str] = None
    debug_info: Optional[str] = None


class MaxRetriesExceededError(Exception):
    """Raised when max retries are exceeded."""
    pass


# ============================================================================
# PhaseContext (for use with the handler)
# ============================================================================


class PhaseContext:
    """Minimal context for testing GuardAction handler.

    This is a simpler class-based context that mirrors what the game engine
    would provide. Handlers can use get_player() and other helper methods.
    """

    def __init__(
        self,
        players: dict[int, Player],
        living_players: set[int],
        dead_players: set[int],
        sheriff: Optional[int] = None,
        day: int = 1,
    ):
        self.players = players
        self.living_players = living_players
        self.dead_players = dead_players
        self.sheriff = sheriff
        self.day = day

    def get_player(self, seat: int) -> Optional[Player]:
        """Get player by seat."""
        return self.players.get(seat)

    def is_alive(self, seat: int) -> bool:
        """Check if a player is alive."""
        return seat in self.living_players
