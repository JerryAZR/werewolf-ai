"""Voting Validators (J.1-J.2).

Rules:
- J.1: Vote target must be a living player
- J.2: Tie vote must result in no banishment
"""

from typing import Optional
from werewolf.engine.game_state import GameState
from werewolf.events.game_events import Vote, Banishment
from .types import ValidationViolation, ValidationSeverity


def validate_vote(
    event: Vote,
    state: GameState,
) -> list[ValidationViolation]:
    """Validate vote rules J.1.

    Args:
        event: Vote event
        state: Game state

    Returns:
        List of validation violations (empty if valid)
    """
    violations: list[ValidationViolation] = []

    # J.1: Vote target must be living
    if event.target is not None:
        if event.target not in state.living_players:
            violations.append(ValidationViolation(
                rule_id="J.1",
                category="Voting",
                message=f"Vote target {event.target} is not alive",
                severity=ValidationSeverity.ERROR,
                context={"target": event.target, "actor": event.actor}
            ))

        # Voter must be alive
        if event.actor not in state.living_players:
            violations.append(ValidationViolation(
                rule_id="J.1",
                category="Voting",
                message=f"Dead player {event.actor} cannot vote",
                severity=ValidationSeverity.ERROR,
                context={"actor": event.actor}
            ))

    return violations


def validate_banishment(
    event: Banishment,
    state: GameState,
) -> list[ValidationViolation]:
    """Validate banishment rules J.2.

    Args:
        event: Banishment event
        state: Game state

    Returns:
        List of validation violations (empty if valid)
    """
    violations: list[ValidationViolation] = []

    # J.2: Tie vote must result in no banishment
    has_tie = len(event.tied_players) > 0
    has_banishment = event.banished is not None

    if has_tie and has_banishment:
        violations.append(ValidationViolation(
            rule_id="J.2",
            category="Voting",
            message=f"Tie vote but player {event.banished} was banished",
            severity=ValidationSeverity.ERROR,
            context={"tied_players": event.tied_players, "banished": event.banished}
        ))

    if not has_tie and not has_banishment:
        violations.append(ValidationViolation(
            rule_id="J.2",
            category="Voting",
            message="No tie and no banishment - unexpected state",
            severity=ValidationSeverity.ERROR,
            context={"tied_players": event.tied_players, "banished": event.banished}
        ))

    return violations


__all__ = ['validate_vote', 'validate_banishment']
