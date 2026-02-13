from __future__ import annotations

"""Level 2: Game State Formatting Functions.

This module provides formatting helpers for game state that changes each subphase.
Functions work with existing PhaseContext from handlers.

Formatting functions:
- format_living_seats(context): Format living player seats
- format_dead_seats(context): Format dead player seats
- format_sheriff_info(context): Format sheriff info
- get_teammate_seats(context, your_seat): Get werewolf teammate seats
"""

from typing import TYPE_CHECKING, Optional

from werewolf.models.player import Role


# =============================================================================
# Formatting functions for PhaseContext
# =============================================================================

def format_living_seats(context: "PhaseContext") -> str:
    """Format living seats as comma-separated string.

    Args:
        context: The phase context

    Returns:
        Formatted string of living seats
    """
    if not context.living_players:
        return "None"
    return ", ".join(map(str, sorted(context.living_players)))


def format_dead_seats(context: "PhaseContext") -> str:
    """Format dead seats as comma-separated string.

    Args:
        context: The phase context

    Returns:
        Formatted string of dead seats
    """
    if not context.dead_players:
        return "none"
    return ", ".join(map(str, sorted(context.dead_players)))


def format_sheriff_info(context: "PhaseContext") -> str:
    """Format sheriff info for display.

    Args:
        context: The phase context

    Returns:
        Formatted sheriff info string
    """
    if context.sheriff is not None:
        return f"\nSheriff: Player at seat {context.sheriff}"
    return ""


def get_teammate_seats(context: "PhaseContext", your_seat: int) -> list[int]:
    """Get werewolf teammate seats.

    Args:
        context: The phase context
        your_seat: The current player's seat

    Returns:
        List of teammate seat numbers
    """
    return [
        seat for seat in context.living_players
        if context.is_werewolf(seat) and seat != your_seat
    ]


def format_teammate_seats(context: "PhaseContext", your_seat: int) -> str:
    """Format teammate seats for werewolf.

    Args:
        context: The phase context
        your_seat: The current player's seat

    Returns:
        Formatted teammate seats string
    """
    teammates = get_teammate_seats(context, your_seat)
    if not teammates:
        return "none (you are alone)"
    return ", ".join(map(str, teammates))


def get_valid_targets(
    context: "PhaseContext",
    your_seat: int,
    exclude_teammates: bool = True,
) -> list[int]:
    """Get valid target seats for werewolf.

    Args:
        context: The phase context
        your_seat: The current player's seat
        exclude_teammates: Whether to exclude werewolf teammates

    Returns:
        List of valid target seat numbers
    """
    targets = []
    for seat in sorted(context.living_players):
        if seat == your_seat:
            continue
        if exclude_teammates and context.is_werewolf(seat):
            continue
        targets.append(seat)
    return targets


# =============================================================================
# Factory functions for Level 3 context
# =============================================================================

def make_werewolf_context(
    context: "PhaseContext",
    your_seat: int,
) -> dict:
    """Create Level 2 context for werewolf decision.

    Args:
        context: The phase context from handlers
        your_seat: The werewolf's seat

    Returns:
        Dict with game state formatted for werewolf prompts
    """
    teammates = get_teammate_seats(context, your_seat)
    return {
        "phase": "NIGHT",
        "day": context.day,
        "your_seat": your_seat,
        "living_seats": format_living_seats(context),
        "dead_seats": format_dead_seats(context),
        "teammate_seats": teammates,
        "teammate_seats_formatted": format_teammate_seats(context, your_seat),
        "sheriff_info": format_sheriff_info(context),
        "valid_targets": get_valid_targets(context, your_seat),
    }


def make_witch_context(
    context: "PhaseContext",
    your_seat: int,
    antidote_available: bool = True,
    poison_available: bool = True,
    werewolf_kill_target: Optional[int] = None,
) -> dict:
    """Create Level 2 context for witch decision.

    Args:
        context: The phase context from handlers
        your_seat: The witch's seat
        antidote_available: Whether antidote is available
        poison_available: Whether poison is available
        werewolf_kill_target: The werewolf kill target

    Returns:
        Dict with game state formatted for witch prompts
    """
    return {
        "phase": "NIGHT",
        "day": context.day,
        "your_seat": your_seat,
        "living_seats": format_living_seats(context),
        "dead_seats": format_dead_seats(context),
        "sheriff_info": format_sheriff_info(context),
        "antidote_available": antidote_available,
        "poison_available": poison_available,
        "werewolf_kill_target": werewolf_kill_target,
        "antidote_display": "Available (1 remaining)" if antidote_available else "Used (0 remaining)",
        "poison_display": "Available (1 remaining)" if poison_available else "Used (0 remaining)",
    }


def make_guard_context(
    context: "PhaseContext",
    your_seat: int,
    guard_prev_target: Optional[int] = None,
) -> dict:
    """Create Level 2 context for guard decision.

    Args:
        context: The phase context from handlers
        your_seat: The guard's seat
        guard_prev_target: Previous night's guard target

    Returns:
        Dict with game state formatted for guard prompts
    """
    living_sorted = sorted(context.living_players)
    valid_targets = [s for s in living_sorted if s != guard_prev_target]

    return {
        "phase": "NIGHT",
        "day": context.day,
        "your_seat": your_seat,
        "living_seats": format_living_seats(context),
        "dead_seats": format_dead_seats(context),
        "sheriff_info": format_sheriff_info(context),
        "guard_prev_target": guard_prev_target,
        "prev_guard_info": (
            f"\nNOTE: You protected seat {guard_prev_target} last night (cannot protect again)."
            if guard_prev_target is not None else ""
        ),
        "valid_targets": valid_targets,
    }


def make_seer_context(
    context: "PhaseContext",
    your_seat: int,
    seer_checks: set[int] | None = None,
) -> dict:
    """Create Level 2 context for seer decision.

    Args:
        context: The phase context from handlers
        your_seat: The seer's seat
        seer_checks: Set of seats already checked by the seer (to exclude)

    Returns:
        Dict with game state formatted for seer prompts
    """
    living_sorted = sorted(context.living_players)
    # Seer cannot check themselves
    valid_targets = [s for s in living_sorted if s != your_seat]
    # Filter out already checked players - no point rechecking them
    if seer_checks:
        valid_targets = [s for s in valid_targets if s not in seer_checks]

    return {
        "phase": "NIGHT",
        "day": context.day,
        "your_seat": your_seat,
        "living_seats": format_living_seats(context),
        "dead_seats": format_dead_seats(context),
        "sheriff_info": format_sheriff_info(context),
        "valid_targets": valid_targets,
        # Include unchecked targets for filtering in choices
        "unchecked_targets": valid_targets,
    }


def make_voting_context(
    context: "PhaseContext",
    your_seat: int,
) -> dict:
    """Create Level 2 context for voting decision.

    Args:
        context: The phase context from handlers
        your_seat: The voter's seat

    Returns:
        Dict with game state formatted for voting prompts
    """
    living_sorted = sorted(context.living_players)

    return {
        "phase": "DAY",
        "day": context.day,
        "your_seat": your_seat,
        "living_seats": format_living_seats(context),
        "dead_seats": format_dead_seats(context),
        "sheriff_info": format_sheriff_info(context),
        "is_sheriff": context.sheriff == your_seat,
        "vote_weight": 1.5 if context.sheriff == your_seat else 1.0,
        "valid_targets": living_sorted,
    }


def make_sheriff_election_context(
    context: "PhaseContext",
    your_seat: int,
    candidates: list[int],
) -> dict:
    """Create Level 2 context for sheriff election.

    Args:
        context: The phase context from handlers
        your_seat: The voter's seat
        candidates: List of candidate seats

    Returns:
        Dict with game state formatted for sheriff election prompts
    """
    return {
        "phase": "DAY",
        "day": context.day,
        "your_seat": your_seat,
        "living_seats": format_living_seats(context),
        "dead_seats": format_dead_seats(context),
        "sheriff_info": format_sheriff_info(context),
        "candidates": candidates,
        "is_sheriff": context.sheriff == your_seat,
        "vote_weight": 1.5 if context.sheriff == your_seat else 1.0,
    }


def make_nomination_context(
    context: "PhaseContext",
    your_seat: int,
) -> dict:
    """Create Level 2 context for nomination decision.

    Args:
        context: The phase context from handlers
        your_seat: The player's seat

    Returns:
        Dict with game state formatted for nomination prompts
    """
    player = context.get_player(your_seat)
    role_name = player.role.value if player else "Unknown"
    is_alive = context.is_alive(your_seat)

    return {
        "phase": "DAY",
        "day": context.day,
        "your_seat": your_seat,
        "role": role_name,
        "is_alive": is_alive,
        "status": "Living" if is_alive else "Dead",
        "living_seats": format_living_seats(context),
        "dead_seats": format_dead_seats(context),
        "sheriff_info": format_sheriff_info(context),
    }


def make_campaign_context(
    context: "PhaseContext",
    your_seat: int,
    candidates: list[int],
) -> dict:
    """Create Level 2 context for campaign stay/opt-out decision.

    Args:
        context: The phase context from handlers
        your_seat: The candidate's seat
        candidates: List of all candidate seats (ordered)

    Returns:
        Dict with game state formatted for campaign opt-out prompts
    """
    other_candidates = [c for c in candidates if c != your_seat and context.is_alive(c)]
    other_candidates_str = ', '.join(map(str, sorted(other_candidates))) if other_candidates else "None"

    return {
        "phase": "DAY",
        "day": context.day,
        "your_seat": your_seat,
        "candidates": candidates,
        "other_candidates": other_candidates,
        "other_candidates_str": other_candidates_str,
        "is_only_candidate": len(candidates) == 1 and candidates[0] == your_seat,
        "living_players": sorted(context.living_players),
        "dead_players": sorted(context.dead_players),
    }


def make_opt_out_context(
    context: "PhaseContext",
    your_seat: int,
) -> dict:
    """Create Level 2 context for opt-out decision.

    Args:
        context: The phase context from handlers
        your_seat: The candidate's seat

    Returns:
        Dict with game state formatted for opt-out prompts
    """
    other_candidates = [
        seat for seat in context.sheriff_candidates
        if seat != your_seat and context.is_alive(seat)
    ]

    return {
        "phase": "DAY",
        "day": context.day,
        "your_seat": your_seat,
        "other_candidates": other_candidates,
        "other_candidates_str": ', '.join(map(str, other_candidates)) if other_candidates else 'none',
        "is_only_candidate": len(other_candidates) == 0,
    }


def make_discussion_context(
    context: "PhaseContext",
    your_seat: int,
    speaking_order: list[int],
    # Private history - per role specific
    seer_checks: list[tuple[int, str, int]] | None = None,  # [(target, result, day), ...]
    guard_prev_target: int | None = None,  # Last night's guard target
    witch_potions: dict[str, int | None] | None = None,  # {"antidote": seat|None, "poison": seat|None}
) -> dict:
    """Create Level 2 context for discussion speech.

    Args:
        context: The phase context from handlers
        your_seat: The speaker's seat
        speaking_order: List of all speakers in order
        seer_checks: List of past seer checks [(target, result, day)]
        guard_prev_target: Guard's target from last night
        witch_potions: Dict of witch potion usage {"antidote": seat, "poison": seat}

    Returns:
        Dict with game state formatted for discussion prompts
    """
    player = context.get_player(your_seat)
    role_name = player.role.value if player else "Unknown"

    position = speaking_order.index(your_seat) + 1
    total = len(speaking_order)

    sheriff_info = ""
    if context.sheriff is not None:
        if context.sheriff == your_seat:
            sheriff_info = "You ARE the Sheriff (speaks LAST)"
        else:
            sheriff_info = f"Seat {context.sheriff} is the Sheriff (speaks LAST)"

    # Count werewolves for strategy guidance
    werewolf_count = sum(1 for seat in context.living_players if context.is_werewolf(seat))
    living_count = len(context.living_players)
    dead_count = len(context.dead_players)

    # Build private info for each role
    private_info = _build_discussion_private_info(
        role=player.role if player else None,
        your_seat=your_seat,
        seer_checks=seer_checks,
        guard_prev_target=guard_prev_target,
        witch_potions=witch_potions,
        living_count=living_count,
        dead_count=dead_count,
        werewolf_count=werewolf_count,
    )

    return {
        "phase": "DAY",
        "day": context.day,
        "your_seat": your_seat,
        "role": role_name,
        "living_seats": format_living_seats(context),
        "dead_seats": format_dead_seats(context),
        "speaking_order": speaking_order,
        "position": position,
        "total": total,
        "sheriff_info": sheriff_info,
        "is_sheriff": context.sheriff == your_seat,
        "private_info": private_info,
    }


def _build_discussion_private_info(
    role: "Role" | None,
    your_seat: int,
    seer_checks: list[tuple[int, str, int]] | None = None,
    guard_prev_target: int | None = None,
    witch_potions: dict[str, int | None] | None = None,
    living_count: int = 0,
    dead_count: int = 0,
    werewolf_count: int = 0,
) -> str:
    """Build per-role private info section for discussion prompt.

    Args:
        role: Your role
        your_seat: Your seat number
        seer_checks: List of past seer checks [(target, result, day)]
        guard_prev_target: Guard's target from last night
        witch_potions: Dict of witch potion usage
        living_count: Number of living players
        dead_count: Number of dead players
        werewolf_count: Number of living werewolves

    Returns:
        Formatted private info string with strategy guidance
    """
    if role is None:
        return ""

    info_parts = []

    # Strategy guidance based on role
    info_parts.append(_get_role_strategy(role, living_count, dead_count, werewolf_count, witch_potions))

    # Private history based on role
    if role == Role.SEER and seer_checks:
        info_parts.append("\nYOUR SEER CHECKS:")
        for target, result, day in seer_checks:
            marker = " (last night)" if day == seer_checks[-1][2] else ""
            info_parts.append(f"  Night {day}: Seat {target} = {result}{marker}")

    elif role == Role.GUARD and guard_prev_target is not None:
        info_parts.append(f"\nLAST NIGHT: You protected seat {guard_prev_target}")

    elif role == Role.WITCH and witch_potions:
        info_parts.append("\nYOUR POTIONS:")
        if witch_potions.get("antidote") is not None:
            info_parts.append(f"  Antidote: Used on seat {witch_potions['antidote']}")
        else:
            info_parts.append("  Antidote: Available (1 remaining)")
        if witch_potions.get("poison") is not None:
            info_parts.append(f"  Poison: Used on seat {witch_potions['poison']}")
        else:
            info_parts.append("  Poison: Available (1 remaining)")

    return "\n".join(info_parts)


def _get_role_strategy(
    role: Role,
    living_count: int,
    dead_count: int,
    werewolf_count: int,
    witch_potions: dict[str, int | None] | None = None,
) -> str:
    """Get strategy guidance based on role and game state.

    Args:
        role: Your role
        living_count: Number of living players
        dead_count: Number of dead players
        werewolf_count: Number of living werewolves
        witch_potions: Dict of witch potion usage (only for witch role)

    Returns:
        Formatted strategy guidance string
    """
    strategies = []

    if role == Role.WEREWOLF:
        strategies.append("STRATEGY (WEREWOLF):")
        strategies.append("  - Coordinate with fellow werewolves to kill key good roles")
        strategies.append("  - Keep your identity hidden as long as possible")
        strategies.append("  - Blend in with ordinary villagers or claim god roles with convincing evidence")
        strategies.append("  - Vote strategically to eliminate confirmed goods")
        if living_count <= 7:
            strategies.append("  - Late game: push for kills when numbers favor werewolves")

    elif role == Role.SEER:
        strategies.append("STRATEGY (SEER):")
        strategies.append("  - Reveal strategically when you have concrete evidence")
        strategies.append("  - Share findings to gain trust from villagers")
        strategies.append("  - Consider hiding info if revealing would get you killed")
        if werewolf_count == 1:
            strategies.append("  - Only 1 werewolf left! Push for conviction.")
        elif werewolf_count == 0:
            strategies.append("  - All werewolves eliminated - victory secured!")

    elif role == Role.WITCH:
        strategies.append("STRATEGY (WITCH):")
        strategies.append("  - Save the antidote for critical moments (don't waste it)")
        strategies.append("  - Use poison strategically to eliminate threats")
        strategies.append("  - Your identity is powerful - reveal carefully")
        if witch_potions is not None and (witch_potions.get("antidote") is None or witch_potions.get("poison") is None):
            strategies.append("  - You still have potions - plan their use")

    elif role == Role.GUARD:
        strategies.append("STRATEGY (GUARD):")
        strategies.append("  - Protect key roles (Seer, Witch) from werewolf kills")
        strategies.append("  - Alternate targets to avoid werewolf predictions")
        strategies.append("  - Your guarding pattern matters - stay unpredictable")
        strategies.append("  - Communicate protection status subtly if needed")

    elif role == Role.HUNTER:
        strategies.append("STRATEGY (HUNTER):")
        strategies.append("  - Your final shot is powerful - save it for a werewolf")
        strategies.append("  - Act confident to avoid suspicion")
        strategies.append("  - If voted out, choose your target wisely")
        strategies.append("  - Blend in while gathering information")

    else:  # Ordinary Villager
        strategies.append("STRATEGY (VILLAGER):")
        strategies.append("  - Analyze speeches for inconsistencies")
        strategies.append("  - Trust confirmed information from Seer/Witch")
        strategies.append("  - Vote to eliminate suspected werewolves")
        strategies.append("  - Stay alert for role claims and verify them")

    return "\n".join(strategies)


def make_death_last_words_context(
    context: "PhaseContext",
    your_seat: int,
    death_day: int,
    death_context: str,
) -> dict:
    """Create Level 2 context for death last words.

    Args:
        context: The phase context from handlers
        your_seat: The dying player's seat
        death_day: The day of death
        death_context: Description of how the player died

    Returns:
        Dict with game state formatted for last words prompts
    """
    player = context.get_player(your_seat)
    role_name = player.role.name.replace("_", " ").title() if player else "Unknown"

    living_seats = sorted(context.living_players - {your_seat})
    dead_seats = sorted(context.dead_players)

    return {
        "phase": "NIGHT" if death_day == 1 else "DAY",
        "day": death_day,
        "your_seat": your_seat,
        "role": role_name,
        "death_context": death_context,
        "living_seats": ", ".join(map(str, living_seats)) if living_seats else "None",
        "dead_seats": ", ".join(map(str, dead_seats)) if dead_seats else "None",
        "is_first_night": death_day == 1,
    }


def make_death_hunter_shoot_context(
    context: "PhaseContext",
    hunter_seat: int,
    day: int,
) -> dict:
    """Create Level 2 context for hunter shoot decision.

    Args:
        context: The phase context from handlers
        hunter_seat: Hunter's seat (dying)
        day: Current day number

    Returns:
        Dict with game state formatted for hunter shoot prompts
    """
    living_players = sorted(context.living_players - {hunter_seat})

    # Identify werewolves for hint
    werewolves = [s for s in living_players if context.is_werewolf(s)]
    werewolf_hint = f"Known werewolves: {werewolves}" if werewolves else "No known werewolves."

    return {
        "phase": "NIGHT" if day == 1 else "DAY",
        "day": day,
        "your_seat": hunter_seat,
        "living_seats": living_players,
        "living_seats_str": ", ".join(map(str, living_players)),
        "werewolf_hint": werewolf_hint,
        "is_wolf_kill": True,  # Only called for werewolf kills
    }


def make_death_badge_transfer_context(
    context: "PhaseContext",
    sheriff_seat: int,
    day: int,
) -> dict:
    """Create Level 2 context for sheriff badge transfer.

    Args:
        context: The phase context from handlers
        sheriff_seat: Sheriff's seat (dying)
        day: Current day number

    Returns:
        Dict with game state formatted for badge transfer prompts
    """
    living_players = sorted(context.living_players - {sheriff_seat})

    # Identify trusted players for hint
    trusted = [s for s in living_players if not context.is_werewolf(s)]
    trusted_hint = f"Trusted players: {trusted}" if trusted else "No known trusted players."

    return {
        "phase": "NIGHT" if day == 1 else "DAY",
        "day": day,
        "your_seat": sheriff_seat,
        "living_seats": living_players,
        "living_seats_str": ", ".join(map(str, living_players)),
        "trusted_hint": trusted_hint,
    }


def make_banishment_last_words_context(
    context: "PhaseContext",
    your_seat: int,
    day: int,
) -> dict:
    """Create Level 2 context for banishment last words.

    Args:
        context: The phase context from handlers
        your_seat: The banished player's seat
        day: Current day number

    Returns:
        Dict with game state formatted for last words prompts
    """
    player = context.get_player(your_seat)
    role_name = player.role.name.replace("_", " ").title() if player else "Unknown"

    living_seats = sorted(context.living_players - {your_seat})
    dead_seats = sorted(context.dead_players)

    return {
        "phase": "DAY",
        "day": day,
        "your_seat": your_seat,
        "role": role_name,
        "death_context": f"You were banished on Day {day} by vote.",
        "living_seats": ", ".join(map(str, living_seats)) if living_seats else "None",
        "dead_seats": ", ".join(map(str, dead_seats)) if dead_seats else "None",
    }


def make_banishment_hunter_shoot_context(
    context: "PhaseContext",
    hunter_seat: int,
    day: int,
) -> dict:
    """Create Level 2 context for banished hunter shoot decision.

    Args:
        context: The phase context from handlers
        hunter_seat: Hunter's seat (being banished)
        day: Current day number

    Returns:
        Dict with game state formatted for hunter shoot prompts
    """
    living_players = sorted(context.living_players - {hunter_seat})

    # Identify werewolves for hint
    werewolves = [s for s in living_players if context.is_werewolf(s)]
    werewolf_hint = f"Known werewolves: {werewolves}" if werewolves else "No known werewolves."

    return {
        "phase": "DAY",
        "day": day,
        "your_seat": hunter_seat,
        "living_seats": living_players,
        "living_seats_str": ", ".join(map(str, living_players)),
        "werewolf_hint": werewolf_hint,
    }


def make_banishment_badge_transfer_context(
    context: "PhaseContext",
    sheriff_seat: int,
    day: int,
) -> dict:
    """Create Level 2 context for banished sheriff badge transfer.

    Args:
        context: The phase context from handlers
        sheriff_seat: Sheriff's seat (being banished)
        day: Current day number

    Returns:
        Dict with game state formatted for badge transfer prompts
    """
    living_players = sorted(context.living_players - {sheriff_seat})

    # Identify trusted players for hint
    trusted = [s for s in living_players if not context.is_werewolf(s)]
    trusted_hint = f"Trusted players: {trusted}" if trusted else "No known trusted players."

    return {
        "phase": "DAY",
        "day": day,
        "your_seat": sheriff_seat,
        "living_seats": living_players,
        "living_seats_str": ", ".join(map(str, living_players)),
        "trusted_hint": trusted_hint,
    }


# For backward compatibility
GameStateSummary = dict


if TYPE_CHECKING:
    from werewolf.handlers.werewolf_handler import PhaseContext
