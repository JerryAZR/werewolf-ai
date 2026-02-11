"""BanishmentResolution handler for the Werewolf AI game.

This handler processes BANISHMENT deaths from Voting, generating DeathEvent
for the banished player with:
- Last words (always required for banishment)
- Hunter shoot target (if Hunter - can shoot unlike night poison death)
- Badge transfer (if Sheriff)

For night deaths, see DeathResolution handler.
"""

from typing import Optional, Sequence, Protocol, Any
from pydantic import BaseModel, Field

from werewolf.events.game_events import (
    DeathEvent,
    DeathCause,
    Phase,
    SubPhase,
)
from werewolf.models.player import Player, Role


# ============================================================================
# AI Prompts (Single Source of Truth)
# ============================================================================
# These constants define all prompts used by this handler.
# See PROMPTS.md for human-readable documentation of these prompts.


PROMPT_LAST_WORDS_SYSTEM = """You are a player at seat {seat} and you are about to be banished.

YOUR ROLE: {role_name}

DEATH CIRCUMSTANCES: You are being banished by the village vote.

This is your chance to speak your final words to the village.
Make them memorable and strategic - consider:
- What information to reveal
- Who to trust or suspect
- What you want your allies/enemies to know

Your response should be your final speech as a single string.
Be authentic to your role and strategic for your team's victory!"""


PROMPT_LAST_WORDS_USER = """=== Banishment - Your Final Words ===

YOUR INFORMATION:
  Your seat: {seat}
  Your role: {role_name} (keep secret or reveal as you choose)
  You are about to be banished!

DEATH CONTEXT:
  Banishment by village vote

LIVING PLAYERS: {living_seats}

DEAD PLAYERS: {dead_seats}

This is your last chance to speak! You may:
- Reveal your role or keep it hidden
- Share information or mislead
- Accuse others or defend yourself
- Say farewell

Enter your final speech below:
(Must be non-empty - this is your last chance to speak!)"""


PROMPT_HUNTER_SHOOT_SYSTEM = """You are the Hunter at seat {hunter_seat} and you are being banished!

YOUR ROLE:
- As the Hunter, you get ONE final shot before dying
- You can shoot any ONE living player (werewolf, villager, anyone)
- You may also choose to SKIP (not shoot anyone)
- Your shot is your last action in the game

IMPORTANT RULES:
1. You can shoot any living player
2. Werewolves appear as WEREWOLF, everyone else appears as GOOD
3. This is your final action - choose wisely!

Your response should be: TARGET_SEAT or "SKIP"
- Example: "7" (shoot player at seat 7)
- Example: "SKIP" (don't shoot anyone)"""


PROMPT_HUNTER_SHOOT_USER = """=== Banishment - Hunter Final Shot ===

YOUR IDENTITY:
  You are the Hunter at seat {hunter_seat}
  You are being banished!
  This is your LAST ACTION - choose wisely!

LIVING PLAYERS (potential targets):
  Seats: {living_seats}

RULES:
  - You can shoot any ONE living player
  - Werewolves appear as WEREWOLF
  - All other roles (Villager, Guard, Witch, Seer) appear as GOOD
  - You may also SKIP (not shoot anyone)

HINT: {werewolf_hint}

Enter your choice (e.g., "7" or "SKIP"):"""


PROMPT_BADGE_TRANSFER_SYSTEM = """You are the Sheriff at seat {sheriff_seat} and you are about to be banished.

SHERIFF POWERS:
- The Sheriff has 1.5x vote weight
- The Sheriff speaks LAST during all discussions
- When you die, you can transfer your badge to ONE living player

IMPORTANT RULES:
1. You can transfer to any living player
2. Werewolves will try to masquerade as good - choose wisely!
3. If you SKIP, no one gets the badge

Your response should be: TARGET_SEAT or "SKIP"
- Example: "7" (transfer badge to player at seat 7)
- Example: "SKIP" (don't transfer the badge)"""


PROMPT_BADGE_TRANSFER_USER = """=== Banishment - Sheriff Badge Transfer ===

YOUR IDENTITY:
  You are the Sheriff at seat {sheriff_seat}
  You are about to be banished and must decide who inherits your badge!

SHERIFF POWERS:
  - Badge holder has 1.5x vote weight
  - Badge holder speaks LAST during discussions
  - This is your LAST DECISION - choose wisely!

LIVING PLAYERS (potential heirs):
  Seats: {living_seats}

RULES:
  - Choose ONE living player to receive your badge
  - You may SKIP (no one gets the badge)
  - Werewolves appear as WEREWOLF
  - All other roles appear as GOOD

HINT: {trusted_hint}

Enter your choice (e.g., "7" or "SKIP"):"""


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
# Handler Result Types
# ============================================================================


class SubPhaseLog(BaseModel):
    """Generic subphase container with events."""

    micro_phase: SubPhase
    events: list[DeathEvent] = Field(default_factory=list)


class HandlerResult(BaseModel):
    """Output from handlers containing all events from a subphase."""

    subphase_log: SubPhaseLog
    debug_info: Optional[str] = None


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
    """

    # Maximum retry attempts for invalid input
    max_retries: int = 3

    async def __call__(
        self,
        context: "PhaseContext",
        banishment_input: "BanishmentInput",
        participant: Optional[Participant] = None,
    ) -> HandlerResult:
        """Execute the BanishmentResolution subphase for banished players.

        Args:
            context: Game state with players, living/dead, sheriff
            banishment_input: Input with banished player seat (None if tie)
            participant: Participant for querying AI/human decisions (the banished player)

        Returns:
            HandlerResult with SubPhaseLog containing DeathEvent (or empty if no banishment)
        """
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
    ) -> DeathEvent:
        """Create a DeathEvent for the banished player.

        Args:
            context: Game state
            banished: Seat of banished player
            day: Current day number
            participant: Participant for querying AI/human decisions

        Returns:
            DeathEvent with all associated actions resolved
        """
        player = context.get_player(banished)

        # Last words: always required for banishment (unlike night deaths)
        last_words = await self._get_last_words(
            context=context,
            seat=banished,
            day=day,
            participant=participant,
        )

        # Hunter shoot: Hunter CAN shoot on banishment (unlike POISON death)
        hunter_shoot_target = await self._get_hunter_shoot_target(
            context=context,
            seat=banished,
            day=day,
            participant=participant,
        )

        # Badge transfer: only if Sheriff
        badge_transfer_to = await self._get_badge_transfer(
            context=context,
            seat=banished,
            day=day,
            participant=participant,
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
    ) -> str:
        """Get last words from banished player.

        Last words are ALWAYS required for banishment.

        Args:
            context: Game state
            seat: Banished player seat
            day: Current day number
            participant: Participant for AI query

        Returns:
            Last words string (always non-empty for banishment)
        """
        player = context.get_player(seat)
        if player is None:
            return "..."

        # If participant available, query them
        if participant is not None:
            system, user = self._build_last_words_prompts(context, seat, day)
            try:
                response = await participant.decide(system, user)
                if response and len(response.strip()) >= 10:
                    return response.strip()
            except Exception:
                pass

        # Fallback to template
        return self._generate_last_words_template(context, seat)

    def _build_last_words_prompts(
        self,
        context: "PhaseContext",
        seat: int,
        day: int,
    ) -> tuple[str, str]:
        """Build system and user prompts for last words.

        Args:
            context: Game state
            seat: Banished player seat
            day: Current day number

        Returns:
            (system_prompt, user_prompt)
        """
        player = context.get_player(seat)
        role_name = player.role.name.replace("_", " ").title() if player else "Unknown"

        living_seats = sorted(context.living_players - {seat})
        dead_seats = sorted(context.dead_players)

        system = PROMPT_LAST_WORDS_SYSTEM.format(
            seat=seat,
            role_name=role_name,
        )
        user = PROMPT_LAST_WORDS_USER.format(
            seat=seat,
            role_name=role_name,
            living_seats=", ".join(map(str, living_seats)) if living_seats else "None",
            dead_seats=", ".join(map(str, dead_seats)) if dead_seats else "None",
        )

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
    ) -> Optional[int]:
        """Get hunter shoot target if applicable.

        Hunter CAN shoot on banishment (unlike POISON death which prevents shooting).

        Args:
            context: Game state
            seat: Dead player seat (potential Hunter)
            day: Current day number
            participant: Participant for AI query

        Returns:
            Hunter shoot target (None = skipped or not applicable)
        """
        player = context.get_player(seat)
        if player is None:
            return None

        # Hunter can shoot on banishment
        if player.role != Role.HUNTER:
            return None

        # If participant available, query them
        if participant is not None:
            return await self._query_hunter_shoot(context, seat, day, participant)

        # Generate AI decision for hunter shoot target
        return self._choose_hunter_shoot_target(context, seat)

    async def _query_hunter_shoot(
        self,
        context: "PhaseContext",
        hunter_seat: int,
        day: int,
        participant: Participant,
    ) -> Optional[int]:
        """Query hunter for shoot target with retries."""
        living_players = sorted(context.living_players - {hunter_seat})

        # Identify werewolves for hint
        werewolves = [s for s in living_players if context.is_werewolf(s)]
        werewolf_hint = f"Known werewolves: {werewolves}" if werewolves else "No known werewolves."

        system = PROMPT_HUNTER_SHOOT_SYSTEM.format(hunter_seat=hunter_seat)
        user = PROMPT_HUNTER_SHOOT_USER.format(
            hunter_seat=hunter_seat,
            living_seats=", ".join(map(str, living_players)),
            werewolf_hint=werewolf_hint,
        )

        for attempt in range(self.max_retries):
            try:
                response = await participant.decide(system, user)
                target = self._parse_hunter_shoot_response(response, context, hunter_seat)
                if target is not None:
                    return target
            except Exception:
                pass

            hint = "Please enter a valid seat number or SKIP."
            try:
                response = await participant.decide(system, user, hint)
                target = self._parse_hunter_shoot_response(response, context, hunter_seat)
                if target is not None:
                    return target
            except Exception:
                break

        return None

    def _parse_hunter_shoot_response(
        self,
        response: str,
        context: "PhaseContext",
        hunter_seat: int,
    ) -> Optional[int]:
        """Parse hunter shoot response."""
        response = response.strip()

        if response.upper() in ("SKIP", "NONE", "-1", "PASS"):
            return None

        try:
            target = int(response)
            living_players = context.living_players - {hunter_seat}
            if target in living_players:
                return target
        except ValueError:
            pass

        return None

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

        # No obvious werewolves - skip or pick random
        # On banishment, hunter is more likely to shoot (revenge motive)
        import random
        if random.random() < 0.3:
            return None

        return min(living_candidates)

    async def _get_badge_transfer(
        self,
        context: "PhaseContext",
        seat: int,
        day: int,
        participant: Optional[Participant] = None,
    ) -> Optional[int]:
        """Get badge transfer target if banished player is Sheriff.

        Args:
            context: Game state
            seat: Banished player seat (potential Sheriff)
            day: Current day number
            participant: Participant for AI query

        Returns:
            Badge transfer target or None
        """
        player = context.get_player(seat)
        if player is None:
            return None

        if not player.is_sheriff:
            return None

        # If participant available, query them
        if participant is not None:
            return await self._query_badge_transfer(context, seat, day, participant)

        # Generate AI decision for badge transfer
        return self._choose_badge_heir(context, seat)

    async def _query_badge_transfer(
        self,
        context: "PhaseContext",
        sheriff_seat: int,
        day: int,
        participant: Participant,
    ) -> Optional[int]:
        """Query sheriff for badge transfer with retries."""
        living_players = sorted(context.living_players - {sheriff_seat})

        # Identify trusted players for hint
        trusted = [s for s in living_players if not context.is_werewolf(s)]
        trusted_hint = f"Trusted players: {trusted}" if trusted else "No known trusted players."

        system = PROMPT_BADGE_TRANSFER_SYSTEM.format(sheriff_seat=sheriff_seat)
        user = PROMPT_BADGE_TRANSFER_USER.format(
            sheriff_seat=sheriff_seat,
            living_seats=", ".join(map(str, living_players)),
            trusted_hint=trusted_hint,
        )

        for attempt in range(self.max_retries):
            try:
                response = await participant.decide(system, user)
                target = self._parse_badge_transfer_response(response, context, sheriff_seat)
                if target is not None:
                    return target
            except Exception:
                pass

            hint = "Please enter a valid seat number or SKIP."
            try:
                response = await participant.decide(system, user, hint)
                target = self._parse_badge_transfer_response(response, context, sheriff_seat)
                if target is not None:
                    return target
            except Exception:
                break

        return None

    def _parse_badge_transfer_response(
        self,
        response: str,
        context: "PhaseContext",
        sheriff_seat: int,
    ) -> Optional[int]:
        """Parse badge transfer response."""
        response = response.strip()

        if response.upper() in ("SKIP", "NONE", "-1", "PASS"):
            return None

        try:
            target = int(response)
            living_players = context.living_players - {sheriff_seat}
            if target in living_players:
                return target
        except ValueError:
            pass

        return None

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
