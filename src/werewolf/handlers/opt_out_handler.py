"""OptOut handler for the Werewolf AI game.

This handler manages the Sheriff candidate opt-out subphase where candidates
who spoke during Campaign decide whether to formally enter the Sheriff race
or withdraw.
"""

from typing import Sequence, Optional, Any
from pydantic import BaseModel, Field

from werewolf.events.game_events import (
    SheriffOptOut,
    Phase,
    SubPhase,
    GameEvent,
)
from werewolf.events.event_visibility import get_public_events, format_public_events
from werewolf.ui.choices import ChoiceSpec, ChoiceOption, ChoiceType
from werewolf.prompt_levels import (
    get_opt_out_system,
    make_opt_out_context,
    build_opt_out_decision,
)
from werewolf.handlers.base import SubPhaseLog, HandlerResult, Participant, MaxRetriesExceededError


# ============================================================================
# OptOut Handler
# ============================================================================


class OptOutHandler:
    """Handler for OptOut subphase.

    Responsibilities:
    1. Build filtered context for candidates (see other candidates' seats only)
    2. Query each candidate for opt-out decision
    3. Return SheriffOptOut events for those who opt out

    Context Filtering (what candidates see):
    - Current day (must be 1)
    - Player's own candidate status
    - List of other candidates (seats only)

    What candidates do NOT see:
    - Other players' roles
    - Campaign speeches content
    - Other candidates' opt-out intentions
    """

    # Maximum retry attempts for invalid input
    max_retries: int = 3

    async def __call__(
        self,
        context: "PhaseContext",
        participants: Sequence[tuple[int, Participant]],
        events_so_far: list[GameEvent] | None = None,
    ) -> HandlerResult:
        """Execute the OptOut subphase.

        Args:
            context: Game state with day and sheriff_candidates
            participants: Sequence of (seat, Participant) tuples for candidates
            events_so_far: Previous events in the current day (for context)

        Returns:
            HandlerResult with SubPhaseLog containing SheriffOptOut events
        """
        events = []
        events_so_far = events_so_far or []

        # Validate day is 1
        if context.day != 1:
            return HandlerResult(
                subphase_log=SubPhaseLog(micro_phase=SubPhase.OPT_OUT),
                debug_info="OptOut only occurs on Day 1",
            )

        # Get living candidates from context
        living_candidates = [
            seat for seat in context.sheriff_candidates
            if context.is_alive(seat)
        ]

        # Edge case: no candidates
        if not living_candidates:
            return HandlerResult(
                subphase_log=SubPhaseLog(micro_phase=SubPhase.OPT_OUT),
                debug_info="No Sheriff candidates, skipping OptOut",
            )

        # Convert participants to dict for easier lookup
        if isinstance(participants, dict):
            participant_dict = participants
        else:
            participant_dict = dict(participants)

        # Query each candidate for their decision
        for seat in living_candidates:
            participant = participant_dict.get(seat)
            if participant:
                should_opt_out = await self._get_valid_decision(
                    context, participant, seat, events_so_far
                )
                if should_opt_out:
                    events.append(SheriffOptOut(
                        actor=seat,
                        phase=Phase.DAY,
                        micro_phase=SubPhase.OPT_OUT,
                        day=context.day,
                    ))

        # Build debug info
        opt_out_seats = [e.actor for e in events]
        import json
        debug_info = json.dumps({
            "total_candidates": len(living_candidates),
            "opted_out": opt_out_seats,
            "remaining_candidates": [
                c for c in living_candidates if c not in opt_out_seats
            ],
        })

        return HandlerResult(
            subphase_log=SubPhaseLog(
                micro_phase=SubPhase.OPT_OUT,
                events=events,
            ),
            debug_info=debug_info,
        )

    def _build_prompts(
        self,
        context: "PhaseContext",
        for_seat: int,
        events_so_far: list[GameEvent] | None = None,
    ) -> tuple[str, str, str]:
        """Build filtered prompts for candidate.

        Args:
            context: Game state
            for_seat: The candidate seat to build prompts for
            events_so_far: All game events for public visibility filtering

        Returns:
            Tuple of (system_prompt, llm_user_prompt, human_user_prompt)
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
        system = get_opt_out_system()

        # Level 2: Game state context
        state_context = make_opt_out_context(context=context, your_seat=for_seat)

        # Level 3: Decision prompt
        decision = build_opt_out_decision(
            state_context,
            public_events_text=public_events_text,
        )

        # Build both LLM and TUI user prompts
        llm_user = decision.to_llm_prompt()
        human_user = decision.to_tui_prompt()

        return system, llm_user, human_user

    def _build_choices(self) -> ChoiceSpec:
        """Build ChoiceSpec for opt-out decision.

        Returns:
            ChoiceSpec with "opt out" and "stay" options
        """
        return ChoiceSpec(
            choice_type=ChoiceType.SINGLE,
            prompt='Do you want to opt out of the Sheriff race? Enter "opt out" or "stay".',
            options=[
                ChoiceOption(value="opt out", display="Opt Out (withdraw from race)"),
                ChoiceOption(value="stay", display="Stay (remain in race)"),
            ],
            allow_none=False,
        )

    async def _get_valid_decision(
        self,
        context: "PhaseContext",
        participant: Participant,
        for_seat: int,
        events_so_far: list[GameEvent] | None = None,
    ) -> bool:
        """Get valid opt-out decision from participant with retry.

        Args:
            context: Game state
            participant: The participant to query
            for_seat: The candidate seat making the decision
            events_so_far: All game events for public visibility filtering

        Returns:
            True if candidate opts out, False if they stay

        Raises:
            MaxRetriesExceededError: If max retries are exceeded
        """
        events_so_far = events_so_far or []

        for attempt in range(self.max_retries):
            system, llm_user, human_user = self._build_prompts(context, for_seat, events_so_far)

            # Select appropriate user prompt based on participant type
            user = human_user if getattr(participant, 'is_human', False) else llm_user

            # Build choices for TUI rendering
            choices = self._build_choices()

            # Add hint for retry attempts
            hint = None
            if attempt > 0:
                hint = 'Previous response was invalid. Please respond with exactly "opt out" or "stay".'

            raw = await participant.decide(system, user, hint=hint, choices=choices)

            # Parse the decision
            decision = self._parse_decision(raw)

            if decision is not None:
                return decision

            # Invalid response, provide hint
            if attempt == self.max_retries - 1:
                raise MaxRetriesExceededError(
                    f"Failed after {self.max_retries} attempts. "
                    'Please respond with exactly "opt out" or "stay".'
                )

            # Retry with hint
            hint = 'Please respond with exactly "opt out" or "stay".'
            raw = await participant.decide(system, user, hint=hint, choices=choices)
            decision = self._parse_decision(raw)

            if decision is not None:
                return decision

        # Default to staying in (safe fallback)
        return False

    def _parse_decision(self, raw_response: str) -> Optional[bool]:
        """Parse the raw response into a boolean decision.

        Args:
            raw_response: Raw string from participant

        Returns:
            True if opting out, False if staying, None if invalid
        """
        cleaned = raw_response.strip().lower()

        if cleaned == "opt out":
            return True
        elif cleaned == "stay":
            return False
        else:
            return None


# ============================================================================
# PhaseContext (for use with the handler)
# ============================================================================


class PhaseContext:
    """Minimal context for testing OptOut handler.

    This is a simpler class-based context that mirrors what the game engine
    would provide. Handlers can use is_alive() and other helper methods.
    """

    def __init__(
        self,
        sheriff_candidates: list[int],
        living_players: set[int],
        dead_players: set[int],
        day: int = 1,
    ):
        self.sheriff_candidates = sheriff_candidates
        self.living_players = living_players
        self.dead_players = dead_players
        self.day = day

    def is_alive(self, seat: int) -> bool:
        """Check if a player is alive."""
        return seat in self.living_players
