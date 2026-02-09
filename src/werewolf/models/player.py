"""Player and Role models."""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict


class Role(str, Enum):
    """Player roles in the game."""

    WEREWOLF = "WEREWOLF"
    VILLAGER = "VILLAGER"
    ORDINARY_VILLAGER = "ORDINARY_VILLAGER"
    SEER = "SEER"
    WITCH = "WITCH"
    HUNTER = "HUNTER"
    GUARD = "GUARD"


class RoleGroup(str, Enum):
    """Role groups for victory conditions."""

    WEREWOLF = "WEREWOLF"
    GOD = "GOD"  # Seer, Witch, Guard, Hunter
    VILLAGER = "VILLAGER"  # Ordinary Villager


class PlayerType(str, Enum):
    """Type of player (AI or Human)."""

    AI = "AI"
    HUMAN = "HUMAN"


class Player(BaseModel):
    """Represents a player in the game.

    Uses seat (int) as primary identifier for internal use.
    Name is stored for display purposes.
    """

    seat: int  # 0-11, primary identifier and seat order
    name: str
    role: Role
    player_type: PlayerType = PlayerType.AI
    is_alive: bool = True
    is_sheriff: bool = False
    is_candidate: bool = False  # Sheriff election candidate
    has_opted_out: bool = False  # Sheriff election opt-out

    def to_dict(self) -> dict:
        """Convert to dictionary, hiding secret info."""
        return {
            "seat": self.seat,
            "name": self.name,
            "role": self.role.value,
            "player_type": self.player_type.value,
            "is_alive": self.is_alive,
            "is_sheriff": self.is_sheriff,
        }


class PlayerSecret(BaseModel):
    """Secret information revealed to specific roles."""

    seat: int
    role: Role


class RoleConfig(BaseModel):
    """Role configuration for game setup."""

    role: Role
    count: int = 0
    description: str = ""

    model_config = ConfigDict(use_enum_values=True)


# Standard 12-player game configuration
STANDARD_12_PLAYER_CONFIG = [
    RoleConfig(role=Role.WEREWOLF, count=4, description="Kill all villagers to win"),
    RoleConfig(role=Role.SEER, count=1, description="Check player's identity each night"),
    RoleConfig(role=Role.WITCH, count=1, description="One antidote, one poison"),
    RoleConfig(role=Role.GUARD, count=1, description="Protect one player each night"),
    RoleConfig(role=Role.HUNTER, count=1, description="Shoot someone when you die"),
    RoleConfig(role=Role.ORDINARY_VILLAGER, count=4, description="Help villagers find werewolves"),
]
