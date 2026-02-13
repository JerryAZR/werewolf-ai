"""Phase Order Validators (C.1-C.16).

Rules:
- C.1: Game must start with Night 1
- C.2: Day phases must follow Night phases (no consecutive Night)
- C.3: Sheriff election must run before DeathResolution on Day 1
- C.4: Night action order: Werewolves -> Witch -> Guard/Seer (parallel)
- C.5: NightResolution must be the last night subphase
- C.6: Night phase must contain WerewolfAction and NightResolution
- C.7: Campaign must be the first phase of Day 1
- C.8: Campaign cannot occur on Day 2+
- C.9: OptOut must follow Campaign IFF candidates exist
- C.10: Sheriff Election must follow OptOut IFF candidates remain
- C.11: Death Resolution must precede Discussion
- C.12: Discussion must precede Voting
- C.13: Banishment Resolution must follow Voting IFF (banishment occurred)
- C.14: Banishment Resolution cannot occur IFF (tie vote)
- C.15: Game must end after 20 days maximum
- C.16: WerewolfAction should make exactly one collective decision (not multiple votes)
"""

from typing import Optional
from werewolf.engine.game_state import GameState
from werewolf.events.game_events import Phase, SubPhase
from .types import ValidationViolation, ValidationSeverity


def validate_game_start(
    current_phase: Phase,
    day: int,
) -> list[ValidationViolation]:
    """Validate C.1: Game must start with Night 1.

    Args:
        current_phase: The starting phase
        day: The current day number

    Returns:
        List of validation violations
    """
    violations: list[ValidationViolation] = []

    if day == 1 and current_phase != Phase.NIGHT:
        violations.append(ValidationViolation(
            rule_id="C.1",
            category="Phase Order",
            message=f"Game must start with Night 1, got {current_phase.value}",
            severity=ValidationSeverity.ERROR,
            context={"phase": current_phase.value, "day": day}
        ))

    return violations


def validate_phase_transition(
    current_phase: Phase,
    previous_phase: Optional[Phase],
    day: int,
) -> list[ValidationViolation]:
    """Validate phase transition rules C.1-C.2.

    Args:
        current_phase: The phase we're entering
        previous_phase: The phase we just left
        day: Current day number

    Returns:
        List of validation violations (empty if valid)
    """
    violations: list[ValidationViolation] = []

    # C.1: Game starts with Night 1 (checked at game start)
    if previous_phase is None and day == 1:
        if current_phase != Phase.NIGHT:
            violations.append(ValidationViolation(
                rule_id="C.1",
                category="Phase Order",
                message=f"First phase must be Night 1, got {current_phase.value}",
                severity=ValidationSeverity.ERROR,
                context={"phase": current_phase.value}
            ))

    # C.2: No consecutive Night phases
    if previous_phase == Phase.NIGHT and current_phase == Phase.NIGHT:
        violations.append(ValidationViolation(
            rule_id="C.2",
            category="Phase Order",
            message="Consecutive Night phases detected",
            severity=ValidationSeverity.ERROR,
            context={"previous": previous_phase.value, "current": current_phase.value}
        ))

    return violations


def validate_phase_order(
    current_phase: Phase,
    previous_phase: Optional[Phase],
    state: GameState,
) -> list[ValidationViolation]:
    """Validate phase ordering rules C.1-C.15.

    Args:
        current_phase: The phase we're entering
        previous_phase: The phase we just left
        state: Game state

    Returns:
        List of validation violations (empty if valid)
    """
    violations: list[ValidationViolation] = []

    # C.15: Max 20 days
    if state.day > 20:
        violations.append(ValidationViolation(
            rule_id="C.15",
            category="Phase Order",
            message=f"Game exceeded 20 days (day={state.day})",
            severity=ValidationSeverity.ERROR,
            context={"day": state.day}
        ))

    # C.2: No consecutive Night phases
    if previous_phase == Phase.NIGHT and current_phase == Phase.NIGHT:
        violations.append(ValidationViolation(
            rule_id="C.2",
            category="Phase Order",
            message="Consecutive Night phases detected",
            severity=ValidationSeverity.ERROR,
            context={"previous": previous_phase.value, "current": current_phase.value}
        ))

    return violations


def validate_night_subphase_order(
    completed_subphases: set[SubPhase],
    current_subphase: SubPhase,
) -> list[ValidationViolation]:
    """Validate night subphase ordering C.4-C.6.

    Args:
        completed_subphases: Subphases already completed this night
        current_subphase: Subphase we're entering

    Returns:
        List of validation violations
    """
    violations: list[ValidationViolation] = []

    # C.4: Night action order: Werewolf -> Witch -> Guard/Seer (parallel)
    # Guard and Seer can happen in any order or parallel
    valid_order = [
        SubPhase.WEREWOLF_ACTION,
        SubPhase.WITCH_ACTION,
        SubPhase.GUARD_ACTION,
        SubPhase.SEER_ACTION,
        SubPhase.NIGHT_RESOLUTION,
    ]

    # Check if we're jumping ahead
    current_index = valid_order.index(current_subphase) if current_subphase in valid_order else -1

    for completed in completed_subphases:
        if completed in valid_order:
            completed_index = valid_order.index(completed)
            if completed_index > current_index:
                violations.append(ValidationViolation(
                    rule_id="C.4",
                    category="Phase Order",
                    message=f"Subphase {current_subphase.value} before {completed.value}",
                    severity=ValidationSeverity.ERROR,
                    context={
                        "current": current_subphase.value,
                        "completed": completed.value
                    }
                ))

    # C.5: NightResolution must be the last night subphase
    if current_subphase != SubPhase.NIGHT_RESOLUTION:
        if SubPhase.NIGHT_RESOLUTION in completed_subphases:
            violations.append(ValidationViolation(
                rule_id="C.5",
                category="Phase Order",
                message="NightResolution must be the last night subphase",
                severity=ValidationSeverity.ERROR,
                context={"current": current_subphase.value, "completed": list(completed_subphases)}
            ))

    return violations


def validate_night_phase_completion(
    completed_subphases: set[SubPhase],
) -> list[ValidationViolation]:
    """Validate C.6: Night phase must contain WerewolfAction and NightResolution.

    Args:
        completed_subphases: All subphases completed during the night

    Returns:
        List of validation violations
    """
    violations: list[ValidationViolation] = []

    # C.6: Night must contain WerewolfAction and NightResolution
    if SubPhase.WEREWOLF_ACTION not in completed_subphases:
        violations.append(ValidationViolation(
            rule_id="C.6",
            category="Phase Order",
            message="Night phase must contain WerewolfAction subphase",
            severity=ValidationSeverity.ERROR,
            context={"completed": list(completed_subphases)}
        ))

    if SubPhase.NIGHT_RESOLUTION not in completed_subphases:
        violations.append(ValidationViolation(
            rule_id="C.6",
            category="Phase Order",
            message="Night phase must contain NightResolution subphase",
            severity=ValidationSeverity.ERROR,
            context={"completed": list(completed_subphases)}
        ))

    return violations


def validate_day_subphase_order(
    completed_subphases: set[SubPhase],
    current_subphase: SubPhase,
    day: int,
    has_candidates: bool,
    has_opted_out: bool,
    has_sheriff_candidates: bool,
) -> list[ValidationViolation]:
    """Validate day subphase ordering C.7-C.14.

    Args:
        completed_subphases: Subphases already completed today
        current_subphase: Subphase we're entering
        day: Current day number
        has_candidates: Whether sheriff candidates exist after campaign
        has_opted_out: Whether opt-out phase completed
        has_sheriff_candidates: Whether sheriff candidates remain after opt-out

    Returns:
        List of validation violations
    """
    violations: list[ValidationViolation] = []

    # C.7: Campaign must be the first phase of Day 1 (or follow NOMINATION)
    if day == 1 and current_subphase == SubPhase.CAMPAIGN:
        invalid_predecessors = completed_subphases - {SubPhase.NOMINATION}
        if invalid_predecessors:
            violations.append(ValidationViolation(
                rule_id="C.7",
                category="Phase Order",
                message="Campaign must be the first subphase of Day 1 (or follow NOMINATION)",
                severity=ValidationSeverity.ERROR,
                context={"completed": list(completed_subphases)}
            ))

    # C.8: Campaign cannot occur on Day 2+
    if current_subphase == SubPhase.CAMPAIGN and day > 1:
        violations.append(ValidationViolation(
            rule_id="C.8",
            category="Phase Order",
            message=f"Campaign on day {day} - only allowed on Day 1",
            severity=ValidationSeverity.ERROR,
            context={"day": day}
        ))

    # C.9: OptOut must follow Campaign or NOMINATION IFF candidates exist
    if current_subphase == SubPhase.OPT_OUT:
        allowed_predecessors = {SubPhase.CAMPAIGN, SubPhase.NOMINATION}
        if not allowed_predecessors.intersection(completed_subphases):
            violations.append(ValidationViolation(
                rule_id="C.9",
                category="Phase Order",
                message="OptOut must follow Campaign or NOMINATION",
                severity=ValidationSeverity.ERROR,
                context={"completed": list(completed_subphases)}
            ))
        if not has_candidates:
            violations.append(ValidationViolation(
                rule_id="C.9",
                category="Phase Order",
                message="OptOut should not occur when no candidates exist",
                severity=ValidationSeverity.WARNING,
                context={"has_candidates": has_candidates}
            ))

    # C.10: Sheriff Election must follow OptOut IFF candidates remain
    if current_subphase == SubPhase.SHERIFF_ELECTION:
        allowed_predecessors = {SubPhase.OPT_OUT, SubPhase.CAMPAIGN, SubPhase.NOMINATION}
        if not allowed_predecessors.intersection(completed_subphases):
            violations.append(ValidationViolation(
                rule_id="C.10",
                category="Phase Order",
                message="Sheriff Election must follow OptOut, Campaign, or NOMINATION",
                severity=ValidationSeverity.ERROR,
                context={"completed": list(completed_subphases)}
            ))
        if not has_sheriff_candidates:
            violations.append(ValidationViolation(
                rule_id="C.10",
                category="Phase Order",
                message="Sheriff Election should not occur when no candidates remain after opt-out",
                severity=ValidationSeverity.WARNING,
                context={"has_sheriff_candidates": has_sheriff_candidates}
            ))

    # C.11: Death Resolution must precede Discussion
    if current_subphase == SubPhase.DISCUSSION:
        if SubPhase.DEATH_RESOLUTION not in completed_subphases:
            violations.append(ValidationViolation(
                rule_id="C.11",
                category="Phase Order",
                message="Death Resolution must precede Discussion",
                severity=ValidationSeverity.ERROR,
                context={"completed": list(completed_subphases)}
            ))

    # C.12: Discussion must precede Voting
    if current_subphase == SubPhase.VOTING:
        if SubPhase.DISCUSSION not in completed_subphases:
            violations.append(ValidationViolation(
                rule_id="C.12",
                category="Phase Order",
                message="Discussion must precede Voting",
                severity=ValidationSeverity.ERROR,
                context={"completed": list(completed_subphases)}
            ))

    return violations


def validate_day_1_sheriff_order(
    completed_subphases: set[SubPhase],
    day: int,
) -> list[ValidationViolation]:
    """Validate C.3: Sheriff election must run before DeathResolution on Day 1.

    Args:
        completed_subphases: Subphases already completed today
        day: Current day number

    Returns:
        List of validation violations
    """
    violations: list[ValidationViolation] = []

    if day != 1:
        return violations

    # C.3: Sheriff election must run before DeathResolution on Day 1
    if SubPhase.DEATH_RESOLUTION in completed_subphases:
        if SubPhase.SHERIFF_ELECTION not in completed_subphases:
            violations.append(ValidationViolation(
                rule_id="C.3",
                category="Phase Order",
                message="Sheriff Election must run before DeathResolution on Day 1",
                severity=ValidationSeverity.ERROR,
                context={"completed": list(completed_subphases)}
            ))

    return violations


def validate_banishment_resolution(
    was_tie: bool,
    banishment_occurred: bool,
) -> list[ValidationViolation]:
    """Validate C.13-C.14: Banishment Resolution rules.

    Args:
        was_tie: Whether the vote was a tie
        banishment_occurred: Whether a banishment actually happened

    Returns:
        List of validation violations
    """
    violations: list[ValidationViolation] = []

    # C.13: Banishment Resolution must follow Voting IFF banishment occurred
    if not banishment_occurred and not was_tie:
        violations.append(ValidationViolation(
            rule_id="C.13",
            category="Phase Order",
            message="Banishment Resolution should only occur when banishment occurred",
            severity=ValidationSeverity.WARNING,
            context={"was_tie": was_tie, "banishment_occurred": banishment_occurred}
        ))

    # C.14: Banishment Resolution cannot occur IFF tie vote
    if was_tie and banishment_occurred:
        violations.append(ValidationViolation(
            rule_id="C.14",
            category="Phase Order",
            message="Banishment Resolution cannot occur on tie vote",
            severity=ValidationSeverity.ERROR,
            context={"was_tie": was_tie}
        ))

    return violations


def validate_werewolf_single_query(
    events: list["GameEvent"],
) -> list[ValidationViolation]:
    """Validate C.16: WerewolfAction should make exactly one collective decision.

    Per RULES.md: "Werewolves make a collective decision via a single AI call."
    The handler should query ONE representative werewolf (human priority, then lowest seat),
    not tally individual votes from all werewolves.

    Args:
        events: Events from the WerewolfAction subphase

    Returns:
        List of validation violations
    """
    import json
    from werewolf.events.game_events import WerewolfKill

    violations: list[ValidationViolation] = []

    for event in events:
        if isinstance(event, WerewolfKill) and event.debug_info:
            try:
                debug = json.loads(event.debug_info)
                if "target_votes" in debug:
                    vote_count = len(debug["target_votes"])
                    if vote_count > 1:
                        violations.append(ValidationViolation(
                            rule_id="C.16",
                            category="Phase Order",
                            message=f"WerewolfAction made {vote_count} individual queries instead of 1 collective decision",
                            severity=ValidationSeverity.ERROR,
                            context={"vote_count": vote_count, "werewolf_seats": debug.get("werewolf_seats")}
                        ))
            except (json.JSONDecodeError, TypeError):
                pass

    return violations


__all__ = [
    'validate_game_start',
    'validate_phase_transition',
    'validate_phase_order',
    'validate_night_subphase_order',
    'validate_night_phase_completion',
    'validate_day_subphase_order',
    'validate_day_1_sheriff_order',
    'validate_werewolf_single_query',
    'validate_banishment_resolution',
    'validate_subphase_phase_match',
]


# Subphases that belong to NIGHT phase
NIGHT_SUBPHASES = {
    SubPhase.WEREWOLF_ACTION,
    SubPhase.WITCH_ACTION,
    SubPhase.GUARD_ACTION,
    SubPhase.SEER_ACTION,
    SubPhase.NIGHT_RESOLUTION,
}

# Subphases that belong to DAY phase
DAY_SUBPHASES = {
    SubPhase.NOMINATION,
    SubPhase.CAMPAIGN,
    SubPhase.OPT_OUT,
    SubPhase.SHERIFF_ELECTION,
    SubPhase.DEATH_RESOLUTION,
    SubPhase.DISCUSSION,
    SubPhase.VOTING,
    SubPhase.BANISHMENT_RESOLUTION,
}


def validate_subphase_phase_match(
    phase: Phase,
    subphase: SubPhase,
) -> list[ValidationViolation]:
    """Validate that subphase belongs to the correct phase.

    This catches bugs where a handler passes the wrong micro_phase to
    SubPhaseLog (e.g., NIGHT_RESOLUTION appearing in DAY phase).

    Args:
        phase: The phase (NIGHT or DAY)
        subphase: The subphase being added

    Returns:
        List of validation violations
    """
    violations: list[ValidationViolation] = []

    if phase == Phase.NIGHT and subphase in DAY_SUBPHASES:
        violations.append(ValidationViolation(
            rule_id="C.17",
            category="Phase Order",
            message=f"DAY subphase {subphase.value} appeared in NIGHT phase - handler bug",
            severity=ValidationSeverity.ERROR,
            context={"phase": phase.value, "subphase": subphase.value}
        ))

    elif phase == Phase.DAY and subphase in NIGHT_SUBPHASES:
        violations.append(ValidationViolation(
            rule_id="C.17",
            category="Phase Order",
            message=f"NIGHT subphase {subphase.value} appeared in DAY phase - handler bug",
            severity=ValidationSeverity.ERROR,
            context={"phase": phase.value, "subphase": subphase.value}
        ))

    return violations
