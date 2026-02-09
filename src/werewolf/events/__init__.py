"""Events package."""

from werewolf.events.game_events import (
    # Base
    GameEvent,
    CharacterAction,
    TargetAction,
    # Enums
    Phase,
    SubPhase,
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

from werewolf.events.event_log import (
    GameEventLog,
    PhaseLog,
    SubPhaseLog,
)

__all__ = [
    # Base
    "GameEvent",
    "CharacterAction",
    "TargetAction",
    # Enums
    "Phase",
    "SubPhase",
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
    # Logs
    "GameEventLog",
    "PhaseLog",
    "SubPhaseLog",
]
