"""Guard Action Validators (F.1-F.3).

Rules:
- F.1: Guard cannot guard the same player on consecutive nights
- F.2: Guard cannot be overridden by Witch poison (enforced by night resolution)
- F.3: Guard skill must work even if Guard dies that night (enforced by night resolution)
"""

from typing import Optional
from werewolf.engine.game_state import GameState
from werewolf.events.game_events import GuardAction
from .types import ValidationViolation, ValidationSeverity


def validate_guard_action(
    event: GuardAction,
    state: GameState,
    prev_guard_target: Optional[int],
) -> list[ValidationViolation]:
    """Validate guard action rules F.1.

    Note: F.2 and F.3 are enforced by night resolution logic, not action validation.

    Args:
        event: The guard action event
        state: Game state
        prev_guard_target: Who guard protected last night (None if Night 1)

    Returns:
        List of validation violations (empty if valid)
    """
    violations: list[ValidationViolation] = []

    # F.1: Cannot guard the same player on consecutive nights
    if event.target is not None and event.target == prev_guard_target:
        violations.append(ValidationViolation(
            rule_id="F.1",
            category="Night Actions - Guard",
            message=f"Guard cannot guard same player {event.target} on consecutive nights",
            severity=ValidationSeverity.ERROR,
            context={"target": event.target, "prev_target": prev_guard_target}
        ))

    # Target must be alive (guard protects living players)
    if event.target is not None and event.target in state.dead_players:
        violations.append(ValidationViolation(
            rule_id="F.1",
            category="Night Actions - Guard",
            message=f"Guard cannot protect dead player {event.target}",
            severity=ValidationSeverity.ERROR,
            context={"target": event.target}
        ))

    return violations


__all__ = ['validate_guard_action']
