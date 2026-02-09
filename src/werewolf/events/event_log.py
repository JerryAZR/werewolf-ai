"""Chronological event log organized by game phase sequence."""

from datetime import datetime
from typing import Optional, Union, Annotated
from pydantic import BaseModel, Field, Discriminator, Tag, model_validator

from .game_events import (
    Phase,
    MicroPhase,
    GameStart,
    WerewolfKill,
    WitchAction,
    GuardAction,
    SeerAction,
    NightResolution,
    DeathAnnouncement,
    Speech,
    SheriffElection,
    SheriffOptOut,
    Vote,
    SheriffBadgeTransfer,
    VictoryCheck,
    GameOver,
)


# ============================================================================
# Night Sub-Phases (data containers)
# ============================================================================

class WerewolfActionSubPhase(BaseModel):
    """Werewolves choose a kill target."""

    micro_phase: MicroPhase = MicroPhase.WEREWOLF_ACTION
    kill: Optional[WerewolfKill] = None

    def __str__(self) -> str:
        if self.kill:
            if self.kill.target is None:
                return "WerewolfAction: no kill"
            return f"WerewolfAction: kill seat {self.kill.target}"
        return "WerewolfAction: pending"


class WitchActionSubPhase(BaseModel):
    """Witch chooses antidote/poison/pass."""

    micro_phase: MicroPhase = MicroPhase.WITCH_ACTION
    action: Optional[WitchAction] = None

    def __str__(self) -> str:
        if self.action:
            if self.action.action_type.value == "PASS":
                return "WitchAction: pass"
            target = f"seat {self.action.target}" if self.action.target else ""
            return f"WitchAction: {self.action.action_type.value} {target}"
        return "WitchAction: pending"


class GuardActionSubPhase(BaseModel):
    """Guard chooses a player to protect."""

    micro_phase: MicroPhase = MicroPhase.GUARD_ACTION
    action: Optional[GuardAction] = None

    def __str__(self) -> str:
        if self.action:
            if self.action.target is None:
                return "GuardAction: skip"
            return f"GuardAction: protect seat {self.action.target}"
        return "GuardAction: pending"


class SeerActionSubPhase(BaseModel):
    """Seer checks a player's identity."""

    micro_phase: MicroPhase = MicroPhase.SEER_ACTION
    action: Optional[SeerAction] = None

    def __str__(self) -> str:
        if self.action:
            return f"SeerAction: check seat {self.action.target} = {self.action.result.value}"
        return "SeerAction: pending"


class NightResolutionSubPhase(BaseModel):
    """Night deaths are calculated and resolved."""

    micro_phase: MicroPhase = MicroPhase.NIGHT_RESOLUTION
    resolution: Optional[NightResolution] = None

    def __str__(self) -> str:
        if self.resolution:
            deaths = self.resolution.deaths
            if not deaths:
                return "NightResolution: no deaths"
            return f"NightResolution: deaths = {deaths}"
        return "NightResolution: pending"


NightSubPhase = Annotated[
    Union[
        WerewolfActionSubPhase,
        WitchActionSubPhase,
        GuardActionSubPhase,
        SeerActionSubPhase,
        NightResolutionSubPhase,
    ],
    Tag("subphase"),
]


class NightPhase(BaseModel):
    """Night phase container.

    Night numbering rules:
    - night_number must be >= 1
    - Night 1 is the first night of the game
    - There is no Night 0
    """

    night_number: int
    phase: Phase = Phase.NIGHT
    subphases: list[NightSubPhase] = Field(default_factory=list)

    @model_validator(mode='after')
    def validate_night_number(self) -> "NightPhase":
        if self.night_number < 1:
            raise ValueError(f"night_number must be >= 1, got {self.night_number}")
        return self

    @property
    def deaths(self) -> list[int]:
        """Get deaths from night resolution."""
        for sp in self.subphases:
            if isinstance(sp, NightResolutionSubPhase) and sp.resolution:
                return sp.resolution.deaths
        return []

    def __str__(self) -> str:
        lines = [f"Night {self.night_number}:"]
        for sp in self.subphases:
            lines.append(f"  {sp}")
        if not self.subphases:
            lines.append("  (no actions)")
        return "\n".join(lines)


# ============================================================================
# Day Sub-Phases (data containers)
# ============================================================================

class CampaignSubPhase(BaseModel):
    """Day 1: Sheriff candidates give campaign speeches."""

    micro_phase: MicroPhase = MicroPhase.CAMPAIGN
    speeches: list[Speech] = Field(default_factory=list)

    def __str__(self) -> str:
        if not self.speeches:
            return "Campaign: no speeches"
        lines = ["Campaign:"]
        for speech in self.speeches:
            preview = speech.content[:50] + "..." if len(speech.content) > 50 else speech.content
            lines.append(f"  Seat {speech.actor}: \"{preview}\"")
        return "\n".join(lines)


class OptOutSubPhase(BaseModel):
    """Day 1: Candidates may drop out of the race."""

    micro_phase: MicroPhase = MicroPhase.OPT_OUT
    opt_outs: list[SheriffOptOut] = Field(default_factory=list)

    def __str__(self) -> str:
        if not self.opt_outs:
            return "OptOut: no one dropped out"
        players = [o.actor for o in self.opt_outs]
        return f"OptOut: dropped out = {players}"


class SheriffElectionSubPhase(BaseModel):
    """Day 1: Sheriff election voting."""

    micro_phase: MicroPhase = MicroPhase.SHERIFF_ELECTION
    election: Optional[SheriffElection] = None

    def __str__(self) -> str:
        if self.election:
            if self.election.winner is not None:
                return f"SheriffElection: winner = seat {self.election.winner}"
            return "SheriffElection: no winner - tie"
        return "SheriffElection: pending"


class DeathAnnouncementSubPhase(BaseModel):
    """Reveal who died during the night."""

    micro_phase: MicroPhase = MicroPhase.DEATH_ANNOUNCEMENT
    announcement: Optional[DeathAnnouncement] = None

    def __str__(self) -> str:
        if self.announcement:
            dead = self.announcement.dead_players
            if not dead:
                return "DeathAnnouncement: no deaths"
            return f"DeathAnnouncement: dead = {dead}"
        return "DeathAnnouncement: pending"


class LastWordsSubPhase(BaseModel):
    """Night death last words (Night 1 only)."""

    micro_phase: MicroPhase = MicroPhase.LAST_WORDS
    speeches: list[Speech] = Field(default_factory=list)

    def __str__(self) -> str:
        if not self.speeches:
            return "LastWords: no speeches"
        lines = ["LastWords:"]
        for speech in self.speeches:
            preview = speech.content[:50] + "..." if len(speech.content) > 50 else speech.content
            lines.append(f"  Seat {speech.actor}: \"{preview}\"")
        return "\n".join(lines)


class DiscussionSubPhase(BaseModel):
    """Players discuss and debate."""

    micro_phase: MicroPhase = MicroPhase.DISCUSSION
    speeches: list[Speech] = Field(default_factory=list)

    def __str__(self) -> str:
        if not self.speeches:
            return "Discussion: no speeches"
        lines = ["Discussion:"]
        for speech in self.speeches:
            preview = speech.content[:50] + "..." if len(speech.content) > 50 else speech.content
            lines.append(f"  Seat {speech.actor}: \"{preview}\"")
        return "\n".join(lines)


class VotingSubPhase(BaseModel):
    """Vote to banish a player."""

    micro_phase: MicroPhase = MicroPhase.VOTING
    votes: list[Vote] = Field(default_factory=list)

    def __str__(self) -> str:
        if not self.votes:
            return "Voting: no votes"
        counts: dict[Optional[int], int] = {}
        for vote in self.votes:
            counts[vote.target] = counts.get(vote.target, 0) + 1
        parts = []
        for target, count in sorted(counts.items(), key=lambda x: -x[1] if x[0] is not None else float('inf')):
            if target is None:
                parts.append(f"{count} abstain")
            else:
                voters = [v.actor for v in self.votes if v.target == target]
                parts.append(f"{count} for seat {target} ({voters})")
        return f"Voting: {', '.join(parts)}"


class BanishedLastWordsSubPhase(BaseModel):
    """Day death speaks before leaving."""

    micro_phase: MicroPhase = MicroPhase.BANNED_LAST_WORDS
    speech: Optional[Speech] = None

    def __str__(self) -> str:
        if self.speech:
            preview = self.speech.content[:30] + "..." if len(self.speech.content) > 30 else self.speech.content
            return f"BanishedLastWords: seat {self.speech.actor} - \"{preview}\""
        return "BanishedLastWords: no speech"


class VictoryCheckSubPhase(BaseModel):
    """Check if victory condition is met."""

    micro_phase: MicroPhase = MicroPhase.VICTORY_CHECK
    check: Optional[VictoryCheck] = None

    def __str__(self) -> str:
        if self.check:
            if self.check.is_game_over:
                return f"VictoryCheck: {self.check.winner} wins by {self.check.condition.value}"
            return "VictoryCheck: game continues"
        return "VictoryCheck: pending"


DaySubPhase = Annotated[
    Union[
        CampaignSubPhase,
        OptOutSubPhase,
        SheriffElectionSubPhase,
        DeathAnnouncementSubPhase,
        LastWordsSubPhase,
        DiscussionSubPhase,
        VotingSubPhase,
        BanishedLastWordsSubPhase,
        VictoryCheckSubPhase,
    ],
    Tag("subphase"),
]


class DayPhase(BaseModel):
    """Day phase container.

    Day numbering rules:
    - day_number must be >= 1
    - Day 1 is the first day of the game (after Night 1)
    - There is no Day 0
    """

    day_number: int
    phase: Phase = Phase.DAY
    subphases: list[DaySubPhase] = Field(default_factory=list)

    @model_validator(mode='after')
    def validate_day_number(self) -> "DayPhase":
        if self.day_number < 1:
            raise ValueError(f"day_number must be >= 1, got {self.day_number}")
        return self

    @property
    def is_day1(self) -> bool:
        """Check if this is Day 1."""
        return self.day_number == 1

    @property
    def all_speeches(self) -> list[Speech]:
        """Get all speeches in order."""
        speeches: list[Speech] = []
        for sp in self.subphases:
            if isinstance(sp, (CampaignSubPhase, LastWordsSubPhase, DiscussionSubPhase)):
                speeches.extend(sp.speeches)
        return speeches

    def __str__(self) -> str:
        lines = [f"Day {self.day_number}:"]
        for sp in self.subphases:
            lines.append(f"  {sp}")
        if not self.subphases:
            lines.append("  (no events)")
        return "\n".join(lines)


# ============================================================================
# Game Phase (discriminated union)
# ============================================================================

GamePhase = Annotated[
    Union[
        Annotated[NightPhase, Tag("night")],
        Annotated[DayPhase, Tag("day")],
    ],
    Discriminator(lambda x: "night" if x.phase == Phase.NIGHT else "day"),
]


# ============================================================================
# Full Game Event Log
# ============================================================================

try:
    import yaml
    _YAML_AVAILABLE = True
except ImportError:
    _YAML_AVAILABLE = False


class GameEventLog(BaseModel):
    """
    Chronological event log with events organized by time.

    Structure:
    - game_start: Initial setup
    - phases: Chronological sequence of NightPhase/DayPhase
    - game_over: Final result
    """

    game_id: str = Field(default_factory=lambda: datetime.now().strftime("%Y%m%d_%H%M%S"))
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    player_count: int
    roles_secret: dict[int, str] = Field(default_factory=dict)

    game_start: Optional[GameStart] = None
    phases: list[GamePhase] = Field(default_factory=list)
    game_over: Optional[GameOver] = None

    final_turn_count: int = 0
    metadata: dict = Field(default_factory=dict)

    def __str__(self) -> str:
        """Human-readable summary of the entire game."""
        lines = [f"Game {self.game_id} ({self.player_count} players)"]
        if self.game_start:
            lines.append(f"  Started: {self.game_start.player_count} players")

        for phase in self.phases:
            lines.append(f"  {phase}")

        if self.game_over:
            lines.append(f"  Game Over: {self.game_over.winner} wins by {self.game_over.condition.value}")

        return "\n".join(lines)

    def to_yaml(self, include_roles: bool = False) -> str:
        """Serialize the event log to YAML string."""
        if not _YAML_AVAILABLE:
            raise ImportError("PyYAML is required")

        data = self.model_dump(mode='python')

        if not include_roles:
            data["roles_secret"] = {}

        def convert_enums(obj):
            if isinstance(obj, dict):
                return {k: convert_enums(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_enums(item) for item in obj]
            elif hasattr(obj, 'value'):
                return obj.value
            return obj

        data = convert_enums(data)
        return yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)

    def save_to_file(self, filepath: str, include_roles: bool = False) -> None:
        """Serialize the event log to a YAML file."""
        yaml_content = self.to_yaml(include_roles=include_roles)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(yaml_content)

    @classmethod
    def load_from_file(cls, filepath: str) -> "GameEventLog":
        """Load an event log from a YAML file."""
        if not _YAML_AVAILABLE:
            raise ImportError("PyYAML is required")

        with open(filepath, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        # Handle phase deserialization with proper type conversion
        if "phases" in data and isinstance(data["phases"], list):
            phases = []
            for phase_data in data["phases"]:
                if isinstance(phase_data, dict):
                    if phase_data.get("phase") == "NIGHT":
                        phases.append(NightPhase.model_validate(phase_data))
                    elif phase_data.get("phase") == "DAY":
                        phases.append(DayPhase.model_validate(phase_data))
                    else:
                        phases.append(phase_data)
                else:
                    phases.append(phase_data)
            data["phases"] = phases

        return cls.model_validate(data)

    # =========================================================================
    # Phase Navigation
    # =========================================================================

    @property
    def current_night(self) -> int:
        """Get current night number (0 if no night yet)."""
        for phase in reversed(self.phases):
            if isinstance(phase, NightPhase):
                return phase.night_number
        return 0

    @property
    def current_day(self) -> int:
        """Get current day number (0 if no day yet)."""
        for phase in reversed(self.phases):
            if isinstance(phase, DayPhase):
                return phase.day_number
        return 0

    def get_night(self, night_number: int) -> Optional[NightPhase]:
        """Get a specific night phase."""
        for phase in self.phases:
            if isinstance(phase, NightPhase) and phase.night_number == night_number:
                return phase
        return None

    def get_day(self, day_number: int) -> Optional[DayPhase]:
        """Get a specific day phase."""
        for phase in self.phases:
            if isinstance(phase, DayPhase) and phase.day_number == day_number:
                return phase
        return None

    def add_phase(self, phase: GamePhase) -> None:
        """Add a phase to the log.

        Args:
            phase: NightPhase or DayPhase to add.

        Raises:
            ValueError: If a phase with the same number already exists.
        """
        if isinstance(phase, NightPhase):
            if self.get_night(phase.night_number) is not None:
                raise ValueError(f"Night {phase.night_number} already exists")
        elif isinstance(phase, DayPhase):
            if self.get_day(phase.day_number) is not None:
                raise ValueError(f"Day {phase.day_number} already exists")
        self.phases.append(phase)

    # =========================================================================
    # Query Methods
    # =========================================================================

    def get_all_deaths(self) -> list[int]:
        """Get all deaths throughout the game."""
        deaths: list[int] = []
        for phase in self.phases:
            if isinstance(phase, NightPhase):
                deaths.extend(phase.deaths)
        return deaths

    def get_all_speeches(self) -> list[tuple[int, str]]:
        """Get all speeches as (day_number, content) tuples."""
        result: list[tuple[int, str]] = []
        for phase in self.phases:
            if isinstance(phase, DayPhase):
                for speech in phase.all_speeches:
                    result.append((phase.day_number, speech.content))
        return result

    def get_sheriffs(self) -> dict[int, int]:
        """Get day_number -> sheriff seat mapping."""
        sheriffs: dict[int, int] = {}
        for phase in self.phases:
            if isinstance(phase, DayPhase) and phase.is_day1:
                for sp in phase.subphases:
                    if isinstance(sp, SheriffElectionSubPhase) and sp.election and sp.election.winner is not None:
                        sheriffs[phase.day_number] = sp.election.winner
                        break
        return sheriffs

    # =========================================================================
    # Serialization
    # =========================================================================

    def model_dump(self, **kwargs) -> dict:
        """Serialize with summary."""
        data = super().model_dump(**kwargs)
        nights = sum(1 for p in self.phases if isinstance(p, NightPhase))
        days = sum(1 for p in self.phases if isinstance(p, DayPhase))
        data["summary"] = {
            "total_nights": nights,
            "total_days": days,
            "total_speeches": sum(
                len(p.all_speeches) for p in self.phases if isinstance(p, DayPhase)
            ),
            "total_deaths": len(self.get_all_deaths()),
        }
        return data
