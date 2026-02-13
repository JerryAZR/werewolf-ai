"""Voting handler for the Werewolf AI game.

This handler manages the voting subphase where all living players cast votes
to banish a suspected werewolf. Key rules:
- Sheriff's vote counts as 1.5
- Abstention allowed (vote for None)
- Tie = no banishment
- Target must be living player (if not abstaining)
"""

import json
from collections import defaultdict
from typing import Sequence, Optional, Any
from pydantic import BaseModel, Field

from werewolf.events.game_events import (
    Vote,
    Banishment,
    Phase,
    SubPhase,
    GameEvent,
)
from werewolf.events.event_visibility import get_public_events, format_public_events
from werewolf.ui.choices import ChoiceSpec, ChoiceOption, ChoiceType, make_seat_choice
from werewolf.prompt_levels import (
    get_voting_system,
    make_voting_context,
    build_voting_decision,
)
from werewolf.handlers.base import SubPhaseLog, HandlerResult, Participant, MaxRetriesExceededError


SHERIFF_VOTE_WEIGHT: float = 1.5
DEFAULT_VOTE_WEIGHT: float = 1.0


class VotingHandler:
    """Handler for Voting subphase.

    Responsibilities:
    1. Collect votes from all living players (abstention allowed)
    2. Calculate weighted vote totals (Sheriff = 1.5)
    3. Determine banished player (majority wins, tie = no banishment)
    4. Return Vote events + Banishment event

    Context Filtering (what voters see):
    - All living player seats
    - Sheriff identity (vote weight = 1.5)
    - Discussion transcripts
    - Death announcements from DeathResolution

    What voters do NOT see:
    - Other players' votes (secret ballot)
    - Role information of any player
    - Night action details
    """

    # Maximum retry attempts for invalid input
    max_retries: int = 3

    async def __call__(
        self,
        context: "PhaseContext",
        participants: Sequence[tuple[int, Participant]],
        events_so_far: list[GameEvent] | None = None,
    ) -> HandlerResult:
        """Execute the Voting subphase.

        Args:
            context: Game state with day, living_players, sheriff
            participants: Sequence of (seat, Participant) tuples for all players
            events_so_far: Previous events (discussion transcripts, death announcements)

        Returns:
            HandlerResult with SubPhaseLog containing Vote events and Banishment
        """
        events = []
        events_so_far = events_so_far or []

        # Build participant lookup
        participant_dict = dict(participants)

        # Collect votes from all living players
        vote_tally: dict[int, float] = defaultdict(float)
        vote_events: list[Vote] = []

        for seat in sorted(context.living_players):
            participant = participant_dict.get(seat)
            if participant:
                target = await self._get_valid_vote(
                    context=context,
                    participant=participant,
                    voter_seat=seat,
                    living_players=context.living_players,
                    events_so_far=events_so_far,
                )

                # Calculate vote weight (Sheriff = 1.5, others = 1.0)
                weight = SHERIFF_VOTE_WEIGHT if seat == context.sheriff else DEFAULT_VOTE_WEIGHT

                # Create Vote event
                vote_event = Vote(
                    actor=seat,
                    target=target,
                    phase=Phase.DAY,
                    micro_phase=SubPhase.VOTING,
                    day=context.day,
                )
                vote_events.append(vote_event)
                events.append(vote_event)

                # Add to weighted tally (None target = abstention, not counted)
                if target is not None:
                    vote_tally[target] += weight

        # Determine banished player
        banished = self._determine_banished(vote_tally)

        # Get tied players for Banishment event
        tied_players = self._get_tied_players(vote_tally, banished)

        # Create Banishment event
        banishment = Banishment(
            votes=dict(vote_tally),
            tied_players=tied_players,
            banished=banished,
            phase=Phase.DAY,
            micro_phase=SubPhase.VOTING,
            day=context.day,
        )
        events.append(banishment)

        # Build debug info
        debug_info = self._build_debug_info(
            day=context.day,
            living_count=len(context.living_players),
            vote_events=vote_events,
            vote_tally=vote_tally,
            banished=banished,
            tied_players=tied_players,
            sheriff=context.sheriff,
        )

        return HandlerResult(
            subphase_log=SubPhaseLog(
                micro_phase=SubPhase.VOTING,
                events=events,
            ),
            debug_info=debug_info,
        )

    def _determine_banished(self, vote_tally: dict[int, float]) -> Optional[int]:
        """Determine the player to be banished from vote counts.

        Args:
            vote_tally: Dictionary of target -> weighted vote count

        Returns:
            Banished player seat, or None if tie/no votes
        """
        if not vote_tally:
            # All players abstained
            return None

        # Find maximum vote count
        max_votes = max(vote_tally.values())

        # Check for tie
        tied = [target for target, count in vote_tally.items() if count == max_votes]

        # Tie = no banishment
        if len(tied) > 1:
            return None

        return tied[0]

    def _get_tied_players(
        self,
        vote_tally: dict[int, float],
        banished: Optional[int],
    ) -> list[int]:
        """Get list of tied players (for Banishment event).

        Args:
            vote_tally: Dictionary of target -> weighted vote count
            banished: The banished player or None

        Returns:
            List of tied player seats (empty if no tie)
        """
        if not vote_tally:
            return []

        max_votes = max(vote_tally.values())
        tied = [target for target, count in vote_tally.items() if count == max_votes]

        return tied if len(tied) > 1 else []

    def _build_prompts(
        self,
        context: "PhaseContext",
        voter_seat: int,
        living_players: set[int],
        events_so_far: list[GameEvent] | None = None,
    ) -> tuple[str, str]:
        """Build filtered prompts for voter.

        Args:
            context: Game state
            voter_seat: The voter seat number
            living_players: Set of living player seats
            events_so_far: All game events for public visibility filtering

        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        # Get public events using the visibility filter
        public_events = get_public_events(
            events_so_far or [],
            context.day,
            voter_seat,
        )

        # Format public events for the prompt
        public_events_text = format_public_events(
            public_events,
            context.living_players,
            context.dead_players,
            voter_seat,
        )

        # Level 1: Static system prompt (role rules only)
        system = get_voting_system()

        # Level 2: Game state context
        state_context = make_voting_context(context=context, your_seat=voter_seat)

        # Level 3: Decision prompt with public events
        decision = build_voting_decision(
            state_context,
            public_events_text=public_events_text,
        )

        # Build user prompt (combine Level 2 context + Level 3 decision)
        user = decision.to_llm_prompt()

        return system, user

    def _build_choices(self, living_players: set[int]) -> ChoiceSpec:
        """Build ChoiceSpec for voting.

        Args:
            living_players: Set of valid vote targets

        Returns:
            ChoiceSpec for selecting a target
        """
        return make_seat_choice(
            prompt="Who do you vote to banish?",
            seats=list(living_players),
            allow_none=True,
        )

    async def _get_valid_vote(
        self,
        context: "PhaseContext",
        participant: Participant,
        voter_seat: int,
        living_players: set[int],
        events_so_far: list[GameEvent] | None = None,
    ) -> Optional[int]:
        """Get valid vote from participant with retry.

        Args:
            context: Game state
            participant: The participant to query
            voter_seat: The voter's seat number
            living_players: Set of valid vote targets
            events_so_far: All game events for public visibility filtering

        Returns:
            The seat number voted for, or None (abstention)
        """
        for attempt in range(self.max_retries):
            system, user = self._build_prompts(
                context,
                voter_seat,
                living_players,
                events_so_far,
            )

            # Build choices for TUI rendering
            choices = self._build_choices(living_players)

            # Add hint for retry attempts
            hint = None
            if attempt > 0:
                hint = 'Previous response was invalid. Please enter a valid seat number or "None".'

            raw = await participant.decide(system, user, hint=hint, choices=choices)

            # Parse the vote
            target = self._parse_vote(raw, living_players)

            # Abstention (target is None) is valid - return it
            if target is not None:
                return target

            # Handle abstention - it's valid, return None
            # Check if the response indicates abstention
            cleaned = raw.strip().lower()
            if cleaned in ('none', 'abstain', 'skip', 'pass', ''):
                return None

            # Invalid response, provide hint
            if attempt == self.max_retries - 1:
                # Default to abstention after max retries
                return None

            # Retry with hint
            hint = f'Please enter a valid seat number from {sorted(living_players)} or "None" to abstain.'
            raw = await participant.decide(system, user, hint=hint, choices=choices)
            target = self._parse_vote(raw, living_players)

            if target is not None:
                return target

            # Check if this is abstention
            cleaned = raw.strip().lower()
            if cleaned in ('none', 'abstain', 'skip', 'pass', ''):
                return None

        # Default to abstention on failure
        return None

    def _parse_vote(
        self,
        raw_response: str,
        living_players: set[int],
    ) -> Optional[int]:
        """Parse the raw response into a vote target.

        Args:
            raw_response: Raw string from participant
            living_players: Set of valid vote targets

        Returns:
            Voted seat number, or None (abstention or invalid)
        """
        try:
            cleaned = raw_response.strip().lower()

            # Handle abstention
            if cleaned in ('none', 'abstain', 'skip', 'pass', ''):
                return None

            # Try to parse as integer
            seat = int(cleaned)

            # Validate it's a living player
            if seat in living_players:
                return seat
            else:
                return None
        except (ValueError, AttributeError):
            return None

    def _build_debug_info(
        self,
        day: int,
        living_count: int,
        vote_events: list[Vote],
        vote_tally: dict[int, float],
        banished: Optional[int],
        tied_players: list[int],
        sheriff: Optional[int],
    ) -> str:
        """Build debug info string for voting.

        Args:
            day: Current day
            living_count: Number of living voters
            vote_events: List of Vote events
            vote_tally: Weighted vote tallies
            banished: Banished player or None
            tied_players: List of tied players
            sheriff: Current Sheriff or None

        Returns:
            Debug info JSON string
        """
        debug_data = {
            "day": day,
            "living_voters": living_count,
            "sheriff": sheriff,
            "sheriff_weight": SHERIFF_VOTE_WEIGHT,
            "vote_events": [
                {"actor": e.actor, "target": e.target}
                for e in vote_events
            ],
            "vote_totals": vote_tally,
            "banished": banished,
            "tied_players": tied_players,
            "abstention_count": sum(1 for e in vote_events if e.target is None),
        }
        return json.dumps(debug_data)


# ============================================================================
# PhaseContext (for use with the handler)
# ============================================================================


# Import PhaseContext from werewolf_handler for type hints
# Using TYPE_CHECKING to avoid circular imports
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from werewolf.handlers.werewolf_handler import PhaseContext
