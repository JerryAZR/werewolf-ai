"""Tests for the event_log module."""

import pytest
import tempfile
import os

from src.werewolf.events.event_log import (
    GameEventLog,
    PhaseLog,
    SubPhaseLog,
)
from src.werewolf.events.game_events import (
    GameStart,
    WerewolfKill,
    WitchAction,
    GuardAction,
    SeerAction,
    SeerResult,
    NightResolution,
    Speech,
    SubPhase,
    SheriffElection,
    SheriffOptOut,
    Vote,
    DeathAnnouncement,
    VictoryCheck,
    VictoryCondition,
    GameOver,
    WitchActionType,
    Phase,
)


class TestSubPhaseLog:
    """Tests for SubPhaseLog container."""

    def test_subphase_empty(self):
        """Test SubPhaseLog with no events."""
        subphase = SubPhaseLog(micro_phase=SubPhase.WEREWOLF_ACTION)
        assert len(subphase.events) == 0
        assert subphase.micro_phase == SubPhase.WEREWOLF_ACTION
        assert str(subphase) == "WEREWOLF_ACTION"

    def test_subphase_with_single_event(self):
        """Test SubPhaseLog with a single event."""
        kill = WerewolfKill(actor=0, day=1, target=5)
        subphase = SubPhaseLog(micro_phase=SubPhase.WEREWOLF_ACTION, events=[kill])
        assert len(subphase.events) == 1
        assert subphase.events[0] == kill
        assert "WEREWOLF_ACTION" in str(subphase)
        assert "5" in str(subphase)  # target seat

    def test_subphase_with_multiple_events(self):
        """Test SubPhaseLog with multiple events."""
        speech1 = Speech(actor=0, day=1, micro_phase=SubPhase.CAMPAIGN, content="Vote me!")
        speech2 = Speech(actor=1, day=1, micro_phase=SubPhase.CAMPAIGN, content="No, vote me!")
        subphase = SubPhaseLog(micro_phase=SubPhase.CAMPAIGN, events=[speech1, speech2])
        assert len(subphase.events) == 2
        output = str(subphase)
        assert "CAMPAIGN" in output
        assert "Vote me!" in output
        assert "No, vote me!" in output


class TestPhase:
    """Tests for unified Phase container."""

    def test_phase_night_basic(self):
        """Test basic Night Phase creation."""
        night = PhaseLog(number=1, kind=Phase.NIGHT)
        assert night.number == 1
        assert night.kind == Phase.NIGHT
        assert len(night.subphases) == 0

    def test_phase_day_basic(self):
        """Test basic Day Phase creation."""
        day = PhaseLog(number=1, kind=Phase.DAY)
        assert day.number == 1
        assert day.kind == Phase.DAY
        assert len(day.subphases) == 0

    def test_phase_with_subphases(self):
        """Test Phase with subphases."""
        kill = WerewolfKill(actor=0, day=1, target=5)
        werewolf_sp = SubPhaseLog(micro_phase=SubPhase.WEREWOLF_ACTION, events=[kill])

        guard_action = GuardAction(actor=1, day=1, target=3)
        guard_sp = SubPhaseLog(micro_phase=SubPhase.GUARD_ACTION, events=[guard_action])

        night = PhaseLog(number=1, kind=Phase.NIGHT, subphases=[werewolf_sp, guard_sp])
        assert len(night.subphases) == 2

    def test_phase_str_empty_night(self):
        """Test Phase string representation for empty night."""
        night = PhaseLog(number=1, kind=Phase.NIGHT)
        assert "NIGHT 1" in str(night)
        assert "(no events)" in str(night)

    def test_phase_str_empty_day(self):
        """Test Phase string representation for empty day."""
        day = PhaseLog(number=1, kind=Phase.DAY)
        assert "DAY 1" in str(day)
        assert "(no events)" in str(day)

    def test_phase_str_with_subphases(self):
        """Test Phase string representation with subphases."""
        kill = WerewolfKill(actor=0, day=1, target=5)
        werewolf_sp = SubPhaseLog(micro_phase=SubPhase.WEREWOLF_ACTION, events=[kill])
        night = PhaseLog(number=1, kind=Phase.NIGHT, subphases=[werewolf_sp])
        output = str(night)
        assert "NIGHT 1" in output
        assert "WEREWOLF_ACTION" in output


class TestGameEventLog:
    """Tests for GameEventLog."""

    def test_game_event_log_basic(self):
        """Test basic GameEventLog creation."""
        log = GameEventLog(player_count=12)
        assert log.player_count == 12
        assert len(log.phases) == 0
        assert log.game_start is None
        assert log.game_over is None

    def test_game_event_log_default_game_id(self):
        """Test that game_id is auto-generated."""
        log = GameEventLog(player_count=12)
        assert log.game_id is not None
        assert len(log.game_id) > 0

    def test_game_event_log_created_at(self):
        """Test that created_at is set."""
        log = GameEventLog(player_count=12)
        assert log.created_at is not None
        assert "T" in log.created_at  # ISO format

    def test_game_event_log_add_night_phase(self):
        """Test adding a night phase to the log."""
        log = GameEventLog(player_count=12)
        night = PhaseLog(number=1, kind=Phase.NIGHT)
        log.add_phase(night)
        assert len(log.phases) == 1
        assert log.current_night == 1
        assert log.current_day == 0

    def test_game_event_log_add_day_phase(self):
        """Test adding a day phase to the log."""
        log = GameEventLog(player_count=12)
        day = PhaseLog(number=1, kind=Phase.DAY)
        log.add_phase(day)
        assert len(log.phases) == 1
        assert log.current_day == 1
        assert log.current_night == 0

    def test_game_event_log_add_multiple_phases(self):
        """Test adding multiple phases in order."""
        log = GameEventLog(player_count=12)
        night1 = PhaseLog(number=1, kind=Phase.NIGHT)
        day1 = PhaseLog(number=1, kind=Phase.DAY)
        night2 = PhaseLog(number=2, kind=Phase.NIGHT)
        log.add_phase(night1)
        log.add_phase(day1)
        log.add_phase(night2)
        assert len(log.phases) == 3

    def test_game_event_log_duplicate_night_raises(self):
        """Test that adding duplicate Night raises ValueError."""
        log = GameEventLog(player_count=12)
        night1 = PhaseLog(number=1, kind=Phase.NIGHT)
        night1_copy = PhaseLog(number=1, kind=Phase.NIGHT)
        log.add_phase(night1)
        with pytest.raises(ValueError, match="Night 1 already exists"):
            log.add_phase(night1_copy)

    def test_game_event_log_duplicate_day_raises(self):
        """Test that adding duplicate Day raises ValueError."""
        log = GameEventLog(player_count=12)
        day1 = PhaseLog(number=1, kind=Phase.DAY)
        day1_copy = PhaseLog(number=1, kind=Phase.DAY)
        log.add_phase(day1)
        with pytest.raises(ValueError, match="Day 1 already exists"):
            log.add_phase(day1_copy)

    def test_game_event_log_get_night(self):
        """Test get_night method."""
        log = GameEventLog(player_count=12)
        night1 = PhaseLog(number=1, kind=Phase.NIGHT)
        night2 = PhaseLog(number=2, kind=Phase.NIGHT)
        log.add_phase(night1)
        log.add_phase(night2)

        assert log.get_night(1) == night1
        assert log.get_night(2) == night2
        assert log.get_night(3) is None

    def test_game_event_log_get_day(self):
        """Test get_day method."""
        log = GameEventLog(player_count=12)
        day1 = PhaseLog(number=1, kind=Phase.DAY)
        day2 = PhaseLog(number=2, kind=Phase.DAY)
        log.add_phase(day1)
        log.add_phase(day2)

        assert log.get_day(1) == day1
        assert log.get_day(2) == day2
        assert log.get_day(3) is None

    def test_game_event_log_current_night_empty(self):
        """Test current_night when no phases added."""
        log = GameEventLog(player_count=12)
        assert log.current_night == 0

    def test_game_event_log_current_day_empty(self):
        """Test current_day when no phases added."""
        log = GameEventLog(player_count=12)
        assert log.current_day == 0

    def test_game_event_log_current_night_with_only_day(self):
        """Test current_night when only day phases exist."""
        log = GameEventLog(player_count=12)
        day = PhaseLog(number=1, kind=Phase.DAY)
        log.add_phase(day)
        assert log.current_night == 0

    def test_game_event_log_current_day_with_only_night(self):
        """Test current_day when only night phases exist."""
        log = GameEventLog(player_count=12)
        night = PhaseLog(number=1, kind=Phase.NIGHT)
        log.add_phase(night)
        assert log.current_day == 0


class TestGameEventLogQueries:
    """Tests for GameEventLog query methods."""

    def test_get_all_deaths_empty(self):
        """Test get_all_deaths when no deaths."""
        log = GameEventLog(player_count=12)
        assert log.get_all_deaths() == []

    def test_get_all_deaths_with_night_deaths(self):
        """Test get_all_deaths with night deaths."""
        log = GameEventLog(player_count=12)

        # Add night with deaths
        resolution = NightResolution(day=1, deaths=[5, 7])
        resolution_sp = SubPhaseLog(micro_phase=SubPhase.NIGHT_RESOLUTION, events=[resolution])
        night1 = PhaseLog(number=1, kind=Phase.NIGHT, subphases=[resolution_sp])
        log.add_phase(night1)

        # Add another night with different deaths
        resolution2 = NightResolution(day=2, deaths=[3])
        resolution_sp2 = SubPhaseLog(micro_phase=SubPhase.NIGHT_RESOLUTION, events=[resolution2])
        night2 = PhaseLog(number=2, kind=Phase.NIGHT, subphases=[resolution_sp2])
        log.add_phase(night2)

        deaths = log.get_all_deaths()
        assert len(deaths) == 3
        assert 5 in deaths
        assert 7 in deaths
        assert 3 in deaths

    def test_get_all_speeches_empty(self):
        """Test get_all_speeches when no speeches."""
        log = GameEventLog(player_count=12)
        assert log.get_all_speeches() == []

    def test_get_all_speeches_with_campaign(self):
        """Test get_all_speeches with campaign speeches."""
        log = GameEventLog(player_count=12)

        speech1 = Speech(
            actor=0, day=1, micro_phase=SubPhase.CAMPAIGN, content="Speech 1"
        )
        campaign = SubPhaseLog(micro_phase=SubPhase.CAMPAIGN, events=[speech1])
        day1 = PhaseLog(number=1, kind=Phase.DAY, subphases=[campaign])
        log.add_phase(day1)

        speeches = log.get_all_speeches()
        assert len(speeches) == 1
        assert speeches[0] == (1, "Speech 1")

    def test_get_all_speeches_multiple_days(self):
        """Test get_all_speeches across multiple days."""
        log = GameEventLog(player_count=12)

        # Day 1
        speech1 = Speech(
            actor=0, day=1, micro_phase=SubPhase.CAMPAIGN, content="Day 1 speech"
        )
        campaign = SubPhaseLog(micro_phase=SubPhase.CAMPAIGN, events=[speech1])
        day1 = PhaseLog(number=1, kind=Phase.DAY, subphases=[campaign])
        log.add_phase(day1)

        # Day 2
        speech2 = Speech(
            actor=3, day=2, micro_phase=SubPhase.DISCUSSION, content="Day 2 speech"
        )
        discussion = SubPhaseLog(micro_phase=SubPhase.DISCUSSION, events=[speech2])
        day2 = PhaseLog(number=2, kind=Phase.DAY, subphases=[discussion])
        log.add_phase(day2)

        speeches = log.get_all_speeches()
        assert len(speeches) == 2
        assert speeches[0] == (1, "Day 1 speech")
        assert speeches[1] == (2, "Day 2 speech")

    def test_get_sheriffs_empty(self):
        """Test get_sheriffs when no sheriff elected."""
        log = GameEventLog(player_count=12)
        day = PhaseLog(number=1, kind=Phase.DAY)
        log.add_phase(day)
        assert log.get_sheriffs() == {}

    def test_get_sheriffs_with_election(self):
        """Test get_sheriffs with sheriff election."""
        log = GameEventLog(player_count=12)

        election = SheriffElection(day=1, winner=3)
        election_sp = SubPhaseLog(micro_phase=SubPhase.SHERIFF_ELECTION, events=[election])
        day1 = PhaseLog(number=1, kind=Phase.DAY, subphases=[election_sp])
        log.add_phase(day1)

        sheriffs = log.get_sheriffs()
        assert sheriffs == {1: 3}

    def test_get_sheriffs_multiple_days(self):
        """Test get_sheriffs across multiple days (only Day 1 has sheriff election)."""
        log = GameEventLog(player_count=12)

        # Day 1 election
        election1 = SheriffElection(day=1, winner=3)
        election_sp1 = SubPhaseLog(micro_phase=SubPhase.SHERIFF_ELECTION, events=[election1])
        day1 = PhaseLog(number=1, kind=Phase.DAY, subphases=[election_sp1])
        log.add_phase(day1)

        # Day 2 (no sheriff election)
        discussion = SubPhaseLog(micro_phase=SubPhase.DISCUSSION)
        day2 = PhaseLog(number=2, kind=Phase.DAY, subphases=[discussion])
        log.add_phase(day2)

        sheriffs = log.get_sheriffs()
        assert sheriffs == {1: 3}


class TestGameEventLogSerialization:
    """Tests for GameEventLog YAML serialization."""

    def test_to_yaml_basic(self):
        """Test basic to_yaml serialization."""
        log = GameEventLog(player_count=12)
        yaml_str = log.to_yaml(include_roles=False)
        assert "player_count: 12" in yaml_str

    def test_to_yaml_with_game_start(self):
        """Test to_yaml with game_start set."""
        log = GameEventLog(player_count=12)
        game_start = GameStart(player_count=12, roles_secret={0: "Werewolf"})
        log.game_start = game_start

        yaml_str = log.to_yaml(include_roles=False)
        assert "GameStart" in yaml_str or "game_start" in yaml_str

    def test_to_yaml_excludes_roles_by_default(self):
        """Test that roles_secret is excluded by default."""
        log = GameEventLog(player_count=12)
        log.roles_secret = {0: "Werewolf", 1: "Seer"}

        yaml_str = log.to_yaml()  # include_roles=False by default
        assert "Werewolf" not in yaml_str
        assert "Seer" not in yaml_str

    def test_to_yaml_includes_roles_when_requested(self):
        """Test that roles_secret is included when requested."""
        log = GameEventLog(player_count=12)
        log.roles_secret = {0: "Werewolf", 1: "Seer"}

        yaml_str = log.to_yaml(include_roles=True)
        assert "Werewolf" in yaml_str
        assert "Seer" in yaml_str

    def test_to_yaml_with_phases(self):
        """Test to_yaml with phases."""
        log = GameEventLog(player_count=12)

        kill = WerewolfKill(actor=0, day=1, target=5)
        werewolf_sp = SubPhaseLog(micro_phase=SubPhase.WEREWOLF_ACTION, events=[kill])
        night = PhaseLog(number=1, kind=Phase.NIGHT, subphases=[werewolf_sp])
        log.add_phase(night)

        yaml_str = log.to_yaml()
        assert "NIGHT" in yaml_str or "night" in yaml_str

    def test_save_to_file_and_load_from_file(self):
        """Test round-trip save and load."""
        log = GameEventLog(player_count=12)

        # Set up game start
        game_start = GameStart(player_count=12, roles_secret={0: "Werewolf"})
        log.game_start = game_start

        # Add a night with action
        kill = WerewolfKill(actor=0, day=1, target=5)
        werewolf_sp = SubPhaseLog(micro_phase=SubPhase.WEREWOLF_ACTION, events=[kill])
        night = PhaseLog(number=1, kind=Phase.NIGHT, subphases=[werewolf_sp])
        log.add_phase(night)

        # Save to temp file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            filepath = f.name

        try:
            log.save_to_file(filepath, include_roles=False)

            # Load back
            loaded_log = GameEventLog.load_from_file(filepath)
            assert loaded_log.player_count == 12
            assert len(loaded_log.phases) == 1
            assert loaded_log.current_night == 1
        finally:
            os.unlink(filepath)


class TestGameEventLogStr:
    """Tests for GameEventLog string representation."""

    def test_str_empty(self):
        """Test str of empty log."""
        log = GameEventLog(player_count=12)
        output = str(log)
        assert "Game" in output
        assert "12 players" in output

    def test_str_with_game_start(self):
        """Test str with game_start."""
        log = GameEventLog(player_count=12)
        game_start = GameStart(player_count=12)
        log.game_start = game_start
        output = str(log)
        assert "Started" in output

    def test_str_with_phases(self):
        """Test str with phases."""
        log = GameEventLog(player_count=12)

        kill = WerewolfKill(actor=0, day=1, target=5)
        werewolf_sp = SubPhaseLog(micro_phase=SubPhase.WEREWOLF_ACTION, events=[kill])
        night = PhaseLog(number=1, kind=Phase.NIGHT, subphases=[werewolf_sp])
        log.add_phase(night)

        output = str(log)
        assert "NIGHT 1" in output
        assert "WEREWOLF_ACTION" in output

    def test_str_with_game_over(self):
        """Test str with game_over."""
        log = GameEventLog(player_count=12)
        game_over = GameOver(
            winner="WEREWOLF",
            condition=VictoryCondition.ALL_WEREWOLVES_BANISHED,
            final_turn_count=5,
        )
        log.game_over = game_over
        output = str(log)
        assert "Game Over" in output
        assert "WEREWOLF" in output


class TestGameEventLogModelDump:
    """Tests for GameEventLog model_dump summary."""

    def test_model_dump_includes_summary(self):
        """Test that model_dump includes summary."""
        log = GameEventLog(player_count=12)

        # Add a night with deaths
        resolution = NightResolution(day=1, deaths=[5])
        resolution_sp = SubPhaseLog(micro_phase=SubPhase.NIGHT_RESOLUTION, events=[resolution])
        night = PhaseLog(number=1, kind=Phase.NIGHT, subphases=[resolution_sp])
        log.add_phase(night)

        # Add a day with speeches
        speech = Speech(actor=0, day=1, micro_phase=SubPhase.CAMPAIGN, content="Hello")
        campaign = SubPhaseLog(micro_phase=SubPhase.CAMPAIGN, events=[speech])
        day = PhaseLog(number=1, kind=Phase.DAY, subphases=[campaign])
        log.add_phase(day)

        data = log.model_dump()
        assert "summary" in data
        summary = data["summary"]
        assert summary["total_nights"] == 1
        assert summary["total_days"] == 1
        assert summary["total_speeches"] == 1
        assert summary["total_deaths"] == 1

    def test_model_dump_empty_summary(self):
        """Test summary for empty log."""
        log = GameEventLog(player_count=12)
        data = log.model_dump()
        summary = data["summary"]
        assert summary["total_nights"] == 0
        assert summary["total_days"] == 0
        assert summary["total_speeches"] == 0
        assert summary["total_deaths"] == 0


class TestIntegration:
    """Integration tests simulating full game scenarios."""

    def test_night_1_complete(self):
        """Test building a complete Night 1 scenario."""
        log = GameEventLog(player_count=12)

        # Werewolf kill
        werewolf_kill = WerewolfKill(actor=0, day=1, target=5)
        werewolf_sp = SubPhaseLog(micro_phase=SubPhase.WEREWOLF_ACTION, events=[werewolf_kill])

        # Witch action
        witch_action = WitchAction(
            actor=2, day=1, action_type=WitchActionType.PASS
        )
        witch_sp = SubPhaseLog(micro_phase=SubPhase.WITCH_ACTION, events=[witch_action])

        # Guard action
        guard_action = GuardAction(actor=1, day=1, target=3)
        guard_sp = SubPhaseLog(micro_phase=SubPhase.GUARD_ACTION, events=[guard_action])

        # Seer action
        seer_action = SeerAction(actor=3, day=1, target=0, result=SeerResult.WEREWOLF)
        seer_sp = SubPhaseLog(micro_phase=SubPhase.SEER_ACTION, events=[seer_action])

        # Night resolution - player 5 dies
        night_resolution = NightResolution(day=1, deaths=[5])
        resolution_sp = SubPhaseLog(micro_phase=SubPhase.NIGHT_RESOLUTION, events=[night_resolution])

        night1 = PhaseLog(
            number=1,
            kind=Phase.NIGHT,
            subphases=[werewolf_sp, witch_sp, guard_sp, seer_sp, resolution_sp],
        )
        log.add_phase(night1)

        assert log.current_night == 1
        assert log.get_all_deaths() == [5]

    def test_day_1_complete(self):
        """Test building a complete Day 1 scenario."""
        log = GameEventLog(player_count=12)

        # Sheriff campaign speeches
        speech1 = Speech(actor=0, day=1, micro_phase=SubPhase.CAMPAIGN, content="I should be Sheriff!")
        speech2 = Speech(actor=3, day=1, micro_phase=SubPhase.CAMPAIGN, content="Vote for me!")
        campaign = SubPhaseLog(micro_phase=SubPhase.CAMPAIGN, events=[speech1, speech2])

        # Opt outs
        opt_out = SheriffOptOut(actor=5, day=1)
        opt_out_sp = SubPhaseLog(micro_phase=SubPhase.OPT_OUT, events=[opt_out])

        # Sheriff election
        election = SheriffElection(day=1, winner=0)
        election_sp = SubPhaseLog(micro_phase=SubPhase.SHERIFF_ELECTION, events=[election])

        # Death announcement
        announcement = DeathAnnouncement(day=1, dead_players=[7])
        death_sp = SubPhaseLog(micro_phase=SubPhase.DEATH_ANNOUNCEMENT, events=[announcement])

        # Last words
        last_words = Speech(actor=7, day=1, micro_phase=SubPhase.LAST_WORDS, content="I was the Guard!")
        last_words_sp = SubPhaseLog(micro_phase=SubPhase.LAST_WORDS, events=[last_words])

        # Discussion
        discussion_speech = Speech(actor=3, day=1, micro_phase=SubPhase.DISCUSSION, content="Player 0 is suspicious!")
        discussion = SubPhaseLog(micro_phase=SubPhase.DISCUSSION, events=[discussion_speech])

        # Voting
        votes = [
            Vote(actor=0, day=1, target=3),
            Vote(actor=1, day=1, target=3),
            Vote(actor=2, day=1, target=3),
            Vote(actor=4, day=1, target=None),  # abstain
        ]
        voting = SubPhaseLog(micro_phase=SubPhase.VOTING, events=votes)

        # Victory check
        victory_check = VictoryCheck(phase=Phase.DAY, is_game_over=False)
        victory_sp = SubPhaseLog(micro_phase=SubPhase.VICTORY_CHECK, events=[victory_check])

        day1 = PhaseLog(
            number=1,
            kind=Phase.DAY,
            subphases=[
                campaign,
                opt_out_sp,
                election_sp,
                death_sp,
                last_words_sp,
                discussion,
                voting,
                victory_sp,
            ],
        )
        log.add_phase(day1)

        assert log.current_day == 1
        sheriffs = log.get_sheriffs()
        assert sheriffs == {1: 0}
        speeches = log.get_all_speeches()
        assert len(speeches) == 4  # 2 campaign + 1 last words + 1 discussion

    def test_game_over_scenario(self):
        """Test a complete game over scenario."""
        log = GameEventLog(player_count=12)

        # Game start
        game_start = GameStart(player_count=12, roles_secret={0: "Werewolf"})
        log.game_start = game_start

        # Night 1 with deaths
        night_resolution = NightResolution(day=1, deaths=[5])
        resolution_sp = SubPhaseLog(micro_phase=SubPhase.NIGHT_RESOLUTION, events=[night_resolution])
        night1 = PhaseLog(number=1, kind=Phase.NIGHT, subphases=[resolution_sp])
        log.add_phase(night1)

        # Day 1
        day1 = PhaseLog(number=1, kind=Phase.DAY)
        log.add_phase(day1)

        # Night 2 with deaths
        night_resolution2 = NightResolution(day=2, deaths=[7, 8])
        resolution_sp2 = SubPhaseLog(micro_phase=SubPhase.NIGHT_RESOLUTION, events=[night_resolution2])
        night2 = PhaseLog(number=2, kind=Phase.NIGHT, subphases=[resolution_sp2])
        log.add_phase(night2)

        # Game over
        game_over = GameOver(
            winner="WEREWOLF",
            condition=VictoryCondition.ALL_WEREWOLVES_KILLED,
            final_turn_count=4,
        )
        log.game_over = game_over

        deaths = log.get_all_deaths()
        assert len(deaths) == 3
        assert set(deaths) == {5, 7, 8}

        # Serialization test - verify YAML output is valid
        yaml_str = log.to_yaml(include_roles=False)
        assert "NIGHT" in yaml_str or "night" in yaml_str
        assert "DAY" in yaml_str or "day" in yaml_str
        assert "GameOver" in yaml_str or "GAME_OVER" in yaml_str
        assert "WEREWOLF" in yaml_str
        assert "deaths" in yaml_str.lower()
