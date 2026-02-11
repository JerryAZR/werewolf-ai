"""WerewolfAction handler for the Werewolf AI game.

This handler manages the werewolf subphase where living werewolves collectively
choose a target to kill.
"""

from collections import Counter
from typing import Protocol, Sequence, Optional, Any
from pydantic import BaseModel, Field

from werewolf.events.game_events import (
    WerewolfKill,
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
    ) -> HandlerResult:
        """Execute the WerewolfAction subphase.

        Args:
            context: Game state with players, living/dead, sheriff
            participants: Sequence of (seat, Participant) tuples for werewolves
                          Can also be a dict[int, Participant] for test compatibility

        Returns:
            HandlerResult with SubPhaseLog containing WerewolfKill event
        """
        events = []

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

        # Single werewolf - query directly
        if len(werewolf_seats) == 1:
            seat = werewolf_seats[0]
            participant = participant_dict.get(seat)
            if participant:
                target = await self._get_valid_target(context, participant, seat)
                events.append(WerewolfKill(
                    actor=seat,
                    target=target,
                    phase=Phase.NIGHT,
                    micro_phase=SubPhase.WEREWOLF_ACTION,
                    day=context.day,
                ))
        else:
            # Multiple werewolves - collect votes
            votes: dict[int, int] = {}
            for seat in werewolf_seats:
                participant = participant_dict.get(seat)
                if participant:
                    votes[seat] = await self._get_valid_target(context, participant, seat)

            # Consensus: most votes wins, lowest seat breaks ties
            target = self._resolve_consensus(votes, context)
            # Use first werewolf (lowest seat) as representative actor
            actor = min(werewolf_seats)

            # Create debug info
            import json
            debug_info = json.dumps({
                "werewolf_seats": werewolf_seats,
                "target_votes": votes,
                "final_target": target,
            })

            events.append(WerewolfKill(
                actor=actor,
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
    ) -> tuple[str, str]:
        """Build filtered prompts for werewolf.

        Args:
            context: Game state
            for_seat: The werewolf seat to build prompts for

        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        # Filter visible information
        living_players = sorted(context.living_players)
        werewolf_teammates = [
            seat for seat in living_players
            if context.is_werewolf(seat) and seat != for_seat
        ]
        dead_players = sorted(context.dead_players)

        # Build system prompt
        # Note: Night number = day (game starts Night 1 → Day 1)
        night = context.day
        system = f"""You are a werewolf on Night {night}.
Your teammates are: {', '.join(map(str, werewolf_teammates)) if werewolf_teammates else 'none (you are alone)'}

Living players (seat numbers): {', '.join(map(str, living_players))}
Dead players: {', '.join(map(str, dead_players)) if dead_players else 'none'}

IMPORTANT RULES:
1. You MAY choose to skip killing (enter -1 or "none").
2. You CANNOT kill dead players.
3. You decide the final target for your werewolf team.

Your response should be a single integer representing the seat number of your target, or -1 to skip.
Example: "7" means you want to kill the player at seat 7. "-1" means you want to skip."""

        # Build user prompt
        sheriff_info = ""
        if context.sheriff is not None:
            sheriff_info = f"\nSheriff: Player at seat {context.sheriff} holds the sheriff badge (1.5x vote weight)."

        user = f"""=== Night {context.day} - Werewolf Kill Decision ===

YOUR TEAMMATES (fellow werewolves):
  Seats: {werewolf_teammates if werewolf_teammates else 'None - you are alone!'}

LIVING PLAYERS (potential targets):
  Seats: {living_players}

DEAD PLAYERS (cannot be targeted):
  Seats: {dead_players if dead_players else 'None'}{sheriff_info}

Enter the seat number of your target to kill (or -1 to skip):"""

        return system, user

    async def _get_valid_target(
        self,
        context: "PhaseContext",
        participant: Participant,
        for_seat: int = 0,
    ) -> int:
        """Get valid target from participant with retry.

        Args:
            context: Game state
            participant: The participant to query
            for_seat: The werewolf seat making the decision

        Returns:
            Valid target seat number

        Raises:
            MaxRetriesExceededError: If max retries are exceeded
        """
        for attempt in range(self.max_retries):
            system, user = self._build_prompts(context, for_seat)

            # Add hint for retry attempts
            hint = None
            if attempt > 0:
                hint = "Previous response was invalid. Please choose a living player or -1 to skip."

            raw = await participant.decide(system, user, hint=hint)

            try:
                target = self._parse_target(raw)
            except ValueError:
                hint = "Please enter a valid seat number (0-11)."
                raw = await participant.decide(system, user, hint=hint)
                target = self._parse_target(raw)

            # Validate target
            if self._is_valid_target(context, target):
                return target

            # Provide helpful hint based on what went wrong
            if target in context.dead_players:
                hint = "That player is dead. Choose a living player or -1 to skip."
            else:
                hint = "Invalid choice. Choose a living player or -1 to skip."

            if attempt == self.max_retries - 1:
                raise MaxRetriesExceededError(
                    f"Failed after {self.max_retries} attempts. Last hint: {hint}"
                )

            # Retry with hint
            raw = await participant.decide(system, user, hint=hint)
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


class MaxRetriesExceededError(Exception):
    """Raised when max retries are exceeded."""
    pass


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
