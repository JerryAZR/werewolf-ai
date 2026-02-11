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

        # Get last words from morning deaths for context
        last_words = self._extract_last_words(events_so_far)

        # Query each speaker for their speech
        for seat in ordered_speakers:
            participant = participant_dict.get(seat)
            if participant:
                speech = await self._get_valid_speech(
                    context=context,
                    participant=participant,
                    for_seat=seat,
                    speaking_order=ordered_speakers,
                    previous_speeches=self._extract_previous_discussion_speeches(events_so_far),
                    last_words=last_words,
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

    def _build_prompts(
        self,
        context: "PhaseContext",
        for_seat: int,
        speaking_order: list[int],
        previous_speeches: list[Speech],
        last_words: dict[int, str],
    ) -> tuple[str, str]:
        """Build filtered prompts for discussion speech.

        Args:
            context: Game state
            for_seat: The speaker's seat
            speaking_order: List of all speakers in order
            previous_speeches: List of previous speeches this phase
            last_words: Dictionary of last words from deaths

        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        # Get player's own role (for their own context)
        player = context.get_player(for_seat)
        role_name = player.role.value if player else "Unknown"

        # Living players (seats only, no roles)
        living_players_str = ', '.join(map(str, sorted(context.living_players)))

        # Position in speaking order
        position = speaking_order.index(for_seat) + 1
        total = len(speaking_order)

        # Sheriff info
        sheriff_info = ""
        if context.sheriff is not None:
            sheriff_status = "You ARE the Sheriff" if context.sheriff == for_seat else f"Seat {context.sheriff} is the Sheriff"
            sheriff_info = f"\n- {sheriff_status} (speaks LAST)"

        # Previous speeches
        prev_speeches_text = ""
        if previous_speeches:
            prev_speeches_text = "\n\nPREVIOUS SPEECHES:\n"
            for i, speech in enumerate(previous_speeches):
                prev_speeches_text += f"  Seat {speech.actor}: {speech.content[:200]}{'...' if len(speech.content) > 200 else ''}\n"

        # Last words from morning deaths
        last_words_text = ""
        if last_words:
            last_words_text = "\n\nLAST WORDS FROM THIS MORNING:\n"
            for seat, words in sorted(last_words.items()):
                last_words_text += f"  Seat {seat}: {words[:200]}{'...' if len(words) > 200 else ''}\n"

        # Build system prompt
        system = f"""You are speaking during Day {context.day} discussion phase.

DISCUSSION RULES:
- All living players will speak once before voting begins
- You speak in position {position} of {total}
- The Sheriff speaks LAST and has 1.5x vote weight
- You may reveal your role or keep it hidden - choose what benefits your strategy
- You can share information strategically (like Seer findings) but be careful
- Your goal is to influence the vote and avoid being eliminated

What makes a good discussion speech:
- Analyze the current game state
- Share suspicions about other players
- Defend yourself if you're under suspicion
- Try to build trust or cast doubt on others
- Consider your role strategy

Your response should be your discussion speech as a single string.
Be persuasive and strategic!"""

        # Build user prompt
        user = f"""=== Day {context.day} - Your Discussion Speech ===

YOUR INFORMATION:
  Your seat: {for_seat}
  Your role: {role_name} (keep this secret!)
  Speaking position: {position} of {total}{sheriff_info}

LIVING PLAYERS (seats): {living_players_str}

DEAD PLAYERS: {', '.join(map(str, sorted(context.dead_players))) if context.dead_players else 'None'}

{prev_speeches_text}{last_words_text}
Enter your discussion speech below:
(Must be non-empty - make it strategic!)"""

        return system, user

    async def _get_valid_speech(
        self,
        context: "PhaseContext",
        participant: Participant,
        for_seat: int,
        speaking_order: list[int],
        previous_speeches: list[Speech],
        last_words: dict[int, str],
    ) -> Speech:
        """Get valid discussion speech from participant with retry.

        Args:
            context: Game state
            participant: The participant to query
            for_seat: The speaker's seat
            speaking_order: List of all speakers in order
            previous_speeches: List of previous speeches this phase
            last_words: Dictionary of last words from deaths

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
                previous_speeches=previous_speeches,
                last_words=last_words,
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
