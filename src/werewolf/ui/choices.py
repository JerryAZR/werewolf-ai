"""Choice specifications for interactive TUI.

Defines structured choice options that handlers can provide for TUI rendering.
"""

from enum import Enum
from typing import Optional, Union
from pydantic import BaseModel, Field


class ChoiceType(str, Enum):
    """Type of choice interaction."""
    SINGLE = "single"  # Select one from a list
    SEAT = "seat"      # Select a player seat (0-11)
    BOOLEAN = "bool"   # Yes/No type choice
    COMMAND = "command"  # Type a command string


class ChoiceOption(BaseModel):
    """A single choice option for TUI rendering."""
    value: str          # The value returned when selected
    display: str        # Text shown to user (can include formatting)
    seat_hint: Optional[int] = None  # If this is a seat choice, which seat


class ChoiceSpec(BaseModel):
    """Specification for interactive TUI choices.

    Handlers provide this to tell the TUI what options to present.
    """
    choice_type: ChoiceType
    prompt: str         # Question to ask the user
    options: list[ChoiceOption] = Field(default_factory=list)
    allow_none: bool = False  # Allow "skip", "pass", "abstain"
    none_display: str = "Skip / Pass / Abstain"
    max_select: int = 1  # For multi-select (future use)
    seat_info: Optional[dict[int, str]] = None  # seat -> display name

    def get_option_by_value(self, value: str) -> Optional[ChoiceOption]:
        """Find option by its value."""
        for opt in self.options:
            if opt.value == value:
                return opt
        return None

    def get_seat_display(self, seat: int) -> str:
        """Get display name for a seat."""
        if self.seat_info and seat in self.seat_info:
            return f"Player {seat} ({self.seat_info[seat]})"
        return f"Player {seat}"

    def format_response(self, raw_input: str) -> str:
        """Format raw user input into handler-compatible response.

        Args:
            raw_input: What the user selected/typed

        Returns:
            String formatted for handler parsing
        """
        if self.choice_type == ChoiceType.SEAT:
            # Validate seat number
            try:
                seat = int(raw_input)
                if 0 <= seat <= 11:
                    return str(seat)
            except ValueError:
                pass
            return raw_input

        elif self.choice_type == ChoiceType.BOOLEAN:
            lower = raw_input.lower()
            if lower in ["y", "yes", "true", "1"]:
                return "yes"
            elif lower in ["n", "no", "false", "0"]:
                return "no"
            return raw_input

        elif self.choice_type == ChoiceType.COMMAND:
            return raw_input.upper()

        else:  # SINGLE
            opt = self.get_option_by_value(raw_input)
            if opt:
                return opt.value
            return raw_input


# ============================================================================
# Builder helpers for common choice patterns
# ============================================================================

def make_seat_choice(
    prompt: str,
    seats: list[int],
    seat_info: Optional[dict[int, str]] = None,
    allow_none: bool = True,
) -> ChoiceSpec:
    """Create a seat selection choice.

    Args:
        prompt: Question to ask
        seats: Available seat numbers
        seat_info: Optional seat -> role/name info
        allow_none: Allow skipping
    """
    options = []
    for seat in seats:
        display = f"Player {seat}"
        if seat_info and seat in seat_info:
            display = f"Player {seat} ({seat_info[seat]})"
        options.append(ChoiceOption(value=str(seat), display=display, seat_hint=seat))

    return ChoiceSpec(
        choice_type=ChoiceType.SEAT,
        prompt=prompt,
        options=options,
        allow_none=allow_none,
        none_display="Skip / Pass",
        seat_info=seat_info or {},
    )


def make_action_choice(
    prompt: str,
    actions: list[tuple[str, str]],  # (value, display)
    allow_none: bool = True,
) -> ChoiceSpec:
    """Create a single-choice action selector.

    Args:
        prompt: Question to ask
        actions: List of (value, display_name) tuples
        allow_none: Allow skipping
    """
    options = [
        ChoiceOption(value=value, display=display)
        for value, display in actions
    ]

    # Only include none_display if allow_none is True
    kwargs = {
        "choice_type": ChoiceType.SINGLE,
        "prompt": prompt,
        "options": options,
        "allow_none": allow_none,
    }
    if allow_none:
        kwargs["none_display"] = "Pass / Skip"

    return ChoiceSpec(**kwargs)


def make_yes_no_choice(prompt: str) -> ChoiceSpec:
    """Create a yes/no choice."""
    return ChoiceSpec(
        choice_type=ChoiceType.BOOLEAN,
        prompt=prompt,
        options=[
            ChoiceOption(value="yes", display="Yes"),
            ChoiceOption(value="no", display="No"),
        ],
        allow_none=False,
    )


__all__ = [
    "ChoiceSpec",
    "ChoiceOption",
    "ChoiceType",
    "make_seat_choice",
    "make_action_choice",
    "make_yes_no_choice",
]
