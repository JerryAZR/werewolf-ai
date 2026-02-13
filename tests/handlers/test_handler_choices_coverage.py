"""Tests: Verify ALL handlers pass choices parameter to participant.decide().

This test file ensures architectural compliance:
- Discrete-choice handlers MUST provide ChoiceSpec to participant.decide()
- If a handler doesn't pass choices, this test will FAIL.

The Bug Pattern:
- Handlers build prompts and call participant.decide() but forget to pass choices=
- This causes TextualParticipant to show broken fallback menus
- StubAI works because it has built-in phase detection (which we will remove)

FIX:
- Each handler's _get_valid_* method must pass choices=... to participant.decide()
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock
from typing import Optional

from werewolf.models import Player, Role, PlayerType, create_players_from_config
from werewolf.ui.choices import ChoiceSpec, ChoiceOption, ChoiceType


def create_players(seed: Optional[int] = None) -> dict[int, Player]:
    """Create standard 12-player config."""
    import random
    rng = random.Random(seed)
    role_assignments = create_players_from_config(rng=rng)
    players = {}
    for seat, role in role_assignments:
        players[seat] = Player(seat=seat, name=f"Player {seat}", role=role)
    return players


# ============================================================================
# Test: All Discrete-Choice Handlers MUST Pass Choices
# ============================================================================


class TestAllHandlersPassChoices:
    """Tests: Every discrete-choice handler must pass choices parameter.

    These tests FAIL if handlers don't pass choices=... to participant.decide()
    """

    @pytest.mark.asyncio
    async def test_seer_handler_passes_choices(self):
        """SeerHandler MUST pass choices (not self, living players only)."""
        from werewolf.handlers.seer_handler import SeerHandler, PhaseContext as SeerContext

        players = create_players(seed=42)
        living = set(players.keys())

        seer_seat = next((s for s, p in players.items() if p.role == Role.SEER and s in living), None)
        assert seer_seat is not None, "Seer not found"

        mock_participant = AsyncMock()
        mock_participant.decide = AsyncMock(return_value="0")

        context = SeerContext(
            players=players,
            living_players=living,
            dead_players=set(),
            sheriff=None,
            day=1,
        )

        handler = SeerHandler()
        await handler(context, [(seer_seat, mock_participant)])

        choices_passed = mock_participant.decide.call_args.kwargs.get('choices')
        assert choices_passed is not None, (
            "FAIL: SeerHandler did not pass 'choices' to participant.decide()"
        )

        # Verify self is NOT in choices
        if hasattr(choices_passed, 'options'):
            values = [opt.value for opt in choices_passed.options]
        else:
            values = []
        assert str(seer_seat) not in values, (
            f"FAIL: SeerHandler included self (seat {seer_seat}) in choices"
        )

    @pytest.mark.asyncio
    async def test_guard_handler_passes_choices(self):
        """GuardHandler MUST pass choices (not same as prev, living only)."""
        from werewolf.handlers.guard_handler import GuardHandler, PhaseContext as GuardContext

        players = create_players(seed=42)
        living = set(players.keys())

        guard_seat = next((s for s, p in players.items() if p.role == Role.GUARD and s in living), None)
        assert guard_seat is not None, "Guard not found"

        mock_participant = AsyncMock()
        mock_participant.decide = AsyncMock(return_value="0")

        context = GuardContext(
            players=players,
            living_players=living,
            dead_players=set(),
            sheriff=None,
            day=1,
        )

        handler = GuardHandler()
        await handler(context, [(guard_seat, mock_participant)], guard_prev_target=None)

        choices_passed = mock_participant.decide.call_args.kwargs.get('choices')
        assert choices_passed is not None, (
            "FAIL: GuardHandler did not pass 'choices' to participant.decide()"
        )

    @pytest.mark.asyncio
    async def test_werewolf_handler_passes_choices(self):
        """WerewolfHandler MUST pass choices (not self, not other WW)."""
        from werewolf.handlers.werewolf_handler import WerewolfHandler

        players = create_players(seed=42)
        living = set(players.keys())

        ww_seats = [s for s, p in players.items() if p.role == Role.WEREWOLF and s in living]
        assert ww_seats, "No werewolves found"

        mock_participant = AsyncMock()
        mock_participant.decide = AsyncMock(return_value="5")

        class WWContext:
            def __init__(self, players, living, dead, sheriff, day):
                self.players = players
                self.living_players = living
                self.dead_players = dead
                self.sheriff = sheriff
                self.day = day

            def is_werewolf(self, seat):
                p = self.players.get(seat)
                return p is not None and p.role == Role.WEREWOLF

        context = WWContext(players, living, set(), None, 1)

        handler = WerewolfHandler()
        await handler(context, [(ww_seats[0], mock_participant)])

        choices_passed = mock_participant.decide.call_args.kwargs.get('choices')
        assert choices_passed is not None, (
            "FAIL: WerewolfHandler did not pass 'choices' to participant.decide()"
        )

    @pytest.mark.asyncio
    async def test_witch_handler_passes_choices(self):
        """WitchHandler MUST pass choices (action + target options)."""
        from werewolf.handlers.witch_handler import WitchHandler, PhaseContext, NightActions

        players = create_players(seed=42)
        living = set(players.keys())

        witch_seat = next((s for s, p in players.items() if p.role == Role.WITCH and s in living), None)
        assert witch_seat is not None, "Witch not found"

        mock_participant = AsyncMock()
        mock_participant.decide = AsyncMock(return_value="PASS")

        context = PhaseContext(
            players=players,
            living_players=living,
            dead_players=set(),
            sheriff=None,
            day=1,
        )

        night_actions = NightActions(
            kill_target=5,
            antidote_used=False,
            poison_used=True,  # Only PASS available
        )

        handler = WitchHandler()
        await handler(context, [(witch_seat, mock_participant)], night_actions=night_actions)

        choices_passed = mock_participant.decide.call_args.kwargs.get('choices')
        assert choices_passed is not None, (
            "FAIL: WitchHandler did not pass 'choices' to participant.decide()"
        )

    @pytest.mark.asyncio
    async def test_sheriff_election_handler_passes_choices(self):
        """SheriffElectionHandler MUST pass choices (candidates only)."""
        from werewolf.handlers.sheriff_election_handler import SheriffElectionHandler

        players = create_players(seed=42)
        living = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11}
        candidates = [0, 3, 7]
        # Use a voter who is NOT a candidate (candidates cannot vote)
        voter_seat = 1

        class TestContext:
            def __init__(self, players, living, sheriff, day):
                self.players = players
                self.living_players = living
                self.dead_players = set(players.keys()) - living
                self.sheriff = sheriff
                self.day = day

            def get_player(self, seat):
                return self.players.get(seat)

            def is_alive(self, seat):
                return seat in self.living_players

        context = TestContext(players, living, None, 1)

        mock_participant = AsyncMock()
        mock_participant.decide = AsyncMock(return_value="3")

        handler = SheriffElectionHandler()
        await handler(context, [(voter_seat, mock_participant)], sheriff_candidates=candidates)

        choices_passed = mock_participant.decide.call_args.kwargs.get('choices')
        assert choices_passed is not None, (
            "FAIL: SheriffElectionHandler did not pass 'choices' to participant.decide()"
        )

    @pytest.mark.asyncio
    async def test_voting_handler_passes_choices(self):
        """VotingHandler MUST pass choices (any living player)."""
        from werewolf.handlers.voting_handler import VotingHandler

        players = create_players(seed=42)
        living = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11}

        class TestContext:
            def __init__(self, players, living, sheriff, day):
                self.players = players
                self.living_players = living
                self.dead_players = set(players.keys()) - living
                self.sheriff = sheriff
                self.day = day

            def get_player(self, seat):
                return self.players.get(seat)

            def is_alive(self, seat):
                return seat in self.living_players

        context = TestContext(players, living, None, 1)

        mock_participant = AsyncMock()
        mock_participant.decide = AsyncMock(return_value="5")

        handler = VotingHandler()
        await handler(context, [(0, mock_participant)])

        choices_passed = mock_participant.decide.call_args.kwargs.get('choices')
        assert choices_passed is not None, (
            "FAIL: VotingHandler did not pass 'choices' to participant.decide()"
        )

    @pytest.mark.asyncio
    async def test_nomination_handler_passes_choices(self):
        """NominationHandler MUST pass choices ('run' / 'not running')."""
        from werewolf.handlers.nomination_handler import NominationHandler, PhaseContext

        players = create_players(seed=42)

        context = PhaseContext(
            players=players,
            living_players=set(players.keys()),
            dead_players=set(),
            sheriff=None,
            day=1,
        )

        mock_participant = AsyncMock()
        mock_participant.decide = AsyncMock(return_value="run")

        handler = NominationHandler()
        await handler(context, [(0, mock_participant)])

        choices_passed = mock_participant.decide.call_args.kwargs.get('choices')
        assert choices_passed is not None, (
            "FAIL: NominationHandler did not pass 'choices' to participant.decide()"
        )

        # Verify it's SINGLE choice type with run/not running
        assert hasattr(choices_passed, 'choice_type')
        values = [opt.value for opt in choices_passed.options]
        assert "run" in values, "FAIL: Nomination choices missing 'run'"
        assert "not running" in values, "FAIL: Nomination choices missing 'not running'"

    @pytest.mark.asyncio
    async def test_opt_out_handler_passes_choices(self):
        """OptOutHandler MUST pass choices ('stay' / 'opt-out')."""
        from werewolf.handlers.opt_out_handler import OptOutHandler, PhaseContext as OptOutContext

        players = create_players(seed=42)
        living = set(players.keys())
        candidates = list(living)[:5]

        context = OptOutContext(
            sheriff_candidates=candidates,
            living_players=living,
            dead_players=set(),
            day=1,
        )

        mock_participant = AsyncMock()
        mock_participant.decide = AsyncMock(return_value="stay")

        handler = OptOutHandler()
        await handler(context, {0: mock_participant})

        choices_passed = mock_participant.decide.call_args.kwargs.get('choices')
        assert choices_passed is not None, (
            "FAIL: OptOutHandler did not pass 'choices' to participant.decide()"
        )

    @pytest.mark.asyncio
    async def test_death_resolution_handler_passes_choices(self):
        """DeathResolutionHandler MUST pass choices for badge transfer."""
        from werewolf.handlers.death_resolution_handler import DeathResolutionHandler, NightOutcomeInput
        from werewolf.events.game_events import DeathCause

        players = create_players(seed=42)
        living = {0, 1, 2, 3, 4, 5, 6, 7}
        dead = {8, 9, 10, 11}

        # Make seat 8 the sheriff
        players[8].is_sheriff = True

        class TestContext:
            def __init__(self, players, living, dead, sheriff, day):
                self.players = players
                self.living_players = living
                self.dead_players = dead
                self.sheriff = sheriff
                self.day = day

            def get_player(self, seat):
                return self.players.get(seat)

            def is_alive(self, seat):
                return seat in self.living_players

            def is_werewolf(self, seat):
                p = self.players.get(seat)
                return p is not None and p.role == Role.WEREWOLF

        # Sheriff dies at seat 8
        context = TestContext(players, living, dead, 8, 1)

        # Create night outcome with sheriff death
        night_outcome = NightOutcomeInput(
            day=1,
            deaths={8: DeathCause.WEREWOLF_KILL}
        )

        mock_participant = AsyncMock()
        mock_participant.decide = AsyncMock(return_value="3")

        handler = DeathResolutionHandler()
        await handler(
            context,
            night_outcome,
            participants=[(8, mock_participant)],
        )

        # Check that badge transfer passed choices
        # Note: After reordering, calls are: badge_transfer, last_words (no hunter for this player)
        # Badge transfer (1st call) should pass choices
        calls = mock_participant.decide.call_args_list
        print(f"DEBUG: Number of calls = {len(calls)}")
        for i, call in enumerate(calls):
            print(f"DEBUG: Call {i} kwargs = {call.kwargs}")

        assert len(calls) >= 1, f"Expected at least 1 call, got {len(calls)}"

        # Check badge transfer call (index 0) passes choices
        badge_transfer_call = calls[0]
        choices_passed = badge_transfer_call.kwargs.get('choices')
        assert choices_passed is not None, (
            "FAIL: DeathResolutionHandler did not pass 'choices' for badge transfer (1st call)"
        )


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
