"""Seer Action Validators (G.1-G.2).

Rules:
- G.1: Seer cannot check more than one living player per night (enforced by handler flow)
- G.2: Seer result must be GOOD or WEREWOLF
"""

from werewolf.engine.game_state import GameState
from werewolf.events.game_events import SeerAction, SeerResult
from .types import ValidationViolation, ValidationSeverity


def validate_seer_action(
    event: SeerAction,
    state: GameState,
) -> list[ValidationViolation]:
    """Validate seer action rules G.1-G.2.

    Args:
        event: The seer action event
        state: Game state

    Returns:
        List of validation violations (empty if valid)
    """
    violations: list[ValidationViolation] = []

    # G.1: Seer cannot check more than one living player per night
    # The handler enforces this by only querying once per night.
    # Validation: Target must be a living player
    if event.target not in state.living_players:
        violations.append(ValidationViolation(
            rule_id="G.1",
            category="Night Actions - Seer",
            message=f"Seer cannot check dead player {event.target}",
            severity=ValidationSeverity.ERROR,
            context={"target": event.target, "actor": event.actor}
        ))

    # G.2: Seer result must be GOOD or WEREWOLF
    if event.result not in (SeerResult.GOOD, SeerResult.WEREWOLF):
        violations.append(ValidationViolation(
            rule_id="G.2",
            category="Night Actions - Seer",
            message=f"Seer result must be GOOD or WEREWOLF, got {event.result}",
            severity=ValidationSeverity.ERROR,
            context={"result": event.result, "actor": event.actor, "target": event.target}
        ))

    return violations


__all__ = ['validate_seer_action']
