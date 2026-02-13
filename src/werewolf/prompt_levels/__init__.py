from __future__ import annotations

"""Three-Level Prompt System for Werewolf AI.

Level 1: Static system prompts - role rules that never change during gameplay.
Level 2: Game state context - current game state and event context.
Level 3: Decision prompt - specific question with choices for the current decision.

Usage:
    from werewolf.prompt_levels import (
        get_werewolf_system,  # Level 1
        make_werewolf_context,  # Level 2
        build_werewolf_decision,  # Level 3
        build_full_prompt,
    )
"""

from werewolf.prompt_levels.level1_system import (
    # Night phase
    get_werewolf_system,
    get_witch_system,
    get_guard_system,
    get_seer_system,
    # Day phase
    get_nomination_system,
    get_campaign_opt_out_system,
    get_opt_out_system,
    get_sheriff_election_system,
    get_discussion_system,
    get_voting_system,
    # Death resolution
    get_death_last_words_system,
    get_death_hunter_shoot_system,
    get_death_badge_transfer_system,
    get_banishment_last_words_system,
    get_banishment_hunter_shoot_system,
    get_banishment_badge_transfer_system,
)

from werewolf.prompt_levels.level2_state import (
    # Formatting functions
    format_living_seats,
    format_dead_seats,
    format_sheriff_info,
    get_teammate_seats,
    format_teammate_seats,
    get_valid_targets,
    # Factory functions for Level 3
    make_werewolf_context,
    make_witch_context,
    make_guard_context,
    make_seer_context,
    make_voting_context,
    make_sheriff_election_context,
    make_nomination_context,
    make_campaign_context,
    make_opt_out_context,
    make_discussion_context,
    # Death resolution
    make_death_last_words_context,
    make_death_hunter_shoot_context,
    make_death_badge_transfer_context,
    # Banishment resolution
    make_banishment_last_words_context,
    make_banishment_hunter_shoot_context,
    make_banishment_badge_transfer_context,
    # Backward compatibility alias
    GameStateSummary,
)

from werewolf.prompt_levels.level3_decision import (
    DecisionPrompt,
    Choice,
    build_full_prompt,
    # Decision builders
    build_werewolf_decision,
    build_witch_decision,
    build_guard_decision,
    build_seer_decision,
    build_nomination_decision,
    build_campaign_opt_out_decision,
    build_voting_decision,
    build_sheriff_election_decision,
    build_opt_out_decision,
    build_discussion_decision,
    # Death resolution
    build_death_last_words_decision,
    build_death_hunter_shoot_decision,
    build_death_badge_transfer_decision,
    # Banishment resolution
    build_banishment_last_words_decision,
    build_banishment_hunter_shoot_decision,
    build_banishment_badge_transfer_decision,
)

__all__ = [
    # Level 1 - Static system prompts
    "get_werewolf_system",
    "get_witch_system",
    "get_guard_system",
    "get_seer_system",
    "get_nomination_system",
    "get_campaign_opt_out_system",
    "get_opt_out_system",
    "get_sheriff_election_system",
    "get_discussion_system",
    "get_voting_system",
    "get_death_last_words_system",
    "get_death_hunter_shoot_system",
    "get_death_badge_transfer_system",
    "get_banishment_last_words_system",
    "get_banishment_hunter_shoot_system",
    "get_banishment_badge_transfer_system",
    # Level 2 - Game state formatting
    "format_living_seats",
    "format_dead_seats",
    "format_sheriff_info",
    "get_teammate_seats",
    "format_teammate_seats",
    "get_valid_targets",
    "make_werewolf_context",
    "make_witch_context",
    "make_guard_context",
    "make_seer_context",
    "make_voting_context",
    "make_sheriff_election_context",
    "make_nomination_context",
    "make_campaign_context",
    "make_opt_out_context",
    "make_discussion_context",
    # Death resolution
    "make_death_last_words_context",
    "make_death_hunter_shoot_context",
    "make_death_badge_transfer_context",
    # Banishment resolution
    "make_banishment_last_words_context",
    "make_banishment_hunter_shoot_context",
    "make_banishment_badge_transfer_context",
    "GameStateSummary",  # Backward compatibility alias
    # Level 3 - Decision prompts
    "DecisionPrompt",
    "Choice",
    "build_full_prompt",
    # Decision builders
    "build_werewolf_decision",
    "build_witch_decision",
    "build_guard_decision",
    "build_seer_decision",
    "build_nomination_decision",
    "build_campaign_opt_out_decision",
    "build_voting_decision",
    "build_sheriff_election_decision",
    "build_opt_out_decision",
    "build_discussion_decision",
    # Death resolution
    "build_death_last_words_decision",
    "build_death_hunter_shoot_decision",
    "build_death_badge_transfer_decision",
    # Banishment resolution
    "build_banishment_last_words_decision",
    "build_banishment_hunter_shoot_decision",
    "build_banishment_badge_transfer_decision",
]
