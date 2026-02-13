"""Stub AI implementations for testing.

These AIs generate valid responses without calling LLMs.
Useful for integration tests and development testing.
"""

import random
from typing import Optional, Protocol, Any


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
