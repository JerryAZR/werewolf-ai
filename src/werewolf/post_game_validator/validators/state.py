"""State consistency validators (M.1-M.7).

Rules:
- M.1: living_players and dead_players must be disjoint
- M.2: dead_players must match players with is_alive=False
- M.3: living_players + dead_players = all players
- M.4: Sheriff must be alive
- M.5: No duplicate players by seat
- M.6: All seats must be valid (0-11 for 12-player game)
- M.7: Role counts must match state
"""

from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from werewolf.engine.game_state import GameState
    from werewolf.post_game_validator.types import ValidationViolation


def validate_state_consistency(
    state: Optional["GameState"],
    existing_violations: list["ValidationViolation"],
) -> list["ValidationViolation"]:
    """Validate state consistency rules M.1-M.7.

    Args:
        state: Current game state
        existing_violations: List to append violations to

    Returns:
        List of validation violations found
    """
    violations: list["ValidationViolation"] = []

    if state is None:
        return violations

    all_seats = set(state.players.keys())

    # M.1: living_players and dead_players must be disjoint
    overlap = state.living_players & state.dead_players
    if overlap:
        violations.append({
            "rule_id": "M.1",
            "category": "State Consistency",
            "message": f"Players in both living and dead sets: {sorted(overlap)}",
            "severity": "error",
        })

    # M.2: dead_players must match players with is_alive=False
    expected_dead = {seat for seat, p in state.players.items() if not p.is_alive}
    if state.dead_players != expected_dead:
        violations.append({
            "rule_id": "M.2",
            "category": "State Consistency",
            "message": f"dead_players set {state.dead_players} doesn't match expected {expected_dead}",
            "severity": "error",
        })

    # M.3: living_players + dead_players = all players
    expected_living = all_seats - state.dead_players
    if state.living_players != expected_living:
        violations.append({
            "rule_id": "M.3",
            "category": "State Consistency",
            "message": f"living_players set {state.living_players} doesn't match expected {expected_living}",
            "severity": "error",
        })

    # M.4: Sheriff must be alive
    if state.sheriff is not None and state.sheriff not in state.living_players:
        violations.append({
            "rule_id": "M.4",
            "category": "State Consistency",
            "message": f"Sheriff {state.sheriff} is not alive",
            "severity": "error",
        })

    # M.5: No duplicate players by seat
    if len(state.players) != len(all_seats):
        violations.append({
            "rule_id": "M.5",
            "category": "State Consistency",
            "message": f"Duplicate seats detected in players dict",
            "severity": "error",
        })

    # M.6: All seats must be valid (0-11 for 12-player game)
    expected_seats = set(range(12))
    if all_seats != expected_seats:
        missing = expected_seats - all_seats
        extra = all_seats - expected_seats
        if missing:
            violations.append({
                "rule_id": "M.6",
                "category": "State Consistency",
                "message": f"Missing seats: {sorted(missing)}",
                "severity": "error",
            })
        if extra:
            violations.append({
                "rule_id": "M.6",
                "category": "State Consistency",
                "message": f"Invalid seats: {sorted(extra)}",
                "severity": "error",
            })

    # M.7: Role counts must match state
    expected_counts = {"WEREWOLF": 4, "SEER": 1, "WITCH": 1, "GUARD": 1, "HUNTER": 1, "ORDINARY_VILLAGER": 4}
    for role_str, expected_count in expected_counts.items():
        actual_count = sum(1 for p in state.players.values() if p.role.value == role_str)
        if actual_count != expected_count:
            violations.append({
                "rule_id": "M.7",
                "category": "State Consistency",
                "message": f"Role {role_str}: expected {expected_count}, got {actual_count}",
                "severity": "error",
            })

    return violations
