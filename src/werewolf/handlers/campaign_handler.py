"""Campaign handler for the Werewolf AI game.

This handler manages the Campaign subphase on Day 1 where Sheriff candidates
give campaign speeches before the election.
"""

from typing import Protocol, Sequence, Optional, Any
from pydantic import BaseModel, Field

from werewolf.events.game_events import (
    Speech,
    Phase,
    SubPhase,
    GameEvent,
)
from werewolf.models.player import Player, Role


# ============================================================================
# Campaign Response Protocol
# ============================================================================

# Valid responses for campaign phase
CAMPAIGN_SPEECH = "speech"  # Valid campaign speech (non-empty)
CAMPAIGN_OPT_OUT = "opt out"  # Candidate opts out after nomination


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
# Campaign Handler
# ============================================================================


class CampaignHandler:
    """Handler for Campaign subphase (Day 1 only).

    Responsibilities:
    1. Validate that day == 1 (Campaign only occurs on Day 1)
    2. Query only nominated candidates for campaign speeches
    3. Build filtered context (role visible to self, not others)
    4. Query each candidate for their campaign speech OR opt-out
    5. Validate content is non-empty or opt-out
    6. Order speeches with Sheriff speaking LAST if incumbent running
    7. Return HandlerResult with SubPhaseLog containing Speech events

    Context Filtering (what candidates see):
    - Current day (must be 1)
    - List of Sheriff candidates (seats only)
    - Sheriff speaks LAST rule
    - Player's own role (to know if running)

    What candidates do NOT see:
    - Who died (death announcements come AFTER Campaign)
    - Other candidates' campaign speeches (private until all given)
    - Any game events from previous phases
    """

    # Maximum retry attempts for invalid input
    max_retries: int = 3

    async def __call__(
        self,
        context: "PhaseContext",
        participants: Sequence[tuple[int, Participant]],
        sheriff_candidates: list[int],
    ) -> HandlerResult:
        """Execute the Campaign subphase.

        Args:
            context: Game state with players, living/dead, sheriff, day
            participants: Sequence of (seat, Participant) tuples for all players
            sheriff_candidates: List of candidate seats running for Sheriff

        Returns:
            HandlerResult with SubPhaseLog containing Speech events
        """
        events = []

        # Validate day == 1
        if context.day != 1:
            return HandlerResult(
                subphase_log=SubPhaseLog(micro_phase=SubPhase.CAMPAIGN),
                debug_info="Campaign only occurs on Day 1, skipping",
            )

        # Filter living candidates and get their participants
        living_candidates = [
            seat for seat in sheriff_candidates
            if seat in context.living_players
        ]

        # Edge case: no living candidates
        if not living_candidates:
            return HandlerResult(
                subphase_log=SubPhaseLog(micro_phase=SubPhase.CAMPAIGN),
                debug_info="No living Sheriff candidates",
            )

        # Get opted-out seats from sheriff_candidates (candidates who opted out during nomination)
        opted_out_seats = set(sheriff_candidates) - set(living_candidates)

        # Build participant lookup
        participant_dict = dict(participants)

        # Order candidates: non-Sheriff first, Sheriff speaks LAST
        current_sheriff = context.sheriff
        ordered_candidates = self._order_speakers(living_candidates, current_sheriff)

        # Query each candidate for their speech
        for seat in ordered_candidates:
            participant = participant_dict.get(seat)
            if participant:
                speech = await self._get_valid_speech(
                    context=context,
                    participant=participant,
                    for_seat=seat,
                    candidates=ordered_candidates,
                )
                # Skip "not running" responses
                if speech is not None:
                    events.append(speech)

        # Build debug info
        import json
        debug_info = json.dumps({
            "day": context.day,
            "candidates": ordered_candidates,
            "speech_count": len(events),
        })

        return HandlerResult(
            subphase_log=SubPhaseLog(
                micro_phase=SubPhase.CAMPAIGN,
                events=events,
            ),
            debug_info=debug_info,
        )

    def _order_speakers(
        self,
        candidates: list[int],
        current_sheriff: Optional[int],
    ) -> list[int]:
        """Order candidates so Sheriff speaks last if running.

        Args:
            candidates: List of candidate seats
            current_sheriff: Current Sheriff seat (None on Day 1)

        Returns:
            Candidates ordered with Sheriff last if running
        """
        if current_sheriff is None or current_sheriff not in candidates:
            # No incumbent Sheriff running, maintain original order
            return sorted(candidates)

        # Sheriff is running, put them last
        return sorted(candidates, key=lambda s: s == current_sheriff)

    def _build_prompts(
        self,
        context: "PhaseContext",
        for_seat: int,
        candidates: list[int],
    ) -> tuple[str, str]:
        """Build filtered prompts for campaign speech.

        Args:
            context: Game state
            for_seat: The candidate seat to build prompts for
            candidates: List of all candidate seats (ordered)

        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        player = context.get_player(for_seat)
        role_name = player.role.value if player else "Unknown"

        # Other candidates (seats only, not roles)
        other_candidates = [c for c in candidates if c != for_seat]
        other_candidates_str = ', '.join(map(str, sorted(other_candidates)))

        # Position in speaking order
        position = candidates.index(for_seat) + 1
        total = len(candidates)

        # Check if Sheriff (incumbent) is running and will speak last
        incumbent = context.sheriff
        sheriff_running = incumbent is not None and incumbent in candidates

        sheriff_note = ""
        if sheriff_running:
            sheriff_note = f"\n- Note: The incumbent Sheriff (seat {incumbent}) is also running and will speak LAST."

        # Build system prompt
        system = f"""You are running for Sheriff on Day {context.day}.

SHERIFF POWERS:
- The Sheriff has 1.5x vote weight during voting phases
- If eliminated, the Sheriff can transfer the badge to another player
- The Sheriff speaks LAST during all discussion phases

CAMPAIGN RESPONSE PROTOCOL:
You have two choices:
1. Give a campaign speech (any non-empty text)
2. Say "opt out" to withdraw from the race (you already nominated)

If you give a speech, it will be visible to all players.
If you say "opt out", you will not appear in the election.

Your response should be your campaign speech as a single string.
Make it compelling and appropriate for a social deduction game."""

        # Build user prompt
        user = f"""=== Day {context.day} - Sheriff Campaign ===

YOUR INFORMATION:
  Your seat: {for_seat}
  Your role: {role_name}
  You nominated to run for Sheriff!

SHERIFF CANDIDATES (seats): {other_candidates_str if other_candidates else 'None - you are alone!'}

SPEAKING ORDER:
  Position: {position} of {total}{sheriff_note}

CAMPAIGN RESPONSE:
  You may either:
  - Give a campaign speech (type your speech)
  - Withdraw from the race (type: "opt out")

  Your speech should convince others to vote for you as Sheriff.

  Your response:"""

        return system, user

    async def _get_valid_speech(
        self,
        context: "PhaseContext",
        participant: Participant,
        for_seat: int,
        candidates: list[int],
    ) -> Optional[Speech]:
        """Get valid campaign speech from participant with retry.

        Campaign Response Protocol:
        - "opt out" (case-insensitive): Candidate opts out after nomination
        - Any non-empty text: Valid campaign speech, returns Speech event

        Args:
            context: Game state
            participant: The participant to query
            for_seat: The candidate's seat
            candidates: List of all candidates (ordered)

        Returns:
            Speech event, or None if participant says "opt out"

        Raises:
            MaxRetriesExceededError: If max retries are exceeded without valid input
        """
        for attempt in range(self.max_retries):
            system, user = self._build_prompts(context, for_seat, candidates)

            # Add hint for retry attempts
            hint = None
            if attempt > 0:
                hint = "Your speech was empty. Please provide a campaign speech or 'opt out'."

            raw = await participant.decide(system, user, hint=hint)

            # Validate content
            content = raw.strip().lower()
            if not content:
                if attempt == self.max_retries - 1:
                    raise MaxRetriesExceededError(
                        f"Failed after {self.max_retries} attempts. Speech was empty."
                    )
                hint = "Your speech was empty. Please provide a campaign speech or 'opt out'."
                raw = await participant.decide(system, user, hint=hint)
                content = raw.strip().lower()

            # Check for OPT_OUT response
            if content == CAMPAIGN_OPT_OUT:
                return None

            if raw.strip():
                # Create speech with preview for debug
                preview = raw.strip()[:100] + "..." if len(raw.strip()) > 100 else raw.strip()
                return Speech(
                    actor=for_seat,
                    content=raw.strip(),
                    phase=Phase.DAY,
                    micro_phase=SubPhase.CAMPAIGN,
                    day=context.day,
                    debug_info=f"speech_preview={preview}",
                )

        # Fallback - should not reach here
        default_speech = "I would like to be your Sheriff."
        return Speech(
            actor=for_seat,
            content=default_speech,
            phase=Phase.DAY,
            micro_phase=SubPhase.CAMPAIGN,
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
    """Minimal context for testing Campaign handler.

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
