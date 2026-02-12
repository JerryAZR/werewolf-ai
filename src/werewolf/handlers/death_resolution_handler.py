"""DeathResolution handler for the Werewolf AI game.

This handler processes NIGHT deaths from NightOutcome, querying participants
for:
- Last words (Night 1 only, any role)
- Hunter shoot target (if Hunter + WEREWOLF_KILL)
- Badge transfer (if Sheriff)

For banishment deaths, see BanishmentResolution handler.
"""

import random
from typing import Optional, Sequence, Protocol, Any
from pydantic import BaseModel, Field

from werewolf.events.game_events import GameEvent

from werewolf.events.game_events import (
    DeathEvent,
    DeathCause,
    Phase,
    SubPhase,
    GameEvent,
)
from werewolf.models.player import Player, Role


# ============================================================================
# AI Prompts (Single Source of Truth)
# ============================================================================
# These constants define all prompts used by this handler.
# See PROMPTS.md for human-readable documentation of these prompts.


PROMPT_LAST_WORDS_SYSTEM = """You are a player at seat {seat} and you are about to die.

YOUR ROLE: {role_name}

DEATH CIRCUMSTANCES: You died on Night {day} due to werewolf attack.

This is your chance to speak your final words to the village.
Make them memorable and strategic - consider:
- What information to reveal
- Who to trust or suspect
- What you want your allies/enemies to know

Your response should be your final speech as a single string.
Be authentic to your role and strategic for your team's victory!"""


PROMPT_LAST_WORDS_USER = """=== Night {day} - Your Final Words ===

YOUR INFORMATION:
  Your seat: {seat}
  Your role: {role_name} (keep secret or reveal as you choose)
  You are about to die!

DEATH CONTEXT:
  Night {day} death due to werewolf attack

LIVING PLAYERS: {living_seats}

DEAD PLAYERS: {dead_seats}

This is your last chance to speak! You may:
- Reveal your role or keep it hidden
- Share information or mislead
- Accuse others or defend yourself
- Say farewell

Enter your final speech below:
(Must be non-empty - this is your last chance to speak!)"""


PROMPT_HUNTER_SHOOT_SYSTEM = """You are the Hunter at seat {hunter_seat} and you have been killed by werewolves!

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


PROMPT_HUNTER_SHOOT_USER = """=== Night {day} - Hunter Final Shot ===

YOUR IDENTITY:
  You are the Hunter at seat {hunter_seat}
  You have been killed by werewolves!
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


PROMPT_BADGE_TRANSFER_SYSTEM = """You are the Sheriff at seat {sheriff_seat} and you are about to die.

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


PROMPT_BADGE_TRANSFER_USER = """=== Night {day} - Sheriff Badge Transfer ===

YOUR IDENTITY:
  You are the Sheriff at seat {sheriff_seat}
  You are about to die and must decide who inherits your badge!

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
# Death Resolution Handler
# ============================================================================


class DeathResolutionHandler:
    """Handler for NIGHT_RESOLUTION subphase (night deaths only).

    Responsibilities:
    1. Process deaths from NightOutcome (WEREWOLF_KILL or POISON)
    2. Query dying participants for:
       - Last words (Night 1 only)
       - Hunter shoot target (if Hunter + WEREWOLF_KILL)
       - Badge transfer (if Sheriff)

    Creates DeathEvents with micro_phase=NIGHT_RESOLUTION for inclusion
    in the NIGHT_RESOLUTION subphase of the night phase.

    Validation Rules:
    - Hunter can ONLY shoot if killed by WEREWOLF_KILL
    - Hunter cannot shoot if POISONED
    - Badge transfer target must be living
    - Hunter shoot target must be living
    """

    # Maximum retry attempts for invalid input
    max_retries: int = 3

    async def __call__(
        self,
        context: "PhaseContext",
        night_outcome: "NightOutcomeInput",
        participants: Optional[Sequence[tuple[int, Participant]]] = None,
        micro_phase: SubPhase = SubPhase.NIGHT_RESOLUTION,
    ) -> HandlerResult:
        """Execute the NIGHT_RESOLUTION subphase for night deaths.

        Args:
            context: Game state with players, living/dead, sheriff
            night_outcome: NightOutcome with deaths dict {seat: DeathCause}
            participants: Sequence of (seat, Participant) tuples for dying players
            micro_phase: SubPhase type for the subphase log (NIGHT_RESOLUTION or DEATH_RESOLUTION)

        Returns:
            HandlerResult with SubPhaseLog containing DeathEvent(s)
        """
        events = []
        deaths = night_outcome.deaths

        # Convert participants to dict for easier lookup
        if participants is not None:
            if isinstance(participants, dict):
                participant_dict = participants
            else:
                participant_dict = dict(participants)
        else:
            participant_dict = {}

        # No deaths - return empty result
        if not deaths:
            return HandlerResult(
                subphase_log=SubPhaseLog(
                    micro_phase=micro_phase,
                    events=[],
                ),
                debug_info="No night deaths to resolve",
            )

        # Process each death
        for seat, cause in sorted(deaths.items()):
            participant = participant_dict.get(seat)
            death_event = await self._create_death_event(
                context=context,
                seat=seat,
                cause=cause,
                day=night_outcome.day,
                participant=participant,
                micro_phase=micro_phase,
            )
            events.append(death_event)

        # Build debug info
        debug_info = self._build_debug_info(events, deaths)

        return HandlerResult(
            subphase_log=SubPhaseLog(
                micro_phase=micro_phase,
                events=events,
            ),
            debug_info=debug_info,
        )

    async def _create_death_event(
        self,
        context: "PhaseContext",
        seat: int,
        cause: DeathCause,
        day: int,
        participant: Optional[Participant] = None,
        micro_phase: SubPhase = SubPhase.NIGHT_RESOLUTION,
    ) -> DeathEvent:
        """Create a DeathEvent for a single death.

        Args:
            context: Game state
            seat: Dead player seat
            cause: DeathCause (WEREWOLF_KILL or POISON)
            day: Current day number
            participant: Participant for querying AI/human decisions
            micro_phase: SubPhase type for the death event

        Returns:
            DeathEvent with all associated actions resolved
        """
        player = context.get_player(seat)
        if player is None:
            player = Player(seat=seat, role=Role.ORDINARY_VILLAGER)

        # Query last words (Night 1 only)
        last_words = await self._get_last_words(
            context=context,
            seat=seat,
            day=day,
            participant=participant,
        )

        # Query hunter shoot target (only if Hunter + WEREWOLF_KILL)
        hunter_shoot_target = await self._get_hunter_shoot_target(
            context=context,
            seat=seat,
            cause=cause,
            day=day,
            participant=participant,
        )

        # Query badge transfer (only if Sheriff)
        badge_transfer_to = await self._get_badge_transfer(
            context=context,
            seat=seat,
            day=day,
            participant=participant,
        )

        return DeathEvent(
            actor=seat,
            cause=cause,
            last_words=last_words,
            hunter_shoot_target=hunter_shoot_target,
            badge_transfer_to=badge_transfer_to,
            phase=Phase.NIGHT,
            micro_phase=micro_phase,
            day=day,
        )

    async def _get_last_words(
        self,
        context: "PhaseContext",
        seat: int,
        day: int,
        participant: Optional[Participant] = None,
    ) -> Optional[str]:
        """Get last words from dying player (Night 1 only).

        Args:
            context: Game state
            seat: Dead player seat
            day: Current day number
            participant: Participant for AI query

        Returns:
            Last words string or None (night 2+ or no participant)
        """
        # Night 2+ no last words for night deaths
        if day > 1:
            return None

        # If no participant, use template
        if participant is None:
            return self._generate_last_words_template(context, seat)

        # Build prompts
        system, user = self._build_last_words_prompts(context, seat, day)

        # Query participant
        try:
            response = await participant.decide(system, user)
            # Validate response
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
            seat: Dying player seat
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
            day=day,
        )
        user = PROMPT_LAST_WORDS_USER.format(
            day=day,
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
        """Generate last words template for a dying player.

        Args:
            context: Game state
            seat: Dying player seat

        Returns:
            Last words string
        """
        player = context.get_player(seat)
        if player is None:
            return ""

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
        """Generate last words for a dying Seer."""
        return "I am the Seer. Trust my previous visions."

    def _generate_witch_last_words(self, context: "PhaseContext") -> str:
        """Generate last words for a dying Witch."""
        return "I am the Witch. I used my potions wisely."

    def _generate_hunter_last_words(self, context: "PhaseContext") -> str:
        """Generate last words for a dying Hunter."""
        return "I am the Hunter. I will have my revenge."

    def _generate_guard_last_words(self, context: "PhaseContext") -> str:
        """Generate last words for a dying Guard."""
        return "I am the Guard. I protected our team."

    def _generate_werewolf_last_words(self, context: "PhaseContext") -> str:
        """Generate last words for a dying Werewolf."""
        return "The wolves will prevail."

    def _generate_villager_last_words(self, context: "PhaseContext") -> str:
        """Generate last words for a dying Villager."""
        return "I am an Ordinary Villager. Find the wolves!"

    async def _get_hunter_shoot_target(
        self,
        context: "PhaseContext",
        seat: int,
        cause: DeathCause,
        day: int,
        participant: Optional[Participant] = None,
    ) -> Optional[int]:
        """Get hunter shoot target from participant.

        Hunter can ONLY shoot if:
        1. Dead player is Hunter
        2. Death cause is WEREWOLF_KILL (not POISON)

        Args:
            context: Game state
            seat: Dead player seat (potential Hunter)
            cause: DeathCause
            day: Current day number
            participant: Participant for AI query

        Returns:
            Hunter shoot target (None = skipped or not applicable)
        """
        player = context.get_player(seat)
        if player is None:
            return None

        # Hunter can only shoot if killed by werewolves
        if player.role != Role.HUNTER:
            return None

        if cause != DeathCause.WEREWOLF_KILL:
            return None

        # If no participant, use template
        if participant is None:
            return self._choose_hunter_shoot_target(context, seat)

        # Build prompts
        system, user = self._build_hunter_shoot_prompts(context, seat, day)

        # Query participant with retries
        for attempt in range(self.max_retries):
            try:
                response = await participant.decide(system, user)
                target = self._parse_hunter_shoot_response(response, context, seat)
                if target is not None:
                    return target
            except Exception:
                pass

            # Provide hint on retry
            hint = "Please enter a valid seat number or SKIP."
            try:
                response = await participant.decide(system, user, hint)
                target = self._parse_hunter_shoot_response(response, context, seat)
                if target is not None:
                    return target
            except Exception:
                break

        # Fallback to template
        return self._choose_hunter_shoot_target(context, seat)

    def _build_hunter_shoot_prompts(
        self,
        context: "PhaseContext",
        hunter_seat: int,
        day: int,
    ) -> tuple[str, str]:
        """Build system and user prompts for hunter shoot decision.

        Args:
            context: Game state
            hunter_seat: Hunter's seat (dying)
            day: Current day number

        Returns:
            (system_prompt, user_prompt)
        """
        living_players = sorted(context.living_players - {hunter_seat})

        # Identify werewolves for hint
        werewolves = [s for s in living_players if context.is_werewolf(s)]
        werewolf_hint = f"Known werewolves: {werewolves}" if werewolves else "No known werewolves."

        system = PROMPT_HUNTER_SHOOT_SYSTEM.format(hunter_seat=hunter_seat)
        user = PROMPT_HUNTER_SHOOT_USER.format(
            day=day,
            hunter_seat=hunter_seat,
            living_seats=", ".join(map(str, living_players)),
            werewolf_hint=werewolf_hint,
        )

        return system, user

        return system, user

    def _parse_hunter_shoot_response(
        self,
        response: str,
        context: "PhaseContext",
        hunter_seat: int,
    ) -> Optional[int]:
        """Parse hunter shoot response.

        Args:
            response: Raw response from participant
            context: Game state for validation
            hunter_seat: Hunter's seat

        Returns:
            Valid target seat or None
        """
        response = response.strip()

        # Handle SKIP variants
        if response.upper() in ("SKIP", "NONE", "-1", "PASS"):
            return None

        # Try to parse as seat number
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
        """Choose hunter shoot target (template fallback).

        Args:
            context: Game state
            hunter_seat: Hunter's seat (dying)

        Returns:
            Target seat to shoot, or None to skip
        """
        living_candidates = sorted(context.living_players - {hunter_seat})

        if not living_candidates:
            return None

        # Try to identify werewolves
        werewolf_candidates = [
            seat for seat in living_candidates
            if context.is_werewolf(seat)
        ]

        if werewolf_candidates:
            return min(werewolf_candidates)

        # No obvious werewolves - 50% chance to skip
        if random.random() < 0.5:
            return None

        return min(living_candidates)

    async def _get_badge_transfer(
        self,
        context: "PhaseContext",
        seat: int,
        day: int,
        participant: Optional[Participant] = None,
    ) -> Optional[int]:
        """Get badge transfer target from participant.

        Args:
            context: Game state
            seat: Dead player seat (potential Sheriff)
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

        # If no participant, use template
        if participant is None:
            return self._choose_badge_heir(context, seat)

        # Build prompts
        system, user = self._build_badge_transfer_prompts(context, seat, day)

        # Query participant with retries
        for attempt in range(self.max_retries):
            try:
                response = await participant.decide(system, user)
                target = self._parse_badge_transfer_response(response, context, seat)
                if target is not None:
                    return target
            except Exception:
                pass

            # Provide hint on retry
            hint = "Please enter a valid seat number or SKIP."
            try:
                response = await participant.decide(system, user, hint)
                target = self._parse_badge_transfer_response(response, context, seat)
                if target is not None:
                    return target
            except Exception:
                break

        # Fallback to template
        return self._choose_badge_heir(context, seat)

    def _build_badge_transfer_prompts(
        self,
        context: "PhaseContext",
        sheriff_seat: int,
        day: int,
    ) -> tuple[str, str]:
        """Build system and user prompts for badge transfer.

        Args:
            context: Game state
            sheriff_seat: Sheriff's seat (dying)
            day: Current day number

        Returns:
            (system_prompt, user_prompt)
        """
        living_players = sorted(context.living_players - {sheriff_seat})

        # Identify trusted players for hint
        trusted = [s for s in living_players if not context.is_werewolf(s)]
        trusted_hint = f"Trusted players: {trusted}" if trusted else "No known trusted players."

        system = PROMPT_BADGE_TRANSFER_SYSTEM.format(sheriff_seat=sheriff_seat)
        user = PROMPT_BADGE_TRANSFER_USER.format(
            day=day,
            sheriff_seat=sheriff_seat,
            living_seats=", ".join(map(str, living_players)),
            trusted_hint=trusted_hint,
        )

        return system, user

    def _parse_badge_transfer_response(
        self,
        response: str,
        context: "PhaseContext",
        sheriff_seat: int,
    ) -> Optional[int]:
        """Parse badge transfer response.

        Args:
            response: Raw response from participant
            context: Game state for validation
            sheriff_seat: Sheriff's seat

        Returns:
            Valid heir seat or None
        """
        response = response.strip()

        # Handle SKIP variants
        if response.upper() in ("SKIP", "NONE", "-1", "PASS"):
            return None

        # Try to parse as seat number
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
        """Choose badge heir (template fallback).

        Args:
            context: Game state
            sheriff_seat: Sheriff's seat (dying)

        Returns:
            Heir seat or None to skip
        """
        living_candidates = sorted(context.living_players - {sheriff_seat})

        if not living_candidates:
            return None

        # Filter out werewolves
        trusted_candidates = [
            seat for seat in living_candidates
            if not context.is_werewolf(seat)
        ]

        if trusted_candidates:
            return min(trusted_candidates)

        # All remaining are werewolves - skip
        return None

    def _build_debug_info(
        self,
        events: list[DeathEvent],
        deaths: dict[int, DeathCause],
    ) -> str:
        """Build debug info string for death resolution.

        Args:
            events: Created DeathEvent objects
            deaths: Original deaths dict

        Returns:
            Debug info string
        """
        parts = [
            f"deaths={sorted(deaths.items())}",
            f"death_count={len(deaths)}",
        ]

        for event in events:
            player_parts = [f"seat={event.actor}", f"cause={event.cause.value}"]

            if event.last_words:
                player_parts.append("has_last_words=True")
            else:
                player_parts.append("has_last_words=False")

            if event.hunter_shoot_target is not None:
                player_parts.append(f"hunter_shoot={event.hunter_shoot_target}")
            else:
                player_parts.append("hunter_shoot=None")

            if event.badge_transfer_to is not None:
                player_parts.append(f"badge_transfer={event.badge_transfer_to}")
            else:
                player_parts.append("badge_transfer=None")

            parts.append(f"event({', '.join(player_parts)})")

        return ", ".join(parts)


# ============================================================================
# Input Types
# ============================================================================


class NightOutcomeInput:
    """Input type representing NightOutcome for death resolution.

    This is a simplified version that captures the deaths dict.
    In the full game, this would be the NightOutcome event from NightResolution.
    """

    day: int
    deaths: dict[int, DeathCause]  # {seat: cause}

    def __init__(self, day: int, deaths: dict[int, DeathCause]):
        self.day = day
        self.deaths = deaths


# ============================================================================
# PhaseContext (for type hints)
# ============================================================================


# Import PhaseContext from werewolf_handler for type hints
# Using TYPE_CHECKING to avoid circular imports
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from werewolf.handlers.werewolf_handler import PhaseContext
