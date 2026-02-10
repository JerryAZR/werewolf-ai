"""GameValidator - runtime validation hooks for game rules.

This module provides a Protocol for validating game state transitions
and rule compliance at runtime. Hooks can be injected at key points
in the game flow to catch violations early.

Usage:
    # In tests or development
    validator = GameValidatorImpl()
    game = WerewolfGame(players, participants, validator=validator)
    violations = validator.get_violations()

    # No overhead in production (validator=None)
    game = WerewolfGame(players, participants)  # Fast, no validation
"""

from typing import Protocol, Optional, AsyncGenerator
from werewolf.engine import GameState, EventCollector
from werewolf.events import GameEvent, Phase, SubPhase


class ValidationError(Exception):
    """Raised when a game rule violation is detected."""
    pass


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
    ) -> list[str]:
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
    ) -> list[str]:
        return []


class CollectingValidator(NoOpValidator):
    """Validator that collects violations for later inspection.

    Use this in tests to verify game rules are being followed.
    """

    def __init__(self):
        self._violations: list[str] = []

    def get_violations(self) -> list[str]:
        """Get all collected violations."""
        return list(self._violations)

    def clear(self) -> None:
        """Clear collected violations."""
        self._violations.clear()

    async def on_event_applied(
        self,
        event: GameEvent,
        state: GameState,
    ) -> None:
        """Collect validation observations (placeholder for future implementation)."""
        # TODO: Implement actual validation rules
        pass

    async def on_death_chain_complete(
        self,
        deaths: list[int],
        state: GameState,
    ) -> None:
        """Collect validation observations (placeholder for future implementation)."""
        # TODO: Validate death chain rules
        pass

    async def on_game_over(
        self,
        winner: str,
        state: GameState,
        collector: EventCollector,
    ) -> list[str]:
        """Return collected violations."""
        return self.get_violations()


def create_validator(collect: bool = False) -> GameValidator:
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
