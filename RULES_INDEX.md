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

## Phase Order
- **B.1** Game MUST start with Night 1 (Phase.NIGHT, day == 1).
- **B.2** Day phases MUST follow Night phases (no consecutive Night phases).
- **B.3** Sheriff election phases MUST run before DeathResolution on Day 1.
- **B.4** Night action order: Werewolves MUST act before Witch.
- **B.5** NightResolution MUST be the last night subphase.
- **B.6** A night phase MUST contain WerewolfAction and NightResolution subphases.
- **B.7** Day phases MUST follow order: Campaign -> OptOut -> Sheriff -> Death -> Discussion -> Voting.
- **B.8** Campaign MUST be the first phase of Day 1.
- **B.9** Campaign CANNOT occur on Day 2+.
- **B.10** OptOut MUST follow Campaign IFF (candidates exist after Campaign).
- **B.11** Sheriff Election MUST follow OptOut IFF (candidates remain after OptOut).
- **B.12** Death Resolution MUST precede Discussion.
- **B.13** Discussion MUST precede Voting.
- **B.14** Banishment Resolution MUST follow Voting IFF (banishment occurred, i.e., not a tie).
- **B.15** Banishment Resolution CANNOT occur IFF (tie vote).
- **B.16** Game MUST end after 20 days maximum (implementation safeguard).

## Night Actions - Werewolf
- **C.1** Werewolf kill target MUST be a living player.
- **C.2** Werewolves MUST either kill a living player or return "-1" to skip.
- **C.3** Dead Werewolves CANNOT participate in night action.

## Night Actions - Witch
- **D.1** Witch MUST know Werewolf kill target when deciding antidote.
- **D.2** Witch CANNOT use more than one potion per night.
- **D.3** Witch CANNOT use antidote on self.
- **D.4** Witch CANNOT use antidote if already used (antidote_used == True).
- **D.5** Witch CANNOT use poison if already used (poison_used == True).
- **D.6** Antidote MUST override Werewolf kill (saved player survives).
- **D.7** Poison MUST kill target regardless of guard protection.

## Night Actions - Guard
- **E.1** Guard CANNOT guard the same player on consecutive nights.
- **E.2** Guard MUST be allowed to guard self.
- **E.3** Guard protection MUST NOT apply to Witch poison.
- **E.4** Guard skill MUST work even if Guard dies that night.

## Night Actions - Seer
- **F.1** Seer CANNOT check more than one living player per night.
- **F.2** Seer result MUST be GOOD or WEREWOLF.

## Sheriff Election (Day 1 Only)
- **G.1** Sheriff election MUST occur on Day 1 only.
- **G.2** Sheriff election CANNOT occur on Day 2+.
- **G.3** All living players MUST be initial Sheriff candidates.
- **G.4** Night 1 deaths MUST be eligible for Sheriff (campaign, speak, vote).
- **G.5** Sheriff election CANNOT allow abstention (all candidates must vote).
- **G.6** Sheriff vote weight MUST be 1.5 (tie-breaking).

## Death Resolution
- **H.1** Night deaths MUST be announced after Sheriff phases (Day 1).
- **H.2** Cause of death MUST NOT be revealed.
- **H.3** Role and camp of dead player MUST be hidden.
- **H.4** Night 1 deaths MUST get last words (day == 1).
- **H.5** Night 2+ deaths CANNOT get last words (day > 1).
- **H.6** Banished players MUST get last words (always).
- **H.7** Multiple night deaths MUST give last words in seat order.
- **H.8** Dead players CANNOT participate in Discussion.
- **H.9** Dead players CANNOT vote in Day voting.

## Voting
- **I.1** All living players MUST vote (abstain is a valid response).
- **I.2** Vote target MUST be a living player.
- **I.3** Tie vote MUST result in no banishment.

## Hunter
- **J.1** Hunter CANNOT activate when poisoned (cause == POISON).
- **J.2** Hunter target MUST be a living player.
- **J.3** Hunter MUST either shoot a living player or return "SKIP".
- **J.4** Hunter shot target MUST die immediately.
- **J.5** Hunter shot target CANNOT activate Hunter skill (no chain).

## Badge Transfer
- **K.1** Badge transfer target MUST be living.
- **K.2** Sheriff role MUST remain single (one badge at a time).
- **K.3** Werewolf Sheriff MUST still win with Werewolf camp.

## State Consistency
- **L.1** living_players ∪ dead_players MUST equal all_players.
- **L.2** living_players ∩ dead_players MUST be empty.
- **L.3** Player.is_alive MUST match seat in living_players.
- **L.4** Player.is_sheriff MUST match sheriff state.
- **L.5** Dead players CANNOT appear in living-only operations.
- **L.6** All events MUST have valid day number.
- **L.7** All events MUST have valid actor (seat exists).

## Event Logging
- **M.1** Every subphase MUST produce a SubPhaseLog.
- **M.2** Every phase MUST produce a PhaseLog.
- **M.3** GameStart event MUST be recorded.
- **M.4** GameOver event MUST be recorded with winner.
- **M.5** NightOutcome MUST record deaths.
- **M.6** All player actions MUST be logged as events.

## Role-Specific
- **N.1** Dead players CANNOT be queried for night or day actions.

## Summary

| Category | Rules | Enforcement Point |
|----------|-------|-------------------|
| Victory Conditions | 4 | on_game_over |
| Phase Order | 16 | Scheduler flow |
| Night Actions - Werewolf | 3 | WerewolfHandler |
| Night Actions - Witch | 7 | WitchHandler, NightActionResolver |
| Night Actions - Guard | 4 | GuardHandler, NightActionResolver |
| Night Actions - Seer | 2 | SeerHandler |
| Sheriff Election (Day 1 Only) | 6 | SheriffElectionHandler |
| Death Resolution | 9 | DeathResolutionHandler |
| Voting | 3 | VotingHandler |
| Hunter | 5 | DeathResolutionHandler |
| Badge Transfer | 3 | DeathResolutionHandler |
| State Consistency | 7 | on_event_applied |
| Event Logging | 6 | EventCollector |
| Role-Specific | 1 | Handlers |

**Total: 76 assertions**