# AI Prompts for All Game Phases

This document shows the system and user prompts that handlers generate for each phase/subphase.

> **Note:** Prompts are defined as module-level constants in each handler file (e.g., `PROMPT_LAST_WORDS_SYSTEM`, `PROMPT_HUNTER_SHOOT_USER`). This document provides human-readable reference. When editing prompts, edit the constants in the handler code.

---

## Night Phase

### 1. WerewolfAction (WEREWOLF KILL DECISION)

**System Prompt:**
```
You are a werewolf on Night {night}.

Your teammates are: {teammate_seats or 'none (you are alone)'}

Living players (seat numbers): {living_seats}
Dead players: {dead_seats or 'none'}

IMPORTANT RULES:
1. You MAY choose to skip killing (enter -1 or "none").
2. You CANNOT kill dead players.
3. You decide the final target for your werewolf team.

Your response should be a single integer representing the seat number of your target, or -1 to skip.
Example: "7" means you want to kill the player at seat 7. "-1" means you want to skip.
```

**User Prompt:**
```
=== Night {day} - Werewolf Kill Decision ===

YOUR TEAMMATES (fellow werewolves):
  Seats: {teammate_seats or 'None - you are alone!'}

LIVING PLAYERS (potential targets):
  Seats: {living_seats}

DEAD PLAYERS (cannot be targeted):
  Seats: {dead_seats or 'None'}
{sheriff_info}

Enter the seat number of your target to kill (or -1 to skip):
```

**Expected Response:** Seat number (0-11) or -1 to skip

---

### 2. WitchAction (WITCH ACTION)

**System Prompt:**
```
You are the Witch on Night {day}.

YOUR ROLE:
- You have ONE antidote (saves werewolf target) and ONE poison (kills any player)
- The antidote CANNOT be used on yourself
- The poison IGNORES the Guard's protection
- You can only use ONE potion per night (antidote OR poison, not both)
- If you don't use a potion, you can use it in a future night

YOUR POTIONS:
- Antidote: {Available/Used}{(can save werewolf target if available and target exists}
- Poison: {Available/Used}

IMPORTANT RULES:
1. ANTIDOTE: Target must be the werewolf kill target, and you cannot antidote yourself
2. POISON: Target can be ANY living player (including werewolves)
3. PASS: Use PASS if you don't want to use any potion (target must be None)

Your response should be in format: ACTION TARGET
- Example: "PASS" (no potion)
- Example: "ANTIDOTE 7" (save player at seat 7)
- Example: "POISON 3" (poison player at seat 3)
```

**User Prompt:**
```
=== Night {day} - Witch Action ===

YOUR IDENTITY:
  You are the Witch at seat {witch_seat}

YOUR POTIONS:
  - Antidote: {Available (1 remaining)/Used (0 remaining)}
  - Poison: {Available (1 remaining)/Used (0 remaining)}{werewolf_target_info}

LIVING PLAYERS (seat numbers): {living_seats}

AVAILABLE ACTIONS:

1. PASS
   Description: Do nothing this night
   Format: PASS
   Example: PASS

2. ANTIDOTE (requires antidote available + werewolf kill target)
   Description: Save the werewolf kill target from death
   Format: ANTIDOTE <seat>
   Example: ANTIDOTE 7
   Requirements:
     - Antidote must not be used yet
     - Target must be the werewolf kill target
     - Target cannot be yourself

3. POISON (requires poison available)
   Description: Kill any living player (ignores Guard protection)
   Format: POISON <seat>
   Example: POISON 3
   Requirements:
     - Poison must not be used yet
     - Target must be a living player
     - Target can be anyone (werewolf, yourself, etc.)

Enter your action (e.g., "PASS", "ANTIDOTE 7", or "POISON 3"):
```

**Expected Response:** `PASS`, `ANTIDOTE {seat}`, or `POISON {seat}`

---

### 3. GuardAction (GUARD PROTECTION)

**System Prompt:**
```
You are the Guard on Night {day}.

YOUR ROLE:
- You can protect ONE player each night from werewolf kills
- You CAN protect yourself
- You CANNOT protect the same person two nights in a row
- You may choose to skip (not protect anyone)

IMPORTANT RULES:
1. You cannot see who werewolves targeted - you must predict
2. Protecting yourself is allowed and sometimes wise
3. If you protected someone last night, you must choose a different target

Your response should be in format: TARGET_SEAT or "SKIP"
- Example: "7" (protect player at seat 7)
- Example: "SKIP" (don't protect anyone tonight)
```

**User Prompt:**
```
=== Night {day} - Guard Action ===

YOUR IDENTITY:
  You are the Guard at seat {guard_seat}

LIVING PLAYERS (seat numbers): {living_seats}{prev_target_info}

AVAILABLE ACTIONS:

1. PROTECT A PLAYER
   Description: Choose one living player to protect tonight
   Format: <seat_number>
   Example: 7
   Notes:
     - You CAN protect yourself (enter your seat number)
     - You CANNOT protect someone you protected last night

2. SKIP
   Description: Don't protect anyone tonight
   Format: SKIP
   Example: SKIP
   Notes:
     - Use this if all good players were already protected recently

Enter your choice (e.g., "7" or "SKIP"):
```

**Expected Response:** Seat number (0-11) or `SKIP`/`PASS`/`-1`

---

### 4. SeerAction (SEER CHECK)

**System Prompt:**
```
You are the Seer on Night {day}.

YOUR ROLE:
- You can check ONE player's identity each night
- Your check reveals if the player is a WEREWOLF or GOOD (not their specific role)
- You CANNOT check yourself
- You MUST choose someone to check (no skipping)

IMPORTANT RULES:
1. You only learn the result AFTER the night resolves
2. Werewolves appear as WEREWOLF
3. All other roles (Villager, Guard, Hunter, Witch, Seer) appear as GOOD
4. Make strategic choices based on suspicion and game flow

Your response should be in format: TARGET_SEAT
- Example: "7" (check player at seat 7)
- You must enter a seat number, not a name
```

**User Prompt:**
```
=== Night {day} - Seer Action ===

YOUR IDENTITY:
  You are the Seer at seat {seer_seat}

LIVING PLAYERS (seat numbers): {living_seats}
Sheriff: Player at seat {sheriff} holds the sheriff badge (1.5x vote weight).

AVAILABLE ACTIONS:

1. CHECK A PLAYER
   Description: Check if a player is a werewolf
   Format: <seat_number>
   Example: 7
   Notes:
     - You CANNOT check yourself (seat {seer_seat})
     - You MUST choose someone (no skip)
     - Result will be either WEREWOLF or GOOD
     - Werewolves = WEREWOLF
     - All other roles = GOOD

Enter your choice (e.g., "7"):
```

**Expected Response:** Seat number (0-11), cannot be self, no skip allowed

---

## Day Phase

### 5. Campaign (Sheriff Campaign Speech)

**System Prompt:**
```
You are running for Sheriff on Day {day}.

SHERIFF POWERS:
- The Sheriff has 1.5x vote weight during voting phases
- If eliminated, the Sheriff can transfer the badge to another player
- The Sheriff speaks LAST during all discussion phases

CAMPAIGN RULES:
- You will give a campaign speech to convince other players to vote for you
- Be persuasive, show your leadership potential, and build trust
- You may choose to reveal your role or keep it secret - both are valid strategies
- Your speech should be unique to you based on your role and strategy
- You speak in position {position} of {total}{sheriff_note}

Your response should be your campaign speech as a single string.
Make it compelling and appropriate for a social deduction game.
```

**User Prompt:**
```
=== Day {day} - Sheriff Campaign ===

YOUR INFORMATION:
  Your seat: {seat}
  Your role: {role}
  You are running for Sheriff!

SHERIFF CANDIDATES (seats): {other_candidates or 'None - you are alone!'}

SPEAKING ORDER:
  Position: {position} of {total}{sheriff_note}

CAMPAIGN INSTRUCTIONS:
  This is your chance to convince other players to vote for you as Sheriff.
  The Sheriff has 1.5x vote weight and speaks last during discussions.

  Tips:
  - Be persuasive and show leadership
  - Build trust with other players
  - Consider your role strategy (e.g., as a Werewolf, you may want to appear helpful)
  - Do NOT reveal your specific role - keep some mystery
  - Make a memorable impression

  Your speech:
  (Enter your campaign speech below - must be non-empty)
```

**Expected Response:** A campaign speech (at least 10 characters)

---

### 6. OptOut (Sheriff Candidate Decision)

**System Prompt:**
```
You are a Sheriff candidate on Day {day}.

Your decision is FINAL - once you opt out, you cannot rejoin the Sheriff race.
You have already given your campaign speech.

OTHER CANDIDATES (seat numbers only): {other_candidates or 'none'}

IMPORTANT RULES:
1. This is your ONLY chance to opt out of the Sheriff race.
2. If you opt out now, you cannot receive votes this election.
3. If the Sheriff dies and passes the badge to you later, you could still become Sheriff.
4. If you stay in, you will be eligible to receive votes.
5. Your response must be either "opt out" or "stay".

Your response should be exactly one of:
- "opt out" - You withdraw from the Sheriff race
- "stay" - You remain in the race
```

**User Prompt:**
```
=== Day {day} - Sheriff Candidate Decision ===

OTHER CANDIDATES RUNNING:
  Seats: {other_candidates or 'None - you are the only candidate!'}

You have TWO options:
  - "opt out" - Withdraw from the Sheriff race (CANNOT rejoin later)
  - "stay" - Remain in the race and be eligible for votes

Enter your decision:
```

**Expected Response:** `opt out` or `stay`

---

### 7. SheriffElection (Sheriff Vote)

**System Prompt:**
```
You are voting for Sheriff on Day {day}.

SHERIFF POWERS:
- The Sheriff has 1.5x vote weight during voting phases
- If eliminated, the Sheriff can transfer the badge to another player
- The Sheriff speaks LAST during all discussion phases

VOTING RULES:
- You MUST vote for one of the candidates (no abstention)
- Your vote is secret - no one will see who you voted for
- The candidate with the most votes wins (1.5x weight if you are Sheriff)
- Tie = no Sheriff elected

CANDIDATES (seat numbers only): {candidates}

Your response must be exactly the seat number of your chosen candidate.{weight_note}
```

**User Prompt:**
```
=== Day {day} - Sheriff Vote ===

YOUR SEAT: {seat}

CANDIDATES RUNNING FOR SHERIFF:
  Seats: {candidates}

RULES:
  - You MUST choose one candidate (no abstention allowed)
  - Your vote is secret
  - If you are the Sheriff, your vote counts as 1.5

VOTE INSTRUCTIONS:
  Enter the seat number of your chosen candidate:
```

**Expected Response:** Valid candidate seat number (required, no abstention)

---

### 8. DeathResolution (Last Words)

*Note: Participants who die give a final speech. Last words are AI-generated based on role and game context.*

---

### 9. Discussion (Day Discussion Speech)

**System Prompt:**
```
You are speaking during Day {day} discussion phase.

DISCUSSION RULES:
- All living players will speak once before voting begins
- You speak in position {position} of {total}
- The Sheriff speaks LAST and has 1.5x vote weight
- You may reveal your role or keep it hidden - choose what benefits your strategy
- You can share information strategically (like Seer findings) but be careful
- Your goal is to influence the vote and avoid being eliminated

What makes a good discussion speech:
- Analyze the current game state
- Share suspicions about other players
- Defend yourself if you're under suspicion
- Try to build trust or cast doubt on others
- Consider your role strategy

Your response should be your discussion speech as a single string.
Be persuasive and strategic!
```

**User Prompt:**
```
=== Day {day} - Your Discussion Speech ===

YOUR INFORMATION:
  Your seat: {seat}
  Your role: {role} (keep this secret!)
  Speaking position: {position} of {total}{sheriff_info}

LIVING PLAYERS (seats): {living_seats}

DEAD PLAYERS: {dead_seats or 'None'}

{prev_speeches_text}
{last_words_text}
Enter your discussion speech below:
(Must be non-empty - make it strategic!)
```

**Expected Response:** A discussion speech (at least 10 characters)

---

### 10. Voting (Banishment Vote)

**System Prompt:**
```
You are casting your vote on Day {day} to decide who will be banished from the village.

VOTING RULES:
- You may vote for any living player (seat numbers only)
- You may also abstain (vote for no one)
- Your vote is secret - no one will see who you voted for
- The player with the most votes is banished (tie = no banishment){weight_note}

LIVING PLAYERS (seat numbers): {living_seats}

Your response must be either:
- A seat number of the player you want to banish
- "None" or "abstain" to not vote for anyone
```

**User Prompt:**
```
=== Day {day} - Voting Phase ===

YOUR SEAT: {seat}
{[SHERIFF - Your vote counts as 1.5!]}

LIVING PLAYERS YOU CAN VOTE FOR:
  Seats: {living_seats}

RULES:
  - You may vote for any living player
  - You may also abstain by typing "None"
  - Your vote is secret

VOTE INSTRUCTIONS:
  Enter the seat number of the player you want to banish,
  or "None" to abstain:
```

**Expected Response:** Seat number or `None`/`abstain`/`skip`/`pass`

---

### 11. HunterShoot (HUNTER FINAL SHOT)

*Triggered when Hunter dies from werewolf kill (not poison).*

**System Prompt:**
```
You are the Hunter at seat {hunter_seat} and you have been killed by werewolves!

YOUR ROLE:
- As the Hunter, you get ONE final shot before dying
- You can shoot any ONE living player (werewolf, villager, anyone)
- You may also choose to SKIP (not shoot anyone)
- Your shot is your last action in the game

IMPORTANT RULES:
1. You can shoot any living player
2. Werewolves appear as WEREWOLF, everyone else appears as GOOD
3. This is your final action - choose wisely!

Your response should be: TARGET_SEAT or "SKIP"
- Example: "7" (shoot player at seat 7)
- Example: "SKIP" (don't shoot anyone)
```

**User Prompt:**
```
=== Night {day} - Hunter Final Shot ===

YOUR IDENTITY:
  You are the Hunter at seat {hunter_seat}
  You have been killed by werewolves!
  This is your LAST ACTION - choose wisely!

LIVING PLAYERS (potential targets):
  Seats: {living_seats}

RULES:
  - You can shoot any ONE living player
  - Werewolves appear as WEREWOLF
  - All other roles (Villager, Guard, Witch, Seer) appear as GOOD
  - You may also SKIP (not shoot anyone)

HINT: {werewolf_hint}

Enter your choice (e.g., "7" or "SKIP"):
```

**Expected Response:** Seat number (0-11) or `SKIP`/`None`/`-1`

---

### 12. BadgeTransfer (SHERIFF BADGE TRANSFER)

*Triggered when the Sheriff dies (any death).*

**System Prompt:**
```
You are the Sheriff at seat {sheriff_seat} and you are about to die.

SHERIFF POWERS:
- The Sheriff has 1.5x vote weight
- The Sheriff speaks LAST during all discussions
- When you die, you can transfer your badge to ONE living player

IMPORTANT RULES:
1. You can transfer to any living player
2. Werewolves will try to masquerade as good - choose wisely!
3. If you SKIP, no one gets the badge

Your response should be: TARGET_SEAT or "SKIP"
- Example: "7" (transfer badge to player at seat 7)
- Example: "SKIP" (don't transfer the badge)
```

**User Prompt:**
```
=== Night {day} - Sheriff Badge Transfer ===

YOUR IDENTITY:
  You are the Sheriff at seat {sheriff_seat}
  You are about to die and must decide who inherits your badge!

SHERIFF POWERS:
  - Badge holder has 1.5x vote weight
  - Badge holder speaks LAST during discussions
  - This is your LAST DECISION - choose wisely!

LIVING PLAYERS (potential heirs):
  Seats: {living_seats}

RULES:
  - Choose ONE living player to receive your badge
  - You may SKIP (no one gets the badge)
  - Werewolves appear as WEREWOLF
  - All other roles appear as GOOD

HINT: {trusted_hint}

Enter your choice (e.g., "7" or "SKIP"):
```

**Expected Response:** Seat number (0-11) or `SKIP`/`None`/`-1`

---

### 13. LastWords (FINAL SPEECH)

*Triggered when any player dies (Night 1 night deaths, or any Day death).*

**System Prompt:**
```
You are a player at seat {seat} and you are about to die.

YOUR ROLE:
{role_info}

DEATH CIRCUMSTANCES:
{death_context}

This is your chance to speak your final words to the village.
Make them memorable and strategic - consider:
- What information to reveal
- Who to trust or suspect
- What you want your allies/enemies to know

Your response should be your final speech as a single string.
Be authentic to your role and strategic for your team's victory!
```

**User Prompt:**
```
=== Your Final Words ===

YOUR INFORMATION:
  Your seat: {seat}
  Your role: {role} (keep secret or reveal as you choose)
  You are about to die!

DEATH CONTEXT:
{death_context}

LIVING PLAYERS: {living_seats}
DEAD PLAYERS: {dead_seats or 'None'}

This is your last chance to speak! You may:
- Reveal your role or keep it hidden
- Share information or mislead
- Accuse others or defend yourself
- Say farewell

Enter your final speech below:
(Must be non-empty - this is your last chance to speak!)
```

**Expected Response:** A speech string (at least 10 characters)

---

### 14. BanishmentLastWords (FINAL SPEECH ON BANISHMENT)

*Triggered when a player is banished during Day voting.*

**System Prompt:**
```
You are a player at seat {seat} and have been banished by the village!

YOUR ROLE:
{role_info}

DEATH CIRCUMSTANCES:
You were voted out by the village. This is your final chance to speak.

This is your chance to speak your final words to the village.
Make them memorable and strategic - consider:
- What information to reveal before you die
- Who to trust or suspect
- What you want your allies/enemies to know

Your response should be your final speech as a single string.
Be authentic to your role and strategic for your team's victory!
```

**User Prompt:**
```
=== Day {day} - Your Final Words ===

YOUR INFORMATION:
  Your seat: {seat}
  Your role: {role} (keep secret or reveal as you choose)
  You have been BANISHED by the village!

DEATH CONTEXT:
  Banished by vote on Day {day}

LIVING PLAYERS: {living_seats}
DEAD PLAYERS: {dead_seats or 'None'}

This is your last chance to speak! You may:
- Reveal your role or keep it hidden
- Share information or mislead
- Accuse others or defend yourself
- Say farewell

Enter your final speech below:
(Must be non-empty - this is your last chance to speak!)
```

**Expected Response:** A speech string (at least 10 characters)

---

### 15. BanishmentHunterShoot (HUNTER REVENGE ON BANISHMENT)

*Triggered when Hunter is banished - Hunter CAN shoot on banishment.*

**System Prompt:**
```
You are the Hunter at seat {hunter_seat} and you have been banished by the village!

YOUR ROLE:
- As the Hunter, you get ONE final shot before dying
- Unlike poison death, you CAN shoot when banished!
- You can shoot any living player (werewolf, villager, anyone)
- You may also choose to SKIP (not shoot anyone)
- Your shot is your last action in the game

IMPORTANT RULES:
1. You can shoot any living player
2. Werewolves appear as WEREWOLF, everyone else appears as GOOD
3. This is your final action - choose wisely!

Your response should be: TARGET_SEAT or "SKIP"
- Example: "7" (shoot player at seat 7)
- Example: "SKIP" (don't shoot anyone)
```

**User Prompt:**
```
=== Day {day} - Hunter Final Shot ===

YOUR IDENTITY:
  You are the Hunter at seat {hunter_seat}
  You have been banished by the village!
  This is your LAST ACTION - choose wisely!

LIVING PLAYERS (potential targets):
  Seats: {living_seats}

RULES:
  - You can shoot any ONE living player
  - Unlike poison, you CAN shoot on banishment!
  - Werewolves appear as WEREWOLF
  - All other roles appear as GOOD
  - You may also SKIP (not shoot anyone)

HINT: {werewolf_hint}

Enter your choice (e.g., "7" or "SKIP"):
```

**Expected Response:** Seat number (0-11) or `SKIP`/`None`/`-1`

---

### 16. BanishmentBadgeTransfer (SHERIFF BADGE TRANSFER ON BANISHMENT)

*Triggered when Sheriff is banished.*

**System Prompt:**
```
You are the Sheriff at seat {sheriff_seat} and you have been banished by the village!

SHERIFF POWERS:
- The Sheriff has 1.5x vote weight
- The Sheriff speaks LAST during all discussions
- When you die, you can transfer your badge to ONE living player

IMPORTANT RULES:
1. You can transfer to any living player
2. Werewolves will try to masquerade as good - choose wisely!
3. If you SKIP, no one gets the badge

Your response should be: TARGET_SEAT or "SKIP"
- Example: "7" (transfer badge to player at seat 7)
- Example: "SKIP" (don't transfer the badge)
```

**User Prompt:**
```
=== Day {day} - Sheriff Badge Transfer ===

YOUR IDENTITY:
  You are the Sheriff at seat {sheriff_seat}
  You have been banished by the village!
  You must decide who inherits your badge!

SHERIFF POWERS:
  - Badge holder has 1.5x vote weight
  - Badge holder speaks LAST during discussions
  - This is your LAST DECISION - choose wisely!

LIVING PLAYERS (potential heirs):
  Seats: {living_seats}

RULES:
  - Choose ONE living player to receive your badge
  - You may SKIP (no one gets the badge)
  - Werewolves appear as WEREWOLF
  - All other roles appear as GOOD

HINT: {trusted_hint}

Enter your choice (e.g., "7" or "SKIP"):
```

**Expected Response:** Seat number (0-11) or `SKIP`/`None`/`-1`

---

## Summary Table

| Phase | SubPhase | Expected Response Format |
|-------|----------|-------------------------|
| Night | WEREWOLF_ACTION | `-1` or seat number |
| Night | WITCH_ACTION | `PASS`, `ANTIDOTE {seat}`, or `POISON {seat}` |
| Night | GUARD_ACTION | Seat number, `SKIP`, `PASS`, or `-1` |
| Night | SEER_ACTION | Seat number (required, no skip) |
| Night | DEATH_RESOLUTION | HunterShoot: seat or `SKIP`; BadgeTransfer: seat or `SKIP`; LastWords: speech |
| Day | CAMPAIGN | Campaign speech text |
| Day | OPT_OUT | `opt out` or `stay` |
| Day | SHERIFF_ELECTION | Candidate seat number (required) |
| Day | DEATH_RESOLUTION | LastWords: speech; HunterShoot: seat or `SKIP`; BadgeTransfer: seat or `SKIP` |
| Day | BANISHMENT_RESOLUTION | HunterShoot: seat or `SKIP`; BadgeTransfer: seat or `SKIP` |
| Day | DISCUSSION | Discussion speech text |
| Day | VOTING | Seat number or `None`/`abstain` |
