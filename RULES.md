# Werewolf Game Rules

## Game Overview

Werewolf is a multiplayer social deduction game divided into two camps: the Werewolf camp and the Villager camp. Werewolves hide among the villagers. Every night, the werewolves kill one villager, and during the day, all players vote to eliminate a suspected werewolf after discussion.

The Villager camp needs to find the disguised werewolves and banish them; the Werewolf camp needs to eliminate the villagers through deception and cooperation.

## Victory Conditions (Slaughter the Side)

The Werewolf camp has two ways to win:
- **Slaughter the Town**: Kill all villagers and all gods (special roles).
- **Slaughter the Side**: Kill all gods OR kill all ordinary villagers.

This game adopts the **Slaughter the Side** rule. If either side of the Villager camp (Ordinary Villagers or Gods) is completely eliminated, the Werewolves win immediately. The Villager camp must eliminate all Werewolves to win.

## Role Configuration (12-Player Standard)

### Werewolf Camp (4 Players)
| Role | Description |
|------|-------------|
| Werewolf | Can jointly kill one player every night. |

### Villager Camp (8 Players)
| Role | Count | Description |
|------|-------|-------------|
| Ordinary Villager | 4 | No special abilities. Participates in voting and discussion during the day. |
| Seer | 1 | Can check the identity (Good/Werewolf) of one player every night. |
| Witch | 1 | Has one bottle of antidote and one bottle of poison. Can save one person or poison one person per night. |
| Hunter | 1 | Can shoot and take one player with them upon death (cannot activate if poisoned by the Witch). |
| Guard | 1 | Can guard one player every night, protecting them from werewolf attacks (cannot guard the same person two nights in a row). |

### Sheriff (Title)
The Sheriff is **not a separate role** but a **title** that can be given to any player. One player may be elected as Sheriff on Day 1, gaining the following abilities:
- Vote counts as 1.5 (breaks ties)
- Leads discussion
- Badge is transferable on death |

## Game Flow

The game is divided into Day and Night phases, cycling in "Days". The game starts from the **First Night**.

Cycle structure: **Night Phase → Day Phase → Night Phase → Day Phase → ...**

Regardless of whether it is the first night or subsequent nights, every night is followed by a day phase for discussion and voting.

### Night Phase

Since this is an electronic game implementation, role actions do not need to be strictly sequential. Night actions can be processed in parallel, with the following constraints:

- The **Witch** acts after the Werewolves have made their kill decision to decide whether to use the antidote.
- The **Guard** and **Seer** can act at any time without special timing restrictions.
- Except for the Witch (who knows the Werewolf kill target), action results are secret.

#### Night Rule Details:
- The **Werewolves** decide their kill target first.
- The **Witch** then acts, knowing the Werewolf's kill target, to decide whether to use the antidote or poison.
- **The Guard's protection is ineffective against the Witch's poison**; a poisoned player dies regardless of protection.
- If a guarded player is also saved by the Witch's antidote, the player survives.
- **If the Witch poisons the Guard, the Guard's skill for that night remains effective.**
- The Witch and Guard do not know each other's actions during the night.
- Werewolves can see their teammates and decide on a kill target as a group.
- The Witch can see who was killed by the Werewolves.

### Day Phase

1. **Sheriff Election (Day 1 only)**: The Sheriff election is held **first** on Day 1, **before night results are announced**. Since death information has not been revealed yet, **any player can run for Sheriff** (including players who died last night but haven't been announced).
2. **Announce Night Results**: Announce dead players, but do not disclose the cause of death or identity.
3. **Last Words**: Players who died last night give their last words (each player has only one chance for last words per game).
4. **Discussion**: Living players speak in order. The Sheriff leads the discussion.
5. **Voting**: All players vote to banish one suspect.
6. **Banishment**: The player with the most votes is banished.
7. **Victory Check**: Check if victory conditions are met.

## Death Mechanisms

- **Werewolf Kill**: The player selected by Werewolves dies at night.
- **Witch Poison**: The player poisoned by the Witch dies at night.
- **Banishment**: The player with the most votes during the day is banished.
- **Hunter's Gun**: If the Hunter is killed by Werewolves or banished, they can choose to shoot and take one player with them.

## Last Words Rules

- Characters dying at night: Have last words on the **First Night** only; **no last words** for deaths on the second night and beyond.
- Characters banished during the day: **Always have last words**.
- **Multiple night deaths**: When multiple players die at night, last words are given in seat order.
- Last words are given immediately after death and can include accusations and analysis.
- After giving last words, the player no longer participates in the game.

## Voting Rules

- All living players must vote during the voting phase; **abstaining is allowed**.
- Tie handling: Players with the most votes enter a PK (Player Kill) round.
- PK Rules: Tied players speak again, followed by a revote by other players.
- If the revote is still a tie, no one is banished this round.

## Hidden Identity Rules

When a player is eliminated, their **identity card is NOT revealed**. Other players can only infer their identity from their speech and behavior.

Therefore, analyzing information revealed in a player's last words is a crucial basis for judging the situation.

## Victory Conditions

### Villager Camp Victory
- All Werewolves are banished or dead.

### Werewolf Camp Victory
- All Ordinary Villagers die, OR all Gods die (Slaughter the Side rule).

## Game Flow Overview

```
Start Game
    │
    ▼
First Night → Guard Acts → Seer Checks → Witch Uses Potion → Werewolves Kill
    │
    ▼
Day 1 → Sheriff Election → Announce Deaths → Last Words → Discussion → Voting & Banishment
    │
    ▼
Victory Check ─┬─ Villager Victory → Game Over
         │
         ▼
    Day 2+ → Announce Deaths → Last Words → Discussion → Voting & Banishment
         │
         ▼
    Victory Check ─┬─ Villager Victory → Game Over
              │
              ▼
         Night → Loop...
              │
              ▼
         Werewolf Victory → Game Over
```

## Role Details

### Seer
- Can choose one living player to check their identity every night.
- Result is "Good" or "Werewolf".
- Recommended to reveal identity and report results early in the day.
- Must be wary of Werewolves pretending to be Seers to confuse others.

### Witch
- Has one antidote (saves a player killed by Werewolves) and one poison (kills any player).
- **Only one potion can be used per night**.
- Usually recommended to use the antidote on the first night (if the Werewolf target is valuable).
- Cannot use the antidote on oneself.
- Poison can kill Werewolves, Gods, or Villagers.
- **Poison ignores Guard protection**; the poisoned player dies.
- **Poisoning the Guard does not affect the Guard's already activated skill for that night.**

### Hunter
- Can immediately shoot and take one player when killed by Werewolves.
- Can shoot and take one player when banished by vote.
- Cannot activate skill if poisoned by the Witch.
- **Optional usage**: May choose not to use the skill.
- **Targeting rule**: Can target any living player by their public identifier (name/ID), not by role or faction.
- Recommended to use skill cautiously after confirming a Werewolf's identity.

### Guard
- Can guard one player every night, protecting them from Werewolf harm.
- **Cannot guard the same person for two consecutive nights.**
- If the Guard protects the same person the Witch saves, the player survives.
- **Guard is ineffective against Witch's poison**; the poisoned player dies.
- Even if poisoned by the Witch, the Guard's skill for that night remains effective.
- If the Guard's identity is exposed, they may become a high-priority target for Werewolves.

### Sheriff
- Elected by majority vote on **Day 1** before any announcements. The election happens first, then night results are revealed.
- **Eligibility**: The Sheriff election is held **before** death announcements. Any player can run (including players who died last night but haven't been announced yet).
- **Vote Value**: The Sheriff's vote always counts as **1.5 votes** (not 1), which effectively breaks ties in their favor.
- **PK Round**: In PK rounds, the Sheriff's vote still counts as 1.5 votes.
- **Discussion Leader**: The Sheriff leads and organizes the day's discussion.
- **Badge Transfer**: If the Sheriff is banished or killed at night, the badge can be passed to another player of their choice.
- **No Win Condition Change**: The Sheriff does NOT change the player's original alignment. A werewolf Sheriff still wins with the Werewolf camp.
- **Death Rules**: If the Sheriff is banished, they can give last words and then choose who inherits the badge.
- **Night Death**: If the Sheriff is killed at night, the badge is not revealed. The Sheriff can designate an heir when night results are announced the next morning.

### Werewolf Coordination
- All living Werewolves act as a group at night to decide the kill target.
- Werewolves know each other's identities and act in unison after discussion.
- (Note: In this AI version, Werewolves make a collective decision via a single AI call).

## Rule Clarifications & Settings

Werewolf has many variations. This game uses the following specific rules:

### Basic Rules
| Rule Item | Our Implementation |
|-----------|--------------------|
| Victory Condition | Slaughter the Side (Werewolves win if all Gods OR all Villagers die) |
| Identity Reveal | Hidden (Identity not revealed upon elimination) |
| Game Start | Starts from First Night, with Sheriff election on Day 1 |
| Day Flow | Every round includes a full day phase (Discussion + Voting) |

### Night Action Rules
| Rule Item | Our Implementation |
|-----------|--------------------|
| Action Order | Werewolves act first, then Witch; Guard and Seer can act in parallel with Werewolves |
| Information | Witch and Guard do not know each other's actions; Witch knows Werewolf target |
| No Kill | Allowed (Werewolves can choose not to kill anyone) |
| Peace Night | Announced if no player dies after night settlement |
| Werewolf Team | All Werewolves act as a unit |
| Guard vs Poison | Guard cannot protect against Witch's poison; Guard skill works even if Guard dies |

### Role Skill Rules
| Rule Item | Our Implementation |
|-----------|--------------------|
| Sheriff Election | Held on Day 1 **before** death announcements; any player can run (including those who died last night but haven't been announced); majority vote; no abstention |
| Sheriff Power | Tie-breaking vote (1.5 votes, **also applies in PK rounds**); leads discussion; badge transferable on death |
| Hunter Skill | Activates on Werewolf kill or Banishment; Disabled by Poison; **Optional usage** |
| Guard Skill | Cannot guard same person twice in a row; **Self-guard allowed** |
| Witch Potions | One potion per night; Antidote invalid on self; **Poison allowed on First Night** |

### Voting & Last Words
| Rule Item | Our Implementation |
|-----------|--------------------|
| Voting Method | Abstention allowed |
| Tie Handling | PK round (respeech + revote); if still tied, no banishment |
| Night Last Words | Only for players dying on the First Night |
| Day Last Words | Banished players always have last words |

### Unimplemented Rules
Common rules NOT implemented in this project:
| Rule Item | Note |
|-----------|------|
| Self-Destruct | Werewolves cannot self-destruct during the day to force night phase |
