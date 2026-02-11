"""Game Initialization Validators (B.1-B.4).

Rules:
- B.1: Werewolf count must be greater than 0
- B.2: Ordinary Villager count must be greater than 0
- B.3: God count must be greater than 0
- B.4: Each God role must be unique (no duplicate Seer, Witch, Hunter, Guard)
"""

from werewolf.engine.game_state import GameState
from werewolf.models.player import Role
from .types import ValidationViolation, ValidationSeverity


GOD_ROLES = {Role.SEER, Role.WITCH, Role.HUNTER, Role.GUARD}


def validate_game_start(state: GameState) -> list[ValidationViolation]:
    """Validate game initialization rules B.1-B.4.

    Called during on_game_start hook.

    Args:
        state: Game state after player setup

    Returns:
        List of validation violations (empty if valid)
    """
    violations: list[ValidationViolation] = []

    werewolf_count = sum(1 for p in state.players.values() if p.role == Role.WEREWOLF)
    villager_count = sum(1 for p in state.players.values() if p.role == Role.ORDINARY_VILLAGER)
    god_count = sum(1 for p in state.players.values() if p.role in GOD_ROLES)

    # B.1: Werewolf count > 0
    if werewolf_count == 0:
        violations.append(ValidationViolation(
            rule_id="B.1",
            category="Game Initialization",
            message="Werewolf count must be greater than 0",
            severity=ValidationSeverity.ERROR,
            context={"werewolf_count": werewolf_count}
        ))

    # B.2: Ordinary Villager count > 0
    if villager_count == 0:
        violations.append(ValidationViolation(
            rule_id="B.2",
            category="Game Initialization",
            message="Ordinary Villager count must be greater than 0",
            severity=ValidationSeverity.ERROR,
            context={"villager_count": villager_count}
        ))

    # B.3: God count > 0
    if god_count == 0:
        violations.append(ValidationViolation(
            rule_id="B.3",
            category="Game Initialization",
            message="God count must be greater than 0",
            severity=ValidationSeverity.ERROR,
            context={"god_count": god_count}
        ))

    # B.4: Unique god roles
    god_seen: set[Role] = set()
    for player in state.players.values():
        if player.role in GOD_ROLES:
            if player.role in god_seen:
                violations.append(ValidationViolation(
                    rule_id="B.4",
                    category="Game Initialization",
                    message=f"Duplicate god role: {player.role.value}",
                    severity=ValidationSeverity.ERROR,
                    context={"duplicate_role": player.role.value, "seat": player.seat}
                ))
            god_seen.add(player.role)

    return violations


__all__ = ['validate_game_start']
