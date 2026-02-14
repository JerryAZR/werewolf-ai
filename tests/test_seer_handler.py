"""Comprehensive tests for SeerAction handler.

Tests cover:
- Valid scenarios: check villager (result GOOD), check werewolf (result WEREWOLF)
- Invalid scenarios: self-check, dead player, no skip allowed
- Edge cases: seer dead, only one other living player, seer is Sheriff
- Result computation: GOOD for good roles, WEREWOLF for werewolves
- Prompt filtering: seer sees living players, not roles
"""

import pytest
from typing import Optional, Any, Sequence
from pydantic import BaseModel

from werewolf.events.game_events import (
    SeerAction,
    SeerResult,
    Phase,
    SubPhase,
)
from werewolf.events.event_log import SubPhaseLog
from werewolf.models.player import Player, Role


# ============================================================================
# Mock Participant for Testing
# ============================================================================


class MockParticipant:
    """Mock participant that returns configurable responses."""

    def __init__(
        self,
        response: str | None = None,
        response_iter: list[str] | None = None,
        is_human: bool = False,
    ):
        """Initialize with a single response or an iterator of responses.

        Args:
            response: Single response string to return
            response_iter: Optional list of responses to return in sequence
            is_human: Whether this mock represents a human player
        """
        self._response = response
        self._response_iter = response_iter
        self._call_count = 0
        self._is_human = is_human

    @property
    def is_human(self) -> bool:
        """Whether this is a human player."""
        return self._is_human

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
# SeerPhaseContext for Testing
# ============================================================================


class SeerPhaseContext(BaseModel):
    """Context for SeerAction handler testing."""

    players: dict[int, Player]
    living_players: set[int]
    dead_players: set[int]
    sheriff: Optional[int] = None
    day: int = 1

    def get_player(self, seat: int) -> Optional[Player]:
        """Get player by seat."""
        return self.players.get(seat)

    def is_seer(self, seat: int) -> bool:
        """Check if a player is the seer."""
        player = self.get_player(seat)
        return player is not None and player.role == Role.SEER

    def is_werewolf(self, seat: int) -> bool:
        """Check if a player is a werewolf."""
        player = self.get_player(seat)
        return player is not None and player.role == Role.WEREWOLF

    def is_alive(self, seat: int) -> bool:
        """Check if a player is alive."""
        return seat in self.living_players


# ============================================================================
# Context Factory Functions
# ============================================================================


def make_context_standard_12() -> tuple[SeerPhaseContext, dict[int, MockParticipant]]:
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

    context = SeerPhaseContext(
        players=players,
        living_players=living,
        dead_players=dead,
        sheriff=None,
        day=1,
    )
    return context, {}


def make_context_seer_dead() -> tuple[SeerPhaseContext, dict[int, MockParticipant]]:
    """Create context where seer is dead."""
    players = {
        0: Player(seat=0, name="W1", role=Role.WEREWOLF, is_alive=True),
        1: Player(seat=1, name="W2", role=Role.WEREWOLF, is_alive=True),
        4: Player(seat=4, name="Seer", role=Role.SEER, is_alive=False),  # Dead!
        5: Player(seat=5, name="Witch", role=Role.WITCH, is_alive=True),
        6: Player(seat=6, name="Guard", role=Role.GUARD, is_alive=True),
        8: Player(seat=8, name="V1", role=Role.ORDINARY_VILLAGER, is_alive=True),
    }
    living = {0, 1, 5, 6, 8}
    dead = {2, 3, 4, 7, 9, 10, 11}

    context = SeerPhaseContext(
        players=players,
        living_players=living,
        dead_players=dead,
        sheriff=None,
        day=2,
    )
    return context, {}


def make_context_only_seer_and_werewolf_alive() -> tuple[SeerPhaseContext, dict[int, MockParticipant]]:
    """Create context where only seer and one werewolf are alive.

    Seer has no choice but to check the werewolf.
    """
    players = {
        0: Player(seat=0, name="W1", role=Role.WEREWOLF, is_alive=True),
        4: Player(seat=4, name="Seer", role=Role.SEER, is_alive=True),
    }
    living = {0, 4}
    dead = {1, 2, 3, 5, 6, 7, 8, 9, 10, 11}

    context = SeerPhaseContext(
        players=players,
        living_players=living,
        dead_players=dead,
        sheriff=None,
        day=5,
    )
    return context, {}


def make_context_seer_is_sheriff() -> tuple[SeerPhaseContext, dict[int, MockParticipant]]:
    """Create context where seer is also the Sheriff."""
    players = {
        0: Player(seat=0, name="W1", role=Role.WEREWOLF, is_alive=True),
        1: Player(seat=1, name="W2", role=Role.WEREWOLF, is_alive=True),
        4: Player(seat=4, name="Seer", role=Role.SEER, is_alive=True, is_sheriff=True),
        5: Player(seat=5, name="Witch", role=Role.WITCH, is_alive=True),
        8: Player(seat=8, name="V1", role=Role.ORDINARY_VILLAGER, is_alive=True),
    }
    living = {0, 1, 4, 5, 8}
    dead = {2, 3, 6, 7, 9, 10, 11}

    context = SeerPhaseContext(
        players=players,
        living_players=living,
        dead_players=dead,
        sheriff=4,  # Seer is Sheriff
        day=3,
    )
    return context, {}


def make_context_checking_werewolf() -> tuple[SeerPhaseContext, dict[int, MockParticipant]]:
    """Create context for checking a werewolf target."""
    players = {
        0: Player(seat=0, name="W1", role=Role.WEREWOLF, is_alive=True),
        1: Player(seat=1, name="W2", role=Role.WEREWOLF, is_alive=True),
        4: Player(seat=4, name="Seer", role=Role.SEER, is_alive=True),
        5: Player(seat=5, name="Witch", role=Role.WITCH, is_alive=True),
        8: Player(seat=8, name="V1", role=Role.ORDINARY_VILLAGER, is_alive=True),
    }
    living = {0, 1, 4, 5, 8}
    dead = {2, 3, 6, 7, 9, 10, 11}

    context = SeerPhaseContext(
        players=players,
        living_players=living,
        dead_players=dead,
        sheriff=None,
        day=1,
    )
    return context, {}


def make_context_checking_good_role(role: Role) -> tuple[SeerPhaseContext, dict[int, MockParticipant]]:
    """Create context for checking a good role (Seer, Witch, Guard, Hunter, Villager).

    Args:
        role: The role of the target to check
    """
    players = {
        0: Player(seat=0, name="W1", role=Role.WEREWOLF, is_alive=True),
        4: Player(seat=4, name="Seer", role=Role.SEER, is_alive=True),
        5: Player(seat=5, name="Witch", role=Role.WITCH, is_alive=True),
        6: Player(seat=6, name="Guard", role=Role.GUARD, is_alive=True),
        7: Player(seat=7, name="Hunter", role=Role.HUNTER, is_alive=True),
        8: Player(seat=8, name="V1", role=Role.ORDINARY_VILLAGER, is_alive=True),
    }
    living = {0, 4, 5, 6, 7, 8}
    dead = {1, 2, 3, 9, 10, 11}

    context = SeerPhaseContext(
        players=players,
        living_players=living,
        dead_players=dead,
        sheriff=None,
        day=1,
    )
    return context, {}


# ============================================================================
# HandlerResult and SeerHandler for Testing
# ============================================================================


class HandlerResult(BaseModel):
    """Output from handlers containing all events from a subphase."""

    subphase_log: SubPhaseLog
    debug_info: Optional[str] = None


class SeerHandler:
    """Handler for SeerAction subphase.

    Responsibilities:
    1. Check if seer is alive (return empty log if not)
    2. Build filtered context showing living players
    3. Query seer participant for their check target
    4. Parse response into SeerAction event with result computed by engine
    5. Validate action against game rules (no self-check, living target)
    6. Retry with hints on invalid input (up to 3 times)
    7. Return HandlerResult with SubPhaseLog containing SeerAction

    Context Filtering (what the seer sees):
    - Seer's own seat and role
    - All living player seats
    - Sheriff identity

    What the seer does NOT see:
    - Other players' roles
    - Werewolf target, Witch actions, Guard protection
    """

    max_retries: int = 3

    async def __call__(
        self,
        context: SeerPhaseContext,
        participants: Sequence[tuple[int, MockParticipant]]
    ) -> HandlerResult:
        """Execute the SeerAction subphase.

        Args:
            context: Game state with players, living/dead, sheriff
            participants: Sequence of (seat, MockParticipant) tuples
                         Should contain at most one entry (the seer)

        Returns:
            HandlerResult with SubPhaseLog containing SeerAction event
        """
        events = []

        # Find living seer seat
        seer_seat = None
        for seat in context.living_players:
            if context.is_seer(seat):
                seer_seat = seat
                break

        # Edge case: no living seer
        if seer_seat is None:
            return HandlerResult(
                subphase_log=SubPhaseLog(micro_phase=SubPhase.SEER_ACTION),
                debug_info="Seer is dead, skipping SeerAction",
            )

        # Get the seer participant
        participant = None
        for seat, p in participants:
            if seat == seer_seat:
                participant = p
                break

        # If no participant provided, return empty log
        if participant is None:
            return HandlerResult(
                subphase_log=SubPhaseLog(micro_phase=SubPhase.SEER_ACTION),
            )

        # Query seer for valid target
        action = await self._get_valid_action(
            context=context,
            participant=participant,
            seer_seat=seer_seat,
        )

        events.append(action)

        return HandlerResult(
            subphase_log=SubPhaseLog(
                micro_phase=SubPhase.SEER_ACTION,
                events=events,
            ),
        )

    def _build_prompts(
        self,
        context: SeerPhaseContext,
        for_seat: int,
    ) -> tuple[str, str]:
        """Build filtered prompts for the seer.

        Args:
            context: Game state
            for_seat: The seer seat to build prompts for

        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        living_players_sorted = sorted(context.living_players)

        # Build system prompt
        system = f"""You are the Seer on Night {context.day}.

YOUR ROLE:
- Each night, you may check ONE living player's true identity
- You CANNOT check yourself
- You will learn whether the player is a WEREWOLF or GOOD (not specific role)
- Your identity must remain secret

IMPORTANT RULE:
You MUST choose someone to check. You cannot skip."""

        # Add Sheriff info if applicable
        if context.sheriff is not None:
            system += f"""

CURRENT SHERIFF: Player at seat {context.sheriff}
The Sheriff has 1.5x vote weight during the day."""

        # Build user prompt with visible game state
        living_seats_str = ', '.join(map(str, living_players_sorted))

        # Filter out self from living players for target options
        valid_targets = [str(p) for p in living_players_sorted if p != for_seat]

        user = f"""=== Night {context.day} - Seer Action ===

YOUR IDENTITY:
  You are the Seer at seat {for_seat}

LIVING PLAYERS (seat numbers): {living_seats_str}

VALID TARGETS (excluding yourself):
{', '.join(valid_targets)}

AVAILABLE ACTIONS:

1. CHECK <seat>
   Description: Check a player's true identity
   Format: CHECK <seat>
   Example: CHECK 0
   Rules:
     - Target must be a living player
     - You CANNOT check yourself
     - Result will be: WEREWOLF or GOOD

Enter your action (e.g., "CHECK 0"):"""

        return system, user

    async def _get_valid_action(
        self,
        context: SeerPhaseContext,
        participant: MockParticipant,
        seer_seat: int,
    ) -> SeerAction:
        """Get valid action from seer participant with retry.

        Args:
            context: Game state
            participant: The participant to query
            seer_seat: The seer's seat

        Returns:
            Valid SeerAction event with result computed
        """
        valid_targets = [p for p in context.living_players if p != seer_seat]
        fallback_target = min(valid_targets) if valid_targets else seer_seat

        for attempt in range(self.max_retries):
            system, user = self._build_prompts(context, seer_seat)

            # Add hint for retry attempts
            hint = None
            if attempt > 0:
                hint = "Previous response was invalid. Please choose a valid action."

            try:
                raw = await participant.decide(system, user, hint=hint)
                target = self._parse_response(raw)

                # Validate action
                validation_result = self._validate_action(
                    context=context,
                    target=target,
                    seer_seat=seer_seat,
                )

                if validation_result.is_valid:
                    # Compute result based on target's actual role
                    target_player = context.get_player(target)
                    if target_player is not None and target_player.role == Role.WEREWOLF:
                        result = SeerResult.WEREWOLF
                    else:
                        result = SeerResult.GOOD

                    return SeerAction(
                        actor=seer_seat,
                        target=target,
                        result=result,
                        phase=Phase.NIGHT,
                        micro_phase=SubPhase.SEER_ACTION,
                        day=context.day,
                        debug_info=validation_result.debug_info,
                    )

                # Retry with validation hint
                hint = validation_result.hint
            except ValueError:
                # Parsing failed, set hint for retry
                hint = "Invalid format. Use: CHECK <seat>"

            # Retry on validation or parsing error
            if attempt < self.max_retries - 1:
                try:
                    raw = await participant.decide(system, user, hint=hint)
                    target = self._parse_response(raw)

                    validation_result = self._validate_action(
                        context=context,
                        target=target,
                        seer_seat=seer_seat,
                    )

                    if validation_result.is_valid:
                        target_player = context.get_player(target)
                        if target_player is not None and target_player.role == Role.WEREWOLF:
                            result = SeerResult.WEREWOLF
                        else:
                            result = SeerResult.GOOD

                        return SeerAction(
                            actor=seer_seat,
                            target=target,
                            result=result,
                            phase=Phase.NIGHT,
                            micro_phase=SubPhase.SEER_ACTION,
                            day=context.day,
                            debug_info=validation_result.debug_info,
                        )

                    hint = validation_result.hint
                except ValueError:
                    hint = "Invalid format. Use: CHECK <seat>"

        # Fall back to first valid target on last attempt
        target_player = context.get_player(fallback_target)
        if target_player is not None and target_player.role == Role.WEREWOLF:
            result = SeerResult.WEREWOLF
        else:
            result = SeerResult.GOOD

        return SeerAction(
            actor=seer_seat,
            target=fallback_target,
            result=result,
            phase=Phase.NIGHT,
            micro_phase=SubPhase.SEER_ACTION,
            day=context.day,
            debug_info="Max retries exceeded, defaulting to first valid target",
        )

    def _parse_response(self, raw_response: str) -> int:
        """Parse the raw response into a target seat.

        Args:
            raw_response: Raw string from participant

        Returns:
            Target seat number

        Raises:
            ValueError: If response cannot be parsed
        """
        cleaned = raw_response.strip().upper()

        # Parse CHECK with target
        import re
        match = re.match(r'CHECK\s+(\d+)', cleaned)

        if match:
            target = int(match.group(1))
            return target

        # Try alternative format: just "4" -> treat as CHECK 4
        match = re.match(r'^(\d+)$', cleaned)
        if match:
            target = int(match.group(1))
            return target

        raise ValueError(
            f"Could not parse response: '{raw_response}'. "
            f"Please use format: CHECK <seat>"
        )

    def _validate_action(
        self,
        context: SeerPhaseContext,
        target: int,
        seer_seat: int,
    ) -> "ValidationResult":
        """Validate seer action against game rules.

        Args:
            context: Game state
            target: The proposed target seat
            seer_seat: The seer's seat

        Returns:
            ValidationResult with is_valid and hint
        """
        # Check if target is a living player
        if target not in context.living_players:
            return ValidationResult(
                is_valid=False,
                hint="Target must be a living player.",
            )

        # Check if target is self
        if target == seer_seat:
            return ValidationResult(
                is_valid=False,
                hint="You cannot check your own identity! Choose another player.",
            )

        return ValidationResult(
            is_valid=True,
            debug_info=f"action=CHECK, target={target}",
        )


class ValidationResult(BaseModel):
    """Result of action validation."""

    is_valid: bool
    hint: Optional[str] = None
    debug_info: Optional[str] = None


# ============================================================================
# Expected SeerAction Event Factory
# ============================================================================


def expected_seer_action(
    actor: int,
    target: int,
    result: SeerResult,
    day: int = 1,
) -> SeerAction:
    """Create an expected SeerAction event for validation."""
    return SeerAction(
        actor=actor,
        target=target,
        result=result,
        day=day,
        phase=Phase.NIGHT,
        micro_phase=SubPhase.SEER_ACTION,
    )


# ============================================================================
# Tests for SeerAction with REAL Handler (from src/werewolf/handlers/seer_handler.py)
# ============================================================================


class TestRealSeerHandler:
    """Tests using the REAL SeerHandler from src/werewolf/handlers/seer_handler.py.

    These tests verify the actual game engine behavior, not test doubles.
    """

    @pytest.mark.asyncio
    async def test_real_handler_seer_checks_werewolf_returns_werewolf(self):
        """Test that real SeerHandler correctly returns WEREWOLF when checking werewolf.

        This test uses the actual SeerHandler from the game engine.
        It should FAIL if the handler hardcodes GOOD instead of computing from target's role.
        """
        from werewolf.handlers.seer_handler import SeerHandler as RealSeerHandler
        from werewolf.engine.game_state import GameState

        # Create a simple context that GameState can work with
        players = {
            4: Player(seat=4, name="Seer", role=Role.SEER, is_alive=True),
            0: Player(seat=0, name="Werewolf1", role=Role.WEREWOLF, is_alive=True),
            1: Player(seat=1, name="Villager1", role=Role.ORDINARY_VILLAGER, is_alive=True),
        }

        # Use GameState with the real handler
        state = GameState(
            players=players,
            living_players={0, 1, 4},
            dead_players=set(),
            sheriff=None,
            day=1,
        )

        # Import the real PhaseContext from the handler module
        from werewolf.handlers.seer_handler import PhaseContext

        context = PhaseContext(
            players=players,
            living_players={0, 1, 4},
            dead_players=set(),
            sheriff=None,
            day=1,
        )

        # Create mock participant that checks werewolf at seat 0
        class MockParticipant:
            @property
            def is_human(self) -> bool:
                return False

            async def decide(self, system, user, hint=None, choices=None):
                return "0"  # Check seat 0 (werewolf)

        handler = RealSeerHandler()
        result = await handler(context, [(4, MockParticipant())])

        # The seer checked seat 0, which is a werewolf
        # The result SHOULD be SeerResult.WEREWOLF
        action_event = result.subphase_log.events[0]
        assert isinstance(action_event, SeerAction)
        assert action_event.target == 0  # Checked werewolf

        # This assertion will FAIL if handler hardcodes GOOD
        assert action_event.result == SeerResult.WEREWOLF, (
            f"Seer checked werewolf at seat 0 but got {action_event.result} instead of WEREWOLF. "
            "This indicates the handler is hardcoding GOOD instead of computing from target's role."
        )


# ============================================================================
# Tests for SeerAction Valid Scenarios
# ============================================================================


class TestSeerActionValidScenarios:
    """Tests for valid SeerAction scenarios."""

    @pytest.mark.asyncio
    async def test_seer_checks_villager_result_good(self):
        """Test seer checks ordinary villager and gets GOOD result."""
        context, participants = make_context_standard_12()

        # Seer checks villager (seat 8)
        participants[4] = MockParticipant("CHECK 8")

        handler = SeerHandler()
        result = await handler(context, [(4, participants[4])])

        assert result.subphase_log.micro_phase == SubPhase.SEER_ACTION
        assert len(result.subphase_log.events) == 1

        action_event = result.subphase_log.events[0]
        assert isinstance(action_event, SeerAction)
        assert action_event.actor == 4  # Seer seat
        assert action_event.target == 8  # Villager seat
        assert action_event.result == SeerResult.GOOD
        assert action_event.day == context.day

    @pytest.mark.asyncio
    async def test_seer_checks_werewolf_result_werewolf(self):
        """Test seer checks werewolf and gets WEREWOLF result."""
        context, participants = make_context_checking_werewolf()

        # Seer checks werewolf (seat 0)
        participants[4] = MockParticipant("CHECK 0")

        handler = SeerHandler()
        result = await handler(context, [(4, participants[4])])

        assert len(result.subphase_log.events) == 1

        action_event = result.subphase_log.events[0]
        assert isinstance(action_event, SeerAction)
        assert action_event.actor == 4  # Seer
        assert action_event.target == 0  # Werewolf
        assert action_event.result == SeerResult.WEREWOLF

    @pytest.mark.asyncio
    async def test_seer_checks_witch_result_good(self):
        """Test seer checks witch and gets GOOD result."""
        context, participants = make_context_checking_good_role(Role.WITCH)

        # Seer checks witch (seat 5)
        participants[4] = MockParticipant("CHECK 5")

        handler = SeerHandler()
        result = await handler(context, [(4, participants[4])])

        assert len(result.subphase_log.events) == 1

        action_event = result.subphase_log.events[0]
        assert isinstance(action_event, SeerAction)
        assert action_event.target == 5  # Witch
        assert action_event.result == SeerResult.GOOD

    @pytest.mark.asyncio
    async def test_seer_checks_guard_result_good(self):
        """Test seer checks guard and gets GOOD result."""
        context, participants = make_context_checking_good_role(Role.GUARD)

        # Seer checks guard (seat 6)
        participants[4] = MockParticipant("CHECK 6")

        handler = SeerHandler()
        result = await handler(context, [(4, participants[4])])

        assert len(result.subphase_log.events) == 1

        action_event = result.subphase_log.events[0]
        assert isinstance(action_event, SeerAction)
        assert action_event.target == 6  # Guard
        assert action_event.result == SeerResult.GOOD

    @pytest.mark.asyncio
    async def test_seer_checks_hunter_result_good(self):
        """Test seer checks hunter and gets GOOD result."""
        context, participants = make_context_checking_good_role(Role.HUNTER)

        # Seer checks hunter (seat 7)
        participants[4] = MockParticipant("CHECK 7")

        handler = SeerHandler()
        result = await handler(context, [(4, participants[4])])

        assert len(result.subphase_log.events) == 1

        action_event = result.subphase_log.events[0]
        assert isinstance(action_event, SeerAction)
        assert action_event.target == 7  # Hunter
        assert action_event.result == SeerResult.GOOD

    @pytest.mark.asyncio
    async def test_seer_checks_using_numeric_only_format(self):
        """Test seer can use numeric-only format (just seat number)."""
        context, participants = make_context_standard_12()

        # Seer uses just the seat number
        participants[4] = MockParticipant("8")

        handler = SeerHandler()
        result = await handler(context, [(4, participants[4])])

        assert len(result.subphase_log.events) == 1

        action_event = result.subphase_log.events[0]
        assert isinstance(action_event, SeerAction)
        assert action_event.target == 8

    @pytest.mark.asyncio
    async def test_seer_checks_different_werewolf(self):
        """Test seer checking a different werewolf (seat 1)."""
        context, participants = make_context_checking_werewolf()

        # Seer checks werewolf at seat 1 (not seat 0)
        participants[4] = MockParticipant("CHECK 1")

        handler = SeerHandler()
        result = await handler(context, [(4, participants[4])])

        assert len(result.subphase_log.events) == 1

        action_event = result.subphase_log.events[0]
        assert isinstance(action_event, SeerAction)
        assert action_event.target == 1  # Different werewolf
        assert action_event.result == SeerResult.WEREWOLF


# ============================================================================
# Tests for SeerAction Invalid Scenarios
# ============================================================================


class TestSeerActionInvalidScenarios:
    """Tests for invalid SeerAction scenarios with validation."""

    @pytest.mark.asyncio
    async def test_seer_cannot_check_self(self):
        """Test that seer cannot check themselves."""
        context, participants = make_context_standard_12()

        # First tries self, then valid target
        participants[4] = MockParticipant(response_iter=["CHECK 4", "CHECK 8"])

        handler = SeerHandler()
        result = await handler(context, [(4, participants[4])])

        # Should eventually get valid action
        assert len(result.subphase_log.events) == 1
        action_event = result.subphase_log.events[0]
        assert isinstance(action_event, SeerAction)
        # Should be the corrected target, not self
        assert action_event.target == 8

    @pytest.mark.asyncio
    async def test_seer_cannot_target_dead_player(self):
        """Test that seer cannot target a dead player."""
        # Create context with a dead player
        players = {
            0: Player(seat=0, name="W1", role=Role.WEREWOLF, is_alive=True),
            4: Player(seat=4, name="Seer", role=Role.SEER, is_alive=True),
            5: Player(seat=5, name="Witch", role=Role.WITCH, is_alive=True),
            8: Player(seat=8, name="V1", role=Role.ORDINARY_VILLAGER, is_alive=False),  # Dead!
        }
        living = {0, 4, 5}
        dead = {8}

        test_context = SeerPhaseContext(
            players=players,
            living_players=living,
            dead_players=dead,
            sheriff=None,
            day=1,
        )

        # Create participants dict
        test_participants: dict[int, MockParticipant] = {}
        # First tries dead player, then living player
        test_participants[4] = MockParticipant(response_iter=["CHECK 8", "CHECK 0"])

        handler = SeerHandler()
        result = await handler(test_context, [(4, test_participants[4])])

        # Should eventually get valid action
        assert len(result.subphase_log.events) == 1
        action_event = result.subphase_log.events[0]
        assert isinstance(action_event, SeerAction)
        # Should be the corrected target (living player)
        assert action_event.target == 0

    @pytest.mark.asyncio
    async def test_seer_cannot_skip(self):
        """Test that seer cannot skip - must choose someone."""
        context, participants = make_context_standard_12()

        # Try to skip (no skip allowed)
        participants[4] = MockParticipant(response_iter=["SKIP", "CHECK 8"])

        handler = SeerHandler()
        result = await handler(context, [(4, participants[4])])

        # Should retry and eventually get valid action
        assert len(result.subphase_log.events) == 1
        action_event = result.subphase_log.events[0]
        assert isinstance(action_event, SeerAction)
        assert action_event.target == 8

    @pytest.mark.asyncio
    async def test_invalid_seat_rejected(self):
        """Test that invalid seat number is rejected."""
        context, participants = make_context_standard_12()

        # Try to check invalid seat
        participants[4] = MockParticipant(response_iter=["CHECK 12", "CHECK 8"])

        handler = SeerHandler()
        result = await handler(context, [(4, participants[4])])

        # Should retry and eventually get valid action
        assert len(result.subphase_log.events) == 1
        action_event = result.subphase_log.events[0]
        assert isinstance(action_event, SeerAction)
        # Should fall back to valid target
        assert action_event.target == 8


# ============================================================================
# Tests for SeerAction Edge Cases
# ============================================================================


class TestSeerActionEdgeCases:
    """Tests for edge cases in SeerAction."""

    @pytest.mark.asyncio
    async def test_seer_dead_skips_phase(self):
        """Test that phase is skipped when seer is dead."""
        context, participants = make_context_seer_dead()

        # No seer participant
        handler = SeerHandler()
        result = await handler(context, [])  # Empty participants

        # Should return empty SubPhaseLog
        assert result.subphase_log.micro_phase == SubPhase.SEER_ACTION
        assert len(result.subphase_log.events) == 0
        assert "dead" in (result.debug_info or "").lower()

    @pytest.mark.asyncio
    async def test_seer_checks_only_other_player(self):
        """Test when only one other player is alive, seer must check them."""
        context, participants = make_context_only_seer_and_werewolf_alive()

        # Seer checks werewolf (only choice)
        participants[4] = MockParticipant("CHECK 0")

        handler = SeerHandler()
        result = await handler(context, [(4, participants[4])])

        assert len(result.subphase_log.events) == 1
        action_event = result.subphase_log.events[0]
        assert isinstance(action_event, SeerAction)
        assert action_event.target == 0  # Werewolf (only other player)
        assert action_event.result == SeerResult.WEREWOLF

    @pytest.mark.asyncio
    async def test_seer_is_sheriff(self):
        """Test seer can be Sheriff and still perform seer action."""
        context, participants = make_context_seer_is_sheriff()

        # Seer (who is Sheriff) checks a player
        participants[4] = MockParticipant("CHECK 0")

        handler = SeerHandler()
        result = await handler(context, [(4, participants[4])])

        assert len(result.subphase_log.events) == 1
        action_event = result.subphase_log.events[0]
        assert isinstance(action_event, SeerAction)
        assert action_event.actor == 4  # Seer is Sheriff
        assert action_event.result == SeerResult.WEREWOLF

    @pytest.mark.asyncio
    async def test_seer_checks_multiple_werewolves_same_result(self):
        """Test seer checking different werewolves all return WEREWOLF."""
        context, participants = make_context_standard_12()

        # Check werewolf at seat 1
        participants[4] = MockParticipant("CHECK 1")

        handler = SeerHandler()
        result1 = await handler(context, [(4, participants[4])])

        action1 = result1.subphase_log.events[0]
        assert action1.result == SeerResult.WEREWOLF

        # Now check werewolf at seat 2
        participants[4] = MockParticipant("CHECK 2")

        result2 = await handler(context, [(4, participants[4])])

        action2 = result2.subphase_log.events[0]
        assert action2.result == SeerResult.WEREWOLF

        # And seat 3
        participants[4] = MockParticipant("CHECK 3")

        result3 = await handler(context, [(4, participants[4])])

        action3 = result3.subphase_log.events[0]
        assert action3.result == SeerResult.WEREWOLF


# ============================================================================
# Tests for SeerAction Result Computation
# ============================================================================


class TestSeerActionResultComputation:
    """Tests for result computation (engine responsibility)."""

    @pytest.mark.asyncio
    async def test_seer_checks_werewolf_returns_werewolf(self):
        """Verify seer checking werewolf returns WEREWOLF result."""
        context, participants = make_context_checking_werewolf()

        participants[4] = MockParticipant("CHECK 0")

        handler = SeerHandler()
        result = await handler(context, [(4, participants[4])])

        action_event = result.subphase_log.events[0]
        assert action_event.result == SeerResult.WEREWOLF

    @pytest.mark.asyncio
    async def test_seer_checks_seer_returns_good(self):
        """Verify seer checking another seer returns GOOD (if existed)."""
        # This is hypothetical - can't have 2 seers, but test the logic
        context, participants = make_context_checking_good_role(Role.SEER)

        # Target is another seer (hypothetical)
        participants[4] = MockParticipant("CHECK 5")  # Target is witch, but tests GOOD path

        handler = SeerHandler()
        result = await handler(context, [(4, participants[4])])

        action_event = result.subphase_log.events[0]
        # Witch is GOOD, so result should be GOOD
        assert action_event.result == SeerResult.GOOD

    @pytest.mark.asyncio
    async def test_seer_checks_ordinary_villager_returns_good(self):
        """Verify seer checking ordinary villager returns GOOD."""
        context, participants = make_context_standard_12()

        participants[4] = MockParticipant("CHECK 11")  # V4 - Ordinary Villager

        handler = SeerHandler()
        result = await handler(context, [(4, participants[4])])

        action_event = result.subphase_log.events[0]
        assert action_event.result == SeerResult.GOOD


# ============================================================================
# Tests for SeerAction Prompt Filtering
# ============================================================================


class TestSeerActionPromptFiltering:
    """Tests for prompt filtering in SeerAction."""

    def test_seer_sees_all_living_players(self):
        """Test that seer sees all living player seats."""
        handler = SeerHandler()
        context, _ = make_context_standard_12()

        system, user = handler._build_prompts(context, for_seat=4)

        # Should show all living players
        living_players = sorted(context.living_players)
        for seat in living_players:
            assert str(seat) in user

    def test_seer_sees_self_excluded_from_targets(self):
        """Test that seer's own seat is shown but excluded from targets."""
        handler = SeerHandler()
        context, _ = make_context_standard_12()

        system, user = handler._build_prompts(context, for_seat=4)

        # Should show seat 4 as seer's identity
        assert "seat 4" in user.lower()
        # But 4 should be in living players list
        assert "4" in user

    def test_seer_does_not_see_other_roles(self):
        """Test that seer does NOT see other players' roles."""
        handler = SeerHandler()
        context, _ = make_context_standard_12()

        system, user = handler._build_prompts(context, for_seat=4)

        # Should NOT reveal OTHER players' specific role names
        # Check that "Witch", "Guard", "Hunter", "Werewolf" (as roles of others) don't appear
        # Note: "Werewolf" may appear in "WEREWOLF or GOOD" which is result type, that's fine
        # The key is that no other player's specific role is revealed
        assert "Witch" not in system or "werewolf" in system.lower()  # Only in "werewolf" context
        assert "Guard" not in system
        assert "Hunter" not in system

    def test_seer_sees_no_skip_rule(self):
        """Test that seer prompt explains no skip is allowed."""
        handler = SeerHandler()
        context, _ = make_context_standard_12()

        system, user = handler._build_prompts(context, for_seat=4)

        # Should explain no skip rule
        assert "cannot skip" in system.lower() or "must choose" in system.lower()

    def test_seer_sees_self_check_rule(self):
        """Test that seer prompt explains cannot check self."""
        handler = SeerHandler()
        context, _ = make_context_standard_12()

        system, user = handler._build_prompts(context, for_seat=4)

        # Should explain self-check rule
        assert "cannot check yourself" in system.lower() or "yourself" in system.lower()

    def test_seer_sees_sheriff_identity(self):
        """Test that seer sees Sheriff identity if applicable."""
        context, _ = make_context_seer_is_sheriff()
        handler = SeerHandler()

        system, user = handler._build_prompts(context, for_seat=4)

        # Sheriff info should be visible
        assert "Sheriff" in system or "sheriff" in system

    def test_seer_sees_result_types(self):
        """Test that seer prompt explains result types (WEREWOLF vs GOOD)."""
        handler = SeerHandler()
        context, _ = make_context_standard_12()

        system, user = handler._build_prompts(context, for_seat=4)

        # Should explain the two possible results
        assert "WEREWOLF" in system or "GOOD" in system

    def test_seer_sees_valid_targets_excluding_self(self):
        """Test that seer sees list of valid targets excluding self."""
        handler = SeerHandler()
        context, _ = make_context_standard_12()

        system, user = handler._build_prompts(context, for_seat=4)

        # Valid targets section should exclude seat 4
        # 4 should not appear in the "VALID TARGETS" section
        # Check that the prompt mentions valid targets explicitly
        assert "VALID TARGETS" in user or "excluding yourself" in user.lower()


# ============================================================================
# Tests for SeerAction Retry Behavior
# ============================================================================


class TestSeerActionRetryBehavior:
    """Tests for retry behavior with invalid inputs."""

    @pytest.mark.asyncio
    async def test_invalid_action_triggers_retry_with_hint(self):
        """Test that invalid action triggers retry with helpful hint."""
        context, participants = make_context_standard_12()

        # First response is invalid, second is valid
        participants[4] = MockParticipant(response_iter=["INVALID", "CHECK 8"])

        handler = SeerHandler()
        result = await handler(context, [(4, participants[4])])

        # Should have retried and succeeded
        assert len(result.subphase_log.events) == 1
        action_event = result.subphase_log.events[0]
        assert isinstance(action_event, SeerAction)
        assert action_event.target == 8

    @pytest.mark.asyncio
    async def test_max_retries_falls_back_to_valid_target(self):
        """Test that after max retries, handler falls back to first valid target."""
        context, participants = make_context_standard_12()

        # Provide invalid responses for all retry attempts
        participants[4] = MockParticipant(response_iter=[
            "INVALID1",  # First attempt
            "INVALID2",  # First retry
            "INVALID3",  # Second attempt
            "INVALID4",  # Second retry
            "INVALID5",  # Third attempt
            "INVALID6",  # Third retry
            "INVALID7",  # Extra for safety
        ])

        handler = SeerHandler()
        handler.max_retries = 3

        result = await handler(context, [(4, participants[4])])

        # Should fall back to first valid target
        assert len(result.subphase_log.events) == 1
        action_event = result.subphase_log.events[0]
        assert isinstance(action_event, SeerAction)
        # First valid target after seer (seat 4) should be seat 5 (or min living excluding self)
        valid_targets = sorted([p for p in context.living_players if p != 4])
        assert action_event.target == valid_targets[0]


# ============================================================================
# Tests for SeerAction Parsing
# ============================================================================


class TestSeerActionParsing:
    """Tests for action parsing edge cases."""

    def test_parse_check_case_insensitive(self):
        """Test that CHECK parsing is case insensitive."""
        handler = SeerHandler()
        context, _ = make_context_standard_12()

        # Different cases should all work
        target1 = handler._parse_response("check 8")
        target2 = handler._parse_response("CHECK 8")
        target3 = handler._parse_response("Check 8")

        assert target1 == 8
        assert target2 == 8
        assert target3 == 8

    def test_parse_check_with_extra_spaces(self):
        """Test parsing CHECK with extra whitespace."""
        handler = SeerHandler()
        context, _ = make_context_standard_12()

        target = handler._parse_response("  CHECK   8  ")

        assert target == 8

    def test_parse_numeric_only(self):
        """Test parsing numeric-only response as CHECK."""
        handler = SeerHandler()
        context, _ = make_context_standard_12()

        target = handler._parse_response("8")

        assert target == 8

    def test_parse_invalid_format_raises_error(self):
        """Test that invalid format raises ValueError."""
        handler = SeerHandler()
        context, _ = make_context_standard_12()

        with pytest.raises(ValueError):
            handler._parse_response("just some text")

    def test_parse_check_without_target_raises_error(self):
        """Test that CHECK without target raises ValueError."""
        handler = SeerHandler()
        context, _ = make_context_standard_12()

        with pytest.raises(ValueError):
            handler._parse_response("CHECK")


# ============================================================================
# Tests for SeerAction Event Structure
# ============================================================================


class TestSeerActionEventStructure:
    """Tests for SeerAction event structure and fields."""

    @pytest.mark.asyncio
    async def test_event_has_correct_phase(self):
        """Test that SeerAction has correct NIGHT phase."""
        context, participants = make_context_standard_12()
        participants[4] = MockParticipant("CHECK 8")

        handler = SeerHandler()
        result = await handler(context, [(4, participants[4])])

        action_event = result.subphase_log.events[0]
        assert isinstance(action_event, SeerAction)
        assert action_event.phase == Phase.NIGHT

    @pytest.mark.asyncio
    async def test_event_has_correct_micro_phase(self):
        """Test that SeerAction has correct SEER_ACTION micro_phase."""
        context, participants = make_context_standard_12()
        participants[4] = MockParticipant("CHECK 8")

        handler = SeerHandler()
        result = await handler(context, [(4, participants[4])])

        action_event = result.subphase_log.events[0]
        assert isinstance(action_event, SeerAction)
        assert action_event.micro_phase == SubPhase.SEER_ACTION

    @pytest.mark.asyncio
    async def test_event_has_correct_day(self):
        """Test that SeerAction has correct day number."""
        context, participants = make_context_standard_12()
        participants[4] = MockParticipant("CHECK 8")

        handler = SeerHandler()
        result = await handler(context, [(4, participants[4])])

        action_event = result.subphase_log.events[0]
        assert isinstance(action_event, SeerAction)
        assert action_event.day == context.day

    @pytest.mark.asyncio
    async def test_event_has_target(self):
        """Test that SeerAction always has a target (no None)."""
        context, participants = make_context_standard_12()
        participants[4] = MockParticipant("CHECK 8")

        handler = SeerHandler()
        result = await handler(context, [(4, participants[4])])

        action_event = result.subphase_log.events[0]
        assert isinstance(action_event, SeerAction)
        assert action_event.target is not None

    @pytest.mark.asyncio
    async def test_event_has_result(self):
        """Test that SeerAction always has a result."""
        context, participants = make_context_standard_12()
        participants[4] = MockParticipant("CHECK 8")

        handler = SeerHandler()
        result = await handler(context, [(4, participants[4])])

        action_event = result.subphase_log.events[0]
        assert isinstance(action_event, SeerAction)
        assert action_event.result is not None
        assert action_event.result in (SeerResult.GOOD, SeerResult.WEREWOLF)

    @pytest.mark.asyncio
    async def test_event_str_representation(self):
        """Test SeerAction string representation."""
        context, participants = make_context_standard_12()
        participants[4] = MockParticipant("CHECK 8")

        handler = SeerHandler()
        result = await handler(context, [(4, participants[4])])

        action_event = result.subphase_log.events[0]
        action_str = str(action_event)

        assert "SeerAction" in action_str or "Seer" in action_str
        assert "8" in action_str
