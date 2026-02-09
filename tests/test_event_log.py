"""Tests for the event_log module."""

import pytest
import tempfile
import os
from pathlib import Path

from src.werewolf.events.event_log import (
    GameEventLog,
    NightPhase,
    DayPhase,
    WerewolfActionSubPhase,
    WitchActionSubPhase,
    GuardActionSubPhase,
    SeerActionSubPhase,
    NightResolutionSubPhase,
    CampaignSubPhase,
    OptOutSubPhase,
    SheriffElectionSubPhase,
    DeathAnnouncementSubPhase,
    LastWordsSubPhase,
    DiscussionSubPhase,
    VotingSubPhase,
    BanishedLastWordsSubPhase,
    VictoryCheckSubPhase,
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
    MicroPhase,
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


class TestNightSubPhases:
    """Tests for NightSubPhase data containers."""

    def test_werewolf_action_subphase_pending(self):
        """Test WerewolfActionSubPhase with no action."""
        subphase = WerewolfActionSubPhase()
        assert subphase.kill is None
        assert subphase.micro_phase == MicroPhase.WEREWOLF_ACTION
        assert "pending" in str(subphase)

    def test_werewolf_action_subphase_with_kill(self):
        """Test WerewolfActionSubPhase with a kill action."""
        kill = WerewolfKill(actor=0, day=1, target=5)
        subphase = WerewolfActionSubPhase(kill=kill)
        assert subphase.kill == kill
        assert "kill seat 5" in str(subphase)

    def test_werewolf_action_subphase_no_kill(self):
        """Test WerewolfActionSubPhase when werewolves choose not to kill."""
        kill = WerewolfKill(actor=0, day=1, target=None)
        subphase = WerewolfActionSubPhase(kill=kill)
        assert "no kill" in str(subphase)

    def test_witch_action_subphase_pending(self):
        """Test WitchActionSubPhase with no action."""
        subphase = WitchActionSubPhase()
        assert subphase.action is None
        assert "pending" in str(subphase)

    def test_witch_action_subphase_pass(self):
        """Test WitchActionSubPhase with pass action."""
        action = WitchAction(
            actor=2, day=1, action_type=WitchActionType.PASS
        )
        subphase = WitchActionSubPhase(action=action)
        assert "pass" in str(subphase)  # "WitchAction: pass"

    def test_witch_action_subphase_antidote(self):
        """Test WitchActionSubPhase with antidote action."""
        action = WitchAction(
            actor=2, day=1, action_type=WitchActionType.ANTIDOTE, target=5
        )
        subphase = WitchActionSubPhase(action=action)
        assert "ANTIDOTE" in str(subphase)
        assert "seat 5" in str(subphase)

    def test_witch_action_subphase_poison(self):
        """Test WitchActionSubPhase with poison action."""
        action = WitchAction(
            actor=2, day=1, action_type=WitchActionType.POISON, target=7
        )
        subphase = WitchActionSubPhase(action=action)
        assert "POISON" in str(subphase)
        assert "seat 7" in str(subphase)

    def test_guard_action_subphase_pending(self):
        """Test GuardActionSubPhase with no action."""
        subphase = GuardActionSubPhase()
        assert subphase.action is None
        assert "pending" in str(subphase)

    def test_guard_action_subphase_with_target(self):
        """Test GuardActionSubPhase with a protect target."""
        action = GuardAction(actor=1, day=1, target=5)
        subphase = GuardActionSubPhase(action=action)
        assert "protect seat 5" in str(subphase)

    def test_guard_action_subphase_skip(self):
        """Test GuardActionSubPhase when guard skips."""
        action = GuardAction(actor=1, day=1, target=None)
        subphase = GuardActionSubPhase(action=action)
        assert "skip" in str(subphase)

    def test_seer_action_subphase_pending(self):
        """Test SeerActionSubPhase with no action."""
        subphase = SeerActionSubPhase()
        assert subphase.action is None
        assert "pending" in str(subphase)

    def test_seer_action_subphase_good_result(self):
        """Test SeerActionSubPhase with GOOD result."""
        action = SeerAction(actor=3, day=1, target=5, result=SeerResult.GOOD)
        subphase = SeerActionSubPhase(action=action)
        assert "check seat 5 = GOOD" in str(subphase)

    def test_seer_action_subphase_werewolf_result(self):
        """Test SeerActionSubPhase with WEREWOLF result."""
        action = SeerAction(actor=3, day=1, target=5, result=SeerResult.WEREWOLF)
        subphase = SeerActionSubPhase(action=action)
        assert "check seat 5 = WEREWOLF" in str(subphase)

    def test_night_resolution_subphase_pending(self):
        """Test NightResolutionSubPhase with no resolution."""
        subphase = NightResolutionSubPhase()
        assert subphase.resolution is None
        assert "pending" in str(subphase)

    def test_night_resolution_subphase_with_deaths(self):
        """Test NightResolutionSubPhase with deaths."""
        resolution = NightResolution(day=1, deaths=[5, 7])
        subphase = NightResolutionSubPhase(resolution=resolution)
        assert "deaths = [5, 7]" in str(subphase)

    def test_night_resolution_subphase_no_deaths(self):
        """Test NightResolutionSubPhase when no one dies."""
        resolution = NightResolution(day=1, deaths=[])
        subphase = NightResolutionSubPhase(resolution=resolution)
        assert "no deaths" in str(subphase)


class TestDaySubPhases:
    """Tests for DaySubPhase data containers."""

    def test_campaign_subphase_empty(self):
        """Test CampaignSubPhase with no speeches."""
        subphase = CampaignSubPhase()
        assert len(subphase.speeches) == 0
        assert "no speeches" in str(subphase)

    def test_campaign_subphase_with_speech(self):
        """Test CampaignSubPhase with a campaign speech."""
        speech = Speech(
            actor=0, day=1, micro_phase=MicroPhase.CAMPAIGN, content="Vote for me!"
        )
        subphase = CampaignSubPhase(speeches=[speech])
        assert len(subphase.speeches) == 1
        assert "Vote for me!" in str(subphase)
        assert "Seat 0" in str(subphase)

    def test_campaign_subphase_long_content_preview(self):
        """Test CampaignSubPhase truncates long speech content."""
        long_content = "A" * 100
        speech = Speech(actor=0, day=1, micro_phase=MicroPhase.CAMPAIGN, content=long_content)
        subphase = CampaignSubPhase(speeches=[speech])
        assert "..." in str(subphase)
        assert len(long_content) > 50

    def test_opt_out_subphase_empty(self):
        """Test OptOutSubPhase with no opt-outs."""
        subphase = OptOutSubPhase()
        assert len(subphase.opt_outs) == 0
        assert "no one dropped out" in str(subphase)

    def test_opt_out_subphase_with_opt_outs(self):
        """Test OptOutSubPhase with players dropping out."""
        opt_out1 = SheriffOptOut(actor=2, day=1)
        opt_out2 = SheriffOptOut(actor=5, day=1)
        subphase = OptOutSubPhase(opt_outs=[opt_out1, opt_out2])
        assert len(subphase.opt_outs) == 2
        assert "[2, 5]" in str(subphase)

    def test_sheriff_election_subphase_pending(self):
        """Test SheriffElectionSubPhase with no election."""
        subphase = SheriffElectionSubPhase()
        assert subphase.election is None
        assert "pending" in str(subphase)

    def test_sheriff_election_subphase_with_winner(self):
        """Test SheriffElectionSubPhase with a winner."""
        election = SheriffElection(day=1, winner=3)
        subphase = SheriffElectionSubPhase(election=election)
        assert "winner = seat 3" in str(subphase)

    def test_sheriff_election_subphase_tie(self):
        """Test SheriffElectionSubPhase when no winner (tie)."""
        election = SheriffElection(day=1, winner=None)
        subphase = SheriffElectionSubPhase(election=election)
        assert "no winner" in str(subphase)

    def test_death_announcement_subphase_pending(self):
        """Test DeathAnnouncementSubPhase with no announcement."""
        subphase = DeathAnnouncementSubPhase()
        assert subphase.announcement is None
        assert "pending" in str(subphase)

    def test_death_announcement_subphase_with_deaths(self):
        """Test DeathAnnouncementSubPhase with dead players."""
        announcement = DeathAnnouncement(day=1, dead_players=[5, 7])
        subphase = DeathAnnouncementSubPhase(announcement=announcement)
        assert "dead = [5, 7]" in str(subphase)

    def test_death_announcement_subphase_no_deaths(self):
        """Test DeathAnnouncementSubPhase when no one died."""
        announcement = DeathAnnouncement(day=1, dead_players=[])
        subphase = DeathAnnouncementSubPhase(announcement=announcement)
        assert "no deaths" in str(subphase)

    def test_last_words_subphase_empty(self):
        """Test LastWordsSubPhase with no speeches."""
        subphase = LastWordsSubPhase()
        assert len(subphase.speeches) == 0
        assert "no speeches" in str(subphase)

    def test_last_words_subphase_with_speech(self):
        """Test LastWordsSubPhase with last words."""
        speech = Speech(
            actor=5, day=1, micro_phase=MicroPhase.LAST_WORDS, content="I was the seer!"
        )
        subphase = LastWordsSubPhase(speeches=[speech])
        assert len(subphase.speeches) == 1
        assert "I was the seer!" in str(subphase)

    def test_discussion_subphase_empty(self):
        """Test DiscussionSubPhase with no speeches."""
        subphase = DiscussionSubPhase()
        assert len(subphase.speeches) == 0
        assert "no speeches" in str(subphase)

    def test_discussion_subphase_with_speeches(self):
        """Test DiscussionSubPhase with multiple speeches."""
        speech1 = Speech(
            actor=0, day=1, micro_phase=MicroPhase.DISCUSSION, content="I trust player 3."
        )
        speech2 = Speech(
            actor=3, day=1, micro_phase=MicroPhase.DISCUSSION, content="I'm innocent!"
        )
        subphase = DiscussionSubPhase(speeches=[speech1, speech2])
        assert len(subphase.speeches) == 2

    def test_voting_subphase_empty(self):
        """Test VotingSubPhase with no votes."""
        subphase = VotingSubPhase()
        assert len(subphase.votes) == 0
        assert "no votes" in str(subphase)

    def test_voting_subphase_with_votes(self):
        """Test VotingSubPhase with votes."""
        votes = [
            Vote(actor=0, day=1, target=5),
            Vote(actor=1, day=1, target=5),
            Vote(actor=2, day=1, target=7),
        ]
        subphase = VotingSubPhase(votes=votes)
        assert len(subphase.votes) == 3
        assert "2 for seat 7" in str(subphase) or "2 for seat 5" in str(subphase)

    def test_voting_subphase_abstain(self):
        """Test VotingSubPhase with abstain votes."""
        votes = [
            Vote(actor=0, day=1, target=None),  # abstain
            Vote(actor=1, day=1, target=5),
        ]
        subphase = VotingSubPhase(votes=votes)
        assert "abstain" in str(subphase)

    def test_banished_last_words_subphase_no_speech(self):
        """Test BanishedLastWordsSubPhase with no speech."""
        subphase = BanishedLastWordsSubPhase()
        assert subphase.speech is None
        assert "no speech" in str(subphase)

    def test_banished_last_words_subphase_with_speech(self):
        """Test BanishedLastWordsSubPhase with a speech."""
        speech = Speech(
            actor=5, day=1, micro_phase=MicroPhase.BANNED_LAST_WORDS, content="Good game!"
        )
        subphase = BanishedLastWordsSubPhase(speech=speech)
        assert "seat 5" in str(subphase)
        assert "Good game!" in str(subphase)

    def test_victory_check_subphase_pending(self):
        """Test VictoryCheckSubPhase with no check."""
        subphase = VictoryCheckSubPhase()
        assert subphase.check is None
        assert "pending" in str(subphase)

    def test_victory_check_subphase_game_continues(self):
        """Test VictoryCheckSubPhase when game continues."""
        check = VictoryCheck(phase=Phase.DAY, is_game_over=False)
        subphase = VictoryCheckSubPhase(check=check)
        assert "game continues" in str(subphase)

    def test_victory_check_subphase_game_over(self):
        """Test VictoryCheckSubPhase when game is over."""
        check = VictoryCheck(
            phase=Phase.DAY,
            is_game_over=True,
            winner="WEREWOLF",
            condition=VictoryCondition.ALL_WEREWOLVES_KILLED,
        )
        subphase = VictoryCheckSubPhase(check=check)
        assert "WEREWOLF" in str(subphase)
        assert "WOLVES_KILLED" in str(subphase)


class TestNightPhase:
    """Tests for NightPhase container."""

    def test_night_phase_basic(self):
        """Test basic NightPhase creation."""
        night = NightPhase(night_number=1)
        assert night.night_number == 1
        assert night.phase.value == "NIGHT"
        assert len(night.subphases) == 0

    def test_night_phase_with_subphases(self):
        """Test NightPhase with subphases."""
        kill = WerewolfKill(actor=0, day=1, target=5)
        werewolf_sp = WerewolfActionSubPhase(kill=kill)

        guard_action = GuardAction(actor=1, day=1, target=3)
        guard_sp = GuardActionSubPhase(action=guard_action)

        night = NightPhase(night_number=1, subphases=[werewolf_sp, guard_sp])
        assert len(night.subphases) == 2

    def test_night_phase_deaths_property(self):
        """Test NightPhase.deaths property."""
        night = NightPhase(night_number=1)

        # No resolution yet
        assert night.deaths == []

        # With resolution
        resolution = NightResolution(day=1, deaths=[5, 7])
        resolution_sp = NightResolutionSubPhase(resolution=resolution)
        night.subphases.append(resolution_sp)
        assert night.deaths == [5, 7]

    def test_night_phase_str_empty(self):
        """Test NightPhase string representation with no subphases."""
        night = NightPhase(night_number=1)
        assert "(no actions)" in str(night)

    def test_night_phase_str_with_subphases(self):
        """Test NightPhase string representation with subphases."""
        kill = WerewolfKill(actor=0, day=1, target=5)
        werewolf_sp = WerewolfActionSubPhase(kill=kill)
        night = NightPhase(night_number=1, subphases=[werewolf_sp])
        output = str(night)
        assert "Night 1" in output
        assert "kill seat 5" in output


class TestDayPhase:
    """Tests for DayPhase container."""

    def test_day_phase_basic(self):
        """Test basic DayPhase creation."""
        day = DayPhase(day_number=1)
        assert day.day_number == 1
        assert day.phase.value == "DAY"
        assert len(day.subphases) == 0

    def test_day_phase_is_day1(self):
        """Test DayPhase.is_day1 property."""
        day1 = DayPhase(day_number=1)
        day2 = DayPhase(day_number=2)
        assert day1.is_day1 is True
        assert day2.is_day1 is False

    def test_day_phase_all_speeches_empty(self):
        """Test DayPhase.all_speeches when no speeches."""
        day = DayPhase(day_number=1)
        assert day.all_speeches == []

    def test_day_phase_all_speeches_from_campaign(self):
        """Test DayPhase.all_speeches from CampaignSubPhase."""
        speech = Speech(
            actor=0, day=1, micro_phase=MicroPhase.CAMPAIGN, content="Vote me!"
        )
        campaign = CampaignSubPhase(speeches=[speech])
        day = DayPhase(day_number=1, subphases=[campaign])
        assert len(day.all_speeches) == 1
        assert day.all_speeches[0].content == "Vote me!"

    def test_day_phase_all_speeches_from_discussion(self):
        """Test DayPhase.all_speeches from DiscussionSubPhase."""
        speech = Speech(
            actor=3, day=1, micro_phase=MicroPhase.DISCUSSION, content="I'm innocent."
        )
        discussion = DiscussionSubPhase(speeches=[speech])
        day = DayPhase(day_number=1, subphases=[discussion])
        assert len(day.all_speeches) == 1
        assert day.all_speeches[0].content == "I'm innocent."

    def test_day_phase_all_speeches_from_multiple_sources(self):
        """Test DayPhase.all_speeches from multiple subphases."""
        campaign_speech = Speech(
            actor=0, day=1, micro_phase=MicroPhase.CAMPAIGN, content="Campaign."
        )
        discussion_speech = Speech(
            actor=3, day=1, micro_phase=MicroPhase.DISCUSSION, content="Discussion."
        )
        campaign = CampaignSubPhase(speeches=[campaign_speech])
        discussion = DiscussionSubPhase(speeches=[discussion_speech])
        day = DayPhase(day_number=1, subphases=[campaign, discussion])
        assert len(day.all_speeches) == 2

    def test_day_phase_str_empty(self):
        """Test DayPhase string representation with no subphases."""
        day = DayPhase(day_number=1)
        assert "(no events)" in str(day)

    def test_day_phase_str_with_subphases(self):
        """Test DayPhase string representation with subphases."""
        speech = Speech(
            actor=0, day=1, micro_phase=MicroPhase.CAMPAIGN, content="Vote me!"
        )
        campaign = CampaignSubPhase(speeches=[speech])
        day = DayPhase(day_number=1, subphases=[campaign])
        output = str(day)
        assert "Day 1" in output
        assert "Campaign:" in output


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
        """Test adding a NightPhase to the log."""
        log = GameEventLog(player_count=12)
        night = NightPhase(night_number=1)
        log.add_phase(night)
        assert len(log.phases) == 1
        assert log.current_night == 1
        assert log.current_day == 0

    def test_game_event_log_add_day_phase(self):
        """Test adding a DayPhase to the log."""
        log = GameEventLog(player_count=12)
        day = DayPhase(day_number=1)
        log.add_phase(day)
        assert len(log.phases) == 1
        assert log.current_day == 1
        assert log.current_night == 0

    def test_game_event_log_add_multiple_phases(self):
        """Test adding multiple phases in order."""
        log = GameEventLog(player_count=12)
        night1 = NightPhase(night_number=1)
        day1 = DayPhase(day_number=1)
        night2 = NightPhase(night_number=2)
        log.add_phase(night1)
        log.add_phase(day1)
        log.add_phase(night2)
        assert len(log.phases) == 3

    def test_game_event_log_duplicate_night_raises(self):
        """Test that adding duplicate Night raises ValueError."""
        log = GameEventLog(player_count=12)
        night1 = NightPhase(night_number=1)
        night1_copy = NightPhase(night_number=1)
        log.add_phase(night1)
        with pytest.raises(ValueError, match="Night 1 already exists"):
            log.add_phase(night1_copy)

    def test_game_event_log_duplicate_day_raises(self):
        """Test that adding duplicate Day raises ValueError."""
        log = GameEventLog(player_count=12)
        day1 = DayPhase(day_number=1)
        day1_copy = DayPhase(day_number=1)
        log.add_phase(day1)
        with pytest.raises(ValueError, match="Day 1 already exists"):
            log.add_phase(day1_copy)

    def test_game_event_log_get_night(self):
        """Test get_night method."""
        log = GameEventLog(player_count=12)
        night1 = NightPhase(night_number=1)
        night2 = NightPhase(night_number=2)
        log.add_phase(night1)
        log.add_phase(night2)

        assert log.get_night(1) == night1
        assert log.get_night(2) == night2
        assert log.get_night(3) is None

    def test_game_event_log_get_day(self):
        """Test get_day method."""
        log = GameEventLog(player_count=12)
        day1 = DayPhase(day_number=1)
        day2 = DayPhase(day_number=2)
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
        day = DayPhase(day_number=1)
        log.add_phase(day)
        assert log.current_night == 0

    def test_game_event_log_current_day_with_only_night(self):
        """Test current_day when only night phases exist."""
        log = GameEventLog(player_count=12)
        night = NightPhase(night_number=1)
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
        resolution_sp = NightResolutionSubPhase(resolution=resolution)
        night1 = NightPhase(night_number=1, subphases=[resolution_sp])
        log.add_phase(night1)

        # Add another night with different deaths
        resolution2 = NightResolution(day=2, deaths=[3])
        resolution_sp2 = NightResolutionSubPhase(resolution=resolution2)
        night2 = NightPhase(night_number=2, subphases=[resolution_sp2])
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
            actor=0, day=1, micro_phase=MicroPhase.CAMPAIGN, content="Speech 1"
        )
        campaign = CampaignSubPhase(speeches=[speech1])
        day1 = DayPhase(day_number=1, subphases=[campaign])
        log.add_phase(day1)

        speeches = log.get_all_speeches()
        assert len(speeches) == 1
        assert speeches[0] == (1, "Speech 1")

    def test_get_all_speeches_multiple_days(self):
        """Test get_all_speeches across multiple days."""
        log = GameEventLog(player_count=12)

        # Day 1
        speech1 = Speech(
            actor=0, day=1, micro_phase=MicroPhase.CAMPAIGN, content="Day 1 speech"
        )
        campaign = CampaignSubPhase(speeches=[speech1])
        day1 = DayPhase(day_number=1, subphases=[campaign])
        log.add_phase(day1)

        # Day 2
        speech2 = Speech(
            actor=3, day=2, micro_phase=MicroPhase.DISCUSSION, content="Day 2 speech"
        )
        discussion = DiscussionSubPhase(speeches=[speech2])
        day2 = DayPhase(day_number=2, subphases=[discussion])
        log.add_phase(day2)

        speeches = log.get_all_speeches()
        assert len(speeches) == 2
        assert speeches[0] == (1, "Day 1 speech")
        assert speeches[1] == (2, "Day 2 speech")

    def test_get_sheriffs_empty(self):
        """Test get_sheriffs when no sheriff elected."""
        log = GameEventLog(player_count=12)
        day = DayPhase(day_number=1)
        log.add_phase(day)
        assert log.get_sheriffs() == {}

    def test_get_sheriffs_with_election(self):
        """Test get_sheriffs with sheriff election."""
        log = GameEventLog(player_count=12)

        election = SheriffElection(day=1, winner=3)
        election_sp = SheriffElectionSubPhase(election=election)
        day1 = DayPhase(day_number=1, subphases=[election_sp])
        log.add_phase(day1)

        sheriffs = log.get_sheriffs()
        assert sheriffs == {1: 3}

    def test_get_sheriffs_multiple_days(self):
        """Test get_sheriffs across multiple days (only Day 1 has sheriff election)."""
        log = GameEventLog(player_count=12)

        # Day 1 election
        election1 = SheriffElection(day=1, winner=3)
        election_sp1 = SheriffElectionSubPhase(election=election1)
        day1 = DayPhase(day_number=1, subphases=[election_sp1])
        log.add_phase(day1)

        # Day 2 (no sheriff election)
        discussion = DiscussionSubPhase()
        day2 = DayPhase(day_number=2, subphases=[discussion])
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
        werewolf_sp = WerewolfActionSubPhase(kill=kill)
        night = NightPhase(night_number=1, subphases=[werewolf_sp])
        log.add_phase(night)

        yaml_str = log.to_yaml()
        assert "NightPhase" in yaml_str or "night" in yaml_str

    def test_save_to_file_and_load_from_file(self):
        """Test round-trip save and load."""
        log = GameEventLog(player_count=12)

        # Set up game start
        game_start = GameStart(player_count=12, roles_secret={0: "Werewolf"})
        log.game_start = game_start

        # Add a night with action
        kill = WerewolfKill(actor=0, day=1, target=5)
        werewolf_sp = WerewolfActionSubPhase(kill=kill)
        night = NightPhase(night_number=1, subphases=[werewolf_sp])
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
        werewolf_sp = WerewolfActionSubPhase(kill=kill)
        night = NightPhase(night_number=1, subphases=[werewolf_sp])
        log.add_phase(night)

        output = str(log)
        assert "Night 1" in output
        assert "kill seat 5" in output

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
        resolution_sp = NightResolutionSubPhase(resolution=resolution)
        night = NightPhase(night_number=1, subphases=[resolution_sp])
        log.add_phase(night)

        # Add a day with speeches
        speech = Speech(actor=0, day=1, micro_phase=MicroPhase.CAMPAIGN, content="Hello")
        campaign = CampaignSubPhase(speeches=[speech])
        day = DayPhase(day_number=1, subphases=[campaign])
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
        werewolf_sp = WerewolfActionSubPhase(kill=werewolf_kill)

        # Witch action
        witch_action = WitchAction(
            actor=2, day=1, action_type=WitchActionType.PASS
        )
        witch_sp = WitchActionSubPhase(action=witch_action)

        # Guard action
        guard_action = GuardAction(actor=1, day=1, target=3)
        guard_sp = GuardActionSubPhase(action=guard_action)

        # Seer action
        seer_action = SeerAction(actor=3, day=1, target=0, result=SeerResult.WEREWOLF)
        seer_sp = SeerActionSubPhase(action=seer_action)

        # Night resolution - player 5 dies
        night_resolution = NightResolution(day=1, deaths=[5])
        resolution_sp = NightResolutionSubPhase(resolution=night_resolution)

        night1 = NightPhase(
            night_number=1,
            subphases=[werewolf_sp, witch_sp, guard_sp, seer_sp, resolution_sp],
        )
        log.add_phase(night1)

        assert log.current_night == 1
        assert log.get_all_deaths() == [5]

    def test_day_1_complete(self):
        """Test building a complete Day 1 scenario."""
        log = GameEventLog(player_count=12)

        # Sheriff campaign speeches
        speech1 = Speech(actor=0, day=1, micro_phase=MicroPhase.CAMPAIGN, content="I should be Sheriff!")
        speech2 = Speech(actor=3, day=1, micro_phase=MicroPhase.CAMPAIGN, content="Vote for me!")
        campaign = CampaignSubPhase(speeches=[speech1, speech2])

        # Opt outs
        opt_out = SheriffOptOut(actor=5, day=1)
        opt_out_sp = OptOutSubPhase(opt_outs=[opt_out])

        # Sheriff election
        election = SheriffElection(day=1, winner=0)
        election_sp = SheriffElectionSubPhase(election=election)

        # Death announcement
        announcement = DeathAnnouncement(day=1, dead_players=[7])
        death_sp = DeathAnnouncementSubPhase(announcement=announcement)

        # Last words
        last_words = Speech(actor=7, day=1, micro_phase=MicroPhase.LAST_WORDS, content="I was the Guard!")
        last_words_sp = LastWordsSubPhase(speeches=[last_words])

        # Discussion
        discussion_speech = Speech(actor=3, day=1, micro_phase=MicroPhase.DISCUSSION, content="Player 0 is suspicious!")
        discussion = DiscussionSubPhase(speeches=[discussion_speech])

        # Voting
        votes = [
            Vote(actor=0, day=1, target=3),
            Vote(actor=1, day=1, target=3),
            Vote(actor=2, day=1, target=3),
            Vote(actor=4, day=1, target=None),  # abstain
        ]
        voting = VotingSubPhase(votes=votes)

        # Victory check
        victory_check = VictoryCheck(phase=Phase.DAY, is_game_over=False)
        victory_sp = VictoryCheckSubPhase(check=victory_check)

        day1 = DayPhase(
            day_number=1,
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
        resolution_sp = NightResolutionSubPhase(resolution=night_resolution)
        night1 = NightPhase(night_number=1, subphases=[resolution_sp])
        log.add_phase(night1)

        # Day 1
        day1 = DayPhase(day_number=1)
        log.add_phase(day1)

        # Night 2 with deaths
        night_resolution2 = NightResolution(day=2, deaths=[7, 8])
        resolution_sp2 = NightResolutionSubPhase(resolution=night_resolution2)
        night2 = NightPhase(night_number=2, subphases=[resolution_sp2])
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
        assert "NightPhase" in yaml_str or "night" in yaml_str
        assert "DayPhase" in yaml_str or "day" in yaml_str
        assert "GameOver" in yaml_str or "GAME_OVER" in yaml_str
        assert "WEREWOLF" in yaml_str
        assert "deaths" in yaml_str.lower()
