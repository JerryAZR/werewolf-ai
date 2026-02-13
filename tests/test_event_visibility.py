"""Tests for event_visibility module.

Tests the public/private event filtering functionality.
"""

import pytest
from typing import Optional

from werewolf.events.game_events import (
    GameEvent,
    Speech,
    Phase,
    SubPhase,
    DeathEvent,
    DeathCause,
    Vote,
    WerewolfKill,
    WitchAction,
    WitchActionType,
    SeerAction,
    SeerResult,
    GuardAction,
    SheriffOutcome,
    SheriffNomination,
    SheriffOptOut,
    DeathAnnouncement,
)
from werewolf.events.event_visibility import (
    PublicEvents,
    DefaultEventSummarizer,
    get_public_events,
    format_public_events,
)


class TestPublicEvents:
    """Tests for PublicEvents class."""

    def test_empty_public_events(self):
        """Test creating empty PublicEvents."""
        events = PublicEvents()
        assert events.deaths_today == []
        assert events.previous_speeches == []
        assert events.sheriff_outcome is None
        assert events.sheriff_nominations == []
        assert events.sheriff_opt_outs == []
        assert events.death_announcements == []

    def test_public_events_with_data(self):
        """Test creating PublicEvents with data."""
        death = DeathEvent(
            actor=5,
            cause=DeathCause.WEREWOLF_KILL,
            phase=Phase.DAY,
            day=1,
        )
        speech = Speech(
            actor=2,
            content="Test speech",
            phase=Phase.DAY,
            micro_phase=SubPhase.DISCUSSION,
            day=1,
        )

        events = PublicEvents(
            deaths_today=[death],
            previous_speeches=[speech],
            sheriff_outcome=None,
        )

        assert len(events.deaths_today) == 1
        assert events.deaths_today[0].actor == 5
        assert len(events.previous_speeches) == 1
        assert events.previous_speeches[0].actor == 2


class TestDefaultEventSummarizer:
    """Tests for DefaultEventSummarizer."""

    def test_no_events(self):
        """Test summarizing with no events."""
        summarizer = DefaultEventSummarizer()
        result = summarizer.summarize([], 1, 0)

        assert result.deaths_today == []
        assert result.previous_speeches == []
        assert result.sheriff_outcome is None

    def test_death_events_are_public(self):
        """Test that DeathEvent is included in public events."""
        events = [
            DeathEvent(
                actor=5,
                cause=DeathCause.WEREWOLF_KILL,
                last_words="Goodbye",
                phase=Phase.DAY,
                day=1,
            ),
        ]

        summarizer = DefaultEventSummarizer()
        result = summarizer.summarize(events, 1, 0)

        assert len(result.deaths_today) == 1
        assert result.deaths_today[0].actor == 5

    def test_speech_is_public_but_not_own(self):
        """Test that speeches are public but own speech is excluded."""
        events = [
            Speech(
                actor=2,
                content="First speech",
                phase=Phase.DAY,
                micro_phase=SubPhase.DISCUSSION,
                day=1,
            ),
            Speech(
                actor=0,
                content="Second speech",
                phase=Phase.DAY,
                micro_phase=SubPhase.DISCUSSION,
                day=1,
            ),
        ]

        summarizer = DefaultEventSummarizer()

        # For seat 0, only seat 2's speech should be visible
        result = summarizer.summarize(events, 1, 0)
        assert len(result.previous_speeches) == 1
        assert result.previous_speeches[0].actor == 2

        # For seat 2, only seat 0's speech should be visible
        result = summarizer.summarize(events, 1, 2)
        assert len(result.previous_speeches) == 1
        assert result.previous_speeches[0].actor == 0

        # For seat 5, both speeches should be visible
        result = summarizer.summarize(events, 1, 5)
        assert len(result.previous_speeches) == 2

    def test_vote_is_hidden(self):
        """Test that Vote events are NOT included."""
        events = [
            Vote(
                actor=2,
                target=5,
                phase=Phase.DAY,
                micro_phase=SubPhase.VOTING,
                day=1,
            ),
        ]

        summarizer = DefaultEventSummarizer()
        result = summarizer.summarize(events, 1, 0)

        # Votes should not be in any public category
        assert result.deaths_today == []
        assert result.previous_speeches == []

    def test_werewolf_kill_is_hidden(self):
        """Test that WerewolfKill is NOT included."""
        events = [
            WerewolfKill(
                actor=0,
                target=5,
                phase=Phase.NIGHT,
                micro_phase=SubPhase.WEREWOLF_ACTION,
                day=1,
            ),
        ]

        summarizer = DefaultEventSummarizer()
        result = summarizer.summarize(events, 1, 0)

        assert result.deaths_today == []

    def test_witch_action_is_hidden(self):
        """Test that WitchAction is NOT included."""
        events = [
            WitchAction(
                actor=5,
                action_type=WitchActionType.POISON,
                target=3,
                phase=Phase.NIGHT,
                day=1,
            ),
        ]

        summarizer = DefaultEventSummarizer()
        result = summarizer.summarize(events, 1, 0)

        assert result.deaths_today == []

    def test_seer_action_is_hidden(self):
        """Test that SeerAction is NOT included."""
        events = [
            SeerAction(
                actor=4,
                target=2,
                result=SeerResult.WEREWOLF,
                phase=Phase.NIGHT,
                day=1,
            ),
        ]

        summarizer = DefaultEventSummarizer()
        result = summarizer.summarize(events, 1, 0)

        # Seer checks should not appear in public events
        assert result.deaths_today == []

    def test_guard_action_is_hidden(self):
        """Test that GuardAction is NOT included."""
        events = [
            GuardAction(
                actor=6,
                target=4,
                phase=Phase.NIGHT,
                day=1,
            ),
        ]

        summarizer = DefaultEventSummarizer()
        result = summarizer.summarize(events, 1, 0)

        assert result.deaths_today == []

    def test_sheriff_outcome_is_public(self):
        """Test that SheriffOutcome is included."""
        events = [
            SheriffOutcome(
                candidates=[2, 4, 6],
                votes={2: 1.5, 4: 1.0, 6: 1.0},
                winner=2,
                phase=Phase.DAY,
                day=1,
            ),
        ]

        summarizer = DefaultEventSummarizer()
        result = summarizer.summarize(events, 1, 0)

        assert result.sheriff_outcome is not None
        assert result.sheriff_outcome.winner == 2

    def test_sheriff_nomination_is_public(self):
        """Test that SheriffNomination is included."""
        events = [
            SheriffNomination(
                actor=2,
                running=True,
                phase=Phase.DAY,
                day=1,
            ),
        ]

        summarizer = DefaultEventSummarizer()
        result = summarizer.summarize(events, 1, 0)

        assert len(result.sheriff_nominations) == 1
        assert result.sheriff_nominations[0].actor == 2

    def test_sheriff_opt_out_is_public(self):
        """Test that SheriffOptOut is included."""
        events = [
            SheriffOptOut(
                actor=4,
                phase=Phase.DAY,
                day=1,
            ),
        ]

        summarizer = DefaultEventSummarizer()
        result = summarizer.summarize(events, 1, 0)

        assert len(result.sheriff_opt_outs) == 1
        assert result.sheriff_opt_outs[0].actor == 4

    def test_death_announcement_is_public(self):
        """Test that DeathAnnouncement is included."""
        events = [
            DeathAnnouncement(
                dead_players=[3, 7],
                death_count=2,
                phase=Phase.DAY,
                day=1,
            ),
        ]

        summarizer = DefaultEventSummarizer()
        result = summarizer.summarize(events, 1, 0)

        assert len(result.death_announcements) == 1
        assert result.death_announcements[0].dead_players == [3, 7]

    def test_only_current_day_events(self):
        """Test that only current day events are included."""
        events = [
            DeathEvent(
                actor=5,
                cause=DeathCause.WEREWOLF_KILL,
                phase=Phase.DAY,
                day=1,  # Previous day
            ),
            DeathEvent(
                actor=7,
                cause=DeathCause.BANISHMENT,
                phase=Phase.DAY,
                day=2,  # Current day
            ),
        ]

        summarizer = DefaultEventSummarizer()
        result = summarizer.summarize(events, 2, 0)

        assert len(result.deaths_today) == 1
        assert result.deaths_today[0].actor == 7

    def test_mixed_events_filtering(self):
        """Test filtering a mix of public and private events."""
        events = [
            DeathEvent(
                actor=5,
                cause=DeathCause.WEREWOLF_KILL,
                phase=Phase.DAY,
                day=1,
            ),
            Vote(
                actor=2,
                target=5,
                phase=Phase.DAY,
                micro_phase=SubPhase.VOTING,
                day=1,
            ),
            Speech(
                actor=3,
                content="I think seat 2 is suspicious",
                phase=Phase.DAY,
                micro_phase=SubPhase.DISCUSSION,
                day=1,
            ),
            WerewolfKill(
                actor=0,
                target=5,
                phase=Phase.NIGHT,
                day=1,
            ),
        ]

        summarizer = DefaultEventSummarizer()
        result = summarizer.summarize(events, 1, 0)

        # Only death and speech should be public
        assert len(result.deaths_today) == 1
        assert result.deaths_today[0].actor == 5
        assert len(result.previous_speeches) == 1
        assert result.previous_speeches[0].actor == 3


class TestGetPublicEvents:
    """Tests for get_public_events convenience function."""

    def test_default_summarizer(self):
        """Test using default summarizer."""
        events = [
            DeathEvent(
                actor=5,
                cause=DeathCause.WEREWOLF_KILL,
                phase=Phase.DAY,
                day=1,
            ),
        ]

        result = get_public_events(events, 1, 0)
        assert len(result.deaths_today) == 1

    def test_custom_summarizer(self):
        """Test using custom summarizer."""
        class CustomSummarizer:
            def summarize(self, events, current_day, your_seat):
                return PublicEvents(deaths_today=[])

        events = [
            DeathEvent(
                actor=5,
                cause=DeathCause.WEREWOLF_KILL,
                phase=Phase.DAY,
                day=1,
            ),
        ]

        result = get_public_events(events, 1, 0, summarizer=CustomSummarizer())
        assert result.deaths_today == []


class TestFormatPublicEvents:
    """Tests for format_public_events function."""

    def test_empty_events(self):
        """Test formatting empty public events."""
        result = format_public_events(
            PublicEvents(),
            {0, 1, 2},
            {3, 4, 5},
            0,
        )
        assert result == ""

    def test_format_death_with_last_words(self):
        """Test formatting death with last words."""
        death = DeathEvent(
            actor=5,
            cause=DeathCause.WEREWOLF_KILL,
            last_words="I trust seat 2",
            phase=Phase.DAY,
            day=1,
        )
        public_events = PublicEvents(deaths_today=[death])

        result = format_public_events(
            public_events,
            {0, 1, 2, 5},
            {3, 4, 6},
            0,
        )

        assert "DEATHS THIS MORNING" in result
        assert "Seat 5" in result
        # Cause should be hidden per game rules
        assert "WEREWOLF_KILL" not in result
        assert "I trust seat 2" in result

    def test_format_death_without_last_words(self):
        """Test formatting death without last words."""
        death = DeathEvent(
            actor=5,
            cause=DeathCause.BANISHMENT,
            phase=Phase.DAY,
            day=1,
        )
        public_events = PublicEvents(deaths_today=[death])

        result = format_public_events(
            public_events,
            {0, 1, 2},
            {3, 4, 5},
            0,
        )

        assert "Seat 5" in result
        # Cause should be hidden per game rules
        assert "BANISHMENT" not in result
        assert "last_words" not in result.lower()

    def test_format_previous_speeches(self):
        """Test formatting previous speeches."""
        speech = Speech(
            actor=2,
            content="I believe seat 5 is a werewolf based on the voting patterns.",
            phase=Phase.DAY,
            micro_phase=SubPhase.DISCUSSION,
            day=1,
        )
        public_events = PublicEvents(previous_speeches=[speech])

        result = format_public_events(
            public_events,
            {0, 1, 2},
            {3, 4, 5},
            0,
        )

        assert "PREVIOUS SPEECHES" in result
        assert "Seat 2" in result
        assert "werewolf" in result.lower()

    def test_format_sheriff_outcome(self):
        """Test formatting sheriff outcome."""
        outcome = SheriffOutcome(
            candidates=[2, 4, 6],
            votes={2: 1.5, 4: 1.0, 6: 1.0},
            winner=2,
            phase=Phase.DAY,
            day=1,
        )
        public_events = PublicEvents(sheriff_outcome=outcome)

        result = format_public_events(
            public_events,
            {0, 1, 2},
            {3, 4, 5},
            0,
        )

        assert "SHERIFF" in result
        assert "Seat 2" in result

    def test_format_full_public_events(self):
        """Test formatting complete public events."""
        death = DeathEvent(
            actor=5,
            cause=DeathCause.WEREWOLF_KILL,
            last_words="Goodbye",
            phase=Phase.DAY,
            day=1,
        )
        speech = Speech(
            actor=3,
            content="Seat 2 seems suspicious",
            phase=Phase.DAY,
            micro_phase=SubPhase.DISCUSSION,
            day=1,
        )
        outcome = SheriffOutcome(
            candidates=[2, 4, 6],
            votes={2: 1.5, 4: 1.0, 6: 1.0},
            winner=2,
            phase=Phase.DAY,
            day=1,
        )

        public_events = PublicEvents(
            deaths_today=[death],
            previous_speeches=[speech],
            sheriff_outcome=outcome,
        )

        result = format_public_events(
            public_events,
            {0, 1, 2, 3},
            {4, 5, 6},
            0,
        )

        assert "DEATHS THIS MORNING" in result
        assert "PREVIOUS SPEECHES" in result
        assert "SHERIFF" in result

    def test_speech_truncation(self):
        """Test that long speeches are truncated."""
        long_speech = "a" * 200
        speech = Speech(
            actor=2,
            content=long_speech,
            phase=Phase.DAY,
            micro_phase=SubPhase.DISCUSSION,
            day=1,
        )
        public_events = PublicEvents(previous_speeches=[speech])

        result = format_public_events(
            public_events,
            {0, 1, 2},
            {3, 4, 5},
            0,
        )

        # Should contain "..." indicating truncation
        assert "..." in result


class TestEventVisibilityIntegration:
    """Integration tests for event visibility with handlers."""

    def test_seer_sees_only_own_checks(self):
        """Test that seer only sees their own check results in private info."""
        events = [
            SeerAction(
                actor=4,  # Seer
                target=2,
                result=SeerResult.WEREWOLF,
                phase=Phase.NIGHT,
                day=1,
            ),
            SeerAction(
                actor=7,  # Different seer (hypothetical)
                target=3,
                result=SeerResult.GOOD,
                phase=Phase.NIGHT,
                day=1,
            ),
        ]

        summarizer = DefaultEventSummarizer()

        # Seer at seat 4 should NOT see any seer actions in public events
        result = summarizer.summarize(events, 1, 4)
        assert result.deaths_today == []
        assert result.previous_speeches == []

    def test_werewolf_does_not_see_werewolf_kill_in_public(self):
        """Test that werewolf kill is hidden even from werewolves."""
        events = [
            WerewolfKill(
                actor=0,  # Werewolf
                target=5,
                phase=Phase.NIGHT,
                day=1,
            ),
        ]

        summarizer = DefaultEventSummarizer()

        # Even for seat 0 (werewolf), the kill should not be in public events
        result = summarizer.summarize(events, 1, 0)
        assert result.deaths_today == []

    def test_private_info_not_in_public_formatting(self):
        """Test that private info like seer checks don't appear in format_public_events."""
        events = [
            SeerAction(
                actor=4,
                target=2,
                result=SeerResult.WEREWOLF,
                phase=Phase.NIGHT,
                day=1,
            ),
            DeathEvent(
                actor=2,
                cause=DeathCause.WEREWOLF_KILL,
                phase=Phase.DAY,
                day=1,
            ),
        ]

        # The death is public, but the seer check is private
        public_events = get_public_events(events, 1, 0)

        assert len(public_events.deaths_today) == 1  # Death is public
        # Seer checks should not be in any public category

    def test_discussion_speeches_accumulate(self):
        """Test that discussion speeches from previous speakers are visible."""
        events = [
            Speech(
                actor=0,
                content="First speech",
                phase=Phase.DAY,
                micro_phase=SubPhase.DISCUSSION,
                day=1,
            ),
            Speech(
                actor=1,
                content="Second speech",
                phase=Phase.DAY,
                micro_phase=SubPhase.DISCUSSION,
                day=1,
            ),
        ]

        summarizer = DefaultEventSummarizer()

        # For seat 2, both previous speeches should be visible
        result = summarizer.summarize(events, 1, 2)
        assert len(result.previous_speeches) == 2
