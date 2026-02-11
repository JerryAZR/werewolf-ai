"""Interactive TUI module for human players.

Provides:
- ChoiceSpec: Structured choice specifications for TUI rendering
- PromptSession: Multi-step prompt flows
- InteractiveParticipant: Rich-based interactive player
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

from .prompt_session import (
    PromptSession,
    PromptStep,
    PromptOption,
    PromptType,
    witch_action_session,
    guard_action_session,
    voting_session,
    sheriff_vote_session,
    opt_out_session,
)

from .interactive import (
    InteractiveParticipant,
    create_interactive_participant,
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
    # Prompt Session
    "PromptSession",
    "PromptStep",
    "PromptOption",
    "PromptType",
    "witch_action_session",
    "guard_action_session",
    "voting_session",
    "sheriff_vote_session",
    "opt_out_session",
    # Interactive Participant
    "InteractiveParticipant",
    "create_interactive_participant",
    # Textual Arrow Key Selection
    "select_with_arrows",
    "select_seat",
    "select_action",
    "confirm_yes_no",
]
