"""Events package."""

from werewolf.events.game_events import (
    # Base
    GameEvent,
    CharacterAction,
    TargetAction,
    # Enums
    Phase,
    MicroPhase,
    DeathCause,
    WitchActionType,
    SeerResult,
    VictoryCondition,
    # Non-Character Events
    GameStart,
    DeathAnnouncement,
    SheriffElection,
    Banishment,
    SheriffBadgeTransfer,
    NightResolution,
    # Character Actions
    WitchAction,
    SeerAction,
    Speech,
    SheriffOptOut,
    Vote,
    DeathResolution,
    WerewolfKill,
    GuardAction,
    HunterShoot,
    # Victory (TBD)
    VictoryCheck,
    GameOver,
)

__all__ = [
    # Base
    "GameEvent",
    "CharacterAction",
    "TargetAction",
    # Enums
    "Phase",
    "MicroPhase",
    "DeathCause",
    "WitchActionType",
    "SeerResult",
    "VictoryCondition",
    # Non-Character Events
    "GameStart",
    "DeathAnnouncement",
    "SheriffElection",
    "Banishment",
    "SheriffBadgeTransfer",
    "NightResolution",
    # Character Actions
    "WitchAction",
    "SeerAction",
    "Speech",
    "SheriffOptOut",
    "Vote",
    "DeathResolution",
    "WerewolfKill",
    "GuardAction",
    "HunterShoot",
    # Victory (TBD)
    "VictoryCheck",
    "GameOver",
]
