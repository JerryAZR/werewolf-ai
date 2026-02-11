"""State Consistency Validators (M.1-M.7).

Rules:
- M.1: living_players union dead_players must equal all_players
- M.2: living_players and dead_players must be disjoint
- M.3: Player.is_alive must match seat in living_players
- M.4: Player.is_sheriff must match sheriff state
- M.5: Dead players cannot appear in living-only operations (enforced by handlers)
- M.6: All events must have valid day number
- M.7: All events must have valid actor (seat exists)
"""

from werewolf.engine.game_state import GameState
from werewolf.events.game_events import GameEvent
from .types import ValidationViolation, ValidationSeverity


def validate_state_consistency(
    state: GameState,
    event: GameEvent | None = None,
) -> list[ValidationViolation]:
    """Validate state consistency rules M.1-M.7.

    Args:
        state: Current game state
        event: Optional event that was just applied

    Returns:
        List of validation violations (empty if valid)
    """
    violations: list[ValidationViolation] = []

    living = state.living_players
    dead = state.dead_players
    all_ids = {seat for seat in state.players.keys()}

    # M.1: living ∪ dead == all
    if living | dead != all_ids:
        missing = all_ids - (living | dead)
        extra = (living | dead) - all_ids
        violations.append(ValidationViolation(
            rule_id="M.1",
            category="State Consistency",
            message="living_players union dead_players must equal all_players",
            severity=ValidationSeverity.ERROR,
            context={"missing": list(missing), "extra": list(extra)}
        ))

    # M.2: living ∩ dead == ∅
    if living & dead:
        overlaps = living & dead
        violations.append(ValidationViolation(
            rule_id="M.2",
            category="State Consistency",
            message="living_players and dead_players must be disjoint",
            severity=ValidationSeverity.ERROR,
            context={"overlapping_seats": list(overlaps)}
        ))

    # M.3: Player.is_alive matches living_players
    for seat, player in state.players.items():
        expected_alive = seat in living
        if player.is_alive != expected_alive:
            violations.append(ValidationViolation(
                rule_id="M.3",
                category="State Consistency",
                message=f"Player {seat}: is_alive={player.is_alive} but seat in living={expected_alive}",
                severity=ValidationSeverity.ERROR,
                context={"seat": seat, "is_alive": player.is_alive, "in_living": expected_alive}
            ))

    # M.4: Player.is_sheriff matches sheriff state
    sheriff_id = state.sheriff
    for seat, player in state.players.items():
        expected_sheriff = seat == sheriff_id
        if player.is_sheriff != expected_sheriff:
            violations.append(ValidationViolation(
                rule_id="M.4",
                category="State Consistency",
                message=f"Player {seat}: is_sheriff={player.is_sheriff} but sheriff={sheriff_id}",
                severity=ValidationSeverity.ERROR,
                context={"seat": seat, "is_sheriff": player.is_sheriff, "sheriff_id": sheriff_id}
            ))

    # M.6: Event day validation
    if event and hasattr(event, 'day') and event.day != state.day:
        violations.append(ValidationViolation(
            rule_id="M.6",
            category="State Consistency",
            message=f"Event day={event.day} != state day={state.day}",
            severity=ValidationSeverity.ERROR,
            context={"event_day": event.day, "state_day": state.day}
        ))

    # M.7: Event actor validation (if applicable)
    if event and hasattr(event, 'actor') and event.actor is not None:
        if event.actor not in all_ids:
            violations.append(ValidationViolation(
                rule_id="M.7",
                category="State Consistency",
                message=f"Event actor={event.actor} not in all_players",
                severity=ValidationSeverity.ERROR,
                context={"actor": event.actor, "all_ids": list(all_ids)}
            ))

    return violations


__all__ = ['validate_state_consistency']
