"""Game state management for the Werewolf game."""

from typing import Optional
from pydantic import BaseModel

from werewolf.models.player import Player, Role
from werewolf.events.game_events import GameEvent, DeathEvent, DeathCause


class GameState(BaseModel):
    """Represents the current state of the game.

    Manages player states, living/dead tracking, and victory conditions.
    """

    players: dict[int, Player]  # seat -> Player
    living_players: set[int]  # seats of living players
    dead_players: set[int]  # seats of dead players
    sheriff: Optional[int] = None  # seat number of sheriff
    day: int = 1  # current day number

    def apply_events(self, events: list[GameEvent]) -> None:
        """Apply a list of game events to update the game state.

        Only processes DeathEvent to update living/dead players.
        """
        for event in events:
            if isinstance(event, DeathEvent):
                self._apply_death_event(event)

    def _apply_death_event(self, event: DeathEvent) -> None:
        """Apply a single death event to update player states."""
        dead_seat = event.actor

        # Mark player as dead in the players dict
        if dead_seat in self.players:
            self.players[dead_seat].is_alive = False

        # Update living/dead sets
        if dead_seat in self.living_players:
            self.living_players.remove(dead_seat)
            self.dead_players.add(dead_seat)

        # Handle sheriff badge transfer
        if event.badge_transfer_to is not None:
            self.sheriff = event.badge_transfer_to
            if event.badge_transfer_to in self.players:
                self.players[event.badge_transfer_to].is_sheriff = True

        # Handle hunter's final shot (death chain)
        if event.hunter_shoot_target is not None:
            self._apply_hunter_shot(event.hunter_shoot_target)

    def _apply_hunter_shot(self, target_seat: int) -> None:
        """Apply hunter's final shot, potentially causing another death."""
        if target_seat in self.living_players and target_seat in self.players:
            self.players[target_seat].is_alive = False
            self.living_players.remove(target_seat)
            self.dead_players.add(target_seat)

    def apply_events_from_deaths(self, deaths: dict[int, DeathCause]) -> None:
        """Apply deaths from a deaths dict to update player states.

        Args:
            deaths: Dict mapping seat -> DeathCause
        """
        for seat in deaths.keys():
            if seat in self.players:
                self.players[seat].is_alive = False
            if seat in self.living_players:
                self.living_players.remove(seat)
                self.dead_players.add(seat)

    def is_game_over(self) -> tuple[bool, Optional[str]]:
        """Check if the game has ended and return the winner.

        Returns:
            tuple: (is_game_over, winner) where winner is "VILLAGER", "WEREWOLF", or None for tie
        """
        werewolf_count = self.get_role_count(Role.WEREWOLF)
        god_count = self.get_god_count()
        villager_count = self.get_ordinary_villager_count()

        werewolves_alive = werewolf_count > 0
        villagers_alive = villager_count > 0
        gods_alive = god_count > 0

        # Check each victory condition independently
        # - Villager victory condition: ALL_WEREWOLVES_KILLED
        # - Werewolf victory condition: ALL_GODS_KILLED OR ALL_VILLAGERS_KILLED
        werewolves_eliminated = not werewolves_alive
        villagers_eliminated = not villagers_alive
        gods_eliminated = not gods_alive

        # Werewolf wins if all villagers OR all gods are dead
        werewolf_condition_met = villagers_eliminated or gods_eliminated
        # Villager wins if all werewolves are dead
        villager_condition_met = werewolves_eliminated

        # A.5: Tie when BOTH conditions are met simultaneously
        if villager_condition_met and werewolf_condition_met:
            return True, None

        # Normal victory conditions
        if werewolf_condition_met:
            return True, "WEREWOLF"

        if villager_condition_met:
            return True, "VILLAGER"

        return False, None

    def get_role_count(self, role: Role) -> int:
        """Get count of living players with a specific role."""
        count = 0
        for seat in self.living_players:
            player = self.players.get(seat)
            if player and player.role == role:
                count += 1
        return count

    def get_god_count(self) -> int:
        """Get count of living god roles (Seer, Witch, Guard, Hunter)."""
        god_roles = {Role.SEER, Role.WITCH, Role.GUARD, Role.HUNTER}
        count = 0
        for seat in self.living_players:
            player = self.players.get(seat)
            if player and player.role in god_roles:
                count += 1
        return count

    def get_ordinary_villager_count(self) -> int:
        """Get count of living ordinary villagers."""
        return self.get_role_count(Role.ORDINARY_VILLAGER)

    def get_werewolf_count(self) -> int:
        """Get count of living werewolves."""
        return self.get_role_count(Role.WEREWOLF)

    def get_player(self, seat: int) -> Optional[Player]:
        """Get player by seat number.

        Args:
            seat: The player's seat number (0-11)

        Returns:
            Player if found, None otherwise
        """
        return self.players.get(seat)

    def is_alive(self, seat: int) -> bool:
        """Check if a player is alive.

        Args:
            seat: The player's seat number

        Returns:
            True if player is alive, False otherwise
        """
        return seat in self.living_players

    def is_werewolf(self, seat: int) -> bool:
        """Check if a player is a werewolf.

        Args:
            seat: The player's seat number

        Returns:
            True if player is a werewolf, False otherwise
        """
        player = self.players.get(seat)
        return player is not None and player.role == Role.WEREWOLF

    def get_sheriff(self) -> Optional[int]:
        """Get the current sheriff's seat number.

        Returns:
            Sheriff's seat number or None if no sheriff
        """
        return self.sheriff

    def is_sheriff(self, seat: int) -> bool:
        """Check if a player is the sheriff.

        Args:
            seat: The player's seat number

        Returns:
            True if player is sheriff, False otherwise
        """
        return self.sheriff == seat
