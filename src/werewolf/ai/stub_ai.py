"""Stub AI implementations for testing.

These AIs generate valid responses without calling LLMs.
Useful for integration tests and development testing.
"""

import logging
import random
import json
from typing import Optional, Protocol, Any

logger = logging.getLogger(__name__)


class Participant(Protocol):
    """Protocol for AI or human participants."""

    async def decide(
        self,
        system_prompt: str,
        user_prompt: str,
        hint: Optional[str] = None,
        choices: Optional[Any] = None,
    ) -> str:
        """Make a decision and return raw response string."""
        ...


# Default speech for when no choices are provided (free-text responses)
DEFAULT_SPEECH = (
    "I don't have much to say yet. I've been watching carefully. "
    "The werewolves have been quiet today. That's suspicious."
)


class StubPlayer:
    """A stub AI player for testing.

    Two cases only:
    1. Choices provided -> pick one from the options
    2. No choices -> return a generic speech string
    """

    is_human = False  # AI player, uses LLM prompt format

    def __init__(self, seed: Optional[int] = None):
        self._rng = random.Random(seed) if seed is not None else random.Random()

    async def decide(
        self,
        system_prompt: str,
        user_prompt: str,
        hint: Optional[str] = None,
        choices: Optional[Any] = None,
    ) -> str:
        """Return a valid response.

        If choices provided, pick one. Otherwise return default speech.
        """
        if choices is not None:
            return self._choose_from_spec(choices)
        return DEFAULT_SPEECH

    def _choose_from_spec(self, choices: Any) -> str:
        """Pick a valid response from ChoiceSpec options.

        Args:
            choices: ChoiceSpec object with options

        Returns:
            A valid choice value as string

        Raises:
            ValueError: If format is invalid or has no options
        """
        # Handle ChoiceSpec objects
        if hasattr(choices, 'options') and choices.options:
            opts = choices.options
            if isinstance(opts, list) and len(opts) > 0:
                # Extract values from ChoiceOption objects
                if hasattr(opts[0], 'value'):
                    values = [str(opt.value) for opt in opts]
                elif isinstance(opts[0], tuple):
                    values = [str(v) for _, v in opts]
                else:
                    values = [str(v) for v in opts]
                if values:
                    return str(self._rng.choice(values))
            # allow_none means skip is valid
            if hasattr(choices, 'allow_none') and choices.allow_none:
                return "skip"
            raise ValueError("ChoiceSpec has no valid options")

        # Handle list of tuples [(label, value), ...]
        if isinstance(choices, list) and choices and isinstance(choices[0], tuple):
            values = [str(v) for _, v in choices]
            return str(self._rng.choice(values))

        # Handle plain dict (extract values)
        if isinstance(choices, dict) and choices:
            values = list(choices.values())
            if values:
                return str(self._rng.choice(values))

        raise ValueError(f"Expected ChoiceSpec, list of tuples, or dict, got {type(choices).__name__}")


def create_stub_player(seed: Optional[int] = None) -> StubPlayer:
    """Create a stub player with optional random seed."""
    return StubPlayer(seed=seed)


# Keep deprecated aliases for backward compatibility
StubAI = StubPlayer
WerewolfAI = StubPlayer
WitchAI = StubPlayer
GuardAI = StubPlayer
SeerAI = StubPlayer
SheriffCandidateAI = StubPlayer
SheriffVoterAI = StubPlayer
DiscussionAI = StubPlayer
VoterAI = StubPlayer
LastWordsAI = StubPlayer
HunterShootAI = StubPlayer
BadgeTransferAI = StubPlayer


# ============================================================================
# Debug Stub Player - Prints all prompts for inspection
# ============================================================================

class DebugStubPlayer:
    """A stub AI that prints ALL prompts and choices for debugging.

    This is useful for understanding what prompts are sent to players during
    a game, and what structured choices are available at each decision point.

    Usage:
        participants = {seat: DebugStubPlayer(seat) for seat in players}
    """

    is_human = False  # AI player, uses LLM prompt format

    def __init__(self, seat: int, verbose: bool = True):
        self.seat = seat
        self.verbose = verbose
        self._rng = random.Random(42 + seat)  # Deterministic choices
        self._call_count = 0

    async def decide(
        self,
        system_prompt: str,
        user_prompt: str,
        hint: Optional[str] = None,
        choices: Optional[Any] = None,
    ) -> str:
        """Print prompt info and return a valid response."""
        self._call_count += 1
        call_num = self._call_count

        if not self.verbose:
            # Just make a choice without printing
            if choices is not None:
                return self._choose_from_spec(choices)
            return DEFAULT_SPEECH

        # Log comprehensive debug info
        logger.debug(f"\n{'='*70}")
        logger.debug(f"DEBUG STUB #{call_num} | Seat {self.seat}")
        logger.debug(f"{'='*70}")

        # Parse and display phase info from user_prompt
        phase_info = self._extract_phase_info(user_prompt)
        if phase_info:
            logger.debug(f"PHASE: {phase_info}")

        logger.debug(f"\n--- SYSTEM PROMPT ({len(system_prompt)} chars) ---")
        logger.debug(system_prompt)

        logger.debug(f"\n--- USER PROMPT ({len(user_prompt)} chars) ---")
        # Show the full user prompt for debugging
        logger.debug(user_prompt)

        if hint:
            logger.debug(f"\n--- HINT ---")
            logger.debug(hint)

        # Format and display choices
        choice_info = self._format_choices(choices)
        if choice_info:
            # Calculate total options including skip/none
            total_opts = len(choice_info['options'])
            if choice_info.get('allow_none'):
                total_opts += 1
            logger.debug(f"\n--- CHOICES ({total_opts} options) ---")
            for i, opt in enumerate(choice_info['options'], 1):
                logger.debug(f"  {i}. [{opt['value']}] {opt['display']}")
            if choice_info.get('allow_none'):
                logger.debug(f"  {len(choice_info['options']) + 1}. [skip/none] Skip/Pass")

        # Make deterministic choice
        if choices is not None:
            response = self._choose_from_spec(choices)
        else:
            response = DEFAULT_SPEECH

        logger.debug(f"\n>>> RESPONSE: {response}")
        logger.debug(f"{'='*70}\n")

        return response

    def _extract_phase_info(self, user_prompt: str) -> Optional[str]:
        """Extract phase/subphase info from the user prompt."""
        # Look for section headers like "=== Day 1 - Sheriff Election ==="
        lines = user_prompt.split('\n')
        for line in lines[:5]:  # Check first few lines
            if line.strip().startswith('==='):
                return line.strip().strip('=').strip()
        return None

    def _format_choices(self, choices: Any) -> Optional[dict]:
        """Format choices into a structured dict for display."""
        if choices is None:
            return None

        result = {'options': [], 'allow_none': False}

        # Handle ChoiceSpec objects
        if hasattr(choices, 'options') and choices.options:
            opts = choices.options
            if hasattr(opts[0], 'value'):
                # List of ChoiceOption objects
                for opt in opts:
                    result['options'].append({
                        'value': str(opt.value),
                        'display': str(opt.display),
                        'seat_hint': opt.seat_hint,
                    })
            elif isinstance(opts[0], tuple):
                # List of (display, value) tuples
                for display, value in opts:
                    result['options'].append({
                        'value': str(value),
                        'display': str(display),
                    })
            result['allow_none'] = getattr(choices, 'allow_none', False)
            result['prompt'] = getattr(choices, 'prompt', '')
            result['choice_type'] = getattr(choices, 'choice_type', '')

        # Handle list of tuples
        elif isinstance(choices, list) and choices:
            if isinstance(choices[0], tuple):
                for display, value in choices:
                    result['options'].append({
                        'value': str(value),
                        'display': str(display),
                    })

        # Handle dict
        elif isinstance(choices, dict) and choices:
            for key, value in choices.items():
                result['options'].append({
                    'value': str(value),
                    'display': str(key),
                })

        return result if result['options'] else None

    def _choose_from_spec(self, choices: Any) -> str:
        """Pick a valid response from ChoiceSpec options."""
        if hasattr(choices, 'options') and choices.options:
            opts = choices.options
            if hasattr(opts[0], 'value'):
                values = [str(opt.value) for opt in opts]
            elif isinstance(opts[0], tuple):
                values = [str(v) for _, v in opts]
            else:
                values = [str(v) for v in opts]
            if values:
                return str(self._rng.choice(values))
            if hasattr(choices, 'allow_none') and choices.allow_none:
                return "-1"
            raise ValueError("ChoiceSpec has no valid options")

        if isinstance(choices, list) and choices:
            if isinstance(choices[0], tuple):
                values = [str(v) for _, v in choices]
                return str(self._rng.choice(values))

        if isinstance(choices, dict) and choices:
            values = list(choices.values())
            if values:
                return str(self._rng.choice(values))

        return DEFAULT_SPEECH


def create_debug_stub_player(seat: int, verbose: bool = True) -> DebugStubPlayer:
    """Create a debug stub player for a given seat."""
    return DebugStubPlayer(seat=seat, verbose=verbose)


# ============================================================================
# Capturing Stub Player - Captures prompts exactly as humans see them
# ============================================================================


class CapturingStubPlayer:
    """A stub player that captures prompts exactly as humans receive them.

    This is useful for running automated games and reviewing what human players
    would see at each decision point. The handler builds human-format prompts
    (using DecisionPrompt.to_tui_prompt()) when this player is used.

    Usage:
        participants = {seat: CapturingStubPlayer(seat) for seat in players}
        # After game:
        for call in participants[0].get_captured_calls():
            print(call["user_prompt"])
    """

    is_human = True  # Signals handlers to build human-format prompts

    def __init__(self, seat: int, seed: Optional[int] = None):
        self.seat = seat
        self._rng = random.Random(seed if seed is not None else 42 + seat)
        self._calls: list[dict] = []

    async def decide(
        self,
        system_prompt: str,
        user_prompt: str,
        hint: Optional[str] = None,
        choices: Optional[Any] = None,
    ) -> str:
        """Capture prompts and return a valid response."""
        # Capture exactly what human receives
        self._calls.append({
            "call_num": len(self._calls) + 1,
            "seat": self.seat,
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "hint": hint,
            "choices": self._serialize_choices(choices),
        })

        # Make valid response
        response = self._choose_from_spec(choices) if choices else DEFAULT_SPEECH
        self._calls[-1]["response"] = response
        return response

    def get_captured_calls(self) -> list[dict]:
        """Return all captured decision data."""
        return self._calls

    def _serialize_choices(self, choices: Any) -> Optional[dict]:
        """Serialize choices to dict for storage."""
        if choices is None:
            return None

        result = {'options': [], 'allow_none': False}

        # Handle ChoiceSpec objects
        if hasattr(choices, 'options') and choices.options:
            opts = choices.options
            if hasattr(opts[0], 'value'):
                # List of ChoiceOption objects
                for opt in opts:
                    result['options'].append({
                        'value': str(opt.value),
                        'display': str(opt.display),
                        'seat_hint': opt.seat_hint,
                    })
            elif isinstance(opts[0], tuple):
                # List of (display, value) tuples
                for display, value in opts:
                    result['options'].append({
                        'value': str(value),
                        'display': str(display),
                    })
            result['allow_none'] = getattr(choices, 'allow_none', False)
            result['prompt'] = getattr(choices, 'prompt', '')
            result['choice_type'] = str(getattr(choices, 'choice_type', ''))

        # Handle list of tuples
        elif isinstance(choices, list) and choices:
            if isinstance(choices[0], tuple):
                for display, value in choices:
                    result['options'].append({
                        'value': str(value),
                        'display': str(display),
                    })

        # Handle dict
        elif isinstance(choices, dict) and choices:
            for key, value in choices.items():
                result['options'].append({
                    'value': str(value),
                    'display': str(key),
                })

        return result if result['options'] else None

    def _choose_from_spec(self, choices: Any) -> str:
        """Pick a valid response from ChoiceSpec options."""
        if hasattr(choices, 'options') and choices.options:
            opts = choices.options
            if hasattr(opts[0], 'value'):
                values = [str(opt.value) for opt in opts]
            elif isinstance(opts[0], tuple):
                values = [str(v) for _, v in opts]
            else:
                values = [str(v) for v in opts]
            if values:
                return str(self._rng.choice(values))
            if hasattr(choices, 'allow_none') and choices.allow_none:
                return "-1"
            raise ValueError("ChoiceSpec has no valid options")

        if isinstance(choices, list) and choices:
            if isinstance(choices[0], tuple):
                values = [str(v) for _, v in choices]
                return str(self._rng.choice(values))

        if isinstance(choices, dict) and choices:
            values = list(choices.values())
            if values:
                return str(self._rng.choice(values))

        return DEFAULT_SPEECH


def create_capturing_stub_player(seat: int, seed: Optional[int] = None) -> CapturingStubPlayer:
    """Create a capturing stub player for a given seat."""
    return CapturingStubPlayer(seat=seat, seed=seed)
