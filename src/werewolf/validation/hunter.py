"""Hunter Action Validators (K.1-K.4).

Rules:
- K.1: Hunter cannot activate when poisoned
- K.2: Hunter cannot target dead players
- K.3: Hunter must either shoot a living player or return "SKIP"
- K.4: Hunter shot target must die immediately
"""

from typing import Optional
from werewolf.engine.game_state import GameState
from werewolf.events.game_events import DeathEvent, DeathCause
from .types import ValidationViolation, ValidationSeverity


def validate_hunter_action(
    event: DeathEvent,
    state: GameState,
) -> list[ValidationViolation]:
    """Validate hunter action rules K.1-K.4.

    Args:
        event: Death event with hunter_shoot_target field
        state: Game state after event applied

    Returns:
        List of validation violations (empty if valid)
    """
    violations: list[ValidationViolation] = []

    hunter_seat = event.actor
    shoot_target = event.hunter_shoot_target
    cause = event.cause

    # K.1: Hunter cannot activate when poisoned
    if cause == DeathCause.POISON:
        if shoot_target is not None:
            violations.append(ValidationViolation(
                rule_id="K.1",
                category="Hunter",
                message="Hunter cannot shoot when poisoned",
                severity=ValidationSeverity.ERROR,
                context={"hunter": hunter_seat, "target": shoot_target, "cause": cause.value if cause else None}
            ))

    # K.2: Hunter cannot target dead players
    if shoot_target is not None and shoot_target in state.dead_players:
        violations.append(ValidationViolation(
            rule_id="K.2",
            category="Hunter",
            message=f"Hunter cannot shoot dead player {shoot_target}",
            severity=ValidationSeverity.ERROR,
            context={"hunter": hunter_seat, "target": shoot_target}
        ))

    # K.3: Hunter must either shoot or SKIP (None)
    # This is enforced by the handler choice - shoot_target being None indicates SKIP

    # K.4: Hunter shot target must die immediately
    # Verified by checking state after death resolution

    return violations


def validate_hunter_death_chain(
    event: DeathEvent,
    state: GameState,
) -> list[ValidationViolation]:
    """Validate K.4: Hunter shot target must die immediately.

    Args:
        event: Death event with hunter_shoot_target field
        state: Game state after death chain resolution

    Returns:
        List of validation violations
    """
    violations: list[ValidationViolation] = []

    hunter_seat = event.actor
    shoot_target = event.hunter_shoot_target
    cause = event.cause

    # K.4: Hunter shot target must die immediately
    if shoot_target is not None and cause != DeathCause.POISON:
        if shoot_target not in state.dead_players:
            violations.append(ValidationViolation(
                rule_id="K.4",
                category="Hunter",
                message=f"Hunter shot target {shoot_target} did not die",
                severity=ValidationSeverity.ERROR,
                context={"hunter": hunter_seat, "target": shoot_target}
            ))

    return violations


__all__ = ['validate_hunter_action', 'validate_hunter_death_chain']
