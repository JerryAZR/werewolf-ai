"""Werewolf game handlers for subphase execution."""

from .werewolf_handler import (
    PhaseContext,
    HandlerResult,
    SubPhaseLog,
    Participant,
    WerewolfHandler,
)
from .campaign_handler import (
    CampaignHandler,
    PhaseContext as CampaignPhaseContext,
    CAMPAIGN_OPT_OUT,
)
from .death_resolution_handler import (
    DeathResolutionHandler,
    HandlerResult as DeathResolutionHandlerResult,
    SubPhaseLog as DeathResolutionSubPhaseLog,
    NightOutcomeInput,
)
from .discussion_handler import (
    DiscussionHandler,
    PhaseContext as DiscussionPhaseContext,
)

__all__ = [
    "PhaseContext",
    "HandlerResult",
    "SubPhaseLog",
    "Participant",
    "WerewolfHandler",
    "CampaignHandler",
    "CampaignPhaseContext",
    "CAMPAIGN_OPT_OUT",
    "DeathResolutionHandler",
    "DeathResolutionHandlerResult",
    "DeathResolutionSubPhaseLog",
    "NightOutcomeInput",
    "DiscussionHandler",
    "DiscussionPhaseContext",
]
