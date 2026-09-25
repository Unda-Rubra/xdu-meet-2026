# Sprint Racer 1.6.13 release source map

Historical source investigation only. Preset writer, fixed round references and UUID-based privileges below describe a **retired proposal**, not the deployed manual-token event. Current behavior and operator commands are in `docs/RULES.md` and `docs/OPERATIONS.md`; use this file solely for the cited native function locations.

Source: official CurseForge file 8422262, downloaded ZIP SHA-256 `ff661fabd6214fa10986866f05c57d30365552d8653739e264ffd04d1a7ba81f`. Actual sr_code pack range is exactly 107 (not development HEAD 121). Files extracted locally under ignored downloads/. This is source evidence, not multiplayer acceptance.

## Controls, sequence and termination

## Evidence scope and notation
All source references below are relative to `downloads/release-code/data/sprint_racer/function/`, abbreviated `F/`. Configuration references use `downloads/upstream-world/datapacks/sr_config/data/sprint_racer_config/function/`, abbreviated `C/`. These findings are source-proven against the provided local release tree, NOT runtime-validated. I did not independently recompute the supplied ZIP hash. No files or world state changed.

Use a single synchronous adapter function invoked by RCON:
```mcfunction
execute in minecraft:overworld as @e[type=minecraft:armor_stand,tag=w,x=1560,y=150,z=406,distance=..1,limit=1] at @s run function xdu_race:preset/apply
```
Before using `limit=1`, count the unrestricted matching anchor and require exactly one. Explicit dimension matters: the native selectors and world-block reads assume the overworld. `F/_force_load_chunks.mcfunction:1–2` force-loads 1536,336 through 1695,479, covering anchor, registry, and sequence blocks. Treat missing loaded entities/blocks as failure, not an invitation to create substitutes.

## 1. Minimal native writer, without any player executor
Preconditions: adapter idle/archived-reset state, no active native GP, exactly one world anchor, all requested registry entries resolved uniquely and enabled, no active temporary Save State/settings override. Run the following in one function as w, not separate RCON commands that allow ticks between steps:
```mcfunction
function sprint_racer:game_logic/11/_initialize
function sprint_racer:game_logic/11/buttons/red
# Require these transient tags absent before writing; clear only in idle prepare.
tag @s remove randomMode
tag @s remove randomTrack
tag @s remove eraseTrack
tag @s remove nope_avi
scoreboard players set @s worldmapID 1
function sprint_racer:game_logic/11/choose_track
scoreboard players set @s worldmapID 2
function sprint_racer:game_logic/11/choose_track
scoreboard players set @s worldmapID 3
function sprint_racer:game_logic/11/choose_track
scoreboard players set @s worldmapID 4
function sprint_racer:game_logic/11/choose_track
scoreboard players set @s worldmapID 5
function sprint_racer:game_logic/11/choose_track
scoreboard players set @s worldmapID 6
function sprint_racer:game_logic/11/choose_track
function sprint_racer:game_logic/11/update_display
```
Why this is a real writer rather than inferred from naming:
- `11/_initialize:1–4` enters setup only if not grandprix; otherwise it CANCELS an existing GP. Therefore caller must reject active GP before calling it. `_initialize_for_real:65` assigns native gameState=11; it does not require a player executor. It performs lobby/UI/AI cleanup, not a race start. Do not use it as a supposedly harmless status operation.
- `11/buttons/red:6–10,12–66` clears the old sequence, gpNumber=0, gpRound=1 and all gpNo1..50 tags. Its fill only covers x=1584..1587, not the final two settings columns; this is safe for the new six rows because the native writer overwrites all SIX columns for every inserted slot. Still verify final gpNumber=6 and no out-of-range slot membership.
- `11/choose_track:1–9` adds gpOrderSet, removes dontSetGamemode, sets caller carrotInput=1, clears chosenTrack, invokes worldmap_choose. Thus no player ready/click/item entity is required.
- `0/worldmap_choose:2` requires carrotInput. Lines 6–8 overwrite worldmapID only for player executors, so w's explicitly assigned ID survives. Lines 26–31 set/synchronize Race gameState from worldmapID 0..999. Lines 44–50 select IDs 1..6. Lines 145–147 suppress actual gameplay initialization while gpOrderSet is present; line 154 calls add_track.
- `11/add_track:5,10` increments gpNumber then invokes `write_new_track/position` as w positioned at 1584 39 372. `position:1–6` offsets by the new gpNumber. `add_track:18–24` attaches gpNoN to the chosen registry stand. Its final three commands restore both w/global gameState=11 and remove chosenTrack. The temporary gameState=1 during writing must not escape to a tick.
- `write_new_track/go:4–22` writes `[light_blue_wool, stone, oak_planks, stone, stone, stone]` at x=1584..1589, y=39, z=372+slot. That is Race, explicit track (not random), default gamemode, no modifier, no alternate track-selection override, no Save State. Lines 34–35 preserve/restore row-one backup at y=40; bypassing this writer by setting blocks yourself misses that native quirk.

Readback MUST check: gpNumber=6, gpRound=1, gameState=11; every six-block row exactly matches the above; each gpNo1..6 resolves to exactly the expected stand; no duplicates/disabled entries; chosenTrack absent; configured public-settings digest unchanged. `#gpTrackSelect=1` decoded from stone is NOT evidence of random selection: `read_rtrack` comes only from the SECOND column being black wool (`11/read_gamemode:5`); `0/grand_prix_round_start:20` uses explicit gpNoN whenever that tag is absent. Do not change column five to claim a fixed sequence is necessary.

## 2. Six definite stock Race identifiers
Canonical selector for ID N, used for validation (do NOT put limit=1 on the count):
```mcfunction
@e[type=minecraft:armor_stand,tag=random,tag=trackStandR,tag=!customrace,tag=!rtBlacklist,x=1548,y=155,z=406,distance=..1,scores={rNumber=N}]
```
Also count the raw native worldmap selector (`tag=random`, same coordinates/rNumber, without extra filters) and require it resolves to that same single entity: native worldmap_choose does not itself filter disabled tracks or enforce type/trackStandR. A duplicate/banned stand must reject prepare, not be hidden by a narrower successful selector.

| worldmapID / rNumber | stock ID | loading proof | per-tick routing proof |
|---|---|---|---|
|1|river_valley|`1/_initialize_index:11`|`levels/_index_levels_race_1_5:4`|
|2|highlight_stadium|`:12`|`:5`|
|3|sakura_city|`:13`|`:6`|
|4|seaside_village|`:14`|`:7`|
|5|laeto_forest|`:15`|`:8`|
|6|petra_mountains|`:16`|`levels/_index_levels_race_6_10:4`|

`0/worldmap_choose:44–50` proves numeric worldmapID → registry rNumber; `1/_initialize_index:11–16` dispatches actual stock initialization, not just display names. Each corresponding `levels/<id>/_initialize.mcfunction:1–8` contains real world teleport/lap/time settings. Native Race lap counts for those IDs are respectively 4, 7, 3, 3, 3, 3; preserve them unless an explicit common-lap policy is approved. Names also agree with `6/worldmap_say_name:9–14`. Runtime existence/uniqueness and loaded track nodes still require server readback; source registration alone does not prove a prepared world contains an intact track.

## 3. Arm/start and the ready gate
Prepare can remain at setup gameState=11; it must not call race initialization. With the adapter's state/idempotency checks already passing, native GP arming is:
```mcfunction
function sprint_racer:game_logic/11/start_grand_prix
```
`11/start_grand_prix:19–25` forces unready, gpRound=1, grandprix tag and fake-player grandprix gameState=1. Lines 28–35 save gamemode defaults and clear native points/gpPoints. Lines 37–38 peek then run lobby initialization. Because input gameState was 11, the GP advancement function does NOT increment: setup enters lobby gameState=0 with gpRound=1. This entry is destructive to old native results, so archive/reset/attempt gating must precede it.

For an explicit approved first launch, after native arming and roster validation:
```mcfunction
function sprint_racer:game_logic/0/set_mode_ready
scoreboard players set @s gameTime 0
```
The next normal ready-lobby tick reaches `0/gl0_main_ready`'s penultimate GP launch command, calling `0/grand_prix_round_start`. `set_mode_ready:1–3` adds readyup to ALL online players and sets readyState=1; it is not a UUID-aware tournament gate. Access must already ensure only the fixed roster is playing. Do not report started at this point: Race GO effects actually occur at gameTime=160 in `1/start_countdown:72–96`.

A lone `scoreboard ... readyState 1` is NOT durable: `0/gl0_main:98–116` recomputes majority from playing+readyup and can undo it every tick; `_initialize_for_real:15–35` has a second computation. Required hooks:
1. Gate manual self_ready/self_not_ready inputs at `0/gl0_main:90–93` (Access owner).
2. Gate `0/set_mode_ready` before line 1 so prepare/finished/stopped cannot be readied by another native caller; keep the native inner routine for an authorized first start.
3. Gate `0/grand_prix_round_start` BEFORE line 1 using backend attempt/state plus expected slot; permit first slot only with trusted start authorization, subsequent slots only after prior settlement. It is the common auto-advance boundary, not just a UI button.
4. Also prevent ordinary non-GP race entry after completion: `4/end` returns to an ordinary lobby with old readyup tags still present (unready commands are COMMENTED OUT). A GP-only guard alone does not prevent an unintended free Race after ceremony. Hold lifecycle gate closed in GP_FINISHED/STOPPED/ERROR and block non-tournament gameplay initialization for the managed event server.

## 4. Advancement, fallback rejection, and no seventh race
`1/end_sequence:31–36` loads/adds native results around gameTime=100120 and presents incremental points at 100160; line 42 returns to `0/_initialize` at 100260+. `0/_initialize:26` invokes GP advancement. `0/grand_prix_decide_if_skip:2–9` recognizes old gameState=1 (also 3,4,7,8), tags gp_skip2next, and adds one to gpRound unless noskip2next. Its subsequent peek decodes the next slot. For fixed rows, `#gpTrackSelect=1`, so no vote/choose mode stops native auto-advance. `0/_initialize:135` → `_initialize_skip_to_next:66` → `grand_prix_round_start` launches slots 2–6.

After the sixth result, gpRound becomes **7**. This is a valid native completion sentinel, not proof of a seventh start. `0/_initialize:125` compares gpRound > gpNumber and adds ceremony; line 133 starts ceremony; line 135 explicitly excludes ceremony from auto-launch. Keep that increment intact. Reject gpRound outside 1..6 at the LAUNCH boundary, not at the increment/ceremony boundary.

`grand_prix_round_start:20` calls `11/choose_track_defined`, whose lines 1–6 use `limit=1,sort=random` among gpNoN-tagged stands: duplicates cause random choice. Lines 30–33 of round_start then silently choose a random track when missing. Required launch hook before line 1 must verify exact slot row, exact registry identity, unique gpNoN membership, enabled status, settings, roster and zero AI. On violation, return from the native function with backend ERROR; do not merely omit the call and allow lines 31–33 to run. Recheck chosenTrack after line 20/before fallback if selection can be changed elsewhere.

`4/_initialize:1–2` uses endlessMode to choose full ceremony vs skip. `4/_initialize_for_real:1–6` can immediately call `4/end` if no ONLINE player has positive dummyPoints (or AI/team score exists). Therefore the GP-finished/freeze hook belongs at entry to `4/_initialize`, before either branch, after confirming sixth-track settlement; a hook only late in the podium animation misses the no-online-results path. `4/end:2–10` resets gpRound to 1, removes grandprix only if !grandprixloop, and recreates gpPoints; lines 18–19 clear other scores. Capture before that destruction. Preserve the normal ceremony presentation; end hook must be idempotent and not infer external ranks from podium's online-only logic.

## 5. Stop/cancel by phase
No single native function is a safe tournament stop: native functions know neither immutable history nor attempt gates. First latch backend STOPPED/ERROR (closing all launch/ready paths), record interrupted facts, clear readyup/readyState, and cancel outstanding `schedule function sprint_racer:game_logic/1/check_for_lone_player` if a race initialization just scheduled it. That scheduled function has no gameState guard and can otherwise act after a stop.

- **Setup gameState=11, no grandprix:** `function sprint_racer:game_logic/11/exit` returns through `0/_initialize` (`exit:10–11`), without starting a GP or clearing the configured six slots. Do not call cancel_grand_prix here: it unnecessarily clears scores.
- **Armed lobby gameState=0, grandprix:** after snapshot/latch, `function sprint_racer:game_logic/11/cancel_grand_prix` is the full native cancellation. It clears points (`:7–8`), restores saved gamemode defaults (`:14–16`), clears pending Save State request (`:19`), removes grandprix BEFORE returning to `0/_initialize` (`:21–24`). Thus it cannot increment the GP on that return. This is cancellation, never natural GP_FINISHED.
- **Loading/countdown/running Race gameState=1, or its settlement animation:** for immediate authorized force-stop, record an interrupted/pending-judge snapshot FIRST; the same native cancel routine removes GP before cleanup and therefore does not advance. Alternatively, `0/_return_to_lobby:2–5` adds noskip2next and returns without incrementing the current slot, but RETAINS grandprix and permits replay if the adapter gate reopens; it is not a completed cancellation. Never call bare `0/_initialize` from a running GP to stop: it increments/auto-launches. Never force timeRemaining=-1 to implement cancel: `1/end_game_logic` calls end_sequence, which awards/settles and advances as though the native race ended.
- **BETWEEN_TRACKS:** native transition can increment and start the next track in the SAME function execution. There is no reliable external RCON pause window. A queued stop must be consumed inside the launch guard before round_start line 1; after prior settlement is recorded, cancel safely under the same closed gate. If it arrives after launch, report actual race/countdown phase and require force policy rather than pretending it stopped between tracks.
- **Ceremony gameState=4 after completed sixth settlement:** let presentation finish with loop/endless disabled. If operator explicitly skips the presentation, capture/freeze first then call `4/end` AS w; it contains @s-dependent loop handling and clears scores. Do NOT call `_return_to_lobby` here: with gpRound=7 it can re-enter ceremony, and without noskip it would increment again. Completed frozen results must remain GP_FINISHED, not be rewritten as STOPPED.
- **Already finished/idle:** no native cancellation needed; return idempotent state. Reset requires archive approval and may later enter setup; neither clear_points nor buttons/red is a historical-results reset.

All safety statements here describe source control flow and necessary adapter conditions; entity cleanup, tick interleavings, client state and Paper execution still need runtime verification.

## 6. Fixed native settings and preservation boundary
Required invariant baseline before apply/start/every next-track launch:
- adminMode=1 in `C/admin_mode.mcfunction:2`; current shipped value is 0. realmsMode=0 in `C/realms_mode.mcfunction:2` (admin comment states Realms mode overrides admin restrictions). Access still must audit ready/cancel paths.
- Remove `grandprixloop` AND `endlessMode` on w. Loop removal alone is insufficient: `4/skip_podium_sequence:5–6,14–15` resets gpRound and sets return-control tags without the normal `4/end` GP cleanup. Preserve stock presentation using the normal ceremony branch.
- Race AI disabled: w has optRAInever; remove optRAIsingle, optRAIalways and RAIautocount; optRAIcount=0. `1/ai_initialize:24–42,52–61` proves eligibility/count logic. These are necessary settings, not a complete zero-AI proof. Access must defend every other spawn/reconnect path.
- Preserve Race mode with approved gamemodePresetA (standard Race is 1; source uses 2 for elimination and 3 for tactics at `1/_initialize:269–285`, `1/start_countdown:33,91`). No randomPresetA/B; slot oak_planks means retain the saved/default mode, not force mode 1. Native start saves A/B and lobby restore reapplies them (`11/start_grand_prix:28–29`, `0/_initialize:65–69`). Do not let a preset silently choose another mode.
- Six slots have no modifier and no Save State; require #gpSaveState/#requestSaveState=0 and no live temporary-save/overridden-settings state. `0/_initialize:1–5` restores temporary settings; `0/grand_prix_peek:21` requests the decoded Save State. Compare an explicit public-settings whitelist before/after preset; transient scores, gpNumber, worldmapID, presentation/world time are not public option changes.
- Keep approved items, teams, lap policy, balance, timeouts and performance settings unchanged. The GP writer does not need to change them. Do not invent final event defaults from this investigation.
- Critical zero-AI/single-player edge: `1/_initialize:309` schedules `check_for_lone_player` one tick later. That function `:6–8,23–25` diverts fewer than two humans to Time Attack when bots are disabled. A tournament-specific guard is required to preserve Race semantics, otherwise a one-human ZERO-AI GP silently changes mode. Do not add bots to avoid the diversion.

## Remaining runtime acceptance
Must still execute the writer on the real world and read back all blocks/entities/settings; prove playerless prepare stays setup; two accounts run all six native races; verify one-human no-AI path stays Race after the guard; observe actual GO capture at 160; stop during load/GO/settlement/transition; finish with everyone offline; ensure podium fast-exit capture; ensure no seventh GP or ordinary free Race after ceremony; restart and repeat all invariant readbacks. None of those scenarios was run in this read-only assignment.

## Access, zero AI and results

## Scope and evidence
All findings below are from the actual local release supplied in the assignment, not the GitHub reference. Read-only file/archive searches only; no tests, builds, formatting, edits, or multiplayer execution. Source proof is not acceptance evidence.

Path shorthand used below:
- F = `downloads/release-code/data/sprint_racer/function/`
- C = `downloads/upstream-world/datapacks/sr_config/data/sprint_racer_config/function/`
- L = archive member prefix `downloads/upstream-world/datapacks/sr_language_all.zip:data/sprint_racer_language/function/`
These expand to precise relative source paths. Proposed `xdu_*` names below are recommendations, NOT existing native names or implemented interfaces.

## 1. Native state and executor contracts

World controller selector W: `@e[tag=w,x=1560,y=150,z=406,distance=..1,type=armor_stand,limit=1]`. Most `game_logic` ticks execute AS W, but some initializers are invoked by players, scheduled functions, or console and use explicit W selectors internally. Do not blindly add `unless entity @s[tag=admin] return` to shared lifecycle functions: it would reject legitimate W/scheduled calls and would not constitute a trusted-console gate.

Native controller objectives/tags relevant here: `gameState`, `gameTime`, `timeRemaining`, `timeOut`, `readyState`, `readyCount`, `readyRequired`, `gpRound`, `gpNumber`, `roundNumber`, `gamemodePresetA`, `playerCount`, `playerCountB`, `finishPos`, `addPoints`; tags `grandprix`, `grandprixloop`, `requireAdmin`, `realms`, `teamplay`, `customTesting`, `initFailed`, `choosingTrack`, `settingTracks`, `noskip2next`, `gp_skip2next`.

Separate fake-player state: `global gameState`, `grandprix gameState`, `#join_tick value`, `#halftick value`, `#getOnWithIt value`, `#requestSaveState value`. The event GP round 1–5 must NOT reuse native `gpRound`, which is the current track/slot within one GP.

Native participant identity is ephemeral `playerID`; it is not UUID. Native tags include `playing`, `finished`, `activeplayer`, `forcespectate`, `spectate`, `afk`, `admin`, `readyup`, `lobby`. `activeplayer` is reconstructed in `F_main.mcfunction:79–83`: only adventure-mode humans with hp>=1 and playing, plus AI entities. It explicitly excludes normal finished spectators. Never use it as historical roster or export membership.

## 2. Zero AI: configuration, actual creation, and single-human trap

### Required fixed settings
Actual sr_config only has admin/Realms/secret-lobby/item-balance functions; there is no separate declarative AI config file. Set AI using actual W tags/scores and lock their mutators:
- add `optRAInever`, `optBAInever`;
- remove `optRAIsingle`, `optRAIalways`, `optBAIsingle`, `optBAIalways`;
- remove `RAIautocount`, `BAIautocount` (the MEET/fill-to-target options);
- set `optRAIcount`, `optBAIcount` to 0 as additional explicit configuration, while recognizing native UI save encoding only represents positive counts. NEVER rely on count=0 alone;
- remove `grandprixloop`; enforce non-team Standard Race `gamemodePresetA=1`, no `randomPresetA`, no `teamplay`, no `customTesting` for this capture contract.

Actual race choices: `Fgame_logic/1/ai_initialize.mcfunction:24–42` counts `@a[tag=playing]`, sets `agogo` for single-player or always-on settings, and subtracts playerCount from configured count if `RAIautocount`. Lines 53–61 activate the desired `AImaster` controller stands; line 65 removes them again when optRAInever. Battle equivalent is `Fgame_logic/3/ai_initialize.mcfunction:24–63`, using BAI settings. Both are called at `gameTime=45` from their start_countdown line 32. This is pre-GO and runs again on each track/restart, not only at initial GP launch.

AI master selector: `@e[tag=AImaster,type=armor_stand,x=1548,y=155,z=406,distance=..1,scores={rNumber=1..9}]`. Actual competitors use `@e[type=!player,tag=ai]`; native activeplayer construction excludes marker/armor_stand types. Count actual competitors separately from active masters; report both so dormant respawn controllers cannot be hidden by an apparent zero living-AI count.

Continuous respawn: `Fall_20hz_stuff.mcfunction:2` calls `ai/general/__ai_main`; `Fai/general/__ai_main.mcfunction:10–11` runs active masters; `_ai_master.mcfunction:8` calls `check_if_alive/_index`; that function line 11 invokes `respawn/_index_find_respawn` if `needRespawn`; ultimately `Fai/general/respawn/_index_entity.mcfunction:5` calls `_index_entity_spawn`. This is why killing entities alone does not establish zero AI.

Additional real activation found by broad search: `Fgame_logic/12/ai_initialize.mcfunction:29` unconditionally activates all nine masters for credits, ignoring optRAInever. `Fgame_logic/12/start_countdown.mcfunction:30` calls it. Credits entry is `Fgame_logic/0/misc_lobby_happenings/credits_button/success.mcfunction:2`; Time Attack can also enter credits via `Fgame_logic/6/_initialize.mcfunction:2`. Podium `Fgame_logic/4/spawn_ai_entity.mcfunction:2` calls the same low-level spawn dispatcher for AI podium appearances. Block alternate-mode/credits entry on tournament servers and guard the shared AI spawn dispatcher in tournament mode. Do not mistake decorative lobby entities with NBT `NoAI:1b` for racer bots.

Small source guards recommended:
1. At entry of Race/Battle/Credits `ai_initialize`, tournament guard validates locked AI settings and zero master/entity presence, records a violation and refuses activation rather than silently repairing injected settings. A defensive tournament return must precede the broad `kill @e[type=marker,tag=!node]`/cloud cleanup in these functions; do NOT use that broad cleanup as your zero-AI enforcement.
2. Guard `ai/general/respawn/_index_entity_spawn` entry against tournament activation; this also covers podium spawning. Log/mark ERROR when reached unexpectedly, do not erase evidence and report success.
3. At start acceptance and every automatic next-track acceptance verify both configured disabled state and actual/master counts. Detect contamination before native `_initialize` calls `ai_stop_all` (line 43) and erases controller evidence.
4. On boot/reload verify settings before gameplay and mark interrupted attempt uncertain. Do not silently resume an in-flight tournament merely because configuration now looks correct.

### CRITICAL: zero AI plus one human does not stay in Race
`Fgame_logic/1/_initialize.mcfunction:309` schedules `check_for_lone_player` after 1t unless initFailed/customTesting. `Fgame_logic/1/check_for_lone_player.mcfunction:6–8` sets noBots for optRAInever/count<=0/noAItrack. Lines 23–25 call `_switch_to_time_attack` when fewer than two playing humans, or cheat 23a is present. `_switch_to_time_attack.mcfunction:1–2` adds return2lobby and initializes game_logic/7.

Tournament patch must guard this actual switch (or return at check_for_lone_player entry in tournament mode), preserving a genuine Standard Race for a permitted one-human roster. Merely turning AI off fails the stated one-human acceptance. If one-human start is not authorized by policy, reject before launch rather than allowing Time Attack. No AI compensation is needed or recommended.

### Settings mutation backdoors
AI UI: tOption 1027/1028 counts, 1040/1041 context, 1044/1045 fill/add mode, 1021 custom AI, 1046/1047 difficulty, 1048 rival, 1050 mannequins; map in `Fboq/trigger_option_0_99.mcfunction:22–51`. Actual add-type toggle is `L_dlc_6/lobby/options/ai_add_type_race.mcfunction:3–6`. Context mutator is `Llobby/options/ai_context_race.mcfunction`; it cycles never → single → always → never and defaults missing state to single. `Fgame_logic/0/save_state/load_block_state.mcfunction:104–124` reloads AI context/count from blocks; 126 onward does battle. GP per-slot Save State can reinstate AI settings at race initialization: `Fgame_logic/1/_initialize.mcfunction:1–2` handles #requestSaveState. Freeze these surfaces; validating only when loading a tournament preset is insufficient.

## 3. Practical permission seam map (narrow guards, preserve items)

### Authorization source and join/boot
`Cadmin_mode.mcfunction:2` defaults W adminMode=0. `Cadmin_player_list.mcfunction:5–6` documents name-based scoreboard adminMode=1. `Crealms_mode.mcfunction:2` defaults realmsMode=0; keep it zero. `Fbootup_delayed.mcfunction:24–31` Realms forces adminMode=0; normal mode calls config, adds requireAdmin, then loads admin list.

`Fjoin.mcfunction:10` adds admin from adminMode, but line 19 removes admin on first-ever join; stale admin tags are otherwise not revoked. Line 38 resets ALL objectives on @s, including any event scores stored on that player. Recommendation: derive admin authorization from configured UUID storage, explicitly clear/recompute native admin tag, after native first-join stripping and after final native join routing (end of join is simplest), and refresh on whitelist changes. Do not depend on persistent player xdu scoreboard fields surviving join. Add a pre-join capture/continuity hook before line 38 if transient native facts must be observed.

### Signs and dialogs
Actual path: `_main:146` executes `coordinates` as all players; `Fcoordinates.mcfunction:40–45` dispatches/re-enables tOption/tEditor/tTrackEditor. `Fboq/trigger_option.mcfunction:5,8` checks allowed mode/spectator, not admin; calls option switch line 11. Most `Fgame_logic/0/options_signs/*.mcfunction` wrappers use `clickSign`, checking requireAdmin and @s[tag=admin], e.g. ai_context_race lines 1–8, then execute language-pack mutators. Add the authoritative UUID-derived authorization/locked-settings check BEFORE first mutation in these wrappers. A guard in tOption dispatcher is useful for consuming unauthorized triggers, but is not a replacement for guards on direct/scheduled mutators.

`downloads/upstream-world/datapacks/sr_dialog/data/sprint_racer/dialog/quick_warp.json` actions use trigger tOption 1051–1058; no separate dialog permission boundary. 1051–1055 are public movement warps, 1056–1058 use require-admin warps. Preserve benign movement/personal settings if desired; block access to global setting mutators. Do NOT block the entire coordinates function, carrot_on_stick function, or all carrotInput: they service movement, right-clicks, reset items and gameplay.

### Ready/start/pause
Native ready votes IGNORE admin mode: `Fgame_logic/0/gl0_main.mcfunction:91–92` any playing user holding readyup custom_data toggles `self_ready`/`self_not_ready`; lines 98–116 count majority and call `set_mode_ready`/`set_mode_not_ready`. `_initialize_for_real.mcfunction:34–35` repeats majority transitions. `set_mode_ready.mcfunction:1–3` readies ALL players and sets readyState=1; `set_mode_not_ready.mcfunction:1–3` unreadies ALL and sets readyState=0.

Patch `self_ready`/`self_not_ready` entry to consume unauthorized menu input without changing readiness. More importantly guard the actual set_mode_ready/not_ready global mutations with tournament lifecycle permission, because initialization can invoke them without a player. A prepared GP start should acquire an explicit adapter-owned permit; native automatic progression must be authorized by RUNNING/BETWEEN_TRACKS and expected slot, not by whichever player is online. Deny ordinary pause/unready throughout the fixed attempt. This is lobby countdown pause; I did not find a distinct source-level generic race-pause command.

Admin input also bypasses ready voting: `Fboq/trigger_editor_0_99.mcfunction:64–71` tEditor 1063 race restart, 1064 battle restart, 1065 return lobby, 1066 restart lobby, 1067 force ready, 1068 force unready, 1069 set 5sec, 1070 full_restart. `Fboq/trigger_editor.mcfunction:12` checks CREATIVE only, not authoritative admin. The native admin menu `L_dlc_2/admin_controls.mcfunction` explicitly changes its player to creative at the end. Guard `Finventory_check/inventory_controls/admin_menu.mcfunction` before showing it and guard tEditor entry; route destructive lifecycle values to the controlled stop/reset contract rather than permitting even an event admin to accidentally wipe an attempt.

`F_main.mcfunction:143` gives creative players editor controls unless restricted/Realms; guard `Fadmin_enter_editor.mcfunction` and editor trigger entry in tournament mode. Administrative OP/console capabilities remain a separate server trust boundary; datapack tags cannot restrain an operator who intentionally edits the world.

### Track selection and voting
`Fgame_logic/0/worldmap_choose_try.mcfunction:7–8` explicitly allows non-admin selection when no active admin exists. This fallback must not apply to tournament mode. Guard the actual `worldmap_choose` entry before mutations, plus `worldmap_choose_custom`, not just menu rendering. Allow only the verified preset writer permit for fixed sequence commits. Account for native calls where @s is W/track stand, not a human.

Mid-game vote is independent: `Fmid_game_vote/listen_for_votes.mcfunction:1` accepts mgVoteTrigger; final two lines call language `pass_restart` and `pass_lobby` on majority. Disable tournament vote mutation at `vote_in`/pass boundary and guard underlying restart/return_to_lobby. `Fgame_logic/0/_return_to_lobby.mcfunction:2` adds noskip2next then initializes lobby; intercept before this mutation to record controlled STOPPED rather than a natural track completion.

### Physical extras portals and alternate modes
`Fgame_logic/0/misc_lobby_happenings/_main.mcfunction:48–55` ejects non-admins from rooms, but lines 69–73 independently schedule alternate-mode initialization based on player coordinates. These commands switch executor AS W before scheduling, losing the initiating player. Add actor authorization before that AS W and guard actual initializer against tournament wrong-state execution:
- (1623,81,371): game_logic/6 Time Attack menu;
- (1627,81,371): game_logic/5 free roam;
- (1623,81,360): game_logic/10/_initialize_def custom track manager;
- (1627,81,360): game_logic/9 track pool;
- (1619,81,360): game_logic/11 GP editor / cancel existing GP.
Room barriers/ejection alone are not load-bearing permission checks. Guard credits success and game_logic/12 initialization too, because credits creates nine AI.

### GP editor and cancellation
`Fgame_logic/11/_initialize.mcfunction:4` cancels active GP by calling cancel_grand_prix. Guard BEFORE dispatch; `cancel_grand_prix.mcfunction:1–8` begins global messages/teleport/clear_points immediately. Route cancellation through controlled stop with captured interruption, never erase historical storage.

`Fgame_logic/11/gl11_menu.mcfunction:6–9` dispatches all online gpMenu1/gpMenu2 inputs without admin filtering. Actual mutators `triggers/gp_menu_1`, `_2`, `_3`, `_4` start with setblock mutations at line 1; guard there and consume unauthorized score. `_4` values 201–211 select per-track Save State, cloning into x=1589 at each slot, not harmless display controls.

Physical green/yellow/red checks near end of gl11_menu run as W. `buttons/green.mcfunction:3` calls start_grand_prix if gpNumber>=1; `buttons/red.mcfunction:7–10` erases slot blocks, zeroes gpNumber, resets gpRound, then clears all gpNo tags. These have no player executor to authorize reliably. In tournament mode block the actual mutators unless the preset/control adapter explicitly permits the specific operation; do not authorize based on nearest player. Also guard `start_grand_prix` entry: lines 32–35 clear points and delete/recreate gpPoints, so replaying it destroys a running result.

`gl11_set_order.mcfunction` invokes `click_map` as any player with right-click input near its end; guard click_map plus leaf writer operations under the same preset-write permit. Structure-void exit calls back_to_menu as W based on any player's held item; `gl11_menu` barrier exit calls `Fgame_logic/11/exit.mcfunction`, whose line 11 globally initializes lobby. Guard these global exits, not only editor admission.

### Save State / defaults / custom settings
Guard `Fgame_logic/0/options_signs/save_state_{load,save,delete,defaults,previous,next,loading}` wrappers, and actual macro functions `save_state_load_specific` / `save_state_save_specific`. `save_state_load_specific.mcfunction:1–6` already mutates #noLobbyReload/global saveState before calling language loaders; authorization must precede line 1. This function also restores `sprint_racer:round_sequence custom` from saved storage at lines 9–18.

For tournament-mode internal mutations, guard `Fgame_logic/0/save_state/load_block_state.mcfunction` and `handle_state_request` against unauthorized Save State injection; permit only explicitly intended template construction, not per-track preset loading. `_initialize:1–4` removes temporary states and can restore prior settings on handoff. Validate again after any permitted native restoration. Fixed six-slot tournament presets should have no Save State side effects.

`Fgame_logic/0/round_sequence/handle_button_press.mcfunction:1–7` is an existing good pattern: execute on target, check actual clicker admin, clear interaction, then early return. Replace/reinforce its tag check with authoritative UUID access and lock sequence modifications; preserve its actor-context pattern. Do not block all interaction entities: race position calculator also uses zero-sized interactions.

Custom AI/cheat triggers: `Fgame_logic/0/misc_lobby_happenings/cheats_room.mcfunction:26–27` dispatch cl_trigger and ca_trigger as all score-bearing players, not only an admin in the room. Guard these leaf trigger functions before first score/block changes and consume score on rejection. ca_trigger modifies customAIset/customAIdiff/customAIteam at lines 7–14. tTrackEditor dispatcher only checks gameState=10 and non-spectator (`Fboq/trigger_track_editor.mcfunction:1–10`), so guard it too.

### Free roam and player membership
Free roam exit `Fgame_logic/5/gl5_main.mcfunction:81` invokes end_fr on any matching item; `end_fr.mcfunction:11` initializes global lobby. Guard end_fr and mode admission, leaving ordinary race checkpoint-reset item logic (`game_logic/1/reset/player_use_reset`) intact.

Membership cannot be inferred from playing. `Fgame_logic/0/gl0_main.mcfunction:11–18` automatically tags all non-forcespectate, non-AFK players playing. Ensure unauthorized/late/wrong-group users stay forcespectate and cannot clear it via `Finventory_check/inventory_controls/become_player.mcfunction:4–6`. That function directly calls mid_game_spec/join_success in gameState 1..3. `join_logic/mid_game_spec/join_attempt.mcfunction:1` only checks specJoinTime; it has no roster check. Guard both join_attempt and join_success. Native join_success resets finished and lap/check to initial values (lines 22–35), so do NOT allow a previously finished entrant to rejoin and earn another finish. Whether an unfinished disconnected entrant may restart from lap 1 is unresolved policy: retain facts and mark review rather than pretending seamless resume.

## 4. Exact event-capture and freeze hooks

### A. Successful track start
Do NOT mark started at `game_logic/1/_initialize` (sets gameState=1/gameTime=-50 before load success), GP editor start, or preset load. Actual GO block is `Fgame_logic/1/start_countdown.mcfunction:71–98`, all gated `gameTime=160`. Add `execute if score @s gameTime matches 160 run function xdu_race:results/track_started` after native GO setup (e.g. after new_spawnpoint at end). At this point verify W gameState=1, native gpRound equals expected 1–6, chosenTrack matches preset, Standard Race mode, no init failure, locked settings and zero AI.

Function must be idempotent by attempt+slot, NOT 'called only once'; normal and halftick echo paths both invoke start_countdown (`gl1_main_standard_race:35`, `gl1_main_standard_race_echo:17`). Capture planned roster independently, and record actually started online players with UUID plus native playing status. Missing planned players remain explicit DNS/pending-policy rows, never disappear. Fixed-roster membership is the authoritative selection; activeplayer/gamemode alone is unsuitable.

### B. Finish event / raw award
`Fgame_logic/1/finish_lap.mcfunction:37` dispatches player_finish when lapCalc>=1. In player_finish:
- lines 1–3 copy controller clock to storedTimeMin/storedTimeSec/storedTimeMsec;
- line 10 adds finished; line 11 normally switches @s to spectator;
- line 39 sets @s finishPos; line 40 increments global next finish position;
- lines 52–55 copy current controller addPoints, clamp to >=1, decrement controller award.
Insert `function xdu_race:results/finish` immediately AFTER line 55 and before finish music. Executor is the finishing player, already a spectator. Copy UUID and raw `finishPos`, raw `addPoints` as award, stored time components, server timestamp, current attempt/slot. Do not filter gamemode, team spectator, or activeplayer. Do not derive award from rank: native initial award comes from count at initialization (`_initialize:194–197`) and AI initialization can increase it; capture actual awarded value. Capturing only at end of track loses offline finishers.

### C. Track close / unresolved entrants
`Fgame_logic/1/end_game_logic.mcfunction:15–23` increments timeOut, resets it if any playing !finished human remains, sets timeRemaining=-1 after 60 ticks without such players, then invokes end_sequence. Timeout is also possible. `end_sequence:6` clamps gameTime to 100000; insert close-once capture immediately after it, gated gameTime=100000, before line 16 disables AI and line 17 makes EVERY online player spectator. Capture close reason/time, planned roster's remaining nonfinish states, and any AI contamination. This is race closed, NOT score-settled/final GP.

### D. Native GP award settlement
Correct cumulative-score commit is NOT `game_logic/1/give_points`. `Fgame_logic/1/end_sequence.mcfunction:31` calls `load_saved_points` at gameTime=100120 for non-team mode. `Fload_saved_points.mcfunction:10` loads gpPoints into dummyPoints; line 14 immediately performs `gpPoints += addPoints` AS @a. Add a tournament capture hook directly after this function call at end_sequence:31, or after the commit line with strict race-phase guard. The end_sequence callsite is preferable: load_saved_points is called again at podium setup, so a hook inside it cannot imply one track settlement unconditionally.

Snapshot actual gpPoints for every online authorized entrant after the commit, including finished spectators. For offline roster rows either read the existing named scoreboard holder using the previously verified start name, or retain the last observed total plus explicit unobserved flag; never fabricate an added award. Record per-player 'native commit observed' separately from globally 'commit phase reached'.

Native visual tally then runs `L_dlc_2/gameplay/race_end/increment_points.mcfunction` from end_sequence:36 at gameTime=100160. It drains addPoints into points for `@a[tag=playing]` and rewinds W gameTime by 4 until online pending awards finish (plus AI pending awards). This is why addPoints MUST already be captured. The nearby `Fgame_logic/1/give_points.mcfunction` is not the called race-end function and even uses a different 11-point step; do not patch that unused-looking helper instead of the actual call.

### E. End-of-track handoff and final freeze
Add a handoff hook immediately BEFORE `Fgame_logic/1/end_sequence.mcfunction:42` (`gameTime=100260.. → game_logic/0/_initialize`). At this point native award animation has passed. The hook closes settlement evidence, preserves cumulative totals, and, for completed slot 6, freezes the six-slot attempt if required facts are valid. If offline awards were not natively applied, distinguish completed lifecycle from pending-judge results; do not invent a rank. On failed validation stop automatic progression, do not merely return from a child hook and then allow the parent initializer call to run.

This is the last clean hook while native gpRound still denotes the just-completed track. `Fgame_logic/0/_initialize.mcfunction:25` calls grand_prix_decide_if_skip; `grand_prix_decide_if_skip:9` increments gpRound. `_initialize:102` removes finished tags, line 125 tests gpRound>gpNumber to add ceremony, line 133 calls game_logic/4/_initialize.

Final-GP extra safety hook at entry `Fgame_logic/4/_initialize.mcfunction` can assert tournament ledger already has six closed/settled slots and freeze if needed, BEFORE podium code resets finish positions. `game_logic/4/_initialize_for_real:2–6` can immediately call end if no currently ONLINE player has dummyPoints>0; thus waiting until podium animation is visible misses all-offline/no-points cases. It resets @a finishPos at line 48. `Fgame_logic/4/end.mcfunction:2` resets gpRound, lines 9–10 delete/recreate gpPoints, and line 18 clears points. End is too late as the first capture boundary; guard it only to ensure frozen historical storage exists before allowing native presentation cleanup.

Preserve native podium presentation if desired; independent tournament GP_FINISHED storage stays frozen even if native HUD scores are cleaned afterward. Disable grandprixloop and gate all subsequent start/ready entries so no seventh map or fresh GP can run until explicit archived reset.

## 5. UUID/name/storage design and offline loss facts

Proven UUID operation already used by release: `Fgame_logic/1/position_calc/improved/player_calc_prep.mcfunction:11` does `data modify storage sprint_racer:player_pos_calc uuid set from entity @s UUID`. Reuse this native form for an independent `xdu_race` storage, not transient native storage. Read scoreboard numbers using `execute store result storage ... int 1 run scoreboard players get @s <objective>`. Use `time query gametime` for an actual server-tick timestamp; native currentTime/gameTime are presentation/lifecycle counters and the latter jumps to 100000/rewinds during settlement.

Name caveat: player entity CustomName is NOT established here as an account-name source. Searches found AI name macros and track CustomName copying, not a reusable player-name extraction implementation. Safe design is imported UUID/name roster plus at-start verification that the named online entity has the expected UUID, then snapshot that verified name as name_at_start. If player renamed since import, explicitly reject or refresh the verified identity before start. Do not store an unresolved `{selector:"@s"}` component and call it an immutable name. A new resolved-text/profile extraction mechanism needs its own 26.2 runtime proof.

Proposed event-storage model (design, not current implementation): immutable historical attempts keyed event/GP-round/attempt/group; six planned slot records; UUID-keyed participant rows created from the planned roster before start. Store started_at, finished_at, finish_pos, award, clock components, observed native_total, native_commit_seen, track_close/settlement status, connectivity facts and judge-review flags. Deduplicate all event writes by full key; one revision increment per logical fact/transition, not per tick/status query. Preserve frozen attempts on stop/reset/reload; current state pointers must not overwrite them.

Actual offline hazards:
1. `Fload_saved_points.mcfunction:14` only visits @a. Finisher leaves before gameTime=100120: native gpPoints does NOT receive that award at that commit. Keep captured raw award and mark native settlement missing/pending review. Do not silently add the award to an exported 'native' total.
2. `Fjoin.mcfunction:38` resets ALL player score objectives, so a rejoining finisher loses addPoints and finishPos, and line 70 removes finished. Native preserves gpPoints only via W scratch at lines 14–15 and restoration at 196–198. This does not restore a pre-commit award. Independent storage is mandatory; using an xdu per-player scoreboard alone is insufficient.
3. Last-online reconnect invokes `join_solo` at join:170. `Fjoin_solo.mcfunction:1–3` resets random cooldowns, roundNumber and readyState; its final line clears points. Then `join_logic/in_game_no_players.mcfunction` unconditionally calls lobby initialization. Tournament mode must bypass these lifecycle-reset side effects, retain membership/history, and enter an explicit continuity/review state if resume cannot be proven.
4. `Fgo_afk.mcfunction:3` removes playing, and resets points/racePosDisplay later. Native end condition can consequently terminate a race with no playing unfinished players even though planned roster members are offline/AFK. Capture tracks against stored roster; distinguish DNF/disconnected/AFK facts with pending judge review.
5. Ordinary finish already turns the human spectator at player_finish:11. Using `@a[gamemode=!spectator]`, `@e[tag=activeplayer]`, or current team to collect results loses successful finishers even before disconnect.
6. `game_logic/4/end` deletes gpPoints for offline score holders too. Exporting current scoreboard after ceremony cannot recover a GP. Frozen storage must precede resets.
7. Server crash can occur before Minecraft saves storage. An in-flight attempt on new boot is continuity-unknown/ERROR pending review, not proof of uninterrupted settlement. Read-only export cannot repair this with save-all or reconstruction.

## 6. Recommended small integration order and acceptance boundaries

1. Integrator owns all shared upstream patches. Add independent storage/access functions; hook join tail and boot; enforce UUID whitelist and roster membership. Do not put persistent event truth on resettable player objectives.
2. Lock actual setting/control mutators listed above; actor-aware guards for player-triggered entry, explicit adapter permit for W/console/scheduled mutation. Remove no-admin fallback and close physical button/portal paths. Leave gameplay carrotInput, movement, items, checkpoints and race-reset item paths alone.
3. Enforce zero AI at configuration + activation/spawn boundaries, with contamination visible. Disable one-player Time Attack switch and credits/alternate-mode entry in tournament mode.
4. Hook GO, finish, close, native commit and handoff; freeze before native cleanup. Preserve raw award separately from gpPoints so offline-native loss is not concealed.
5. Explicit pending judge review is appropriate for offline pre-settlement loss, unresolved DNF/DNS/reconnect and disputed ranks; do not invent external points or ties policy.

Still UNPROVED and required runtime scenarios: both proxy UUIDs match backend UUIDs; first join/rejoin/revocation; every prohibited sign/trigger/physical button path with no admin online; normal items/checkpoint reset unaffected; one-human Standard Race stays gameState=1 with zero AI; disconnect before finish and after finish-before-commit; all-offline final ceremony; six consecutive GO/close/commit/handoff events and no seventh start; halftick mode and #getOnWithIt timing; repeated callbacks/export idempotency; boot continuity and injected AI-settings fail-closed behavior. No multiplayer or permission acceptance claim is made by this report.
