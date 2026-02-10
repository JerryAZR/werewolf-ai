"""Test models and events."""

from werewolf.events import (
    GameStart,
    Phase,
    SubPhase,
    WerewolfKill,
    WitchAction,
    WitchActionType,
    GuardAction,
    SeerAction,
    SeerResult,
    DeathAnnouncement,
    Vote,
    VictoryOutcome,
    Speech,
    DeathEvent,
    DeathCause,
)
from werewolf.models import (
    Player,
    Role,
    PlayerType,
    STANDARD_12_PLAYER_CONFIG,
)


def test_player_creation():
    """Test creating a player."""
    player = Player(
        seat=0,
        name="Alice",
        role=Role.WEREWOLF,
        player_type=PlayerType.HUMAN,
    )
    assert player.seat == 0
    assert player.name == "Alice"
    assert player.role == Role.WEREWOLF
    assert player.is_alive
    assert not player.is_sheriff


def test_game_start_event():
    """Test GameStart event."""
    event = GameStart(
        player_count=12,
        roles_secret={0: "WEREWOLF", 1: "SEER"},
    )
    assert event.player_count == 12
    assert event.roles_secret[0] == "WEREWOLF"


def test_werewolf_kill_event():
    """Test WerewolfKill event."""
    event = WerewolfKill(
        day=1,
        actor=0,  # Any werewolf seat
        target=3,
    )
    assert event.actor == 0
    assert event.target == 3
    assert event.phase == Phase.NIGHT
    assert event.micro_phase == SubPhase.WEREWOLF_ACTION


def test_witch_action_event():
    """Test WitchAction event."""
    event = WitchAction(
        day=1,
        actor=4,  # Witch seat
        action_type=WitchActionType.ANTIDOTE,
        target=3,
    )
    assert event.actor == 4
    assert event.action_type == WitchActionType.ANTIDOTE
    assert event.target == 3


def test_guard_action_event():
    """Test GuardAction event."""
    event = GuardAction(
        day=1,
        actor=2,  # Guard seat
        target=5,
    )
    assert event.actor == 2
    assert event.target == 5


def test_seer_action_event():
    """Test SeerAction event."""
    event = SeerAction(
        day=1,
        actor=1,  # Seer seat
        target=7,
        result=SeerResult.WEREWOLF,
    )
    assert event.actor == 1
    assert event.target == 7
    assert event.result == SeerResult.WEREWOLF


def test_speech_event():
    """Test Speech for campaign and discussion."""
    event = Speech(
        day=1,
        actor=0,
        micro_phase=SubPhase.CAMPAIGN,
        content="I am the Sheriff!",
    )
    assert event.actor == 0
    assert event.content == "I am the Sheriff!"
    assert event.micro_phase == SubPhase.CAMPAIGN


def test_vote_event():
    """Test Vote event."""
    event = Vote(
        day=1,
        actor=0,
        micro_phase=SubPhase.VOTING,
        target=5,
    )
    assert event.actor == 0
    assert event.target == 5


def test_death_announcement():
    """Test DeathAnnouncement event."""
    event = DeathAnnouncement(
        day=1,
        dead_players=[2, 5],
        death_count=2,
    )
    assert event.dead_players == [2, 5]
    assert event.death_count == 2


def test_death_resolution():
    """Test DeathEvent event."""
    event = DeathEvent(
        day=1,
        actor=5,  # Dying player
        cause=DeathCause.BANISHMENT,
        last_words="I was not a werewolf...",
    )
    assert event.actor == 5
    assert event.cause == DeathCause.BANISHMENT
    assert event.last_words == "I was not a werewolf..."
    assert "Death" in str(event)


def test_str_methods():
    """Test __str__ methods for readability."""
    # WerewolfKill with target
    kill = WerewolfKill(day=1, actor=0, target=5)
    assert str(kill) == "WerewolfKill(target=5)"

    # WerewolfKill without target (no kill)
    no_kill = WerewolfKill(day=1, actor=0)
    assert str(no_kill) == "WerewolfKill(no kill)"

    # Vote abstain
    abstain = Vote(day=1, actor=0)
    assert "abstain" in str(abstain)

    # Vote with target
    vote = Vote(day=1, actor=0, target=5)
    assert "target=5" in str(vote)

    # Guard skip
    guard_skip = GuardAction(day=1, actor=2)
    assert "skip" in str(guard_skip)

    # Speech truncation
    long_speech = Speech(day=1, actor=0, micro_phase=SubPhase.CAMPAIGN, content="x" * 100)
    assert "..." in str(long_speech)


def test_role_config():
    """Test role configuration."""
    assert len(STANDARD_12_PLAYER_CONFIG) == 6
    total = sum(c.count for c in STANDARD_12_PLAYER_CONFIG)
    assert total == 12


if __name__ == "__main__":
    test_player_creation()
    test_game_start_event()
    test_werewolf_kill_event()
    test_witch_action_event()
    test_guard_action_event()
    test_seer_action_event()
    test_speech_event()
    test_vote_event()
    test_death_announcement()
    test_death_resolution()
    test_role_config()
    print("All tests passed!")
