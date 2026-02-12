"""Event types for game logging."""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class Phase(str, Enum):
    """Macro phases of the game."""

    NIGHT = "NIGHT"
    DAY = "DAY"
    GAME_OVER = "GAME_OVER"


class SubPhase(str, Enum):
    """Micro phases within NIGHT and DAY."""

    # Night micro-phases
    WEREWOLF_ACTION = "WEREWOLF_ACTION"
    WITCH_ACTION = "WITCH_ACTION"
    GUARD_ACTION = "GUARD_ACTION"
    SEER_ACTION = "SEER_ACTION"
    NIGHT_RESOLUTION = "NIGHT_RESOLUTION"

    # Day micro-phases
    NOMINATION = "NOMINATION"
    CAMPAIGN = "CAMPAIGN"
    OPT_OUT = "OPT_OUT"
    SHERIFF_ELECTION = "SHERIFF_ELECTION"
    DEATH_RESOLUTION = "DEATH_RESOLUTION"
    BANISHMENT_RESOLUTION = "BANISHMENT_RESOLUTION"
    DEATH_ANNOUNCEMENT = "DEATH_ANNOUNCEMENT"
    VICTORY_CHECK = "VICTORY_CHECK"
    DISCUSSION = "DISCUSSION"
    VOTING = "VOTING"


class DeathCause(str, Enum):
    """Cause of death."""

    WEREWOLF_KILL = "WEREWOLF_KILL"
    POISON = "POISON"
    BANISHMENT = "BANISHMENT"


class WitchActionType(str, Enum):
    """Types of witch actions."""

    ANTIDOTE = "ANTIDOTE"
    POISON = "POISON"
    PASS = "PASS"


class SeerResult(str, Enum):
    """Result of seer's vision."""

    GOOD = "GOOD"
    WEREWOLF = "WEREWOLF"


class VictoryCondition(str, Enum):
    """How the game was won."""

    ALL_WEREWOLVES_KILLED = "ALL_WEREWOLVES_KILLED"
    ALL_GODS_KILLED = "ALL_GODS_KILLED"
    ALL_VILLAGERS_KILLED = "ALL_VILLAGERS_KILLED"
    ALL_WEREWOLVES_BANISHED = "ALL_WEREWOLVES_BANISHED"


class GameEvent(BaseModel):
    """Base class for all game events."""

    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    day: int = 0
    phase: Phase
    micro_phase: Optional[SubPhase] = None
    debug_info: Optional[str] = None  # JSON string for AI auditing

    def __str__(self) -> str:
        """Human-readable representation."""
        return f"{self.__class__.__name__}(day={self.day}, phase={self.phase.value})"


# ============================================================================
# Character Actions (events with an actor)
# ============================================================================


class CharacterAction(GameEvent):
    """Base class for events with a character actor."""

    actor: int  # seat number of the acting player

    def __str__(self) -> str:
        return f"{self.__class__.__name__}(actor={self.actor}, day={self.day})"


class TargetAction(CharacterAction):
    """Action that selects a target player."""

    target: Optional[int] = None  # None = no action/pass

    def __str__(self) -> str:
        target_str = f", target={self.target}" if self.target is not None else ""
        return f"{self.__class__.__name__}(actor={self.actor}, day={self.day}{target_str})"


class WitchAction(CharacterAction):
    """Witch performs an action."""

    phase: Phase = Phase.NIGHT
    micro_phase: SubPhase = SubPhase.WITCH_ACTION
    action_type: WitchActionType  # ANTIDOTE, POISON, or PASS
    target: Optional[int] = None  # Target for antidote/poison, None for PASS

    def __str__(self) -> str:
        target_str = f", target={self.target}" if self.target is not None else ""
        return f"Witch(actor={self.actor}, action={self.action_type.value}{target_str})"


class SeerAction(CharacterAction):
    """Seer checks a player's identity."""

    phase: Phase = Phase.NIGHT
    micro_phase: SubPhase = SubPhase.SEER_ACTION
    target: int
    result: SeerResult

    def __str__(self) -> str:
        return f"Seer(actor={self.actor}, target={self.target}, result={self.result.value})"


class Speech(CharacterAction):
    """Player speech."""

    phase: Phase = Phase.DAY
    micro_phase: SubPhase  # CAMPAIGN or DISCUSSION
    content: str

    def __str__(self) -> str:
        preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"Speech(actor={self.actor}, {self.micro_phase.value}: \"{preview}\")"


class SheriffOptOut(CharacterAction):
    """A candidate drops out of the Sheriff race."""

    phase: Phase = Phase.DAY
    micro_phase: SubPhase = SubPhase.OPT_OUT

    def __str__(self) -> str:
        return f"SheriffOptOut(actor={self.actor})"


class SheriffNomination(CharacterAction):
    """Player decides to run for Sheriff or not during nomination phase."""

    phase: Phase = Phase.DAY
    micro_phase: SubPhase = SubPhase.NOMINATION
    running: bool  # True = running, False = not running

    def __str__(self) -> str:
        action = "running" if self.running else "not running"
        return f"SheriffNomination(actor={self.actor}, {action})"


class Vote(TargetAction):
    """A player casts their vote."""

    phase: Phase = Phase.DAY
    micro_phase: SubPhase = SubPhase.VOTING
    # target: Optional[int] = None  # Inherited from TargetAction, None = abstain

    def __str__(self) -> str:
        if self.target is None:
            return f"Vote(actor={self.actor}, abstain)"
        return f"Vote(actor={self.actor}, target={self.target})"


class DeathEvent(CharacterAction):
    """Single death with all associated actions.

    Created once per player death, containing:
    - Cause of death
    - Last words (if any)
    - Hunter shoot target (if hunter dies; None = skipped)
    - Badge transfer (if sheriff dies)
    """

    phase: Phase = Phase.DAY
    micro_phase: SubPhase = SubPhase.DEATH_RESOLUTION
    cause: DeathCause
    last_words: Optional[str] = None
    hunter_shoot_target: Optional[int] = None  # None = hunter skipped
    badge_transfer_to: Optional[int] = None

    def __str__(self) -> str:
        words = f", last_words=\"{self.last_words}\"" if self.last_words else ""
        hunter = f", hunter_shoot={self.hunter_shoot_target}" if self.hunter_shoot_target else ", hunter_skipped"
        badge = f", badge_to={self.badge_transfer_to}" if self.badge_transfer_to else ""
        return f"Death(actor={self.actor}, cause={self.cause.value}{words}{hunter}{badge})"


class WerewolfKill(TargetAction):
    """Werewolves choose a target to kill."""

    phase: Phase = Phase.NIGHT
    micro_phase: SubPhase = SubPhase.WEREWOLF_ACTION
    # actor can be any werewolf seat

    def __str__(self) -> str:
        if self.target is None:
            return f"WerewolfKill(no kill)"
        return f"WerewolfKill(target={self.target})"


class GuardAction(TargetAction):
    """Guard protects a player."""

    phase: Phase = Phase.NIGHT
    micro_phase: SubPhase = SubPhase.GUARD_ACTION
    # target: Optional[int] = None  # Inherited from TargetAction, may skip

    def __str__(self) -> str:
        if self.target is None:
            return f"GuardAction(skip)"
        return f"GuardAction(target={self.target})"


# ============================================================================
# Non-Character Events (aggregate results, announcements, etc.)
# ============================================================================


class GameStart(GameEvent):
    """Game has started with player assignments."""

    day: int = 0
    phase: Phase = Phase.NIGHT
    player_count: int
    roles_secret: dict[int, str] = Field(default_factory=dict)  # seat -> role

    def __str__(self) -> str:
        return f"GameStart({self.player_count} players)"


class DeathAnnouncement(GameEvent):
    """Announcement of who died during the night."""

    phase: Phase = Phase.DAY
    micro_phase: SubPhase = SubPhase.DEATH_ANNOUNCEMENT
    dead_players: list[int] = Field(default_factory=list)  # Ordered by seat
    death_count: int = 0

    def __str__(self) -> str:
        return f"DeathAnnouncement({self.dead_players})"


class SheriffOutcome(GameEvent):
    """Sheriff election voting results."""

    phase: Phase = Phase.DAY
    micro_phase: SubPhase = SubPhase.SHERIFF_ELECTION
    candidates: list[int] = Field(default_factory=list)  # seats
    votes: dict[int, float] = Field(default_factory=dict)  # seat -> vote count (Sheriff = 1.5)
    winner: Optional[int] = None

    def __str__(self) -> str:
        return f"SheriffOutcome(winner={self.winner})"


class Banishment(GameEvent):
    """Voting has resulted in a banishment."""

    phase: Phase = Phase.DAY
    micro_phase: SubPhase = SubPhase.VOTING
    votes: dict[int, float] = Field(default_factory=dict)  # target -> vote count
    tied_players: list[int] = Field(default_factory=list)  # Empty if no tie; if non-empty, no banishment occurs
    banished: Optional[int] = None

    def __str__(self) -> str:
        return f"Banishment(banished={self.banished})"


class NightOutcome(GameEvent):
    """Night phase has resolved with all deaths calculated."""

    phase: Phase = Phase.NIGHT
    micro_phase: SubPhase = SubPhase.NIGHT_RESOLUTION
    deaths: dict[int, DeathCause] = Field(default_factory=dict)  # seat -> cause

    def __str__(self) -> str:
        if not self.deaths:
            return "NightOutcome(no deaths)"
        death_strs = [f"{seat}({cause.value})" for seat, cause in sorted(self.deaths.items())]
        return f"NightOutcome(deaths={death_strs})"


# ============================================================================
# Victory Events (TBD - discuss later)
# ============================================================================


class VictoryOutcome(GameEvent):
    """Victory condition check."""

    is_game_over: bool = False
    winner: Optional[str] = None  # "WEREWOLF" or "VILLAGER"
    condition: Optional[VictoryCondition] = None

    def __str__(self) -> str:
        if self.is_game_over:
            return f"VictoryOutcome({self.winner} wins by {self.condition.value})"
        return f"VictoryOutcome(ongoing)"


class GameOver(GameEvent):
    """Game has ended."""

    phase: Phase = Phase.GAME_OVER
    winner: str  # "WEREWOLF" or "VILLAGER"
    condition: VictoryCondition
    final_turn_count: int

    def __str__(self) -> str:
        return f"GameOver({self.winner} wins by {self.condition.value}, turns={self.final_turn_count})"
