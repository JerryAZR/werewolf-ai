"""GuardAction handler for the Werewolf AI game.

This handler manages the guard subphase where the living Guard can
protect a player for the night.
"""

import re
from typing import Protocol, Sequence, Optional, Any
from pydantic import BaseModel, Field

from werewolf.events.game_events import (
    GuardAction,
    Phase,
    SubPhase,
    GameEvent,
)
from werewolf.events.event_visibility import get_public_events, format_public_events
from werewolf.models.player import Player, Role
from werewolf.prompt_levels import (
    get_guard_system,
    make_guard_context,
    build_guard_decision,
)


def _get_choice_spec_helpers():
    """Lazy import to avoid dependency when choices not used."""
    from werewolf.ui.choices import make_seat_choice
    return make_seat_choice


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

    For interactive TUI play, handlers may provide a ChoiceSpec to guide
    the participant's decision-making with structured choices.
    """

    async def decide(
        self,
        system_prompt: str,
        user_prompt: str,
        hint: Optional[str] = None,
        choices: Optional[Any] = None,
    ) -> str:
        """Make a decision and return raw response string.

        Args:
            system_prompt: System instructions defining the role/constraints
            user_prompt: User prompt with current game state
            hint: Optional hint for invalid previous attempts
            choices: Optional ChoiceSpec for interactive TUI selection

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
        events_so_far: Optional[list[GameEvent]] = None,
    ) -> HandlerResult:
        """Execute the GuardAction subphase.

        Args:
            context: Game state with players, living/dead, sheriff
            participants: Sequence of (seat, Participant) tuples
                         Should contain at most one entry (the guard)
            guard_prev_target: The player guarded previous night (None if Night 1)
            events_so_far: Previous game events for public visibility filtering

        Returns:
            HandlerResult with SubPhaseLog containing GuardAction event
        """
        events = []
        events_so_far = events_so_far or []

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
            events_so_far=events_so_far,
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
        events_so_far: Optional[list[GameEvent]] = None,
    ) -> tuple[str, str]:
        """Build filtered prompts for the guard.

        Args:
            context: Game state
            for_seat: The guard seat to build prompts for
            guard_prev_target: The player guarded previous night
            events_so_far: Previous game events for public visibility filtering

        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        events_so_far = events_so_far or []

        # Get public events
        public_events = get_public_events(events_so_far, context.day, for_seat)
        public_events_text = format_public_events(
            public_events, context.living_players, context.dead_players, for_seat,
        )

        # Get static system prompt (Level 1)
        system = get_guard_system()

        # Build game state context (Level 2)
        state_context = make_guard_context(
            context=context,
            your_seat=for_seat,
            guard_prev_target=guard_prev_target,
        )

        # Build decision prompt (Level 3) with public events
        decision = build_guard_decision(
            state_context,
            public_events_text=public_events_text,
        )

        # Use LLM format for user prompt
        user = decision.to_llm_prompt()

        return system, user

    def build_choice_spec(
        self,
        context: "PhaseContext",
        guard_seat: int,
        guard_prev_target: Optional[int],
    ) -> Optional[Any]:
        """Build ChoiceSpec for interactive TUI.

        Returns ChoiceSpec with valid targets (excluding previous night's target).
        """
        make_seat_choice = _get_choice_spec_helpers()

        # Build list of valid targets (all living except previous target)
        if guard_prev_target is not None:
            valid_targets = [p for p in sorted(context.living_players) if p != guard_prev_target]
        else:
            valid_targets = list(sorted(context.living_players))

        # Guard can protect themselves, so no need to exclude own seat

        return make_seat_choice(
            prompt="Choose a player to protect:",
            seats=valid_targets,
            allow_none=True,  # Guard can skip
        )

    async def _get_valid_action(
        self,
        context: "PhaseContext",
        participant: Participant,
        guard_seat: int,
        guard_prev_target: Optional[int],
        events_so_far: Optional[list[GameEvent]] = None,
    ) -> GuardAction:
        """Get valid action from guard participant with retry.

        Args:
            context: Game state
            participant: The participant to query
            guard_seat: The guard's seat
            guard_prev_target: The player guarded previous night
            events_so_far: Previous game events for public visibility filtering

        Returns:
            Valid GuardAction event

        Raises:
            MaxRetriesExceededError: If max retries are exceeded
        """
        events_so_far = events_so_far or []

        # Build ChoiceSpec with valid targets
        choices = self.build_choice_spec(context, guard_seat, guard_prev_target)

        for attempt in range(self.max_retries):
            system, user = self._build_prompts(context, guard_seat, guard_prev_target, events_so_far)

            # Add hint for retry attempts
            hint = None
            if attempt > 0:
                hint = "Previous response was invalid. Please enter a seat number or 'SKIP'"

            raw = await participant.decide(system, user, hint=hint, choices=choices)

            try:
                target = self._parse_response(raw)
            except ValueError as e:
                hint = str(e)
                raw = await participant.decide(system, user, hint=hint, choices=choices)
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

            raw = await participant.decide(system, user, hint=hint, choices=choices)
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
