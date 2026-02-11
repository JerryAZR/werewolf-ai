"""Interactive prompt session for multi-step TUI decisions.

Provides a clean API for handlers to define choice flows that
InteractiveParticipant can render interactively.
"""

from enum import Enum
from typing import Optional, Callable, Any
from pydantic import BaseModel, Field


class PromptType(str, Enum):
    """Type of prompt."""
    ACTION = "action"  # Choose from action types (PASS, ANTIDOTE, etc.)
    SEAT = "seat"      # Choose a player seat
    VOTE = "vote"      # Vote for a candidate
    TEXT = "text"      # Free-form text input
    CONFIRM = "confirm"  # Yes/No confirmation


class PromptOption(BaseModel):
    """A single option in a prompt."""
    value: str          # Returned when selected
    display: str        # Shown to user
    seat_hint: Optional[int] = None  # Associated seat (if any)


class PromptStep(BaseModel):
    """A single step in a multi-step prompt."""
    prompt_type: PromptType
    prompt_text: str
    options: list[PromptOption] = Field(default_factory=list)
    allow_none: bool = False
    none_display: str = "Skip / Pass"
    seat_info: dict[int, str] = Field(default_factory=dict)
    validator: Optional[Callable[[str], tuple[bool, str]]] = None  # (is_valid, error_msg)


class PromptSession(BaseModel):
    """A multi-step interactive prompt session.

    Handlers define the session steps, and InteractiveParticipant
    executes them with TUI rendering.

    Example (Witch action):
        session = PromptSession(
            steps=[
                PromptStep(
                    prompt_type=PromptType.ACTION,
                    prompt_text="Choose your action:",
                    options=[
                        PromptOption(value="PASS", display="Pass (do nothing)"),
                        PromptOption(value="ANTIDOTE", display="Antidote (save target)"),
                        PromptOption(value="POISON", display="Poison (kill player)"),
                    ],
                ),
                PromptStep(
                    prompt_type=PromptType.SEAT,
                    prompt_text="Select target:",
                    options=[...],
                    seat_info={3: "Werewolf", 7: "Ordinary Villager"},
                ),
            ]
        )
    """
    steps: list[PromptStep] = Field(default_factory=list)
    current_step: int = 0
    collected: dict[str, str] = Field(default_factory=dict)

    def add_action_step(
        self,
        prompt_text: str,
        actions: list[tuple[str, str]],  # (value, display)
        allow_none: bool = False,
    ) -> "PromptSession":
        """Add an action selection step."""
        options = [
            PromptOption(value=v, display=d)
            for v, d in actions
        ]
        self.steps.append(PromptStep(
            prompt_type=PromptType.ACTION,
            prompt_text=prompt_text,
            options=options,
            allow_none=allow_none,
        ))
        return self

    def add_seat_step(
        self,
        prompt_text: str,
        seats: list[int],
        seat_info: Optional[dict[int, str]] = None,
        allow_none: bool = True,
    ) -> "PromptSession":
        """Add a seat selection step."""
        options = [
            PromptOption(value=str(s), display=f"Player {s}", seat_hint=s)
            for s in seats
        ]
        self.steps.append(PromptStep(
            prompt_type=PromptType.SEAT,
            prompt_text=prompt_text,
            options=options,
            allow_none=allow_none,
            seat_info=seat_info or {},
        ))
        return self

    def add_vote_step(
        self,
        prompt_text: str,
        candidates: list[int],
        allow_none: bool = True,
    ) -> "PromptSession":
        """Add a voting step."""
        options = [
            PromptOption(value=str(s), display=f"Vote: Player {s}", seat_hint=s)
            for s in candidates
        ]
        self.steps.append(PromptStep(
            prompt_type=PromptType.VOTE,
            prompt_text=prompt_text,
            options=options,
            allow_none=allow_none,
            seat_info={s: f"Player {s}" for s in candidates},
        ))
        return self

    def add_text_step(self, prompt_text: str) -> "PromptSession":
        """Add a free-form text input step."""
        self.steps.append(PromptStep(
            prompt_type=PromptType.TEXT,
            prompt_text=prompt_text,
        ))
        return self

    def add_confirm_step(self, prompt_text: str) -> "PromptSession":
        """Add a yes/no confirmation step."""
        self.steps.append(PromptStep(
            prompt_type=PromptType.CONFIRM,
            prompt_text=prompt_text,
            options=[
                PromptOption(value="yes", display="Yes"),
                PromptOption(value="no", display="No"),
            ],
            allow_none=False,
        ))
        return self

    def is_complete(self) -> bool:
        """Check if all steps have been answered."""
        return self.current_step >= len(self.steps)

    def current_prompt(self) -> Optional[PromptStep]:
        """Get the current prompt step."""
        if self.is_complete():
            return None
        return self.steps[self.current_step]

    def answer(self, value: str) -> None:
        """Record an answer and advance to next step."""
        step = self.current_prompt()
        if step:
            self.collected[f"step_{self.current_step}"] = value
            self.current_step += 1

    def get_result(self, format_type: str = "witch") -> str:
        """Get the final result formatted for the handler.

        Args:
            format_type: Format type ("witch", "vote", "simple", etc.)

        Returns:
            Formatted response string
        """
        if format_type == "witch":
            # Steps: action, then target (if needed)
            action = self.collected.get("step_0", "PASS")
            target = self.collected.get("step_1", "")
            if action == "PASS":
                return "PASS"
            elif target:
                return f"{action} {target}"
            return action

        elif format_type == "guard":
            target = self.collected.get("step_0", "")
            return target if target else "SKIP"

        elif format_type == "vote":
            target = self.collected.get("step_0", "")
            return target if target else "abstain"

        elif format_type == "simple":
            # Single value
            values = list(self.collected.values())
            return values[0] if values else ""

        else:
            # Default: return last answer
            values = list(self.collected.values())
            return values[-1] if values else ""


# ============================================================================
# Convenience builders for common patterns
# ============================================================================

def witch_action_session(
    living_players: list[int],
    witch_seat: int,
    antidote_available: bool,
    poison_available: bool,
    kill_target: Optional[int],
) -> PromptSession:
    """Build a witch action prompt session."""
    session = PromptSession()

    # Build action options based on available potions
    actions: list[tuple[str, str]] = [("PASS", "Pass (do nothing)")]

    if antidote_available and kill_target is not None and kill_target != witch_seat:
        actions.append(("ANTIDOTE", f"Antidote (save Player {kill_target})"))

    if poison_available:
        actions.append(("POISON", "Poison (kill a player)"))

    # Only one action option - no need for choice
    if len(actions) == 1:
        session.add_action_step("Choose your action:", actions, allow_none=False)
        return session

    # Multi-action choice
    session.add_action_step("Choose your action:", actions, allow_none=False)

    # Add target step if needed (handled dynamically based on action)
    return session


def guard_action_session(
    living_players: list[int],
    prev_guarded: Optional[int],
) -> PromptSession:
    """Build a guard action prompt session."""
    # Filter out prev_guarded player
    available = [p for p in living_players if p != prev_guarded]

    session = PromptSession()
    session.add_seat_step(
        prompt_text="Choose who to protect:",
        seats=available,
        allow_none=True,
    )
    return session


def voting_session(
    candidates: list[int],
    living_players: set[int],
) -> PromptSession:
    """Build a voting prompt session."""
    session = PromptSession()
    # Only include living candidates
    valid = [c for c in candidates if c in living_players]
    session.add_vote_step(
        prompt_text="Who do you want to banish?",
        candidates=valid,
        allow_none=True,
    )
    return session


def sheriff_vote_session(
    candidates: list[int],
) -> PromptSession:
    """Build a sheriff election prompt session."""
    session = PromptSession()
    session.add_vote_step(
        prompt_text="Who do you want to elect as Sheriff?",
        candidates=candidates,
        allow_none=True,
    )
    return session


def opt_out_session() -> PromptSession:
    """Build an opt-out prompt session."""
    session = PromptSession()
    session.add_confirm_step("Do you want to opt out of Sheriff candidacy?")
    return session


__all__ = [
    "PromptSession",
    "PromptStep",
    "PromptOption",
    "PromptType",
    "witch_action_session",
    "guard_action_session",
    "voting_session",
    "sheriff_vote_session",
    "opt_out_session",
]
