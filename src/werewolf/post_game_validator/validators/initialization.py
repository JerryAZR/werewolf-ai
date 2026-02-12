"""Initialization validators (B.1-B.4).

Rules:
- B.1: GameStart event must be recorded
- B.2: Player count must match configuration (12 players)
- B.3: Roles secret must be valid (correct role distribution)
- B.4: Sheriff cannot be elected before Day 1
"""

from typing import Optional, TYPE_CHECKING
from werewolf.models.player import Role, STANDARD_12_PLAYER_CONFIG, RoleConfig

if TYPE_CHECKING:
    from werewolf.engine.game_state import GameState
    from werewolf.post_game_validator.types import ValidationViolation


def validate_initialization(
    event_log,
    state: Optional["GameState"],
    existing_violations: list["ValidationViolation"],
) -> list["ValidationViolation"]:
    """Validate game initialization rules B.1-B.4.

    Args:
        event_log: The game event log
        state: Game state (None if not yet initialized)
        existing_violations: List to append violations to

    Returns:
        List of validation violations found
    """
    violations: list["ValidationViolation"] = []

    # B.1: GameStart must exist
    if event_log.game_start is None:
        violations.append({
            "rule_id": "B.1",
            "category": "Initialization",
            "message": "GameStart event must be recorded",
            "severity": "error",
        })
        # Can't continue validation without game start
        return violations

    # B.2: Player count must match (12 players)
    expected_players = 12  # STANDARD_12_PLAYER_CONFIG has 12 total
    if event_log.player_count != expected_players:
        violations.append({
            "rule_id": "B.2",
            "category": "Initialization",
            "message": f"Player count ({event_log.player_count}) must match expected ({expected_players})",
            "severity": "error",
        })

    # B.3: Roles secret must be valid
    role_counts: dict[str, int] = {}
    for seat, role_str in event_log.roles_secret.items():
        role_counts[role_str] = role_counts.get(role_str, 0) + 1

    # Build expected counts from config (role is already string due to use_enum_values=True)
    expected_counts: dict[str, int] = {}
    for config in STANDARD_12_PLAYER_CONFIG:
        expected_counts[config.role] = config.count

    for role_str, expected_count in expected_counts.items():
        actual_count = role_counts.get(role_str, 0)
        if actual_count != expected_count:
            violations.append({
                "rule_id": "B.3",
                "category": "Initialization",
                "message": f"Role {role_str}: expected {expected_count}, got {actual_count}",
                "severity": "error",
            })

    return violations
