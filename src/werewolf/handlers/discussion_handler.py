"""Discussion handler for the Werewolf AI game.

This handler manages the Discussion subphase where all living players
give speeches before the voting phase.
"""

import json
from typing import Protocol, Sequence, Optional, Any
from pydantic import BaseModel, Field

from werewolf.events.game_events import (
    Speech,
    Phase,
    SubPhase,
    GameEvent,
    DeathEvent,
    SeerAction,
    GuardAction,
    WitchAction,
    WitchActionType,
)
from werewolf.events.event_visibility import get_public_events, format_public_events
from werewolf.models.player import Player, Role
from werewolf.prompt_levels import (
    get_discussion_system,
    make_discussion_context,
    build_discussion_decision,
)


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
# Discussion Handler
# ============================================================================


class DiscussionHandler:
    """Handler for Discussion subphase.

    Responsibilities:
    1. Compute speaking order (Sheriff speaks LAST)
    2. Build filtered context (no role info, no night action details)
    3. Query each living player in order for their speech
    4. Validate content is non-empty
    5. Return HandlerResult with SubPhaseLog containing Speech events

    Context Filtering (what players see):
    - Current day number
    - Living player seats (no roles)
    - Sheriff identity (speaks last)
    - Previous speakers' speeches (in order)
    - Last words from morning deaths

    What players do NOT see:
    - Any role information
    - Night action details (werewolf target, witch actions, etc.)
    - Seer check results (unless voluntarily revealed)
    """

    # Maximum retry attempts for invalid input
    max_retries: int = 3

    # Toggle for clockwise/counter-clockwise alternation
    alternate_direction: bool = False

    def __init__(
        self,
        alternate_direction: bool = False,
        max_retries: int = 3,
    ):
        """Initialize the Discussion handler.

        Args:
            alternate_direction: If True, reverse direction on alternate days
            max_retries: Maximum retry attempts for invalid input
        """
        self.alternate_direction = alternate_direction
        self.max_retries = max_retries

    async def __call__(
        self,
        context: "PhaseContext",
        participants: Sequence[tuple[int, Participant]],
        events_so_far: list[GameEvent] = None,
    ) -> HandlerResult:
        """Execute the Discussion subphase.

        Args:
            context: Game state with players, living/dead, sheriff, day
            participants: Sequence of (seat, Participant) tuples for all players
            events_so_far: Previous events in the current day (for context)

        Returns:
            HandlerResult with SubPhaseLog containing Speech events
        """
        events = []
        events_so_far = events_so_far or []

        # Get living players
        living_players = sorted(context.living_players)

        # Edge case: no living players
        if not living_players:
            return HandlerResult(
                subphase_log=SubPhaseLog(micro_phase=SubPhase.DISCUSSION),
                debug_info="No living players, skipping Discussion",
            )

        # Build participant lookup
        participant_dict = dict(participants)

        # Compute speaking order (Sheriff speaks LAST)
        ordered_speakers = self._compute_speaking_order(
            living_players=living_players,
            sheriff=context.sheriff,
            day=context.day,
        )

        # Extract private history for each role (only needed for specific seats)
        # Find special role seats
        seer_seat = None
        guard_seat = None
        witch_seat = None
        for seat in living_players:
            player = context.get_player(seat)
            if player:
                if player.role == Role.SEER:
                    seer_seat = seat
                elif player.role == Role.GUARD:
                    guard_seat = seat
                elif player.role == Role.WITCH:
                    witch_seat = seat

        # Extract private info (shared across all speakers - not role-specific)
        seer_checks = self._extract_seer_checks(events_so_far, seer_seat) if seer_seat else None
        guard_prev_target = self._extract_guard_prev_target(events_so_far, guard_seat) if guard_seat else None
        witch_potions = self._extract_witch_potions(events_so_far, witch_seat) if witch_seat else None

        # Query each speaker for their speech
        for seat in ordered_speakers:
            participant = participant_dict.get(seat)
            if participant:
                speech = await self._get_valid_speech(
                    context=context,
                    participant=participant,
                    for_seat=seat,
                    speaking_order=ordered_speakers,
                    seer_checks=seer_checks,
                    guard_prev_target=guard_prev_target,
                    witch_potions=witch_potions,
                    events_so_far=events_so_far,
                )
                events.append(speech)

        # Build debug info
        debug_info = json.dumps({
            "day": context.day,
            "speakers": ordered_speakers,
            "speech_count": len(events),
            "sheriff": context.sheriff,
        })

        return HandlerResult(
            subphase_log=SubPhaseLog(
                micro_phase=SubPhase.DISCUSSION,
                events=events,
            ),
            debug_info=debug_info,
        )

    def _compute_speaking_order(
        self,
        living_players: list[int],
        sheriff: Optional[int],
        day: int,
    ) -> list[int]:
        """Compute speaking order with Sheriff speaking LAST.

        Args:
            living_players: Sorted list of living player seats
            sheriff: Current Sheriff seat (None if no Sheriff)
            day: Current day number (used for direction alternation)

        Returns:
            Ordered list of speakers with Sheriff last
        """
        # Filter out Sheriff from the list (they speak last)
        non_sheriff_speakers = [p for p in living_players if p != sheriff]
        sheriff_in_list = sheriff in living_players

        # Determine direction based on day (alternate each day)
        # Day 1: clockwise (default ascending order)
        # Day 2: counter-clockwise (reverse)
        # Day 3: clockwise again, etc.
        if self.alternate_direction and day % 2 == 0:
            non_sheriff_speakers = list(reversed(non_sheriff_speakers))

        # Sheriff speaks last if alive
        if sheriff_in_list:
            return non_sheriff_speakers + [sheriff]
        else:
            return non_sheriff_speakers

    def _extract_last_words(
        self,
        events_so_far: list[GameEvent],
    ) -> dict[int, str]:
        """Extract last words from morning deaths.

        Args:
            events_so_far: All events that have occurred

        Returns:
            Dictionary mapping dead seat -> last words
        """
        last_words = {}
        for event in events_so_far:
            if isinstance(event, DeathEvent) and event.last_words:
                last_words[event.actor] = event.last_words
        return last_words

    def _extract_previous_discussion_speeches(
        self,
        events_so_far: list[GameEvent],
    ) -> list[Speech]:
        """Extract previous discussion speeches from events.

        Args:
            events_so_far: All events that have occurred

        Returns:
            List of previous Speech events in order
        """
        speeches = []
        for event in events_so_far:
            if isinstance(event, Speech) and event.micro_phase == SubPhase.DISCUSSION:
                speeches.append(event)
        return speeches

    def _extract_seer_checks(
        self,
        events_so_far: list[GameEvent],
        seer_seat: int,
    ) -> list[tuple[int, str, int]]:
        """Extract seer's past checks: [(target, result, day)].

        Args:
            events_so_far: All events that have occurred
            seer_seat: The seer's seat number

        Returns:
            List of (target, result, day) tuples for past checks
        """
        checks = []
        for event in events_so_far:
            if isinstance(event, SeerAction) and event.actor == seer_seat:
                checks.append((event.target, event.result.value, event.day))
        return checks

    def _extract_guard_prev_target(
        self,
        events_so_far: list[GameEvent],
        guard_seat: int,
    ) -> int | None:
        """Extract guard's previous target from last GuardAction.

        Args:
            events_so_far: All events that have occurred
            guard_seat: The guard's seat number

        Returns:
            Seat number of previous guard target, or None
        """
        for event in reversed(events_so_far):
            if isinstance(event, GuardAction) and event.actor == guard_seat:
                return event.target
        return None

    def _extract_witch_potions(
        self,
        events_so_far: list[GameEvent],
        witch_seat: int,
    ) -> dict[str, int | None]:
        """Extract witch's potion usage.

        Args:
            events_so_far: All events that have occurred
            witch_seat: The witch's seat number

        Returns:
            Dict with "antidote" and "poison" keys (None if unused)
        """
        potions = {"antidote": None, "poison": None}
        for event in events_so_far:
            if isinstance(event, WitchAction) and event.actor == witch_seat:
                if event.action_type == WitchActionType.ANTIDOTE:
                    potions["antidote"] = event.target
                elif event.action_type == WitchActionType.POISON:
                    potions["poison"] = event.target
        return potions

    def _build_prompts(
        self,
        context: "PhaseContext",
        for_seat: int,
        speaking_order: list[int],
        # Private history - per role specific
        seer_checks: list[tuple[int, str, int]] | None = None,
        guard_prev_target: int | None = None,
        witch_potions: dict[str, int | None] | None = None,
        events_so_far: list[GameEvent] | None = None,
    ) -> tuple[str, str]:
        """Build filtered prompts for discussion speech.

        Args:
            context: Game state
            for_seat: The speaker's seat
            speaking_order: List of all speakers in order
            seer_checks: List of past seer checks [(target, result, day)]
            guard_prev_target: Guard's target from last night
            witch_potions: Dict of witch potion usage
            events_so_far: All game events for public visibility filtering

        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        # Get public events using the visibility filter
        public_events = get_public_events(
            events_so_far or [],
            context.day,
            for_seat,
        )

        # Format public events for the prompt
        public_events_text = format_public_events(
            public_events,
            context.living_players,
            context.dead_players,
            for_seat,
        )

        # Level 1: Static system prompt (role rules only)
        system = get_discussion_system()

        # Level 2: Game state context
        state_context = make_discussion_context(
            context=context,
            your_seat=for_seat,
            speaking_order=speaking_order,
            seer_checks=seer_checks,
            guard_prev_target=guard_prev_target,
            witch_potions=witch_potions,
        )

        # Level 3: Decision prompt (with public events text)
        decision = build_discussion_decision(
            state_context,
            public_events_text=public_events_text,
        )

        # Build user prompt (combine Level 2 context + Level 3 decision)
        user = decision.to_llm_prompt()

        return system, user

    async def _get_valid_speech(
        self,
        context: "PhaseContext",
        participant: Participant,
        for_seat: int,
        speaking_order: list[int],
        # Private history - per role specific
        seer_checks: list[tuple[int, str, int]] | None = None,
        guard_prev_target: int | None = None,
        witch_potions: dict[str, int | None] | None = None,
        events_so_far: list[GameEvent] | None = None,
    ) -> Speech:
        """Get valid discussion speech from participant with retry.

        Args:
            context: Game state
            participant: The participant to query
            for_seat: The speaker's seat
            speaking_order: List of all speakers in order
            seer_checks: List of past seer checks [(target, result, day)]
            guard_prev_target: Guard's target from last night
            witch_potions: Dict of witch potion usage
            events_so_far: All game events for public visibility filtering

        Returns:
            Valid Speech event

        Raises:
            MaxRetriesExceededError: If max retries are exceeded
        """
        for attempt in range(self.max_retries):
            system, user = self._build_prompts(
                context=context,
                for_seat=for_seat,
                speaking_order=speaking_order,
                seer_checks=seer_checks,
                guard_prev_target=guard_prev_target,
                witch_potions=witch_potions,
                events_so_far=events_so_far,
            )

            # Add hint for retry attempts
            hint = None
            if attempt > 0:
                hint = "Your speech was empty. Please provide a discussion speech."

            raw = await participant.decide(system, user, hint=hint)

            # Validate content
            content = raw.strip()
            if not content:
                if attempt == self.max_retries - 1:
                    raise MaxRetriesExceededError(
                        f"Failed after {self.max_retries} attempts. Speech was empty."
                    )
                hint = "Your speech was empty. Please provide a discussion speech."
                raw = await participant.decide(system, user, hint=hint)
                content = raw.strip()

            if content:
                # Create speech with preview for debug
                preview = content[:100] + "..." if len(content) > 100 else content
                return Speech(
                    actor=for_seat,
                    content=content,
                    phase=Phase.DAY,
                    micro_phase=SubPhase.DISCUSSION,
                    day=context.day,
                    debug_info=f"speech_preview={preview}",
                )

        # Fallback - should not reach here
        default_speech = "I have nothing to share at this time."
        return Speech(
            actor=for_seat,
            content=default_speech,
            phase=Phase.DAY,
            micro_phase=SubPhase.DISCUSSION,
            day=context.day,
            debug_info="Max retries exceeded, using default speech",
        )


class MaxRetriesExceededError(Exception):
    """Raised when max retries are exceeded."""
    pass


# ============================================================================
# PhaseContext (for use with the handler)
# ============================================================================


class PhaseContext:
    """Minimal context for testing Discussion handler.

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

    def is_alive(self, seat: int) -> bool:
        """Check if a player is alive."""
        return seat in self.living_players
