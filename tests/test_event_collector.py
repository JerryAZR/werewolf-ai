"""Tests for the EventCollector component."""

import pytest

from werewolf.engine.event_collector import EventCollector
from werewolf.events import (
    GameEvent,
    WerewolfKill,
    WitchAction,
    GuardAction,
    SeerAction,
    SeerResult,
    NightOutcome,
    Speech,
    SheriffOutcome,
    Vote,
    DeathAnnouncement,
    GameStart,
    GameOver,
    SubPhaseLog,
    SubPhase,
    PhaseLog,
    Phase,
    GameEventLog,
    WitchActionType,
    DeathCause,
    VictoryCondition,
)


class TestEventCollectorInit:
    """Tests for EventCollector initialization."""

    def test_default_init(self):
        """Test EventCollector with default day=0."""
        collector = EventCollector()
        assert collector.day == 0

    def test_custom_day_init(self):
        """Test EventCollector with custom day."""
        collector = EventCollector(day=3)
        assert collector.day == 3

    def test_empty_event_log(self):
        """Test that collector starts with empty event log."""
        collector = EventCollector()
        event_log = collector.get_event_log()
        assert isinstance(event_log, GameEventLog)
        assert len(event_log.phases) == 0
        assert event_log.game_start is None


class TestEventCollectorCreatePhase:
    """Tests for create_phase_log method."""

    def test_create_night_phase(self):
        """Test creating a NIGHT phase."""
        collector = EventCollector(day=1)
        collector.create_phase_log(Phase.NIGHT)

        event_log = collector.get_event_log()
        assert len(event_log.phases) == 1
        assert event_log.phases[0].kind == Phase.NIGHT
        assert event_log.phases[0].number == 1

    def test_create_day_phase(self):
        """Test creating a DAY phase."""
        collector = EventCollector(day=1)
        collector.create_phase_log(Phase.DAY)

        event_log = collector.get_event_log()
        assert len(event_log.phases) == 1
        assert event_log.phases[0].kind == Phase.DAY
        assert event_log.phases[0].number == 1

    def test_create_multiple_phases(self):
        """Test creating multiple phases in sequence."""
        collector = EventCollector(day=1)
        collector.create_phase_log(Phase.NIGHT)
        collector.create_phase_log(Phase.DAY)
        collector.create_phase_log(Phase.NIGHT)
        collector.create_phase_log(Phase.DAY)

        event_log = collector.get_event_log()
        assert len(event_log.phases) == 4
        assert event_log.phases[0].kind == Phase.NIGHT
        assert event_log.phases[1].kind == Phase.DAY
        assert event_log.phases[2].kind == Phase.NIGHT
        assert event_log.phases[3].kind == Phase.DAY

    def test_phase_transition_night_to_day(self):
        """Test transitioning from NIGHT to DAY."""
        collector = EventCollector(day=1)
        collector.create_phase_log(Phase.NIGHT)

        # Add an event to night
        kill = WerewolfKill(actor=0, day=1, target=5)
        collector.add_event(kill)

        # Transition to day
        collector.create_phase_log(Phase.DAY)

        event_log = collector.get_event_log()
        assert len(event_log.phases) == 2
        assert event_log.phases[0].kind == Phase.NIGHT
        assert event_log.phases[1].kind == Phase.DAY

        # Night should have the kill event
        night = event_log.get_night(1)
        assert night is not None
        assert len(night.subphases) == 1


class TestEventCollectorAddEvent:
    """Tests for add_event method."""

    def test_add_event_requires_phase(self):
        """Test that add_event raises if no phase created."""
        collector = EventCollector()
        kill = WerewolfKill(actor=0, day=1, target=5)

        with pytest.raises(RuntimeError, match="No phase has been created"):
            collector.add_event(kill)

    def test_add_werewolf_kill(self):
        """Test adding a werewolf kill event."""
        collector = EventCollector(day=1)
        collector.create_phase_log(Phase.NIGHT)

        kill = WerewolfKill(actor=0, day=1, target=5)
        collector.add_event(kill)

        events = collector.get_events()
        assert len(events) == 1
        assert events[0] == kill

    def test_add_multiple_events_same_subphase(self):
        """Test adding multiple events to same subphase."""
        collector = EventCollector(day=1)
        collector.create_phase_log(Phase.NIGHT)

        # Add multiple votes in voting subphase
        collector.create_phase_log(Phase.DAY)

        vote1 = Vote(actor=0, day=1, target=3)
        vote2 = Vote(actor=1, day=1, target=3)
        vote3 = Vote(actor=2, day=1, target=None)  # abstain

        collector.add_event(vote1)
        collector.add_event(vote2)
        collector.add_event(vote3)

        events = collector.get_events()
        assert len(events) == 3

    def test_add_event_sets_day_if_zero(self):
        """Test that add_event sets day from collector if event day is 0."""
        collector = EventCollector(day=2)
        collector.create_phase_log(Phase.NIGHT)

        kill = WerewolfKill(actor=0, day=0, target=5)  # day=0
        collector.add_event(kill)

        events = collector.get_events()
        assert events[0].day == 2

    def test_add_event_preserves_existing_day(self):
        """Test that add_event preserves event's existing day."""
        collector = EventCollector(day=2)
        collector.create_phase_log(Phase.NIGHT)

        kill = WerewolfKill(actor=0, day=1, target=5)  # day=1
        collector.add_event(kill)

        events = collector.get_events()
        assert events[0].day == 1


class TestEventCollectorAddSubphaseLog:
    """Tests for add_subphase_log method."""

    def test_add_subphase_log_requires_phase(self):
        """Test that add_subphase_log raises if no phase created."""
        collector = EventCollector()
        subphase_log = SubPhaseLog(micro_phase=SubPhase.WEREWOLF_ACTION)

        with pytest.raises(RuntimeError, match="No phase has been created"):
            collector.add_subphase_log(subphase_log)

    def test_add_subphase_log(self):
        """Test adding a complete subphase log."""
        collector = EventCollector(day=1)
        collector.create_phase_log(Phase.NIGHT)

        kill = WerewolfKill(actor=0, day=1, target=5)
        witch_action = WitchAction(actor=2, day=1, action_type=WitchActionType.PASS)

        subphase_log = SubPhaseLog(
            micro_phase=SubPhase.WEREWOLF_ACTION,
            events=[kill, witch_action]
        )
        collector.add_subphase_log(subphase_log)

        events = collector.get_events()
        assert len(events) == 2
        assert events[0] == kill
        assert events[1] == witch_action

    def test_add_subphase_log_updates_day_for_events(self):
        """Test that add_subphase_log updates day for events with day=0."""
        collector = EventCollector(day=3)
        collector.create_phase_log(Phase.NIGHT)

        kill = WerewolfKill(actor=0, day=0, target=5)
        subphase_log = SubPhaseLog(micro_phase=SubPhase.WEREWOLF_ACTION, events=[kill])
        collector.add_subphase_log(subphase_log)

        events = collector.get_events()
        assert events[0].day == 3


class TestEventCollectorGetEventLog:
    """Tests for get_event_log method."""

    def test_get_empty_event_log(self):
        """Test get_event_log with no events."""
        collector = EventCollector()
        collector.create_phase_log(Phase.NIGHT)

        event_log = collector.get_event_log()
        assert isinstance(event_log, GameEventLog)
        assert len(event_log.phases) == 1
        assert event_log.phases[0].kind == Phase.NIGHT

    def test_get_event_log_with_night_events(self):
        """Test get_event_log with complete night scenario."""
        collector = EventCollector(day=1)
        collector.create_phase_log(Phase.NIGHT)

        # Werewolf kill
        kill = WerewolfKill(actor=0, day=1, target=5)
        collector.add_event(kill)

        # Witch action
        witch = WitchAction(actor=2, day=1, action_type=WitchActionType.PASS)
        collector.add_event(witch)

        # Night resolution
        resolution = NightOutcome(day=1, deaths={5: DeathCause.WEREWOLF_KILL})
        collector.add_event(resolution)

        event_log = collector.get_event_log()
        night = event_log.get_night(1)
        assert night is not None
        assert len(night.subphases) >= 1  # May have 3 subphases

    def test_get_event_log_with_day_events(self):
        """Test get_event_log with complete day scenario."""
        collector = EventCollector(day=1)
        collector.create_phase_log(Phase.DAY)

        # Death announcement
        announcement = DeathAnnouncement(day=1, dead_players=[5])
        collector.add_event(announcement)

        # Discussion speeches
        speech1 = Speech(actor=0, day=1, micro_phase=SubPhase.DISCUSSION, content="Player 0 is suspicious!")
        speech2 = Speech(actor=1, day=1, micro_phase=SubPhase.DISCUSSION, content="Player 3 is lying!")
        collector.add_event(speech1)
        collector.add_event(speech2)

        event_log = collector.get_event_log()
        day = event_log.get_day(1)
        assert day is not None

        speeches = event_log.get_all_speeches()
        assert len(speeches) == 2


class TestEventCollectorGetEvents:
    """Tests for get_events method."""

    def test_get_empty_events(self):
        """Test get_events with no events."""
        collector = EventCollector()
        collector.create_phase_log(Phase.NIGHT)

        events = collector.get_events()
        assert events == []

    def test_get_single_event(self):
        """Test get_events with single event."""
        collector = EventCollector(day=1)
        collector.create_phase_log(Phase.NIGHT)

        kill = WerewolfKill(actor=0, day=1, target=5)
        collector.add_event(kill)

        events = collector.get_events()
        assert len(events) == 1
        assert events[0] == kill

    def test_get_events_preserves_order(self):
        """Test that get_events returns events in order."""
        collector = EventCollector(day=1)
        collector.create_phase_log(Phase.DAY)

        vote1 = Vote(actor=0, day=1, target=1)
        vote2 = Vote(actor=1, day=1, target=2)
        vote3 = Vote(actor=2, day=1, target=1)

        collector.add_event(vote1)
        collector.add_event(vote2)
        collector.add_event(vote3)

        events = collector.get_events()
        assert len(events) == 3
        assert events[0].actor == 0
        assert events[1].actor == 1
        assert events[2].actor == 2


class TestEventCollectorSetMethods:
    """Tests for set_player_count, set_game_start, set_game_over."""

    def test_set_player_count(self):
        """Test setting player count."""
        collector = EventCollector()
        collector.set_player_count(12)

        event_log = collector.get_event_log()
        assert event_log.player_count == 12

    def test_set_game_start(self):
        """Test setting game start event."""
        collector = EventCollector()
        game_start = GameStart(player_count=12)
        collector.set_game_start(game_start)

        event_log = collector.get_event_log()
        assert event_log.game_start == game_start

    def test_set_game_over(self):
        """Test setting game over event."""
        collector = EventCollector()
        game_over = GameOver(
            winner="WEREWOLF",
            condition=VictoryCondition.ALL_VILLAGERS_KILLED,
            final_turn_count=5,
        )
        collector.set_game_over(game_over)

        event_log = collector.get_event_log()
        assert event_log.game_over == game_over


class TestEventCollectorIntegration:
    """Integration tests simulating complete scenarios."""

    def test_complete_night_1(self):
        """Test collecting all events from Night 1."""
        collector = EventCollector(day=1)
        collector.set_player_count(12)

        # Game start
        game_start = GameStart(player_count=12)
        collector.set_game_start(game_start)

        # Start night
        collector.create_phase_log(Phase.NIGHT)

        # Werewolf action
        kill = WerewolfKill(actor=0, day=1, target=5)
        collector.add_event(kill)

        # Witch action
        witch = WitchAction(actor=2, day=1, action_type=WitchActionType.PASS)
        collector.add_event(witch)

        # Guard action
        guard = GuardAction(actor=1, day=1, target=3)
        collector.add_event(guard)

        # Seer action
        seer = SeerAction(actor=3, day=1, target=0, result=SeerResult.WEREWOLF)
        collector.add_event(seer)

        # Night resolution
        resolution = NightOutcome(day=1, deaths={5: DeathCause.WEREWOLF_KILL})
        collector.add_event(resolution)

        event_log = collector.get_event_log()

        # Verify
        assert event_log.player_count == 12
        assert event_log.game_start is not None
        assert event_log.current_night == 1

        night = event_log.get_night(1)
        assert night is not None

        deaths = event_log.get_all_deaths()
        assert len(deaths) == 1
        assert 5 in deaths

    def test_complete_day_1(self):
        """Test collecting all events from Day 1."""
        collector = EventCollector(day=1)
        collector.create_phase_log(Phase.DAY)

        # Death announcement
        announcement = DeathAnnouncement(day=1, dead_players=[5])
        collector.add_event(announcement)

        # Discussion
        speech1 = Speech(actor=0, day=1, micro_phase=SubPhase.DISCUSSION, content="I think player 1 is werewolf!")
        speech2 = Speech(actor=1, day=1, micro_phase=SubPhase.DISCUSSION, content="No, player 0 is suspicious!")
        collector.add_event(speech1)
        collector.add_event(speech2)

        # Voting
        vote1 = Vote(actor=0, day=1, target=1)
        vote2 = Vote(actor=2, day=1, target=1)
        vote3 = Vote(actor=3, day=1, target=None)  # abstain
        collector.add_event(vote1)
        collector.add_event(vote2)
        collector.add_event(vote3)

        event_log = collector.get_event_log()

        # Verify
        assert event_log.current_day == 1

        speeches = event_log.get_all_speeches()
        assert len(speeches) == 2

        events = collector.get_events()
        assert len(events) == 6  # announcement + 2 speeches + 3 votes

    def test_multi_night_day_cycle(self):
        """Test collecting events across multiple nights and days."""
        collector = EventCollector()
        collector.set_player_count(12)

        game_start = GameStart(player_count=12)
        collector.set_game_start(game_start)

        # Night 1
        collector.day = 1
        collector.create_phase_log(Phase.NIGHT)
        collector.add_event(WerewolfKill(actor=0, day=1, target=5))
        collector.add_event(NightOutcome(day=1, deaths={5: DeathCause.WEREWOLF_KILL}))

        # Day 1
        collector.create_phase_log(Phase.DAY)
        collector.add_event(DeathAnnouncement(day=1, dead_players=[5]))

        # Night 2
        collector.day = 2
        collector.create_phase_log(Phase.NIGHT)
        collector.add_event(WerewolfKill(actor=0, day=2, target=7))
        collector.add_event(NightOutcome(day=2, deaths={7: DeathCause.WEREWOLF_KILL}))

        # Day 2
        collector.create_phase_log(Phase.DAY)
        collector.add_event(DeathAnnouncement(day=2, dead_players=[7]))

        event_log = collector.get_event_log()

        assert event_log.current_night == 2
        assert event_log.current_day == 2

        deaths = event_log.get_all_deaths()
        assert len(deaths) == 2
        assert 5 in deaths
        assert 7 in deaths

    def test_add_subphase_log_integration(self):
        """Test using add_subphase_log for batch adding."""
        collector = EventCollector(day=1)
        collector.create_phase_log(Phase.DAY)

        # Create a subphase log with multiple speeches
        speech1 = Speech(actor=0, day=1, micro_phase=SubPhase.DISCUSSION, content="Speech 1")
        speech2 = Speech(actor=1, day=1, micro_phase=SubPhase.DISCUSSION, content="Speech 2")
        discussion_log = SubPhaseLog(
            micro_phase=SubPhase.DISCUSSION,
            events=[speech1, speech2]
        )

        collector.add_subphase_log(discussion_log)

        events = collector.get_events()
        assert len(events) == 2

        event_log = collector.get_event_log()
        speeches = event_log.get_all_speeches()
        assert len(speeches) == 2
