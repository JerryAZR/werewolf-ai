"""Night action resolution - computes final deaths from accumulated night actions."""

from werewolf.engine import GameState, NightActionStore
from werewolf.events.game_events import DeathCause


class NightActionResolver:
    """Computes final deaths from accumulated night actions.

    Resolution order:
    1. Poison (kills regardless of guard)
    2. Werewolf kill (saved if antidoted OR guarded)
    """

    def resolve(
        self,
        state: GameState,
        actions: NightActionStore
    ) -> dict[int, DeathCause]:
        """Compute final deaths from accumulated night actions.

        Args:
            state: Current game state with living/dead player information.
            actions: Night action store containing kill, poison, antidote, and guard targets.

        Returns:
            Dictionary mapping seat number to DeathCause for each death.

        Resolution logic:
            - Poison kills regardless of guard (poison_target, if alive -> POISON)
            - Werewolf kill (kill_target):
                - Saved if antidoted (antidote_target == kill_target)
                - Saved if guarded AND guard_target == kill_target
                - Otherwise -> WEREWOLF_KILL
        """
        deaths: dict[int, DeathCause] = {}

        # Resolution order: Poison first (kills regardless of guard)
        if actions.poison_target is not None:
            poison_target = actions.poison_target
            # Poison only kills if target is alive
            if state.is_alive(poison_target):
                deaths[poison_target] = DeathCause.POISON

        # Werewolf kill resolution
        if actions.kill_target is not None:
            kill_target = actions.kill_target

            # Werewolf kill is saved if:
            # 1. Antidoted (antidote_target matches kill_target)
            # 2. OR Guarded AND guard_target matches kill_target
            is_antidoted = actions.antidote_target == kill_target
            is_guarded = (
                actions.guard_target is not None
                and actions.guard_target == kill_target
            )

            if not is_antidoted and not is_guarded:
                # Kill only happens if target is alive
                if state.is_alive(kill_target):
                    deaths[kill_target] = DeathCause.WEREWOLF_KILL

        return deaths
