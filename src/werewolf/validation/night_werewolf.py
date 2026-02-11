"""Werewolf Action Validators (D.1-D.2).

Rules:
- D.1: Werewolves cannot target dead players
- D.2: Dead Werewolves cannot participate in night action
"""

from werewolf.engine.game_state import GameState
from werewolf.events.game_events import WerewolfKill
from .types import ValidationViolation, ValidationSeverity


def validate_werewolf_action(
    event: WerewolfKill,
    state: GameState,
) -> list[ValidationViolation]:
    """Validate werewolf action rules D.1-D.2.

    Args:
        event: The werewolf kill event
        state: Game state after event applied

    Returns:
        List of validation violations (empty if valid)
    """
    violations: list[ValidationViolation] = []

    # D.1: Cannot target dead players
    if event.target is not None and event.target in state.dead_players:
        violations.append(ValidationViolation(
            rule_id="D.1",
            category="Night Actions - Werewolf",
            message=f"Werewolf cannot target dead player {event.target}",
            severity=ValidationSeverity.ERROR,
            context={"target": event.target, "actor": event.actor}
        ))

    # D.2: Dead werewolves cannot act
    if event.actor in state.dead_players:
        violations.append(ValidationViolation(
            rule_id="D.2",
            category="Night Actions - Werewolf",
            message=f"Dead werewolf (seat {event.actor}) cannot participate in night action",
            severity=ValidationSeverity.ERROR,
            context={"actor": event.actor}
        ))

    return violations


__all__ = ['validate_werewolf_action']
