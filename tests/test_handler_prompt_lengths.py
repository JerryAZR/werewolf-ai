"""Test: All handler prompts must meet minimum length requirements.

This test catches the bug where campaign_handler was using 70-char prompts
instead of proper multi-line prompts (400+ chars).

Rule: System prompts should be > 200 chars, User prompts should be > 100 chars.
"""

import pytest
from unittest.mock import AsyncMock
from typing import Optional, Any

from werewolf.models import Player, Role, PlayerType


class PhaseContext:
    """Minimal context for testing."""

    def __init__(
        self,
        players: dict[int, Player],
        living_players: set[int],
        dead_players: set[int],
        sheriff: Optional[int] = None,
        day: int = 1,
    ):
        self.players = players
        self.living_players = living_players
        self.dead_players = dead_players
        self.sheriff = sheriff
        self.day = day

    def get_player(self, seat: int) -> Optional[Player]:
        return self.players.get(seat)

    def is_alive(self, seat: int) -> bool:
        return seat in self.living_players


# Minimum lengths for comprehensive prompts
MIN_SYSTEM_PROMPT_LENGTH = 200
MIN_USER_PROMPT_LENGTH = 100


@pytest.mark.asyncio
async def test_campaign_handler_prompts_meet_minimum_length():
    """Stage 1 (stay/opt-out) prompts must meet minimum length requirements.

    This catches the bug where prompts were only ~70 chars.
    """
    from werewolf.handlers.campaign_handler import CampaignHandler

    players = {
        0: Player(seat=0, name="Player_0", role=Role.VILLAGER, player_type=PlayerType.AI),
    }
    context = PhaseContext(
        players=players,
        living_players={0},
        dead_players=set(),
        sheriff=None,
        day=1,
    )

    captured_prompts = []

    async def mock_decide(system_prompt, user_prompt, hint=None, choices=None):
        captured_prompts.append({
            "system": system_prompt,
            "user": user_prompt,
            "choices": choices,
        })
        if choices is not None:
            return "stay"
        return "My campaign speech"

    mock_participant = AsyncMock()
    mock_participant.decide = mock_decide

    handler = CampaignHandler()
    await handler(context, [(0, mock_participant)], sheriff_candidates=[0])

    # First call should have ChoiceSpec for stay/opt-out
    assert len(captured_prompts) >= 2, "Expected at least 2 calls (stage 1 + stage 2)"

    stage1 = captured_prompts[0]

    # Validate Stage 1 system prompt length
    assert len(stage1["system"]) >= MIN_SYSTEM_PROMPT_LENGTH, (
        f"FAIL: Stage 1 system prompt is only {len(stage1['system'])} chars. "
        f"Expected >= {MIN_SYSTEM_PROMPT_LENGTH} chars for comprehensive prompt.\n"
        f"Actual: {stage1['system'][:200]}..."
    )

    # Validate Stage 1 user prompt length
    assert len(stage1["user"]) >= MIN_USER_PROMPT_LENGTH, (
        f"FAIL: Stage 1 user prompt is only {len(stage1['user'])} chars. "
        f"Expected >= {MIN_USER_PROMPT_LENGTH} chars.\n"
        f"Actual: {stage1['user']}"
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
