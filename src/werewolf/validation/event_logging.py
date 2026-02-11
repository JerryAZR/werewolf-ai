"""Event Logging Validators (N.1-N.6).

Rules:
- N.1: Every subphase must produce a SubPhaseLog
- N.2: Every phase must produce a PhaseLog
- N.3: GameStart event must be recorded
- N.4: GameOver event must be recorded with winner
- N.5: NightOutcome must record deaths
- N.6: All player actions must be logged as events
"""

from typing import Optional
from werewolf.engine.event_collector import EventCollector
from werewolf.events.game_events import (
    Phase,
    SubPhase,
    GameStart,
    GameOver,
    NightOutcome,
    CharacterAction,
)
from .types import ValidationViolation, ValidationSeverity


def validate_event_logging(
    collector: EventCollector,
    phase: Phase,
    day: int,
) -> list[ValidationViolation]:
    """Validate event logging rules N.1-N.6.

    Args:
        collector: Event collector containing all logged events
        phase: Current phase
        day: Current day number

    Returns:
        List of validation violations (empty if valid)
    """
    violations: list[ValidationViolation] = []
    event_log = collector._event_log

    # N.2: Every phase must produce a PhaseLog
    if not event_log.phases:
        violations.append(ValidationViolation(
            rule_id="N.2",
            category="Event Logging",
            message="No PhaseLogs recorded in event log",
            severity=ValidationSeverity.ERROR,
            context={"phase": phase.value, "day": day}
        ))

    # N.3: GameStart must be recorded
    if event_log.game_start is None:
        violations.append(ValidationViolation(
            rule_id="N.3",
            category="Event Logging",
            message="GameStart event not recorded",
            severity=ValidationSeverity.ERROR,
            context={"phase": phase.value, "day": day}
        ))

    # N.4: GameOver must be recorded with winner
    if phase == Phase.GAME_OVER:
        if event_log.game_over is None:
            violations.append(ValidationViolation(
                rule_id="N.4",
                category="Event Logging",
                message="GameOver event not recorded",
                severity=ValidationSeverity.ERROR,
                context={"phase": phase.value, "day": day}
            ))
        elif event_log.game_over.winner is None:
            violations.append(ValidationViolation(
                rule_id="N.4",
                category="Event Logging",
                message="GameOver event missing winner information",
                severity=ValidationSeverity.ERROR,
                context={"phase": phase.value, "day": day}
            ))

    # N.6: All player actions must be logged as events
    actions = [e for e in collector.get_events() if isinstance(e, CharacterAction)]
    if not actions and day > 0:
        violations.append(ValidationViolation(
            rule_id="N.6",
            category="Event Logging",
            message="No player actions recorded",
            severity=ValidationSeverity.WARNING,
            context={"phase": phase.value, "day": day}
        ))

    return violations


def validate_phase_logging(
    collector: EventCollector,
    phase: Phase,
    day: int,
) -> list[ValidationViolation]:
    """Validate phase logging N.1-N.2.

    Args:
        collector: Event collector containing all logged events
        phase: Current phase to validate
        day: Current day number

    Returns:
        List of validation violations
    """
    violations: list[ValidationViolation] = []
    event_log = collector._event_log

    # N.2: Every phase must produce a PhaseLog
    phase_log = None
    for pl in event_log.phases:
        if pl.kind == phase and pl.number == day:
            phase_log = pl
            break

    if phase_log is None:
        violations.append(ValidationViolation(
            rule_id="N.2",
            category="Event Logging",
            message=f"No PhaseLog found for phase={phase.value}, day={day}",
            severity=ValidationSeverity.ERROR,
            context={"phase": phase.value, "day": day}
        ))
        return violations  # Cannot validate N.1 without phase log

    # N.1: Every subphase must produce a SubPhaseLog
    if not phase_log.subphases:
        violations.append(ValidationViolation(
            rule_id="N.1",
            category="Event Logging",
            message=f"No SubPhaseLogs recorded for phase={phase.value}, day={day}",
            severity=ValidationSeverity.ERROR,
            context={"phase": phase.value, "day": day, "phase_log": phase_log.model_dump()}
        ))

    return violations


def validate_night_outcome(
    collector: EventCollector,
    phase: Phase,
    day: int,
) -> list[ValidationViolation]:
    """Validate night outcome logging N.5.

    Args:
        collector: Event collector containing all logged events
        phase: Current phase (should be NIGHT)
        day: Current day number

    Returns:
        List of validation violations
    """
    violations: list[ValidationViolation] = []
    event_log = collector._event_log

    # N.5: NightOutcome must record deaths
    if phase == Phase.NIGHT and day > 0:
        # Get all night resolution subphases for this day
        for phase_log in event_log.phases:
            if phase_log.kind == Phase.NIGHT and phase_log.number == day:
                night_outcomes = [
                    e for e in phase_log.get_events()
                    if isinstance(e, NightOutcome)
                ]
                if not night_outcomes:
                    violations.append(ValidationViolation(
                        rule_id="N.5",
                        category="Event Logging",
                        message="NightOutcome event not recorded for night phase",
                        severity=ValidationSeverity.ERROR,
                        context={"phase": phase.value, "day": day}
                    ))
                else:
                    # Verify NightOutcome contains death information
                    for outcome in night_outcomes:
                        if outcome.deaths is None:
                            violations.append(ValidationViolation(
                                rule_id="N.5",
                                category="Event Logging",
                                message="NightOutcome missing deaths information",
                                severity=ValidationSeverity.ERROR,
                                context={"phase": phase.value, "day": day}
                            ))

    return violations


def validate_action_logging(
    collector: EventCollector,
    phase: Phase,
    day: int,
    expected_actions: Optional[list[int]] = None,
) -> list[ValidationViolation]:
    """Validate N.6: All player actions must be logged as events.

    Args:
        collector: Event collector containing all logged events
        phase: Current phase
        day: Current day number
        expected_actions: List of actor seats expected to act this phase (optional)

    Returns:
        List of validation violations
    """
    violations: list[ValidationViolation] = []
    all_events = collector.get_events()

    # Get events for current phase/day
    phase_events = [
        e for e in all_events
        if e.phase == phase and e.day == day
    ]

    # Get character actions for this phase
    character_actions = [e for e in phase_events if isinstance(e, CharacterAction)]

    # N.6: All player actions must be logged as events
    if expected_actions is not None:
        actors_with_actions = set(e.actor for e in character_actions)
        expected_actors = set(expected_actions)
        missing_actors = expected_actors - actors_with_actions

        if missing_actors:
            violations.append(ValidationViolation(
                rule_id="N.6",
                category="Event Logging",
                message=f"Player actions not logged for actors: {sorted(missing_actors)}",
                severity=ValidationSeverity.ERROR,
                context={
                    "phase": phase.value,
                    "day": day,
                    "expected_actors": list(expected_actors),
                    "logged_actors": list(actors_with_actions)
                }
            ))

    return violations


__all__ = [
    'validate_event_logging',
    'validate_phase_logging',
    'validate_night_outcome',
    'validate_action_logging',
]
