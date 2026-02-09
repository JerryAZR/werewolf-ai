"""Chronological event log organized by game phase sequence."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, model_validator

from .game_events import (
    Phase,
    MicroPhase,
    GameEvent,
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
# Night Sub-Phases
# ============================================================================

class WerewolfActionSubPhase(BaseModel):
    """Werewolves choose a kill target."""

    night_number: int
    micro_phase: MicroPhase = MicroPhase.WEREWOLF_ACTION
    kill: Optional[WerewolfKill] = None

    def __str__(self) -> str:
        if self.kill:
            if self.kill.target is None:
                return f"WerewolfAction: no kill"
            return f"WerewolfAction: kill seat {self.kill.target}"
        return f"WerewolfAction: pending"


class WitchActionSubPhase(BaseModel):
    """Witch chooses antidote/poison/pass."""

    night_number: int
    micro_phase: MicroPhase = MicroPhase.WITCH_ACTION
    action: Optional[WitchAction] = None

    def __str__(self) -> str:
        if self.action:
            if self.action.action_type.value == "PASS":
                return f"WitchAction: pass"
            target = f"seat {self.action.target}" if self.action.target else ""
            return f"WitchAction: {self.action.action_type.value} {target}"
        return f"WitchAction: pending"


class GuardActionSubPhase(BaseModel):
    """Guard chooses a player to protect."""

    night_number: int
    micro_phase: MicroPhase = MicroPhase.GUARD_ACTION
    action: Optional[GuardAction] = None

    def __str__(self) -> str:
        if self.action:
            if self.action.target is None:
                return f"GuardAction: skip"
            return f"GuardAction: protect seat {self.action.target}"
        return f"GuardAction: pending"


class SeerActionSubPhase(BaseModel):
    """Seer checks a player's identity."""

    night_number: int
    micro_phase: MicroPhase = MicroPhase.SEER_ACTION
    action: Optional[SeerAction] = None

    def __str__(self) -> str:
        if self.action:
            return f"SeerAction: check seat {self.action.target} = {self.action.result.value}"
        return f"SeerAction: pending"


class NightResolutionSubPhase(BaseModel):
    """Night deaths are calculated and resolved."""

    night_number: int
    micro_phase: MicroPhase = MicroPhase.NIGHT_RESOLUTION
    resolution: Optional[NightResolution] = None

    def __str__(self) -> str:
        if self.resolution:
            deaths = self.resolution.deaths
            if not deaths:
                return f"NightResolution: no deaths"
            return f"NightResolution: deaths = {deaths}"
        return f"NightResolution: pending"


class NightPhase(BaseModel):
    """Complete night phase with all sub-phases."""

    night_number: int
    phase: Phase = Phase.NIGHT
    werewolf_action: WerewolfActionSubPhase = Field(default_factory=lambda: WerewolfActionSubPhase(night_number=0))
    witch_action: WitchActionSubPhase = Field(default_factory=lambda: WitchActionSubPhase(night_number=0))
    guard_action: GuardActionSubPhase = Field(default_factory=lambda: GuardActionSubPhase(night_number=0))
    seer_action: SeerActionSubPhase = Field(default_factory=lambda: SeerActionSubPhase(night_number=0))
    night_resolution: NightResolutionSubPhase = Field(default_factory=lambda: NightResolutionSubPhase(night_number=0))

    @model_validator(mode="after")
    def propagate_night_number(self) -> "NightPhase":
        """Ensure all sub-phases have the correct night number."""
        self.werewolf_action.night_number = self.night_number
        self.witch_action.night_number = self.night_number
        self.guard_action.night_number = self.night_number
        self.seer_action.night_number = self.night_number
        self.night_resolution.night_number = self.night_number
        return self

    @property
    def deaths(self) -> list[int]:
        """Get deaths from night resolution."""
        if self.night_resolution.resolution:
            return self.night_resolution.resolution.deaths
        return []

    def __str__(self) -> str:
        lines = [f"Night {self.night_number}:"]
        lines.append(f"  {self.werewolf_action}")
        lines.append(f"  {self.witch_action}")
        lines.append(f"  {self.guard_action}")
        lines.append(f"  {self.seer_action}")
        lines.append(f"  {self.night_resolution}")
        return "\n".join(lines)


# ============================================================================
# Day Sub-Phases (Day 1)
# ============================================================================

class CampaignSubPhase(BaseModel):
    """Day 1: Sheriff candidates give campaign speeches."""

    day_number: int
    micro_phase: MicroPhase = MicroPhase.CAMPAIGN
    speeches: list[Speech] = Field(default_factory=list)

    def __str__(self) -> str:
        if not self.speeches:
            return f"Campaign: no speeches"

        lines = ["Campaign:"]
        for speech in self.speeches:
            preview = speech.content[:50] + "..." if len(speech.content) > 50 else speech.content
            lines.append(f"  Seat {speech.actor}: \"{preview}\"")
        return "\n".join(lines)


class OptOutSubPhase(BaseModel):
    """Day 1: Candidates may drop out of the race."""

    day_number: int
    micro_phase: MicroPhase = MicroPhase.OPT_OUT
    opt_outs: list[SheriffOptOut] = Field(default_factory=list)

    def __str__(self) -> str:
        if not self.opt_outs:
            return f"OptOut: no one dropped out"
        players = [o.actor for o in self.opt_outs]
        return f"OptOut: dropped out = {players}"


class SheriffElectionSubPhase(BaseModel):
    """Day 1: Sheriff election voting."""

    day_number: int
    micro_phase: MicroPhase = MicroPhase.SHERIFF_ELECTION
    election: Optional[SheriffElection] = None

    def __str__(self) -> str:
        if self.election:
            if self.election.winner is not None:
                return f"SheriffElection: winner = seat {self.election.winner}"
            return f"SheriffElection: no winner - tie"
        return f"SheriffElection: pending"


class DeathAnnouncementSubPhase(BaseModel):
    """Reveal who died during the night."""

    day_number: int
    micro_phase: MicroPhase = MicroPhase.DEATH_ANNOUNCEMENT
    announcement: Optional[DeathAnnouncement] = None

    def __str__(self) -> str:
        if self.announcement:
            dead = self.announcement.dead_players
            if not dead:
                return f"DeathAnnouncement: no deaths"
            return f"DeathAnnouncement: dead = {dead}"
        return f"DeathAnnouncement: pending"


class LastWordsSubPhase(BaseModel):
    """Night death last words (Night 1 only)."""

    day_number: int
    micro_phase: MicroPhase = MicroPhase.LAST_WORDS
    speeches: list[Speech] = Field(default_factory=list)

    def __str__(self) -> str:
        if not self.speeches:
            return f"LastWords: no speeches"

        lines = ["LastWords:"]
        for speech in self.speeches:
            preview = speech.content[:50] + "..." if len(speech.content) > 50 else speech.content
            lines.append(f"  Seat {speech.actor}: \"{preview}\"")
        return "\n".join(lines)


class DiscussionSubPhase(BaseModel):
    """Players discuss and debate."""

    day_number: int
    micro_phase: MicroPhase = MicroPhase.DISCUSSION
    speeches: list[Speech] = Field(default_factory=list)

    def __str__(self) -> str:
        if not self.speeches:
            return f"Discussion: no speeches"

        lines = ["Discussion:"]
        for speech in self.speeches:
            preview = speech.content[:50] + "..." if len(speech.content) > 50 else speech.content
            lines.append(f"  Seat {speech.actor}: \"{preview}\"")
        return "\n".join(lines)


class VotingSubPhase(BaseModel):
    """Vote to banish a player."""

    day_number: int
    micro_phase: MicroPhase = MicroPhase.VOTING
    votes: list[Vote] = Field(default_factory=list)

    def __str__(self) -> str:
        if not self.votes:
            return f"Voting: no votes"

        # Count votes by target
        counts: dict[Optional[int], int] = {}
        for vote in self.votes:
            counts[vote.target] = counts.get(vote.target, 0) + 1

        # Build breakdown string
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

    day_number: int
    micro_phase: MicroPhase = MicroPhase.BANNED_LAST_WORDS
    speech: Optional[Speech] = None

    def __str__(self) -> str:
        if self.speech:
            preview = self.speech.content[:30] + "..." if len(self.speech.content) > 30 else self.speech.content
            return f"BanishedLastWords: seat {self.speech.actor} - \"{preview}\""
        return f"BanishedLastWords: no speech"


class VictoryCheckSubPhase(BaseModel):
    """Check if victory condition is met."""

    day_number: int
    micro_phase: MicroPhase = MicroPhase.VICTORY_CHECK
    check: Optional[VictoryCheck] = None

    def __str__(self) -> str:
        if self.check:
            if self.check.is_game_over:
                return f"VictoryCheck: {self.check.winner} wins by {self.check.condition.value}"
            return f"VictoryCheck: game continues"
        return f"VictoryCheck: pending"


# ============================================================================
# Day Phase
# ============================================================================

class DayPhase(BaseModel):
    """Day phase with sub-phases (Day 1 has additional sub-phases)."""

    day_number: int
    phase: Phase = Phase.DAY
    campaign: Optional[CampaignSubPhase] = None
    opt_out: Optional[OptOutSubPhase] = None
    sheriff_election: Optional[SheriffElectionSubPhase] = None
    death_announcement: Optional[DeathAnnouncementSubPhase] = None
    last_words: Optional[LastWordsSubPhase] = None
    discussion: DiscussionSubPhase = Field(default_factory=lambda: DiscussionSubPhase(day_number=0))
    voting: VotingSubPhase = Field(default_factory=lambda: VotingSubPhase(day_number=0))
    banished_last_words: Optional[BanishedLastWordsSubPhase] = None
    victory_check: VictoryCheckSubPhase = Field(default_factory=lambda: VictoryCheckSubPhase(day_number=0))

    @classmethod
    def create(cls, day_number: int) -> "DayPhase":
        """Create a day phase for the given day number."""
        return cls(day_number=day_number)

    @property
    def is_day1(self) -> bool:
        """Check if this is Day 1."""
        return self.day_number == 1

    @property
    def all_speeches(self) -> list[Speech]:
        """Get all speeches in order."""
        speeches: list[Speech] = []
        if self.campaign:
            speeches.extend(self.campaign.speeches)
        if self.last_words:
            speeches.extend(self.last_words.speeches)
        speeches.extend(self.discussion.speeches)
        return speeches

    def __str__(self) -> str:
        lines = [f"Day {self.day_number}:"]
        if self.campaign:
            lines.append(f"  {self.campaign}")
        if self.opt_out:
            lines.append(f"  {self.opt_out}")
        if self.sheriff_election:
            lines.append(f"  {self.sheriff_election}")
        if self.death_announcement:
            lines.append(f"  {self.death_announcement}")
        if self.last_words:
            lines.append(f"  {self.last_words}")
        lines.append(f"  {self.discussion}")
        lines.append(f"  {self.voting}")
        if self.banished_last_words:
            lines.append(f"  {self.banished_last_words}")
        lines.append(f"  {self.victory_check}")
        return "\n".join(lines)


# ============================================================================
# Game Phase Union
# ============================================================================

class GamePhase(BaseModel):
    """A single phase in the game sequence (night or day)."""

    phase: Phase
    night_number: Optional[int] = None  # Set if Night
    day_number: Optional[int] = None    # Set if Day
    night: Optional[NightPhase] = None
    day: Optional[DayPhase] = None

    @classmethod
    def create_night(cls, night_number: int) -> "GamePhase":
        """Create a night phase."""
        return cls(
            phase=Phase.NIGHT,
            night_number=night_number,
            night=NightPhase(night_number=night_number),
        )

    @classmethod
    def create_day(cls, day_number: int) -> "GamePhase":
        """Create a day phase."""
        return cls(
            phase=Phase.DAY,
            day_number=day_number,
            day=DayPhase.create(day_number),
        )

    def __str__(self) -> str:
        if self.phase == Phase.NIGHT and self.night:
            return str(self.night)
        if self.phase == Phase.DAY and self.day:
            return str(self.day)
        return f"{self.phase.value}: pending"


# ============================================================================
# Full Game Event Log
# ============================================================================

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
    - phases: Chronological sequence of GamePhase (Night1 → Day1 → Night2 → Day2 → ...)
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
        """Serialize the event log to YAML string.

        Args:
            include_roles: If True, include secret role assignments (for debugging).
                          If False, roles are omitted from the output.
        """
        if not _YAML_AVAILABLE:
            raise ImportError("PyYAML is required for YAML serialization. Install it with: pip install pyyaml")

        # Serialize with enum values (not Python objects)
        data = self.model_dump(mode='python')

        # Optionally exclude secret roles from output
        if not include_roles:
            data["roles_secret"] = {}

        # Convert enum objects to their values recursively
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
        """Serialize the event log to a YAML file.

        Args:
            filepath: Path to write the YAML file.
            include_roles: If True, include secret role assignments (for debugging).
        """
        yaml_content = self.to_yaml(include_roles=include_roles)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(yaml_content)

    @classmethod
    def load_from_file(cls, filepath: str) -> "GameEventLog":
        """Load an event log from a YAML file.

        Args:
            filepath: Path to read the YAML file from.

        Returns:
            A new GameEventLog instance.
        """
        if not _YAML_AVAILABLE:
            raise ImportError("PyYAML is required for YAML deserialization. Install it with: pip install pyyaml")

        with open(filepath, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        return cls.model_validate(data)

    # =========================================================================
    # Phase Navigation
    # =========================================================================

    @property
    def current_night(self) -> int:
        """Get current night number (0 if no night yet)."""
        for phase in reversed(self.phases):
            if phase.phase == Phase.NIGHT and phase.night_number:
                return phase.night_number
        return 0

    @property
    def current_day(self) -> int:
        """Get current day number (0 if no day yet)."""
        for phase in reversed(self.phases):
            if phase.phase == Phase.DAY and phase.day_number:
                return phase.day_number
        return 0

    @property
    def is_night(self) -> bool:
        """Check if we're currently in a night phase."""
        return len(self.phases) > 0 and self.phases[-1].phase == Phase.NIGHT

    @property
    def is_day(self) -> bool:
        """Check if we're currently in a day phase."""
        return len(self.phases) > 0 and self.phases[-1].phase == Phase.DAY

    def get_current_phase(self) -> Optional[GamePhase]:
        """Get the most recent phase."""
        return self.phases[-1] if self.phases else None

    def start_night(self, night_number: int) -> GamePhase:
        """Start a new night phase."""
        phase = GamePhase.create_night(night_number)
        self.phases.append(phase)
        return phase

    def start_day(self, day_number: int) -> GamePhase:
        """Start a new day phase."""
        phase = GamePhase.create_day(day_number)
        self.phases.append(phase)
        return phase

    # =========================================================================
    # Add Events
    # =========================================================================

    def add_event(self, event: GameEvent) -> None:
        """Add any game event to the log."""
        if isinstance(event, GameStart):
            self.game_start = event
        elif isinstance(event, GameOver):
            self.game_over = event
        elif event.phase == Phase.NIGHT:
            self._add_night_event(event)
        elif event.phase == Phase.DAY:
            self._add_day_event(event)

    def _add_night_event(self, event: GameEvent) -> None:
        """Add a night event to the current or new night."""
        night_num = event.day  # Night 1, 2, etc.

        # Find or create the night phase
        current = self.get_current_phase()
        if current is None or current.night_number != night_num:
            self.start_night(night_num)

        phase = self.phases[-1]
        assert phase.night is not None

        if isinstance(event, WerewolfKill):
            phase.night.werewolf_action.kill = event
        elif isinstance(event, WitchAction):
            phase.night.witch_action.action = event
        elif isinstance(event, GuardAction):
            phase.night.guard_action.action = event
        elif isinstance(event, SeerAction):
            phase.night.seer_action.action = event
        elif isinstance(event, NightResolution):
            phase.night.night_resolution.resolution = event

    def _add_day_event(self, event: GameEvent) -> None:
        """Add a day event to the current or new day."""
        day_num = event.day  # Day 1, 2, etc.

        # Find or create the day phase
        current = self.get_current_phase()
        if current is None or current.day_number != day_num:
            self.start_day(day_num)

        phase = self.phases[-1]
        assert phase.day is not None
        day = phase.day

        if isinstance(event, Speech):
            if event.micro_phase == MicroPhase.CAMPAIGN:
                if day.campaign is None:
                    day.campaign = CampaignSubPhase(day_number=day_num)
                day.campaign.speeches.append(event)
            elif event.micro_phase == MicroPhase.LAST_WORDS:
                if day.last_words is None:
                    day.last_words = LastWordsSubPhase(day_number=day_num)
                day.last_words.speeches.append(event)
            elif event.micro_phase == MicroPhase.BANNED_LAST_WORDS:
                day.banished_last_words = BanishedLastWordsSubPhase(day_number=day_num, speech=event)
            else:
                day.discussion.speeches.append(event)
        elif isinstance(event, SheriffOptOut):
            if day.opt_out is None:
                day.opt_out = OptOutSubPhase(day_number=day_num)
            day.opt_out.opt_outs.append(event)
        elif isinstance(event, SheriffElection):
            if day.sheriff_election is None:
                day.sheriff_election = SheriffElectionSubPhase(day_number=day_num)
            day.sheriff_election.election = event
        elif isinstance(event, Vote):
            day.voting.votes.append(event)
        elif isinstance(event, DeathAnnouncement):
            if day.death_announcement is None:
                day.death_announcement = DeathAnnouncementSubPhase(day_number=day_num)
            day.death_announcement.announcement = event

    # =========================================================================
    # Query Methods
    # =========================================================================

    def get_night(self, night_number: int) -> Optional[NightPhase]:
        """Get a specific night phase."""
        for phase in self.phases:
            if phase.night and phase.night.night_number == night_number:
                return phase.night
        return None

    def get_day(self, day_number: int) -> Optional[DayPhase]:
        """Get a specific day phase."""
        for phase in self.phases:
            if phase.day and phase.day.day_number == day_number:
                return phase.day
        return None

    def get_all_deaths(self) -> list[int]:
        """Get all deaths throughout the game."""
        deaths: list[int] = []
        for phase in self.phases:
            if phase.night:
                deaths.extend(phase.night.deaths)
        return deaths

    def get_all_speeches(self) -> list[tuple[int, str]]:
        """Get all speeches as (day_number, content) tuples."""
        result: list[tuple[int, str]] = []
        for phase in self.phases:
            if phase.day:
                for speech in phase.day.all_speeches:
                    result.append((phase.day.day_number, speech.content))
        return result

    def get_sheriffs(self) -> dict[int, int]:
        """Get day_number -> sheriff seat mapping."""
        sheriffs: dict[int, int] = {}
        for phase in self.phases:
            if phase.day and phase.day.is_day1 and phase.day.sheriff_election:
                election = phase.day.sheriff_election.election
                if election and election.winner:
                    sheriffs[phase.day.day_number] = election.winner
        return sheriffs

    # =========================================================================
    # Serialization
    # =========================================================================

    def model_dump(self, **kwargs) -> dict:
        """Serialize with summary."""
        data = super().model_dump(**kwargs)
        nights = sum(1 for p in self.phases if p.phase == Phase.NIGHT)
        days = sum(1 for p in self.phases if p.phase == Phase.DAY)
        data["summary"] = {
            "total_nights": nights,
            "total_days": days,
            "total_speeches": sum(len(p.day.all_speeches) for p in self.phases if p.day),
            "total_deaths": len(self.get_all_deaths()),
        }
        return data
