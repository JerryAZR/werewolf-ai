"""BanishmentResolution handler for the Werewolf AI game.

This handler processes BANISHMENT deaths from Voting, generating DeathEvent
for the banished player with:
- Last words (always required for banishment)
- Hunter shoot target (if Hunter - can shoot unlike night poison death)
- Badge transfer (if Sheriff)

For night deaths, see DeathResolution handler.
"""

from typing import Optional
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

    This is engine-only logic - no participants are consulted.
    """

    def __call__(
        self,
        context: "PhaseContext",
        banishment_input: "BanishmentInput",
    ) -> HandlerResult:
        """Execute the BanishmentResolution subphase for banished players.

        Args:
            context: Game state with players, living/dead, sheriff
            banishment_input: Input with banished player seat (None if tie)

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
        death_event = self._create_banishment_death_event(
            context=context,
            banished=banished,
            day=day,
        )

        debug_info = self._build_debug_info(death_event, banished)

        return HandlerResult(
            subphase_log=SubPhaseLog(
                micro_phase=SubPhase.BANISHMENT_RESOLUTION,
                events=[death_event],
            ),
            debug_info=debug_info,
        )

    def _create_banishment_death_event(
        self,
        context: "PhaseContext",
        banished: int,
        day: int,
    ) -> DeathEvent:
        """Create a DeathEvent for the banished player.

        Args:
            context: Game state
            banished: Seat of banished player
            day: Current day number

        Returns:
            DeathEvent with all associated actions resolved
        """
        player = context.get_player(banished)

        # Last words: always required for banishment (unlike night deaths)
        last_words = self._generate_last_words(context, banished)

        # Hunter shoot: Hunter CAN shoot on banishment (unlike POISON death)
        hunter_shoot_target = self._get_hunter_shoot_target(
            context=context,
            seat=banished,
        )

        # Badge transfer: only if Sheriff
        badge_transfer_to = self._get_badge_transfer(
            context=context,
            seat=banished,
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

    def _generate_last_words(
        self,
        context: "PhaseContext",
        seat: int,
    ) -> str:
        """Generate last words for a banished player.

        Last words are ALWAYS required for banishment (unlike night deaths
        where only Night 1 gets last words).

        Args:
            context: Game state
            seat: Banished player seat

        Returns:
            Last words string (always non-empty for banishment)
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

    def _get_hunter_shoot_target(
        self,
        context: "PhaseContext",
        seat: int,
    ) -> Optional[int]:
        """Get hunter shoot target if applicable.

        Hunter CAN shoot on banishment (unlike POISON death which prevents shooting).

        Args:
            context: Game state
            seat: Dead player seat (potential Hunter)

        Returns:
            Hunter shoot target (None = skipped or not applicable)
        """
        player = context.get_player(seat)
        if player is None:
            return None

        # Hunter can shoot on banishment
        if player.role != Role.HUNTER:
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

    def _get_badge_transfer(
        self,
        context: "PhaseContext",
        seat: int,
    ) -> Optional[int]:
        """Get badge transfer target if banished player is Sheriff.

        Args:
            context: Game state
            seat: Banished player seat (potential Sheriff)

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
    from src.werewolf.handlers.werewolf_handler import PhaseContext
