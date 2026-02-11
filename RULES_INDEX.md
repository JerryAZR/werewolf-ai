# Werewolf Game Rules - Assertion Index

> **WARNING: This file is auto-generated. Edit `scripts/rules_index.yaml` instead.**
> Run `python scripts/regenerate_rules_index.py` after modifying the YAML.

This document provides a canonical indexed list of **hard constraints** for the game
validator. Each rule is written as an assertion with "MUST" or "CANNOT" for
unambiguous enforcement. Optional player choices (e.g., Hunter activation, badge
transfer) are NOT included here.

## Victory Conditions
- **A.1** Game MUST end with a winner when victory condition is met.
- **A.2** Villagers win when all Werewolves are dead (werewolf_count == 0).
- **A.3** Werewolves win when all Ordinary Villagers are dead (villager_count == 0).
- **A.4** Werewolves win when all Gods are dead (god_count == 0).
- **A.5** If both Werewolf and Villager victory conditions are met simultaneously, the game ends in a tie.

## Game Initialization
- **B.1** Werewolf count MUST be greater than 0.
- **B.2** Ordinary Villager count MUST be greater than 0.
- **B.3** God count MUST be greater than 0.
- **B.4** Each God role MUST be unique (no duplicate Seers, Witches, Hunters, or Guards).

## Phase Order
- **C.1** Game MUST start with Night 1 (Phase.NIGHT, day == 1).
- **C.2** Day phases MUST follow Night phases (no consecutive Night phases).
- **C.3** Sheriff election phases MUST run before DeathResolution on Day 1.
- **C.4** Night action order: Werewolves MUST act before Witch.
- **C.5** NightResolution MUST be the last night subphase.
- **C.6** A night phase MUST contain WerewolfAction and NightResolution subphases.
- **C.7** Campaign MUST be the first phase of Day 1.
- **C.8** Campaign CANNOT occur on Day 2+.
- **C.9** OptOut MUST follow Campaign IFF (candidates exist after Campaign).
- **C.10** Sheriff Election MUST follow OptOut IFF (candidates remain after OptOut).
- **C.11** Death Resolution MUST precede Discussion.
- **C.12** Discussion MUST precede Voting.
- **C.13** Banishment Resolution MUST follow Voting IFF (banishment occurred, i.e., not a tie).
- **C.14** Banishment Resolution CANNOT occur IFF (tie vote).
- **C.15** Game MUST end after 20 days maximum (implementation safeguard).

## Night Actions - Werewolf
- **D.1** Werewolves CANNOT target dead players.
- **D.2** Dead Werewolves CANNOT participate in night action.

## Night Actions - Witch
- **E.1** Witch MUST be informed of Werewolf kill target before making any potion decision.
- **E.2** Witch CANNOT use more than one potion per night.
- **E.3** Witch CANNOT use antidote on self.
- **E.4** Witch CANNOT use antidote if already used (antidote_used == True).
- **E.5** Witch CANNOT use poison if already used (poison_used == True).
- **E.6** Antidote MUST override Werewolf kill (saved player survives).
- **E.7** Poison MUST kill target regardless of guard protection.

## Night Actions - Guard
- **F.1** Guard CANNOT guard the same player on consecutive nights.
- **F.2** Guard CANNOT be overridden by Witch poison.
- **F.3** Guard skill MUST work even if Guard dies that night.

## Night Actions - Seer
- **G.1** Seer CANNOT check more than one living player per night.
- **G.2** Seer result MUST be GOOD or WEREWOLF.

## Sheriff Election (Day 1 Only)
- **H.1** Sheriff election MUST occur on Day 1 only.
- **H.2** Sheriff election CANNOT occur on Day 2+.
- **H.3** Night 1 deaths MUST be eligible for Sheriff.
- **H.4** Sheriff candidates CANNOT vote.
- **H.5** Sheriff vote weight MUST be greater than 1 and less than 2 (1.5 for tie-breaking).

## Death Resolution
- **I.1** Night deaths MUST be announced after Sheriff phases (Day 1).
- **I.2** Cause of death MUST NOT be revealed.
- **I.3** Role and camp of dead player MUST be hidden.
- **I.4** Night 1 deaths MUST get last words (day == 1).
- **I.5** Night 2+ deaths CANNOT get last words (day > 1).
- **I.6** Banished players MUST get last words (always).
- **I.7** Multiple night deaths MUST give last words in seat order.
- **I.8** Dead players CANNOT participate in Discussion.
- **I.9** Dead players CANNOT vote in Day voting.

## Voting
- **J.1** Vote target MUST be a living player.
- **J.2** Tie vote MUST result in no banishment.

## Hunter
- **K.1** Hunter CANNOT activate when poisoned (cause == POISON).
- **K.2** Hunter CANNOT target dead players.
- **K.3** Hunter MUST either shoot a living player or return "SKIP".
- **K.4** Hunter shot target MUST die immediately.

## Badge Transfer
- **L.1** Badge transfer target MUST be living.
- **L.2** Sheriff role MUST remain single (one badge at a time).
- **L.3** Werewolf Sheriff MUST still win with Werewolf camp.
- **L.4** When a Sheriff dies, they MUST be queried for badge transfer target during death resolution.

## State Consistency
- **M.1** living_players union dead_players MUST equal all_players.
- **M.2** living_players intersect dead_players MUST be empty.
- **M.3** Player.is_alive MUST match seat in living_players.
- **M.4** Player.is_sheriff MUST match sheriff state.
- **M.5** Dead players CANNOT appear in living-only operations.
- **M.6** All events MUST have valid day number.
- **M.7** All events MUST have valid actor (seat exists).

## Event Logging
- **N.1** Every subphase MUST produce a SubPhaseLog.
- **N.2** Every phase MUST produce a PhaseLog.
- **N.3** GameStart event MUST be recorded.
- **N.4** GameOver event MUST be recorded with winner.
- **N.5** NightOutcome MUST record deaths.
- **N.6** All player actions MUST be logged as events.

## Role-Specific
- **O.1** Dead players CANNOT be queried for night or day actions.

## Summary

| Category | Rules | Enforcement Point |
|----------|-------|-------------------|
| Victory Conditions | 5 | on_game_over |
| Game Initialization | 4 | Game setup |
| Phase Order | 15 | Scheduler flow |
| Night Actions - Werewolf | 2 | WerewolfHandler |
| Night Actions - Witch | 7 | WitchHandler, NightActionResolver |
| Night Actions - Guard | 3 | GuardHandler, NightActionResolver |
| Night Actions - Seer | 2 | SeerHandler |
| Sheriff Election (Day 1 Only) | 5 | SheriffElectionHandler |
| Death Resolution | 9 | DeathResolutionHandler |
| Voting | 2 | VotingHandler |
| Hunter | 4 | DeathResolutionHandler |
| Badge Transfer | 4 | DeathResolutionHandler |
| State Consistency | 7 | on_event_applied |
| Event Logging | 6 | EventCollector |
| Role-Specific | 1 | Handlers |

**Total: 76 assertions**