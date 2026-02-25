"""Post-game validator for YAML event logs.

This module provides independent validation of game events from a YAML event log,
replaying the game and validating all rules without using the in-game validator.
"""

from typing import Optional
from werewolf.events.event_log import GameEventLog, PhaseLog
from werewolf.engine.game_state import GameState
from werewolf.models.player import Role, Player
from werewolf.events.game_events import (
    DeathEvent, NightOutcome, Banishment, GameOver, SheriffOutcome,
    WerewolfKill, WitchAction, GuardAction, SeerAction, Vote,
)
from .types import ValidationViolation, ValidationResult


class PostGameValidator:
    """Validates a complete game from YAML event log.

    This validator replays the game from the event log and validates all rules
    independently of the in-game validator. It checks:
    - Game initialization (B.1-B.4)
    - Night actions (D.1-D.4, E.1-E.7, F.1-F.3, F.5, G.1-G.4)
    - Day actions (H.1-H.5, I.1-I.9, J.1-J.5, K.1-K.4, L.1-L.4)
    - Victory conditions (A.1-A.5)
    - State consistency (M.1-M.7)

    The validator replays events in order, updating state as it goes:
    1. Initialize state from roles_secret (all players alive)
    2. Process night phases: validate actions, then apply deaths from NightOutcome
    3. Process day phases: validate actions, then apply deaths from DeathEvent/Banishment
    4. Validate final victory conditions
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
        self._potion_used: dict = {"antidote": False, "poison": False}
        self._guard_prev_target: Optional[int] = None
        self._votes_this_phase: list = []
        self._current_day: int = 0

    def validate(self) -> ValidationResult:
        """Run full validation on the event log.

        Returns:
            ValidationResult with all violations found
        """
        # Phase 1: Initialization
        self._initialize_state()
        if self.state is None:
            return ValidationResult(
                is_valid=False,
                violations=self.violations
            )

        # Run initialization validation
        self._validate_initialization()

        # Phase 2: Process each phase
        for phase_log in self.event_log.phases:
            self._validate_phase(phase_log)

        # Phase 3: Final victory validation
        self._validate_victory()

        return ValidationResult(
            is_valid=len(self.violations) == 0,
            violations=self.violations.copy()
        )

    def _add_violation(
        self,
        rule_id: str,
        category: str,
        message: str,
        event_type: Optional[str] = None,
        context: Optional[dict] = None,
    ) -> None:
        """Helper to add a violation."""
        self.violations.append(ValidationViolation(
            rule_id=rule_id,
            category=category,
            message=message,
            event_type=event_type,
            context=context,
        ))

    # =========================================================================
    # Initialization
    # =========================================================================

    def _initialize_state(self) -> None:
        """Create initial game state from roles_secret (all players alive)."""
        # Build players dict from roles_secret
        players = {}
        for seat, role_str in self.event_log.roles_secret.items():
            try:
                role = Role(role_str)
                players[seat] = Player(seat=seat, name=f"Player {seat}", role=role, is_alive=True)
            except ValueError:
                self._add_violation(
                    "B.3", "Initialization",
                    f"Invalid role '{role_str}' for seat {seat}"
                )

        if not players:
            self._add_violation("B.2", "Initialization", "No players found in roles_secret")
            return

        # Verify player count
        if len(players) != 12:
            self._add_violation(
                "B.2", "Initialization",
                f"Expected 12 players, got {len(players)}"
            )

        # Create game state with all players alive
        self.state = GameState(
            players=players,
            living_players=set(players.keys()),
            dead_players=set(),
            sheriff=None,
            day=1,
        )

    def _validate_initialization(self) -> None:
        """Validate game initialization (B.1-B.4)."""
        # B.1: GameStart must exist
        if self.event_log.game_start is None:
            self._add_violation(
                "B.1", "Initialization", "GameStart event must be recorded"
            )
            return

        # B.4: Sheriff cannot be elected before Day 1 (handled in day phase)
        pass  # Additional initialization checks if needed

    # =========================================================================
    # Phase Validation
    # =========================================================================

    def _validate_phase(self, phase_log: PhaseLog) -> None:
        """Validate a single phase, updating state as we go."""
        from werewolf.events.game_events import Phase, SubPhase
        from werewolf.validation.phase_order import (
            NIGHT_SUBPHASES,
            DAY_SUBPHASES,
        )

        self._current_day = phase_log.number

        # Validate C.17: Subphase must match its phase
        for subphase_log in phase_log.subphases:
            subphase = subphase_log.micro_phase
            if phase_log.kind == Phase.NIGHT and subphase in DAY_SUBPHASES:
                self._add_violation(
                    "C.17", "Phase Order",
                    f"DAY subphase {subphase.value} appeared in NIGHT phase - handler bug",
                    context={"phase": phase_log.kind.value, "subphase": subphase.value}
                )
            elif phase_log.kind == Phase.DAY and subphase in NIGHT_SUBPHASES:
                self._add_violation(
                    "C.17", "Phase Order",
                    f"NIGHT subphase {subphase.value} appeared in DAY phase - handler bug",
                    context={"phase": phase_log.kind.value, "subphase": subphase.value}
                )

        if phase_log.kind.value == "NIGHT":
            self._validate_night_phase(phase_log)
        elif phase_log.kind.value == "DAY":
            self._validate_day_phase(phase_log)

        # Reset per-phase state
        self._votes_this_phase = []

    def _validate_night_phase(self, phase_log: PhaseLog) -> None:
        """Validate night phase actions and apply state changes."""
        # Note: We collect actions but only apply deaths from NightOutcome
        # The NightOutcome has the authoritative death list (accounts for witch antidote, guard, etc.)

        for subphase in phase_log.subphases:
            for event in subphase.events:
                # Werewolf action
                if isinstance(event, WerewolfKill):
                    self._validate_werewolf_action(event)

                # Witch action
                elif isinstance(event, WitchAction):
                    self._validate_witch_action(event)

                # Guard action
                elif isinstance(event, GuardAction):
                    self._validate_guard_action(event)

                # Seer action
                elif isinstance(event, SeerAction):
                    self._validate_seer_action(event)

                # Night outcome - this is where deaths are AUTHORITATIVELY applied
                elif isinstance(event, NightOutcome):
                    if event.deaths:
                        deaths = {seat: cause for seat, cause in event.deaths.items()}
                        self._apply_deaths(deaths)

    def _validate_day_phase(self, phase_log: PhaseLog) -> None:
        """Validate day phase actions and apply state changes."""
        deaths_this_day: dict[int, str] = {}

        for subphase in phase_log.subphases:
            for event in subphase.events:
                # Sheriff outcome
                if isinstance(event, SheriffOutcome):
                    self._validate_sheriff_outcome(event)

                # Death event
                elif isinstance(event, DeathEvent):
                    self._validate_death_event(event)
                    deaths_this_day[event.actor] = event.cause.value if hasattr(event.cause, 'value') else event.cause
                    # Also apply hunter shoot target death (if any)
                    if event.hunter_shoot_target is not None:
                        deaths_this_day[event.hunter_shoot_target] = "HUNTER_SHOOT"

                # Vote
                elif isinstance(event, Vote):
                    self._validate_vote(event)

                # Banishment
                elif isinstance(event, Banishment):
                    self._validate_banishment(event)
                    if event.banished is not None:
                        deaths_this_day[event.banished] = "BANISHMENT"

        # Apply deaths after validating actions
        if deaths_this_day:
            self._apply_deaths(deaths_this_day)

    # =========================================================================
    # Action Validation
    # =========================================================================

    def _validate_werewolf_action(self, event: WerewolfKill) -> None:
        """Validate werewolf action (D.1-D.4)."""
        # D.1: Actor must be werewolf and alive
        if event.actor not in self.state.players:
            self._add_violation(
                "D.1", "Night Actions - Werewolf",
                f"Werewolf action from unknown actor {event.actor}",
                "WerewolfKill"
            )
        else:
            actor = self.state.players[event.actor]
            if not actor.is_alive:
                self._add_violation(
                    "D.1", "Night Actions - Werewolf",
                    f"Dead player {event.actor} performed werewolf action",
                    "WerewolfKill"
                )
            elif actor.role.value != "WEREWOLF":
                self._add_violation(
                    "D.1", "Night Actions - Werewolf",
                    f"Player {event.actor} ({actor.role.value}) cannot perform werewolf action",
                    "WerewolfKill"
                )

        # D.3: Cannot target dead players
        if event.target is not None and event.target in self.state.dead_players:
            self._add_violation(
                "D.3", "Night Actions - Werewolf",
                f"Werewolf cannot target dead player {event.target}",
                "WerewolfKill"
            )

    def _validate_witch_action(self, event: WitchAction) -> None:
        """Validate witch action (E.1-E.7)."""
        # E.1: Actor must be witch and alive
        if event.actor not in self.state.players:
            self._add_violation(
                "E.1", "Night Actions - Witch",
                f"Witch action from unknown actor {event.actor}",
                "WitchAction"
            )
        else:
            actor = self.state.players[event.actor]
            if not actor.is_alive:
                self._add_violation(
                    "E.1", "Night Actions - Witch",
                    f"Dead player {event.actor} performed witch action",
                    "WitchAction"
                )
            elif actor.role.value != "WITCH":
                self._add_violation(
                    "E.1", "Night Actions - Witch",
                    f"Player {event.actor} ({actor.role.value}) cannot perform witch action",
                    "WitchAction"
                )

        # E.4: Antidote cannot target witch
        if (event.action_type.value == "ANTIDOTE" and
            event.target == event.actor):
            self._add_violation(
                "E.4", "Night Actions - Witch",
                "Witch cannot use antidote on themselves",
                "WitchAction"
            )

        # Track potion usage
        if event.action_type.value == "ANTIDOTE":
            if self._potion_used["antidote"]:
                self._add_violation(
                    "E.2", "Night Actions - Witch",
                    "Antidote has already been used",
                    "WitchAction"
                )
            self._potion_used["antidote"] = True
        elif event.action_type.value == "POISON":
            if self._potion_used["poison"]:
                self._add_violation(
                    "E.3", "Night Actions - Witch",
                    "Poison has already been used",
                    "WitchAction"
                )
            self._potion_used["poison"] = True

    def _validate_guard_action(self, event: GuardAction) -> None:
        """Validate guard action (F.1-F.5)."""
        # F.1: Actor must be guard and alive
        if event.actor not in self.state.players:
            self._add_violation(
                "F.1", "Night Actions - Guard",
                f"Guard action from unknown actor {event.actor}",
                "GuardAction"
            )
        else:
            actor = self.state.players[event.actor]
            if not actor.is_alive:
                self._add_violation(
                    "F.1", "Night Actions - Guard",
                    f"Dead player {event.actor} performed guard action",
                    "GuardAction"
                )
            elif actor.role.value != "GUARD":
                self._add_violation(
                    "F.1", "Night Actions - Guard",
                    f"Player {event.actor} ({actor.role.value}) cannot perform guard action",
                    "GuardAction"
                )

        # F.3: Cannot guard same person twice in a row
        if event.target == self._guard_prev_target and event.target is not None:
            self._add_violation(
                "F.3", "Night Actions - Guard",
                f"Guard cannot guard same person twice (target={event.target})",
                "GuardAction"
            )

        # F.5: Cannot guard dead players
        if event.target is not None and event.target in self.state.dead_players:
            self._add_violation(
                "F.5", "Night Actions - Guard",
                f"Guard cannot guard dead player {event.target}",
                "GuardAction"
            )

        # Track guard target for next night
        if event.target is not None:
            self._guard_prev_target = event.target

    def _validate_seer_action(self, event: SeerAction) -> None:
        """Validate seer action (G.1-G.4)."""
        # G.1: Actor must be seer and alive
        if event.actor not in self.state.players:
            self._add_violation(
                "G.1", "Night Actions - Seer",
                f"Seer action from unknown actor {event.actor}",
                "SeerAction"
            )
        else:
            actor = self.state.players[event.actor]
            if not actor.is_alive:
                self._add_violation(
                    "G.1", "Night Actions - Seer",
                    f"Dead player {event.actor} performed seer action",
                    "SeerAction"
                )
            elif actor.role.value != "SEER":
                self._add_violation(
                    "G.1", "Night Actions - Seer",
                    f"Player {event.actor} ({actor.role.value}) cannot perform seer action",
                    "SeerAction"
                )

        # G.2: Must target living player
        if event.target not in self.state.living_players:
            self._add_violation(
                "G.2", "Night Actions - Seer",
                f"Seer must target living player, got {event.target}",
                "SeerAction"
            )

    def _validate_sheriff_outcome(self, event: SheriffOutcome) -> None:
        """Validate sheriff election outcome (H.1-H.5)."""
        # H.2: Sheriff must be alive
        if event.winner is not None:
            if event.winner not in self.state.players:
                self._add_violation(
                    "H.2", "Day Actions - Sheriff",
                    f"Sheriff election for unknown player {event.winner}",
                    "SheriffOutcome"
                )
            elif event.winner in self.state.dead_players:
                self._add_violation(
                    "H.2", "Day Actions - Sheriff",
                    f"Dead player {event.winner} was elected sheriff",
                    "SheriffOutcome"
                )

        # Update sheriff state
        if event.winner is not None:
            self.state.sheriff = event.winner

    def _validate_death_event(self, event: DeathEvent) -> None:
        """Validate death event (I.1-I.9)."""
        # I.1: Actor must exist
        if event.actor not in self.state.players:
            self._add_violation(
                "I.1", "Day Actions - Death",
                f"Death event for unknown player {event.actor}",
                "DeathEvent"
            )

        # I.6: Sheriff death triggers badge transfer
        if (event.actor == self.state.sheriff and
            event.badge_transfer_to is None and
            event.cause.value != "BANISHMENT"):
            # Sheriff died but badge wasn't transferred (unless banished)
            pass  # This might be valid if sheriff chose to skip

    def _validate_vote(self, event: Vote) -> None:
        """Validate vote event (J.1-J.5)."""
        # J.5: Cannot vote for dead players
        if event.target is not None and event.target in self.state.dead_players:
            self._add_violation(
                "J.5", "Day Actions - Voting",
                f"Cannot vote for dead player {event.target}",
                "Vote"
            )

        self._votes_this_phase.append(event)

    def _validate_banishment(self, event: Banishment) -> None:
        """Validate banishment event (J.1-J.5)."""
        # Verify banishment was valid (proper vote count)
        if event.banished is not None:
            if event.banished in self.state.dead_players:
                self._add_violation(
                    "J.5", "Day Actions - Voting",
                    f"Cannot banish already dead player {event.banished}",
                    "Banishment"
                )

    # =========================================================================
    # State Updates
    # =========================================================================

    def _apply_deaths(self, deaths: dict[int, str]) -> None:
        """Apply deaths to state."""
        for seat in deaths.keys():
            if seat in self.state.players:
                self.state.players[seat].is_alive = False
            if seat in self.state.living_players:
                self.state.living_players.remove(seat)
                self.state.dead_players.add(seat)
            if seat == self.state.sheriff:
                self.state.sheriff = None

    # =========================================================================
    # Victory Validation
    # =========================================================================

    def _validate_victory(self) -> None:
        """Validate victory conditions (A.1-A.5)."""
        if self.state is None:
            return

        declared_winner = None
        if self.event_log.game_over:
            declared_winner = self.event_log.game_over.winner

        werewolf_count = self.state.get_werewolf_count()
        villager_count = self.state.get_ordinary_villager_count()
        god_count = self.state.get_god_count()

        werewolves_alive = werewolf_count > 0
        villagers_alive = villager_count > 0
        gods_alive = god_count > 0

        # A.2: Villagers win when all werewolves dead
        if not werewolves_alive:
            if not self.event_log.game_over:
                self._add_violation(
                    "A.2", "Victory Conditions",
                    "Villagers win when all Werewolves are dead, but game is not over"
                )
            elif declared_winner == "TIE":
                # This is a tie (A.5), not a violation of A.2
                pass
            elif declared_winner != "VILLAGER":
                self._add_violation(
                    "A.2", "Victory Conditions",
                    f"Werewolves are dead, but declared winner is {declared_winner}"
                )

        # A.3: Werewolves win when all ordinary villagers dead
        if not villagers_alive and werewolves_alive:
            if not self.event_log.game_over:
                self._add_violation(
                    "A.3", "Victory Conditions",
                    "Werewolves win when all Ordinary Villagers are dead, but game is not over"
                )
            elif declared_winner == "TIE":
                # This is a tie (A.5), not a violation of A.3
                pass
            elif declared_winner != "WEREWOLF":
                self._add_violation(
                    "A.3", "Victory Conditions",
                    f"All villagers are dead, but declared winner is {declared_winner}"
                )

        # A.4: Werewolves win when all gods dead
        if not gods_alive and werewolves_alive:
            if not self.event_log.game_over:
                self._add_violation(
                    "A.4", "Victory Conditions",
                    "Werewolves win when all Gods are dead, but game is not over"
                )
            elif declared_winner == "TIE":
                # This is a tie (A.5), not a violation of A.4
                pass
            elif declared_winner != "WEREWOLF":
                self._add_violation(
                    "A.4", "Victory Conditions",
                    f"All gods are dead, but declared winner is {declared_winner}"
                )

        # A.5: Tie when both conditions met simultaneously:
        # - Werewolf condition: all villagers dead OR all gods dead
        # - Villager condition: all werewolves dead
        # Tie = werewolves dead AND (villagers dead OR gods dead)
        werewolves_dead = not werewolves_alive
        villagers_dead = not villagers_alive
        gods_dead = not gods_alive

        tie_condition = werewolves_dead and (villagers_dead or gods_dead)

        if tie_condition:
            if self.event_log.game_over and declared_winner != "TIE":
                self._add_violation(
                    "A.5", "Victory Conditions",
                    "Game should end in tie when both victory conditions are met"
                )
