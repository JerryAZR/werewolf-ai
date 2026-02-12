"""Nomination handler for the Werewolf AI game.

This handler manages the Nomination subphase on Day 1 where all players
decide if they want to run for Sheriff.
"""

from typing import Protocol, Sequence, Optional, Any
from pydantic import BaseModel, Field

from werewolf.events.game_events import (
    SheriffNomination,
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
    ) -> HandlerResult:
        """Execute the Nomination subphase.

        Args:
            context: Game state with players, living/dead, sheriff, day
            participants: Sequence of (seat, Participant) tuples for all players

        Returns:
            HandlerResult with SubPhaseLog containing SheriffNomination events
        """
        events = []

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
    ) -> tuple[str, str]:
        """Build filtered prompts for nomination decision.

        Args:
            context: Game state
            for_seat: The player seat to build prompts for

        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        player = context.get_player(for_seat)
        role_name = player.role.value if player else "Unknown"
        is_alive = context.is_alive(for_seat)

        # Build system prompt
        system = f"""You are deciding whether to run for Sheriff on Day {context.day}.

SHERIFF POWERS:
- The Sheriff has 1.5x vote weight during voting phases
- If eliminated, the Sheriff can transfer the badge to another player
- The Sheriff speaks LAST during all discussion phases

NOMINATION RULES:
- You may choose to run for Sheriff or decline
- If you run, you will give a campaign speech (optional, can opt-out during speech)
- If you decline, you will not appear in the election
- Your decision is private until all players have nominated

Your response should be exactly one of:
- "run" - You want to run for Sheriff
- "not running" - You decline to run for Sheriff"""

        # Build user prompt
        alive_status = "Living" if is_alive else "Dead"
        user = f"""=== Day {context.day} - Sheriff Nomination ===

YOUR INFORMATION:
  Your seat: {for_seat}
  Your role: {role_name}
  Status: {alive_status}

SHERIFF POWERS:
  - 1.5x vote weight during voting phases
  - Can transfer badge if eliminated
  - Speaks LAST during discussions

NOMINATION DECISION:
  You may either:
  - "run" - Declare your candidacy for Sheriff
  - "not running" - Decline to run for Sheriff

If you run, you will have a chance to give a campaign speech later.
Your nomination decision is private until all players have responded.

Enter your decision:"""

        return system, user

    async def _get_valid_nomination(
        self,
        context: "PhaseContext",
        participant: Participant,
        for_seat: int,
    ) -> Optional[SheriffNomination]:
        """Get valid nomination decision from participant with retry.

        Nomination Response Protocol:
        - "run" (case-insensitive): Player wants to run
        - "not running" (case-insensitive): Player declines

        Args:
            context: Game state
            participant: The participant to query
            for_seat: The player's seat

        Returns:
            SheriffNomination event with running=True/False
        """
        for attempt in range(self.max_retries):
            system, user = self._build_prompts(context, for_seat)

            # Add hint for retry attempts
            hint = None
            if attempt > 0:
                hint = 'Please enter either "run" or "not running".'

            raw = await participant.decide(system, user, hint=hint)

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
                # Default to not running on failure
                return SheriffNomination(
                    actor=for_seat,
                    running=False,
                    phase=Phase.DAY,
                    micro_phase=SubPhase.NOMINATION,
                    day=context.day,
                    debug_info="Max retries exceeded, defaulting to not running",
                )

        # Fallback (should not reach here)
        return SheriffNomination(
            actor=for_seat,
            running=False,
            phase=Phase.DAY,
            micro_phase=SubPhase.NOMINATION,
            day=context.day,
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


class MaxRetriesExceededError(Exception):
    """Raised when max retries are exceeded."""
    pass


# ============================================================================
# PhaseContext (for use with the handler)
# ============================================================================


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
