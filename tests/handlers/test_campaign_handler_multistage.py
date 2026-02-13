"""Tests: CampaignHandler MUST make two separate queries.

Campaign phase requires two stages:
1. ChoiceSpec query for "stay" / "opt-out" selection
2. Free-form text query for speech (if stay) or explanation (if opt-out)

These tests verify the multi-stage pattern.
"""

import pytest
from unittest.mock import AsyncMock
from typing import Optional, Any

from werewolf.models import Player, Role, PlayerType


class PhaseContext:
    """Minimal context for testing Campaign handler."""

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


class TestCampaignHandlerTwoStageQueries:
    """Tests: CampaignHandler must make two separate decide() calls."""

    @pytest.mark.asyncio
    async def test_campaign_stay_choice_then_speech(self):
        """When candidate chooses 'stay', handler should query twice.

        Stage 1: ChoiceSpec for stay/opt-out
        Stage 2: Free-form text for campaign speech
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

        # Track all calls to decide()
        call_log = []

        async def mock_decide(system_prompt, user_prompt, hint=None, choices=None):
            call_log.append({"choices": choices})
            # Return "stay" on first call, speech on second
            if len(call_log) == 1:
                return "stay"
            else:
                return "I want to be your Sheriff because I'm trustworthy!"

        mock_participant = AsyncMock()
        mock_participant.decide = mock_decide

        handler = CampaignHandler()
        result = await handler(context, [(0, mock_participant)], sheriff_candidates=[0])

        # Verify TWO calls were made
        assert len(call_log) == 2, (
            f"FAIL: Expected 2 decide() calls, got {len(call_log)}. "
            f"This means CampaignHandler isn't doing two-stage queries."
        )

        # Verify first call had ChoiceSpec
        first_call = call_log[0]
        assert first_call["choices"] is not None, (
            "FAIL: First call must have choices=ChoiceSpec for stay/opt-out"
        )

        # Verify second call was free-form (choices=None)
        second_call = call_log[1]
        assert second_call["choices"] is None, (
            "FAIL: Second call (speech) must have choices=None for free-form text"
        )

        # Verify result
        assert len(result.subphase_log.events) == 1
        event = result.subphase_log.events[0]
        assert event.content == "I want to be your Sheriff because I'm trustworthy!"

    @pytest.mark.asyncio
    async def test_campaign_optout_choice_then_explanation(self):
        """When candidate chooses 'opt-out', handler should query twice.

        Stage 1: ChoiceSpec for stay/opt-out
        Stage 2: Free-form text for explanation
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

        call_log = []

        async def mock_decide(system_prompt, user_prompt, hint=None, choices=None):
            call_log.append({"choices": choices})
            if len(call_log) == 1:
                return "opt-out"
            else:
                return "I'm feeling unwell, I must withdraw from the race."

        mock_participant = AsyncMock()
        mock_participant.decide = mock_decide

        handler = CampaignHandler()
        result = await handler(context, [(0, mock_participant)], sheriff_candidates=[0])

        # Verify TWO calls
        assert len(call_log) == 2, f"Expected 2 calls, got {len(call_log)}"

        # First should have choices
        assert call_log[0]["choices"] is not None, "First call needs ChoiceSpec"

        # Second should be free-form
        assert call_log[1]["choices"] is None, "Second call should be free-form"

    @pytest.mark.asyncio
    async def test_campaign_choices_has_stay_and_optout(self):
        """First query's ChoiceSpec must have 'stay' and 'opt-out' options."""
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

        call_count = 0
        captured_choices = None

        async def mock_decide(system_prompt, user_prompt, hint=None, choices=None):
            nonlocal captured_choices, call_count
            call_count += 1
            if choices is not None:
                captured_choices = choices
            # Return "stay" on first choice query, "My speech" on speech query
            if call_count == 1:
                return "stay"
            return "My speech"

        mock_participant = AsyncMock()
        mock_participant.decide = mock_decide

        handler = CampaignHandler()
        await handler(context, [(0, mock_participant)], sheriff_candidates=[0])

        # Verify ChoiceSpec structure
        assert captured_choices is not None, "ChoiceSpec should be provided"
        from werewolf.ui.choices import ChoiceSpec, ChoiceType
        assert isinstance(captured_choices, ChoiceSpec)

        # Check options
        values = [opt.value for opt in captured_choices.options]
        assert "stay" in values, f"'stay' must be in options: {values}"
        assert "opt-out" in values, f"'opt-out' must be in options: {values}"

        # Verify choice_type is SINGLE
        assert captured_choices.choice_type == ChoiceType.SINGLE

    @pytest.mark.asyncio
    async def test_campaign_single_query_is_wrong(self):
        """FAIL: Single query pattern should be detected and flagged.

        This test documents the WRONG pattern - single query where
        participant must parse "opt out" from free-form text.
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

        call_count = 0

        async def mock_decide(system_prompt, user_prompt, hint=None, choices=None):
            nonlocal call_count
            call_count += 1
            return "opt out"  # Single query expects "opt out" as text

        mock_participant = AsyncMock()
        mock_participant.decide = mock_decide

        handler = CampaignHandler()
        await handler(context, [(0, mock_participant)], sheriff_candidates=[0])

        # If this is still using single-query pattern, call_count will be 1
        # With proper fix, it should be 2
        assert call_count == 2, (
            f"FAIL: Handler made {call_count} call(s). "
            f"Multi-stage pattern requires exactly 2 calls."
        )


class TestCampaignHandlerReturnValues:
    """Tests: Verify correct return values from two-stage queries."""

    @pytest.mark.asyncio
    async def test_stay_returns_speech_event(self):
        """'stay' should result in Speech event with campaign content."""
        from werewolf.handlers.campaign_handler import CampaignHandler
        from werewolf.events.game_events import Speech, SubPhase

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

        async def mock_decide(system_prompt, user_prompt, hint=None, choices=None):
            if choices is not None:
                return "stay"
            return "My campaign speech for Sheriff"

        mock_participant = AsyncMock()
        mock_participant.decide = mock_decide

        handler = CampaignHandler()
        result = await handler(context, [(0, mock_participant)], sheriff_candidates=[0])

        assert len(result.subphase_log.events) == 1
        event = result.subphase_log.events[0]
        assert isinstance(event, Speech)
        assert event.content == "My campaign speech for Sheriff"
        assert event.micro_phase == SubPhase.CAMPAIGN

    @pytest.mark.asyncio
    async def test_optout_returns_none(self):
        """'opt-out' should result in None (no Speech event)."""
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

        async def mock_decide(system_prompt, user_prompt, hint=None, choices=None):
            if choices is not None:
                return "opt-out"
            return "Explanation for withdrawing"

        mock_participant = AsyncMock()
        mock_participant.decide = mock_decide

        handler = CampaignHandler()
        result = await handler(context, [(0, mock_participant)], sheriff_candidates=[0])

        # opt-out means no speech event
        assert len(result.subphase_log.events) == 0, (
            f"opt-out should result in no events, got {len(result.subphase_log.events)}"
        )


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
