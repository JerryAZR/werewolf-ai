"""WerewolfGame - main game controller that orchestrates the complete game loop."""

from typing import Optional, Protocol, TYPE_CHECKING

from werewolf.engine import (
    GameState,
    NightActionStore,
    EventCollector,
    NightScheduler,
    DayScheduler,
)
from werewolf.models import Player
from werewolf.events import (
    GameEventLog,
    GameStart,
    GameOver,
    VictoryCondition,
    Phase,
    DeathCause,
)
from werewolf.handlers import Participant

# Import validator for type hints (avoid circular import)
if TYPE_CHECKING:
    from werewolf.engine.validator import GameValidator

# Maximum number of days before game is forced to end (prevent infinite loops)
MAX_GAME_DAYS = 20


class WerewolfGame:
    """Main game controller - runs the complete game loop.

    Game Flow:
        1. Night 1: Werewolf -> Witch -> Guard/Seer -> Resolution
        2. Day 1: Campaign -> OptOut -> SheriffElection -> DeathResolution -> Discussion -> Voting -> VictoryCheck
        3. Night 2: (repeat)
        4. Day 2: (repeat)
        5. ... until victory condition is met
    """

    def __init__(
        self,
        players: dict[int, Player],
        participants: dict[int, Participant],
        seed: Optional[int] = None,
        validator: Optional["GameValidator"] = None,
    ):
        """Initialize the WerewolfGame.

        Args:
            players: Dict mapping seat number (0-11) to Player with role info.
            participants: Dict mapping seat number to Participant (AI or human)
                          who can make decisions.
            seed: Optional random seed for reproducible games. If None, uses
                  natural randomness. Same seed + same participants = identical game.
            validator: Optional validator for runtime rule checking.
                       Pass None or NoOpValidator for production (zero overhead).
        """
        self.players = players
        self.participants = participants
        self._seed = seed
        self._validator = validator

        # Initialize game state
        self._state = GameState(
            players=players,
            living_players=set(players.keys()),
            dead_players=set(),
            sheriff=None,
            day=1,
        )

        # Initialize night action store for first night
        self._night_actions = NightActionStore()

        # Initialize event collector
        self._collector = EventCollector(day=1)

        # Initialize schedulers with optional validator
        self._night_scheduler = NightScheduler(validator=validator)
        self._day_scheduler = DayScheduler(validator=validator)

    async def run(self) -> tuple[GameEventLog, Optional[str]]:
        """Run complete game until victory.

        The game alternates between Night and Day phases:
        - Night: Werewolf action, Witch action, Guard/Seer actions, Death resolution
        - Day: Campaign, OptOut, Sheriff Election, Death resolution, Discussion, Voting

        Victory conditions:
        - Werewolves win if all Gods (Seer, Witch, Guard, Hunter) are dead
          OR all Ordinary Villagers are dead
        - Villagers win if all Werewolves are dead

        Returns:
            Tuple of (event_log, winner) where winner is "WEREWOLF" or "VILLAGER"
            (or None if game ended without a clear winner)
        """
        # Set up the event log
        self._collector.set_player_count(len(self.players))

        # Record game start
        game_start = self._create_game_start()
        self._collector.set_game_start(game_start)

        # Hook: game start
        if self._validator:
            await self._validator.on_game_start(self._state, self._collector)

        winner: Optional[str] = None
        current_day = 1
        night_deaths: dict[int, DeathCause] = {}  # Deaths from previous night

        while current_day <= MAX_GAME_DAYS:
            # Increment day number for this night/day cycle
            # Night N runs when state.day = N, followed by Day N
            self._state.day = current_day

            # Run night phase and get deaths
            self._state, self._night_actions, self._collector, night_deaths = await self._night_scheduler.run_night(
                state=self._state,
                actions=self._night_actions,
                collector=self._collector,
                participants=self.participants,
            )

            # Check if game ended (werewolves killed during night)
            is_over, winner = self._state.is_game_over()
            if is_over:
                break

            # Run day phase (pass deaths from previous night for death resolution)
            self._state, self._collector = await self._day_scheduler.run_day(
                state=self._state,
                collector=self._collector,
                participants=self.participants,
                night_deaths=night_deaths,
            )
            current_day += 1

            # Check if game ended (banishment or werewolves killed)
            is_over, winner = self._state.is_game_over()
            if is_over:
                break

        # If we hit max days, force a winner based on current state
        if winner is None:
            is_over, winner = self._state.is_game_over()
            if not is_over:
                # Fallback: determine winner by current counts
                werewolf_count = self._state.get_werewolf_count()
                god_count = self._state.get_god_count()
                villager_count = self._state.get_ordinary_villager_count()

                werewolves_alive = werewolf_count > 0
                villagers_alive = villager_count > 0
                gods_alive = god_count > 0

                # Check for tie (both victory conditions met)
                villagers_win = not werewolves_alive
                werewolves_win = werewolves_alive and (not gods_alive or not villagers_alive)

                if villagers_win and werewolves_win:
                    # Tie - both conditions met
                    winner = None
                elif werewolves_alive and (not gods_alive or not villagers_alive):
                    winner = "WEREWOLF"
                elif not werewolves_alive:
                    winner = "VILLAGER"
                else:
                    # Still tied after max days - use tie
                    winner = None

        # Create GameOver event
        game_over = self._create_game_over(winner)
        self._collector.set_game_over(game_over)

        # Hook: game over
        if self._validator:
            await self._validator.on_game_over(winner, self._state, self._collector)

        # Return event log and winner (canonical singular form)
        return self._collector.get_event_log(), winner

    def _create_game_start(self) -> GameStart:
        """Create the GameStart event."""
        return GameStart(
            player_count=len(self.players),
            roles_secret={seat: player.role.value for seat, player in self.players.items()},
        )

    def _create_game_over(self, winner: Optional[str]) -> GameOver:
        """Create the GameOver event."""
        condition = self._determine_victory_condition(winner)

        return GameOver(
            winner=winner,
            condition=condition,
            final_turn_count=self._collector.day,
        )

    def _determine_victory_condition(self, winner: Optional[str]) -> VictoryCondition:
        """Determine the victory condition based on the winner and game state."""
        if winner is None:
            # Tie - both victory conditions were met
            return VictoryCondition.TIE

        if winner == "WEREWOLF":
            # Check if werewolves won by killing all gods or all villagers
            werewolf_count = self._state.get_werewolf_count()
            god_count = self._state.get_god_count()
            villager_count = self._state.get_ordinary_villager_count()

            if god_count == 0:
                return VictoryCondition.ALL_GODS_KILLED
            elif villager_count == 0:
                return VictoryCondition.ALL_VILLAGERS_KILLED
            else:
                return VictoryCondition.ALL_WEREWOLVES_KILLED  # Fallback
        elif winner == "VILLAGER":
            return VictoryCondition.ALL_WEREWOLVES_KILLED
        else:
            return VictoryCondition.ALL_WEREWOLVES_KILLED  # Fallback
