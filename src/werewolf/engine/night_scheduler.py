"""NightScheduler - orchestrates the night phase of the Werewolf game.

Night order:
1. WerewolfAction (query werewolves, set kill_target)
2. WitchAction (query witch, set antidote/poison)
3. GuardAction + SeerAction (parallel)
4. Resolve deaths via NightActionResolver
"""

from typing import Protocol, Optional, TYPE_CHECKING

from werewolf.engine import (
    GameState,
    NightActionStore,
    EventCollector,
    NightActionResolver,
)
from werewolf.engine.game_state import GameState
from werewolf.events import (
    Phase,
    SubPhase,
    GameEvent,
    NightOutcome,
    DeathEvent,
    DeathCause,
)
from werewolf.models.player import Role

# Import validator for type hints (avoid circular import)
if TYPE_CHECKING:
    from werewolf.engine.validator import GameValidator

# Import handlers
from werewolf.handlers.werewolf_handler import (
    WerewolfHandler,
    PhaseContext as WerewolfPhaseContext,
    HandlerResult as WerewolfHandlerResult,
)
from werewolf.handlers.witch_handler import (
    WitchHandler,
    NightActions as WitchNightActions,
    HandlerResult as WitchHandlerResult,
)
from werewolf.handlers.guard_handler import GuardHandler, HandlerResult as GuardHandlerResult
from werewolf.handlers.seer_handler import SeerHandler, HandlerResult as SeerHandlerResult
from werewolf.handlers.death_resolution_handler import (
    DeathResolutionHandler,
    NightOutcomeInput,
    HandlerResult as DeathResolutionHandlerResult,
)
from werewolf.handlers.witch_handler import MaxRetriesExceededError


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


class NightScheduler:
    """Orchestrates the night phase: Werewolf -> Witch -> Guard/Seer (parallel) -> Resolution."""

    def __init__(self, validator: Optional["GameValidator"] = None):
        """Initialize the night scheduler with handlers.

        Args:
            validator: Optional validator for runtime rule checking.
                       Pass None or NoOpValidator for production (zero overhead).
        """
        self._werewolf_handler = WerewolfHandler()
        self._witch_handler = WitchHandler()
        self._guard_handler = GuardHandler()
        self._seer_handler = SeerHandler()
        self._resolver = NightActionResolver()
        self._death_handler = DeathResolutionHandler()
        self._validator = validator

    async def run_night(
        self,
        state: GameState,
        actions: NightActionStore,
        collector: EventCollector,
        participants: dict[int, Participant],
    ) -> tuple[GameState, NightActionStore, EventCollector]:
        """Run complete night phase.

        Night order:
        1. WerewolfAction (query werewolves, set kill_target)
        2. WitchAction (query witch, set antidote/poison)
        3. GuardAction + SeerAction (parallel)
        4. Resolve deaths via NightActionResolver

        Args:
            state: Current game state with players, living/dead tracking.
            actions: Night action store with persistent state (potions used, previous guard).
            collector: Event collector to accumulate game events.
            participants: Dict mapping seat -> Participant for AI/human decisions.

        Returns:
            Tuple of (updated state, updated actions, updated collector).
        """
        # Create fresh NightActionStore from snapshot (preserves persistent state)
        night_actions = NightActionStore.from_snapshot(actions.snapshot())

        # Set day BEFORE creating phase log (so phase number uses correct day)
        collector.day = state.day

        # Hook: night start
        if self._validator:
            await self._validator.on_phase_start(Phase.NIGHT, state.day, state)

        # Create phase log for NIGHT
        collector.create_phase_log(Phase.NIGHT)

        # Hook: subphase start - WerewolfAction
        if self._validator:
            await self._validator.on_subphase_start(SubPhase.WEREWOLF_ACTION, state.day, state)

        # Build PhaseContext for handlers
        context = self._build_phase_context(state)

        # Step 1: WerewolfAction
        werewolf_participants = self._extract_role_participants(
            participants, state, Role.WEREWOLF
        )
        ww_result = await self._run_werewolf_action(context, werewolf_participants)
        collector.add_subphase_log(ww_result.subphase_log)

        # Hook: subphase end - WerewolfAction
        if self._validator:
            await self._validator.on_subphase_end(
                SubPhase.WEREWOLF_ACTION, state.day, Phase.NIGHT, state, collector
            )

        # Update kill_target from werewolf action
        self._update_kill_target(ww_result, night_actions)

        # Step 2: WitchAction
        witch_participants = self._extract_role_participants(
            participants, state, Role.WITCH
        )

        # Hook: subphase start - WitchAction
        if self._validator:
            await self._validator.on_subphase_start(SubPhase.WITCH_ACTION, state.day, state)

        witch_result = await self._run_witch_action(context, witch_participants, night_actions)
        collector.add_subphase_log(witch_result.subphase_log)

        # Hook: subphase end - WitchAction
        if self._validator:
            await self._validator.on_subphase_end(
                SubPhase.WITCH_ACTION, state.day, Phase.NIGHT, state, collector
            )

        # Update antidote/poison targets from witch action
        self._update_witch_targets(witch_result, night_actions)

        # Step 3: GuardAction + SeerAction (parallel - run sequentially for simplicity)
        guard_participants = self._extract_role_participants(
            participants, state, Role.GUARD
        )

        # Hook: subphase start - GuardAction
        if self._validator:
            await self._validator.on_subphase_start(SubPhase.GUARD_ACTION, state.day, state)

        guard_result = await self._run_guard_action(
            context, guard_participants, night_actions
        )
        collector.add_subphase_log(guard_result.subphase_log)

        # Hook: subphase end - GuardAction
        if self._validator:
            await self._validator.on_subphase_end(
                SubPhase.GUARD_ACTION, state.day, Phase.NIGHT, state, collector
            )

        # Update guard_target from guard action
        self._update_guard_target(guard_result, night_actions)

        seer_participants = self._extract_role_participants(
            participants, state, Role.SEER
        )

        # Hook: subphase start - SeerAction
        if self._validator:
            await self._validator.on_subphase_start(SubPhase.SEER_ACTION, state.day, state)

        seer_result = await self._run_seer_action(context, seer_participants)
        collector.add_subphase_log(seer_result.subphase_log)

        # Hook: subphase end - SeerAction
        if self._validator:
            await self._validator.on_subphase_end(
                SubPhase.SEER_ACTION, state.day, Phase.NIGHT, state, collector
            )

        # Step 4: Resolve deaths (who died, cause)

        # Hook: subphase start - NightResolution
        if self._validator:
            await self._validator.on_subphase_start(SubPhase.NIGHT_RESOLUTION, state.day, state)

        deaths = self._resolver.resolve(state, night_actions)

        # Add NightOutcome event to announce who died during the night
        # Death resolution (last words, hunter shots, badge transfer) happens during DAY
        night_outcome_event = NightOutcome(
            day=state.day,
            deaths=deaths,
        )
        collector.add_event(night_outcome_event)

        # Hook: subphase end - NightResolution
        if self._validator:
            await self._validator.on_subphase_end(
                SubPhase.NIGHT_RESOLUTION, state.day, Phase.NIGHT, state, collector
            )

        # Apply death events to state (remove dead players, handle hunter shots, badge transfer)
        # This is done immediately to update living/dead status for the day
        state.apply_events_from_deaths(deaths)

        # Hook: death chain complete
        if self._validator:
            await self._validator.on_death_chain_complete(list(deaths.keys()), state)

        # Update actions with any persisted changes (e.g., antidote_used, poison_used)
        actions = self._update_actions_persistent_state(actions, night_actions)

        # Hook: night end
        if self._validator:
            await self._validator.on_phase_end(Phase.NIGHT, state.day, state, collector)

        return state, actions, collector, deaths

    def _build_phase_context(self, state: GameState) -> WerewolfPhaseContext:
        """Build PhaseContext from GameState for handlers."""
        return WerewolfPhaseContext(
            players=state.players,
            living_players=state.living_players,
            dead_players=state.dead_players,
            sheriff=state.sheriff,
            day=state.day,
        )

    def _extract_role_participants(
        self,
        participants: dict[int, Participant],
        state: GameState,
        role: Role,
    ) -> dict[int, Participant]:
        """Extract participants for a specific role from the participants dict."""
        result = {}
        for seat in state.living_players:
            player = state.players.get(seat)
            if player and player.role == role:
                if seat in participants:
                    result[seat] = participants[seat]
        return result

    async def _run_werewolf_action(
        self,
        context: WerewolfPhaseContext,
        participants: dict[int, Participant],
    ) -> WerewolfHandlerResult:
        """Run werewolf action subphase."""
        return await self._werewolf_handler(
            context, list(participants.items())
        )

    async def _run_witch_action(
        self,
        context: WerewolfPhaseContext,
        participants: dict[int, Participant],
        night_actions: NightActionStore,
    ) -> WitchHandlerResult:
        """Run witch action subphase."""
        # Convert NightActionStore to WitchNightActions format
        witch_night_actions = WitchNightActions(
            kill_target=night_actions.kill_target,
            antidote_used=night_actions.antidote_used,
            poison_used=night_actions.poison_used,
        )

        try:
            return await self._witch_handler(
                context, list(participants.items()), witch_night_actions
            )
        except MaxRetriesExceededError:
            # If witch fails to decide after retries, return empty result (pass)
            from werewolf.events import SubPhase
            from werewolf.handlers.witch_handler import SubPhaseLog as WitchSubPhaseLog
            return WitchHandlerResult(
                subphase_log=WitchSubPhaseLog(
                    micro_phase=SubPhase.WITCH_ACTION,
                    events=[],
                ),
                debug_info="Witch failed to decide after retries, passing",
            )

    async def _run_guard_action(
        self,
        context: WerewolfPhaseContext,
        participants: dict[int, Participant],
        night_actions: NightActionStore,
    ) -> GuardHandlerResult:
        """Run guard action subphase."""
        return await self._guard_handler(
            context,
            list(participants.items()),
            guard_prev_target=night_actions.guard_prev_target,
        )

    async def _run_seer_action(
        self,
        context: WerewolfPhaseContext,
        participants: dict[int, Participant],
    ) -> SeerHandlerResult:
        """Run seer action subphase."""
        return await self._seer_handler(context, list(participants.items()))

    async def _run_death_resolution(
        self,
        context: WerewolfPhaseContext,
        deaths: dict[int, DeathCause],
        participants: dict[int, Participant],
    ) -> DeathResolutionHandlerResult:
        """Run death resolution subphase."""
        # Create NightOutcomeInput
        night_outcome = NightOutcomeInput(day=context.day, deaths=deaths)

        return await self._death_handler(
            context, night_outcome, list(participants.items())
        )

    def _update_kill_target(
        self, result: WerewolfHandlerResult, actions: NightActionStore
    ) -> None:
        """Extract kill_target from werewolf result and update actions."""
        from werewolf.events.game_events import WerewolfKill

        for event in result.subphase_log.events:
            if isinstance(event, WerewolfKill):
                actions.kill_target = event.target
                break

    def _update_witch_targets(
        self, result: WitchHandlerResult, actions: NightActionStore
    ) -> None:
        """Extract antidote/poison targets from witch result and update actions."""
        from werewolf.events.game_events import WitchAction, WitchActionType

        for event in result.subphase_log.events:
            if isinstance(event, WitchAction):
                if event.action_type == WitchActionType.ANTIDOTE:
                    actions.antidote_target = event.target
                    actions.antidote_used = True
                elif event.action_type == WitchActionType.POISON:
                    actions.poison_target = event.target
                    actions.poison_used = True
                break

    def _update_guard_target(
        self, result: GuardHandlerResult, actions: NightActionStore
    ) -> None:
        """Extract guard_target from guard result and update actions."""
        from werewolf.events.game_events import GuardAction

        for event in result.subphase_log.events:
            if isinstance(event, GuardAction):
                actions.guard_target = event.target
                break

    def _update_actions_persistent_state(
        self,
        original: NightActionStore,
        updated: NightActionStore,
    ) -> NightActionStore:
        """Update persistent state from nightly actions back to original store."""
        # Return a new NightActionStore with persistent state preserved
        return NightActionStore(
            antidote_used=updated.antidote_used,
            poison_used=updated.poison_used,
            guard_prev_target=updated.guard_target,  # Tonight's guard target becomes prev for next night
            kill_target=None,  # Reset ephemeral targets
            antidote_target=None,
            poison_target=None,
            guard_target=None,
        )
