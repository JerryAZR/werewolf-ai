"""Werewolf game handlers for subphase execution."""

# Re-export common types from base
from werewolf.handlers.base import (
    HandlerResult,
    SubPhaseLog,
    Participant,
    MaxRetriesExceededError,
)

# Import handlers
from .werewolf_handler import (
    PhaseContext,
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
from .guard_handler import GuardHandler, PhaseContext as GuardPhaseContext
from .seer_handler import SeerHandler, PhaseContext as SeerPhaseContext
from .witch_handler import WitchHandler, PhaseContext as WitchPhaseContext, NightActions, ValidationResult
from .voting_handler import VotingHandler
from .nomination_handler import NominationHandler, PhaseContext as NominationPhaseContext
from .opt_out_handler import OptOutHandler, PhaseContext as OptOutPhaseContext
from .sheriff_election_handler import SheriffElectionHandler, PhaseContext as SheriffElectionPhaseContext
from .night_resolution_handler import NightResolutionHandler, NightActionAccumulator
from .banishment_resolution_handler import BanishmentResolutionHandler

__all__ = [
    # Common types from base
    "HandlerResult",
    "SubPhaseLog",
    "Participant",
    "MaxRetriesExceededError",
    # Werewolf handler
    "PhaseContext",
    "WerewolfHandler",
    # Campaign handler
    "CampaignHandler",
    "CampaignPhaseContext",
    "CAMPAIGN_OPT_OUT",
    # Death resolution handler
    "DeathResolutionHandler",
    "DeathResolutionHandlerResult",
    "DeathResolutionSubPhaseLog",
    "NightOutcomeInput",
    # Discussion handler
    "DiscussionHandler",
    "DiscussionPhaseContext",
    # Guard handler
    "GuardHandler",
    "GuardPhaseContext",
    # Seer handler
    "SeerHandler",
    "SeerPhaseContext",
    # Witch handler
    "WitchHandler",
    "WitchPhaseContext",
    "NightActions",
    "ValidationResult",
    # Voting handler
    "VotingHandler",
    # Nomination handler
    "NominationHandler",
    "NominationPhaseContext",
    # Opt out handler
    "OptOutHandler",
    "OptOutPhaseContext",
    # Sheriff election handler
    "SheriffElectionHandler",
    "SheriffElectionPhaseContext",
    # Night resolution handler
    "NightResolutionHandler",
    "NightActionAccumulator",
    # Banishment resolution handler
    "BanishmentResolutionHandler",
]
