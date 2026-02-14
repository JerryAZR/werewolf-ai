"""BanishmentResolution handler for the Werewolf AI game.

This handler processes BANISHMENT deaths from Voting, generating DeathEvent
for the banished player with:
- Last words (always required for banishment)
- Hunter shoot target (if Hunter - can shoot unlike night poison death)
- Badge transfer (if Sheriff)

For night deaths, see DeathResolution handler.
"""

import logging
import random
from typing import Optional, Sequence, Any
from pydantic import BaseModel, Field

from werewolf.events.game_events import (
    DeathEvent,
    DeathCause,
    Phase,
    SubPhase,
    GameEvent,
)
from werewolf.events.event_visibility import get_public_events, format_public_events
from werewolf.models.player import Player, Role
from werewolf.ui.choices import ChoiceSpec, make_seat_choice
from werewolf.prompt_levels import (
    get_banishment_last_words_system,
    get_banishment_hunter_shoot_system,
    get_banishment_badge_transfer_system,
    make_banishment_last_words_context,
    make_banishment_hunter_shoot_context,
    make_banishment_badge_transfer_context,
    build_banishment_last_words_decision,
    build_banishment_hunter_shoot_decision,
    build_banishment_badge_transfer_decision,
)
from werewolf.handlers.base import SubPhaseLog, HandlerResult, Participant


# ============================================================================
# Banishment Resolution Handler
# ============================================================================


class BanishmentResolutionHandler:
    """Handler for BanishmentResolution subphase (banishment deaths only).

    Responsibilities:
    1. Process banishment from Voting phase
    2. Generate DeathEvent for the banished player with:
       - cause: BANISHMENT
       - last_words: always required for banishment (unlike night deaths)
       - hunter_shoot_target: if Hunter (can shoot unlike night POISON death)
       - badge_transfer_to: if Sheriff

    Validation Rules:
    - Hunter can shoot on banishment (unlike POISON death)
    - Badge transfer target must be living
    - Hunter shoot target must be living
    - If banished is None (tie), return empty SubPhaseLog

    Participants are consulted for:
    - Last words (always required for banishment)
    - Hunter shoot target (if Hunter)
    - Badge transfer (if Sheriff)

    Attributes:
        logger: Logger for this handler.
    """

    logger = logging.getLogger(__name__)

    # Maximum retry attempts for invalid input
    max_retries: int = 3

    def __init__(self, rng: Optional[random.Random] = None):
        """Initialize handler with optional RNG for reproducibility.

        Args:
            rng: Random number generator. If None, uses module-level random.
        """
        self._rng = rng

    @property
    def _random(self) -> random.Random:
        """Get the RNG, falling back to module random if not set."""
        return self._rng if self._rng is not None else random

    async def __call__(
        self,
        context: "PhaseContext",
        banishment_input: "BanishmentInput",
        participant: Optional[Participant] = None,
        events_so_far: Optional[list[GameEvent]] = None,
    ) -> HandlerResult:
        """Execute the BanishmentResolution subphase for banished players.

        Args:
            context: Game state with players, living/dead, sheriff
            banishment_input: Input with banished player seat (None if tie)
            participant: Participant for querying AI/human decisions (the banished player)
            events_so_far: Previous game events for public visibility filtering

        Returns:
            HandlerResult with SubPhaseLog containing DeathEvent (or empty if no banishment)
        """
        events_so_far = events_so_far or []
        banished = banishment_input.banished
        day = banishment_input.day

        # No banishment - return empty result
        if banished is None:
            return HandlerResult(
                subphase_log=SubPhaseLog(
                    micro_phase=SubPhase.BANISHMENT_RESOLUTION,
                    events=[],
                ),
                debug_info="No banishment (tie or no votes)",
            )

        # Process the banishment
        death_event = await self._create_banishment_death_event(
            context=context,
            banished=banished,
            day=day,
            participant=participant,
            events_so_far=events_so_far,
        )

        debug_info = self._build_debug_info(death_event, banished)

        return HandlerResult(
            subphase_log=SubPhaseLog(
                micro_phase=SubPhase.BANISHMENT_RESOLUTION,
                events=[death_event],
            ),
            debug_info=debug_info,
        )

    async def _create_banishment_death_event(
        self,
        context: "PhaseContext",
        banished: int,
        day: int,
        participant: Optional[Participant] = None,
        events_so_far: Optional[list[GameEvent]] = None,
    ) -> DeathEvent:
        """Create a DeathEvent for the banished player.

        Args:
            context: Game state
            banished: Seat of banished player
            day: Current day number
            participant: Participant for querying AI/human decisions
            events_so_far: Previous game events for public visibility filtering

        Returns:
            DeathEvent with all associated actions resolved
        """
        events_so_far = events_so_far or []
        player = context.get_player(banished)

        # Last words: always required for banishment (unlike night deaths)
        last_words = await self._get_last_words(
            context=context,
            seat=banished,
            day=day,
            participant=participant,
            events_so_far=events_so_far,
        )

        # Hunter shoot: Hunter CAN shoot on banishment (unlike POISON death)
        hunter_shoot_target = await self._get_hunter_shoot_target(
            context=context,
            seat=banished,
            day=day,
            participant=participant,
            events_so_far=events_so_far,
        )

        # Badge transfer: only if Sheriff
        badge_transfer_to = await self._get_badge_transfer(
            context=context,
            seat=banished,
            day=day,
            participant=participant,
            events_so_far=events_so_far,
        )

        return DeathEvent(
            actor=banished,
            cause=DeathCause.BANISHMENT,
            last_words=last_words,
            hunter_shoot_target=hunter_shoot_target,
            badge_transfer_to=badge_transfer_to,
            phase=Phase.DAY,
            micro_phase=SubPhase.BANISHMENT_RESOLUTION,
            day=day,
        )

    async def _get_last_words(
        self,
        context: "PhaseContext",
        seat: int,
        day: int,
        participant: Optional[Participant] = None,
        events_so_far: Optional[list[GameEvent]] = None,
    ) -> str:
        """Get last words from banished player.

        Last words are ALWAYS required for banishment.

        Args:
            context: Game state
            seat: Banished player seat
            day: Current day number
            participant: Participant for AI query
            events_so_far: Previous game events for public visibility filtering

        Returns:
            Last words string (always non-empty for banishment)
        """
        events_so_far = events_so_far or []
        player = context.get_player(seat)
        if player is None:
            return "..."

        # If participant available, query them
        if participant is not None:
            system, user = self._build_last_words_prompts(context, seat, day, events_so_far)
            try:
                response = await participant.decide(system, user)
                if response and len(response.strip()) >= 10:
                    return response.strip()
            except Exception as e:
                self.logger.warning(f"Last words generation failed for seat {seat}: {e}")

        # Fallback to template
        return self._generate_last_words_template(context, seat)

    def _build_last_words_prompts(
        self,
        context: "PhaseContext",
        seat: int,
        day: int,
        events_so_far: Optional[list[GameEvent]] = None,
    ) -> tuple[str, str]:
        """Build system and user prompts for last words.

        Args:
            context: Game state
            seat: Banished player seat
            day: Current day number
            events_so_far: Previous game events for public visibility filtering

        Returns:
            (system_prompt, user_prompt)
        """
        # Get public events
        public_events = get_public_events(events_so_far or [], day, seat)
        public_events_text = format_public_events(
            public_events, context.living_players, context.dead_players, seat,
        )

        # Level 1: Static system prompt
        system = get_banishment_last_words_system()

        # Level 2: Game state context
        state_context = make_banishment_last_words_context(
            context=context,
            your_seat=seat,
            day=day,
        )

        # Level 3: Decision prompt with public events
        decision = build_banishment_last_words_decision(
            state_context,
            public_events_text=public_events_text,
        )

        # Build user prompt
        user = decision.to_llm_prompt()

        return system, user

    def _generate_last_words_template(
        self,
        context: "PhaseContext",
        seat: int,
    ) -> str:
        """Generate last words template for a banished player.

        Args:
            context: Game state
            seat: Banished player seat

        Returns:
            Last words string
        """
        player = context.get_player(seat)
        if player is None:
            return "..."

        role = player.role

        # Generate role-appropriate last words
        if role == Role.SEER:
            return self._generate_seer_last_words(context)
        elif role == Role.WITCH:
            return self._generate_witch_last_words(context)
        elif role == Role.HUNTER:
            return self._generate_hunter_last_words(context)
        elif role == Role.GUARD:
            return self._generate_guard_last_words(context)
        elif role == Role.WEREWOLF:
            return self._generate_werewolf_last_words(context)
        else:
            return self._generate_villager_last_words(context)

    def _generate_seer_last_words(self, context: "PhaseContext") -> str:
        """Generate last words for a banished Seer."""
        return "I am the Seer. Trust my visions and find the wolves!"

    def _generate_witch_last_words(self, context: "PhaseContext") -> str:
        """Generate last words for a banished Witch."""
        return "I am the Witch. I protected our team with my potions."

    def _generate_hunter_last_words(self, context: "PhaseContext") -> str:
        """Generate last words for a banished Hunter."""
        return "I am the Hunter. The real wolves will regret this!"

    def _generate_guard_last_words(self, context: "PhaseContext") -> str:
        """Generate last words for a banished Guard."""
        return "I am the Guard. I protected players every night."

    def _generate_werewolf_last_words(self, context: "PhaseContext") -> str:
        """Generate last words for a banished Werewolf."""
        return "The werewolves will have their revenge. You made a mistake."

    def _generate_villager_last_words(self, context: "PhaseContext") -> str:
        """Generate last words for a banished Villager."""
        return "I am an Innocent Villager. You voted out the wrong person!"

    async def _get_hunter_shoot_target(
        self,
        context: "PhaseContext",
        seat: int,
        day: int,
        participant: Optional[Participant] = None,
        events_so_far: Optional[list[GameEvent]] = None,
    ) -> Optional[int]:
        """Get hunter shoot target if applicable.

        Hunter CAN shoot on banishment (unlike POISON death which prevents shooting).

        Args:
            context: Game state
            seat: Dead player seat (potential Hunter)
            day: Current day number
            participant: Participant for AI query
            events_so_far: Previous game events for public visibility filtering

        Returns:
            Hunter shoot target (None = skipped or not applicable)
        """
        events_so_far = events_so_far or []
        player = context.get_player(seat)
        if player is None:
            return None

        # Hunter can shoot on banishment
        if player.role != Role.HUNTER:
            return None

        # If participant available, query them
        if participant is not None:
            return await self._query_hunter_shoot(context, seat, day, participant, events_so_far)

        # Generate AI decision for hunter shoot target
        return self._choose_hunter_shoot_target(context, seat)

    async def _query_hunter_shoot(
        self,
        context: "PhaseContext",
        hunter_seat: int,
        day: int,
        participant: Participant,
        events_so_far: Optional[list[GameEvent]] = None,
    ) -> Optional[int]:
        """Query hunter for shoot target with retries."""
        events_so_far = events_so_far or []

        # Get public events
        public_events = get_public_events(events_so_far, day, hunter_seat)
        public_events_text = format_public_events(
            public_events, context.living_players, context.dead_players, hunter_seat,
        )

        # Level 1: Static system prompt
        system = get_banishment_hunter_shoot_system()

        # Level 2: Game state context
        state_context = make_banishment_hunter_shoot_context(
            context=context,
            hunter_seat=hunter_seat,
            day=day,
        )

        # Level 3: Decision prompt with public events
        decision = build_banishment_hunter_shoot_decision(
            state_context,
            public_events_text=public_events_text,
        )

        # Build user prompt
        user = decision.to_llm_prompt()

        # Build choices using the handler's method (returns ChoiceSpec)
        choices = self._build_hunter_shoot_choices(context, hunter_seat)

        for attempt in range(self.max_retries):
            response = await participant.decide(system, user, choices=choices)
            target = self._parse_hunter_shoot_response(response, context, hunter_seat)
            if target is None:
                return None  # User chose to skip
            if target != 'RETRY':
                return target

            hint = "Please enter a valid seat number or SKIP."
            response = await participant.decide(system, user, hint=hint, choices=choices)
            target = self._parse_hunter_shoot_response(response, context, hunter_seat)
            if target is None:
                return None  # User chose to skip
            if target != 'RETRY':
                return target

        raise ValueError(f"Hunter {hunter_seat} failed to provide valid shoot target after {self.max_retries} attempts")

    def _build_hunter_shoot_choices(self, context: "PhaseContext", hunter_seat: int) -> ChoiceSpec:
        """Build ChoiceSpec for hunter shoot decision.

        Args:
            context: Game state
            hunter_seat: Hunter's seat

        Returns:
            ChoiceSpec with skip option and living player seats
        """
        living_players = sorted(context.living_players - {hunter_seat})

        return make_seat_choice(
            prompt="Choose a player to shoot:",
            seats=living_players,
            allow_none=True,  # Hunter can skip
        )

    def _parse_hunter_shoot_response(
        self,
        response: str,
        context: "PhaseContext",
        hunter_seat: int,
    ) -> Optional[int]:
        """Parse hunter shoot response.

        Returns:
            - None: User explicitly chose to skip (SKIP, NONE, -1, PASS)
            - int: Target seat to shoot
            - 'RETRY': Response was invalid, need to retry
        """
        response = response.strip()

        if response.upper() in ("SKIP", "NONE", "-1", "PASS"):
            return None  # Explicit skip

        try:
            target = int(response)
            living_players = context.living_players - {hunter_seat}
            if target in living_players:
                return target
        except ValueError:
            pass

        return 'RETRY'  # Invalid response, should retry

    def _choose_hunter_shoot_target(
        self,
        context: "PhaseContext",
        hunter_seat: int,
    ) -> Optional[int]:
        """Choose hunter shoot target (AI decision).

        Hunter chooses one living player to shoot, or None to skip.

        Args:
            context: Game state
            hunter_seat: Hunter's seat (being banished)

        Returns:
            Target seat to shoot, or None to skip
        """
        # Get living players (excluding the hunter who is about to die)
        living_candidates = sorted(context.living_players - {hunter_seat})

        if not living_candidates:
            return None

        # AI strategy: prefer werewolves, then random
        # This is a simplified strategy - in a full implementation,
        # this would involve AI reasoning

        # Try to identify werewolves among living players
        werewolf_candidates = [
            seat for seat in living_candidates
            if context.is_werewolf(seat)
        ]

        if werewolf_candidates:
            # Shoot lowest seat werewolf
            return min(werewolf_candidates)

        # No obvious werewolves - skip or pick random (30% skip chance)
        # On banishment, hunter is more likely to shoot (revenge motive)
        if self._random.random() < 0.3:
            return None

        if living_candidates:
            return min(living_candidates)

        return None

    async def _get_badge_transfer(
        self,
        context: "PhaseContext",
        seat: int,
        day: int,
        participant: Optional[Participant] = None,
        events_so_far: Optional[list[GameEvent]] = None,
    ) -> Optional[int]:
        """Get badge transfer target if banished player is Sheriff.

        Args:
            context: Game state
            seat: Banished player seat (potential Sheriff)
            day: Current day number
            participant: Participant for AI query
            events_so_far: Previous game events for public visibility filtering

        Returns:
            Badge transfer target or None
        """
        events_so_far = events_so_far or []
        player = context.get_player(seat)
        if player is None:
            return None

        if not player.is_sheriff:
            return None

        # If participant available, query them
        if participant is not None:
            return await self._query_badge_transfer(context, seat, day, participant, events_so_far)

        # Generate AI decision for badge transfer
        return self._choose_badge_heir(context, seat)

    async def _query_badge_transfer(
        self,
        context: "PhaseContext",
        sheriff_seat: int,
        day: int,
        participant: Participant,
        events_so_far: Optional[list[GameEvent]] = None,
    ) -> Optional[int]:
        """Query sheriff for badge transfer with retries."""
        events_so_far = events_so_far or []

        # Get public events
        public_events = get_public_events(events_so_far, day, sheriff_seat)
        public_events_text = format_public_events(
            public_events, context.living_players, context.dead_players, sheriff_seat,
        )

        # Level 1: Static system prompt
        system = get_banishment_badge_transfer_system()

        # Level 2: Game state context
        state_context = make_banishment_badge_transfer_context(
            context=context,
            sheriff_seat=sheriff_seat,
            day=day,
        )

        # Level 3: Decision prompt with public events
        decision = build_banishment_badge_transfer_decision(
            state_context,
            public_events_text=public_events_text,
        )

        # Build user prompt
        user = decision.to_llm_prompt()

        # Build choices using the handler's method (returns ChoiceSpec)
        choices = self._build_badge_transfer_choices(context, sheriff_seat)

        for attempt in range(self.max_retries):
            response = await participant.decide(system, user, choices=choices)
            target = self._parse_badge_transfer_response(response, context, sheriff_seat)
            if target is None:
                return None  # User chose to skip
            if target != 'RETRY':
                return target

            hint = "Please enter a valid seat number or SKIP."
            response = await participant.decide(system, user, hint=hint, choices=choices)
            target = self._parse_badge_transfer_response(response, context, sheriff_seat)
            if target is None:
                return None  # User chose to skip
            if target != 'RETRY':
                return target

        raise ValueError(f"Sheriff {sheriff_seat} failed to provide valid badge transfer target after {self.max_retries} attempts")

    def _build_badge_transfer_choices(self, context: "PhaseContext", sheriff_seat: int) -> ChoiceSpec:
        """Build ChoiceSpec for badge transfer.

        Args:
            context: Game state
            sheriff_seat: Sheriff's seat

        Returns:
            ChoiceSpec with skip option and living player seats
        """
        living_players = sorted(context.living_players - {sheriff_seat})

        return make_seat_choice(
            prompt="Choose who to pass the badge to (or Skip):",
            seats=living_players,
            allow_none=True,
        )

    def _parse_badge_transfer_response(
        self,
        response: str,
        context: "PhaseContext",
        sheriff_seat: int,
    ) -> Optional[int]:
        """Parse badge transfer response.

        Returns:
            - None: User explicitly chose to skip (SKIP, NONE, -1, PASS)
            - int: Target seat for badge transfer
            - 'RETRY': Response was invalid, need to retry
        """
        response = response.strip()

        if response.upper() in ("SKIP", "NONE", "-1", "PASS"):
            return None  # Explicit skip

        try:
            target = int(response)
            living_players = context.living_players - {sheriff_seat}
            if target in living_players:
                return target
        except ValueError:
            pass

        return 'RETRY'  # Invalid response, should retry

    def _choose_badge_heir(
        self,
        context: "PhaseContext",
        sheriff_seat: int,
    ) -> Optional[int]:
        """Choose badge heir (AI decision).

        Sheriff designates a living player as badge heir, or None to skip.

        Args:
            context: Game state
            sheriff_seat: Sheriff's seat (being banished)

        Returns:
            Heir seat or None to skip
        """
        # Get living players (excluding the sheriff who is about to die)
        living_candidates = sorted(context.living_players - {sheriff_seat})

        if not living_candidates:
            return None

        # AI strategy: prefer trusted players (God roles, then villagers)
        # Prefer non-werewolves obviously
        # This is a simplified strategy - in a full implementation,
        # this would involve AI reasoning based on game state

        # Filter out werewolves
        trusted_candidates = [
            seat for seat in living_candidates
            if not context.is_werewolf(seat)
        ]

        if trusted_candidates:
            # Choose lowest seat trusted player
            return min(trusted_candidates)

        # All remaining are werewolves - skip
        return None

    def _build_debug_info(
        self,
        event: DeathEvent,
        banished: int,
    ) -> str:
        """Build debug info string for banishment resolution.

        Args:
            event: Created DeathEvent object
            banished: Original banished seat

        Returns:
            Debug info string
        """
        player_parts = [
            f"banished={banished}",
            f"cause={event.cause.value}",
        ]

        if event.last_words:
            player_parts.append(f"last_words=\"{event.last_words}\"")
        else:
            player_parts.append("last_words=None")

        if event.hunter_shoot_target is not None:
            player_parts.append(f"hunter_shoot={event.hunter_shoot_target}")
        else:
            player_parts.append("hunter_shoot=None")

        if event.badge_transfer_to is not None:
            player_parts.append(f"badge_transfer={event.badge_transfer_to}")
        else:
            player_parts.append("badge_transfer=None")

        return ", ".join(player_parts)


# ============================================================================
# Input Types
# ============================================================================


class BanishmentInput:
    """Input type representing a banishment for resolution.

    Contains the banished player seat (None if tie/no banishment).
    """

    day: int
    banished: Optional[int]  # None = no banishment (tie)

    def __init__(self, day: int, banished: Optional[int]):
        self.day = day
        self.banished = banished


# ============================================================================
# PhaseContext (for type hints)
# ============================================================================


# Import PhaseContext from werewolf_handler for type hints
# Using TYPE_CHECKING to avoid circular imports
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from werewolf.handlers.werewolf_handler import PhaseContext
