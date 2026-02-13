"""Stress tests: Run multiple games with human player stubs.

Tests verify that the game engine handles multiple human players correctly
under load. Uses different seeds to ensure coverage.
"""

import pytest
from werewolf.models import Player, create_players_from_config
from werewolf.engine import WerewolfGame
from werewolf.ai.stub_ai import create_stub_player


def create_players_shuffled(seed):
    """Create a dict of players with shuffled roles from standard config."""
    import random
    rng = random.Random(seed)
    role_assignments = create_players_from_config(rng=rng)
    players = {}
    for seat, role in role_assignments:
        players[seat] = Player(
            seat=seat,
            name=f"Player {seat}",
            role=role,
        )
    return players


class HumanPlayerStub:
    """Stub that makes consistent, valid choices for testing."""

    def __init__(self, seat: int):
        self.seat = seat
        self.choice_count = 0

    async def decide(self, system_prompt: str, user_prompt: str, hint: str = None, choices=None) -> str:
        self.choice_count += 1

        if choices and hasattr(choices, 'options') and choices.options:
            return choices.options[0].value
        elif choices and hasattr(choices, 'allow_none') and choices.allow_none:
            return "-1"
        else:
            return "0"


@pytest.mark.asyncio
@pytest.mark.parametrize("game_seed", list(range(1000, 2000)))  # 1000 games: 1000-1999
async def test_1000_games_with_human_stub(game_seed: int):
    """Run 10 complete games with a human player stub at seat 0."""
    players = create_players_shuffled(seed=game_seed)

    participants = {}
    for seat in players.keys():
        if seat == 0:
            participants[seat] = HumanPlayerStub(seat)
        else:
            participants[seat] = create_stub_player(seed=game_seed + seat)

    game = WerewolfGame(
        players=players,
        participants=participants,
        seed=game_seed,
    )

    event_log, winner = await game.run()

    assert event_log is not None
    # Winner can be None for ties (A.5 condition)
    assert winner in ["WEREWOLF", "VILLAGER", None]
    assert event_log.game_over is not None


@pytest.mark.asyncio
@pytest.mark.parametrize("num_humans", [1, 3, 5, 7])
async def test_games_with_multiple_human_stubs(num_humans: int):
    """Run games with varying numbers of human stubs."""
    import random
    random.seed(999)

    human_seats = random.sample(list(range(12)), num_humans)

    players = create_players_shuffled(seed=777)

    participants = {}
    for seat in players.keys():
        if seat in human_seats:
            participants[seat] = HumanPlayerStub(seat)
        else:
            participants[seat] = create_stub_player(seed=42 + seat)

    game = WerewolfGame(
        players=players,
        participants=participants,
        seed=777,
    )

    event_log, winner = await game.run()

    assert event_log is not None
    assert winner in ["WEREWOLF", "VILLAGER", None]
    assert event_log.game_over is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
