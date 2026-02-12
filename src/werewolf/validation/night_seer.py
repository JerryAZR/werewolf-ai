"""Seer Action Validators (G.1-G.3).

Rules:
- G.1: Seer cannot check more than one living player per night (enforced by handler flow)
- G.2: Seer result must be GOOD or WEREWOLF
- G.3: Seer result must match the target's actual role (WEREWOLF if target is werewolf)
"""

from werewolf.engine.game_state import GameState
from werewolf.events.game_events import SeerAction, SeerResult
from werewolf.models.player import Role
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


def validate_seer_result(
    events: list["SeerAction"],
    state: GameState,
) -> list[ValidationViolation]:
    """Validate G.3: Seer result must match the target's actual role.

    The seer's result should be WEREWOLF if the target is a werewolf,
    and GOOD otherwise (for all non-werewolf roles).

    Args:
        events: List of SeerAction events to validate
        state: Game state with player roles

    Returns:
        List of validation violations (empty if valid)
    """
    violations: list[ValidationViolation] = []

    for event in events:
        if event.target is None:
            continue

        # Get the target's actual role from state
        target_player = state.players.get(event.target)
        if target_player is None:
            continue

        # Determine expected result based on target's role
        is_werewolf = target_player.role == Role.WEREWOLF
        expected_result = SeerResult.WEREWOLF if is_werewolf else SeerResult.GOOD

        # Check if result matches
        if event.result != expected_result:
            violations.append(ValidationViolation(
                rule_id="G.3",
                category="Night Actions - Seer",
                message=f"Seer result mismatch: checked {target_player.role.value}, got {event.result.value}, expected {expected_result.value}",
                severity=ValidationSeverity.ERROR,
                context={
                    "actor": event.actor,
                    "target": event.target,
                    "target_role": target_player.role.value,
                    "actual_result": event.result.value,
                    "expected_result": expected_result.value,
                }
            ))

    return violations


__all__ = ['validate_seer_action', 'validate_seer_result']
