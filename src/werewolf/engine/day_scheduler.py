"""DayScheduler - orchestrates the day phase of the Werewolf game."""

from typing import Protocol, Sequence, Optional, TYPE_CHECKING
from pydantic import BaseModel, Field

from werewolf.events import (
    GameEvent,
    SubPhaseLog,
    SubPhase,
    Phase,
    DeathCause,
)
from werewolf.models import Player
from werewolf.engine import GameState, EventCollector

# Import validator for type hints (avoid circular import)
if TYPE_CHECKING:
    from werewolf.engine.validator import GameValidator


class Participant(Protocol):
    """A player (AI or human) that can make decisions."""

    async def decide(
        self,
        system_prompt: str,
        user_prompt: str,
        hint: Optional[str] = None,
    ) -> str:
        """Make a decision and return raw response string."""
        ...


class DayScheduler:
    """Orchestrates the day phase: Nomination -> Campaign -> OptOut -> SheriffElection -> DeathResolution -> Discussion -> Voting -> VictoryCheck"""

    def __init__(self, validator: Optional["GameValidator"] = None):
        """Initialize the DayScheduler.

        Args:
            validator: Optional validator for runtime rule checking.
                       Pass None or NoOpValidator for production (zero overhead).
        """
        self._validator = validator

    async def run_day(
        self,
        state: GameState,
        collector: EventCollector,
        participants: dict[int, Participant],
        night_deaths: dict[int, DeathCause] | None = None,
    ) -> tuple[GameState, EventCollector]:
        """Run complete day phase.

        Day order:
        1. NominationHandler (all players decide to run) - Day 1 only
        2. CampaignHandler (candidates give speeches) - Day 1 only
        3. OptOutHandler (candidates may drop out) - Day 1 only
        4. SheriffElectionHandler (vote for sheriff) - Day 1 only
        5. DeathResolutionHandler (night deaths, last words)
        6. DiscussionHandler (living players speak)
        7. VotingHandler (banishment vote)
        8. Victory check

        Args:
            state: Current game state
            collector: Event collector for the game
            participants: Dict mapping seat -> Participant
            night_deaths: Deaths from the previous night phase (for death resolution)

        Returns:
            Tuple of (updated state, updated collector)
        """
        # Create a copy to avoid mutating the input state
        state = state.model_copy(deep=True)

        # Default to empty dict if no deaths
        if night_deaths is None:
            night_deaths = {}
        # Update collector day
        collector.day = state.day

        # Hook: day start
        if self._validator:
            await self._validator.on_phase_start(Phase.DAY, state.day, state)

        collector.create_phase_log(Phase.DAY)

        # Build participants sequence from dict for handlers
        all_participants = list(participants.items())

        # Run Day 1 special phases
        if state.day == 1:
            # Nomination - all players decide if they want to run for Sheriff

            # Hook: subphase start - Nomination
            if self._validator:
                await self._validator.on_subphase_start(SubPhase.NOMINATION, state.day, state)

            nomination_result = await self._run_nomination(
                state=state,
                participants=all_participants,
            )
            collector.add_subphase_log(nomination_result.subphase_log)
            state.apply_events(nomination_result.subphase_log.events)

            # Hook: subphase end - Nomination
            if self._validator:
                await self._validator.on_subphase_end(
                    SubPhase.NOMINATION, state.day, Phase.DAY, state, collector
                )

            # Get candidates who nominated to run
            sheriff_candidates = self._get_nominated_seats(nomination_result.subphase_log.events)

            # If no one nominated, skip remaining sheriff phases
            if not sheriff_candidates:
                # No sheriff election occurs
                pass
            else:
                # Campaign - nominated candidates give speeches

                # Hook: subphase start - Campaign
                if self._validator:
                    await self._validator.on_subphase_start(SubPhase.CAMPAIGN, state.day, state)

                campaign_result = await self._run_campaign(
                    state=state,
                    participants=all_participants,
                    sheriff_candidates=sheriff_candidates,
                )
                collector.add_subphase_log(campaign_result.subphase_log)
                state.apply_events(campaign_result.subphase_log.events)

                # Hook: subphase end - Campaign
                if self._validator:
                    await self._validator.on_subphase_end(
                        SubPhase.CAMPAIGN, state.day, Phase.DAY, state, collector
                    )

                # Determine remaining candidates after speeches (those who gave speeches)
                candidates_after_speech = [
                    seat for seat in sheriff_candidates
                    if seat in [e.actor for e in campaign_result.subphase_log.events]
                ]

                # If no candidates remain after speech phase, skip opt-out and election
                if not candidates_after_speech:
                    sheriff_candidates = []
                else:
                    # OptOut - candidates decide whether to stay in race

                    # Hook: subphase start - OptOut
                    if self._validator:
                        await self._validator.on_subphase_start(SubPhase.OPT_OUT, state.day, state)

                    opt_out_result = await self._run_opt_out(
                        state=state,
                        participants=all_participants,
                        sheriff_candidates=candidates_after_speech,
                    )
                    collector.add_subphase_log(opt_out_result.subphase_log)
                    state.apply_events(opt_out_result.subphase_log.events)

                    # Hook: subphase end - OptOut
                    if self._validator:
                        await self._validator.on_subphase_end(
                            SubPhase.OPT_OUT, state.day, Phase.DAY, state, collector
                        )

                    # Determine remaining candidates after opt-outs
                    sheriff_candidates = [
                        seat for seat in candidates_after_speech
                        if seat not in self._get_opted_out_seats(opt_out_result.subphase_log.events)
                    ]

                # SheriffElection - vote for sheriff (only if candidates remain)
                if sheriff_candidates:
                    # Hook: subphase start - SheriffElection
                    if self._validator:
                        await self._validator.on_subphase_start(SubPhase.SHERIFF_ELECTION, state.day, state)

                    sheriff_result = await self._run_sheriff_election(
                        state=state,
                        participants=all_participants,
                        sheriff_candidates=sheriff_candidates,
                    )
                    collector.add_subphase_log(sheriff_result.subphase_log)
                    state.apply_events(sheriff_result.subphase_log.events)

                    # Hook: subphase end - SheriffElection
                    if self._validator:
                        await self._validator.on_subphase_end(
                            SubPhase.SHERIFF_ELECTION, state.day, Phase.DAY, state, collector
                        )

        # DeathResolution - process night deaths (from NightOutcome)

        # Hook: subphase start - DeathResolution
        if self._validator:
            await self._validator.on_subphase_start(SubPhase.DEATH_RESOLUTION, state.day, state)

        death_result = await self._run_death_resolution(
            state=state,
            participants=participants,
            deaths=night_deaths,
        )
        collector.add_subphase_log(death_result.subphase_log)
        # Apply death events to state (handles hunter shots and badge transfers)
        state.apply_events(death_result.subphase_log.events)

        # Hook: subphase end - DeathResolution
        if self._validator:
            await self._validator.on_subphase_end(
                SubPhase.DEATH_RESOLUTION, state.day, Phase.DAY, state, collector
            )

        # Hook: death chain complete (for day deaths as well)
        death_seats = [e.actor for e in death_result.subphase_log.events if hasattr(e, 'actor')]
        if self._validator and death_seats:
            await self._validator.on_death_chain_complete(death_seats, state)

        # Discussion - living players speak

        # Hook: subphase start - Discussion
        if self._validator:
            await self._validator.on_subphase_start(SubPhase.DISCUSSION, state.day, state)

        discussion_result = await self._run_discussion(
            state=state,
            participants=all_participants,
        )
        collector.add_subphase_log(discussion_result.subphase_log)
        state.apply_events(discussion_result.subphase_log.events)

        # Hook: subphase end - Discussion
        if self._validator:
            await self._validator.on_subphase_end(
                SubPhase.DISCUSSION, state.day, Phase.DAY, state, collector
            )

        # Voting - banishment vote

        # Hook: subphase start - Voting
        if self._validator:
            await self._validator.on_subphase_start(SubPhase.VOTING, state.day, state)

        voting_result = await self._run_voting(
            state=state,
            participants=all_participants,
        )
        collector.add_subphase_log(voting_result.subphase_log)

        # Hook: subphase end - Voting
        if self._validator:
            await self._validator.on_subphase_end(
                SubPhase.VOTING, state.day, Phase.DAY, state, collector
            )

        # Process banishment death if there was a banishment
        banished_seat = self._get_banished_seat(voting_result.subphase_log.events)
        if banished_seat is not None:
            # Hook: subphase start - BanishmentResolution
            if self._validator:
                await self._validator.on_subphase_start(SubPhase.BANISHMENT_RESOLUTION, state.day, state)

            # Run banishment resolution to get death event
            banishment_result = await self._run_banishment_resolution(
                state=state,
                participants=participants,
                banished_seat=banished_seat,
            )
            collector.add_subphase_log(banishment_result.subphase_log)
            state.apply_events(banishment_result.subphase_log.events)

            # Hook: subphase end - BanishmentResolution
            if self._validator:
                await self._validator.on_subphase_end(
                    SubPhase.BANISHMENT_RESOLUTION, state.day, Phase.DAY, state, collector
                )
        else:
            # No banishment, apply voting events (for Vote events)
            state.apply_events(voting_result.subphase_log.events)

        # Victory check
        is_over, winner = state.is_game_over()

        # Hook: victory check
        if self._validator:
            await self._validator.on_victory_check(state, is_over, winner)

        if is_over:
            self._finalize_game(collector, winner)

        # Hook: day end
        if self._validator:
            await self._validator.on_phase_end(Phase.DAY, state.day, state, collector)

        return state, collector

    async def _run_nomination(
        self,
        state: GameState,
        participants: Sequence[tuple[int, Participant]],
    ) -> "HandlerResult":
        """Run Nomination subphase."""
        from werewolf.handlers.nomination_handler import NominationHandler, HandlerResult
        handler = NominationHandler()
        context = self._build_context(state)
        return await handler(context, participants)

    def _build_context(self, state: GameState) -> "DayPhaseContext":
        """Build DayPhaseContext from GameState."""
        return DayPhaseContext(
            players=state.players,
            living_players=state.living_players,
            dead_players=state.dead_players,
            sheriff=state.sheriff,
            day=state.day,
        )

    async def _run_campaign(
        self,
        state: GameState,
        participants: Sequence[tuple[int, Participant]],
        sheriff_candidates: list[int],
    ) -> "HandlerResult":
        """Run Campaign subphase."""
        from werewolf.handlers.campaign_handler import CampaignHandler, HandlerResult
        handler = CampaignHandler()
        context = self._build_context(state)
        return await handler(context, participants, sheriff_candidates)

    async def _run_opt_out(
        self,
        state: GameState,
        participants: Sequence[tuple[int, Participant]],
        sheriff_candidates: list[int],
    ) -> "HandlerResult":
        """Run OptOut subphase."""
        from werewolf.handlers.opt_out_handler import OptOutHandler, HandlerResult
        handler = OptOutHandler()
        context = OptOutPhaseContext(
            sheriff_candidates=sheriff_candidates,
            living_players=state.living_players,
            dead_players=state.dead_players,
            day=state.day,
        )
        return await handler(context, participants)

    async def _run_sheriff_election(
        self,
        state: GameState,
        participants: Sequence[tuple[int, Participant]],
        sheriff_candidates: list[int],
    ) -> "HandlerResult":
        """Run SheriffElection subphase."""
        from werewolf.handlers.sheriff_election_handler import SheriffElectionHandler, HandlerResult
        handler = SheriffElectionHandler()
        context = SheriffElectionPhaseContext(
            sheriff_candidates=sheriff_candidates,
            living_players=state.living_players,
            dead_players=state.dead_players,
            sheriff=state.sheriff,
            day=state.day,
        )
        return await handler(context, participants, sheriff_candidates)

    async def _run_death_resolution(
        self,
        state: GameState,
        participants: dict[int, Participant],
        deaths: dict[int, DeathCause],
    ) -> "HandlerResult":
        """Run DeathResolution subphase (for night deaths during day phase).

        Args:
            state: Current game state
            participants: Dict mapping seat -> Participant
            deaths: Deaths dict from NightOutcome {seat: DeathCause}
        """
        from werewolf.handlers.death_resolution_handler import DeathResolutionHandler, HandlerResult
        from werewolf.events import SubPhase
        handler = DeathResolutionHandler()
        context = self._build_context(state)
        # Use deaths from NightOutcome (passed from WerewolfGame)
        night_outcome = DeathResolutionNightOutcome(
            day=state.day,
            deaths=deaths,
        )
        # Use DEATH_RESOLUTION micro_phase since this runs during DAY phase
        return await handler(context, night_outcome, participants, SubPhase.DEATH_RESOLUTION)

    async def _run_discussion(
        self,
        state: GameState,
        participants: Sequence[tuple[int, Participant]],
    ) -> "HandlerResult":
        """Run Discussion subphase."""
        from werewolf.handlers.discussion_handler import DiscussionHandler, HandlerResult
        handler = DiscussionHandler()
        context = self._build_context(state)
        return await handler(context, participants)

    async def _run_voting(
        self,
        state: GameState,
        participants: Sequence[tuple[int, Participant]],
    ) -> "HandlerResult":
        """Run Voting subphase."""
        from werewolf.handlers.voting_handler import VotingHandler, HandlerResult
        handler = VotingHandler()
        context = self._build_context(state)
        return await handler(context, participants)

    def _get_opted_out_seats(self, events: list[GameEvent]) -> list[int]:
        """Get seats that opted out from events."""
        from werewolf.events.game_events import SheriffOptOut
        return [e.actor for e in events if isinstance(e, SheriffOptOut)]

    def _get_nominated_seats(self, events: list[GameEvent]) -> list[int]:
        """Get seats that nominated to run from nomination events."""
        from werewolf.events.game_events import SheriffNomination
        return [e.actor for e in events if isinstance(e, SheriffNomination) and e.running]

    async def _run_banishment_resolution(
        self,
        state: GameState,
        participants: dict[int, Participant],
        banished_seat: int,
    ) -> "HandlerResult":
        """Run BanishmentResolution subphase."""
        from werewolf.handlers.banishment_resolution_handler import BanishmentResolutionHandler, HandlerResult, BanishmentInput
        handler = BanishmentResolutionHandler()
        banishment_input = BanishmentInput(
            day=state.day,
            banished=banished_seat,
        )
        context = self._build_context(state)
        # Get the participant for the banished player (single participant, not list)
        participant = participants.get(banished_seat)
        return await handler(context, banishment_input, participant)

    def _get_banished_seat(self, events: list[GameEvent]) -> Optional[int]:
        """Get banished seat from voting events."""
        from werewolf.events.game_events import Banishment
        for event in events:
            if isinstance(event, Banishment):
                return event.banished
        return None

    def _finalize_game(self, collector: EventCollector, winner: str) -> None:
        """Finalize game with winner."""
        from werewolf.events.game_events import GameOver, VictoryCondition
        from werewolf.engine import GameState

        # Determine victory condition based on winner and game state
        # This is a simplified version - a full implementation would track the condition
        if winner == "WEREWOLF":
            condition = VictoryCondition.ALL_GODS_KILLED
        else:
            condition = VictoryCondition.ALL_WEREWOLVES_KILLED

        game_over = GameOver(
            winner=winner,
            day=collector.day,
            condition=condition,
            final_turn_count=collector.day,
        )
        collector.set_game_over(game_over)


# ============================================================================
# Context classes for handlers
# ============================================================================

from werewolf.models.player import Role


class DayPhaseContext:
    """Context for day phase handlers."""

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

    def is_werewolf(self, seat: int) -> bool:
        player = self.get_player(seat)
        return player is not None and player.role == Role.WEREWOLF

    def is_alive(self, seat: int) -> bool:
        return seat in self.living_players


class OptOutPhaseContext:
    """Context for OptOut handler."""

    def __init__(
        self,
        sheriff_candidates: list[int],
        living_players: set[int],
        dead_players: set[int],
        day: int = 1,
    ):
        self.sheriff_candidates = sheriff_candidates
        self.living_players = living_players
        self.dead_players = dead_players
        self.day = day

    def is_alive(self, seat: int) -> bool:
        return seat in self.living_players


class SheriffElectionPhaseContext:
    """Context for SheriffElection handler."""

    def __init__(
        self,
        sheriff_candidates: list[int],
        living_players: set[int],
        dead_players: set[int],
        sheriff: Optional[int] = None,
        day: int = 1,
    ):
        self.sheriff_candidates = sheriff_candidates
        self.living_players = living_players
        self.dead_players = dead_players
        self.sheriff = sheriff
        self.day = day

    def is_alive(self, seat: int) -> bool:
        return seat in self.living_players


class DeathResolutionNightOutcome:
    """Night outcome input for death resolution."""

    def __init__(self, day: int, deaths: dict[int, DeathCause]):
        self.day = day
        self.deaths = deaths


# Type alias for HandlerResult (any handler's result)
HandlerResult = "DeathResolutionHandlerResult"  # Placeholder, actual type imported in methods
