"""SheriffElection handler for the Werewolf AI game.

This handler manages the Sheriff election voting subphase where all living
players cast votes for Sheriff candidates.
"""

from typing import Protocol, Sequence, Optional, Any
from collections import defaultdict
from pydantic import BaseModel, Field

from werewolf.events.game_events import (
    SheriffOutcome,
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
# SheriffElection Handler
# ============================================================================


SHERIFF_VOTE_WEIGHT: float = 1.5
DEFAULT_VOTE_WEIGHT: float = 1.0


class SheriffElectionHandler:
    """Handler for SheriffElection subphase (Day 1 only).

    Responsibilities:
    1. Validate that day == 1
    2. Collect votes from non-candidates only (candidates cannot vote, no abstention)
    3. Calculate weighted vote totals (Sheriff = 1.5, others = 1.0)
    4. Determine winner (majority wins, tie = no Sheriff)
    5. Return SheriffOutcome event

    Context Filtering (what voters see):
    - Remaining candidates after OptOut (seats only)
    - All living players (seats only)
    - Sheriff vote weight = 1.5
    - No abstention rule (non-candidates must vote)

    What voters do NOT see:
    - Other players' votes (secret ballot)
    - Role information of candidates or other players
    - Vote intentions
    """

    # Maximum retry attempts for invalid input
    max_retries: int = 3

    async def __call__(
        self,
        context: "PhaseContext",
        participants: Sequence[tuple[int, Participant]],
        sheriff_candidates: list[int],
    ) -> HandlerResult:
        """Execute the SheriffElection subphase.

        Args:
            context: Game state with day, sheriff_candidates, living_players
            participants: Sequence of (seat, Participant) tuples for all players
            sheriff_candidates: Remaining candidates after OptOut

        Returns:
            HandlerResult with SheriffOutcome event
        """
        events = []

        # Validate day == 1
        if context.day != 1:
            return HandlerResult(
                subphase_log=SubPhaseLog(micro_phase=SubPhase.SHERIFF_ELECTION),
                debug_info="Sheriff election only occurs on Day 1",
            )

        # Edge case: no candidates
        if not sheriff_candidates:
            outcome = SheriffOutcome(
                day=context.day,
                phase=Phase.DAY,
                micro_phase=SubPhase.SHERIFF_ELECTION,
                candidates=[],
                votes={},
                winner=None,
            )
            events.append(outcome)

            import json
            debug_info = json.dumps({
                "day": context.day,
                "candidates": [],
                "reason": "No candidates after OptOut",
            })

            return HandlerResult(
                subphase_log=SubPhaseLog(
                    micro_phase=SubPhase.SHERIFF_ELECTION,
                    events=events,
                ),
                debug_info=debug_info,
            )

        # Build participant lookup
        participant_dict = dict(participants)

        # Collect votes from NON-CANDIDATES only (candidates cannot vote)
        votes: dict[int, float] = defaultdict(float)

        for seat, participant in participants:
            # Skip candidates - they cannot vote
            if seat in sheriff_candidates:
                continue

            participant = participant_dict.get(seat)
            if participant:
                target = await self._get_valid_vote(
                    context=context,
                    participant=participant,
                    voter_seat=seat,
                    candidates=sheriff_candidates,
                )

                # Calculate vote weight (default 1.0, Sheriff 1.5)
                weight = SHERIFF_VOTE_WEIGHT if seat == context.sheriff else DEFAULT_VOTE_WEIGHT

                if target is not None:
                    votes[target] += weight

        # Calculate total votes for debug info
        total_votes = sum(votes.values())

        # Determine winner (majority wins, tie = no Sheriff)
        winner = self._determine_winner(votes)

        # Create SheriffOutcome
        outcome = SheriffOutcome(
            day=context.day,
            phase=Phase.DAY,
            micro_phase=SubPhase.SHERIFF_ELECTION,
            candidates=sheriff_candidates,
            votes=dict(votes),
            winner=winner,
        )
        events.append(outcome)

        # Build debug info
        import json
        debug_info = json.dumps({
            "day": context.day,
            "candidates": sheriff_candidates,
            "vote_totals": dict(votes),
            "total_votes": total_votes,
            "winner": winner,
        })

        return HandlerResult(
            subphase_log=SubPhaseLog(
                micro_phase=SubPhase.SHERIFF_ELECTION,
                events=events,
            ),
            debug_info=debug_info,
        )

    def _determine_winner(self, votes: dict[int, float]) -> Optional[int]:
        """Determine the winner from vote counts.

        Args:
            votes: Dictionary of candidate -> vote count

        Returns:
            Winner seat number, or None if tie/no votes
        """
        if not votes:
            return None

        # Find maximum vote count
        max_votes = max(votes.values())

        # Check for tie
        winners = [candidate for candidate, count in votes.items() if count == max_votes]

        # Tie = no winner
        if len(winners) > 1:
            return None

        return winners[0]

    def _build_prompts(
        self,
        context: "PhaseContext",
        voter_seat: int,
        candidates: list[int],
    ) -> tuple[str, str]:
        """Build filtered prompts for voter.

        Args:
            context: Game state
            voter_seat: The voter seat number
            candidates: List of remaining candidate seats

        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        # Filter visible information - only seats
        other_living = [
            seat for seat in context.living_players
            if seat != voter_seat
        ]

        # Check if voter is Sheriff (incumbent)
        is_sheriff = voter_seat == context.sheriff
        weight_note = "Your Sheriff vote counts as 1.5!" if is_sheriff else ""

        # Build candidate list string
        candidates_str = ', '.join(map(str, candidates))

        # Build system prompt
        system = f"""You are voting for Sheriff on Day {context.day}.

SHERIFF POWERS:
- The Sheriff has 1.5x vote weight during voting phases
- If eliminated, the Sheriff can transfer the badge to another player
- The Sheriff speaks LAST during all discussion phases

VOTING RULES:
- You may vote for one of the candidates or abstain
- Your vote is secret - no one will see who you voted for
- The candidate with the most votes wins (1.5x weight if you are Sheriff)
- Tie = no Sheriff elected

CANDIDATES (seat numbers only): {candidates_str}

Your response must be exactly the seat number of your chosen candidate, or "None" to abstain.{weight_note}"""

        # Build user prompt
        user = f"""=== Day {context.day} - Sheriff Vote ===

YOUR SEAT: {voter_seat}

CANDIDATES RUNNING FOR SHERIFF:
  Seats: {candidates_str}

RULES:
  - You may vote for a candidate or abstain
  - Your vote is secret
  - If you are the Sheriff, your vote counts as 1.5

VOTE INSTRUCTIONS:
  Enter the seat number of your chosen candidate, or "None" to abstain:
  """

        return system, user

    async def _get_valid_vote(
        self,
        context: "PhaseContext",
        participant: Participant,
        voter_seat: int,
        candidates: list[int],
    ) -> Optional[int]:
        """Get valid vote from participant with retry.

        Args:
            context: Game state
            participant: The participant to query
            voter_seat: The voter's seat number
            candidates: List of valid candidate seats

        Returns:
            The seat number voted for, or None if invalid
        """
        for attempt in range(self.max_retries):
            system, user = self._build_prompts(context, voter_seat, candidates)

            # Add hint for retry attempts
            hint = None
            if attempt > 0:
                hint = 'Previous response was invalid. Please enter a valid candidate seat number.'

            raw = await participant.decide(system, user, hint=hint)

            # Parse the vote
            target = self._parse_vote(raw, candidates)

            if target is not None:
                return target

            # Invalid response, provide hint
            if attempt == self.max_retries - 1:
                raise MaxRetriesExceededError(
                    f"Failed after {self.max_retries} attempts. "
                    f"Please vote for one of: {candidates}"
                )

            # Retry with hint
            hint = f'Please enter a valid seat number from: {candidates}'
            raw = await participant.decide(system, user, hint=hint)
            target = self._parse_vote(raw, candidates)

            if target is not None:
                return target

        # Default: skip vote on failure (shouldn't happen with retry logic)
        return None

    def _parse_vote(self, raw_response: str, valid_candidates: list[int]) -> Optional[int]:
        """Parse the raw response into a vote target.

        Args:
            raw_response: Raw string from participant
            valid_candidates: List of valid candidate seats

        Returns:
            Voted seat number, or None if abstaining/invalid
        """
        try:
            cleaned = raw_response.strip().lower()

            # Allow abstention
            if cleaned in ('none', 'abstain', 'skip', 'pass', ''):
                return None

            # Try to parse as integer
            seat = int(cleaned)

            # Validate it's a valid candidate
            if seat in valid_candidates:
                return seat
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
    """Minimal context for testing SheriffElection handler.

    This is a simpler class-based context that mirrors what the game engine
    would provide. Handlers can use is_alive() and other helper methods.
    """

    def __init__(
        self,
        sheriff_candidates: list[int],
        living_players: set[int],
        dead_players: set[int],
        sheriff: Optional[int] = None,
        day: int = 1,
    ):
        self.sheriff_candidates = sheriff_candidates
        self.living_players = living_players
        self.dead_players = dead_players
        self.sheriff = sheriff
        self.day = day

    def is_alive(self, seat: int) -> bool:
        """Check if a player is alive."""
        return seat in self.living_players
