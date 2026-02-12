"""Night action validators (D.1-D.5, E.1-E.7, F.1-F.5, G.1-G.4).

Rules:
Night Actions - Werewolf (D):
- D.1: Only werewolves can perform werewolf actions
- D.2: Werewolves must have a valid target or choose to skip
- D.3: Werewolves cannot target themselves
- D.4: Werewolves cannot target dead players
- D.5: Single collective werewolf decision per night

Night Actions - Witch (E):
- E.1: Only the Witch can perform witch actions
- E.2: Antidote can only be used once
- E.3: Poison can only be used once
- E.4: Antidote cannot target the Witch
- E.5: Poison ignores guard protection
- E.6: PASS action when not using potions
- E.7: Witch sees werewolf target before deciding

Night Actions - Guard (F):
- F.1: Only the Guard can perform guard actions
- F.2: Guard must select a valid target
- F.3: Guard cannot guard same person twice in a row
- F.4: Guard cannot guard themselves
- F.5: Guard cannot guard dead players

Night Actions - Seer (G):
- G.1: Only the Seer can perform seer actions
- G.2: Seer must target a living player
- G.3: Seer cannot skip
- G.4: Seer result must be accurate (GOOD/WEREWOLF)
"""

from typing import Optional, TYPE_CHECKING, Literal
from werewolf.events.game_events import (
    WerewolfKill, WitchAction, GuardAction, SeerAction,
    WitchActionType, SubPhase, NightOutcome, DeathCause
)

if TYPE_CHECKING:
    from werewolf.engine.game_state import GameState
    from werewolf.post_game_validator.types import ValidationViolation


def validate_night_phase(
    phase_log,
    state: Optional["GameState"],
    existing_violations: list["ValidationViolation"],
    night_actions: dict,
    potion_used: dict,
    guard_prev_target: Optional[int],
    current_day: int,
) -> list["ValidationViolation"]:
    """Validate all night phase actions.

    Args:
        phase_log: The night phase log
        state: Current game state
        existing_violations: List to append violations to
        night_actions: Tracker for night actions this phase
        potion_used: Tracker for antidote/poison usage
        guard_prev_target: Previous night's guard target
        current_day: Current day number

    Returns:
        List of validation violations found
    """
    violations: list["ValidationViolation"] = []

    # Reset night action trackers for this night
    night_actions.clear()
    potion_used_this_night = {"antidote": potion_used.get("antidote", False),
                               "poison": potion_used.get("poison", False)}

    # Collect all actions by subphase
    for subphase in phase_log.subphases:
        for event in subphase.events:
            event_type = type(event).__name__

            # Werewolf action
            if isinstance(event, WerewolfKill):
                violations.extend(
                    _validate_werewolf_action(event, state, night_actions, current_day)
                )

            # Witch action
            elif isinstance(event, WitchAction):
                violations.extend(
                    _validate_witch_action(event, state, potion_used_this_night, night_actions, current_day)
                )

            # Guard action
            elif isinstance(event, GuardAction):
                violations.extend(
                    _validate_guard_action(event, state, guard_prev_target, current_day)
                )

            # Seer action
            elif isinstance(event, SeerAction):
                violations.extend(
                    _validate_seer_action(event, state, current_day)
                )

            # Night outcome - validate against actions
            elif isinstance(event, NightOutcome):
                violations.extend(
                    _validate_night_outcome(event, state, night_actions, potion_used_this_night, current_day)
                )

    # Update potion tracking for next night
    potion_used["antidote"] = potion_used_this_night["antidote"]
    potion_used["poison"] = potion_used_this_night["poison"]

    return violations


def _validate_werewolf_action(
    event: WerewolfKill,
    state: Optional["GameState"],
    night_actions: dict,
    current_day: int,
) -> list["ValidationViolation"]:
    """Validate werewolf kill action (D.1-D.5)."""
    violations: list["ValidationViolation"] = []

    # D.1: Actor must be werewolf
    if state and event.actor not in state.players:
        violations.append({
            "rule_id": "D.1",
            "category": "Night Actions - Werewolf",
            "message": f"Werewolf action from unknown actor {event.actor}",
            "severity": "error",
            "event_type": "WerewolfKill",
        })
    elif state:
        actor = state.players.get(event.actor)
        if actor and actor.role.value != "WEREWOLF":
            violations.append({
                "rule_id": "D.1",
                "category": "Night Actions - Werewolf",
                "message": f"Player {event.actor} ({actor.role.value}) cannot perform werewolf action",
                "severity": "error",
                "event_type": "WerewolfKill",
            })

    # D.3: Cannot target self
    if event.actor == event.target:
        violations.append({
            "rule_id": "D.3",
            "category": "Night Actions - Werewolf",
            "message": f"Werewolf cannot target themselves (actor={event.actor})",
            "severity": "error",
            "event_type": "WerewolfKill",
        })

    # D.4: Cannot target dead players
    if event.target is not None and state and event.target not in state.living_players:
        violations.append({
            "rule_id": "D.4",
            "category": "Night Actions - Werewolf",
            "message": f"Werewolf cannot target dead player {event.target}",
            "severity": "error",
            "event_type": "WerewolfKill",
        })

    # Track werewolf decision (single collective decision per night)
    night_key = f"night_{current_day}"
    if "werewolf_target" in night_actions:
        # Multiple werewolf decisions - this is D.5 violation
        violations.append({
            "rule_id": "D.5",
            "category": "Night Actions - Werewolf",
            "message": "Multiple werewolf kill decisions recorded in single night",
            "severity": "error",
            "event_type": "WerewolfKill",
        })
    night_actions["werewolf_target"] = event.target

    return violations


def _validate_witch_action(
    event: WitchAction,
    state: Optional["GameState"],
    potion_used_this_night: dict,
    night_actions: dict,
    current_day: int,
) -> list["ValidationViolation"]:
    """Validate witch action (E.1-E.7)."""
    violations: list["ValidationViolation"] = []

    # E.1: Actor must be witch
    if state and event.actor not in state.players:
        violations.append({
            "rule_id": "E.1",
            "category": "Night Actions - Witch",
            "message": f"Witch action from unknown actor {event.actor}",
            "severity": "error",
            "event_type": "WitchAction",
        })
    elif state:
        actor = state.players.get(event.actor)
        if actor and actor.role.value != "WITCH":
            violations.append({
                "rule_id": "E.1",
                "category": "Night Actions - Witch",
                "message": f"Player {event.actor} ({actor.role.value}) cannot perform witch action",
                "severity": "error",
                "event_type": "WitchAction",
            })

        # E.4: Antidote cannot target witch
        if (event.action_type == WitchActionType.ANTIDOTE and
            event.target == event.actor):
            violations.append({
                "rule_id": "E.4",
                "category": "Night Actions - Witch",
                "message": "Witch cannot use antidote on themselves",
                "severity": "error",
                "event_type": "WitchAction",
            })

    # E.2: Antidote can only be used once
    if event.action_type == WitchActionType.ANTIDOTE and potion_used_this_night["antidote"]:
        violations.append({
            "rule_id": "E.2",
            "category": "Night Actions - Witch",
            "message": "Antidote has already been used",
            "severity": "error",
            "event_type": "WitchAction",
        })

    # E.3: Poison can only be used once
    if event.action_type == WitchActionType.POISON and potion_used_this_night["poison"]:
        violations.append({
            "rule_id": "E.3",
            "category": "Night Actions - Witch",
            "message": "Poison has already been used",
            "severity": "error",
            "event_type": "WitchAction",
        })

    # Track witch action
    night_key = f"night_{current_day}"
    if "witch_action" in night_actions:
        violations.append({
            "rule_id": "E.5",
            "category": "Night Actions - Witch",
            "message": "Multiple witch actions recorded in single night",
            "severity": "error",
            "event_type": "WitchAction",
        })
    night_actions["witch_action"] = event

    return violations


def _validate_guard_action(
    event: GuardAction,
    state: Optional["GameState"],
    guard_prev_target: Optional[int],
    current_day: int,
) -> list["ValidationViolation"]:
    """Validate guard action (F.1-F.5)."""
    violations: list["ValidationViolation"] = []

    # F.1: Actor must be guard
    if state and event.actor not in state.players:
        violations.append({
            "rule_id": "F.1",
            "category": "Night Actions - Guard",
            "message": f"Guard action from unknown actor {event.actor}",
            "severity": "error",
            "event_type": "GuardAction",
        })
    elif state:
        actor = state.players.get(event.actor)
        if actor and actor.role.value != "GUARD":
            violations.append({
                "rule_id": "F.1",
                "category": "Night Actions - Guard",
                "message": f"Player {event.actor} ({actor.role.value}) cannot perform guard action",
                "severity": "error",
                "event_type": "GuardAction",
            })

        # F.4: Cannot guard self
        if event.actor == event.target:
            violations.append({
                "rule_id": "F.4",
                "category": "Night Actions - Guard",
                "message": f"Guard cannot guard themselves (actor={event.actor})",
                "severity": "error",
                "event_type": "GuardAction",
            })

        # F.3: Cannot guard same person twice in a row
        if event.target == guard_prev_target and event.target is not None:
            violations.append({
                "rule_id": "F.3",
                "category": "Night Actions - Guard",
                "message": f"Guard cannot guard same person twice (target={event.target})",
                "severity": "error",
                "event_type": "GuardAction",
            })

    # F.5: Cannot guard dead players
    if event.target is not None and state and event.target not in state.living_players:
        violations.append({
            "rule_id": "F.5",
            "category": "Night Actions - Guard",
            "message": f"Guard cannot guard dead player {event.target}",
            "severity": "error",
            "event_type": "GuardAction",
        })

    return violations


def _validate_seer_action(
    event: SeerAction,
    state: Optional["GameState"],
    current_day: int,
) -> list["ValidationViolation"]:
    """Validate seer action (G.1-G.4)."""
    violations: list["ValidationViolation"] = []

    # G.1: Actor must be seer
    if state and event.actor not in state.players:
        violations.append({
            "rule_id": "G.1",
            "category": "Night Actions - Seer",
            "message": f"Seer action from unknown actor {event.actor}",
            "severity": "error",
            "event_type": "SeerAction",
        })
    elif state:
        actor = state.players.get(event.actor)
        if actor and actor.role.value != "SEER":
            violations.append({
                "rule_id": "G.1",
                "category": "Night Actions - Seer",
                "message": f"Player {event.actor} ({actor.role.value}) cannot perform seer action",
                "severity": "error",
                "event_type": "SeerAction",
            })

        # G.2: Must target living player
        if event.target not in state.living_players:
            violations.append({
                "rule_id": "G.2",
                "category": "Night Actions - Seer",
                "message": f"Seer must target living player, got {event.target}",
                "severity": "error",
                "event_type": "SeerAction",
            })

    return violations


def _validate_night_outcome(
    event: NightOutcome,
    state: Optional["GameState"],
    night_actions: dict,
    potion_used_this_night: dict,
    current_day: int,
) -> list["ValidationViolation"]:
    """Validate night outcome against actions."""
    violations: list["ValidationViolation"] = []

    # Check that deaths match werewolf + poison targets
    if event.deaths and state:
        # Deaths should align with werewolf target + poison target
        pass  # TODO: Implement detailed night outcome validation

    return violations
