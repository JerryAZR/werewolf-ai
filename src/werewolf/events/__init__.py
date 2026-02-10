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
    SheriffOutcome,
    Banishment,
    NightOutcome,
    VictoryOutcome,
    GameOver,
    # Character Actions
    WitchAction,
    SeerAction,
    Speech,
    SheriffOptOut,
    Vote,
    DeathEvent,
    WerewolfKill,
    GuardAction,
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
    "SheriffOutcome",
    "Banishment",
    "NightOutcome",
    "VictoryOutcome",
    "GameOver",
    # Character Actions
    "WitchAction",
    "SeerAction",
    "Speech",
    "SheriffOptOut",
    "Vote",
    "DeathEvent",
    "WerewolfKill",
    "GuardAction",
    # Logs
    "GameEventLog",
    "PhaseLog",
    "SubPhaseLog",
]
