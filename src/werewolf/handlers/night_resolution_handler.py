"""NightResolution handler for the Werewolf AI game.

This handler computes night phase deaths based on all accumulated night actions:
werewolf kill, witch antidote/poison, and guard protection.

Death Calculation Logic:
1. Start with kill_target -> WEREWOLF_KILL
2. If antidote_target == kill_target: remove (target saved by witch)
3. If guard_target == kill_target: remove (target saved by guard)
4. If poison_target exists: add {poison_target: POISON}
5. Return deaths dict

Special Rules:
- Poison ignores guard protection (poison kills regardless of guard)
- Both antidote + guard on same target = still saved
- Guard can be poisoned and still save the werewolf target
- If poison_target == kill_target, poison wins (player dies from poison)
"""

from typing import Optional, Sequence
from pydantic import BaseModel, Field

from src.werewolf.events.game_events import (
    NightOutcome,
    DeathCause,
    Phase,
    SubPhase,
    GameEvent,
)
from src.werewolf.models.player import Player


# ============================================================================
# Night Actions Context (accumulated from all night subphases)
# ============================================================================


class NightActionAccumulator(BaseModel):
    """Accumulated night actions from all night subphases.

    This is passed to NightResolution to compute final deaths.

    Attributes:
        kill_target: Seat targeted by werewolves (None if no werewolves alive)
        antidote_target: Seat saved by witch's antidote (None if not used)
        poison_target: Seat killed by witch's poison (None if not used)
        guard_target: Seat protected by guard (None if not used)
        antidote_used: Whether witch's antidote has been used
        poison_used: Whether witch's poison has been used
    """

    kill_target: Optional[int] = None
    antidote_target: Optional[int] = None
    poison_target: Optional[int] = None
    guard_target: Optional[int] = None
    antidote_used: bool = False
    poison_used: bool = False


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
# Participant Protocol (not used - engine-only logic)
# ============================================================================


# NightResolution is engine-only logic, no participants needed


# ============================================================================
# Night Resolution Handler
# ============================================================================


class NightResolutionHandler:
    """Handler for NightResolution subphase.

    Responsibilities:
    1. Compute deaths from all accumulated night actions
    2. Apply special rules (poison ignores guard, antidote/guard both save)
    3. Return NightOutcome with deaths dict {seat: DeathCause}

    This is engine-only logic - no participants are consulted.
    """

    def __call__(
        self,
        context: "PhaseContext",
        night_actions: NightActionAccumulator,
    ) -> HandlerResult:
        """Execute the NightResolution subphase.

        Args:
            context: Game state with players, living/dead, sheriff
            night_actions: Accumulated night action data from all subphases

        Returns:
            HandlerResult with SubPhaseLog containing NightOutcome event
        """
        deaths = self._compute_deaths(night_actions)

        # Build debug info
        debug_info = self._build_debug_info(night_actions, deaths)

        outcome = NightOutcome(
            phase=Phase.NIGHT,
            micro_phase=SubPhase.NIGHT_RESOLUTION,
            day=context.day,
            deaths=deaths,
            debug_info=debug_info,
        )

        return HandlerResult(
            subphase_log=SubPhaseLog(
                micro_phase=SubPhase.NIGHT_RESOLUTION,
                events=[outcome],
            ),
            debug_info=debug_info,
        )

    def _compute_deaths(
        self,
        night_actions: NightActionAccumulator,
    ) -> dict[int, DeathCause]:
        """Compute deaths based on all night actions.

        Death Calculation Logic:
        1. Start with werewolf kill target -> WEREWOLF_KILL
        2. If antidote_target == kill_target: remove (target saved)
        3. If guard_target == kill_target: remove (target saved)
        4. If poison_target exists: add {poison_target: POISON}
        5. Return deaths dict

        Special Rules:
        - Poison IGNORES guard protection
        - Both antidote AND guard on same target = still saved
        - Guard can be poisoned and still save target
        - Poison same as werewolf target = poison wins

        Args:
            night_actions: Accumulated night actions

        Returns:
            Dict mapping seat -> DeathCause for all deaths this night
        """
        deaths: dict[int, DeathCause] = {}

        # Step 1: Start with werewolf kill target
        kill_target = night_actions.kill_target
        if kill_target is not None:
            deaths[kill_target] = DeathCause.WEREWOLF_KILL

        # Step 2: Check antidote (saves werewolf target if used correctly)
        antidote_target = night_actions.antidote_target
        if antidote_target is not None and kill_target is not None:
            if antidote_target == kill_target:
                # Antidote saves the werewolf target
                deaths.pop(kill_target, None)

        # Step 3: Check guard protection (also saves werewolf target)
        # Note: Guard can be poisoned and still save the werewolf target
        guard_target = night_actions.guard_target
        if guard_target is not None and kill_target is not None:
            if guard_target == kill_target:
                # Guard protects the werewolf target
                deaths.pop(kill_target, None)

        # Step 4: Add poison deaths (poison ignores guard protection)
        poison_target = night_actions.poison_target
        if poison_target is not None:
            deaths[poison_target] = DeathCause.POISON

        return deaths

    def _build_debug_info(
        self,
        night_actions: NightActionAccumulator,
        deaths: dict[int, DeathCause],
    ) -> str:
        """Build debug info string for the night resolution.

        Args:
            night_actions: Accumulated night actions
            deaths: Computed deaths

        Returns:
            Debug info string
        """
        parts = [
            f"kill_target={night_actions.kill_target}",
            f"antidote_target={night_actions.antidote_target}",
            f"poison_target={night_actions.poison_target}",
            f"guard_target={night_actions.guard_target}",
        ]

        if deaths:
            death_strs = [f"{seat}({cause.value})" for seat, cause in sorted(deaths.items())]
            parts.append(f"deaths={death_strs}")
        else:
            parts.append("deaths=[]")

        return ", ".join(parts)


# ============================================================================
# PhaseContext (imported from werewolf_handler for type hints)
# ============================================================================

# Import PhaseContext from werewolf_handler for type hints
# Using TYPE_CHECKING to avoid circular imports
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.werewolf.handlers.werewolf_handler import PhaseContext
