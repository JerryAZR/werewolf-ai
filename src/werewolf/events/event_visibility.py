"""Event visibility filtering for user prompts.

This module provides functions to filter events based on visibility rules:

- Public events: visible to all players during day phases
- Private events: only visible to the acting player

The visibility functions are designed to be swappable with an LLM-based
summarizer for more sophisticated context management.
"""

from typing import Protocol, TypeVar
from typing import TYPE_CHECKING

from werewolf.events.game_events import (
    GameEvent,
    DeathEvent,
    Speech,
    DeathAnnouncement,
    SheriffOutcome,
    SheriffNomination,
    SheriffOptOut,
)

if TYPE_CHECKING:
    pass


# ============================================================================
# Event Types for Filtered Output
# ============================================================================


class PublicEvents:
    """Container for public events visible to all players.

    Attributes:
        deaths_today: Death events from today's death resolution
        previous_speeches: Previous speeches in the current discussion
        sheriff_outcome: Sheriff election result (if any)
        sheriff_nominations: Sheriff nomination events
        sheriff_opt_outs: Sheriff opt-out events
        death_announcements: Death announcements from night resolution
    """

    deaths_today: list["DeathEvent"]
    previous_speeches: list["Speech"]
    sheriff_outcome: "SheriffOutcome | None"
    sheriff_nominations: list["SheriffNomination"]
    sheriff_opt_outs: list["SheriffOptOut"]
    death_announcements: list["DeathAnnouncement"]

    def __init__(
        self,
        deaths_today: list["DeathEvent"] | None = None,
        previous_speeches: list["Speech"] | None = None,
        sheriff_outcome: "SheriffOutcome | None" = None,
        sheriff_nominations: list["SheriffNomination"] | None = None,
        sheriff_opt_outs: list["SheriffOptOut"] | None = None,
        death_announcements: list["DeathAnnouncement"] | None = None,
    ):
        self.deaths_today = deaths_today or []
        self.previous_speeches = previous_speeches or []
        self.sheriff_outcome = sheriff_outcome
        self.sheriff_nominations = sheriff_nominations or []
        self.sheriff_opt_outs = sheriff_opt_outs or []
        self.death_announcements = death_announcements or []


# ============================================================================
# Visibility Filter Protocol (for pluggable summarization)
# ============================================================================


T = TypeVar("T", bound=PublicEvents)


class EventSummarizer(Protocol[T]):
    """Protocol for pluggable event summarizers.

    Implementations can use LLM-based summarization instead of raw events.
    This allows for more sophisticated context management where the LLM
    can synthesize multiple events into coherent summaries.
    """

    def summarize(self, events: list["GameEvent"], current_day: int, your_seat: int) -> T:
        """Summarize events for a player.

        Args:
            events: All events in the game so far
            current_day: The current day number
            your_seat: The player's seat number

        Returns:
            Filtered/summarized public events
        """
        ...


# ============================================================================
# Default Visibility Filter (rule-based)
# ============================================================================


class DefaultEventSummarizer:
    """Default rule-based event visibility filter.

    Filters events based on Werewolf game visibility rules.

    Public events (visible to all):
    - DeathEvent: deaths with last words
    - Speech: previous speeches (not own)
    - DeathAnnouncement: who died during night
    - SheriffOutcome: sheriff election winner
    - SheriffNomination: who ran for sheriff
    - SheriffOptOut: who dropped out

    Private events (NOT visible):
    - Vote: individual votes (secret ballot)
    - WerewolfKill: werewolf's night kill target
    - WitchAction: witch's actions
    - SeerAction: seer's checks
    - GuardAction: guard's protection
    - NightOutcome: detailed night resolution
    - Banishment: banishment results
    """

    def summarize(
        self,
        events: list["GameEvent"],
        current_day: int,
        your_seat: int,
    ) -> PublicEvents:
        """Filter events to only public events.

        Args:
            events: All events in the game so far
            current_day: The current day number
            your_seat: The player's seat number (used to exclude own speech)

        Returns:
            PublicEvents containing only visible events
        """
        result = PublicEvents()

        for event in events:
            # Only consider events from the current day for day phases
            # Also include previous days' events that are inherently public
            # (like death announcements from previous days)

            # Death events are public - include if from current day
            if hasattr(event, "cause") and hasattr(event, "actor"):
                if event.day == current_day:
                    result.deaths_today.append(event)
                continue

            # Previous speeches are public (but not own speech)
            if isinstance(event, Speech):
                # Only include speeches from current discussion phase
                if event.day == current_day and event.actor != your_seat:
                    result.previous_speeches.append(event)
                continue

            # Sheriff-related events are public
            if isinstance(event, SheriffOutcome):
                result.sheriff_outcome = event
            elif isinstance(event, SheriffNomination):
                result.sheriff_nominations.append(event)
            elif isinstance(event, SheriffOptOut):
                result.sheriff_opt_outs.append(event)
            elif isinstance(event, DeathAnnouncement):
                result.death_announcements.append(event)

        return result


# ============================================================================
# Convenience Functions
# ============================================================================


def get_public_events(
    events: list["GameEvent"],
    current_day: int,
    your_seat: int,
    summarizer: EventSummarizer[PublicEvents] | None = None,
) -> PublicEvents:
    """Get public events for a player.

    This is the main entry point for handlers to get filtered events.

    Args:
        events: All game events so far
        current_day: The current day number
        your_seat: The player's seat number
        summarizer: Optional custom summarizer (defaults to DefaultEventSummarizer)

    Returns:
        PublicEvents containing only visible events
    """
    if summarizer is None:
        summarizer = DefaultEventSummarizer()
    return summarizer.summarize(events, current_day, your_seat)


def format_public_events(
    public_events: PublicEvents,
    living_players: set[int],
    dead_players: set[int],
    your_seat: int,
) -> str:
    """Format public events into a readable string for user prompts.

    Args:
        public_events: Filtered public events
        living_players: Set of living player seats
        dead_players: Set of dead player seats
        your_seat: Current player's seat

    Returns:
        Formatted string for user prompt
    """
    parts = []

    # Death announcements
    if public_events.death_announcements:
        parts.append("DEATH ANNOUNCEMENTS:")
        for announcement in public_events.death_announcements:
            parts.append(f"  Seats who died: {sorted(announcement.dead_players)}")

    # Deaths today with last words
    if public_events.deaths_today:
        parts.append("DEATHS THIS MORNING:")
        for death in public_events.deaths_today:
            if hasattr(death, "last_words") and death.last_words:
                parts.append(f"  Seat {death.actor}: {death.cause.value} - \"{death.last_words}\"")
            else:
                parts.append(f"  Seat {death.actor}: {death.cause.value}")

    # Previous speeches
    if public_events.previous_speeches:
        parts.append("\nPREVIOUS SPEECHES:")
        for speech in public_events.previous_speeches:
            preview = speech.content[:150] + "..." if len(speech.content) > 150 else speech.content
            parts.append(f"  Seat {speech.actor}: {preview}")

    # Sheriff nominations
    if public_events.sheriff_nominations:
        nominees = sorted(n.actor for n in public_events.sheriff_nominations)
        parts.append(f"\nSHERIFF CANDIDATES: {sorted(set(nominees))}")

    # Sheriff opt-outs
    if public_events.sheriff_opt_outs:
        opt_outs = sorted(n.actor for n in public_events.sheriff_opt_outs)
        parts.append(f"SHERIFF OPT-OUTS: {sorted(set(opt_outs))}")

    # Sheriff outcome
    if public_events.sheriff_outcome:
        parts.append(f"\nSHERIFF: Seat {public_events.sheriff_outcome.winner}")

    return "\n".join(parts)
