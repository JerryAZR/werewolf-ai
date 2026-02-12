"""Post-game validator for YAML event logs.

This module provides independent validation of game events from a YAML event log,
replaying the game and validating all rules without using the in-game validator.
"""

from typing import Optional
from werewolf.events.event_log import GameEventLog, PhaseLog
from werewolf.engine.game_state import GameState
from werewolf.models.player import Role, Player, STANDARD_12_PLAYER_CONFIG
from .types import ValidationViolation, ValidationResult


class PostGameValidator:
    """Validates a complete game from YAML event log.

    This validator replays the game from the event log and validates all rules
    independently of the in-game validator. It checks:
    - Game initialization (B.1-B.4)
    - Night actions (D.1-D.5, E.1-E.7, F.1-F.5, G.1-G.4)
    - Day actions (H.1-H.5, I.1-I.9, J.1-J.5, K.1-K.4, L.1-L.4)
    - Victory conditions (A.1-A.5)
    - State consistency (M.1-M.7)
    """

    def __init__(self, event_log: GameEventLog):
        """Initialize validator with an event log.

        Args:
            event_log: The game event log to validate
        """
        self.event_log = event_log
        self.state: Optional[GameState] = None
        self.violations: list[ValidationViolation] = []

        # Transient state for validation
        self._night_actions: dict = {}  # Track night actions per night
        self._potion_used: dict = {"antidote": False, "poison": False}
        self._guard_prev_target: Optional[int] = None
        self._votes_this_phase: list = []
        self._current_day: int = 0
        self._current_phase: str = ""

    def validate(self) -> ValidationResult:
        """Run full validation on the event log.

        Returns:
            ValidationResult with all violations found
        """
        # Phase 1: Initialization
        self._validate_initialization()
        if self.state is None:
            # Can't continue without valid initialization
            return ValidationResult(
                is_valid=False,
                violations=self.violations
            )

        # Phase 2: Process each phase
        for phase_log in self.event_log.phases:
            self._validate_phase(phase_log)

        # Phase 3: Final victory validation
        self._validate_victory()

        return ValidationResult(
            is_valid=len(self.violations) == 0,
            violations=self.violations.copy()
        )

    # =========================================================================
    # Initialization
    # =========================================================================

    def _validate_initialization(self) -> None:
        """Validate game initialization (B.1-B.4).

        To be implemented by validators/initialization.py
        """
        from werewolf.post_game_validator.validators.initialization import (
            validate_initialization,
        )
        violations = validate_initialization(
            self.event_log, self.state, self.violations
        )
        if violations:
            self.violations.extend(violations)

        # If validation passed, initialize state
        if self.state is None:
            self._initialize_state()

    def _initialize_state(self) -> None:
        """Create initial game state from GameStart event."""
        if self.event_log.game_start is None:
            return

        # Build players dict from roles_secret
        players = {}
        for seat, role_str in self.event_log.roles_secret.items():
            try:
                role = Role(role_str)
                players[seat] = Player(seat=seat, role=role, is_alive=True)
            except ValueError:
                # Invalid role, will be caught by initialization validation
                pass

        # Create game state with all players alive
        living_players = set(players.keys())
        dead_players: set[int] = set()

        self.state = GameState(
            players=players,
            living_players=living_players,
            dead_players=dead_players,
            sheriff=None,
            day=1,
        )

    # =========================================================================
    # Phase Validation
    # =========================================================================

    def _validate_phase(self, phase_log: PhaseLog) -> None:
        """Validate a single phase.

        Args:
            phase_log: The phase log to validate
        """
        self._current_day = phase_log.number
        self._current_phase = phase_log.kind.value

        if phase_log.kind.value == "NIGHT":
            self._validate_night_phase(phase_log)
        elif phase_log.kind.value == "DAY":
            self._validate_day_phase(phase_log)

        # Reset per-phase state
        self._votes_this_phase = []

    def _validate_night_phase(self, phase_log: PhaseLog) -> None:
        """Validate night phase actions.

        To be implemented by validators/night.py
        """
        from werewolf.post_game_validator.validators.night import (
            validate_night_phase,
        )
        violations = validate_night_phase(
            phase_log, self.state, self.violations, self._night_actions,
            self._potion_used, self._guard_prev_target, self._current_day
        )
        if violations:
            self.violations.extend(violations)

    def _validate_day_phase(self, phase_log: PhaseLog) -> None:
        """Validate day phase actions.

        To be implemented by validators/day.py
        """
        from werewolf.post_game_validator.validators.day import (
            validate_day_phase,
        )
        violations = validate_day_phase(
            phase_log, self.state, self.violations, self._votes_this_phase,
            self._current_day
        )
        if violations:
            self.violations.extend(violations)

    # =========================================================================
    # Victory Validation
    # =========================================================================

    def _validate_victory(self) -> None:
        """Validate victory conditions (A.1-A.5).

        To be implemented by validators/victory.py
        """
        from werewolf.post_game_validator.validators.victory import (
            validate_victory,
        )
        declared_winner = None
        if self.event_log.game_over:
            declared_winner = self.event_log.game_over.winner

        violations = validate_victory(
            self.state, declared_winner, self.event_log.game_over is not None
        )
        if violations:
            self.violations.extend(violations)

    # =========================================================================
    # State Consistency (called throughout)
    # =========================================================================

    def _validate_state_consistency(self) -> None:
        """Validate state consistency (M.1-M.7).

        Can be called after state updates to check invariants.
        """
        from werewolf.post_game_validator.validators.state import (
            validate_state_consistency,
        )
        violations = validate_state_consistency(self.state, self.violations)
        if violations:
            self.violations.extend(violations)
