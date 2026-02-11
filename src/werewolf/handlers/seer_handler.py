"""SeerAction handler for the Werewolf AI game.

This handler manages the seer subphase where the living Seer can
check a player's identity to see if they are a werewolf.
"""

import re
from typing import Protocol, Sequence, Optional, Any
from pydantic import BaseModel, Field

from werewolf.events.game_events import (
    SeerAction,
    SeerResult,
    Phase,
    SubPhase,
    GameEvent,
)
from werewolf.models.player import Player, Role


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
# Seer Handler
# ============================================================================


class SeerHandler:
    """Handler for SeerAction subphase.

    Responsibilities:
    1. Check if seer is alive (return empty log if not)
    2. Build filtered prompt showing living players and Sheriff
    3. Query seer participant for their target
    4. Parse response into SeerAction with target
    5. ENGINE computes result (GOOD/WEREWOLF) based on target's role
    6. Validate target (must be living, not self)
    7. Retry with hints on invalid input (up to 3 times)
    8. Return HandlerResult with SubPhaseLog containing SeerAction

    Context Filtering (what the seer sees):
    - Seer's own seat and role
    - All living players (seat numbers only)
    - Sheriff (if elected)

    What the seer does NOT see:
    - Other players' roles (only learn about checked target)
    - Werewolf kill target
    - Witch actions (antidote/poison usage)
    - Guard protection target
    - Any role-specific information

    Special Rules:
    - Cannot check self
    - Must choose a target (no skip allowed)
    - Engine computes result (GOOD/WEREWOLF) based on target's actual role
    """

    # Maximum retry attempts for invalid input
    max_retries: int = 3

    async def __call__(
        self,
        context: "PhaseContext",
        participants: Sequence[tuple[int, Participant]],
    ) -> HandlerResult:
        """Execute the SeerAction subphase.

        Args:
            context: Game state with players, living/dead, sheriff
            participants: Sequence of (seat, Participant) tuples
                         Should contain at most one entry (the seer)

        Returns:
            HandlerResult with SubPhaseLog containing SeerAction event
        """
        events = []

        # Find living seer seat
        seer_seat = None
        for seat in context.living_players:
            player = context.get_player(seat)
            if player and player.role == Role.SEER:
                seer_seat = seat
                break

        # Edge case: no living seer
        if seer_seat is None:
            return HandlerResult(
                subphase_log=SubPhaseLog(micro_phase=SubPhase.SEER_ACTION),
                debug_info="No living seer, skipping SeerAction",
            )

        # Get the seer participant
        participant = None
        for seat, p in participants:
            if seat == seer_seat:
                participant = p
                break

        # If no participant provided, use default (engine will compute result)
        if participant is None:
            # Default to first living player (excluding self) if no participant
            default_target = None
            for seat in sorted(context.living_players):
                if seat != seer_seat:
                    default_target = seat
                    break

            action = SeerAction(
                actor=seer_seat,
                target=default_target,
                result=SeerResult.GOOD,  # Engine will compute correct result
                phase=Phase.NIGHT,
                micro_phase=SubPhase.SEER_ACTION,
                day=context.day,
                debug_info="No participant, defaulting to first valid target",
            )
            events.append(action)
            return HandlerResult(
                subphase_log=SubPhaseLog(
                    micro_phase=SubPhase.SEER_ACTION,
                    events=events,
                ),
            )

        # Query seer for valid target
        action = await self._get_valid_action(
            context=context,
            participant=participant,
            seer_seat=seer_seat,
        )

        events.append(action)

        return HandlerResult(
            subphase_log=SubPhaseLog(
                micro_phase=SubPhase.SEER_ACTION,
                events=events,
            ),
        )

    def _build_prompts(
        self,
        context: "PhaseContext",
        for_seat: int,
    ) -> tuple[str, str]:
        """Build filtered prompts for the seer.

        Args:
            context: Game state
            for_seat: The seer seat to build prompts for

        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        living_players_sorted = sorted(context.living_players)

        # Build system prompt
        system = f"""You are the Seer on Night {context.day}.

YOUR ROLE:
- You can check ONE player's identity each night
- Your check reveals if the player is a WEREWOLF or GOOD (not their specific role)
- You CANNOT check yourself
- You MUST choose someone to check (no skipping)

IMPORTANT RULES:
1. You only learn the result AFTER the night resolves
2. Werewolves appear as WEREWOLF
3. All other roles (Villager, Guard, Hunter, Witch, Seer) appear as GOOD
4. Make strategic choices based on suspicion and game flow

Your response should be in format: TARGET_SEAT
- Example: "7" (check player at seat 7)
- You must enter a seat number, not a name"""

        # Build user prompt with visible game state
        sheriff_info = ""
        if context.sheriff is not None:
            sheriff_info = f"""
SHERIFF: Player at seat {context.sheriff}"""

        living_seats_str = ', '.join(map(str, living_players_sorted))

        sheriff_info = ""
        if context.sheriff is not None:
            sheriff_info = f"\nSheriff: Player at seat {context.sheriff} holds the sheriff badge (1.5x vote weight)."

        user = f"""=== Night {context.day} - Seer Action ===

YOUR IDENTITY:
  You are the Seer at seat {for_seat}

LIVING PLAYERS (seat numbers): {living_seats_str}{sheriff_info}

AVAILABLE ACTIONS:

1. CHECK A PLAYER
   Description: Check if a player is a werewolf
   Format: <seat_number>
   Example: 7
   Notes:
     - You CANNOT check yourself (seat {for_seat})
     - You MUST choose someone (no skip)
     - Result will be either WEREWOLF or GOOD
     - Werewolves = WEREWOLF
     - All other roles = GOOD

Enter your choice (e.g., "7"):"""

        return system, user

    async def _get_valid_action(
        self,
        context: "PhaseContext",
        participant: Participant,
        seer_seat: int,
    ) -> SeerAction:
        """Get valid target from seer participant with retry.

        Args:
            context: Game state
            participant: The participant to query
            seer_seat: The seer's seat

        Returns:
            Valid SeerAction event (result will be computed by engine)

        Raises:
            MaxRetriesExceededError: If max retries are exceeded
        """
        for attempt in range(self.max_retries):
            system, user = self._build_prompts(context, seer_seat)

            # Add hint for retry attempts
            hint = None
            if attempt > 0:
                hint = "Previous response was invalid. Please enter a seat number (you cannot skip or check yourself)."

            raw = await participant.decide(system, user, hint=hint)

            try:
                target = self._parse_response(raw)
            except ValueError as e:
                hint = str(e)
                raw = await participant.decide(system, user, hint=hint)
                target = self._parse_response(raw)

            # Validate target
            validation_result = self._validate_target(
                context=context,
                target=target,
                seer_seat=seer_seat,
            )

            if validation_result.is_valid:
                return SeerAction(
                    actor=seer_seat,
                    target=target,
                    result=SeerResult.GOOD,  # Engine will compute correct result
                    phase=Phase.NIGHT,
                    micro_phase=SubPhase.SEER_ACTION,
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
            validation_result = self._validate_target(
                context=context,
                target=target,
                seer_seat=seer_seat,
            )

            if validation_result.is_valid:
                return SeerAction(
                    actor=seer_seat,
                    target=target,
                    result=SeerResult.GOOD,  # Engine will compute correct result
                    phase=Phase.NIGHT,
                    micro_phase=SubPhase.SEER_ACTION,
                    day=context.day,
                    debug_info=validation_result.debug_info,
                )

        # Should not reach here - use first valid target
        default_target = None
        for seat in sorted(context.living_players):
            if seat != seer_seat:
                default_target = seat
                break

        return SeerAction(
            actor=seer_seat,
            target=default_target,
            result=SeerResult.GOOD,
            phase=Phase.NIGHT,
            micro_phase=SubPhase.SEER_ACTION,
            day=context.day,
            debug_info="Max retries exceeded, defaulting to first valid target",
        )

    def _parse_response(self, raw_response: str) -> int:
        """Parse the raw response into target seat.

        Args:
            raw_response: Raw string from participant

        Returns:
            Target seat number

        Raises:
            ValueError: If response cannot be parsed as a valid seat number
        """
        cleaned = raw_response.strip()

        # Parse seat number
        match = re.match(r'^(\d+)$', cleaned)
        if match:
            target = int(match.group(1))
            return target

        # Try with "CHECK" prefix
        match = re.match(r'CHECK\s+(\d+)', cleaned, re.IGNORECASE)
        if match:
            target = int(match.group(1))
            return target

        # Try "PLAYER" prefix
        match = re.match(r'PLAYER\s+(\d+)', cleaned, re.IGNORECASE)
        if match:
            target = int(match.group(1))
            return target

        raise ValueError(
            f"Could not parse response: '{raw_response}'. "
            f"Please enter just a seat number (e.g., '7')"
        )

    def _validate_target(
        self,
        context: "PhaseContext",
        target: int,
        seer_seat: int,
    ) -> "ValidationResult":
        """Validate seer target against game rules.

        Args:
            context: Game state
            target: The proposed target seat
            seer_seat: The seer's seat

        Returns:
            ValidationResult with is_valid and hint
        """
        # Target must be in living_players
        if target not in context.living_players:
            return ValidationResult(
                is_valid=False,
                hint="Target must be a living player. Please choose from the living players list.",
            )

        # Target must NOT equal seer's seat (cannot check self)
        if target == seer_seat:
            return ValidationResult(
                is_valid=False,
                hint=f"You cannot check yourself (seat {seer_seat}). Please choose a different player.",
            )

        # All validations passed
        return ValidationResult(
            is_valid=True,
            debug_info=f"action=CHECK, target={target}",
        )


class ValidationResult(BaseModel):
    """Result of target validation."""

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
    """Minimal context for testing SeerAction handler.

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
