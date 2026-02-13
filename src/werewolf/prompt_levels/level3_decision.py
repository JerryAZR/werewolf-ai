from __future__ import annotations

"""Level 3: Decision Prompt with Choices.

This module provides Level 3 of the prompt system - the specific question
being asked and the available choices.

For humans (TUI):
- The question is displayed
- Choices are shown as a structured menu (ChoiceSpec)

For LLMs:
- The question is appended with available options
- Response format is specified
"""

from dataclasses import dataclass
from typing import Optional, Any


@dataclass
class DecisionPrompt:
    """Level 3: Decision prompt with choices.

    This represents the immediate question being asked of the player.
    It's specific to each decision and includes available choices.

    For humans: question + ChoiceSpec for TUI display
    For LLMs: question + choices incorporated into prompt text
    """

    question: str
    choices: Optional[list[Choice]] = None
    response_format: str = "Respond with {choices}"
    hint: Optional[str] = None

    def to_tui_prompt(self) -> str:
        """Format for TUI display (human players).

        Returns:
            String with question and formatted choices
        """
        result = f"{self.question}\n\n"

        if self.choices:
            result += "Options:\n"
            for i, choice in enumerate(self.choices, 1):
                result += f"  {i}. {choice.to_display()}\n"

            result += f"\n{self.response_format.format(choices='one of the above options')}"
        else:
            result += f"\n{self.response_format.format(choices='your answer')}"

        if self.hint:
            result += f"\n\nHint: {self.hint}"

        return result

    def to_llm_prompt(self) -> str:
        """Format for LLM consumption.

        Incorporates choices directly into the prompt text.

        Returns:
            String with question and choices for LLM
        """
        result = f"{self.question}\n\n"

        if self.choices:
            result += "Available options:\n"
            for choice in self.choices:
                result += f"  - {choice.to_llm_format()}\n"

            # Format response instruction
            if self.response_format:
                result += f"\n{self.response_format.format(choices='the option value')}"

        if self.hint:
            result += f"\n\nHint: {self.hint}"

        return result


@dataclass
class Choice:
    """A single choice option for a decision."""

    value: str  # The value to return (e.g., "7", "SKIP", "PASS")
    display: str  # Human-readable display (e.g., "Player 7", "Skip this action")
    description: Optional[str] = None  # Additional explanation
    seat_hint: Optional[int] = None  # Associated seat number (for seat choices)

    def to_display(self) -> str:
        """Format for TUI display."""
        return self.display

    def to_llm_format(self) -> str:
        """Format for LLM prompt."""
        if self.description:
            return f'"{self.value}" - {self.description}'
        return f'"{self.value}"'

    @classmethod
    def seat_choice(cls, seat: int, is_alive: bool = True) -> "Choice":
        """Create a choice for a player seat.

        Args:
            seat: The seat number
            is_alive: Whether the player is alive

        Returns:
            Choice for the seat
        """
        status = "(alive)" if is_alive else "(dead)"
        return cls(
            value=str(seat),
            display=f"Player at seat {seat} {status}",
            description=f"Select player at seat {seat}",
            seat_hint=seat,
        )

    @classmethod
    def skip_choice(cls, display: str = "Skip / Pass / Abstain") -> "Choice":
        """Create a skip/no-selection choice.

        Args:
            display: Custom display text

        Returns:
            Choice for skipping
        """
        return cls(
            value="SKIP",
            display=display,
            description="Choose to skip this action",
        )

    @classmethod
    def none_choice(cls, display: str = "None / Abstain") -> "Choice":
        """Create a none/abstain choice.

        Args:
            display: Custom display text

        Returns:
            Choice for none/abstain
        """
        return cls(
            value="NONE",
            display=display,
            description="Choose to not vote or act",
        )


# =============================================================================
# Decision builders using Level 2 dict context
# =============================================================================

def build_werewolf_decision(
    context: dict,
) -> DecisionPrompt:
    """Build decision prompt for werewolf kill.

    Args:
        context: Level 2 context dict from make_werewolf_context()

    Returns:
        DecisionPrompt for werewolf kill
    """
    choices = []

    # Valid targets = context["valid_targets"]
    for seat in context["valid_targets"]:
        choices.append(Choice.seat_choice(seat))

    choices.append(Choice.skip_choice("Skip (don't kill anyone)"))

    # Build question with game state
    question = f"[Werewolf - Night {context['day']}]\n\n"
    question += f"Your seat: {context['your_seat']}\n"
    question += f"Teammates: {context['teammate_seats_formatted']}\n"
    question += f"\nLiving players: {context['living_seats']}\n"
    question += "\nChoose a target to kill (or SKIP to skip):"

    return DecisionPrompt(
        question=question,
        choices=choices,
        response_format="Enter seat number or SKIP:",
    )


def build_witch_decision(
    context: dict,
) -> DecisionPrompt:
    """Build decision prompt for witch action.

    Args:
        context: Level 2 context dict from make_witch_context()

    Returns:
        DecisionPrompt for witch action
    """
    choices = []

    # PASS option (always available)
    choices.append(Choice(value="PASS", display="PASS", description="Do nothing this night"))

    # ANTIDOTE (if available and target exists)
    if context["antidote_available"] and context["werewolf_kill_target"] is not None:
        target = context["werewolf_kill_target"]
        choices.append(Choice(
            value=f"ANTIDOTE {target}",
            display=f"ANTIDOTE {target}",
            description="Save the werewolf kill target",
        ))

    # POISON (if available)
    if context["poison_available"]:
        # Parse living seats from string
        if context["living_seats"] != "None":
            living = [int(s) for s in context["living_seats"].split(", ")]
            for seat in living:
                choices.append(Choice(
                    value=f"POISON {seat}",
                    display=f"POISON {seat}",
                    description="Kill this player (ignores Guard)",
                ))

    # Build question with game state
    question = f"[Witch - Night {context['day']}]\n\n"
    question += f"Your seat: {context['your_seat']}\n"
    question += f"Antidote: {context['antidote_display']}\n"
    question += f"Poison: {context['poison_display']}\n"

    if context["werewolf_kill_target"] is not None:
        question += f"Werewolf target: seat {context['werewolf_kill_target']}\n"

    question += f"\nLiving players: {context['living_seats']}\n"

    return DecisionPrompt(
        question=question,
        choices=choices,
        response_format="Enter your action (e.g., PASS, ANTIDOTE 7, POISON 3):",
    )


def build_guard_decision(
    context: dict,
) -> DecisionPrompt:
    """Build decision prompt for guard protection.

    Args:
        context: Level 2 context dict from make_guard_context()

    Returns:
        DecisionPrompt for guard action
    """
    choices = []

    # Valid targets (exclude previous target)
    for seat in context["valid_targets"]:
        choices.append(Choice.seat_choice(seat))

    # Skip option
    choices.append(Choice.skip_choice("Skip (don't protect anyone)"))

    # Build question with game state
    question = f"[Guard - Night {context['day']}]\n\n"
    question += f"Your seat: {context['your_seat']}\n"
    question += f"\nLiving players: {context['living_seats']}\n"

    if context.get("guard_prev_target") is not None:
        question += f"\nNOTE: You protected seat {context['guard_prev_target']} last night (cannot protect again)."

    question += "\n\nChoose a player to protect (or SKIP):"

    return DecisionPrompt(
        question=question,
        choices=choices,
        response_format="Enter seat number or SKIP:",
    )


def build_seer_decision(
    context: dict,
) -> DecisionPrompt:
    """Build decision prompt for seer check.

    Args:
        context: Level 2 context dict from make_seer_context()

    Returns:
        DecisionPrompt for seer check
    """
    choices = []

    for seat in context["valid_targets"]:
        choices.append(Choice.seat_choice(seat))

    # Build question with game state
    question = f"[Seer - Night {context['day']}]\n\n"
    question += f"Your seat: {context['your_seat']}\n"
    question += f"\nLiving players: {context['living_seats']}\n"
    question += context["sheriff_info"]

    return DecisionPrompt(
        question=question,
        choices=choices,
        response_format="Enter seat number to check:",
        hint="You cannot check yourself and must choose someone.",
    )


def build_nomination_decision(
    context: dict,
    role: str,
) -> DecisionPrompt:
    """Build decision prompt for sheriff nomination.

    Args:
        context: Level 2 context dict
        role: The player's role name

    Returns:
        DecisionPrompt for nomination
    """
    question = f"[Sheriff Nomination - Day {context['day']}]\n\n"
    question += f"Your seat: {context['your_seat']}\n"
    question += f"Your role: {role}\n"
    question += f"\nLiving players: {context['living_seats']}\n"
    question += context["sheriff_info"]

    return DecisionPrompt(
        question=question,
        choices=[
            Choice(value="run", display="run", description="Declare candidacy for Sheriff"),
            Choice(value="not running", display="not running", description="Decline to run for Sheriff"),
        ],
        response_format='Enter "run" or "not running":',
    )


def build_voting_decision(
    context: dict,
) -> DecisionPrompt:
    """Build decision prompt for banishment voting.

    Args:
        context: Level 2 context dict from make_voting_context()

    Returns:
        DecisionPrompt for voting
    """
    choices = []

    for seat in context["valid_targets"]:
        choices.append(Choice.seat_choice(seat))

    choices.append(Choice.none_choice("None / Abstain"))

    # Build question with game state
    sheriff_note = ""
    if context["is_sheriff"]:
        sheriff_note = "\n\nNOTE: You are Sheriff - your vote counts as 1.5."

    question = f"[Voting - Day {context['day']}]\n\n"
    question += f"Your seat: {context['your_seat']}{sheriff_note}\n"
    question += f"\nLiving players: {context['living_seats']}\n"

    return DecisionPrompt(
        question=question,
        choices=choices,
        response_format="Enter seat number or NONE to abstain:",
    )


def build_sheriff_election_decision(
    context: dict,
    candidates: list[int],
) -> DecisionPrompt:
    """Build decision prompt for sheriff election.

    Args:
        context: Level 2 context dict from make_sheriff_election_context()
        candidates: List of candidate seats

    Returns:
        DecisionPrompt for sheriff election
    """
    choices = []

    for c in candidates:
        choices.append(Choice.seat_choice(c))

    # Build question with game state
    sheriff_note = ""
    if context["is_sheriff"]:
        sheriff_note = "\n\nNOTE: You are Sheriff - your vote counts as 1.5."

    question = f"[Sheriff Election - Day {context['day']}]\n\n"
    question += f"Your seat: {context['your_seat']}{sheriff_note}\n"
    question += f"\nCandidates: {', '.join(map(str, candidates))}\n"

    return DecisionPrompt(
        question=question,
        choices=choices,
        response_format="Enter seat number of your chosen candidate:",
    )


def build_opt_out_decision(
    context: dict,
) -> DecisionPrompt:
    """Build decision prompt for sheriff candidate opt-out.

    Args:
        context: Level 2 context dict from make_opt_out_context()

    Returns:
        DecisionPrompt for opt-out decision
    """
    question = f"[Sheriff Candidate Opt-Out - Day {context['day']}]\n\n"
    question += f"Your seat: {context['your_seat']}\n"

    if context["is_only_candidate"]:
        question += "\nYou are the only candidate remaining!\n"
        question += "If you opt out, there will be no Sheriff election.\n"
    else:
        question += f"\nOther candidates: {context['other_candidates_str']}\n"

    return DecisionPrompt(
        question=question,
        choices=[
            Choice(value="opt out", display="Opt Out", description="Withdraw from Sheriff race"),
            Choice(value="stay", display="Stay", description="Remain in Sheriff race"),
        ],
        response_format='Enter "opt out" or "stay":',
    )


def build_discussion_decision(
    context: dict,
    previous_speeches_text: str = "",
    last_words_text: str = "",
) -> DecisionPrompt:
    """Build decision prompt for discussion speech.

    Args:
        context: Level 2 context dict from make_discussion_context()
        previous_speeches_text: Text of previous speeches this phase
        last_words_text: Text of last words from morning deaths

    Returns:
        DecisionPrompt for discussion speech
    """
    question = f"[Discussion - Day {context['day']}]\n\n"
    question += f"Your seat: {context['your_seat']}\n"
    question += f"Your role: {context['role']}\n"
    question += f"\nSpeaking order: {context['position']} of {context['total']}\n"
    question += f"\nLiving players: {context['living_seats']}\n"
    question += f"Dead players: {context['dead_seats']}\n"

    if context["sheriff_info"]:
        question += f"\n{context['sheriff_info']}\n"

    if previous_speeches_text:
        question += f"\n{previous_speeches_text}"

    if last_words_text:
        question += f"\n{last_words_text}"

    return DecisionPrompt(
        question=question,
        choices=None,  # Free-text speech, no structured choices
        response_format="Enter your speech:",
    )


def build_death_last_words_decision(
    context: dict,
) -> DecisionPrompt:
    """Build decision prompt for death last words.

    Args:
        context: Level 2 context dict from make_death_last_words_context()

    Returns:
        DecisionPrompt for last words
    """
    question = f"[Final Words - Night {context['day']}]\n\n"
    question += f"Your seat: {context['your_seat']}\n"
    question += f"Your role: {context['role']}\n"
    question += f"\n{context['death_context']}\n"
    question += f"\nLiving players: {context['living_seats']}\n"
    question += f"Dead players: {context['dead_seats']}\n"

    return DecisionPrompt(
        question=question,
        choices=None,  # Free-text speech
        response_format="Enter your final words:",
    )


def build_death_hunter_shoot_decision(
    context: dict,
) -> DecisionPrompt:
    """Build decision prompt for death (hunter) shoot action.

    Args:
        context: Level 2 context dict from make_death_hunter_shoot_context()

    Returns:
        DecisionPrompt for hunter shoot
    """
    question = f"[Hunter's Final Shot - Night {context['day']}]\n\n"
    question += f"Your seat: {context['your_seat']}\n"
    question += f"\nLiving players: {context['living_seats_str']}\n"
    question += f"\n{context['werewolf_hint']}\n"

    # Build choices
    choices = []
    for seat in context["living_seats"]:
        choices.append(Choice.seat_choice(seat))
    choices.append(Choice.skip_choice("Skip (don't shoot)"))

    return DecisionPrompt(
        question=question,
        choices=choices,
        response_format="Enter seat number or SKIP:",
    )


def build_death_badge_transfer_decision(
    context: dict,
) -> DecisionPrompt:
    """Build decision prompt for death (sheriff) badge transfer.

    Args:
        context: Level 2 context dict from make_death_badge_transfer_context()

    Returns:
        DecisionPrompt for badge transfer
    """
    question = f"[Sheriff Badge Transfer - Night {context['day']}]\n\n"
    question += f"Your seat: {context['your_seat']}\n"
    question += f"\nLiving players: {context['living_seats_str']}\n"
    question += f"\n{context['trusted_hint']}\n"

    # Build choices
    choices = []
    for seat in context["living_seats"]:
        choices.append(Choice.seat_choice(seat))
    choices.append(Choice.skip_choice("Skip (don't transfer badge)"))

    return DecisionPrompt(
        question=question,
        choices=choices,
        response_format="Enter seat number or SKIP:",
    )


def build_banishment_last_words_decision(
    context: dict,
) -> DecisionPrompt:
    """Build decision prompt for banishment last words.

    Args:
        context: Level 2 context dict from make_banishment_last_words_context()

    Returns:
        DecisionPrompt for last words
    """
    question = f"[Final Words - Day {context['day']} Banishment]\n\n"
    question += f"Your seat: {context['your_seat']}\n"
    question += f"Your role: {context['role']}\n"
    question += f"\n{context['death_context']}\n"
    question += f"\nLiving players: {context['living_seats']}\n"
    question += f"Dead players: {context['dead_seats']}\n"

    return DecisionPrompt(
        question=question,
        choices=None,  # Free-text speech
        response_format="Enter your final words:",
    )


def build_banishment_hunter_shoot_decision(
    context: dict,
) -> DecisionPrompt:
    """Build decision prompt for banishment (hunter) shoot action.

    Args:
        context: Level 2 context dict from make_banishment_hunter_shoot_context()

    Returns:
        DecisionPrompt for hunter shoot
    """
    question = f"[Hunter's Final Shot - Day {context['day']} Banishment]\n\n"
    question += f"Your seat: {context['your_seat']}\n"
    question += f"\nLiving players: {context['living_seats_str']}\n"
    question += f"\n{context['werewolf_hint']}\n"

    # Build choices
    choices = []
    for seat in context["living_seats"]:
        choices.append(Choice.seat_choice(seat))
    choices.append(Choice.skip_choice("Skip (don't shoot)"))

    return DecisionPrompt(
        question=question,
        choices=choices,
        response_format="Enter seat number or SKIP:",
    )


def build_banishment_badge_transfer_decision(
    context: dict,
) -> DecisionPrompt:
    """Build decision prompt for banishment (sheriff) badge transfer.

    Args:
        context: Level 2 context dict from make_banishment_badge_transfer_context()

    Returns:
        DecisionPrompt for badge transfer
    """
    question = f"[Sheriff Badge Transfer - Day {context['day']} Banishment]\n\n"
    question += f"Your seat: {context['your_seat']}\n"
    question += f"\nLiving players: {context['living_seats_str']}\n"
    question += f"\n{context['trusted_hint']}\n"

    # Build choices
    choices = []
    for seat in context["living_seats"]:
        choices.append(Choice.seat_choice(seat))
    choices.append(Choice.skip_choice("Skip (don't transfer badge)"))

    return DecisionPrompt(
        question=question,
        choices=choices,
        response_format="Enter seat number or SKIP:",
    )


# =============================================================================
# Main build function (combines L1, L2, L3)
# =============================================================================

def build_full_prompt(
    system_prompt: str,  # Level 1
    level2_context: dict,  # Level 2
    decision: DecisionPrompt,  # Level 3
    include_events: bool = True,
) -> tuple[str, str]:
    """Build the full prompt for a decision.

    Combines Level 1 (static rules), Level 2 (game state), and Level 3 (decision).

    For humans:
    - Returns (system_prompt, to_tui_prompt())

    For LLMs:
    - Returns (system_prompt + level 2, to_llm_prompt())

    Args:
        system_prompt: Level 1 - static role rules
        level2_context: Level 2 - current game state dict
        decision: Level 3 - specific decision to make
        include_events: Whether to include event context

    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    # System prompt stays as Level 1 only (static)

    # User prompt combines Level 2 (game state) and Level 3 (decision)
    user_parts = []

    # Add game state header
    phase = level2_context.get("phase", "UNKNOWN")
    day = level2_context.get("day", 0)
    user_parts.append(f"=== {phase} {day} ===")

    # Add Level 2 context
    user_parts.append("")
    user_parts.append(f"Your seat: {level2_context.get('your_seat', '?')}")
    user_parts.append(f"Living players: {level2_context.get('living_seats', '?')}")
    user_parts.append(f"Dead players: {level2_context.get('dead_seats', '?')}")

    if level2_context.get("sheriff_info"):
        user_parts.append(level2_context["sheriff_info"])

    # Add role-specific context
    if "teammate_seats_formatted" in level2_context:
        user_parts.append(f"Teammates: {level2_context['teammate_seats_formatted']}")

    if "werewolf_kill_target" in level2_context and level2_context["werewolf_kill_target"] is not None:
        user_parts.append(f"Werewolf kill target: seat {level2_context['werewolf_kill_target']}")

    if "prev_guard_info" in level2_context and level2_context["prev_guard_info"]:
        user_parts.append(level2_context["prev_guard_info"])

    if "antidote_display" in level2_context:
        user_parts.append(f"Antidote: {level2_context['antidote_display']}")
        user_parts.append(f"Poison: {level2_context['poison_display']}")

    user_parts.append("")
    user_parts.append(decision.to_tui_prompt())

    return system_prompt, "\n".join(user_parts)


__all__ = [
    "DecisionPrompt",
    "Choice",
    "build_full_prompt",
    # Decision builders
    "build_werewolf_decision",
    "build_witch_decision",
    "build_guard_decision",
    "build_seer_decision",
    "build_nomination_decision",
    "build_voting_decision",
    "build_sheriff_election_decision",
    "build_opt_out_decision",
    "build_discussion_decision",
    # Death resolution
    "build_death_last_words_decision",
    "build_death_hunter_shoot_decision",
    "build_death_badge_transfer_decision",
    # Banishment resolution
    "build_banishment_last_words_decision",
    "build_banishment_hunter_shoot_decision",
    "build_banishment_badge_transfer_decision",
]
