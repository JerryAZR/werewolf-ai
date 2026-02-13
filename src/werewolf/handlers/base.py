"""Shared base types for Werewolf game handlers.

This module contains common types that are duplicated across all handler files:
- SubPhaseLog: Generic subphase container with events
- HandlerResult: Output from handlers containing all events from a subphase
- Participant Protocol: Interface for AI/human players
- MaxRetriesExceededError: Exception raised when max retries are exceeded

These types are extracted here to eliminate code duplication (~400+ lines)
and ensure consistency across all 12 handler files.
"""

from typing import Protocol, Any, Optional

from pydantic import BaseModel, Field

from werewolf.events.game_events import SubPhase, GameEvent


# ============================================================================
# Shared Handler Result Types
# ============================================================================


class SubPhaseLog(BaseModel):
    """Generic subphase container with events.

    All handlers return a SubPhaseLog containing the micro_phase identifier
    and a list of game events produced during this subphase.
    """

    micro_phase: SubPhase
    events: list[GameEvent] = Field(default_factory=list)


class HandlerResult(BaseModel):
    """Output from handlers containing all events from a subphase.

    The HandlerResult is the primary return type from all handler __call__
    methods. It contains:
    - subphase_log: The SubPhaseLog with all events from this subphase
    - debug_info: Optional debug information for troubleshooting
    """

    subphase_log: SubPhaseLog
    debug_info: Optional[str] = None


# ============================================================================
# Participant Protocol
# ============================================================================


class Participant(Protocol):
    """A player (AI or human) that can make decisions.

    The handler queries participants for their decisions during subphases.
    Participants return raw strings - handlers are responsible for parsing
    and validation.

    For interactive TUI play, handlers may provide a ChoiceSpec to guide
    the participant's decision-making with structured choices.
    """

    async def decide(
        self,
        system_prompt: str,
        user_prompt: str,
        hint: Optional[str] = None,
        choices: Optional[Any] = None,
    ) -> str:
        """Make a decision and return raw response string.

        Args:
            system_prompt: System instructions defining the role/constraints
            user_prompt: User prompt with current game state
            hint: Optional hint for invalid previous attempts
            choices: Optional ChoiceSpec for interactive TUI selection

        Returns:
            Raw response string to be parsed by the handler
        """
        ...


# ============================================================================
# Shared Exceptions
# ============================================================================


class MaxRetriesExceededError(Exception):
    """Raised when max retries are exceeded during action validation.

    Handlers implement retry logic (typically up to 3 attempts) when parsing
    or validating player actions. This exception is raised when all retries
    are exhausted without receiving valid input.
    """

    pass
