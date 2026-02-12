"""Event formatter for human-readable game logs.

Formats game events with ROLE(seat) notation and narrative descriptions.
"""

from typing import Optional

from .game_events import (
    GameEvent,
    WerewolfKill,
    WitchAction,
    SeerAction,
    GuardAction,
    Vote,
    DeathEvent,
    Speech,
    SheriffNomination,
    SheriffOptOut,
    SheriffOutcome,
    Banishment,
    NightOutcome,
    DeathAnnouncement,
    GameStart,
    GameOver,
    VictoryOutcome,
)


class EventFormatter:
    """Format game events with ROLE(seat) notation.

    Takes a roles_secret mapping and produces human-readable strings like:
    - "WEREWOLF(0) killed SEER(7)"
    - "WEREWOLF(5) voted for SEER(7)"
    """

    def __init__(self, roles_secret: dict[int, str]):
        """Initialize formatter with role mapping.

        Args:
            roles_secret: Dict mapping seat number to role name
        """
        self.roles_secret = roles_secret

    def format(self, event: GameEvent) -> str:
        """Format a single event with role context.

        Args:
            event: The game event to format

        Returns:
            Human-readable string describing the event
        """
        return self._dispatch(event)

    def _dispatch(self, event: GameEvent) -> str:
        """Route event to appropriate formatter method."""
        if isinstance(event, WerewolfKill):
            return self._format_werewolf_kill(event)
        elif isinstance(event, WitchAction):
            return self._format_witch_action(event)
        elif isinstance(event, SeerAction):
            return self._format_seer_action(event)
        elif isinstance(event, GuardAction):
            return self._format_guard_action(event)
        elif isinstance(event, Vote):
            return self._format_vote(event)
        elif isinstance(event, DeathEvent):
            return self._format_death_event(event)
        elif isinstance(event, Speech):
            return self._format_speech(event)
        elif isinstance(event, SheriffNomination):
            return self._format_sheriff_nomination(event)
        elif isinstance(event, SheriffOptOut):
            return self._format_sheriff_opt_out(event)
        elif isinstance(event, SheriffOutcome):
            return self._format_sheriff_outcome(event)
        elif isinstance(event, Banishment):
            return self._format_banishment(event)
        elif isinstance(event, NightOutcome):
            return self._format_night_outcome(event)
        elif isinstance(event, DeathAnnouncement):
            return self._format_death_announcement(event)
        elif isinstance(event, GameStart):
            return self._format_game_start(event)
        elif isinstance(event, GameOver):
            return self._format_game_over(event)
        elif isinstance(event, VictoryOutcome):
            return self._format_victory_outcome(event)
        else:
            # Fallback for unknown events
            return str(event)

    def _role_seat(self, seat: Optional[int]) -> str:
        """Format seat as ROLE(seat).

        Args:
            seat: The seat number, or None

        Returns:
            Formatted string like "WEREWOLF(5)" or "(unknown)" if seat is None
        """
        if seat is None:
            return "(unknown)"
        role = self.roles_secret.get(seat, "Unknown")
        return f"{role}({seat})"

    def _format_werewolf_kill(self, event: WerewolfKill) -> str:
        actor = self._role_seat(event.actor)
        if event.target is None:
            return f"{actor} decided to skip the kill"
        target = self._role_seat(event.target)
        return f"{actor} killed {target}"

    def _format_witch_action(self, event: WitchAction) -> str:
        actor = self._role_seat(event.actor)
        action = event.action_type.value

        if action == "PASS":
            return f"{actor} passed"
        elif action == "ANTIDOTE":
            target = self._role_seat(event.target)
            return f"{actor} used antidote on {target}"
        elif action == "POISON":
            target = self._role_seat(event.target)
            return f"{actor} used poison on {target}"
        else:
            return f"{actor} performed {action}"

    def _format_seer_action(self, event: SeerAction) -> str:
        actor = self._role_seat(event.actor)
        target = self._role_seat(event.target)
        result = event.result.value
        return f"{actor} checked {target} - {result}"

    def _format_guard_action(self, event: GuardAction) -> str:
        actor = self._role_seat(event.actor)
        if event.target is None:
            return f"{actor} protected no one (skip)"
        target = self._role_seat(event.target)
        return f"{actor} protected {target}"

    def _format_vote(self, event: Vote) -> str:
        actor = self._role_seat(event.actor)
        if event.target is None:
            return f"{actor} abstained"
        target = self._role_seat(event.target)
        return f"{actor} voted for {target}"

    def _format_death_event(self, event: DeathEvent) -> str:
        victim = self._role_seat(event.actor)
        cause = self._format_death_cause(event.cause)

        parts = [f"{victim} died ({cause})"]

        if event.last_words:
            words = event.last_words[:50] + "..." if len(event.last_words) > 50 else event.last_words
            parts.append(f'last words: "{words}"')

        if event.hunter_shoot_target is not None:
            shooter = self._role_seat(event.hunter_shoot_target)
            parts.append(f"hunter shot {shooter}")
        elif event.hunter_shoot_target is None and event.cause.value == "BANISHMENT":
            # Hunter was banished and chose to skip
            parts.append("hunter skipped shot")

        if event.badge_transfer_to is not None:
            new_sheriff = self._role_seat(event.badge_transfer_to)
            parts.append(f"badge passed to {new_sheriff}")

        return " - ".join(parts)

    def _format_death_cause(self, cause: str) -> str:
        """Format death cause for readability."""
        cause_map = {
            "WEREWOLF_KILL": "killed by werewolves",
            "POISON": "poisoned by witch",
            "BANISHMENT": "banished by vote",
        }
        return cause_map.get(cause, cause.lower().replace("_", " "))

    def _format_speech(self, event: Speech) -> str:
        actor = self._role_seat(event.actor)
        phase_type = event.micro_phase.value.lower()
        preview = event.content[:40] + "..." if len(event.content) > 40 else event.content
        return f"{actor} ({phase_type}): \"{preview}\""

    def _format_sheriff_nomination(self, event: SheriffNomination) -> str:
        actor = self._role_seat(event.actor)
        if event.running:
            return f"{actor} ran for sheriff"
        else:
            return f"{actor} did not run for sheriff"

    def _format_sheriff_opt_out(self, event: SheriffOptOut) -> str:
        actor = self._role_seat(event.actor)
        return f"{actor} withdrew from sheriff race"

    def _format_sheriff_outcome(self, event: SheriffOutcome) -> str:
        if event.winner is None:
            if event.candidates:
                return f"No sheriff elected (candidates: {event.candidates})"
            return "No sheriff elected"
        sheriff = self._role_seat(event.winner)
        return f"{sheriff} elected sheriff"

    def _format_banishment(self, event: Banishment) -> str:
        if event.banished is None:
            if event.tied_players:
                tied = [self._role_seat(s) for s in event.tied_players]
                return f"Tie between {', '.join(tied)} - no banishment"
            return "No banishment"
        victim = self._role_seat(event.banished)
        return f"{victim} was banished"

    def _format_night_outcome(self, event: NightOutcome) -> str:
        if not event.deaths:
            return "No deaths last night"

        death_parts = []
        for seat, cause in sorted(event.deaths.items()):
            victim = self._role_seat(seat)
            cause_str = self._format_death_cause(cause.value)
            death_parts.append(f"{victim} ({cause_str})")

        return " - ".join(death_parts)

    def _format_death_announcement(self, event: DeathAnnouncement) -> str:
        if not event.dead_players:
            return "No deaths announced"
        victims = [self._role_seat(s) for s in event.dead_players]
        return ", ".join(victims)

    def _format_game_start(self, event: GameStart) -> str:
        return f"Game started with {event.player_count} players"

    def _format_game_over(self, event: GameOver) -> str:
        winner = event.winner
        condition = event.condition.value.replace("_", " ").title()
        return f"Game Over: {winner} wins by {condition} (Day {event.final_turn_count})"

    def _format_victory_outcome(self, event: VictoryOutcome) -> str:
        if event.is_game_over:
            winner = event.winner or "Unknown"
            condition = event.condition.value.replace("_", " ").title() if event.condition else ""
            return f"{winner} wins by {condition}"
        return "Game ongoing"


__all__ = ["EventFormatter"]
