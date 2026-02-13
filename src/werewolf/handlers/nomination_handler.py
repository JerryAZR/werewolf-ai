"""Nomination handler for the Werewolf AI game.

This handler manages the Nomination subphase on Day 1 where all players
decide if they want to run for Sheriff.
"""

from typing import Sequence, Optional, Any
from pydantic import BaseModel, Field

from werewolf.events.game_events import (
    SheriffNomination,
    Phase,
    SubPhase,
    GameEvent,
)
from werewolf.events.event_visibility import get_public_events, format_public_events
from werewolf.models.player import Player, Role
from werewolf.ui.choices import ChoiceSpec, ChoiceOption, ChoiceType
from werewolf.prompt_levels import (
    get_nomination_system,
    make_nomination_context,
    build_nomination_decision,
)
from werewolf.handlers.base import SubPhaseLog, HandlerResult, Participant, MaxRetriesExceededError



# ============================================================================
# Nomination Handler
# ============================================================================


class NominationHandler:
    """Handler for Nomination subphase (Day 1 only).

    Responsibilities:
    1. Validate that day == 1 (Nomination only occurs on Day 1)
    2. Query ALL players (living and dead) for nomination decision
    3. Parse response as "run" or "not running"
    4. Return HandlerResult with SubPhaseLog containing SheriffNomination events

    Context Filtering (what players see):
    - Current day (must be 1)
    - List of all seats (living and dead)

    What players do NOT see:
        - Other players' nomination decisions (private until all collected)
    """

    # Maximum retry attempts for invalid input
    max_retries: int = 3

    async def __call__(
        self,
        context: "PhaseContext",
        participants: Sequence[tuple[int, Participant]],
        events_so_far: list[GameEvent] | None = None,
    ) -> HandlerResult:
        """Execute the Nomination subphase.

        Args:
            context: Game state with players, living/dead, sheriff, day
            participants: Sequence of (seat, Participant) tuples for all players
            events_so_far: Previous events in the current day (for context)

        Returns:
            HandlerResult with SubPhaseLog containing SheriffNomination events
        """
        events = []
        events_so_far = events_so_far or []

        # Validate day == 1
        if context.day != 1:
            return HandlerResult(
                subphase_log=SubPhaseLog(micro_phase=SubPhase.NOMINATION),
                debug_info="Nomination only occurs on Day 1, skipping",
            )

        # Build participant lookup
        participant_dict = dict(participants)

        # Query ALL players (living and dead) for nomination
        all_seats = sorted(context.players.keys())

        for seat in all_seats:
            participant = participant_dict.get(seat)
            if participant:
                # Get nomination decision (even dead players can nominate)
                decision = await self._get_valid_nomination(
                    context=context,
                    participant=participant,
                    for_seat=seat,
                    events_so_far=events_so_far,
                )
                if decision is not None:
                    events.append(decision)

        # Build debug info
        import json
        running_count = sum(1 for e in events if e.running)
        debug_info = json.dumps({
            "day": context.day,
            "total_nominations": len(events),
            "candidates_running": running_count,
        })

        return HandlerResult(
            subphase_log=SubPhaseLog(
                micro_phase=SubPhase.NOMINATION,
                events=events,
            ),
            debug_info=debug_info,
        )

    def _build_prompts(
        self,
        context: "PhaseContext",
        for_seat: int,
        events_so_far: list[GameEvent] | None = None,
    ) -> tuple[str, str]:
        """Build filtered prompts for nomination decision.

        Args:
            context: Game state
            for_seat: The player seat to build prompts for
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
        system = get_nomination_system()

        # Level 2: Game state context
        state_context = make_nomination_context(context=context, your_seat=for_seat)

        # Get player's role for Level 3
        player = context.get_player(for_seat)
        role_name = player.role.value if player else "Unknown"

        # Level 3: Decision prompt
        decision = build_nomination_decision(
            state_context,
            role=role_name,
            public_events_text=public_events_text,
        )

        # Build user prompt (combine Level 2 context + Level 3 decision)
        user = decision.to_llm_prompt()

        return system, user

    def _build_choices(self) -> ChoiceSpec:
        """Build ChoiceSpec for nomination decision.

        Returns:
            ChoiceSpec with "run" and "not running" options for TUI rendering
        """
        return ChoiceSpec(
            choice_type=ChoiceType.SINGLE,
            prompt='Do you want to run for Sheriff? Enter "run" or "not running".',
            options=[
                ChoiceOption(value="run", display="Run for Sheriff"),
                ChoiceOption(value="not running", display="Decline to Run"),
            ],
            allow_none=False,
        )

    async def _get_valid_nomination(
        self,
        context: "PhaseContext",
        participant: Participant,
        for_seat: int,
        events_so_far: list[GameEvent] | None = None,
    ) -> Optional[SheriffNomination]:
        """Get valid nomination decision from participant with retry.

        Nomination Response Protocol:
        - "run" (case-insensitive): Player wants to run
        - "not running" (case-insensitive): Player declines

        Args:
            context: Game state
            participant: The participant to query
            for_seat: The player's seat
            events_so_far: All game events for public visibility filtering

        Returns:
            SheriffNomination event with running=True/False
        """
        # Build choices for TUI rendering
        choices = self._build_choices()

        for attempt in range(self.max_retries):
            system, user = self._build_prompts(context, for_seat, events_so_far)

            # Add hint for retry attempts
            hint = None
            if attempt > 0:
                hint = 'Please enter either "run" or "not running".'

            raw = await participant.decide(system, user, hint=hint, choices=choices)

            # Parse response
            decision = self._parse_nomination(raw)

            if decision is not None:
                return SheriffNomination(
                    actor=for_seat,
                    running=decision,
                    phase=Phase.DAY,
                    micro_phase=SubPhase.NOMINATION,
                    day=context.day,
                )

            # Invalid response
            if attempt == self.max_retries - 1:
                raise MaxRetriesExceededError(
                    f"Player {for_seat} failed to provide valid nomination decision "
                    f"after {self.max_retries} attempts. Last response: {raw!r}"
                )

    def _parse_nomination(self, raw_response: str) -> Optional[bool]:
        """Parse the raw response into nomination decision.

        Args:
            raw_response: Raw string from participant

        Returns:
            True if "run", False if "not running", None if invalid
        """
        try:
            cleaned = raw_response.strip().lower()

            if cleaned == "run":
                return True
            elif cleaned == "not running":
                return False
            else:
                return None
        except (ValueError, AttributeError):
            return None


class PhaseContext:
    """Minimal context for testing Nomination handler.

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
