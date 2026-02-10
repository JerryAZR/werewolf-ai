"""DeathResolution handler for the Werewolf AI game.

This handler processes NIGHT deaths from NightOutcome, generating DeathEvent
for each death with:
- Last words (Night 1 only)
- Hunter shoot target (if Hunter + WEREWOLF_KILL)
- Badge transfer (if Sheriff)

For banishment deaths, see BanishmentResolution handler.
"""

from typing import Optional, Sequence
from pydantic import Field

from src.werewolf.events.game_events import (
    DeathEvent,
    DeathCause,
    Phase,
    SubPhase,
)
from src.werewolf.models.player import Player, Role


# ============================================================================
# Handler Result Types
# ============================================================================


class SubPhaseLog:
    """Generic subphase container with events."""

    micro_phase: SubPhase
    events: list[DeathEvent]

    def __init__(self, micro_phase: SubPhase, events: list[DeathEvent]):
        self.micro_phase = micro_phase
        self.events = events


class HandlerResult:
    """Output from handlers containing all events from a subphase."""

    subphase_log: SubPhaseLog
    debug_info: Optional[str] = None

    def __init__(self, subphase_log: SubPhaseLog, debug_info: Optional[str] = None):
        self.subphase_log = subphase_log
        self.debug_info = debug_info


# ============================================================================
# Death Resolution Handler
# ============================================================================


class DeathResolutionHandler:
    """Handler for DeathResolution subphase (night deaths only).

    Responsibilities:
    1. Process deaths from NightOutcome (WEREWOLF_KILL or POISON)
    2. Generate DeathEvent for each death with:
       - cause: matches the death source
       - last_words: Night 1 only (night 2+ no last words)
       - hunter_shoot_target: if Hunter + WEREWOLF_KILL (None = skipped)
       - badge_transfer_to: if Sheriff (None = skipped)

    Validation Rules:
    - Hunter can ONLY shoot if killed by WEREWOLF_KILL
    - Hunter cannot shoot if POISONED
    - Badge transfer target must be living
    - Hunter shoot target must be living

    This is engine-only logic - no participants are consulted.
    """

    def __call__(
        self,
        context: "PhaseContext",
        night_outcome: "NightOutcomeInput",
    ) -> HandlerResult:
        """Execute the DeathResolution subphase for night deaths.

        Args:
            context: Game state with players, living/dead, sheriff
            night_outcome: NightOutcome with deaths dict {seat: DeathCause}

        Returns:
            HandlerResult with SubPhaseLog containing DeathEvent(s)
        """
        events = []
        deaths = night_outcome.deaths

        # No deaths - return empty result
        if not deaths:
            return HandlerResult(
                subphase_log=SubPhaseLog(
                    micro_phase=SubPhase.DEATH_RESOLUTION,
                    events=[],
                ),
                debug_info="No night deaths to resolve",
            )

        # Process each death
        for seat, cause in sorted(deaths.items()):
            death_event = self._create_death_event(
                context=context,
                seat=seat,
                cause=cause,
                day=night_outcome.day,
            )
            events.append(death_event)

        # Build debug info
        debug_info = self._build_debug_info(events, deaths)

        return HandlerResult(
            subphase_log=SubPhaseLog(
                micro_phase=SubPhase.DEATH_RESOLUTION,
                events=events,
            ),
            debug_info=debug_info,
        )

    def _create_death_event(
        self,
        context: "PhaseContext",
        seat: int,
        cause: DeathCause,
        day: int,
    ) -> DeathEvent:
        """Create a DeathEvent for a single death.

        Args:
            context: Game state
            seat: Dead player seat
            cause: DeathCause (WEREWOLF_KILL or POISON)
            day: Current day number

        Returns:
            DeathEvent with all associated actions resolved
        """
        player = context.get_player(seat)

        # Last words: Night 1 only (night 2+ no last words for night deaths)
        last_words = self._get_last_words(context, seat, day)

        # Hunter shoot: only if Hunter + WEREWOLF_KILL
        hunter_shoot_target = self._get_hunter_shoot_target(
            context=context,
            seat=seat,
            cause=cause,
        )

        # Badge transfer: only if Sheriff
        badge_transfer_to = self._get_badge_transfer(
            context=context,
            seat=seat,
        )

        return DeathEvent(
            actor=seat,
            cause=cause,
            last_words=last_words,
            hunter_shoot_target=hunter_shoot_target,
            badge_transfer_to=badge_transfer_to,
            phase=Phase.DAY,
            micro_phase=SubPhase.DEATH_RESOLUTION,
            day=day,
        )

    def _get_last_words(
        self,
        context: "PhaseContext",
        seat: int,
        day: int,
    ) -> Optional[str]:
        """Get last words for a night death.

        Night 1 deaths: last words allowed
        Night 2+ deaths: no last words

        Args:
            context: Game state
            seat: Dead player seat
            day: Current day number

        Returns:
            Last words string or None (night 2+)
        """
        if day == 1:
            return self._generate_last_words(context, seat)
        return None

    def _generate_last_words(
        self,
        context: "PhaseContext",
        seat: int,
    ) -> str:
        """Generate last words for a dying player (Night 1 only).

        This generates appropriate last words based on the player's role
        and game state.

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

    def _get_hunter_shoot_target(
        self,
        context: "PhaseContext",
        seat: int,
        cause: DeathCause,
    ) -> Optional[int]:
        """Get hunter shoot target if applicable.

        Hunter can ONLY shoot if:
        1. Dead player is Hunter
        2. Death cause is WEREWOLF_KILL (not POISON)

        Args:
            context: Game state
            seat: Dead player seat (potential Hunter)
            cause: DeathCause

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

        # Generate AI decision for hunter shoot target
        return self._choose_hunter_shoot_target(context, seat)

    def _choose_hunter_shoot_target(
        self,
        context: "PhaseContext",
        hunter_seat: int,
    ) -> Optional[int]:
        """Choose hunter shoot target (AI decision).

        Hunter chooses one living player to shoot, or None to skip.

        Args:
            context: Game state
            hunter_seat: Hunter's seat (dying)

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
        # 50% chance to skip, 50% chance to pick random
        import random
        if random.random() < 0.5:
            return None

        return min(living_candidates)

    def _get_badge_transfer(
        self,
        context: "PhaseContext",
        seat: int,
    ) -> Optional[int]:
        """Get badge transfer target if dead player is Sheriff.

        Args:
            context: Game state
            seat: Dead player seat (potential Sheriff)

        Returns:
            Badge transfer target or None
        """
        player = context.get_player(seat)
        if player is None:
            return None

        if not player.is_sheriff:
            return None

        # Generate AI decision for badge transfer
        return self._choose_badge_heir(context, seat)

    def _choose_badge_heir(
        self,
        context: "PhaseContext",
        sheriff_seat: int,
    ) -> Optional[int]:
        """Choose badge heir (AI decision).

        Sheriff designates a living player as badge heir, or None to skip.

        Args:
            context: Game state
            sheriff_seat: Sheriff's seat (dying)

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
    from src.werewolf.handlers.werewolf_handler import PhaseContext
