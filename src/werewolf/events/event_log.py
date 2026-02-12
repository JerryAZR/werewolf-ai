"""Chronological event log organized by game phase sequence."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, model_validator

from .game_events import (
    Phase,
    SubPhase,
    GameStart,
    NightOutcome,
    Speech,
    SheriffOutcome,
    GameOver,
    GameEvent,
)
from .event_formatter import EventFormatter


# ============================================================================
# SubPhaseLog Container
# ============================================================================

class SubPhaseLog(BaseModel):
    """Generic subphase container with events.

    A subphase represents a micro-phase within a night or day phase,
    containing zero or more game events.
    """

    micro_phase: SubPhase
    events: list[GameEvent] = Field(default_factory=list)

    def describe(self, roles_secret: Optional[dict[int, str]] = None) -> str:
        """Format subphase log as string with optional role context.

        Args:
            roles_secret: Optional dict mapping seat to role for formatted output.
                         If None, uses default event __str__.
        """
        if not self.events:
            return self.micro_phase.name

        if roles_secret:
            formatter = EventFormatter(roles_secret)
            lines = [f"{self.micro_phase.name}"]
            for event in self.events:
                lines.append(f"    {formatter.format(event)}")
            return "\n".join(lines)
        else:
            lines = [f"{self.micro_phase.name}"]
            for event in self.events:
                lines.append(f"    {event}")
            return "\n".join(lines)

    def __str__(self) -> str:
        """Default string representation without role context."""
        return self.describe()

    def __repr__(self) -> str:
        return self.__str__()


# ============================================================================
# Unified Phase
# ============================================================================

class PhaseLog(BaseModel):
    """Unified container for both night and day phases.

    Phase numbering rules:
    - number must be >= 1
    - Night 1 is the first night, Day 1 is the first day
    - There is no Night 0 or Day 0
    """

    number: int
    kind: Phase  # NIGHT or DAY
    subphases: list[SubPhaseLog] = Field(default_factory=list)

    @model_validator(mode='after')
    def validate_number(self) -> "PhaseLog":
        if self.number < 1:
            raise ValueError(f"number must be >= 1, got {self.number}")
        return self

    def describe(self, roles_secret: Optional[dict[int, str]] = None) -> str:
        """Format phase log as string with optional role context.

        Args:
            roles_secret: Optional dict mapping seat to role for formatted output.
                         If None, uses default event __str__.
        """
        header = f"=== {self.kind.name} {self.number} ==="

        if not self.subphases:
            return f"{header}\n  (no events)"

        lines = [header]
        for i, sp in enumerate(self.subphases):
            if i > 0:
                lines.append("")  # Blank line between subphases
            # Use type().describe() to avoid Pydantic __getattr__ issues
            sp_lines = SubPhaseLog.describe(sp, roles_secret).split("\n")
            for line in sp_lines:
                lines.append(f"  {line}")
        return "\n".join(lines)

    def __str__(self) -> str:
        """Default string representation without role context."""
        return self.describe()


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
    - phases: Chronological sequence of Phase
    - game_over: Final result
    """

    game_id: str = Field(default_factory=lambda: datetime.now().strftime("%Y%m%d_%H%M%S"))
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    player_count: int
    roles_secret: dict[int, str] = Field(default_factory=dict)

    game_start: Optional[GameStart] = None
    phases: list[PhaseLog] = Field(default_factory=list)
    game_over: Optional[GameOver] = None

    final_turn_count: int = 0
    metadata: dict = Field(default_factory=dict)

    def __str__(self) -> str:
        """Human-readable summary of the entire game with role context."""
        # Create formatter with role information
        formatter = EventFormatter(self.roles_secret)

        lines = [f"Game {self.game_id} ({self.player_count} players)"]
        if self.game_start:
            lines.append(f"  Started: {self.game_start.player_count} players")

        for i, phase in enumerate(self.phases):
            if i > 0:
                lines.append("")  # Blank line between phases
            # Pass roles_secret to phase for formatted output
            phase_lines = PhaseLog.describe(phase, self.roles_secret).split("\n")
            lines.extend(phase_lines)

        if self.game_over:
            lines.append("")
            game_over_str = formatter.format(self.game_over)
            lines.append(f"  {game_over_str}")

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

        # Handle phase deserialization
        if "phases" in data and isinstance(data["phases"], list):
            phases = []
            for phase_data in data["phases"]:
                if isinstance(phase_data, dict):
                    phases.append(PhaseLog.model_validate(phase_data))
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
            if phase.kind == Phase.NIGHT:
                return phase.number
        return 0

    @property
    def current_day(self) -> int:
        """Get current day number (0 if no day yet)."""
        for phase in reversed(self.phases):
            if phase.kind == Phase.DAY:
                return phase.number
        return 0

    def get_night(self, night_number: int) -> Optional[PhaseLog]:
        """Get a specific night phase."""
        for phase in self.phases:
            if phase.kind == Phase.NIGHT and phase.number == night_number:
                return phase
        return None

    def get_day(self, day_number: int) -> Optional[PhaseLog]:
        """Get a specific day phase."""
        for phase in self.phases:
            if phase.kind == Phase.DAY and phase.number == day_number:
                return phase
        return None

    def add_phase(self, phase: PhaseLog) -> None:
        """Add a phase to the log.

        Args:
            phase: PhaseLog to add.

        Raises:
            ValueError: If a phase with the same number and kind already exists.
        """
        if phase.kind == Phase.NIGHT:
            if self.get_night(phase.number) is not None:
                raise ValueError(f"Night {phase.number} already exists")
        else:
            if self.get_day(phase.number) is not None:
                raise ValueError(f"Day {phase.number} already exists")
        self.phases.append(phase)

    # =========================================================================
    # Query Methods
    # =========================================================================

    def _get_deaths_from_phase(self, phase: PhaseLog) -> list[int]:
        """Get deaths from a night phase."""
        if phase.kind != Phase.NIGHT:
            return []
        for sp in phase.subphases:
            if sp.micro_phase == SubPhase.NIGHT_RESOLUTION and sp.events:
                resolution = sp.events[0]
                if isinstance(resolution, NightOutcome):
                    return resolution.deaths
        return []

    def _get_speeches_from_phase(self, phase: PhaseLog) -> list[Speech]:
        """Get all speeches from a day phase."""
        if phase.kind != Phase.DAY:
            return []
        speeches: list[Speech] = []
        for sp in phase.subphases:
            for event in sp.events:
                if isinstance(event, Speech):
                    speeches.append(event)
        return speeches

    def get_all_deaths(self) -> list[int]:
        """Get all deaths throughout the game."""
        deaths: list[int] = []
        for phase in self.phases:
            deaths.extend(self._get_deaths_from_phase(phase))
        return deaths

    def get_all_speeches(self) -> list[tuple[int, str]]:
        """Get all speeches as (day_number, content) tuples."""
        result: list[tuple[int, str]] = []
        for phase in self.phases:
            for speech in self._get_speeches_from_phase(phase):
                result.append((phase.number, speech.content))
        return result

    def get_sheriffs(self) -> dict[int, int]:
        """Get day_number -> sheriff seat mapping."""
        sheriffs: dict[int, int] = {}
        for phase in self.phases:
            if phase.kind == Phase.DAY and phase.number == 1:
                for sp in phase.subphases:
                    if sp.micro_phase == SubPhase.SHERIFF_ELECTION and sp.events:
                        election = sp.events[0]
                        if isinstance(election, SheriffOutcome) and election.winner is not None:
                            sheriffs[phase.number] = election.winner
                            break
        return sheriffs

    # =========================================================================
    # Serialization
    # =========================================================================

    def model_dump(self, **kwargs) -> dict:
        """Serialize with summary."""
        data = super().model_dump(**kwargs)
        nights = sum(1 for p in self.phases if p.kind == Phase.NIGHT)
        days = sum(1 for p in self.phases if p.kind == Phase.DAY)
        data["summary"] = {
            "total_nights": nights,
            "total_days": days,
            "total_speeches": sum(
                len(self._get_speeches_from_phase(p)) for p in self.phases
            ),
            "total_deaths": len(self.get_all_deaths()),
        }
        return data
