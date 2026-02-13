"""Night action storage for tracking persistent state across nights."""

from typing import Optional, Set
from pydantic import BaseModel


class NightActionSnapshot(BaseModel):
    """Persistent state snapshot for night actions.

    This captures only the persistent state that needs to be tracked
    across nights (potions used, previous guard target).
    """
    antidote_used: bool = False
    poison_used: bool = False
    guard_prev_target: Optional[int] = None
    # Seer checks are persistent - we track who has been checked
    seer_checks: set[int] = set()


class NightActionStore(BaseModel):
    """Tracks night actions and persistent potion/guard state.

    Persistent state (tracked across nights):
    - antidote_used: Whether witch's antidote has been used
    - poison_used: Whether witch's poison has been used
    - guard_prev_target: The player guarded previous night (for restriction)
    - seer_checks: Set of seats already checked by the seer

    Ephemeral state (cleared each night):
    - kill_target: Werewolves' chosen kill target
    - antidote_target: Witch's antidote target
    - poison_target: Witch's poison target
    - guard_target: Guard's chosen target
    """
    # Persistent (reset nightly but track usage)
    antidote_used: bool = False
    poison_used: bool = False
    guard_prev_target: Optional[int] = None
    # Seer checks are persistent - track all players the seer has checked
    seer_checks: set[int] = set()

    # Ephemeral (cleared each night)
    kill_target: Optional[int] = None
    antidote_target: Optional[int] = None
    poison_target: Optional[int] = None
    guard_target: Optional[int] = None

    def snapshot(self) -> NightActionSnapshot:
        """Create a snapshot of persistent state for next night.

        Returns:
            NightActionSnapshot containing antidote_used, poison_used,
            guard_prev_target, and seer_checks.
        """
        return NightActionSnapshot(
            antidote_used=self.antidote_used,
            poison_used=self.poison_used,
            guard_prev_target=self.guard_prev_target,
            seer_checks=self.seer_checks.copy(),
        )

    @classmethod
    def from_snapshot(cls, snapshot: NightActionSnapshot) -> "NightActionStore":
        """Create a new NightActionStore from a previous night's snapshot.

        Args:
            snapshot: The snapshot from the previous night.

        Returns:
            A new NightActionStore with persistent state from the snapshot
            and all ephemeral targets set to None.
        """
        return cls(
            antidote_used=snapshot.antidote_used,
            poison_used=snapshot.poison_used,
            guard_prev_target=snapshot.guard_prev_target,
            seer_checks=snapshot.seer_checks.copy(),
        )

    def reset_for_new_night(self) -> None:
        """Reset ephemeral targets for a new night.

        Clears all action targets (kill, antidote, poison, guard) but
        preserves the persistent state (antidote_used, poison_used,
        guard_prev_target).
        """
        self.kill_target = None
        self.antidote_target = None
        self.poison_target = None
        self.guard_target = None
