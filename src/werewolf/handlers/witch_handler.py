"""WitchAction handler for the Werewolf AI game.

This handler manages the witch subphase where the living Witch can use
their antidote to save a werewolf target or their poison to kill a player.
"""

from typing import Protocol, Sequence, Optional, Any
from pydantic import BaseModel, Field

from werewolf.events.game_events import (
    WitchAction,
    WitchActionType,
    Phase,
    SubPhase,
    GameEvent,
)
from werewolf.models.player import Player, Role

# Lazy import for ChoiceSpec to avoid circular imports
def _get_choice_spec():
    from werewolf.ui.choices import ChoiceSpec, ChoiceOption, make_action_choice, make_seat_choice
    return ChoiceSpec, ChoiceOption, make_action_choice, make_seat_choice


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
# Night Actions Context
# ============================================================================


class NightActions(BaseModel):
    """Night action results accumulated from previous phases."""

    kill_target: Optional[int] = None  # Werewolf kill target
    antidote_used: bool = False
    poison_used: bool = False


# ============================================================================
# Witch Handler
# ============================================================================


class WitchHandler:
    """Handler for WitchAction subphase.

    Responsibilities:
    1. Check if witch is alive (return empty log if not)
    2. Build filtered context showing werewolf target and remaining potions
    3. Query witch participant for their action
    4. Parse response into WitchAction event
    5. Validate action against game rules
    6. Retry with hints on invalid input (up to 3 times)
    7. Return HandlerResult with SubPhaseLog containing WitchAction

    Context Filtering (what the witch sees):
    - Witch's own seat and role
    - Werewolf kill target (critical for antidote decision)
    - Remaining potions: antidote (1/0), poison (1/0)
    - All living player seats

    What the witch does NOT see:
    - Other players' roles (Seer, Guard, Hunter, Villager)
    - Guard protection target
    - Werewolf team composition
    """

    # Maximum retry attempts for invalid input
    max_retries: int = 3

    async def __call__(
        self,
        context: "PhaseContext",
        participants: Sequence[tuple[int, Participant]],
        night_actions: NightActions,
    ) -> HandlerResult:
        """Execute the WitchAction subphase.

        Args:
            context: Game state with players, living/dead, sheriff
            participants: Sequence of (seat, Participant) tuples
                         Should contain at most one entry (the witch)
            night_actions: Night action data including kill_target, antidote_used, poison_used

        Returns:
            HandlerResult with SubPhaseLog containing WitchAction event
        """
        events = []

        # Find living witch seat
        witch_seat = None
        for seat in context.living_players:
            player = context.get_player(seat)
            if player and player.role == Role.WITCH:
                witch_seat = seat
                break

        # Edge case: no living witch
        if witch_seat is None:
            return HandlerResult(
                subphase_log=SubPhaseLog(micro_phase=SubPhase.WITCH_ACTION),
                debug_info="No living witch, skipping WitchAction",
            )

        # Get the witch participant
        participant = None
        for seat, p in participants:
            if seat == witch_seat:
                participant = p
                break

        # If no participant provided, create PASS action
        if participant is None:
            events.append(WitchAction(
                actor=witch_seat,
                action_type=WitchActionType.PASS,
                target=None,
                phase=Phase.NIGHT,
                micro_phase=SubPhase.WITCH_ACTION,
                day=context.day,
                debug_info="No participant, defaulting to PASS",
            ))
            return HandlerResult(
                subphase_log=SubPhaseLog(
                    micro_phase=SubPhase.WITCH_ACTION,
                    events=events,
                ),
            )

        # Query witch for valid action
        action = await self._get_valid_action(
            context=context,
            participant=participant,
            witch_seat=witch_seat,
            night_actions=night_actions,
        )

        events.append(action)

        return HandlerResult(
            subphase_log=SubPhaseLog(
                micro_phase=SubPhase.WITCH_ACTION,
                events=events,
            ),
        )

    def _build_prompts(
        self,
        context: "PhaseContext",
        for_seat: int,
        night_actions: NightActions,
    ) -> tuple[str, str]:
        """Build filtered prompts for the witch.

        Args:
            context: Game state
            for_seat: The witch seat to build prompts for
            night_actions: Night action data

        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        living_players_sorted = sorted(context.living_players)
        antidote_available = not night_actions.antidote_used
        poison_available = not night_actions.poison_used
        kill_target = night_actions.kill_target

        # Build system prompt
        system = f"""You are the Witch on Night {context.day}.

YOUR ROLE:
- You have ONE antidote (saves werewolf target) and ONE poison (kills any player)
- The antidote CANNOT be used on yourself
- The poison IGNORES the Guard's protection
- You can only use ONE potion per night (antidote OR poison, not both)
- If you don't use a potion, you can use it in a future night

YOUR POTIONS:
- Antidote: {'Available' if antidote_available else 'Used'} {'(can save werewolf target)' if antidote_available and kill_target is not None else ''}
- Poison: {'Available' if poison_available else 'Used'}

IMPORTANT RULES:
1. ANTIDOTE: Target must be the werewolf kill target, and you cannot antidote yourself
2. POISON: Target can be ANY living player (including werewolves)
3. PASS: Use PASS if you don't want to use any potion (target must be None)

Your response should be in format: ACTION TARGET
- Example: "PASS" (no potion)
- Example: "ANTIDOTE 7" (save player at seat 7)
- Example: "POISON 3" (poison player at seat 3)"""

        # Build user prompt with visible game state
        target_info = ""
        if kill_target is not None:
            target_info = f"""
WEREWOLF KILL TARGET: Player at seat {kill_target}
- If you use ANTIDOTE, you MUST target seat {kill_target}
- This is the only valid antidote target"""

        living_seats_str = ', '.join(map(str, living_players_sorted))

        user = f"""=== Night {context.day} - Witch Action ===

YOUR IDENTITY:
  You are the Witch at seat {for_seat}

YOUR POTIONS:
  - Antidote: {'Available (1 remaining)' if antidote_available else 'Used (0 remaining)'}
  - Poison: {'Available (1 remaining)' if poison_available else 'Used (0 remaining)'}{target_info}

LIVING PLAYERS (seat numbers): {living_seats_str}

AVAILABLE ACTIONS:

1. PASS
   Description: Do nothing this night
   Format: PASS
   Example: PASS

2. ANTIDOTE (requires antidote available + werewolf kill target)
   Description: Save the werewolf kill target from death
   Format: ANTIDOTE <seat>
   Example: ANTIDOTE 7
   Requirements:
     - Antidote must not be used yet
     - Target must be the werewolf kill target
     - Target cannot be yourself

3. POISON (requires poison available)
   Description: Kill any living player (ignores Guard protection)
   Format: POISON <seat>
   Example: POISON 3
   Requirements:
     - Poison must not be used yet
     - Target must be a living player
     - Target can be anyone (werewolf, yourself, etc.)

Enter your action (e.g., "PASS", "ANTIDOTE 7", or "POISON 3"):"""

        return system, user

    def build_choice_spec(
        self,
        context: "PhaseContext",
        witch_seat: int,
        night_actions: NightActions,
    ) -> Optional[Any]:
        """Build ChoiceSpec for interactive TUI.

        Returns a flat ChoiceSpec with all valid witch actions as string values:
        - "PASS" - do nothing
        - "ANTIDOTE {seat}" - save werewolf target
        - "POISON {seat}" - kill a player
        """
        ChoiceSpec, ChoiceOption, _, _ = _get_choice_spec()

        antidote_available = not night_actions.antidote_used
        poison_available = not night_actions.poison_used
        kill_target = night_actions.kill_target

        # Build all valid action options as flat strings
        options = []

        # PASS is always available
        options.append(ChoiceOption(value="PASS", display="Pass (do nothing)"))

        # ANTIDOTE: only valid if available, has kill target, not targeting self
        if antidote_available and kill_target is not None and kill_target != witch_seat:
            options.append(ChoiceOption(
                value=f"ANTIDOTE {kill_target}",
                display=f"Antidote (save player {kill_target})"
            ))

        # POISON: can target any living player except self
        if poison_available:
            for seat in sorted(context.living_players):
                if seat == witch_seat:
                    continue
                player = context.get_player(seat)
                if player:
                    options.append(ChoiceOption(
                        value=f"POISON {seat}",
                        display=f"Poison (kill player {seat} - {player.role.value})"
                    ))

        return ChoiceSpec(
            choice_type="single",  # type: ignore
            prompt="Choose your action:",
            options=options,
            allow_none=False,
            none_display="Pass / Skip",
        )

    async def _get_valid_action(
        self,
        context: "PhaseContext",
        participant: Participant,
        witch_seat: int,
        night_actions: NightActions,
    ) -> WitchAction:
        """Get valid action from witch participant with retry.

        Args:
            context: Game state
            participant: The participant to query
            witch_seat: The witch's seat
            night_actions: Night action data

        Returns:
            Valid WitchAction event

        Raises:
            MaxRetriesExceededError: If max retries are exceeded
        """
        for attempt in range(self.max_retries):
            system, user = self._build_prompts(context, witch_seat, night_actions)

            # Build choices for TUI rendering
            choices = self.build_choice_spec(context, witch_seat, night_actions)

            # Add hint for retry attempts
            hint = None
            if attempt > 0:
                hint = "Previous response was invalid. Please follow the format: PASS, ANTIDOTE <seat>, or POISON <seat>"

            raw = await participant.decide(system, user, hint=hint, choices=choices)

            try:
                action_type, target = self._parse_response(raw)
            except ValueError as e:
                hint = str(e)
                raw = await participant.decide(system, user, hint=hint, choices=choices)
                action_type, target = self._parse_response(raw)

            # Validate action
            validation_result = self._validate_action(
                context=context,
                action_type=action_type,
                target=target,
                witch_seat=witch_seat,
                night_actions=night_actions,
            )

            if validation_result.is_valid:
                return WitchAction(
                    actor=witch_seat,
                    action_type=action_type,
                    target=target,
                    phase=Phase.NIGHT,
                    micro_phase=SubPhase.WITCH_ACTION,
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
            action_type, target = self._parse_response(raw)

            # Validate again after retry
            validation_result = self._validate_action(
                context=context,
                action_type=action_type,
                target=target,
                witch_seat=witch_seat,
                night_actions=night_actions,
            )

            if validation_result.is_valid:
                return WitchAction(
                    actor=witch_seat,
                    action_type=action_type,
                    target=target,
                    phase=Phase.NIGHT,
                    micro_phase=SubPhase.WITCH_ACTION,
                    day=context.day,
                    debug_info=validation_result.debug_info,
                )

        # Should not reach here
        return WitchAction(
            actor=witch_seat,
            action_type=WitchActionType.PASS,
            target=None,
            phase=Phase.NIGHT,
            micro_phase=SubPhase.WITCH_ACTION,
            day=context.day,
            debug_info="Max retries exceeded, defaulting to PASS",
        )

    def _parse_response(self, raw_response: str) -> tuple[WitchActionType, Optional[int]]:
        """Parse the raw response into action type and target.

        Args:
            raw_response: Raw string from participant

        Returns:
            Tuple of (action_type, target)

        Raises:
            ValueError: If response cannot be parsed
        """
        cleaned = raw_response.strip().upper()

        # Parse PASS
        if cleaned == "PASS":
            return WitchActionType.PASS, None

        # Parse ANTIDOTE or POISON with target
        import re
        match = re.match(r'(ANTIDOTE|POISON)\s+(\d+)', cleaned)

        if match:
            action_str = match.group(1)
            target = int(match.group(2))

            if action_str == "ANTIDOTE":
                return WitchActionType.ANTIDOTE, target
            elif action_str == "POISON":
                return WitchActionType.POISON, target

        # Try alternative format: just "7" -> treat as target
        match = re.match(r'^(\d+)$', cleaned)
        if match:
            target = int(match.group(1))
            raise ValueError(
                f"Response '{raw_response}' appears to be just a target seat. "
                f"Please specify an action: PASS, ANTIDOTE <seat>, or POISON <seat>"
            )

        raise ValueError(
            f"Could not parse response: '{raw_response}'. "
            f"Please use format: PASS, ANTIDOTE <seat>, or POISON <seat>"
        )

    def _validate_action(
        self,
        context: "PhaseContext",
        action_type: WitchActionType,
        target: Optional[int],
        witch_seat: int,
        night_actions: NightActions,
    ) -> "ValidationResult":
        """Validate witch action against game rules.

        Args:
            context: Game state
            action_type: The proposed action type
            target: The proposed target seat
            witch_seat: The witch's seat
            night_actions: Night action data

        Returns:
            ValidationResult with is_valid and hint
        """
        # PASS validation
        if action_type == WitchActionType.PASS:
            if target is not None:
                return ValidationResult(
                    is_valid=False,
                    hint="PASS cannot have a target. Use just 'PASS'.",
                )
            return ValidationResult(
                is_valid=True,
                debug_info="action=PASS, target=None",
            )

        # ANTIDOTE validation
        if action_type == WitchActionType.ANTIDOTE:
            if night_actions.antidote_used:
                return ValidationResult(
                    is_valid=False,
                    hint="Antidote has already been used.",
                )

            if night_actions.kill_target is None:
                return ValidationResult(
                    is_valid=False,
                    hint="There is no werewolf kill target. You cannot use the antidote.",
                )

            if target != night_actions.kill_target:
                return ValidationResult(
                    is_valid=False,
                    hint=f"Antidote target must be the werewolf kill target (seat {night_actions.kill_target}).",
                )

            if target == witch_seat:
                return ValidationResult(
                    is_valid=False,
                    hint="You cannot use the antidote on yourself.",
                )

            return ValidationResult(
                is_valid=True,
                debug_info=f"action=ANTIDOTE, target={target}",
            )

        # POISON validation
        if action_type == WitchActionType.POISON:
            if night_actions.poison_used:
                return ValidationResult(
                    is_valid=False,
                    hint="Poison has already been used.",
                )

            if target is None:
                return ValidationResult(
                    is_valid=False,
                    hint="Poison requires a target. Use 'POISON <seat>'.",
                )

            if target not in context.living_players:
                return ValidationResult(
                    is_valid=False,
                    hint="Target must be a living player.",
                )

            return ValidationResult(
                is_valid=True,
                debug_info=f"action=POISON, target={target}",
            )

        return ValidationResult(
            is_valid=False,
            hint="Invalid action type. Use PASS, ANTIDOTE, or POISON.",
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
    """Minimal context for testing WitchAction handler.

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

    def is_werewolf(self, seat: int) -> bool:
        """Check if a player is a werewolf."""
        player = self.get_player(seat)
        return player is not None and player.role == Role.WEREWOLF

    def is_witch(self, seat: int) -> bool:
        """Check if a player is the witch."""
        player = self.get_player(seat)
        return player is not None and player.role == Role.WITCH

    def is_alive(self, seat: int) -> bool:
        """Check if a player is alive."""
        return seat in self.living_players
