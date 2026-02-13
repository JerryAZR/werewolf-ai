"""WerewolfAction handler for the Werewolf AI game.

This handler manages the werewolf subphase where living werewolves collectively
choose a target to kill.
"""

from collections import Counter
from typing import Sequence, Optional, Any

from pydantic import BaseModel, Field

from werewolf.events.game_events import (
    WerewolfKill,
    Phase,
    SubPhase,
    GameEvent,
)
from werewolf.events.event_visibility import get_public_events, format_public_events
from werewolf.models.player import Player, Role
from werewolf.prompt_levels import (
    get_werewolf_system,
    make_werewolf_context,
    build_werewolf_decision,
    DecisionPrompt,
)
from werewolf.handlers.base import SubPhaseLog, HandlerResult, Participant, MaxRetriesExceededError


def _get_choice_spec_helpers():
    """Lazy import to avoid dependency when choices not used."""
    from werewolf.ui.choices import make_seat_choice
    return make_seat_choice


# Forward reference to avoid circular import
ChoiceSpec = Any  # Will be resolved at runtime


# ============================================================================
# Werewolf Handler
# ============================================================================


class WerewolfHandler:
    """Handler for WerewolfAction subphase.

    Responsibilities:
    1. Build filtered context for werewolves (see teammates, not roles)
    2. Query living werewolves for kill target
    3. Aggregate multiple werewolf votes into single kill decision
    4. Validate actions against game rules
    5. Retry with hints on invalid input (up to 3 times)
    6. Return WerewolfKill event with representative actor

    Context Filtering (what werewolves see):
    - Current night number
    - Living player seats (any player can be targeted)
    - Fellow werewolf seats (teammates)
    - Dead player seats (roles unknown)
    - Sheriff identity

    What werewolves do NOT see:
    - Role identities (Seer, Witch, Guard, Hunter, Villager)
    - Last night's deaths
    - Witch/Guard action results
    """

    # Maximum retry attempts for invalid input
    max_retries: int = 3

    async def __call__(
        self,
        context: "PhaseContext",
        participants: Sequence[tuple[int, Participant]],
        events_so_far: list[GameEvent] | None = None,
    ) -> HandlerResult:
        """Execute the WerewolfAction subphase.

        Args:
            context: Game state with players, living/dead, sheriff
            participants: Sequence of (seat, Participant) tuples for werewolves
                          Can also be a dict[int, Participant] for test compatibility
            events_so_far: Previous events in the current night (for context)

        Returns:
            HandlerResult with SubPhaseLog containing WerewolfKill event
        """
        events = []
        events_so_far = events_so_far or []

        # Get living werewolf seats
        werewolf_seats = [
            seat for seat in context.living_players
            if context.is_werewolf(seat)
        ]

        # Edge case: no werewolves alive
        if not werewolf_seats:
            return HandlerResult(
                subphase_log=SubPhaseLog(micro_phase=SubPhase.WEREWOLF_ACTION),
                debug_info="No werewolves alive, skipping WerewolfAction",
            )

        # Convert participants to dict for easier lookup
        # Handle both Sequence[tuple[int, Participant]] and dict[int, Participant]
        if isinstance(participants, dict):
            participant_dict = participants
        else:
            participant_dict = dict(participants)

        # Select ONE representative werewolf to make the collective decision
        # Priority: human players first, then lowest seat number
        from werewolf.models.player import PlayerType
        human_werewolves = [
            seat for seat in werewolf_seats
            if context.players[seat].player_type == PlayerType.HUMAN
        ]
        if human_werewolves:
            representative = min(human_werewolves)  # lowest human seat
        else:
            representative = min(werewolf_seats)  # fallback to lowest seat

        # Query only the representative werewolf
        participant = participant_dict.get(representative)
        if participant:
            target = await self._get_valid_target(context, participant, representative, events_so_far)

            # Create debug info with collective decision info
            import json
            debug_info = json.dumps({
                "werewolf_seats": werewolf_seats,
                "representative": representative,
                "target": target,
            })

            events.append(WerewolfKill(
                actor=representative,
                target=target,
                phase=Phase.NIGHT,
                micro_phase=SubPhase.WEREWOLF_ACTION,
                day=context.day,
                debug_info=debug_info,
            ))

        return HandlerResult(
            subphase_log=SubPhaseLog(
                micro_phase=SubPhase.WEREWOLF_ACTION,
                events=events,
            ),
        )

    def _build_prompts(
        self,
        context: "PhaseContext",
        for_seat: int,
        events_so_far: list[GameEvent] | None = None,
    ) -> tuple[str, str]:
        """Build filtered prompts for werewolf.

        Args:
            context: Game state
            for_seat: The werewolf seat to build prompts for
            events_so_far: Previous events in the current night

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

        # Get static system prompt (Level 1)
        system = get_werewolf_system()

        # Build game state context (Level 2)
        state_context = make_werewolf_context(
            context=context,
            your_seat=for_seat,
        )

        # Build decision prompt (Level 3)
        decision = build_werewolf_decision(
            state_context,
            public_events_text=public_events_text,
        )

        # Use LLM format for user prompt (includes choices)
        user = decision.to_llm_prompt()

        return system, user

    def build_choice_spec(
        self,
        context: "PhaseContext",
        for_seat: int,
    ) -> Optional[Any]:
        """Build ChoiceSpec for interactive TUI.

        IMPORTANT: Werewolves can target ANY living player, including:
        - Themselves (suicide)
        - Their own werewolf teammates (betrayal/chaos strategy)

        This is intentionally different from the LLM prompt which filters teammates
        for game balance. The game rules are enforced at validation time, not at
        prompt generation time. This gives werewolves full strategic freedom.

        Returns ChoiceSpec with ALL living players + skip option.
        """
        make_seat_choice = _get_choice_spec_helpers()

        # Include ALL living players - werewolves can target anyone including themselves
        # and teammates. Game rules (not prompt filtering) enforce valid choices.
        valid_targets = sorted(context.living_players)

        return make_seat_choice(
            prompt="Choose a target to kill:",
            seats=valid_targets,
            allow_none=True,  # Werewolf can skip
        )

    async def _get_valid_target(
        self,
        context: "PhaseContext",
        participant: Participant,
        for_seat: int = 0,
        events_so_far: list[GameEvent] | None = None,
    ) -> int:
        """Get valid target from participant with retry.

        Args:
            context: Game state
            participant: The participant to query
            for_seat: The werewolf seat making the decision
            events_so_far: Previous events in the current night

        Returns:
            Valid target seat number

        Raises:
            MaxRetriesExceededError: If max retries are exceeded
        """
        # Build ChoiceSpec with valid targets
        choices = self.build_choice_spec(context, for_seat)

        for attempt in range(self.max_retries):
            system, user = self._build_prompts(context, for_seat, events_so_far)

            # Add hint for retry attempts
            hint = None
            if attempt > 0:
                hint = "Previous response was invalid. Please choose a living player or SKIP."

            raw = await participant.decide(system, user, hint=hint, choices=choices)

            try:
                target = self._parse_target(raw)
            except ValueError:
                hint = "Please enter a valid seat number (0-11)."
                raw = await participant.decide(system, user, hint=hint, choices=choices)
                target = self._parse_target(raw)

            # Validate target
            if self._is_valid_target(context, target):
                return target

            # Provide helpful hint based on what went wrong
            if target in context.dead_players:
                hint = "That player is dead. Choose a living player or SKIP."
            else:
                hint = "Invalid choice. Choose a living player or SKIP."

            if attempt == self.max_retries - 1:
                raise MaxRetriesExceededError(
                    f"Failed after {self.max_retries} attempts. Last hint: {hint}"
                )

            # Retry with hint
            raw = await participant.decide(system, user, hint=hint, choices=choices)
            target = self._parse_target(raw)

            if self._is_valid_target(context, target):
                return target

        # Should not reach here, but return a valid default
        return self._get_default_target(context)

    def _parse_target(self, raw_response: str) -> int:
        """Parse the raw response into a target seat number.

        Args:
            raw_response: Raw string from participant

        Returns:
            Seat number (-1 means skip)

        Raises:
            ValueError: If response cannot be parsed
        """
        # Clean up the response
        cleaned = raw_response.strip().lower()

        # Handle skip explicitly
        if cleaned in ['-1', 'skip', 'none', 'no kill', 'pass']:
            return -1

        # Try to extract a number
        import re
        match = re.search(r'\d+', cleaned)

        if not match:
            raise ValueError(f"Could not parse target from response: '{raw_response}'")

        target = int(match.group())

        # Validate seat range (-1 allowed for skip)
        if target == -1:
            return -1
        if target < 0 or target > 11:
            raise ValueError(f"Invalid seat number: {target}. Seats must be 0-11, or -1 to skip.")

        return target

    def _is_valid_target(self, context: "PhaseContext", target: int) -> bool:
        """Check if target is a valid kill target.

        Args:
            context: Game state
            target: Proposed target seat (-1 means skip)

        Returns:
            True if target is valid
        """
        if target == -1:
            return True  # Skip is allowed
        if target < 0 or target > 11:
            return False
        if target in context.dead_players:
            return False
        return True

    def _resolve_consensus(self, votes: dict[int, int], context: "PhaseContext") -> int:
        """Resolve werewolf consensus from individual votes.

        Uses plurality voting - the target with the most votes wins.
        If there's a tie, the lowest seat number wins.

        Args:
            votes: Dictionary mapping werewolf seat -> their chosen target
            context: Game state

        Returns:
            The consensus target seat
        """
        if not votes:
            return self._get_default_target(context)

        # Count votes for each target
        target_counts = Counter(votes.values())

        # Find max votes
        max_count = max(target_counts.values())

        # Get all targets with max votes
        tied_targets = [t for t, c in target_counts.items() if c == max_count]

        # Return lowest seat (tie-breaker)
        return min(tied_targets)

    def _get_default_target(self, context: "PhaseContext") -> int:
        """Get a valid living target as fallback.

        Args:
            context: Game state

        Returns:
            A valid target seat

        Raises:
            ValueError: If no valid targets are available
        """
        for seat in sorted(context.living_players):
            return seat  # Any living player is valid (including teammates)
        raise ValueError("No valid targets available")


# ============================================================================
# PhaseContext (for use with the handler)
# ============================================================================


class PhaseContext:
    """Minimal context for testing WerewolfAction handler.

    This is a simpler class-based context that mirrors what the game engine
    would provide. Handlers can use is_werewolf() and other helper methods.
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
