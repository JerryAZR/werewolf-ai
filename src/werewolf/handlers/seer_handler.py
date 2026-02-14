"""SeerAction handler for the Werewolf AI game.

This handler manages the seer subphase where the living Seer can
check a player's identity to see if they are a werewolf.
"""

import re
from typing import Sequence, Optional, Any, Set
from pydantic import BaseModel, Field

from werewolf.events.game_events import (
    SeerAction,
    SeerResult,
    Phase,
    SubPhase,
    GameEvent,
)
from werewolf.events.event_visibility import get_public_events, format_public_events
from werewolf.models.player import Player, Role
from werewolf.prompt_levels import (
    get_seer_system,
    make_seer_context,
    build_seer_decision,
)
from werewolf.handlers.base import SubPhaseLog, HandlerResult, Participant, MaxRetriesExceededError


def _get_choice_spec_helpers():
    """Lazy import to avoid dependency when choices not used."""
    from werewolf.ui.choices import make_seat_choice
    return make_seat_choice


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
        seer_checks: Optional[Set[int]] = None,
        events_so_far: Optional[list[GameEvent]] = None,
    ) -> HandlerResult:
        """Execute the SeerAction subphase.

        Args:
            context: Game state with players, living/dead, sheriff
            participants: Sequence of (seat, Participant) tuples
                         Should contain at most one entry (the seer)
            seer_checks: Set of seats already checked by the seer (to exclude)
            events_so_far: Previous game events for public visibility filtering

        Returns:
            HandlerResult with SubPhaseLog containing SeerAction event
        """
        events = []
        events_so_far = events_so_far or []

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
                result=self._compute_seer_result(context, default_target) if default_target else SeerResult.GOOD,
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

        # Check if there are any valid targets to check
        # (all other living players may have already been checked)
        state_context_for_check = make_seer_context(
            context=context,
            your_seat=seer_seat,
            seer_checks=seer_checks,
        )
        if not state_context_for_check.get("valid_targets"):
            # All other players have been checked, skip seer action
            return HandlerResult(
                subphase_log=SubPhaseLog(
                    micro_phase=SubPhase.SEER_ACTION,
                    events=[],
                ),
                debug_info="All other players already checked, seer skips",
            )

        # Query seer for valid target
        action = await self._get_valid_action(
            context=context,
            participant=participant,
            seer_seat=seer_seat,
            seer_checks=seer_checks,
            events_so_far=events_so_far,
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
        seer_checks: Optional[Set[int]] = None,
        events_so_far: Optional[list[GameEvent]] = None,
    ) -> tuple[str, str, str]:
        """Build filtered prompts for the seer.

        Args:
            context: Game state
            for_seat: The seer seat to build prompts for
            seer_checks: Set of seats already checked by the seer
            events_so_far: Previous game events for public visibility filtering

        Returns:
            Tuple of (system_prompt, llm_user_prompt, human_user_prompt)
        """
        events_so_far = events_so_far or []

        # Get public events
        public_events = get_public_events(events_so_far, context.day, for_seat)
        public_events_text = format_public_events(
            public_events, context.living_players, context.dead_players, for_seat,
        )

        # Get static system prompt (Level 1)
        system = get_seer_system()

        # Build game state context (Level 2)
        state_context = make_seer_context(
            context=context,
            your_seat=for_seat,
            seer_checks=seer_checks,
        )

        # Build decision prompt (Level 3) with public events
        decision = build_seer_decision(
            state_context,
            public_events_text=public_events_text,
        )

        # Build both LLM and human user prompts
        llm_user = decision.to_llm_prompt()
        human_user = decision.to_tui_prompt()

        return system, llm_user, human_user

    def build_choice_spec(
        self,
        context: "PhaseContext",
        seer_seat: int,
        seer_checks: Optional[Set[int]] = None,
    ) -> Optional[Any]:
        """Build ChoiceSpec for interactive TUI.

        Returns ChoiceSpec with valid targets (excluding self and already checked).
        """
        make_seat_choice = _get_choice_spec_helpers()

        # Build list of valid targets (all living except self)
        valid_targets = [p for p in sorted(context.living_players) if p != seer_seat]
        # Filter out already checked players - no point rechecking them
        if seer_checks:
            valid_targets = [p for p in valid_targets if p not in seer_checks]

        return make_seat_choice(
            prompt="Choose a player to check:",
            seats=valid_targets,
            allow_none=False,  # Seer must choose someone
        )

    async def _get_valid_action(
        self,
        context: "PhaseContext",
        participant: Participant,
        seer_seat: int,
        seer_checks: Optional[Set[int]] = None,
        events_so_far: Optional[list[GameEvent]] = None,
    ) -> SeerAction:
        """Get valid target from seer participant with retry.

        Args:
            context: Game state
            participant: The participant to query
            seer_seat: The seer's seat
            seer_checks: Set of seats already checked by the seer
            events_so_far: Previous game events for public visibility filtering

        Returns:
            Valid SeerAction event (result will be computed by engine)

        Raises:
            MaxRetriesExceededError: If max retries are exceeded
        """
        events_so_far = events_so_far or []

        # Build ChoiceSpec with valid targets
        choices = self.build_choice_spec(context, seer_seat, seer_checks)

        for attempt in range(self.max_retries):
            system, llm_user, human_user = self._build_prompts(context, seer_seat, seer_checks, events_so_far)
            user = human_user if getattr(participant, 'is_human', False) else llm_user

            # Add hint for retry attempts
            hint = None
            if attempt > 0:
                hint = "Previous response was invalid. Please enter a seat number (you cannot skip or check yourself)."

            raw = await participant.decide(system, user, hint=hint, choices=choices)

            try:
                target = self._parse_response(raw)
            except ValueError as e:
                hint = str(e)
                raw = await participant.decide(system, user, hint=hint, choices=choices)
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
                    result=self._compute_seer_result(context, target),
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

            raw = await participant.decide(system, user, hint=hint, choices=choices)
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
                    result=self._compute_seer_result(context, target),
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
            result=self._compute_seer_result(context, default_target) if default_target else SeerResult.GOOD,
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

    def _compute_seer_result(self, context: "PhaseContext", target: int) -> SeerResult:
        """Compute the seer's check result based on the target's actual role.

        Args:
            context: Game state with player roles
            target: The seat being checked

        Returns:
            SeerResult.WEREWOLF if target is a werewolf, SeerResult.GOOD otherwise
        """
        player = context.get_player(target)
        if player is not None and player.role == Role.WEREWOLF:
            return SeerResult.WEREWOLF
        return SeerResult.GOOD


class ValidationResult(BaseModel):
    """Result of target validation."""

    is_valid: bool
    hint: Optional[str] = None
    debug_info: Optional[str] = None


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
