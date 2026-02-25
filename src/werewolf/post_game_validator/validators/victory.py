"""Victory condition validators (A.1-A.5).

Rules:
- A.1: Game must end with a winner when victory condition is met
- A.2: Villagers win when all Werewolves are dead
- A.3: Werewolves win when all Ordinary Villagers are dead
- A.4: Werewolves win when all Gods are dead
- A.5: If both conditions met simultaneously, game ends in tie
"""

from typing import Optional, TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from werewolf.engine.game_state import GameState
    from werewolf.post_game_validator.types import ValidationViolation


def validate_victory(
    state: Optional["GameState"],
    declared_winner: Optional[str],
    is_over: bool,
) -> list["ValidationViolation"]:
    """Validate victory conditions A.1-A.5.

    Args:
        state: Game state
        declared_winner: Winner that was declared ("VILLAGER" or "WEREWOLF")
        is_over: Whether the game was declared over

    Returns:
        List of validation violations found
    """
    violations: list["ValidationViolation"] = []

    if state is None:
        return violations

    # Get current counts
    werewolf_count = state.get_werewolf_count()
    villager_count = state.get_ordinary_villager_count()
    god_count = state.get_god_count()

    werewolves_alive = werewolf_count > 0
    villagers_alive = villager_count > 0
    gods_alive = god_count > 0

    # A.2: Villagers win when all werewolves dead
    if not werewolves_alive:
        if not is_over:
            violations.append({
                "rule_id": "A.2",
                "category": "Victory Conditions",
                "message": "Villagers win when all Werewolves are dead, but game is not over",
                "severity": "error",
            })
        elif declared_winner == "TIE":
            # This is a tie (A.5), not a violation of A.2
            pass
        elif declared_winner != "VILLAGER":
            violations.append({
                "rule_id": "A.2",
                "category": "Victory Conditions",
                "message": f"Werewolves are dead, but declared winner is {declared_winner}",
                "severity": "error",
            })

    # A.3: Werewolves win when all ordinary villagers dead
    if not villagers_alive and werewolves_alive:
        if not is_over:
            violations.append({
                "rule_id": "A.3",
                "category": "Victory Conditions",
                "message": "Werewolves win when all Ordinary Villagers are dead, but game is not over",
                "severity": "error",
            })
        elif declared_winner == "TIE":
            # This is a tie (A.5), not a violation of A.3
            pass
        elif declared_winner != "WEREWOLF":
            violations.append({
                "rule_id": "A.3",
                "category": "Victory Conditions",
                "message": f"All villagers are dead, but declared winner is {declared_winner}",
                "severity": "error",
            })

    # A.4: Werewolves win when all gods dead
    if not gods_alive and werewolves_alive:
        if not is_over:
            violations.append({
                "rule_id": "A.4",
                "category": "Victory Conditions",
                "message": "Werewolves win when all Gods are dead, but game is not over",
                "severity": "error",
            })
        elif declared_winner == "TIE":
            # This is a tie (A.5), not a violation of A.4
            pass
        elif declared_winner != "WEREWOLF":
            violations.append({
                "rule_id": "A.4",
                "category": "Victory Conditions",
                "message": f"All gods are dead, but declared winner is {declared_winner}",
                "severity": "error",
            })

    # A.5: Tie when both conditions met simultaneously:
    # - Werewolf condition: all villagers dead OR all gods dead
    # - Villager condition: all werewolves dead
    # Tie = werewolves dead AND (villagers dead OR gods dead)
    werewolves_dead = not werewolves_alive
    villagers_dead = not villagers_alive
    gods_dead = not gods_alive

    tie_condition = werewolves_dead and (villagers_dead or gods_dead)

    if tie_condition:
        if is_over and declared_winner != "TIE":
            violations.append({
                "rule_id": "A.5",
                "category": "Victory Conditions",
                "message": "Game should end in tie when both victory conditions are met",
                "severity": "error",
            })

    return violations
