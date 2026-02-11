"""Werewolf validation module.

This module provides comprehensive runtime validation for game rules.
Each rule category has its own validation file for clear separation.

Files:
- types.py: Shared ValidationViolation, ValidationResult, ValidationSeverity
- exceptions.py: ValidationError exception
- state_consistency.py: M.1-M.7 state invariant checks
- initialization.py: B.1-B.4 game initialization checks
- victory.py: A.1-A.5 victory condition checks
- night_werewolf.py: D.1-D.2 werewolf action checks
- night_witch.py: E.1-E.7 witch action checks
- night_guard.py: F.1-F.3 guard action checks
- night_seer.py: G.1-G.2 seer action checks
- day_sheriff.py: H.1-H.5 sheriff election checks
- day_death.py: I.1-I.9 death resolution checks
- day_voting.py: J.1-J.2 voting checks
- hunter.py: K.1-K.4 hunter action checks
- badge_transfer.py: L.1-L.4 badge transfer checks
- phase_order.py: C.1-C.15 phase ordering checks
- event_logging.py: N.1-N.6 event logging checks
"""

from .types import ValidationResult, ValidationViolation, ValidationSeverity
from .exceptions import ValidationError

# State consistency
from .state_consistency import validate_state_consistency

# Game lifecycle
from .initialization import validate_game_start
from .victory import check_victory, validate_victory

# Night actions
from .night_werewolf import validate_werewolf_action
from .night_witch import validate_witch_action
from .night_guard import validate_guard_action
from .night_seer import validate_seer_action

# Day actions
from .day_sheriff import validate_sheriff_election, validate_sheriff_opt_out
from .day_death import validate_death_resolution, validate_death_announcement
from .day_voting import validate_vote, validate_banishment
from .hunter import validate_hunter_action, validate_hunter_death_chain
from .badge_transfer import validate_badge_transfer, validate_no_duplicate_sheriff

# Phase and logging
from .phase_order import (
    validate_phase_order,
    validate_night_subphase_order,
    validate_day_subphase_order,
)
from .event_logging import (
    validate_event_logging,
    validate_phase_logging,
    validate_night_outcome,
)

__all__ = [
    # Types and exceptions
    "ValidationResult",
    "ValidationViolation",
    "ValidationSeverity",
    "ValidationError",
    # State consistency
    "validate_state_consistency",
    # Game lifecycle
    "validate_game_start",
    "check_victory",
    "validate_victory",
    # Night actions
    "validate_werewolf_action",
    "validate_witch_action",
    "validate_guard_action",
    "validate_seer_action",
    # Day actions
    "validate_sheriff_election",
    "validate_sheriff_opt_out",
    "validate_death_resolution",
    "validate_death_announcement",
    "validate_vote",
    "validate_banishment",
    "validate_hunter_action",
    "validate_hunter_death_chain",
    "validate_badge_transfer",
    "validate_no_duplicate_sheriff",
    # Phase and logging
    "validate_phase_order",
    "validate_night_subphase_order",
    "validate_day_subphase_order",
    "validate_event_logging",
    "validate_phase_logging",
    "validate_night_outcome",
]
