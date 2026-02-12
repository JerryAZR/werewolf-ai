"""Victory Condition Validators (A.1-A.5).

Rules:
- A.1: Game must end with a winner when victory condition is met
- A.2: Villagers win when all Werewolves are dead
- A.3: Werewolves win when all Ordinary Villagers are dead
- A.4: Werewolves win when all Gods are dead
- A.5: If both conditions met simultaneously, game ends in tie
"""

from typing import Optional, Literal

from werewolf.engine.game_state import GameState
from werewolf.models.player import Role
from .types import ValidationViolation, ValidationSeverity

# Camp constants (matching game_events.py VictoryOutcome.winner)
Camp = Literal["VILLAGER", "WEREWOLF"]


def validate_a1_game_must_end(state: GameState, is_over: bool) -> list[ValidationViolation]:
    """A.1: Game must end with a winner when victory condition is met.

    Args:
        state: Game state
        is_over: Whether the game was declared over

    Returns:
        List of validation violations
    """
    violations: list[ValidationViolation] = []

    werewolf_count = state.get_werewolf_count()
    villager_count = state.get_ordinary_villager_count()
    god_count = state.get_god_count()

    # Check if victory condition is met
    werewolf_win = werewolf_count > 0 and (god_count == 0 or villager_count == 0)
    villager_win = werewolf_count == 0
    victory_condition_met = werewolf_win or villager_win

    if victory_condition_met and not is_over:
        violations.append(ValidationViolation(
            rule_id="A.1",
            category="Victory Conditions",
            message="Game must end with a winner when victory condition is met",
            severity=ValidationSeverity.ERROR,
            context={
                "werewolf_count": werewolf_count,
                "villager_count": villager_count,
                "god_count": god_count
            }
        ))

    return violations


def validate_a2_villagers_win_when_werewolves_dead(
    state: GameState, declared_winner: Optional[Camp], is_over: bool
) -> list[ValidationViolation]:
    """A.2: Villagers win when all Werewolves are dead.

    Args:
        state: Game state
        declared_winner: Winner that was declared
        is_over: Whether the game was declared over

    Returns:
        List of validation violations
    """
    violations: list[ValidationViolation] = []

    werewolf_count = state.get_werewolf_count()
    villager_count = state.get_ordinary_villager_count()
    god_count = state.get_god_count()

    werewolves_dead = werewolf_count == 0
    villagers_dead = villager_count == 0
    gods_dead = god_count == 0

    # Villager victory condition: all werewolves dead
    # But NOT tie (both werewolves dead AND villagers/gods dead)
    villager_victory_condition = werewolves_dead and not (villagers_dead and gods_dead)

    if villager_victory_condition:
        if not is_over:
            violations.append(ValidationViolation(
                rule_id="A.2",
                category="Victory Conditions",
                message="Villagers win when all Werewolves are dead",
                severity=ValidationSeverity.ERROR,
                context={"declared_winner": declared_winner, "is_over": is_over}
            ))
        elif declared_winner != "VILLAGER":
            violations.append(ValidationViolation(
                rule_id="A.2",
                category="Victory Conditions",
                message=f"Villagers win when all Werewolves are dead, but declared winner is {declared_winner}",
                severity=ValidationSeverity.ERROR,
                context={"declared_winner": declared_winner}
            ))

    return violations


def validate_a3_werewolves_win_when_villagers_dead(
    state: GameState, declared_winner: Optional[Camp], is_over: bool
) -> list[ValidationViolation]:
    """A.3: Werewolves win when all Ordinary Villagers are dead.

    Args:
        state: Game state
        declared_winner: Winner that was declared
        is_over: Whether the game was declared over

    Returns:
        List of validation violations
    """
    violations: list[ValidationViolation] = []

    werewolf_count = state.get_werewolf_count()
    villager_count = state.get_ordinary_villager_count()
    god_count = state.get_god_count()

    werewolves_alive = werewolf_count > 0
    villagers_dead = villager_count == 0
    gods_dead = god_count == 0

    # Werewolf victory condition: all ordinary villagers dead
    # (and werewolves are still alive)
    werewolf_victory_condition_villagers = werewolves_alive and villagers_dead

    if werewolf_victory_condition_villagers:
        if not is_over:
            violations.append(ValidationViolation(
                rule_id="A.3",
                category="Victory Conditions",
                message="Werewolves win when all Ordinary Villagers are dead",
                severity=ValidationSeverity.ERROR,
                context={"declared_winner": declared_winner, "is_over": is_over}
            ))
        elif declared_winner != "WEREWOLF":
            violations.append(ValidationViolation(
                rule_id="A.3",
                category="Victory Conditions",
                message=f"Werewolves win when all Ordinary Villagers are dead, but declared winner is {declared_winner}",
                severity=ValidationSeverity.ERROR,
                context={"declared_winner": declared_winner}
            ))

    return violations


def validate_a4_werewolves_win_when_gods_dead(
    state: GameState, declared_winner: Optional[Camp], is_over: bool
) -> list[ValidationViolation]:
    """A.4: Werewolves win when all Gods are dead.

    Args:
        state: Game state
        declared_winner: Winner that was declared
        is_over: Whether the game was declared over

    Returns:
        List of validation violations
    """
    violations: list[ValidationViolation] = []

    werewolf_count = state.get_werewolf_count()
    god_count = state.get_god_count()

    werewolves_alive = werewolf_count > 0
    gods_dead = god_count == 0

    # Werewolf victory condition: all gods dead
    # (and werewolves are still alive)
    werewolf_victory_condition_gods = werewolves_alive and gods_dead

    if werewolf_victory_condition_gods:
        if not is_over:
            violations.append(ValidationViolation(
                rule_id="A.4",
                category="Victory Conditions",
                message="Werewolves win when all Gods are dead",
                severity=ValidationSeverity.ERROR,
                context={"declared_winner": declared_winner, "is_over": is_over}
            ))
        elif declared_winner != "WEREWOLF":
            violations.append(ValidationViolation(
                rule_id="A.4",
                category="Victory Conditions",
                message=f"Werewolves win when all Gods are dead, but declared winner is {declared_winner}",
                severity=ValidationSeverity.ERROR,
                context={"declared_winner": declared_winner}
            ))

    return violations


def validate_a5_tie_when_both_conditions_met(
    state: GameState, declared_winner: Optional[Camp], is_over: bool
) -> list[ValidationViolation]:
    """A.5: If both conditions met simultaneously, game ends in tie.

    Args:
        state: Game state
        declared_winner: Winner that was declared
        is_over: Whether the game was declared over

    Returns:
        List of validation violations
    """
    violations: list[ValidationViolation] = []

    werewolf_count = state.get_werewolf_count()
    villager_count = state.get_ordinary_villager_count()
    god_count = state.get_god_count()

    werewolves_dead = werewolf_count == 0
    villagers_dead = villager_count == 0
    gods_dead = god_count == 0

    # Tie condition: both werewolves dead AND (villagers dead OR gods dead)
    # Actually per rules: werewolves dead AND villagers dead AND gods dead
    tie_condition = werewolves_dead and villagers_dead and gods_dead

    if tie_condition:
        if not is_over:
            violations.append(ValidationViolation(
                rule_id="A.5",
                category="Victory Conditions",
                message="Both Werewolf and Villager victory conditions met simultaneously - game should end in tie",
                severity=ValidationSeverity.ERROR,
                context={"declared_winner": declared_winner, "is_over": is_over}
            ))
        elif declared_winner is not None:
            violations.append(ValidationViolation(
                rule_id="A.5",
                category="Victory Conditions",
                message=f"Tie condition detected but winner declared: {declared_winner}",
                severity=ValidationSeverity.ERROR,
                context={"declared_winner": declared_winner}
            ))

    return violations


def validate_victory(
    state: GameState,
    declared_winner: Optional[Camp],
    is_over: bool,
) -> list[ValidationViolation]:
    """Validate all victory condition rules (A.1-A.5).

    Args:
        state: Game state
        declared_winner: Winner that was declared
        is_over: Whether the game was declared over

    Returns:
        List of validation violations
    """
    violations: list[ValidationViolation] = []

    # A.1: Game must end with a winner when victory condition is met
    violations.extend(validate_a1_game_must_end(state, is_over))

    # A.2: Villagers win when all Werewolves are dead
    violations.extend(validate_a2_villagers_win_when_werewolves_dead(state, declared_winner, is_over))

    # A.3: Werewolves win when all Ordinary Villagers are dead
    violations.extend(validate_a3_werewolves_win_when_villagers_dead(state, declared_winner, is_over))

    # A.4: Werewolves win when all Gods are dead
    violations.extend(validate_a4_werewolves_win_when_gods_dead(state, declared_winner, is_over))

    # A.5: If both conditions met simultaneously, game ends in tie
    violations.extend(validate_a5_tie_when_both_conditions_met(state, declared_winner, is_over))

    return violations


def check_victory(state: GameState) -> tuple[bool, Optional[Camp], Optional[str]]:
    """Check if victory condition is met.

    Args:
        state: Current game state

    Returns:
        Tuple of (game_over, winner_camp, tie_reason)
        - game_over: True if game should end
        - winner_camp: Camp.VILLAGER or Camp.WEREWOLF
        - tie_reason: None if no tie, reason string if tie
    """
    werewolf_count = state.get_werewolf_count()
    villager_count = state.get_ordinary_villager_count()
    god_count = state.get_god_count()

    werewolves_alive = werewolf_count > 0
    villagers_alive = villager_count > 0
    gods_alive = god_count > 0

    # A.2: Villagers win when all werewolves dead
    # A.3: Werewolves win when all villagers dead
    # A.4: Werewolves win when all gods dead
    # A.5: Simultaneous = tie

    # Check tie condition first (A.5)
    if not werewolves_alive and not villagers_alive and not gods_alive:
        return (True, None, "Both Villager and Werewolf victory conditions met")

    # Check villager victory (A.2)
    if not werewolves_alive:
        return (True, Camp.VILLAGER, None)

    # Check werewolf victories (A.3 and A.4)
    if not villagers_alive or not gods_alive:
        return (True, Camp.WEREWOLF, None)

    return (False, None, None)


__all__ = [
    'check_victory',
    'validate_victory',
    'validate_a1_game_must_end',
    'validate_a2_villagers_win_when_werewolves_dead',
    'validate_a3_werewolves_win_when_villagers_dead',
    'validate_a4_werewolves_win_when_gods_dead',
    'validate_a5_tie_when_both_conditions_met',
]
