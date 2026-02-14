"""Campaign handler for the Werewolf AI game.

This handler manages the Campaign subphase on Day 1 where Sheriff candidates
give campaign speeches before the election.
"""

from typing import Sequence, Optional, Any
from pydantic import BaseModel, Field

from werewolf.events.game_events import (
    Speech,
    Phase,
    SubPhase,
    GameEvent,
)
from werewolf.events.event_visibility import get_public_events, format_public_events
from werewolf.models.player import Player, Role
from werewolf.prompt_levels import (
    get_campaign_opt_out_system,
    make_campaign_context,
    build_campaign_opt_out_decision,
    Choice,
)
from werewolf.ui.choices import ChoiceSpec, ChoiceOption, ChoiceType
from werewolf.handlers.base import SubPhaseLog, HandlerResult, Participant, MaxRetriesExceededError


# ============================================================================
# Campaign Response Protocol
# ============================================================================

# Valid responses for campaign phase
CAMPAIGN_SPEECH = "speech"  # Valid campaign speech (non-empty)
CAMPAIGN_OPT_OUT = "opt out"  # Candidate opts out after nomination


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
        events_so_far: list[GameEvent] | None = None,
    ) -> HandlerResult:
        """Execute the Campaign subphase.

        Args:
            context: Game state with players, living/dead, sheriff, day
            participants: Sequence of (seat, Participant) tuples for all players
            sheriff_candidates: List of candidate seats running for Sheriff
            events_so_far: Previous events in the current day (for context)

        Returns:
            HandlerResult with SubPhaseLog containing Speech events
        """
        events = []
        events_so_far = events_so_far or []

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
                speech = await self._get_valid_decision(
                    context=context,
                    participant=participant,
                    for_seat=seat,
                    candidates=ordered_candidates,
                    events_so_far=events_so_far,
                )
                # Skip None responses (opt-out)
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
        events_so_far: list[GameEvent] | None = None,
    ) -> tuple[str, str, str]:
        """Build filtered prompts for campaign speech.

        Args:
            context: Game state
            for_seat: The candidate seat to build prompts for
            candidates: List of all candidate seats (ordered)
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

{public_events_text}

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

        # For this prompt, LLM and human formats are the same
        return system, user, user

    def _build_speech_prompt(
        self,
        is_opt_out: bool,
        context: "PhaseContext",
        for_seat: int,
        candidates: list[int],
        events_so_far: list[GameEvent] | None = None,
    ) -> tuple[str, str, str]:
        """Build prompts for speech or explanation (Stage 2 of 2).

        Args:
            is_opt_out: True if player is withdrawing (explanation), False if staying (speech)
            context: Game state
            for_seat: The candidate seat
            candidates: List of all candidate seats
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

        player = context.get_player(for_seat)
        role_name = player.role.value if player else "Unknown"

        other_candidates = [c for c in candidates if c != for_seat]
        other_candidates_str = ', '.join(map(str, sorted(other_candidates)))

        if is_opt_out:
            # Explanation for withdrawing
            system = f"""You have chosen to withdraw from the Sheriff race on Day {context.day}.

You must now explain your withdrawal to the village. This explanation will be visible to all players.
Be honest or strategic about why you're stepping down.

Your response should be your explanation as a single string."""

            user = f"""=== Day {context.day} - Sheriff Campaign Withdrawal ===

{public_events_text}

YOUR INFORMATION:
  Your seat: {for_seat}
  Your role: {role_name}
  You have chosen to WITHDRAW from the Sheriff race!

SHERIFF CANDIDATES (seats): {other_candidates_str if other_candidates else 'None - you are alone!'}

WITHDRAWAL EXPLANATION:
  Please explain why you are withdrawing from the race.
  Your explanation will be visible to all players.

  Your response:"""

            # For free-form text, LLM and human prompts are the same
            llm_user = user
            human_user = user
        else:
            # Campaign speech
            system = f"""You have chosen to stay in the Sheriff race on Day {context.day}.

This is your chance to convince the village to vote for you as Sheriff!
Make a compelling campaign speech.

SHERIFF POWERS:
- 1.5x vote weight during voting phases
- Can transfer badge if eliminated
- Speaks LAST during discussions

Your response should be your campaign speech as a single string.
Make it compelling and appropriate for a social deduction game."""

            user = f"""=== Day {context.day} - Sheriff Campaign Speech ===

{public_events_text}

YOUR INFORMATION:
  Your seat: {for_seat}
  Your role: {role_name}
  You have chosen to STAY in the Sheriff race!

SHERIFF CANDIDATES (seats): {other_candidates_str if other_candidates else 'None - you are alone!'}

CAMPAIGN SPEECH:
  This is your chance to convince others to vote for you!
  Your speech will be visible to all players.

  Your response:"""

            # For free-form text, LLM and human prompts are the same
            llm_user = user
            human_user = user

        return system, llm_user, human_user

    async def _get_valid_decision(
        self,
        context: "PhaseContext",
        participant: Participant,
        for_seat: int,
        candidates: list[int],
        events_so_far: list[GameEvent] | None = None,
    ) -> Optional[Speech]:
        """Get valid campaign decision from participant with two-stage queries.

        Stage 1: Query with ChoiceSpec for "stay" / "opt-out"
        Stage 2: If "stay": free-form speech; if "opt-out": explanation

        Campaign Response Protocol:
        - "stay" (case-insensitive): Player stays in race, then speech required
        - "opt-out" (case-insensitive): Player withdraws, then explanation required

        Args:
            context: Game state
            participant: The participant to query
            for_seat: The candidate's seat
            candidates: List of all candidates (ordered)
            events_so_far: All game events for public visibility filtering

        Returns:
            Speech event, or None if participant opts out

        Raises:
            MaxRetriesExceededError: If max retries are exceeded without valid input
        """
        events_so_far = events_so_far or []

        # Build prompts using three-level prompt system
        public_events = get_public_events(events_so_far, context.day, for_seat)
        public_events_text = format_public_events(
            public_events, context.living_players, context.dead_players, for_seat,
        )
        campaign_context = make_campaign_context(context, for_seat, candidates)
        decision = build_campaign_opt_out_decision(campaign_context, public_events_text)

        # Convert DecisionPrompt choices to ChoiceSpec
        choice_options = [
            ChoiceOption(value=c.value, display=c.display, description=c.description)
            for c in (decision.choices or [])
        ]
        choice_spec = ChoiceSpec(
            choice_type=ChoiceType.SINGLE,
            prompt=decision.question,
            options=choice_options,
            allow_none=False,
        )

        for attempt in range(self.max_retries):
            # Query for stay/opt-out selection using proper prompts
            # Build both LLM and human format user prompts
            llm_user = decision.to_llm_prompt()
            human_user = decision.to_tui_prompt()
            user = human_user if getattr(participant, 'is_human', False) else llm_user

            selection = await participant.decide(
                system_prompt=get_campaign_opt_out_system(),
                user_prompt=user,
                hint=decision.hint or 'Please enter either "stay" or "opt-out".',
                choices=choice_spec,
            )

            # Parse selection (be flexible with "opt-out" vs "opt out")
            selection_lower = selection.strip().lower().replace(" ", "-")

            if selection_lower == "stay":
                # Stage 2: Get campaign speech (free-form)
                system, llm_user, human_user = self._build_speech_prompt(
                    is_opt_out=False,
                    context=context,
                    for_seat=for_seat,
                    candidates=candidates,
                    events_so_far=events_so_far,
                )

                for speech_attempt in range(self.max_retries):
                    user = human_user if getattr(participant, 'is_human', False) else llm_user
                    speech = await participant.decide(
                        system_prompt=system,
                        user_prompt=user,
                        hint=None,
                        choices=None,  # Free-form text
                    )

                    if speech.strip():
                        preview = speech.strip()[:100] + "..." if len(speech.strip()) > 100 else speech.strip()
                        return Speech(
                            actor=for_seat,
                            content=speech.strip(),
                            phase=Phase.DAY,
                            micro_phase=SubPhase.CAMPAIGN,
                            day=context.day,
                            debug_info=f"speech_preview={preview}",
                        )

                    if speech_attempt == self.max_retries - 1:
                        raise MaxRetriesExceededError(
                            f"Failed after {self.max_retries} attempts. Speech was empty."
                        )

            elif selection_lower == "opt-out":
                # Stage 2: Get explanation for withdrawing (free-form)
                system, llm_user, human_user = self._build_speech_prompt(
                    is_opt_out=True,
                    context=context,
                    for_seat=for_seat,
                    candidates=candidates,
                    events_so_far=events_so_far,
                )

                # Still need to get explanation, but don't create Speech event
                user = human_user if getattr(participant, 'is_human', False) else llm_user
                await participant.decide(
                    system_prompt=system,
                    user_prompt=user,
                    hint=None,
                    choices=None,  # Free-form text
                )

                # Opt-out means no speech event
                return None

            # Invalid selection
            if attempt == self.max_retries - 1:
                raise MaxRetriesExceededError(
                    f"Player {for_seat} failed to provide valid stay/opt-out decision "
                    f"after {self.max_retries} attempts. Last response: {selection!r}"
                )

        # Fallback - should not reach here
        return None


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
