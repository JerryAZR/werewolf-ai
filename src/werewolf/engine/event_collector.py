"""EventCollector - accumulates events from handlers into unified event log."""

from typing import Callable, Optional

from werewolf.events import (
    GameEvent,
    SubPhaseLog,
    SubPhase,
    GameEventLog,
    PhaseLog,
    Phase,
)


class EventCollector:
    """Collects events from all handlers into a unified event log.

    The collector manages the hierarchy:
    - GameEventLog (top-level)
      - PhaseLog (NIGHT/DAY phases)
        - SubPhaseLog (micro-phases like WEREWOLF_ACTION, VOTING)
          - GameEvent (individual events)

    Usage:
        collector = EventCollector(day=1)
        collector.create_phase_log(Phase.NIGHT)
        collector.add_event(werewolf_kill)
        collector.add_event(witch_action)
        event_log = collector.get_event_log()

    The collector supports an optional callback that fires after each event:
        collector = EventCollector(day=1, on_event=my_callback)
    """

    def __init__(
        self,
        day: int = 0,
        on_event: Optional[Callable[[GameEvent], None]] = None,
    ):
        """Initialize the EventCollector.

        Args:
            day: Current day number (defaults to 0 before game starts).
            on_event: Optional callback fired after each event is added.
                       Callback receives the GameEvent as argument.
        """
        self._day = day
        self._event_log = GameEventLog(player_count=0)  # Will be set when game starts
        self._current_phase: Phase | None = None
        self._current_phase_log: PhaseLog | None = None
        self._current_subphase: SubPhase | None = None
        self._current_subphase_log: SubPhaseLog | None = None
        self._on_event = on_event

    @property
    def day(self) -> int:
        """Get current day number."""
        return self._day

    @day.setter
    def day(self, value: int) -> None:
        """Set current day number."""
        self._day = value

    def create_phase_log(self, phase: Phase) -> None:
        """Create a new PhaseLog when phase changes.

        This finalizes the current phase (if any) and starts a new one.

        Args:
            phase: The new phase (NIGHT or DAY).
        """
        # Finalize current subphase if exists
        self._finalize_subphase()

        # Finalize current phase if exists
        self._finalize_phase()

        # Start new phase
        self._current_phase = phase
        if phase == Phase.NIGHT:
            phase_number = self._day if self._day > 0 else 1
        else:  # DAY
            phase_number = self._day if self._day > 0 else 1

        self._current_phase_log = PhaseLog(number=phase_number, kind=phase)
        self._event_log.phases.append(self._current_phase_log)

    def _finalize_subphase(self) -> None:
        """Finalize the current subphase (if any) to PhaseLog.

        Only adds if not already added (to avoid duplicates).
        """
        if self._current_subphase_log is not None and self._current_phase_log is not None:
            # Check if this subphase log is already in the phase's subphases
            if self._current_subphase_log not in self._current_phase_log.subphases:
                self._current_phase_log.subphases.append(self._current_subphase_log)
            self._current_subphase_log = None
            self._current_subphase = None

    def _add_subphase_to_phase(self, subphase_log: SubPhaseLog) -> None:
        """Add a subphase log to the current phase immediately.

        Args:
            subphase_log: The SubPhaseLog to add.
        """
        if self._current_phase_log is not None:
            self._current_phase_log.subphases.append(subphase_log)

    def _finalize_phase(self) -> None:
        """Finalize the current phase to event log."""
        # Subphase should already be finalized, but just in case
        self._finalize_subphase()
        self._current_phase_log = None
        self._current_phase = None

    def add_event(self, event: GameEvent) -> None:
        """Add an event to the current phase's subphase log.

        Args:
            event: The GameEvent to add.

        Raises:
            RuntimeError: If no phase has been created yet.
        """
        if self._current_phase_log is None:
            raise RuntimeError("No phase has been created. Call create_phase_log() first.")

        # Update event's day if not set
        if event.day == 0:
            event.day = self._day

        # Determine subphase from event if not set
        subphase = event.micro_phase
        if subphase is None:
            # Default subphase based on phase type
            subphase = SubPhase.NIGHT_RESOLUTION if self._current_phase == Phase.NIGHT else SubPhase.VOTING

        # Start new subphase if different from current
        if self._current_subphase != subphase:
            self._current_subphase = subphase
            self._current_subphase_log = SubPhaseLog(micro_phase=subphase)
            # Immediately add to phase so events are visible
            self._add_subphase_to_phase(self._current_subphase_log)

        # Add event to current subphase log
        if self._current_subphase_log is not None:
            self._current_subphase_log.events.append(event)

        # Fire callback if registered
        if self._on_event is not None:
            self._on_event(event)

    def add_subphase_log(self, log: SubPhaseLog) -> None:
        """Merge a complete SubPhaseLog into the current phase.

        Args:
            log: The SubPhaseLog to add.

        Raises:
            RuntimeError: If no phase has been created yet.
        """
        if self._current_phase_log is None:
            raise RuntimeError("No phase has been created. Call create_phase_log() first.")

        # Update day for all events in the log
        for event in log.events:
            if event.day == 0:
                event.day = self._day

            # Fire callback for each event in the subphase log
            if self._on_event is not None:
                self._on_event(event)

        # Add the subphase log to current phase
        self._current_phase_log.subphases.append(log)

    def get_event_log(self) -> GameEventLog:
        """Get the complete GameEventLog with all phases.

        Returns:
            The complete GameEventLog containing all collected events.
        """
        # Finalize any pending subphase
        self._finalize_subphase()
        return self._event_log

    def get_events(self) -> list[GameEvent]:
        """Get a flat list of all GameEvents in chronological order.

        Returns:
            List of all GameEvents collected.
        """
        events: list[GameEvent] = []
        for phase in self._event_log.phases:
            for subphase in phase.subphases:
                events.extend(subphase.events)
        return events

    def set_player_count(self, count: int) -> None:
        """Set the player count for the event log.

        Args:
            count: Number of players in the game.
        """
        self._event_log.player_count = count

    def set_game_start(self, game_start: "GameStart") -> None:
        """Set the game start event.

        Args:
            game_start: The GameStart event.
        """
        self._event_log.game_start = game_start
        # Also populate roles_secret on the event log for formatting
        self._event_log.roles_secret = game_start.roles_secret.copy()

    def set_game_over(self, game_over: "GameOver") -> None:
        """Set the game over event.

        Args:
            game_over: The GameOver event.
        """
        self._event_log.game_over = game_over
