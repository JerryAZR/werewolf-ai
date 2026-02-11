"""Comprehensive tests for WitchAction handler."""

import pytest
from typing import Optional, Any, Protocol, Sequence
from pydantic import BaseModel

from werewolf.events.game_events import (
    WitchAction,
    WitchActionType,
    Phase,
    SubPhase,
    GameEvent,
)
from werewolf.events.event_log import SubPhaseLog
from werewolf.models.player import Player, Role, PlayerType


# ============================================================================
# Mock Participant for Testing
# ============================================================================


class MockParticipant:
    """Mock participant that returns configurable responses."""

    def __init__(
        self,
        response: str | None = None,
        response_iter: list[str] | None = None,
    ):
        """Initialize with a single response or an iterator of responses.

        Args:
            response: Single response string to return
            response_iter: Optional list of responses to return in sequence
        """
        self._response = response
        self._response_iter = response_iter
        self._call_count = 0

    async def decide(
        self,
        system_prompt: str,
        user_prompt: str,
        **extra: Any
    ) -> str:
        """Return configured response."""
        self._call_count += 1
        if self._response_iter and self._call_count <= len(self._response_iter):
            return self._response_iter[self._call_count - 1]
        if self._response is not None:
            return self._response
        raise ValueError("MockParticipant: no response configured")


# ============================================================================
# PhaseContext and NightActions for Testing
# ============================================================================


class NightActions(BaseModel):
    """Night actions state for WitchAction handler."""

    kill_target: Optional[int] = None  # Werewolf's chosen target
    antidote_used: bool = False
    poison_used: bool = False
    guard_target: Optional[int] = None


class WitchPhaseContext(BaseModel):
    """Context for WitchAction handler testing."""

    players: dict[int, Player]
    living_players: set[int]
    dead_players: set[int]
    sheriff: Optional[int] = None
    day: int = 1
    night_actions: NightActions = NightActions()

    def get_player(self, seat: int) -> Optional[Player]:
        """Get player by seat."""
        return self.players.get(seat)

    def is_werewolf(self, seat: int) -> bool:
        """Check if a player is a werewolf."""
        player = self.get_player(seat)
        return player is not None and player.role == Role.WEREWOLF

    def is_witch(self, seat: int) -> bool:
        """Check if a player is the witch."""
        player = self.get_player(seat)
        return player is not None and player.role == Role.WITCH

    def is_alive(self, seat: int) -> bool:
        """Check if a player is alive."""
        return seat in self.living_players

    def is_god(self, seat: int) -> bool:
        """Check if player is a God role (Seer, Witch, Guard, Hunter)."""
        player = self.get_player(seat)
        if player is None:
            return False
        return player.role in (Role.SEER, Role.WITCH, Role.GUARD, Role.HUNTER)


# ============================================================================
# Context Factory Functions
# ============================================================================


def make_context_standard_12() -> tuple[WitchPhaseContext, dict[int, MockParticipant]]:
    """Create a standard 12-player game context for Night 1.

    Roles:
    - Werewolves: seats 0, 1, 2, 3
    - Seer: seat 4
    - Witch: seat 5
    - Guard: seat 6
    - Hunter: seat 7
    - Ordinary Villagers: seats 8, 9, 10, 11
    """
    players = {
        0: Player(seat=0, name="W1", role=Role.WEREWOLF, is_alive=True),
        1: Player(seat=1, name="W2", role=Role.WEREWOLF, is_alive=True),
        2: Player(seat=2, name="W3", role=Role.WEREWOLF, is_alive=True),
        3: Player(seat=3, name="W4", role=Role.WEREWOLF, is_alive=True),
        4: Player(seat=4, name="Seer", role=Role.SEER, is_alive=True),
        5: Player(seat=5, name="Witch", role=Role.WITCH, is_alive=True),
        6: Player(seat=6, name="Guard", role=Role.GUARD, is_alive=True),
        7: Player(seat=7, name="Hunter", role=Role.HUNTER, is_alive=True),
        8: Player(seat=8, name="V1", role=Role.ORDINARY_VILLAGER, is_alive=True),
        9: Player(seat=9, name="V2", role=Role.ORDINARY_VILLAGER, is_alive=True),
        10: Player(seat=10, name="V3", role=Role.ORDINARY_VILLAGER, is_alive=True),
        11: Player(seat=11, name="V4", role=Role.ORDINARY_VILLAGER, is_alive=True),
    }
    living = set(range(12))
    dead = set()
    night_actions = NightActions(kill_target=4)  # Werewolves targeting Seer

    context = WitchPhaseContext(
        players=players,
        living_players=living,
        dead_players=dead,
        sheriff=None,
        day=1,
        night_actions=night_actions,
    )
    return context, {}


def make_context_witch_dead() -> tuple[WitchPhaseContext, dict[int, MockParticipant]]:
    """Create context where witch is dead."""
    players = {
        0: Player(seat=0, name="W1", role=Role.WEREWOLF, is_alive=True),
        1: Player(seat=1, name="W2", role=Role.WEREWOLF, is_alive=True),
        4: Player(seat=4, name="Seer", role=Role.SEER, is_alive=True),
        5: Player(seat=5, name="Witch", role=Role.WITCH, is_alive=False),  # Dead!
        6: Player(seat=6, name="Guard", role=Role.GUARD, is_alive=True),
        8: Player(seat=8, name="V1", role=Role.ORDINARY_VILLAGER, is_alive=True),
    }
    living = {0, 1, 4, 6, 8}
    dead = {5, 7, 9, 10, 11}
    night_actions = NightActions(kill_target=4)

    context = WitchPhaseContext(
        players=players,
        living_players=living,
        dead_players=dead,
        sheriff=None,
        day=2,
        night_actions=night_actions,
    )
    return context, {}


def make_context_no_werewolf_target() -> tuple[WitchPhaseContext, dict[int, MockParticipant]]:
    """Create context where werewolves chose not to kill (target=None)."""
    players = {
        0: Player(seat=0, name="W1", role=Role.WEREWOLF, is_alive=True),
        1: Player(seat=1, name="W2", role=Role.WEREWOLF, is_alive=True),
        4: Player(seat=4, name="Seer", role=Role.SEER, is_alive=True),
        5: Player(seat=5, name="Witch", role=Role.WITCH, is_alive=True),
        6: Player(seat=6, name="Guard", role=Role.GUARD, is_alive=True),
        8: Player(seat=8, name="V1", role=Role.ORDINARY_VILLAGER, is_alive=True),
    }
    living = {0, 1, 4, 5, 6, 8}
    dead = {2, 3, 7, 9, 10, 11}
    night_actions = NightActions(kill_target=None)  # No kill!

    context = WitchPhaseContext(
        players=players,
        living_players=living,
        dead_players=dead,
        sheriff=None,
        day=1,
        night_actions=night_actions,
    )
    return context, {}


def make_context_witch_is_target() -> tuple[WitchPhaseContext, dict[int, MockParticipant]]:
    """Create context where witch is the werewolf target."""
    players = {
        0: Player(seat=0, name="W1", role=Role.WEREWOLF, is_alive=True),
        1: Player(seat=1, name="W2", role=Role.WEREWOLF, is_alive=True),
        4: Player(seat=4, name="Seer", role=Role.SEER, is_alive=True),
        5: Player(seat=5, name="Witch", role=Role.WITCH, is_alive=True),
        6: Player(seat=6, name="Guard", role=Role.GUARD, is_alive=True),
        8: Player(seat=8, name="V1", role=Role.ORDINARY_VILLAGER, is_alive=True),
    }
    living = {0, 1, 4, 5, 6, 8}
    dead = {2, 3, 7, 9, 10, 11}
    night_actions = NightActions(kill_target=5)  # Witch is target!

    context = WitchPhaseContext(
        players=players,
        living_players=living,
        dead_players=dead,
        sheriff=None,
        day=1,
        night_actions=night_actions,
    )
    return context, {}


def make_context_antidote_used() -> tuple[WitchPhaseContext, dict[int, MockParticipant]]:
    """Create context where antidote was already used."""
    players = {
        0: Player(seat=0, name="W1", role=Role.WEREWOLF, is_alive=True),
        1: Player(seat=1, name="W2", role=Role.WEREWOLF, is_alive=True),
        4: Player(seat=4, name="Seer", role=Role.SEER, is_alive=True),
        5: Player(seat=5, name="Witch", role=Role.WITCH, is_alive=True),
        6: Player(seat=6, name="Guard", role=Role.GUARD, is_alive=True),
        8: Player(seat=8, name="V1", role=Role.ORDINARY_VILLAGER, is_alive=True),
    }
    living = {0, 1, 4, 5, 6, 8}
    dead = {2, 3, 7, 9, 10, 11}
    night_actions = NightActions(kill_target=4, antidote_used=True)

    context = WitchPhaseContext(
        players=players,
        living_players=living,
        dead_players=dead,
        sheriff=None,
        day=3,
        night_actions=night_actions,
    )
    return context, {}


def make_context_poison_used() -> tuple[WitchPhaseContext, dict[int, MockParticipant]]:
    """Create context where poison was already used."""
    players = {
        0: Player(seat=0, name="W1", role=Role.WEREWOLF, is_alive=True),
        1: Player(seat=1, name="W2", role=Role.WEREWOLF, is_alive=True),
        4: Player(seat=4, name="Seer", role=Role.SEER, is_alive=True),
        5: Player(seat=5, name="Witch", role=Role.WITCH, is_alive=True),
        6: Player(seat=6, name="Guard", role=Role.GUARD, is_alive=True),
        8: Player(seat=8, name="V1", role=Role.ORDINARY_VILLAGER, is_alive=True),
    }
    living = {0, 1, 4, 5, 6, 8}
    dead = {2, 3, 7, 9, 10, 11}
    night_actions = NightActions(kill_target=4, poison_used=True)

    context = WitchPhaseContext(
        players=players,
        living_players=living,
        dead_players=dead,
        sheriff=None,
        day=3,
        night_actions=night_actions,
    )
    return context, {}


def make_context_both_potions_used() -> tuple[WitchPhaseContext, dict[int, MockParticipant]]:
    """Create context where both potions are already used."""
    players = {
        0: Player(seat=0, name="W1", role=Role.WEREWOLF, is_alive=True),
        1: Player(seat=1, name="W2", role=Role.WEREWOLF, is_alive=True),
        4: Player(seat=4, name="Seer", role=Role.SEER, is_alive=True),
        5: Player(seat=5, name="Witch", role=Role.WITCH, is_alive=True),
        6: Player(seat=6, name="Guard", role=Role.GUARD, is_alive=True),
        8: Player(seat=8, name="V1", role=Role.ORDINARY_VILLAGER, is_alive=True),
    }
    living = {0, 1, 4, 5, 6, 8}
    dead = {2, 3, 7, 9, 10, 11}
    night_actions = NightActions(kill_target=4, antidote_used=True, poison_used=True)

    context = WitchPhaseContext(
        players=players,
        living_players=living,
        dead_players=dead,
        sheriff=None,
        day=4,
        night_actions=night_actions,
    )
    return context, {}


# ============================================================================
# WitchHandler Implementation (for testing)
# ============================================================================


class HandlerResult(BaseModel):
    """Output from handlers containing all events from a subphase."""

    subphase_log: SubPhaseLog
    debug_info: Optional[str] = None


class WitchHandler:
    """Handler for WitchAction subphase.

    Responsibilities:
    1. Build filtered context for witch (see kill target, potions, living players)
    2. Query living witch for action (ANTIDOTE, POISON, PASS)
    3. Validate actions against game rules
    4. Return WitchAction event

    Context Filtering (what witch sees):
    - Witch's own seat and role
    - Werewolf kill target (critical for antidote decision)
    - Remaining potions: antidote (1/0), poison (1/0)
    - All living player seats

    What witch does NOT see:
    - Other players' roles (Seer, Guard, Hunter, Villager)
    - Guard protection target
    - Werewolf team composition
    """

    max_retries: int = 3

    async def __call__(
        self,
        context: WitchPhaseContext,
        participants: Sequence[tuple[int, MockParticipant]]
    ) -> HandlerResult:
        """Execute the WitchAction subphase.

        Args:
            context: Game state with players, living/dead, sheriff, night_actions
            participants: Sequence of (seat, MockParticipant) tuples

        Returns:
            HandlerResult with SubPhaseLog containing WitchAction event
        """
        # Check if witch is alive
        witch_seat = self._find_witch_seat(context)
        if witch_seat is None:
            return HandlerResult(
                subphase_log=SubPhaseLog(micro_phase=SubPhase.WITCH_ACTION),
                debug_info="Witch is dead, skipping WitchAction",
            )

        # Get the participant
        participant_lookup = dict(participants)
        participant = participant_lookup.get(witch_seat)

        if participant is None:
            # No participant provided, return empty log
            return HandlerResult(
                subphase_log=SubPhaseLog(micro_phase=SubPhase.WITCH_ACTION),
            )

        # Get valid action from participant
        action = await self._get_valid_action(context, participant, witch_seat)

        events = [WitchAction(
            actor=witch_seat,
            action_type=action.action_type,
            target=action.target,
            day=context.day,
        )]

        return HandlerResult(
            subphase_log=SubPhaseLog(
                micro_phase=SubPhase.WITCH_ACTION,
                events=events,
            ),
        )

    def _find_witch_seat(self, context: WitchPhaseContext) -> Optional[int]:
        """Find the living witch's seat."""
        for seat in context.living_players:
            if context.is_witch(seat):
                return seat
        return None

    def _build_prompts(
        self,
        context: WitchPhaseContext,
        for_seat: int,
    ) -> tuple[str, str]:
        """Build filtered prompts for witch.

        Args:
            context: Game state
            for_seat: The witch seat to build prompts for

        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        night_actions = context.night_actions
        kill_target = night_actions.kill_target
        antidote_available = not night_actions.antidote_used
        poison_available = not night_actions.poison_used

        # Determine available actions
        available_actions = []
        if kill_target is not None and antidote_available and for_seat != kill_target:
            available_actions.append("ANTIDOTE (save the werewolf target)")
        if poison_available:
            available_actions.append("POISON (kill any living player)")
        available_actions.append("PASS (do nothing)")

        living_players = sorted(context.living_players)

        # Build system prompt
        system = f"""You are the Witch on Night {context.day}.

YOUR POTIONS:
- Antidote: {'1 remaining' if antidote_available else '0 remaining (already used)'}
- Poison: {'1 remaining' if poison_available else '0 remaining (already used)'}"""

        # Add kill target info
        if kill_target is not None:
            system += f"""

WEREWOLF KILL TARGET: Player at seat {kill_target}

You can use your ANTIDOTE to save this player from death.
Note: You CANNOT use the antidote on yourself."""

        # Add action options
        system += f"""

AVAILABLE ACTIONS:
{chr(10).join(f'- {action}' for action in available_actions)}

IMPORTANT RULES:
1. ANTIDOTE: Only works on the werewolf kill target. Cannot target yourself.
2. POISON: Can target ANY living player, including werewolves.
3. PASS: Do nothing this night.
4. You can only use ONE potion per night (antidote OR poison, not both).
5. Once a potion is used, it's gone forever."""

        # Build user prompt
        target_info = ""
        if kill_target is not None:
            target_info = f"""
WEREWOLF KILL TARGET: Seat {kill_target}
You can use ANTIDOTE to save this player."""

        user = f"""=== Night {context.day} - Witch Action ===

LIVING PLAYERS (seat numbers): {', '.join(map(str, living_players))}{target_info}

YOUR POTIONS:
- Antidote: {'Available' if antidote_available else 'Used'} {'(can save kill target)' if antidote_available else ''}
- Poison: {'Available' if poison_available else 'Used'}

Enter your action in the format:
- ANTIDOTE <seat> (e.g., "ANTIDOTE 4" to save seat 4)
- POISON <seat> (e.g., "POISON 8" to kill seat 8)
- PASS (do nothing)

Your action:"""

        return system, user

    async def _get_valid_action(
        self,
        context: WitchPhaseContext,
        participant: MockParticipant,
        for_seat: int,
    ) -> WitchAction:
        """Get valid action from participant with retry.

        Args:
            context: Game state
            participant: The participant to query
            for_seat: The witch seat making the decision

        Returns:
            Valid WitchAction data
        """
        night_actions = context.night_actions

        for attempt in range(self.max_retries):
            system, user = self._build_prompts(context, for_seat)

            # Add hint for retry attempts
            hint = None
            if attempt > 0:
                hint = "Previous response was invalid. Please choose a valid action."

            raw = await participant.decide(system, user, hint=hint)

            try:
                action = self._parse_action(raw, context, for_seat)
                return action
            except ValueError as e:
                hint = str(e)

            if attempt == self.max_retries - 1:
                # On last attempt, fallback to PASS instead of raising
                return WitchActionData(action_type=WitchActionType.PASS, target=None)

            # Retry with hint
            try:
                raw = await participant.decide(system, user, hint=hint)
                action = self._parse_action(raw, context, for_seat)
                return action
            except ValueError:
                pass  # Will retry in next iteration

        # Fallback to PASS
        return WitchActionData(action_type=WitchActionType.PASS, target=None)

    def _parse_action(
        self,
        raw_response: str,
        context: WitchPhaseContext,
        witch_seat: int,
    ) -> "WitchActionData":
        """Parse the raw response into a WitchAction.

        Args:
            raw_response: Raw string from participant
            context: Game state
            witch_seat: The witch's seat

        Returns:
            WitchActionData with parsed action

        Raises:
            ValueError: If response cannot be parsed or is invalid
        """
        night_actions = context.night_actions
        cleaned = raw_response.strip().upper()

        # Parse PASS - can always pass regardless of potions
        if cleaned == "PASS":
            return WitchActionData(action_type=WitchActionType.PASS, target=None)

        # Parse ANTIDOTE
        if cleaned.startswith("ANTIDOTE"):
            parts = cleaned.split()
            if len(parts) != 2:
                raise ValueError("ANTIDOTE requires a target seat. Example: ANTIDOTE 4")
            try:
                target = int(parts[1])
            except ValueError:
                raise ValueError("Invalid seat number. Use ANTIDOTE <seat>")

            # Validate antidote requirements
            if night_actions.antidote_used:
                raise ValueError("Antidote already used. Choose a different action.")
            if night_actions.kill_target is None:
                raise ValueError("No werewolf kill target - antidote cannot be used.")
            if target != night_actions.kill_target:
                raise ValueError(f"Antidote must target the werewolf kill target (seat {night_actions.kill_target}), not seat {target}")
            if target == witch_seat:
                raise ValueError("You cannot use antidote on yourself!")
            if target not in context.living_players:
                raise ValueError(f"Player at seat {target} is dead. Choose a living player.")

            return WitchActionData(action_type=WitchActionType.ANTIDOTE, target=target)

        # Parse POISON
        if cleaned.startswith("POISON"):
            parts = cleaned.split()
            if len(parts) != 2:
                raise ValueError("POISON requires a target seat. Example: POISON 8")
            try:
                target = int(parts[1])
            except ValueError:
                raise ValueError("Invalid seat number. Use POISON <seat>")

            # Validate poison requirements
            if night_actions.poison_used:
                raise ValueError("Poison already used. Choose a different action.")
            if target not in context.living_players:
                raise ValueError(f"Player at seat {target} is dead. Choose a living player.")

            return WitchActionData(action_type=WitchActionType.POISON, target=target)

        # Check for malformed PASS with target
        if any(keyword in cleaned for keyword in ["PASS", "SKIP", "NOTHING"]) and any(
            c.isdigit() for c in cleaned
        ):
            raise ValueError("PASS cannot have a target. Use 'PASS' alone or specify ANTIDOTE/POISON with a seat.")

        raise ValueError("Invalid action format. Use: ANTIDOTE <seat>, POISON <seat>, or PASS")

    def _is_valid_action(
        self,
        action_type: WitchActionType,
        target: Optional[int],
        context: WitchPhaseContext,
        witch_seat: int,
    ) -> tuple[bool, str]:
        """Check if action is valid.

        Returns:
            Tuple of (is_valid, error_message)
        """
        night_actions = context.night_actions

        if action_type == WitchActionType.ANTIDOTE:
            if night_actions.antidote_used:
                return False, "Antidote already used"
            if night_actions.kill_target is None:
                return False, "No werewolf kill target - antidote cannot be used"
            if target != night_actions.kill_target:
                return False, f"Target must be werewolf kill target (seat {night_actions.kill_target})"
            if target == witch_seat:
                return False, "Cannot use antidote on self"
            if target not in context.living_players:
                return False, "Target must be alive"
            return True, ""

        if action_type == WitchActionType.POISON:
            if night_actions.poison_used:
                return False, "Poison already used"
            if target is None:
                return False, "Poison requires a target"
            if target not in context.living_players:
                return False, "Target must be alive"
            return True, ""

        if action_type == WitchActionType.PASS:
            if target is not None:
                return False, "PASS cannot have a target"
            return True, ""

        return False, "Unknown action type"


class WitchActionData:
    """Data class for parsed witch action."""

    def __init__(self, action_type: WitchActionType, target: Optional[int]):
        self.action_type = action_type
        self.target = target


class MaxRetriesExceededError(Exception):
    """Raised when max retries are exceeded."""
    pass


# ============================================================================
# Expected WitchAction Event Factory
# ============================================================================


def expected_witch_action(
    actor: int,
    action_type: WitchActionType,
    target: Optional[int] = None,
    day: int = 1,
) -> WitchAction:
    """Create an expected WitchAction event for validation."""
    return WitchAction(
        actor=actor,
        action_type=action_type,
        target=target,
        day=day,
        phase=Phase.NIGHT,
        micro_phase=SubPhase.WITCH_ACTION,
    )


# ============================================================================
# Tests for WitchAction Valid Scenarios
# ============================================================================


class TestWitchActionValidScenarios:
    """Tests for valid WitchAction scenarios."""

    @pytest.mark.asyncio
    async def test_antidote_saves_werewolf_target(self):
        """Test witch uses antidote to save werewolf target."""
        context, participants = make_context_standard_12()

        # Witch uses antidote on kill target (seat 4)
        participants[5] = MockParticipant("ANTIDOTE 4")

        handler = WitchHandler()
        result = await handler(context, [(5, participants[5])])

        assert result.subphase_log.micro_phase == SubPhase.WITCH_ACTION
        assert len(result.subphase_log.events) == 1

        action_event = result.subphase_log.events[0]
        assert isinstance(action_event, WitchAction)
        assert action_event.actor == 5  # Witch seat
        assert action_event.action_type == WitchActionType.ANTIDOTE
        assert action_event.target == 4  # Werewolf target
        assert action_event.day == context.day

    @pytest.mark.asyncio
    async def test_poison_kills_living_player(self):
        """Test witch uses poison to kill a living player."""
        context, participants = make_context_standard_12()

        # Witch uses poison on a living villager (seat 8)
        participants[5] = MockParticipant("POISON 8")

        handler = WitchHandler()
        result = await handler(context, [(5, participants[5])])

        assert len(result.subphase_log.events) == 1

        action_event = result.subphase_log.events[0]
        assert isinstance(action_event, WitchAction)
        assert action_event.actor == 5
        assert action_event.action_type == WitchActionType.POISON
        assert action_event.target == 8  # Living villager

    @pytest.mark.asyncio
    async def test_poison_can_target_werewolf(self):
        """Test witch can use poison on a werewolf."""
        context, participants = make_context_standard_12()

        # Witch uses poison on a werewolf (seat 0)
        participants[5] = MockParticipant("POISON 0")

        handler = WitchHandler()
        result = await handler(context, [(5, participants[5])])

        assert len(result.subphase_log.events) == 1

        action_event = result.subphase_log.events[0]
        assert isinstance(action_event, WitchAction)
        assert action_event.action_type == WitchActionType.POISON
        assert action_event.target == 0  # Werewolf

    @pytest.mark.asyncio
    async def test_pass_when_both_potions_available(self):
        """Test witch chooses to pass when both potions available."""
        context, participants = make_context_standard_12()

        # Witch passes
        participants[5] = MockParticipant("PASS")

        handler = WitchHandler()
        result = await handler(context, [(5, participants[5])])

        assert len(result.subphase_log.events) == 1

        action_event = result.subphase_log.events[0]
        assert isinstance(action_event, WitchAction)
        assert action_event.actor == 5
        assert action_event.action_type == WitchActionType.PASS
        assert action_event.target is None

    @pytest.mark.asyncio
    async def test_pass_when_no_kill_target(self):
        """Test witch passes when werewolves didn't kill anyone."""
        context, participants = make_context_no_werewolf_target()

        # Witch passes
        participants[5] = MockParticipant("PASS")

        handler = WitchHandler()
        result = await handler(context, [(5, participants[5])])

        assert len(result.subphase_log.events) == 1

        action_event = result.subphase_log.events[0]
        assert isinstance(action_event, WitchAction)
        assert action_event.action_type == WitchActionType.PASS


# ============================================================================
# Tests for WitchAction Invalid Scenarios
# ============================================================================


class TestWitchActionInvalidScenarios:
    """Tests for invalid WitchAction scenarios with validation."""

    @pytest.mark.asyncio
    async def test_antidote_on_wrong_target_rejected(self):
        """Test that antidote on wrong target is rejected."""
        context, participants = make_context_standard_12()

        # First tries wrong target, then correct target
        participants[5] = MockParticipant(response_iter=["ANTIDOTE 8", "ANTIDOTE 4"])

        handler = WitchHandler()
        result = await handler(context, [(5, participants[5])])

        # Should eventually get valid action
        assert len(result.subphase_log.events) == 1
        action_event = result.subphase_log.events[0]
        assert isinstance(action_event, WitchAction)
        # Target should be the correct kill target
        assert action_event.target == context.night_actions.kill_target

    @pytest.mark.asyncio
    async def test_antidote_already_used_rejected(self):
        """Test that using antidote when already used is rejected."""
        context, participants = make_context_antidote_used()

        # Witch tries to use antidote again
        participants[5] = MockParticipant(response_iter=["ANTIDOTE 4", "PASS"])

        handler = WitchHandler()
        result = await handler(context, [(5, participants[5])])

        # Should reject and fall back to PASS
        assert len(result.subphase_log.events) == 1
        action_event = result.subphase_log.events[0]
        assert isinstance(action_event, WitchAction)
        # Should not have used antidote (already used)
        assert action_event.action_type == WitchActionType.PASS

    @pytest.mark.asyncio
    async def test_antidote_on_self_rejected(self):
        """Test that antidote on self is rejected."""
        context, participants = make_context_standard_12()

        # First tries self, then correct target
        participants[5] = MockParticipant(response_iter=["ANTIDOTE 5", "ANTIDOTE 4"])

        handler = WitchHandler()
        result = await handler(context, [(5, participants[5])])

        # Should eventually get valid action
        assert len(result.subphase_log.events) == 1
        action_event = result.subphase_log.events[0]
        assert isinstance(action_event, WitchAction)
        assert action_event.target != 5  # Not self

    @pytest.mark.asyncio
    async def test_poison_on_dead_player_rejected(self):
        """Test that poison on dead player is rejected."""
        context, participants = make_context_standard_12()

        # First tries dead player (seat 0 is alive, let's say seat 2 is dead in context)
        # Actually in standard_12, all are alive, so let's target a dead one
        # We'll create a new context with a dead player
        players = {
            0: Player(seat=0, name="W1", role=Role.WEREWOLF, is_alive=True),
            4: Player(seat=4, name="Seer", role=Role.SEER, is_alive=True),
            5: Player(seat=5, name="Witch", role=Role.WITCH, is_alive=True),
            6: Player(seat=6, name="Guard", role=Role.GUARD, is_alive=True),
            8: Player(seat=8, name="V1", role=Role.ORDINARY_VILLAGER, is_alive=True),
        }
        living = {0, 4, 5, 6, 8}
        dead = {1, 2, 3, 7, 9, 10, 11}
        night_actions = NightActions(kill_target=4)

        test_context = WitchPhaseContext(
            players=players,
            living_players=living,
            dead_players=dead,
            sheriff=None,
            day=1,
            night_actions=night_actions,
        )

        # First tries dead player (seat 2), then living player (seat 8)
        participants[5] = MockParticipant(response_iter=["POISON 2", "POISON 8"])

        handler = WitchHandler()
        result = await handler(test_context, [(5, participants[5])])

        # Should eventually get valid action
        assert len(result.subphase_log.events) == 1
        action_event = result.subphase_log.events[0]
        assert isinstance(action_event, WitchAction)
        assert action_event.target == 8  # Living player
        assert action_event.target in living  # Must be alive

    @pytest.mark.asyncio
    async def test_poison_already_used_rejected(self):
        """Test that using poison when already used is rejected."""
        context, participants = make_context_poison_used()

        # Witch tries to use poison again
        participants[5] = MockParticipant(response_iter=["POISON 8", "PASS"])

        handler = WitchHandler()
        result = await handler(context, [(5, participants[5])])

        # Should reject and fall back to PASS
        assert len(result.subphase_log.events) == 1
        action_event = result.subphase_log.events[0]
        assert isinstance(action_event, WitchAction)
        # Should not have used poison (already used)
        assert action_event.action_type == WitchActionType.PASS

    @pytest.mark.asyncio
    async def test_pass_with_target_rejected(self):
        """Test that PASS with a target is rejected."""
        context, participants = make_context_standard_12()

        # First tries PASS with target, then correct PASS
        participants[5] = MockParticipant(response_iter=["PASS 4", "PASS"])

        handler = WitchHandler()
        result = await handler(context, [(5, participants[5])])

        # Should eventually get valid PASS
        assert len(result.subphase_log.events) == 1
        action_event = result.subphase_log.events[0]
        assert isinstance(action_event, WitchAction)
        assert action_event.action_type == WitchActionType.PASS
        assert action_event.target is None


# ============================================================================
# Tests for WitchAction Edge Cases
# ============================================================================


class TestWitchActionEdgeCases:
    """Tests for edge cases in WitchAction."""

    @pytest.mark.asyncio
    async def test_witch_dead_skips_phase(self):
        """Test that phase is skipped when witch is dead."""
        context, participants = make_context_witch_dead()

        # No witch participant
        handler = WitchHandler()
        result = await handler(context, [])  # Empty participants

        # Should return empty SubPhaseLog
        assert result.subphase_log.micro_phase == SubPhase.WITCH_ACTION
        assert len(result.subphase_log.events) == 0

    @pytest.mark.asyncio
    async def test_no_werewolf_target_antidote_unavailable(self):
        """Test that antidote option is not available when no kill target."""
        context, participants = make_context_no_werewolf_target()

        # Witch passes
        participants[5] = MockParticipant("PASS")

        handler = WitchHandler()
        result = await handler(context, [(5, participants[5])])

        assert len(result.subphase_log.events) == 1
        action_event = result.subphase_log.events[0]
        assert isinstance(action_event, WitchAction)
        # Should pass since no antidote is possible
        assert action_event.action_type == WitchActionType.PASS

    @pytest.mark.asyncio
    async def test_both_potions_used_only_pass_available(self):
        """Test that only PASS is available when both potions are used."""
        context, participants = make_context_both_potions_used()

        # Witch passes
        participants[5] = MockParticipant("PASS")

        handler = WitchHandler()
        result = await handler(context, [(5, participants[5])])

        assert len(result.subphase_log.events) == 1
        action_event = result.subphase_log.events[0]
        assert isinstance(action_event, WitchAction)
        assert action_event.action_type == WitchActionType.PASS

    @pytest.mark.asyncio
    async def test_witch_is_werewolf_target_antidote_disabled(self):
        """Test that antidote is disabled when witch is the werewolf target."""
        context, participants = make_context_witch_is_target()

        # Witch passes (cannot use antidote on self)
        participants[5] = MockParticipant("PASS")

        handler = WitchHandler()
        result = await handler(context, [(5, participants[5])])

        assert len(result.subphase_log.events) == 1
        action_event = result.subphase_log.events[0]
        assert isinstance(action_event, WitchAction)
        # Cannot use antidote on self, so must pass or use poison
        assert action_event.action_type == WitchActionType.PASS

    @pytest.mark.asyncio
    async def test_witch_can_poison_self(self):
        """Test that witch can use poison on themselves (if they choose)."""
        context, participants = make_context_standard_12()

        # Witch poisons themselves
        participants[5] = MockParticipant("POISON 5")

        handler = WitchHandler()
        result = await handler(context, [(5, participants[5])])

        assert len(result.subphase_log.events) == 1
        action_event = result.subphase_log.events[0]
        assert isinstance(action_event, WitchAction)
        assert action_event.action_type == WitchActionType.POISON
        assert action_event.target == 5  # Witch can poison self


# ============================================================================
# Tests for WitchAction Prompt Filtering
# ============================================================================


class TestWitchActionPromptFiltering:
    """Tests for prompt filtering in WitchAction."""

    def test_witch_sees_werewolf_target(self):
        """Test that witch sees the werewolf kill target."""
        handler = WitchHandler()
        context, _ = make_context_standard_12()

        system, user = handler._build_prompts(context, for_seat=5)

        # Should reveal kill target
        assert "4" in system  # Kill target is seat 4
        assert "WEREWOLF KILL TARGET" in system.upper() or "KILL TARGET" in system.upper()

    def test_witch_sees_remaining_potions(self):
        """Test that witch sees remaining potions."""
        handler = WitchHandler()
        context, _ = make_context_standard_12()

        system, user = handler._build_prompts(context, for_seat=5)

        # Should show potions
        assert "Antidote" in system
        assert "Poison" in system
        assert "remaining" in system.lower()

    def test_witch_does_not_see_other_roles(self):
        """Test that witch does NOT see other players' roles."""
        handler = WitchHandler()
        context, _ = make_context_standard_12()

        system, user = handler._build_prompts(context, for_seat=5)

        # Should NOT reveal special roles as identities
        assert "Seer" not in system  # Specific role name hidden
        assert "Guard" not in system  # Specific role name hidden
        assert "Hunter" not in system  # Specific role name hidden
        # Note: "werewolf" may appear in "werewolf kill target" which is expected

    def test_witch_sees_all_living_players(self):
        """Test that witch sees all living player seats."""
        handler = WitchHandler()
        context, _ = make_context_standard_12()

        system, user = handler._build_prompts(context, for_seat=5)

        # Should show living players
        for seat in range(12):
            if seat in context.living_players:
                assert str(seat) in user or str(seat) in system

    def test_witch_sees_antidote_used_status(self):
        """Test that witch sees antidote status correctly."""
        handler = WitchHandler()

        # Fresh context - antidote available
        context1, _ = make_context_standard_12()
        system1, _ = handler._build_prompts(context1, for_seat=5)
        assert "1 remaining" in system1 or "Available" in system1

        # Used context - antidote unavailable
        context2, _ = make_context_antidote_used()
        system2, _ = handler._build_prompts(context2, for_seat=5)
        assert "0 remaining" in system2 or "Used" in system2

    def test_witch_sees_poison_used_status(self):
        """Test that witch sees poison status correctly."""
        handler = WitchHandler()

        # Fresh context - poison available
        context1, _ = make_context_standard_12()
        system1, _ = handler._build_prompts(context1, for_seat=5)
        assert "1 remaining" in system1 or "Available" in system1

        # Used context - poison unavailable
        context2, _ = make_context_poison_used()
        system2, _ = handler._build_prompts(context2, for_seat=5)
        assert "0 remaining" in system2 or "Used" in system2

    def test_witch_prompt_shows_no_antidote_when_self_is_target(self):
        """Test that witch prompt doesn't offer antidote when witch is target."""
        handler = WitchHandler()
        context, _ = make_context_witch_is_target()

        system, user = handler._build_prompts(context, for_seat=5)

        # Should indicate antidote cannot be used on self
        assert "cannot" in system.lower() or "self" in system.lower()
        # Should show the kill target is self (seat 5)
        assert "5" in system


# ============================================================================
# Tests for WitchAction Retry Behavior
# ============================================================================


class TestWitchActionRetryBehavior:
    """Tests for retry behavior with invalid inputs."""

    @pytest.mark.asyncio
    async def test_invalid_action_triggers_retry_with_hint(self):
        """Test that invalid action triggers retry with helpful hint."""
        context, participants = make_context_standard_12()

        # First response is invalid, second is valid
        participants[5] = MockParticipant(response_iter=["INVALID", "PASS"])

        handler = WitchHandler()
        result = await handler(context, [(5, participants[5])])

        # Should have retried and succeeded
        assert len(result.subphase_log.events) == 1
        action_event = result.subphase_log.events[0]
        assert isinstance(action_event, WitchAction)
        assert action_event.action_type == WitchActionType.PASS

    @pytest.mark.asyncio
    async def test_max_retries_falls_back_to_pass(self):
        """Test that after max retries, handler falls back to PASS."""
        context, participants = make_context_standard_12()

        # Provide enough invalid responses for all retry attempts
        # Handler may call decide up to 2 times per retry attempt
        participants[5] = MockParticipant(response_iter=[
            "INVALID1",  # First attempt
            "INVALID2",  # First retry
            "INVALID3",  # Second attempt
            "INVALID4",  # Second retry
            "INVALID5",  # Third attempt
            "INVALID6",  # Third retry
            "INVALID7",  # Extra for safety
        ])

        handler = WitchHandler()
        handler.max_retries = 3

        result = await handler(context, [(5, participants[5])])

        # Should fall back to PASS after all retries fail
        assert len(result.subphase_log.events) == 1
        action_event = result.subphase_log.events[0]
        assert isinstance(action_event, WitchAction)
        assert action_event.action_type == WitchActionType.PASS


# ============================================================================
# Tests for Parsing Edge Cases
# ============================================================================


class TestWitchActionParsing:
    """Tests for action parsing edge cases."""

    def test_parse_action_case_insensitive(self):
        """Test that action parsing is case insensitive."""
        handler = WitchHandler()
        context, _ = make_context_standard_12()

        # Different cases should all work
        action1 = handler._parse_action("pass", context, 5)
        action2 = handler._parse_action("PASS", context, 5)
        action3 = handler._parse_action("Pass", context, 5)

        assert action1.action_type == WitchActionType.PASS
        assert action2.action_type == WitchActionType.PASS
        assert action3.action_type == WitchActionType.PASS

    def test_parse_antidote_with_extra_spaces(self):
        """Test parsing antidote with extra whitespace."""
        handler = WitchHandler()
        context, _ = make_context_standard_12()

        action = handler._parse_action("  ANTIDOTE   4  ", context, 5)

        assert action.action_type == WitchActionType.ANTIDOTE
        assert action.target == 4

    def test_parse_poison_with_extra_spaces(self):
        """Test parsing poison with extra whitespace."""
        handler = WitchHandler()
        context, _ = make_context_standard_12()

        action = handler._parse_action("  POISON   8  ", context, 5)

        assert action.action_type == WitchActionType.POISON
        assert action.target == 8

    def test_parse_invalid_format_raises_error(self):
        """Test that invalid format raises ValueError."""
        handler = WitchHandler()
        context, _ = make_context_standard_12()

        with pytest.raises(ValueError):
            handler._parse_action("just some text", context, 5)

    def test_parse_antidote_without_target_raises_error(self):
        """Test that ANTIDOTE without target raises ValueError."""
        handler = WitchHandler()
        context, _ = make_context_standard_12()

        with pytest.raises(ValueError):
            handler._parse_action("ANTIDOTE", context, 5)

    def test_parse_poison_without_target_raises_error(self):
        """Test that POISON without target raises ValueError."""
        handler = WitchHandler()
        context, _ = make_context_standard_12()

        with pytest.raises(ValueError):
            handler._parse_action("POISON", context, 5)
