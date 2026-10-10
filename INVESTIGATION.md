# Melee animation investigation

Investigated 2026-10-10 at source commit `79b13a32467f7c4f91d6f831f0b9f891b7fb1146`. This report describes the actual checkout and the code paths inspected. Line references refer to that snapshot and may move as the code changes.

## Findings

**The repository contains the code that selects, loads, evaluates, and renders the requested animations. It does not currently contain their model, texture, or keyframe assets.** We can identify the results archives, costume tables, and relevant gameplay states from source, but cannot play the animations or certify their exact lengths and loop seams until the game files are supplied.

| Requested asset | What was found | What still needs game data/runtime verification |
| --- | --- | --- |
| Three victory animations per character | Results archive table; deterministic variant selection; demo constructor and motion IDs | Nested clip public names, durations, appearance, scripts/props, and any natural looping section |
| Loser clapping for every character/costume | Results variant 4, demo animation 9, actual costume enumeration, and live panel rendering | Keyframes, loop flags/range, costume appearance, and visual seam quality |
| Taunt / forward smash | Common and character-specific action entries, state-to-animation mappings, and scripts | Actual clip roots, supported angle/facing variants, props/effects, and capture timing |
| Hit / tumble / ground animations | Extensive reaction, launch, tumble, knockdown, prone, getup, roll, and tech states | Clip data and scenario-dependent motion/physics/transition behavior |

The user's clarified costume requirement is: **record a requested action for every actual costume variant of that character**. Counts vary. The source tables here list 4, 5, or 6 costumes for selectable roster entries; do not impose a fixed count or treat each variant as an arbitrary recolor.

## 1. What is in this checkout?

`orig/GALE01/files/` and `orig/GALE01/sys/` contain only `.gitkeep`. Recursive inspection found no `.dat`, `.usd`, `.dol`, `.iso`, or `.gcm` files in this checkout. There are no extracted character models, textures, or playable animation curves available locally.

The expected inputs are defined by:

- [config/GALE01/config.yml](config/GALE01/config.yml), lines 1-5: original `sys/main.dol`, under `orig/GALE01`, SHA-1 `08e0bf20134dfcb260699671004527b2d6bb1a45`.
- [config/GALE01/dat.yml](config/GALE01/dat.yml): archive directory `orig/GALE01/files`, matching `*.dat`.
- [.gitignore](.gitignore): original extracted files and executable/build outputs are ignored.

GALE01 is the configured version; identify the user's actual executable revision by its hash, rather than assuming the game ID alone guarantees compatible offsets and data. Extraction of local game data is the immediate prerequisite for rendering. A complete extracted files directory is more useful than only the executable.

The upstream goal is matching C reconstruction of the PowerPC program, as described in [docs/getting_started.md](docs/getting_started.md). That does not make this checkout an asset bundle or a desktop animation player, and this investigation did not measure overall decompilation completeness.

## 2. Where the results animations come from

### Results constructor and variant selection

[src/melee/gm/gm_1798.c](src/melee/gm/gm_1798.c), `fn_8017A67C`, starting at line 467, constructs a results fighter:

1. Determine winning/losing status from player or team standings.
2. Resolve a character-specific results archive through `gm_80160438` and load it.
3. Select the character and call `Player_SetCostumeId` with the requested costume ID.
4. Choose winner variant **0, 1, or 2**, or loser variant **4**.
5. Set per-character position/scale and call `Player_80036F34` to instantiate the demo fighter.

The winner selection checks B -> variant 0, Y -> variant 1, X -> variant 2, otherwise `HSD_Randi(3)` (lines 513-523; button masks in [controller.h](src/sysdolphin/baselib/controller.h)). An explicit override can select the variant. The field currently named `costume_override` is used here to override the **animation variant**, not the costume ID. A future export tool should select the variant explicitly and avoid random selection.

### Results archives and real costume counts

The complete archive map is `lbl_803D53A8` in [gm_1601.c](src/melee/gm/gm_1601.c), lines 399-508, used by `gm_80160438` at line 715. The selectable costume counts come from `lbl_803D51A0` at line 378 and `gm_GetNumCostumesForCKind` at line 4318. Internal counts are corroborated by `CostumeListsForeachCharacter` in [ftdata.c](src/melee/ft/ftdata.c), lines 219-254, and each fighter's costume-array declaration.

| Character | Results archive | Costume variants |
| --- | --- | ---: |
| Captain Falcon | `GmRstMCa.dat` | 6 |
| Young Link | `GmRstMCl.dat` | 5 |
| Donkey Kong | `GmRstMDk.dat` | 5 |
| Dr. Mario | `GmRstMDr.dat` | 5 |
| Falco | `GmRstMFc.dat` | 4 |
| Fox | `GmRstMFx.dat` | 4 |
| Mr. Game & Watch | `GmRstMGw.dat` | 4 |
| Ganondorf | `GmRstMGn.dat` | 5 |
| Kirby | `GmRstMKb.dat` | 6 |
| Bowser | `GmRstMKp.dat` | 4 |
| Link | `GmRstMLk.dat` | 5 |
| Luigi | `GmRstMLg.dat` | 4 |
| Marth | `GmRstMMs.dat` | 5 |
| Mario | `GmRstMMr.dat` | 5 |
| Mewtwo | `GmRstMMt.dat` | 4 |
| Ness | `GmRstMNs.dat` | 4 |
| Ice Climbers | `GmRstMPn.dat` | 4 paired variants |
| Peach | `GmRstMPe.dat` | 5 |
| Pikachu | `GmRstMPk.dat` | 4 |
| Pichu | `GmRstMPc.dat` | 4 |
| Jigglypuff | `GmRstMPr.dat` | 5 |
| Samus | `GmRstMSs.dat` | 5 |
| Sheik | `GmRstMSk.dat` | 5 |
| Yoshi | `GmRstMYs.dat` | 6 |
| Zelda | `GmRstMZd.dat` | 5 |
| Roy | `GmRstMFe.dat` | 5 |

This is **123 costume selections across 26 roster entries**, counting Zelda and Sheik separately and Ice Climbers as one paired entry. Three victories across all these selections would produce 369 character/variant/costume combinations; clapping adds 123. Those are catalog/batch targets, not a claim that 492 clips have been extracted or verified. Multiple formats can be encoded from each rendered sequence.

### Demo motion mapping

The constructor dispatch table `on_create_fighter` is in [ftdemo.c](src/melee/ft/ftdemo.c), line 40. Its callbacks enter these states:

| User-facing action | Results constructor variant | Callback | Numeric demo state | Demo animation ID |
| --- | ---: | --- | ---: | ---: |
| Victory 1 | 0 | `ftCo_800BECB0` | 0 | 0 |
| Victory 2 | 1 | `ftCo_800BED88` | 2 | 2 |
| Victory 3 | 2 | `ftCo_800BEF04` | 5 | 5 |
| Loser clapping | 4 | `ftCo_800BEFD4` | 9 | 9 |

Sources: [ft_0BEC.c](src/melee/ft/ft_0BEC.c), lines 55, 78, 102; [ft_0BEF.c](src/melee/ft/ft_0BEF.c), line 9; and `ftData_803C52A0` in [ftmotionstates.c](src/melee/ft/ftmotionstates.c), line 3887.

These callbacks use enum labels such as `ftCo_MS_DeadDown`, `DeadRight`, `DeadUpStarIce`, and `DeadUpFallIce`. **They are results motions in this context.** `ftDemo_CreateFighter` switches the fighter to the separate 14-entry demo state table and `ft_data->x14` motion data (`ftdemo.c`, lines 66-70). Reusing an enum's numeric value does not mean the ordinary death animation should be loaded. Results variant, state ID, and animation ID must remain separate in the catalog.

### How a results clip is loaded

Mario's [ftmariostrings.c](src/melee/ft/kinds/ftMario/ftmariostrings.c), lines 26-31, supplies the public name `ftDemoResultMotionFileMario`. Each fighter has equivalent demo string tables, collected through `ftData_803C2468`.

The source loading chain is:

```text
GmRstMMr.dat
  -> ftDemo_SetArchiveData(..., result index 0)
  -> public ftDemoResultMotionFileMario (packed byte region)
  -> ftData_80085B98: use ftData.x14[animation ID]
  -> nested archive at packed-region base + x4 offset, length x8
  -> HSD_ArchiveParse
  -> public name x0 -> FigaTree
  -> fighter joint/animation evaluator
```

See [ftdemo.c](src/melee/ft/ftdemo.c), `ftDemo_SetArchiveData`, line 134; [ftdata.c](src/melee/ft/ftdata.c), `ftData_80085B98`, line 1701, and the nested loading routines starting at lines 1734 and 1786. Results constructors preload demo entries 0-9, but which additional records/scripts are used for transitions must be checked against the actual data.

The result public is a **packed container**, not a single ready-to-render skeletal animation. [config/GALE01/dat_symbols.txt](config/GALE01/dat_symbols.txt), line 69, currently types `ftDemo*MotionFile*` as raw bytes. Exact nested public names, offsets, sizes, frame lengths, and flags are in the absent assets; do not invent them from a naming convention.

## 3. Costumes are separate from action selection

`ftDemo_CreateFighter` calls `ftData_80085820` to load the selected costume before constructing its joint hierarchy. The loader in [ftdata.c](src/melee/ft/ftdata.c), line 1593, uses `ftData_803C2360[kind][costume_id]` to select a filename, joint public, and optional material-animation public. The global per-fighter string table is at line 1356. [types.h](src/melee/ft/types.h), lines 1161-1173 and 1207-1211, defines the costume records and their count.

Concrete Mario mapping from [ftmariostrings.c](src/melee/ft/kinds/ftMario/ftmariostrings.c):

| Costume ID | Model archive | Joint public |
| --- | --- | --- |
| 0 | `PlMrNr.dat` | `PlyMario5K_Share_joint` |
| 1 | `PlMrYe.dat` | `PlyMario5KYe_Share_joint` |
| 2 | `PlMrBk.dat` | `PlyMario5KBk_Share_joint` |
| 3 | `PlMrBu.dat` | `PlyMario5KBu_Share_joint` |
| 4 | `PlMrGr.dat` | `PlyMario5KGr_Share_joint` |

The corresponding `*_Share_matanim_joint` names are listed beside the joints. `PlMr.dat` contains fighter data under `ftDataMario`; `PlMrAJ.dat` is the ordinary gameplay motion file. A chosen action can be paired with each costume using these tables, but actual joint compatibility and appearance still require asset validation.

Important exceptions:

- **Mr. Game & Watch:** all four costume entries use `PlGwNr.dat` and the same joint in [ftgamewatch.c](src/melee/ft/kinds/ftGameWatch/ftgamewatch.c), lines 483-489. `ftGw_Init_OnLoad` applies `x4_GAMEWATCH_COLOR[fp->costume_id]` at line 539. A filesystem glob or filename deduplication would miss three intended variants.
- **Ice Climbers:** `Player_80036E20` loads both Popo and Nana result roots, and `Player_80036F34` constructs their entities in [player.c](src/melee/pl/player.c), lines 2027 and 2054. `GmRstMPn.dat` supplies `ftDemoResultMotionFilePopo` and `ftDemoResultMotionFileNana`; their models/costumes remain separate internal records. A paired export must preserve the game's costume relationship and relative transforms.
- **Zelda/Sheik:** the results constructor selects the final form from match data (`gm_1798.c`, line 490). A direct asset export should expose the requested form explicitly.
- **Visibility/accessories:** [ftparts.c](src/melee/ft/ftparts.c), line 515, selects per-costume visibility rows, with default-row fallbacks. Some differences are geometry/accessory or runtime material behavior rather than only texture changes.

External roster `CharacterKind` and internal `FighterKind` are different enumerations; their mapping is in [player.c](src/melee/pl/player.c), starting at line 36. Do not use a roster index directly to index internal fighter tables.

## 4. How the results screen constructs the little squares

**The losing characters are live 3D fighters rendered into images used as panel textures. They are not stored as pre-rendered clapping sprites or videos.**

[gm_1798.c](src/melee/gm/gm_1798.c), `fn_80179990`, starting at line 134, selects a player's camera. For losers, it renders the fighter, copies the embedded framebuffer into an image buffer, and points the results-panel texture objects at that image (lines 162-191). Winners' final poses can be copied once after `ftLib_IsFramesRemaining` becomes zero (lines 194-213). The latter is evidence that some results presentation holds a finished pose; it is not proof that an entire victory sequence is cyclic.

Camera setup is in `fn_8017A318` at line 366 and the larger winner-camera path `fn_8017A078` at line 316. [gmresultplayer.c](src/melee/gm/gmresultplayer.c), around lines 38, 218, 355, and 384, contains character scale, framing, and camera-offset data. Mr. Game & Watch receives different facing setup in the constructor.

Full scene initialization is in [gmresult.c](src/melee/gm/gmresult.c), `gm_Scene_Results_OnEnter`, line 1727, with fighter/camera setup around line 1810. Panel/film roots `pnlsce` and `flmsce` load from the basename `GmRst` around line 1695. The localized filename resolver in [lbfile.c](src/melee/lb/lbfile.c), line 57, can choose `.usd` or `.dat`; preserve the selected language/revision in the asset manifest. Results text data also loads `SdRst.dat` / `SIS_ResultData` (`gmresult.c`, line 1482).

Two useful products follow from this:

1. **Isolated character assets:** evaluate the same motions/costumes and render with configurable camera, resolution, and background. No need to inherit the original small panel resolution.
2. **Results-scene recreation:** also reproduce cameras, lights, character placement/scales, team behavior, framebuffer-to-panel composition, UI assets, and timing.

The first is the smaller first milestone. The original scene is useful as a motion/appearance reference even before its interface is rebuilt.

Victory setup also creates props: Fox's blaster, Dr. Mario's pills, and Ness's bat appear in [ft_0BEC.c](src/melee/ft/ft_0BEC.c). Rendering only animated bones and the main mesh would omit these. Character initialization, scripts, part animation, and secondary dynamics can affect results fidelity too.

## 5. Ordinary actions: taunt and forward smash

Ordinary fighters use common/character-specific motion-state tables and `ftData.xC`; results fighters use the separate demo table and `ftData.x14`. `MotionState.anim_id` selects a motion record, not necessarily the same numeric ID as the action state.

The common mappings below are source-confirmed in [ftCommon/forward.h](src/melee/ft/kinds/ftCommon/forward.h) and [ftmotionstates.c](src/melee/ft/ftmotionstates.c):

| Action | Motion state / ID | Animation / ID |
| --- | --- | --- |
| Taunt facing right | `ftCo_MS_AppealSR` / 264 | `ftCo_SM_AppealSR` / 239 |
| Taunt facing left | `ftCo_MS_AppealSL` / 265 | `ftCo_SM_AppealSL` / 240 |
| Forward smash high | `ftCo_MS_AttackS4Hi` / 58 | `ftCo_SM_AttackS4Hi` / 60 |
| Forward smash slightly high | `ftCo_MS_AttackS4HiS` / 59 | `ftCo_SM_AttackS4HiS` / 61 |
| Forward smash neutral | `ftCo_MS_AttackS4S` / 60 | `ftCo_SM_AttackS4` / 62 |
| Forward smash slightly low | `ftCo_MS_AttackS4LwS` / 61 | `ftCo_SM_AttackS4LwS` / 63 |
| Forward smash low | `ftCo_MS_AttackS4Lw` / 62 | `ftCo_SM_AttackS4Lw` / 64 |

Forward-smash mappings start around `ftmotionstates.c`, line 772; neutral smash at line 794; taunts at line 3038. Not every character has every angle/facing variant. Read the character's actual motion entries rather than manufacturing missing variants.

### Loading a gameplay clip

The normal chain is fighter `Pl??.dat` -> `ftData.xC[animation ID]` -> packed `Pl??AJ.dat` offset/size -> nested archive -> named `FigaTree`. [ftdata.c](src/melee/ft/ftdata.c), line 1659, resolves the ordinary motion file; subsequent loaders parse its individual archives and retrieve the named public. The packed-file alignment/parser is already implemented in [tools/dat-cli/src/interop/hsd.rs](tools/dat-cli/src/interop/hsd.rs), including consecutive archives padded to 32-byte boundaries.

`Fighter_WaitAnimData`, in [types.h](src/melee/ft/types.h), line 986, holds the public name `x0`, offset `x4`, archive size `x8`, subaction script `xC`, flags `x10_animCurrFlags`, and runtime resolved location `x14`. These values are supplied by the assets. No exact ordinary taunt/smash clip public name was established from the checked-in source alone.

### Capturing the action faithfully

A standalone importer can show the selected skeleton motion. To recreate the visible gameplay action, it may also need the action entry, subaction script, character callbacks, items, effects, material/visibility changes, and movement.

- [ftCo_AppealS.c](src/melee/ft/kinds/ftCommon/ftCo_AppealS.c), line 52, dispatches Young Link and Dr. Mario to special taunt handlers; line 75 selects left-facing animation only if that variant exists.
- Young Link uses character states 342/343, but taunt animation IDs 239/240. His [ftclinkappeals.c](src/melee/ft/kinds/ftCLink/ftclinkappeals.c) creates/removes the milk item.
- Dr. Mario uses character states 341/342 with the same common taunt animation IDs. [ftdrmarioappeals.c](src/melee/ft/kinds/ftDrMario/ftdrmarioappeals.c) creates/removes a pill and uses random vitamin selection; deterministic capture needs fixed random state.
- [ftCo_AttackS4.c](src/melee/ft/kinds/ftCommon/ftCo_AttackS4.c), lines 145-170, dispatches special cases for Ness, Peach, and Game & Watch, configures Pikachu/Pichu effect callbacks, and selects available angled variants.
- [ft_0DF0.c](src/melee/ft/ft_0DF0.c), line 99, freezes animation rate during smash charging and restores it on release. Charge duration is an input/runtime choice.
- [ftaction.c](src/melee/ft/ftaction.c) executes scripts controlling effects, drawable visibility, texture/part animation, and charging (examples around lines 231, 687, 981, 992, and 1256).

For original rendering/behavior, a deterministic game/Dolphin fixture can select a fighter/costume, enter the correct action, step game ticks and dump frames. That capture harness does not exist in this checkout. For an asset-oriented standalone player, begin with source-compatible skeletal playback and add the above runtime features as needed, reporting unsupported features per clip. The same action/costume catalog can drive either renderer.

## 6. Hit reactions, tumble, knockdown, and ground states

These animation families are present in the state definitions. Common source-confirmed mappings:

| Behavior | Motion-state IDs | Animation IDs |
| --- | --- | --- |
| Tumble/falling after damage, `DamageFall` | 38 | 29 |
| High hit reactions, `DamageHi1-3` | 75-77 | 165-167 |
| Mid hit reactions, `DamageN1-3` | 78-80 | 168-170 |
| Low hit reactions, `DamageLw1-3` | 81-83 | 171-173 |
| Aerial hit reactions, `DamageAir1-3` | 84-86 | 174-176 |
| Knockback high/middle/low, `DamageFlyHi/N/Lw` | 87-89 | 177-179 |
| Knockback upward/rotating, `DamageFlyTop/Roll` | 90-91 | 180-181 |
| Ground impact, `DownBoundU/D` | 183 / 191 | 183 / 191 |
| Prone waiting, `DownWaitU/D` | 184 / 192 | 184 / 192 |
| Damage while prone, `DownDamageU/D` | 185 / 193 | 185 / 193 |
| Getup, `DownStandU/D` | 186 / 194 | 186 / 194 |
| Getup attack, `DownAttackU/D` | 187 / 195 | 187 / 195 |
| Forward getup roll, `DownFowardU/D` | 188 / 196 | 188 / 196 |
| Backward getup roll, `DownBackU/D` | 189 / 197 | 189 / 197 |
| Neutral tech, `Passive` | 199 | 199 |
| Forward/backward tech, `PassiveStandF/B` | 200-201 | 200-201 |
| Wall tech / wall jump / ceiling tech | 202-204 | 202-204 |

See [ftCommon/forward.h](src/melee/ft/kinds/ftCommon/forward.h) and [ftmotionstates.c](src/melee/ft/ftmotionstates.c), especially mappings at lines 552, 959, and 2147. Preserve the repository's spelling `DownFoward` when searching. U/D ground variants must be mapped to the corresponding body orientation using the game's logic.

The **pose clip** and the **whole knockback/ground event** are distinct:

- [ftCo_Damage.c](src/melee/ft/kinds/ftCommon/ftCo_Damage.c), lines 300-405, selects reactions from damage level, hurtbox location, grounded/airborne status, launch angle, element, percent, and sometimes RNG.
- Rotating launch additionally rotates `XRotN` using runtime velocity (`ftCo_Damage.c`, line 1053). Playing `DamageFlyRoll` alone omits this component.
- Launch states transition into `DamageFall` according to hitstun/animation conditions; collision can attempt a tech before knockdown (around lines 1032-1116).
- [ftCo_DownBound.c](src/melee/ft/kinds/ftCommon/ftCo_DownBound.c), lines 37 and 120, chooses the U/D impact variant using the hip transform. Later code transitions into prone wait/getup and handles input-selected attacks/rolls.
- [ftanim.c](src/melee/ft/ftanim.c), line 156, extracts animated root translation into movement offsets and adjusts joints. An in-place clip and world-motion capture need different explicit settings.
- Secondary bone dynamics run separately from baked keyframes: [fighter.c](src/melee/ft/fighter.c), around line 3050, and [ftdynamics.c](src/melee/ft/ftdynamics.c).

All these can become named exports across every costume. Full tumble or knockdown recordings additionally need a defined scenario: initial position/velocity/orientation, facing, floor contact, hitlag/hitstun, random state, and transition timing. Many reactions are naturally one-shot rather than seamless loops.

## 7. Animation structures and evaluation

| Layer | Local source | What it provides |
| --- | --- | --- |
| Archive format | [archive.h](src/sysdolphin/baselib/archive.h), [archive.c](src/sysdolphin/baselib/archive.c), [hsd.rs](tools/dat-cli/src/interop/hsd.rs) | Headers, relocation offsets, named publics, externs, and packed archive traversal |
| Motion records | [ft/types.h](src/melee/ft/types.h), [ftdata.c](src/melee/ft/ftdata.c) | Action/demo motion tables, script references, flags, packed offsets/sizes, and named tree resolution |
| Fighter motion tree | [lbanim.h](src/melee/lb/lbanim.h), lines 13-30; [lbanim.c](src/melee/lb/lbanim.c) | `FigaTree`, duration/type/flags, tracks-per-joint list, compressed `FigaTrack`s, and conversion to HSD animation objects |
| Skeleton/model | [jobj.h](src/sysdolphin/baselib/jobj.h), around line 129; [jobj.c](src/sysdolphin/baselib/jobj.c) | `HSD_Joint` hierarchy/transforms/drawables and joint animation updates |
| Time/loop state | [aobj.h](src/sysdolphin/baselib/aobj.h), [aobj.c](src/sysdolphin/baselib/aobj.c) | Flags, current/rewind/end frames, rate, first-play and stop/wrap semantics |
| Packed curve interpretation | [fobj.c](src/sysdolphin/baselib/fobj.c), lines 119-164 and 338-390 | Numeric decoding, constant/linear and spline/Hermite behavior |
| Mesh/material/texture behavior | [pobj.h](src/sysdolphin/baselib/pobj.h), [pobj.c](src/sysdolphin/baselib/pobj.c), [mobj.c](src/sysdolphin/baselib/mobj.c), [tobj.c](src/sysdolphin/baselib/tobj.c) | GX polygon, material, and texture formats/runtime behavior |

Important importer details:

1. Structural DAT values are big-endian with 32-bit offsets; FObj packed float/16-bit payload values are decoded little-endian in `fobj.c`, line 119. Raw blobs must retain their format-specific decoding.
2. `FigaTree.nodes` is a signed-byte tracks-per-joint list terminated by `-1`; total track count is the sum of the preceding counts. The type walk currently uses an extent annotation as a stopgap.
3. `ftAnim_8006F4C8` in [ftanim.c](src/melee/ft/ftanim.c), line 596, filters/remaps eligible fighter parts when installing tracks. Do not assume one animation node per every raw model joint.
4. Missing channels must preserve their proper defaults. Preserve curve interpolation, units, hierarchy order, scale compensation, joint flags, bind/envelope transforms, and rigid/weighted attachments.
5. Bone transforms alone do not reproduce visibility, texture/part animation, props, procedural motion, or GameCube material shading.

For the first Blender importer, sampling the source-compatible evaluator and baking the resulting poses is safer than translating curves into default Blender keyframes and hoping their interpolation matches.

## 8. What can loop perfectly?

The code supports looping, but **loop flags, exact periods, and visual continuity of the actual clips are currently unverified**.

Both tree flags and motion flags matter: [lbanim.c](src/melee/lb/lbanim.c), lines 100-102, applies `FigaTree.flags`, initializes rewind to zero, and sets end to `FigaTree.frames`. `fighter.c`, around line 1253, copies flags from the selected motion record; `ftanim.c`, around lines 404-420, can additionally enable `AOBJ_LOOP` from its loop bit. [aobj.c](src/sysdolphin/baselib/aobj.c), lines 91-163, establishes these semantics:

- Requesting an animation sets the requested start and first-play state.
- The first evaluation samples the start without advancing; later evaluations add the playback rate.
- If looping and `current >= end`, it wraps to `fmod(current - rewind, end - rewind) + rewind` when the range is valid.
- Nonlooping playback stops at `current >= end`.

Thus a source loop should normally be stored over **`[rewind, end)`**. Inspect the unwrapped terminal pose or endpoint limit before the loop wraps, then compare it with the start and inspect actual repeated frames. Calling the looping evaluator at `end` returns the start automatically, which would conceal a discontinuity. Do not force the last exported frame to duplicate the first. Last-to-first visual movement should look like an ordinary adjacent-frame transition.

Clapping is the best first loop candidate because the results screen continuously renders it, but its authored range and actual loop bit must be inspected in the assets. Victory callbacks inspected here initialize their selected motion and have empty animation callbacks; this source alone does **not** establish an intro-to-separate-loop transition for each victory. Inspect all related motion records/scripts and observe runtime behavior before defining victory loop sections.

If a victory/attack starts and ends in different poses, a repeated file will have a jump. Options are a naturally repeating subsection, one-shot export, or an explicitly edited transition. Reversing/crossfading a clip changes the original motion and should be an intentional mode. Root drift, visibility, material animation, accessories, and procedural bones/effects must be included in seam validation. Dynamic systems may need fixed initial state and warm-up cycles.

See [PLAN.md](PLAN.md) for the output policies, including GIF timing/palette limits and MP4 player-controlled looping.

## 9. Existing tools: useful foundations and limits

### `melee-dat`

[tools/dat-cli/README.md](tools/dat-cli/README.md) documents a Rust archive inspector/type walker using types from the decomp's DWARF build. It can inspect publics and structures, report coverage/type mismatches, generate sample data, and generate a native schema. It is not a model/animation viewer or MP4/GIF exporter.

The existing **normal motion validator** is immediately useful after extracting assets:

```text
cargo run -rqp melee-dat -- symbols check-motions --dol orig/GALE01/sys/main.dol --symbols config/GALE01/symbols.txt --files orig/GALE01/files
```

This command is documented existing functionality, but was **not run** during this investigation: its game inputs are absent and Cargo was not detected on PATH. It reads filenames/counts from the original DOL and verifies `ftData.xC` offsets, exact sizes, and public names against `Pl*AJ.dat`. It does not require MWCC, a full game build, DWARF, or a DTK executable for this check.

**It does not currently validate results demo `ftData.x14` or nested `ftDemo*MotionFile*` containers.** Those remain explicit follow-ups in [tools/dat-cli/TODO.md](tools/dat-cli/TODO.md). Add a demo validator before treating ordinary-motion validation as results coverage.

### Native archive interface

[tools/dat-cli/native](tools/dat-cli/native) supplies a C deserializer from big-endian/32-bit archive layouts to the game's host-native C types. Its schema comes from the source-derived type metadata. This is a valuable reuse option for a small extraction adapter.

It deliberately leaves keyframe streams, texels, GX display lists, scripts, and untyped pointers raw; archive externs are initially null. These need format decoding and, where required, cross-archive symbol resolution. Schema generation/toolchain setup is required. Successful descriptor conversion does not prove visual correctness.

### Existing root host build

The `native` preset in [CMakePresets.json](CMakePresets.json), lines 24-29, is a **32-bit host build**. [cmake/MeleeConfig.cmake](cmake/MeleeConfig.cmake) requires Aurora headers, defines `TARGET_PC`, excludes several files, and produces a static `melee` library. Notably `pobj.c` is excluded because of nontrivial GX array usage. The DWARF build in [cmake/Dwarf.cmake](cmake/Dwarf.cmake) tolerates unresolved symbols to produce type information.

There is no ready-made native animation player demonstrated by these builds. Building a desktop runtime would still need rendering, platform initialization, raw-format decoding, unresolved behavior, and pointer/layout issues addressed. It should not be assumed to be a simple compile-and-run step.

The initial environment had Python and CMake on PATH; Blender, FFmpeg, Dolphin, Rust/Cargo, Ninja, and Nix were not detected there. This is an environment observation, not proof those programs are absent from the machine. No dependencies were installed and no game/native build or rendering test was run.

## 10. Recommended next experiment and unresolved facts

The smallest decisive experiment is **Mario's default-costume clapping**:

1. Verify/extract the configured original game data locally.
2. Resolve `GmRstMMr.dat` -> `ftDemoResultMotionFileMario` -> demo motion 9 -> its named `FigaTree`.
3. Pair it with `PlMrNr.dat` and Mario's actual fighter/part data.
4. Decode/evaluate known poses with original semantics, then render a fixed-camera PNG sequence.
5. Measure the source period/seam and produce MP4/GIF from those same frames.
6. Repeat the action for Mario's other four actual costume IDs.

This proves the whole pipeline before expanding to all characters. The recommended Python/Blender/FFmpeg architecture and alternative adapters are compared in [PLAN.md](PLAN.md); [TODO.md](TODO.md) gives the ordered implementation steps.

Facts still requiring assets or runtime observation:

- Exact nested clip names, byte ranges, motion flags, frame lengths, and supported/shared/missing motions.
- Actual clapping loop periods and whether any victory has an authored cyclic section or transition.
- Skeleton/track compatibility and complete appearance for each costume.
- Required runtime props/scripts/dynamics for every results/action variant.
- Exact source tick-to-time conversion and desired output timing.
- Acceptable visual differences between a Blender material conversion and the game's GX rendering.
- A working importer or deterministic capture harness and the tool versions it supports.

The desired animations are discoverable through the decomp's loading and state code. The first implementation depends on recovering the local game assets and validating one small playable case; the investigation does not claim that source analysis alone has extracted or rendered them.
