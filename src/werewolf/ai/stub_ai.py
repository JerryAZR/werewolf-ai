"""Stub AI implementations for testing and fallback modes.

These AIs generate valid random actions without calling LLMs.
Useful for:
- Integration tests (full game flow without LLM calls)
- Development testing
- Fallback when LLM is unavailable

A StubPlayer can handle ANY phase - it parses the prompt to understand
what's being asked and returns a valid response.
"""

import random
import re
from typing import Optional, Protocol, Any

from werewolf.events.game_events import (
    Phase,
    SubPhase,
)
from werewolf.handlers.campaign_handler import CAMPAIGN_OPT_OUT
from werewolf.models.player import Role


class Participant(Protocol):
    """Protocol for AI or human participants."""

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
            choices: Optional ChoiceSpec for structured TUI selection
        """
        ...


class StubPlayer:
    """A stub AI player that can handle ANY game phase.

    Parses the prompt to understand what action is being requested,
    then generates a valid random response. Handles retries gracefully.

    When choices are provided, selects directly from valid options
    instead of parsing the prompt. This ensures always-valid responses.
    """

    def __init__(self, seed: Optional[int] = None):
        """Initialize stub player with optional random seed."""
        if seed is not None:
            random.seed(seed)
        # Track state across calls for more realistic behavior
        self._last_response: Optional[str] = None

    async def decide(
        self,
        system_prompt: str,
        user_prompt: str,
        hint: Optional[str] = None,
        choices: Optional[Any] = None,
    ) -> str:
        """Parse prompt and return a valid action string.

        When choices is provided, select from valid options instead of
        parsing the prompt. This ensures always-valid responses.
        """
        combined = f"{system_prompt}\n{user_prompt}"

        # If choices provided, use them for guaranteed valid response
        if choices is not None:
            return self._choose_from_spec(choices)

        # Otherwise, detect phase and generate response
        subphase = self._detect_subphase(combined)
        response = await self._generate_response(subphase, combined, hint)

        # If hint provided, validate response and retry if invalid
        if hint and not self._is_valid_for_subphase(response, subphase, combined):
            # Try again with a more careful choice
            response = await self._generate_response(subphase, combined, hint)

        self._last_response = response
        return response

    def _choose_from_spec(self, choices: Any) -> str:
        """Choose a valid response from ChoiceSpec or raw options.

        Args:
            choices: Either a ChoiceSpec object or a list of (label, value) tuples

        Returns:
            A valid choice value as string
        """
        # Check if it has options attribute (ChoiceSpec from werewolf.ui)
        if hasattr(choices, 'options') and choices.options:
            opts = choices.options
            if isinstance(opts, list):
                if len(opts) == 0:
                    return "0"
                # List of (label, value) tuples
                if isinstance(opts[0], tuple) and len(opts[0]) >= 2:
                    values = [str(v) for _, v in opts]
                else:
                    # List of just values
                    values = [str(v) for v in opts]
                return str(random.choice(values))

        # Check if it's a list of tuples (label, value)
        if isinstance(choices, list) and choices:
            if isinstance(choices[0], tuple):
                values = [str(v) for _, v in choices]
                return str(random.choice(values))

        # Check if it's a dict
        if isinstance(choices, dict) and choices:
            values = list(choices.values())
            return str(random.choice(values))

        # Fallback: try to parse as raw options
        if hasattr(choices, '__iter__') and not isinstance(choices, str):
            try:
                values = [str(v) for v in choices]
                if values:
                    return str(random.choice(values))
            except (TypeError, ValueError):
                pass

        # Ultimate fallback
        return "0"

    def _detect_subphase(self, text: str) -> SubPhase:
        """Detect which subphase from prompt text."""
        text_lower = text.lower()

        # Extract key markers for classification
        has_discussion = "discussion" in text_lower
        has_speech = "speech" in text_lower
        has_vote = "vote" in text_lower

        # Check for specific phase markers in prompts (more specific first)
        if "werewolf kill decision" in text_lower or "target to kill" in text_lower:
            return SubPhase.WEREWOLF_ACTION
        if "witch action" in text_lower or "antidote" in text_lower or "poison" in text_lower:
            return SubPhase.WITCH_ACTION
        if "guard" in text_lower and "protect" in text_lower:
            return SubPhase.GUARD_ACTION
        if "seer" in text_lower and "check" in text_lower:
            return SubPhase.SEER_ACTION

        # Hunter Final Shot - use VOTING handler but _generate_response will detect and use special logic
        if "hunter final shot" in text_lower:
            return SubPhase.VOTING

        # Check for campaign/sheriff phases before discussion/voting
        # Sheriff election requires more specific "sheriff vote" pattern
        if "campaign" in text_lower or "sheriff" in text_lower:
            if "opt-out" in text_lower or "withdraw" in text_lower:
                return SubPhase.OPT_OUT
            # Sheriff vote: need both sheriff AND vote-for pattern (not just "vote weight")
            if ("sheriff vote" in text_lower or
                "vote for sheriff" in text_lower or
                "sheriff election" in text_lower):
                return SubPhase.SHERIFF_ELECTION
            if "campaign" in text_lower:
                return SubPhase.CAMPAIGN

        # Check death resolution
        if "death" in text_lower:
            if "last words" in text_lower:
                return SubPhase.DEATH_RESOLUTION

        # Check discussion BEFORE voting (more specific patterns)
        # Discussion: has both "discussion" AND "speech"
        # Voting: only "vote", no "discussion"
        if has_discussion and has_speech:
            return SubPhase.DISCUSSION
        if "speaking during day" in text_lower:
            return SubPhase.DISCUSSION

        # Check voting (less specific - contains "vote")
        if has_vote or "banish" in text_lower:
            return SubPhase.VOTING

        # Fallback based on action keywords
        if "antidote" in text_lower or "poison" in text_lower:
            return SubPhase.WITCH_ACTION
        if "protect" in text_lower:
            return SubPhase.GUARD_ACTION
        if "check" in text_lower:
            return SubPhase.SEER_ACTION
        if has_speech:
            return SubPhase.CAMPAIGN

        return SubPhase.DISCUSSION  # Safe fallback

    async def _generate_response(
        self,
        subphase: SubPhase,
        prompt: str,
        hint: Optional[str] = None,
    ) -> str:
        """Generate appropriate response for the subphase."""
        # Special case: Hunter Final Shot always shoots (never skips)
        if "hunter final shot" in prompt.lower():
            return await self._hunter_shoot_response(prompt)

        generators = {
            SubPhase.WEREWOLF_ACTION: self._werewolf_response,
            SubPhase.WITCH_ACTION: self._witch_response,
            SubPhase.GUARD_ACTION: self._guard_response,
            SubPhase.SEER_ACTION: self._seer_response,
            SubPhase.CAMPAIGN: self._speech_response,
            SubPhase.OPT_OUT: self._opt_out_response,
            SubPhase.SHERIFF_ELECTION: self._sheriff_vote_response,
            SubPhase.DEATH_RESOLUTION: self._last_words_response,
            SubPhase.DISCUSSION: self._speech_response,
            SubPhase.VOTING: self._vote_response,
            SubPhase.BANISHMENT_RESOLUTION: self._last_words_response,
        }

        generator = generators.get(subphase, self._vote_response)
        return await generator(prompt)

    def _is_valid_for_subphase(self, response: str, subphase: SubPhase, prompt: str) -> bool:
        """Check if response format is valid for the subphase."""
        response = response.strip().lower()

        valid_formats = {
            SubPhase.WEREWOLF_ACTION: lambda r: r == "-1" or r.isdigit(),
            SubPhase.WITCH_ACTION: lambda r: r in ["pass"] or r.startswith(("antidote", "poison")),
            SubPhase.GUARD_ACTION: lambda r: r == "-1" or r.isdigit(),
            SubPhase.SEER_ACTION: lambda r: r.isdigit(),
            # Campaign: either CAMPAIGN_NOT_RUNNING or a real speech (>10 chars)
            SubPhase.CAMPAIGN: lambda r: r == CAMPAIGN_NOT_RUNNING or len(r) > 10,
            SubPhase.OPT_OUT: lambda r: r in ["run", "opt-out", "stay"],
            SubPhase.SHERIFF_ELECTION: lambda r: r.isdigit() or r == "abstain",
            SubPhase.DEATH_RESOLUTION: lambda r: len(r) > 5,  # Real last words
            SubPhase.DISCUSSION: lambda r: len(r) > 10,
            SubPhase.VOTING: lambda r: r.isdigit() or r == "abstain",
            SubPhase.BANISHMENT_RESOLUTION: lambda r: len(r) > 5,
        }

        validator = valid_formats.get(subphase, lambda r: True)
        return validator(response)

    # ------------------------------------------------------------------
    # Phase-specific response generators
    # ------------------------------------------------------------------

    async def _werewolf_response(self, prompt: str) -> str:
        """Generate werewolf kill decision."""
        if random.random() < 0.1:  # 10% skip chance
            return "-1"

        living = self._extract_seats(prompt, "living", allow_empty=True)
        if living:
            return str(random.choice(living))
        return "0"

    async def _witch_response(self, prompt: str) -> str:
        """Generate witch action (PASS, ANTIDOTE, POISON)."""
        prompt_lower = prompt.lower()

        # Check availability
        antidote_available = "antidote" in prompt_lower and "available" in prompt_lower
        poison_available = "poison" in prompt_lower and "available" in prompt_lower

        # Extract werewolf target if antidote is an option
        kill_target = self._extract_single_seat(prompt, "werewolf kill target")

        roll = random.random()
        antidote_chance = 0.3 if antidote_available else 0
        poison_chance = 0.3 if poison_available else 0

        if kill_target is not None and antidote_available and roll < antidote_chance:
            return f"ANTIDOTE {kill_target}"

        if poison_available and antidote_chance <= roll < antidote_chance + poison_chance:
            living = self._extract_seats(prompt, "living")
            if living:
                return f"POISON {random.choice(living)}"

        return "PASS"

    async def _guard_response(self, prompt: str) -> str:
        """Generate guard protection target."""
        if random.random() < 0.1:  # 10% skip chance
            return "-1"

        living = self._extract_seats(prompt, "living")
        if living:
            return str(random.choice(living))
        return "-1"

    async def _seer_response(self, prompt: str) -> str:
        """Generate seer check target."""
        living = self._extract_seats(prompt, "living")
        if living:
            return str(random.choice(living))
        return "0"

    async def _speech_response(self, prompt: str) -> str:
        """Generate discussion/campaign speech.

        For campaign: ~60% chance to skip (not running), aiming for ~4-5 candidates.
        For discussion: always give a speech.
        """
        is_campaign = "campaign" in prompt.lower() and "sheriff" in prompt.lower()

        if is_campaign:
            # ~40% enter campaign (~5 out of 12), ~60% skip
            if random.random() < 0.6:
                return CAMPAIGN_NOT_RUNNING

        speeches = [
            "I don't have much to say yet. I'll be watching carefully.",
            "I'm leaning toward voting for someone suspicious, but I'm not ready to share yet.",
            "The werewolves have been quiet today. That's suspicious behavior.",
            "We should trust claims that are backed by evidence.",
            "I think we need more information before making a decision.",
            "Let's not jump to conclusions. Stay rational everyone.",
            "I'll share my thoughts after hearing from more players.",
            "Something feels off about the early discussion.",
        ]
        return random.choice(speeches)

    async def _opt_out_response(self, prompt: str) -> str:
        """Generate sheriff candidacy decision."""
        # ~30% opt-out rate (candidates can drop out after entering)
        if random.random() < 0.3:
            return "opt out"
        return "stay"

    async def _sheriff_vote_response(self, prompt: str) -> str:
        """Generate sheriff election vote.

        Note: Sheriff election does NOT allow abstention - player must vote.
        Uses weighted voting to reduce ties.
        """
        candidates = self._extract_seats(prompt, "candidates", allow_empty=True)
        if candidates:
            # Use weighted choice to reduce ties - slight bias toward lower-numbered seats
            weights = [1.0 / (i + 1) for i in range(len(candidates))]
            total = sum(weights)
            weights = [w / total for w in weights]
            return str(random.choices(candidates, weights=weights)[0])
        # Fallback: return first available candidate seat from prompt
        fallback_match = re.search(r'\b(\d+)\b', prompt)
        if fallback_match:
            return fallback_match.group(1)
        return "0"

    async def _last_words_response(self, prompt: str) -> str:
        """Generate last words."""
        statements = [
            "I am the Seer. Someone nearby is a werewolf!",
            "Trust those who have been protective of the village.",
            "I didn't get to do much this game. Good luck everyone.",
            "The werewolves are being clever, but I've been watching.",
            "I've been trying to help the village survive.",
            "I regret not speaking up more earlier. Stay vigilant.",
            "This is a tough game. Trust your instincts.",
        ]
        return random.choice(statements)

    async def _hunter_shoot_response(self, prompt: str) -> str:
        """Generate hunter shoot target - always shoot if possible.

        Hunter should ALWAYS shoot when killed by werewolves (not poison).
        """
        living = self._extract_seats(prompt, "living")
        if living:
            # Always pick a target (hunter should never skip)
            return str(random.choice(living))
        # No living players to shoot
        return "SKIP"

    async def _vote_response(self, prompt: str) -> str:
        """Generate voting decision.

        Uses weighted voting to reduce ties - slight bias toward lower-numbered seats.
        """
        if random.random() < 0.1:  # 10% abstain chance
            return "ABSTAIN"

        living = self._extract_seats(prompt, "living")
        if living:
            # Use weighted choice to reduce ties - bias toward lower-numbered seats
            weights = [1.0 / (i + 1) for i in range(len(living))]
            total = sum(weights)
            weights = [w / total for w in weights]
            return str(random.choices(living, weights=weights)[0])
        return "ABSTAIN"

    # ------------------------------------------------------------------
    # Helper methods for parsing prompts
    # ------------------------------------------------------------------

    def _extract_seats(self, prompt: str, category: str, allow_empty: bool = False) -> list[int]:
        """Extract seat numbers for a category (living, candidates, etc.)."""
        # Try various patterns
        patterns = [
            rf'{category}.*?:\s*([0-9,\s]+?)(?:\n|$)',
            rf'{category}.*?(?:seats?|numbers?).*?:\s*([0-9,\s]+?)(?:\n|$)',
        ]

        for pattern in patterns:
            match = re.search(pattern, prompt, re.IGNORECASE)
            if match:
                seats = re.findall(r'\d+', match.group(1))
                return [int(s) for s in seats]

        # Also check for bullet list format
        if allow_empty:
            bullet_match = re.search(r'(?:^|\n)\s*[-•*]\s*(\d+)', prompt)
            if bullet_match:
                return [int(bullet_match.group(1))]

        return []

    def _extract_single_seat(self, prompt: str, description: str) -> Optional[int]:
        """Extract a single seat number mentioned in context."""
        # Look for "WEREWOLF KILL TARGET: Player at seat X"
        patterns = [
            rf'{description}.*?seat\s*(\d+)',
            rf'target.*?seat\s*(\d+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, prompt, re.IGNORECASE)
            if match:
                return int(match.group(1))

        return None


# ============================================================================
# Factory function for convenience
# ============================================================================

def create_stub_player(seed: Optional[int] = None) -> StubPlayer:
    """Create a stub player with optional random seed."""
    return StubPlayer(seed=seed)


# ============================================================================
# Deprecated: Keep old class names for backward compatibility
# ============================================================================

WerewolfAI = type("WerewolfAI", (StubPlayer,), {})
WitchAI = type("WitchAI", (StubPlayer,), {})
GuardAI = type("GuardAI", (StubPlayer,), {})
SeerAI = type("SeerAI", (StubPlayer,), {})
SheriffCandidateAI = type("SheriffCandidateAI", (StubPlayer,), {})
SheriffVoterAI = type("SheriffVoterAI", (StubPlayer,), {})
DiscussionAI = type("DiscussionAI", (StubPlayer,), {})
VoterAI = type("VoterAI", (StubPlayer,), {})
LastWordsAI = type("LastWordsAI", (StubPlayer,), {})
HunterShootAI = type("HunterShootAI", (StubPlayer,), {})
BadgeTransferAI = type("BadgeTransferAI", (StubPlayer,), {})
StubAI = StubPlayer
