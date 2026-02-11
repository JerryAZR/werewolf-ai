"""Sheriff Election Validators (H.1-H.5).

Rules:
- H.1: Sheriff election must occur on Day 1 only
- H.2: Sheriff election cannot occur on Day 2+
- H.3: Night 1 deaths must be eligible for Sheriff
- H.4: Sheriff candidates cannot vote
- H.5: Sheriff vote weight must be 1.5
"""

from typing import Optional
from werewolf.engine.game_state import GameState
from werewolf.events.game_events import SheriffOutcome, SheriffOptOut, NightOutcome
from .types import ValidationViolation, ValidationSeverity


def validate_sheriff_election(
    event: SheriffOutcome,
    state: GameState,
) -> list[ValidationViolation]:
    """Validate sheriff election rules H.1-H.5.

    Args:
        event: Sheriff election outcome event
        state: Game state

    Returns:
        List of validation violations (empty if valid)
    """
    violations: list[ValidationViolation] = []

    # H.1-H.2: Sheriff only on Day 1
    if event.day != 1:
        violations.append(ValidationViolation(
            rule_id="H.1",
            category="Sheriff Election",
            message=f"Sheriff election on day {event.day} - must be Day 1 only",
            severity=ValidationSeverity.ERROR,
            context={"day": event.day, "expected_day": 1}
        ))

    # H.4: Sheriff candidates cannot vote
    for candidate in event.candidates:
        if candidate in event.votes and event.votes.get(candidate, 0) > 0:
            violations.append(ValidationViolation(
                rule_id="H.4",
                category="Sheriff Election",
                message=f"Candidate {candidate} voted in sheriff election - candidates cannot vote",
                severity=ValidationSeverity.ERROR,
                context={"candidate": candidate, "vote_count": event.votes.get(candidate)}
            ))

    # H.5: Sheriff vote weight must be 1.5
    for voter_seat, vote_count in event.votes.items():
        if vote_count != 1.5:
            violations.append(ValidationViolation(
                rule_id="H.5",
                category="Sheriff Election",
                message=f"Sheriff vote weight for voter {voter_seat} is {vote_count}, must be 1.5",
                severity=ValidationSeverity.ERROR,
                context={"voter": voter_seat, "vote_weight": vote_count, "expected_weight": 1.5}
            ))

    return violations


def validate_sheriff_opt_out(
    event: SheriffOptOut,
    state: GameState,
) -> list[ValidationViolation]:
    """Validate sheriff opt-out action.

    Args:
        event: Sheriff opt-out event
        state: Game state

    Returns:
        List of validation violations
    """
    violations: list[ValidationViolation] = []

    # H.1-H.2: Sheriff opt-out only on Day 1
    if event.day != 1:
        violations.append(ValidationViolation(
            rule_id="H.1",
            category="Sheriff Election",
            message=f"Sheriff opt-out on day {event.day} - must be Day 1 only",
            severity=ValidationSeverity.ERROR,
            context={"day": event.day, "expected_day": 1}
        ))

    return violations


def validate_night1_deaths_eligible_for_sheriff(
    night_outcome: NightOutcome,
    sheriff_candidates: list[int],
) -> list[ValidationViolation]:
    """Validate that Night 1 deaths are eligible for sheriff election.

    Args:
        night_outcome: Night resolution outcome with deaths
        sheriff_candidates: List of candidate seats for sheriff election

    Returns:
        List of validation violations
    """
    violations: list[ValidationViolation] = []

    # H.3: Night 1 deaths MUST be eligible for Sheriff
    if night_outcome.day == 1:
        for death_seat in night_outcome.deaths.keys():
            if death_seat not in sheriff_candidates:
                # This is informational - Night 1 deaths should be included
                violations.append(ValidationViolation(
                    rule_id="H.3",
                    category="Sheriff Election",
                    message=f"Night 1 death {death_seat} should be eligible for sheriff election",
                    severity=ValidationSeverity.WARNING,
                    context={"death_seat": death_seat, "sheriff_candidates": sheriff_candidates}
                ))

    return violations


__all__ = [
    'validate_sheriff_election',
    'validate_sheriff_opt_out',
    'validate_night1_deaths_eligible_for_sheriff'
]
