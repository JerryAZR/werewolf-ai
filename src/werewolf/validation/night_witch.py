"""Witch Action Validators (E.1-E.7).

Rules:
- E.1: Witch must be informed of Werewolf kill target before potion decision (handled by game flow)
- E.2: Witch cannot use more than one potion per night (enforced by game state)
- E.3: Witch cannot use antidote on self
- E.4: Witch cannot use antidote if already used
- E.5: Witch cannot use poison if already used
- E.6: Antidote must override Werewolf kill (enforced by night resolution)
- E.7: Poison must kill target regardless of guard protection (enforced by night resolution)
"""

from typing import Optional
from werewolf.engine.game_state import GameState
from werewolf.events.game_events import WitchAction, WitchActionType
from .types import ValidationViolation, ValidationSeverity


def validate_witch_action(
    event: WitchAction,
    state: GameState,
    antidote_used: bool,
    poison_used: bool,
) -> list[ValidationViolation]:
    """Validate witch action rules E.2-E.5.

    Note: E.1, E.6, E.7 are enforced by game flow/resolution, not action validation.

    Args:
        event: The witch action event
        state: Game state
        antidote_used: Whether antidote was already used this night
        poison_used: Whether poison was already used this night

    Returns:
        List of validation violations (empty if valid)
    """
    violations: list[ValidationViolation] = []

    # E.2: Cannot use more than one potion per night (checked by handler state)
    # E.3: Cannot use antidote on self
    if event.action_type == WitchActionType.ANTIDOTE:
        if event.target == event.actor:
            violations.append(ValidationViolation(
                rule_id="E.3",
                category="Night Actions - Witch",
                message="Witch cannot use antidote on self",
                severity=ValidationSeverity.ERROR,
                context={"actor": event.actor, "target": event.target}
            ))

        # E.4: Cannot use antidote if already used
        if antidote_used:
            violations.append(ValidationViolation(
                rule_id="E.4",
                category="Night Actions - Witch",
                message="Witch cannot use antidote - already used",
                severity=ValidationSeverity.ERROR,
                context={"actor": event.actor}
            ))

    # E.5: Cannot use poison if already used
    if event.action_type == WitchActionType.POISON:
        if poison_used:
            violations.append(ValidationViolation(
                rule_id="E.5",
                category="Night Actions - Witch",
                message="Witch cannot use poison - already used",
                severity=ValidationSeverity.ERROR,
                context={"actor": event.actor}
            ))

        # Poison target must be alive (poison kills, not eliminates)
        if event.target is not None and event.target in state.dead_players:
            violations.append(ValidationViolation(
                rule_id="E.5",
                category="Night Actions - Witch",
                message=f"Witch cannot poison dead player {event.target}",
                severity=ValidationSeverity.ERROR,
                context={"target": event.target}
            ))

    # Validate target presence for ANTIDOTE/POISON actions
    if event.action_type in (WitchActionType.ANTIDOTE, WitchActionType.POISON):
        if event.target is None:
            violations.append(ValidationViolation(
                rule_id="E.2",
                category="Night Actions - Witch",
                message=f"Witch {event.action_type.value} action missing target",
                severity=ValidationSeverity.ERROR,
                context={"action_type": event.action_type.value}
            ))

    return violations


__all__ = ['validate_witch_action']
