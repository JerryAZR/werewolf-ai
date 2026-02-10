"""OptOut handler for the Werewolf AI game.

This handler manages the Sheriff candidate opt-out subphase where candidates
who spoke during Campaign decide whether to formally enter the Sheriff race
or withdraw.
"""

from typing import Protocol, Sequence, Optional, Any
from pydantic import BaseModel, Field

from src.werewolf.events.game_events import (
    SheriffOptOut,
    Phase,
    SubPhase,
    GameEvent,
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
    ) -> HandlerResult:
        """Execute the OptOut subphase.

        Args:
            context: Game state with day and sheriff_candidates
            participants: Sequence of (seat, Participant) tuples for candidates

        Returns:
            HandlerResult with SubPhaseLog containing SheriffOptOut events
        """
        events = []

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
                    context, participant, seat
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
    ) -> tuple[str, str]:
        """Build filtered prompts for candidate.

        Args:
            context: Game state
            for_seat: The candidate seat to build prompts for

        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        # Filter visible information - only seats
        other_candidates = [
            seat for seat in context.sheriff_candidates
            if seat != for_seat and context.is_alive(seat)
        ]

        # Build system prompt
        system = f"""You are a Sheriff candidate on Day {context.day}.

Your decision is FINAL - once you opt out, you cannot rejoin the Sheriff race.
You have already given your campaign speech.

OTHER CANDIDATES (seat numbers only): {', '.join(map(str, other_candidates)) if other_candidates else 'none'}

IMPORTANT RULES:
1. This is your ONLY chance to opt out of the Sheriff race.
2. If you opt out now, you cannot receive votes this election.
3. If the Sheriff dies and passes the badge to you later, you could still become Sheriff.
4. If you stay in, you will be eligible to receive votes.
5. Your response must be either "opt out" or "stay".

Your response should be exactly one of:
- "opt out" - You withdraw from the Sheriff race
- "stay" - You remain in the race"""

        # Build user prompt
        user = f"""=== Day {context.day} - Sheriff Candidate Decision ===

OTHER CANDIDATES RUNNING:
  Seats: {other_candidates if other_candidates else 'None - you are the only candidate!'}

You have TWO options:
  - "opt out" - Withdraw from the Sheriff race (CANNOT rejoin later)
  - "stay" - Remain in the race and be eligible for votes

Enter your decision:"""

        return system, user

    async def _get_valid_decision(
        self,
        context: "PhaseContext",
        participant: Participant,
        for_seat: int,
    ) -> bool:
        """Get valid opt-out decision from participant with retry.

        Args:
            context: Game state
            participant: The participant to query
            for_seat: The candidate seat making the decision

        Returns:
            True if candidate opts out, False if they stay

        Raises:
            MaxRetriesExceededError: If max retries are exceeded
        """
        for attempt in range(self.max_retries):
            system, user = self._build_prompts(context, for_seat)

            # Add hint for retry attempts
            hint = None
            if attempt > 0:
                hint = 'Previous response was invalid. Please respond with exactly "opt out" or "stay".'

            raw = await participant.decide(system, user, hint=hint)

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
            raw = await participant.decide(system, user, hint=hint)
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


class MaxRetriesExceededError(Exception):
    """Raised when max retries are exceeded."""
    pass


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
