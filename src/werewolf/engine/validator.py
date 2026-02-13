"""GameValidator - runtime validation hooks for game rules.

This module provides a Protocol for validating game state transitions
and rule compliance at runtime. Hooks can be injected at key points
in the game flow to catch violations early.

Usage:
    # In tests or development
    validator = CollectingValidator()
    game = WerewolfGame(players, participants, validator=validator)
    violations = validator.get_violations()

    # No overhead in production (validator=None)
    game = WerewolfGame(players, participants)  # Fast, no validation
"""

from typing import Protocol, Optional
from werewolf.engine import GameState, EventCollector
from werewolf.events import GameEvent, Phase, SubPhase


class GameValidator(Protocol):
    """Hooks for runtime validation at key game points.

    All methods are async and return nothing. Violations are collected
    internally and can be retrieved via get_violations().
    """

    async def on_game_start(
        self,
        state: GameState,
        collector: EventCollector,
    ) -> None:
        """Called when game starts. Validates initial state."""
        ...

    async def on_phase_start(
        self,
        phase: Phase,
        day: int,
        state: GameState,
    ) -> None:
        """Called at the start of each phase (night/day)."""
        ...

    async def on_phase_end(
        self,
        phase: Phase,
        day: int,
        state: GameState,
        collector: EventCollector,
    ) -> None:
        """Called at the end of each phase."""
        ...

    async def on_subphase_start(
        self,
        subphase: SubPhase,
        day: int,
        state: GameState,
    ) -> None:
        """Called at the start of each subphase."""
        ...

    async def on_subphase_end(
        self,
        subphase: SubPhase,
        day: int,
        phase: Phase,
        state: GameState,
        collector: EventCollector,
    ) -> None:
        """Called at the end of each subphase."""
        ...

    async def on_event_applied(
        self,
        event: GameEvent,
        state: GameState,
    ) -> None:
        """Called after each event is applied to state."""
        ...

    async def on_death_chain_complete(
        self,
        deaths: list[int],
        state: GameState,
    ) -> None:
        """Called when a death chain is fully resolved (includes hunter shots, badge transfer)."""
        ...

    async def on_victory_check(
        self,
        state: GameState,
        is_over: bool,
        winner: Optional[str],
    ) -> None:
        """Called when checking for game over conditions."""
        ...

    async def on_game_over(
        self,
        winner: str,
        state: GameState,
        collector: EventCollector,
    ) -> list:
        """Called when game ends. Returns all violations found."""
        ...


class NoOpValidator:
    """No-op validator for production use (zero overhead).

    This validator does nothing - all hooks are no-ops.
    Use this or pass None to avoid validation overhead.
    """

    async def on_game_start(
        self,
        state: GameState,
        collector: EventCollector,
    ) -> None:
        pass

    async def on_phase_start(
        self,
        phase: Phase,
        day: int,
        state: GameState,
    ) -> None:
        pass

    async def on_phase_end(
        self,
        phase: Phase,
        day: int,
        state: GameState,
        collector: EventCollector,
    ) -> None:
        pass

    async def on_subphase_start(
        self,
        subphase: SubPhase,
        day: int,
        state: GameState,
    ) -> None:
        pass

    async def on_subphase_end(
        self,
        subphase: SubPhase,
        day: int,
        phase: Phase,
        state: GameState,
        collector: EventCollector,
    ) -> None:
        pass

    async def on_event_applied(
        self,
        event: GameEvent,
        state: GameState,
    ) -> None:
        pass

    async def on_death_chain_complete(
        self,
        deaths: list[int],
        state: GameState,
    ) -> None:
        pass

    async def on_victory_check(
        self,
        state: GameState,
        is_over: bool,
        winner: Optional[str],
    ) -> None:
        pass

    async def on_game_over(
        self,
        winner: str,
        state: GameState,
        collector: EventCollector,
    ) -> list:
        return []


class CollectingValidator(NoOpValidator):
    """Validator that collects violations for later inspection.

    Use this in tests to verify game rules are being followed.

    All validation functions from src/werewolf/validation/ are composed here.
    Lazy imports are used to avoid circular imports.
    """

    def __init__(self):
        self._violations = []
        self._phase_history = []
        self._subphase_history = {}

    def get_violations(self):
        """Get all collected violations."""
        return list(self._violations)

    def clear(self):
        """Clear collected violations."""
        self._violations.clear()
        self._phase_history.clear()
        self._subphase_history.clear()

    async def on_game_start(
        self,
        state: GameState,
        collector: EventCollector,
    ) -> None:
        """Validate game initialization rules B.1-B.4."""
        from werewolf.validation import validate_game_start
        violations = validate_game_start(state)
        self._violations.extend(violations)

    async def on_phase_start(
        self,
        phase: Phase,
        day: int,
        state: GameState,
    ) -> None:
        """Validate phase ordering C.1-C.15."""
        from werewolf.validation import validate_phase_order
        previous = self._phase_history[-1] if self._phase_history else None
        violations = validate_phase_order(phase, previous, state)
        self._violations.extend(violations)
        self._phase_history.append(phase)

    async def on_phase_end(
        self,
        phase: Phase,
        day: int,
        state: GameState,
        collector: EventCollector,
    ) -> None:
        """Validate event logging N.1-N.6."""
        from werewolf.validation import validate_event_logging
        violations = validate_event_logging(collector, phase, day)
        self._violations.extend(violations)

    async def on_subphase_start(
        self,
        subphase: SubPhase,
        day: int,
        state: GameState,
    ) -> None:
        """Initialize subphase tracking for ordering validation."""
        # Note: subphase tracking is done in on_subphase_end with phase info
        # This method just exists for API compatibility

    async def on_subphase_end(
        self,
        subphase: SubPhase,
        day: int,
        phase: Phase,
        state: GameState,
        collector: EventCollector,
    ) -> None:
        """Validate and track subphase ordering."""
        from werewolf.validation import (
            validate_night_subphase_order,
            validate_day_subphase_order,
            validate_werewolf_single_query,
            validate_seer_result,
            validate_subphase_phase_match,
        )

        # C.17: Validate subphase matches its phase (catches handler bugs)
        violations = validate_subphase_phase_match(phase, subphase)
        self._violations.extend(violations)

        # Use (phase, day) as key to separate night and day subphase history
        key = (phase, day)
        completed = self._subphase_history.get(key, set())

        if phase == Phase.NIGHT:
            violations = validate_night_subphase_order(completed, subphase)
            self._violations.extend(violations)
        elif phase == Phase.DAY:
            violations = validate_day_subphase_order(
                completed, subphase, day,
                has_candidates=True,
                has_opted_out=True,
                has_sheriff_candidates=True,
            )
            self._violations.extend(violations)

        # C.16: WerewolfAction should make exactly one collective decision
        if subphase == SubPhase.WEREWOLF_ACTION:
            # Get events from the most recent subphase log
            event_log = collector.get_event_log()
            if event_log.phases:
                last_phase = event_log.phases[-1]
                if last_phase.subphases:
                    last_subphase = last_phase.subphases[-1]
                    if last_subphase.micro_phase == SubPhase.WEREWOLF_ACTION:
                        violations = validate_werewolf_single_query(last_subphase.events)
                        self._violations.extend(violations)

        # G.3: Seer result must match target's actual role
        if subphase == SubPhase.SEER_ACTION:
            event_log = collector.get_event_log()
            if event_log.phases:
                last_phase = event_log.phases[-1]
                if last_phase.subphases:
                    last_subphase = last_phase.subphases[-1]
                    if last_subphase.micro_phase == SubPhase.SEER_ACTION:
                        violations = validate_seer_result(last_subphase.events, state)
                        self._violations.extend(violations)

        # Track this subphase as completed AFTER validation
        if key not in self._subphase_history:
            self._subphase_history[key] = set()
        self._subphase_history[key].add(subphase)

    async def on_event_applied(
        self,
        event: GameEvent,
        state: GameState,
    ) -> None:
        """Validate event and state consistency."""
        from werewolf.validation import (
            validate_state_consistency,
            validate_werewolf_action,
            validate_witch_action,
            validate_guard_action,
            validate_seer_action,
            validate_vote,
            validate_banishment,
            validate_death_resolution,
            validate_badge_transfer,
            validate_sheriff_election,
            validate_hunter_banishment_shot,
        )

        # State consistency (M.1-M.7)
        violations = validate_state_consistency(state, event)
        self._violations.extend(violations)

        # Event-type specific validation
        from werewolf.events.game_events import (
            WerewolfKill,
            WitchAction,
            GuardAction,
            SeerAction,
            Vote,
            Banishment,
            DeathEvent,
            SheriffOutcome,
        )

        if isinstance(event, WerewolfKill):
            violations = validate_werewolf_action(event, state)
            self._violations.extend(violations)

        elif isinstance(event, WitchAction):
            # Would need antidote_used, poison_used from game state
            violations = validate_witch_action(event, state, False, False)
            self._violations.extend(violations)

        elif isinstance(event, GuardAction):
            # Would need prev_guard_target from game state
            violations = validate_guard_action(event, state, None)
            self._violations.extend(violations)

        elif isinstance(event, SeerAction):
            violations = validate_seer_action(event, state)
            self._violations.extend(violations)

        elif isinstance(event, Vote):
            violations = validate_vote(event, state)
            self._violations.extend(violations)

        elif isinstance(event, Banishment):
            violations = validate_banishment(event, state)
            self._violations.extend(violations)

        elif isinstance(event, DeathEvent):
            violations = validate_death_resolution(event, state)
            self._violations.extend(violations)
            violations = validate_badge_transfer(event, state)
            self._violations.extend(violations)
            violations = validate_hunter_banishment_shot(event, state)
            self._violations.extend(violations)

        elif isinstance(event, SheriffOutcome):
            violations = validate_sheriff_election(event, state)
            self._violations.extend(violations)

    async def on_death_chain_complete(
        self,
        deaths: list[int],
        state: GameState,
    ) -> None:
        """Validate death chain completion."""
        from werewolf.validation import validate_no_duplicate_sheriff
        violations = validate_no_duplicate_sheriff(state)
        self._violations.extend(violations)

    async def on_victory_check(
        self,
        state: GameState,
        is_over: bool,
        winner: Optional[str],
    ) -> None:
        """Check victory conditions."""
        # This returns the check result, not violations
        # Actual validation happens at game over
        pass

    async def on_game_over(
        self,
        winner: str,
        state: GameState,
        collector: EventCollector,
    ) -> list:
        """Return all collected violations at game end."""
        from werewolf.validation import (
            validate_no_duplicate_sheriff,
            validate_state_consistency,
            validate_victory,
        )

        # Validate sheriff state is consistent
        violations = validate_no_duplicate_sheriff(state)
        self._violations.extend(violations)

        # Final state consistency check
        violations = validate_state_consistency(state, None)
        self._violations.extend(violations)

        # Validate victory conditions (A.1-A.5)
        declared_winner = winner if winner else None
        violations = validate_victory(state, declared_winner, True)
        self._violations.extend(violations)

        return self._violations


def create_validator(collect: bool = False):
    """Factory function to create appropriate validator.

    Args:
        collect: If True, returns CollectingValidator for tests.
                 If False, returns NoOpValidator for production.

    Returns:
        A GameValidator implementation.
    """
    if collect:
        return CollectingValidator()
    return NoOpValidator()
