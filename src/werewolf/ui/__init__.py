"""Interactive TUI module for human players.

Provides:
- ChoiceSpec: Structured choice specifications for TUI rendering
- Arrow key selection via Textual
"""

from .choices import (
    ChoiceSpec,
    ChoiceOption,
    ChoiceType,
    make_seat_choice,
    make_action_choice,
    make_yes_no_choice,
)

from .textual_selector import (
    select_with_arrows,
    select_seat,
    select_action,
    confirm_yes_no,
)

__all__ = [
    # Choices
    "ChoiceSpec",
    "ChoiceOption",
    "ChoiceType",
    "make_seat_choice",
    "make_action_choice",
    "make_yes_no_choice",
    # Textual Arrow Key Selection
    "select_with_arrows",
    "select_seat",
    "select_action",
    "confirm_yes_no",
]
