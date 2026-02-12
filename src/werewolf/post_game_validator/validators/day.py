"""Day action validators (H.1-H.5, I.1-I.9, J.1-J.5, K.1-K.4, L.1-L.4).

Rules:
Day Actions - Sheriff (H):
- H.1: Sheriff election only on Day 1
- H.2: Only living players can be sheriff candidates
- H.3: Sheriff vote must have valid participants
- H.4: Sheriff badge must be transferred on death
- H.5: Sheriff cannot abstain from voting

Day Actions - Death (I):
- I.1: Dead players cannot act
- I.2: Last words only on Day 1 night deaths
- I.3: Hunter must shoot when hunter dies by werewolf/poison
- I.4: Hunter cannot shoot when hunter is banished
- I.5: Badge transfer requires valid heir
- I.6: Sheriff death triggers badge transfer
- I.7: Multiple deaths resolved in seat order
- I.8: Night 1 deaths have last words, Day deaths have last words
- I.9: Only one sheriff at a time

Day Actions - Voting (J):
- J.1: All living players must vote
- J.2: Sheriff vote weight is 1.5
- J.3: Banishment requires majority
- J.4: Tie votes result in no banishment
- J.5: Cannot vote for dead players

Day Actions - Hunter (K):
- K.1: Hunter can only shoot when hunter dies
- K.2: Hunter can only shoot living players
- K.3: Hunter result must be accurate
- K.4: Hunter shot executes immediately

Day Actions - Badge (L):
- L.1: Badge transfer only on sheriff death
- L.2: Sheriff can skip badge transfer
- L.3: Badge heir must be living
- L.4: No badge transfer if sheriff banished last
"""

from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from werewolf.engine.game_state import GameState
    from werewolf.post_game_validator.types import ValidationViolation


def validate_day_phase(
    phase_log,
    state: Optional["GameState"],
    existing_violations: list["ValidationViolation"],
    votes_this_phase: list,
    current_day: int,
) -> list["ValidationViolation"]:
    """Validate all day phase actions.

    Args:
        phase_log: The day phase log
        state: Current game state
        existing_violations: List to append violations to
        votes_this_phase: Tracker for votes this phase
        current_day: Current day number

    Returns:
        List of validation violations found
    """
    violations: list["ValidationViolation"] = []

    # Collect events by subphase
    for subphase in phase_log.subphases:
        for event in subphase.events:
            event_type = type(event).__name__

            # Sheriff nomination
            if "Nomination" in event_type or "Sheriff" in event_type:
                pass  # TODO: Implement sheriff validation

            # Sheriff election
            elif "Sheriff" in event_type and "Outcome" in event_type:
                pass  # TODO: Implement sheriff election validation

            # Death events
            elif "Death" in event_type and hasattr(event, 'cause'):
                violations.extend(
                    _validate_death(event, state, current_day)
                )

            # Votes
            elif hasattr(event, 'actor') and hasattr(event, 'target'):
                votes_this_phase.append(event)
                violations.extend(
                    _validate_vote(event, state, current_day)
                )

            # Banishment
            elif "Banishment" in event_type:
                violations.extend(
                    _validate_banishment(event, state, votes_this_phase, current_day)
                )

            # Speeches
            elif "Speech" in event_type:
                pass  # TODO: Implement speech validation

    return violations


def _validate_death(event, state: Optional["GameState"], current_day: int) -> list["ValidationViolation"]:
    """Validate death event."""
    violations: list["ValidationViolation"] = []

    # I.1: Dead players cannot act (actor should be dead at time of event)
    if state and event.actor not in state.players:
        violations.append({
            "rule_id": "I.1",
            "category": "Day Actions - Death",
            "message": f"Death event for unknown player {event.actor}",
            "severity": "error",
        })

    return violations


def _validate_vote(event, state: Optional["GameState"], current_day: int) -> list["ValidationViolation"]:
    """Validate vote event."""
    violations: list["ValidationViolation"] = []

    # J.5: Cannot vote for dead players
    if event.target is not None and state and event.target not in state.living_players:
        violations.append({
            "rule_id": "J.5",
            "category": "Day Actions - Voting",
            "message": f"Cannot vote for dead player {event.target}",
            "severity": "error",
        })

    return violations


def _validate_banishment(event, state: Optional["GameState"], votes: list, current_day: int) -> list["ValidationViolation"]:
    """Validate banishment event."""
    violations: list["ValidationViolation"] = []

    # J.3: Banishment requires majority
    # J.4: Tie votes result in no banishment
    pass  # TODO: Implement banishment validation

    return violations
