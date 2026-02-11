"""Badge Transfer Validators (L.1-L.4).

Rules:
- L.1: Badge transfer target must be living
- L.2: Sheriff role must remain single (one badge at a time)
- L.3: Werewolf Sheriff must still win with Werewolf camp
- L.4: When a Sheriff dies, they must be queried for badge transfer target
"""

from typing import Optional
from werewolf.engine.game_state import GameState
from werewolf.events.game_events import DeathEvent, GameEvent
from werewolf.models.player import Role
from .types import ValidationViolation, ValidationSeverity


def validate_badge_transfer(
    event: DeathEvent,
    state: GameState,
) -> list[ValidationViolation]:
    """Validate badge transfer rules L.1-L.4.

    Args:
        event: Death event with badge_transfer_to field
        state: Game state after death resolution

    Returns:
        List of validation violations (empty if valid)
    """
    violations: list[ValidationViolation] = []

    badge_target = event.badge_transfer_to
    dead_seat = event.actor
    dead_player = state.players.get(dead_seat)
    is_sheriff_death = dead_player is not None and dead_player.is_sheriff

    # L.1: Badge transfer target must be living
    if badge_target is not None:
        if badge_target not in state.living_players:
            violations.append(ValidationViolation(
                rule_id="L.1",
                category="Badge Transfer",
                message=f"Badge transfer target {badge_target} is not alive",
                severity=ValidationSeverity.ERROR,
                context={"badge_target": badge_target, "actor": event.actor}
            ))

        # Badge target must be a valid player
        if badge_target not in state.players:
            violations.append(ValidationViolation(
                rule_id="L.1",
                category="Badge Transfer",
                message=f"Badge transfer target {badge_target} is not a valid player",
                severity=ValidationSeverity.ERROR,
                context={"badge_target": badge_target}
            ))

    # L.4: When a Sheriff dies, they must be queried for badge transfer target
    if is_sheriff_death and badge_target is None:
        violations.append(ValidationViolation(
            rule_id="L.4",
            category="Badge Transfer",
            message=f"Sheriff at seat {dead_seat} died without specifying badge transfer target",
            severity=ValidationSeverity.ERROR,
            context={"actor": dead_seat}
        ))

    # L.3: Werewolf Sheriff still contributes to Werewolf victory
    # This is enforced by victory condition logic - a Werewolf sheriff counts
    # toward the werewolf victory condition (werewolf_count includes sheriff)
    if badge_target is not None and badge_target in state.players:
        new_sheriff = state.players[badge_target]
        if new_sheriff.role == Role.WEREWOLF:
            # Verify the werewolf sheriff is counted in victory conditions
            # by checking the sheriff is included in living_players
            if badge_target not in state.living_players:
                violations.append(ValidationViolation(
                    rule_id="L.3",
                    category="Badge Transfer",
                    message=f"Werewolf Sheriff at seat {badge_target} is not in living_players",
                    severity=ValidationSeverity.ERROR,
                    context={"sheriff_seat": badge_target}
                ))

    return violations


def validate_no_duplicate_sheriff(state: GameState) -> list[ValidationViolation]:
    """Validate L.2: Only one sheriff at a time.

    Args:
        state: Game state

    Returns:
        List of validation violations
    """
    violations: list[ValidationViolation] = []

    sheriff_count = sum(1 for p in state.players.values() if p.is_sheriff)

    if sheriff_count > 1:
        sheriff_seats = [p.seat for p in state.players.values() if p.is_sheriff]
        violations.append(ValidationViolation(
            rule_id="L.2",
            category="Badge Transfer",
            message=f"Multiple sheriffs detected: {sheriff_seats}",
            severity=ValidationSeverity.ERROR,
            context={"sheriff_seats": sheriff_seats}
        ))

    if sheriff_count == 1 and state.sheriff is None:
        violations.append(ValidationViolation(
            rule_id="L.2",
            category="Badge Transfer",
            message="Player marked as sheriff but sheriff state is None",
            severity=ValidationSeverity.ERROR
        ))

    # L.2: Sheriff badge is single - verify sheriff state consistency
    if state.sheriff is not None:
        sheriff_player = state.players.get(state.sheriff)
        if sheriff_player is None:
            violations.append(ValidationViolation(
                rule_id="L.2",
                category="Badge Transfer",
                message=f"Sheriff state references non-existent player: {state.sheriff}",
                severity=ValidationSeverity.ERROR,
                context={"sheriff": state.sheriff}
            ))
        elif not sheriff_player.is_sheriff:
            violations.append(ValidationViolation(
                rule_id="L.2",
                category="Badge Transfer",
                message=f"Sheriff state ({state.sheriff}) does not have is_sheriff=True",
                severity=ValidationSeverity.ERROR,
                context={"sheriff": state.sheriff}
            ))

    return violations


def validate_sheriff_victory_contribution(
    state: GameState,
    winner: str
) -> list[ValidationViolation]:
    """Validate L.3: Werewolf Sheriff contributes to Werewolf victory.

    Args:
        state: Game state at game over
        winner: Winner of the game ("WEREWOLF" or "VILLAGER")

    Returns:
        List of validation violations
    """
    violations: list[ValidationViolation] = []

    if state.sheriff is None:
        return violations

    sheriff_player = state.players.get(state.sheriff)
    if sheriff_player is None:
        return violations

    # L.3: Werewolf Sheriff must win with Werewolf camp
    if sheriff_player.role == Role.WEREWOLF and winner == "WEREWOLF":
        # Verify the werewolf sheriff was counted as a living werewolf
        if state.sheriff not in state.living_players:
            violations.append(ValidationViolation(
                rule_id="L.3",
                category="Badge Transfer",
                message="Werewolf Sheriff was not counted in victory condition",
                severity=ValidationSeverity.ERROR,
                context={"sheriff_seat": state.sheriff, "winner": winner}
            ))

    return violations


__all__ = [
    'validate_badge_transfer',
    'validate_no_duplicate_sheriff',
    'validate_sheriff_victory_contribution'
]
