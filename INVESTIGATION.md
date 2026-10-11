# Melee animation investigation

Initial source investigation and subsequent asset inspection: 2026-10-10, using source commit `79b13a32467f7c4f91d6f831f0b9f891b7fb1146`. The supplied ISO has now been extracted and checked. Line references refer to that source snapshot and may move as the code changes. Section 11 records the asset-backed findings and runnable inspection tools.

## Findings

**The ISO is extracted and verified; the requested victory/clapping/taunt catalog now covers all 26 selectable forms and 123 costume selections.** Zelda and Sheik are separate records. A working Mario prototype now skins the actual model, decodes textures, renders PNG/GIF animations, and generates an offline player. It is not yet a full roster/native-fidelity renderer. Section 12 records the latest playback and handoff state.

| Requested asset | What was found | What still needs game data/runtime verification |
| --- | --- | --- |
| Three victory animations per character | Archive and exact nested publics, durations, nonlooping victory clips, and separate `Win*Wait` assets | Rendered appearance, props/scripts, runtime transition behavior, and visual loop quality |
| Loser clapping for every character/costume | All 27 internal fighter `Lose` clips marked to loop; actual costume references validated | Full model/visibility/dynamics evaluation and visible seam quality |
| Taunt / forward smash | Common/special entries and scripts; exact Mario clips and supported angle/facing entries | Complete props/effects, action behavior, rendered appearance, and capture timing |
| Hit / tumble / ground animations | State families and actual Mario motion publics/durations | Scenario-dependent physics, collision, transitions, and visual playback |

The user's clarified costume requirement is: **record a requested action for every actual costume variant of that character**. Counts vary. The source tables here list 4, 5, or 6 costumes for selectable roster entries; do not impose a fixed count or treat each variant as an arbitrary recolor.

## 1. What is in this checkout?

At the initial source-only investigation these directories contained only `.gitkeep`. They now contain **1,209 game files and five system files**, totaling **1,430,666,499 bytes**, extracted by [extract_iso.py](tools/melee_anim/extract_iso.py). The game files include 838 `.dat` and 56 `.usd` files, all 26 character results archives, models, textures, sound/video files, and the required fighter data. The extraction manifest is local at `orig/GALE01/extraction-manifest.json`; each extracted file was reread and checked against its ISO extent by SHA-256.

The image identifies itself as **GALE01 disc revision 2**, title `Super Smash Bros Melee`. Its SHA-256 is `0de05981a34156b9cedcef73c73d4244ac05cf6149ab3c9cfed917698819e464`. The extracted original DOL SHA-1 is `08e0bf20134dfcb260699671004527b2d6bb1a45`, exactly matching the configuration. This establishes compatibility with the configured executable, not rendered fidelity.

The ISO, manifest, all 1,214 extracted game/system files, reports under `build/melee_anim`, and Python bytecode are Git-ignored. Git ignore checks explicitly covered every manifest path. Extraction reruns verified every output again and wrote zero game/system files. The ISO is opened read-only.

The expected inputs are defined by:

- [config/GALE01/config.yml](config/GALE01/config.yml), lines 1-5: original `sys/main.dol`, under `orig/GALE01`, SHA-1 `08e0bf20134dfcb260699671004527b2d6bb1a45`.
- [config/GALE01/dat.yml](config/GALE01/dat.yml): archive directory `orig/GALE01/files`, matching `*.dat`.
- [.gitignore](.gitignore): original extracted files and executable/build outputs are ignored.

GALE01 remains the configured version; continue checking the executable hash for replacement data. Extraction is complete, and the first Mario importer/CPU rendering proof is now working. Production rendering and other fighter runtime behavior are the next stages.

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

The result public is a **packed container**, not a single ready-to-render skeletal animation. [config/GALE01/dat_symbols.txt](config/GALE01/dat_symbols.txt), line 69, still types `ftDemo*MotionFile*` as raw bytes. The new focused Python inspector now validates actual nested public names, owning-container boundaries, exact sizes, frame lengths, and flags without requiring that general type walk to understand them. See section 11.

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

The corresponding `*_Share_matanim_joint` names are listed beside the joints. `PlMr.dat` contains fighter data under `ftDataMario`; `PlMrAJ.dat` is the ordinary gameplay motion file. All five Mario costume roots and material-animation roots have now been read successfully, with identical skeleton parent lists and local bind transforms. Full appearance still needs rendering and visibility/material setup. Across the rest of the roster, topology matches between a fighter's costumes, but local bind transforms often differ; preserve those defaults per costume.

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

`Fighter_WaitAnimData`, in [types.h](src/melee/ft/types.h), line 986, holds the public name `x0`, offset `x4`, archive size `x8`, subaction script `xC`, flags `x10_animCurrFlags`, and runtime resolved location `x14`. These values are supplied by the assets. Exact Mario examples are now confirmed: `PlyMario5K_Share_ACTION_Appeal_figatree` (180 source frames), `AttackS4Hi` / `AttackS4S` / `AttackS4Lw` with the same prefix/suffix (42 frames each). Mario's animation entries 61, 63, and 240 are empty; do not create nonexistent intermediate-angle or separate left-taunt clips.

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

The code supports looping, and **actual clip flags and periods are now inspected**. Full rendered continuity is still unverified. All 27 internal clapping clips are marked to loop, but neither a loop flag nor equal exact endpoint values guarantees continuity immediately before the wrap.

Both tree flags and motion flags matter: [lbanim.c](src/melee/lb/lbanim.c), lines 100-102, applies `FigaTree.flags`, initializes rewind to zero, and sets end to `FigaTree.frames`. `fighter.c`, around line 1253, copies flags from the selected motion record; `ftanim.c`, around lines 404-420, can additionally enable `AOBJ_LOOP` from its loop bit. [aobj.c](src/sysdolphin/baselib/aobj.c), lines 91-163, establishes these semantics:

- Requesting an animation sets the requested start and first-play state.
- The first evaluation samples the start without advancing; later evaluations add the playback rate.
- If looping and `current >= end`, it wraps to `fmod(current - rewind, end - rewind) + rewind` when the range is valid.
- Nonlooping playback stops at `current >= end`.

Thus a source loop should normally be stored over **`[rewind, end)`**. Inspect the unwrapped terminal pose or endpoint limit before the loop wraps, then compare it with the start and inspect actual repeated frames. Calling the looping evaluator at `end` returns the start automatically, which would conceal a discontinuity. Do not force the last exported frame to duplicate the first. Last-to-first visual movement should look like an ordinary adjacent-frame transition.

Clapping remains the first loop target. Mario's `Lose` is an 18-frame source loop; its precise terminal values match the start, but its pre-terminal limit differs in four finger channels (section 11). Actual results data also contains separate `Win1Wait`, `Win2Wait`, and `Win3Wait` assets. These are usable export targets, not proof that the original results scene automatically transitions into them: the inspected victory callbacks are empty, and winner-panel code can freeze the completed victory pose. Verify runtime behavior separately.

If a victory/attack starts and ends in different poses, a repeated file will have a jump. Options are a naturally repeating subsection, one-shot export, or an explicitly edited transition. Reversing/crossfading a clip changes the original motion and should be an intentional mode. Root drift, visibility, material animation, accessories, and procedural bones/effects must be included in seam validation. Dynamic systems may need fixed initial state and warm-up cycles.

See [PLAN.md](PLAN.md) for the output policies, including GIF timing/palette limits and MP4 player-controlled looping.

## 9. Existing tools: useful foundations and limits

### `melee-dat`

[tools/dat-cli/README.md](tools/dat-cli/README.md) documents a Rust archive inspector/type walker using types from the decomp's DWARF build. It can inspect publics and structures, report coverage/type mismatches, generate sample data, and generate a native schema. It is not a model/animation viewer or MP4/GIF exporter.

The existing **normal motion validator** is immediately useful after extracting assets:

```text
cargo run -rqp melee-dat -- symbols check-motions --dol orig/GALE01/sys/main.dol --symbols config/GALE01/symbols.txt --files orig/GALE01/files
```

This existing Rust command was **not run** because Cargo was not detected on PATH. It reads filenames/counts from the original DOL and verifies `ftData.xC` offsets, exact sizes, and public names against `Pl*AJ.dat`. It does not require MWCC, a full game build, DWARF, or a DTK executable for this check. The new Python inspector independently performs corresponding range/name checks over the supplied data; do not describe that as running the Rust tool.

**The Rust command still does not validate results demo `ftData.x14` or nested `ftDemo*MotionFile*` containers.** Those remain follow-ups in [tools/dat-cli/TODO.md](tools/dat-cli/TODO.md). The focused Python inspector added in this task now provides results-container validation and metadata inspection; it does not update the Rust type walker or general native schema.

### Native archive interface

[tools/dat-cli/native](tools/dat-cli/native) supplies a C deserializer from big-endian/32-bit archive layouts to the game's host-native C types. Its schema comes from the source-derived type metadata. This is a valuable reuse option for a small extraction adapter.

It deliberately leaves keyframe streams, texels, GX display lists, scripts, and untyped pointers raw; archive externs are initially null. These need format decoding and, where required, cross-archive symbol resolution. Schema generation/toolchain setup is required. Successful descriptor conversion does not prove visual correctness.

### Existing root host build

The `native` preset in [CMakePresets.json](CMakePresets.json), lines 24-29, is a **32-bit host build**. [cmake/MeleeConfig.cmake](cmake/MeleeConfig.cmake) requires Aurora headers, defines `TARGET_PC`, excludes several files, and produces a static `melee` library. Notably `pobj.c` is excluded because of nontrivial GX array usage. The DWARF build in [cmake/Dwarf.cmake](cmake/Dwarf.cmake) tolerates unresolved symbols to produce type information.

There is no ready-made native animation player demonstrated by these builds. Building a desktop runtime would still need rendering, platform initialization, raw-format decoding, unresolved behavior, and pointer/layout issues addressed. It should not be assumed to be a simple compile-and-run step.

The environment has Python, NumPy 2.2.4, Pillow 11.1.0, Node, CMake, and .NET. Blender/FFmpeg were not found in usual installation locations; Slippi Dolphin binaries were found under the user's Slippi Launcher `netplay` and `playback` directories. No dependencies were installed and no full game/native build or emulator capture was run. The CPU prototype has now rendered actual character frames using installed Python packages.

## 10. Recommended next experiment and unresolved facts

Extraction, descriptor/curve inspection, and the **rendered Mario clapping proof** are complete. The following sequence describes that proof and remaining production checks:

1. Use the verified model and clip references from the inspection reports.
2. Assemble Mario's default mesh, bind transforms, envelopes, textures, and correct drawable alternatives.
3. Apply the decoded `Lose` channels to the matching hierarchy, honoring part mapping, defaults, and HSD matrix rules.
4. Render known poses and compare them against a game/viewer reference.
5. Render the native 18-frame period, inspect the actual seam, and produce MP4/GIF from the same PNG masters. Any seam repair must be an explicit edited mode.
6. Repeat for Mario's other four costumes with shared framing and their actual model/material references.

This proves the whole pipeline before expanding to all characters. The recommended Python/Blender/FFmpeg architecture and alternative adapters are compared in [PLAN.md](PLAN.md); [TODO.md](TODO.md) gives the ordered implementation steps.

Facts still requiring additional implementation or runtime observation:

- Full pose/mesh/material correctness after combining the now-validated descriptors and curves.
- Visible seam quality, derivatives, and any procedural-state discontinuities; scalar endpoint reports are preliminary.
- Actual results runtime use of the authored victory wait clips and transition timing.
- Complete appearance, visibility/accessory selection, and behavior for every costume.
- Required runtime props/scripts/dynamics for every results/action variant.
- Exact source tick-to-time conversion and desired output timing.
- Acceptable visual differences between a Blender material conversion and the game's GX rendering.
- A working importer or deterministic capture harness and the tool versions it supports.

The supplied assets are now available and structurally validated. A focused Python path can read the models and evaluate scalar motion channels on this machine; the missing next component is model/pose assembly and rendering, not disc extraction or further machine-code disassembly.

## 11. Asset-backed follow-up and reusable tools

### Reproduce extraction and inspection

All commands below are implemented and were run against the supplied image. Run them from the repository root:

```powershell
python tools/melee_anim/extract_iso.py melee.iso
python -m tools.melee_anim.inspect_motions --output build/melee_anim/motions.json
python -m tools.melee_anim.inspect_models --catalog
python -m tools.melee_anim.inspect_results_scene
python -m unittest discover -s tools/melee_anim/tests -v
```

[extract_iso.py](tools/melee_anim/extract_iso.py) reads the raw GameCube filesystem table and system extents without disassembly. It validates the expected DOL before writing, checks filenames/paths/extents, protects differing existing files and symlinks/junctions, and records/verifies file hashes. `--list` is read-only; ordinary reruns verify and reuse matching files; `--overwrite` permits explicit replacement of differing managed outputs. Other DOL revisions require a separate output and `--allow-unverified`; do not use those files with these GALE01 tables.

[hsd.py](tools/melee_anim/hsd.py) is a narrow bounded DAT/DOL reader based on the existing decomp/tool layouts. It preserves relocated offset zero as a real pointer, distinguishes null offsets, and reads DOL globals by their checked-in symbol addresses. It does not implement the Rust type system, resolve arbitrary archive externs, or execute the game.

[inspect_motions.py](tools/melee_anim/inspect_motions.py) checks **8,011 nonempty ordinary motion references across 33 internal fighter tables**, including nonselectable fighters. It also reads **244 nonempty results motion references across 27 internal fighter tables in 26 archives**, including both Ice Climbers members. Shared references are retained. Each nested results archive is checked within its owning public's packed region, with exact size/public-name matching and packet decoding. The reports remain ignored because they contain extensive asset-derived metadata.

[motions.py](tools/melee_anim/motions.py) decodes compressed scalar tracks and provides a source-guided FObj state-machine evaluator with step, linear, Hermite, slope-only, delayed-start, and terminal behavior. It samples unwrapped channels for research; it has not been validated as a complete HSD character runtime or through rendered comparison.

### Actual results clips and periods

The actual assets contain `Win1` / `Win2` / `Win3` at demo animation IDs 0 / 2 / 5, separate `Win1Wait` / `Win2Wait` / `Win3Wait` at IDs 1 / 3 / 6, and clapping `Lose` at ID 9. Other entries include character-selection sequences. All initial victory clips are nonlooping. Most wait entries loop via motion flags; **Falco's 243-frame `Win3Wait` is not marked to loop**. Fox additionally has a 300-frame `Win2Wait2` in slot 4, which is empty for the other fighters. These details must remain data-driven rather than assumed from the name.

All `Lose` entries are loop-enabled. Periods below are **source animation frames**, not a measured video timebase:

| Character | Clapping period | Character | Clapping period |
| --- | ---: | --- | ---: |
| Captain Falcon | 80 | Young Link | 60 |
| Donkey Kong | 30 | Dr. Mario | 120 |
| Falco | 50 | Fox | 60 |
| Mr. Game & Watch | 30 | Ganondorf | 80 |
| Kirby | 160 | Bowser | 40 |
| Link | 60 | Luigi | 120 |
| Marth | 56 | Mario | 18 |
| Mewtwo | 130 | Ness | 15 |
| Ice Climbers: Popo and Nana | 30 each | Peach | 40 |
| Pikachu | 72 | Pichu | 144 |
| Jigglypuff | 320 | Samus | 20 |
| Sheik | 17 | Yoshi | 40 |
| Zelda | 40 | Roy | 56 |

Mario's exact nested examples, within the data region named `ftDemoResultMotionFileMario` (base offset zero):

| Demo ID | Public suffix after `PlyMario5K_Share_ACTION_` | Offset | Exact archive size | Source frames | Loop flag |
| ---: | --- | --- | --- | ---: | --- |
| 0 | `Win1_figatree` | `0x0000` | `0x25D6` | 120 | No |
| 1 | `Win1Wait_figatree` | `0xA360` | `0x0E3A` | 50 | Yes |
| 2 | `Win2_figatree` | `0x25E0` | `0x262A` | 120 | No |
| 3 | `Win2Wait_figatree` | `0xB1A0` | `0x0E5A` | 50 | Yes |
| 5 | `Win3_figatree` | `0x4C20` | `0x247E` | 120 | No |
| 6 | `Win3Wait_figatree` | `0xC000` | `0x0E1E` | 50 | Yes |
| 9 | `Lose_figatree` | `0x90C0` | `0x128A` | 18 | Yes |

Mario's `Lose` has 61 animation nodes, 47 animated nodes, 142 tracks, and 1,989 packed keyframe bytes. Its tree flags are zero; motion flags `0x40000000` enable the loop. Track channels cover rotation, translation, and scale. Its own subaction script is just the end command, so assembling correct appearance also requires generic initialization/part defaults rather than assuming the clapping script supplies them.

**Seam finding:** the focused evaluator returns matching scalar values at frame 0 and exactly frame 18, but the unwrapped limit just before frame 18 differs in four finger Y-rotation channels by approximately `0.084198` radians (4.82 degrees). The terminal key restores the start value; the looping AObj wraps before evaluating it. This exposes why exact endpoint equality can conceal a discontinuity. It is channel evidence, not a measured rendered defect: part visibility, matrix evaluation, and reference capture must determine its visible impact. Preserve a native mode and make any finger/seam correction an explicit edited mode.

### Actual model assembly and costume coverage

[inspect_models.py](tools/melee_anim/inspect_models.py) reads actual `ftMapping_list`, selectable costume counts, internal counts, and `ftData_803C2360` strings from the verified DOL. Its catalog validates **123 selectable jobs plus four Nana model records: 127 costume records referencing 124 distinct model archives**. Every referenced model file, joint public, and nonnull material-animation public was found and its skeleton traversed. This does not yet certify all their mesh/material behavior under animation.

Every participating internal fighter's parent hierarchy matches across its costumes. **20 of the 27 have differing local bind transforms between costumes**; applying one costume's entire bind pose to every other costume would be incorrect. Mario is a particularly simple first case: all five match in both hierarchy and local bind SRT.

Each Mario costume contains 61 joints, 59 drawable/material descriptors, 68 envelope-skinned polygon descriptors, 53 inverse-bind matrices, and 60 texture references: 58 CMPR and two C8. The decoded display lists contain 6,982 vertex corners across all drawable alternatives; that is not a count of vertices simultaneously visible. Weighted-envelope joint references and display-list matrix palette indices were checked. No archive externs or instance joints were present in these five model roots.

The model inspector also traversed all **124 unique costume model archives**, with no parser errors: 8,412 envelope polygon descriptors and 1,661 rigid/shared descriptors. Their texture references include CMPR, C8, C4, I8, RGB5A3, and I4. This establishes readable geometry/descriptor coverage, not rendered correctness. Run `python -m tools.melee_anim.inspect_models --all-models --output build/melee_anim/all_models.json` to regenerate compact summaries.

Mario's default root is at data offset `0x19400`. Its first polygon descriptor is `0xBE00`; positions are indexed 16-bit signed XYZ values with fraction 11 and stride 6, normals signed-byte XYZ with fraction 6 and stride 3, and UV0 signed 16-bit XY with fraction 13 and stride 4. The first position array starts at **data offset zero, relocated**, which is a valid pointer and must not be mistaken for null. The meshes' 257 total envelope-palette entries include 137 single-joint, 118 two-joint, and two three-joint entries; weight sums were within approximately `3e-8` of one. GX matrix index bytes map to palette entries by division by three.

HSD's skinning rules are not always the standard assumption that all raw vertices occupy one bind space. For unit-weight single-joint entries, source setup can use the joint's global matrix directly; mixed envelopes use weighted joint-global times stored envelope matrices. See `ftPartsSetupEnvelopeMtx` in [ftparts.c](src/melee/ft/ftparts.c) and `SetupEnvelopeModelMtx` in [pobj.c](src/sysdolphin/baselib/pobj.c). Normalize vertex coordinates according to their palette/corner before creating conventional Blender weights, and verify skinned positions against reference matrices.

The assembly path is now concrete:

```text
verified costume file + joint public
  -> parent hierarchy, local bind defaults, inverse-bind matrices
  -> DObj -> MObj/TObj -> textures, palettes, material state
  -> PObj -> GX attribute arrays + display-list corners
  -> envelope palette -> referenced joints + weights
  + fighter parts/visibility/default appearance
  + chosen FigaTree channels mapped through fighter-part rules
  -> evaluate joint matrices and skin/deform vertices
  -> Blender mesh/material/camera scene -> PNG frames -> video encoding
```

Reading all drawable meshes and showing them simultaneously is wrong: alternative hands/faces/other parts coexist in the model. `ftData.x8` visibility tables, generic state initialization, motion metadata/scripts, and character callbacks choose the appropriate alternatives. Preserve the game's matrix/part mapping, skinning, per-costume defaults, and CMPR/C8 texture decoding before judging the render.

Actual motion scripts reinforce that requirement. Link/Young Link clapping sets visibility group 1 to option 1; Roy sets group 2 to option 0; Popo/Nana set group 1 to -1. Luigi/Popo clapping includes texture-animation changes. Mario's victory scripts call a subroutine that changes texture-animation frames and also include sound/effect commands. The inspector reads bounded linear script prefixes and records call/goto pointers; it does not execute this control flow, spawn effects, or apply model/material changes.

Additional asset-confirmed cases:

- Mr. Game & Watch's four material colors are RGBA `(0,0,0,255)`, `(110,0,0,255)`, `(0,0,110,255)`, and `(0,110,0,255)`, with outline `(255,255,255,128)` and Z width approximately `0.01`. They share the same model file and remain four distinct costume jobs.
- Captain Falcon's costume 2 basename is `PlCaRe.`. The filename resolver selects `PlCaRe.usd` for US language and `PlCaRe.dat` for Japanese; both were extracted. A trailing-dot source basename is not an actual Windows filename and must be resolved before opening. Language does not add another costume ID.
- Ice Climbers' shared results archive contains separate nested Popo/Nana packed regions. Both were bounded and inspected independently; their costume pair is one selectable job with two model instances.

### Results scene assets are present too

[inspect_results_scene.py](tools/melee_anim/inspect_results_scene.py) reads `GmRst.dat` (476,574 bytes) and `GmRst.usd` (476,318 bytes), both exposing `pnlsce` and `flmsce`. Each panel scene has one model and two lights; each film scene has four models and two lights. Panel models have joint and material animation; the film models also reference material animation. These are scene assets to import later, not a substitute for fighter demo construction.

The stored panel/film camera descriptors use a 640x480 viewport/scissor, eye `(0,0,112)`, target `(0,0,0)`, near/far 1/5000, approximately 25-degree FOV, and aspect approximately 1.216667. These are UI scene cameras; individual fighter cameras are separately configured by `gmresultplayer.c` / `gm_1798.c`. Preserve the distinction and the source projection parameters rather than automatically forcing every camera to 4:3.

### What is proven now, and what is next?

Extraction, hashes, Git exclusion, actual costume references, skeletal topology, Mario mesh/texture/envelope metadata, results packed ranges/names, ordinary motion references, and compressed scalar-channel decoding have been checked. Synthetic tests exercise malformed inputs and format/loop edge cases without embedding game data.

A **Mario model/pose importer and CPU preview renderer** have now been implemented using these primitives (section 12). Blender remains the planned production renderer; the native decomp remains a reference or targeted adapter. Animated GIF/PNG previews exist; MP4 and exact game rendering have not been produced.

## 12. All-character taunts and first playable recordings

### Standard taunts are now cataloged for every form

The inspector resolves actual DOL motion-state callbacks instead of assuming every taunt uses one state. Its 53 taunt records comprise 40 unique standard clips, 12 Fox/Falco stage-taunt parts, and Nana's shared Popo clip record. All are authored one-shots, not source loops. Standard durations are source frames:

| Character | Frames | Character | Frames |
| --- | ---: | --- | ---: |
| Mario | 180 | Fox | 110 |
| Captain Falcon | 60 | Donkey Kong | 60 |
| Kirby | 60 | Bowser | 140 |
| Link | 100 | Sheik | 100 |
| Ness | 60 | Peach | 85 |
| Ice Climbers: Popo/Nana source | 60 | Pikachu | 100 |
| Samus | 70 | Yoshi | 80 |
| Jigglypuff | 100 | Mewtwo | 120 |
| Luigi | 70 | Marth | 93 |
| Zelda | 90 | Young Link | 200 |
| Dr. Mario | 85 | Falco | 115 |
| Pichu | 100 | Mr. Game & Watch | 60 |
| Ganondorf | 100 | Roy | 120 |

Captain Falcon, Donkey Kong, Kirby, Link, Ness, Peach, Pikachu, Samus, Yoshi, Jigglypuff, Zelda, Young Link, Pichu, and Ganondorf have separate right/left standard clips. Others select the right state when the left archive is absent while retaining facing sign -1. Dr. Mario uses custom states 341/342; Young Link uses 342/343; animation IDs remain 239/240. Nana can resolve the taunt through Popo while retaining Nana's own costume and part mapping. Zelda (90 frames) and Sheik (100) retain separate files and rigs.

Fox/Falco also have optional **Corneria or Venom** radio/stage taunts: states 370/372/374 right and 371/373/375 left, animation IDs 321/323/325 or 322/324/326. Their three parts are 25/307/65 frames and explicitly transition through character callbacks. Scene eligibility, radio state, and once-per-match logic are separate from ordinary taunts.

Runtime caveats remain concrete: Young Link's milk and Dr. Mario's randomized pill require item models/callbacks; Kirby cleans up copy state; Ganondorf creates an effect; Game & Watch changes model visibility. Static script traversal now records reachable subroutines and command-variable/texture/visibility fields, but does not execute timed gameplay behavior.

[catalog.py](tools/melee_anim/catalog.py) joins all this with actual costume records: **26 forms, 123 selectable costumes, 1,123 inventory jobs** including clap, three victory entrances, their primary waits, both standard-taunt facings, and optional stage sequences. Every standard clip's node count matches every mapped costume skeleton; this is structural compatibility, not a claim of complete runtime fidelity. Fox's extra `Win2Wait2` is present in the motion report but is not yet a separate inventory job.

### Actual playback/recording prototype

[export_model.py](tools/melee_anim/export_model.py) exports all five Mario costumes into neutral JSON plus 185 decoded PNG textures. Each has 61 bones, 52 selected meshes, 43 materials, 6,518 GX corners, and 4,718 nondegenerate triangles. It retains exact source palettes as well as converted bind geometry. [texture.py](tools/melee_anim/texture.py) decodes GX formats; CMPR uses the hardware's 3/8 interpolation/colored transparent pixels, and the hat requires authored repeat/mirror UV behavior. Pixel decoding references the emulator's [texture decoder](https://github.com/dolphin-emu/dolphin/blob/master/Source/Core/VideoCommon/TextureDecoder_Generic.cpp).

[preview.py](tools/melee_anim/preview.py) evaluates source channels, HSD scale/matrix rules, palette skinning, textures, depth, and approximate lighting, then writes PNG masters and GIFs. Mario's taunt uses type 0 scaling and intentionally grows around 2.25x; results use type 1. The renderer preserves the native finger-channel seam, rather than silently modifying the motion. Timed scripts/props/particles/dynamics/audio and exact TEV/reflection are not implemented.

The first pilot produced these outputs under `build/melee_anim/preview/mario` (subsequently expanded to all colors in section 13):

- Clapping in costume IDs 0-4: five 15-frame GIFs, each 300 ms at the explicit 50 fps / nominal 60 source-tick/s preset.
- Default costume victories 1-3: three one-shot sequences, 101 frames each including the terminal pose.
- Their separate wait clips: three looping sequences, 42 frames each.
- Default costume taunt: one 151-frame one-shot including terminal pose.

These 12 jobs have **655 PNG masters and 12 GIFs**. Source/output timing is recorded; it is not measured emulator timing. Waits are 0.84 s rather than nominal 50/60 s because of output-grid rounding, and one-shot taunt is 3.02 s including the terminal frame. Fix/disclose that policy before production encoding. GIF durations/loop metadata and manifest file counts were checked. Contact sheets show coherent skins/textures, costume colors, victory poses, and intentional taunt scaling.

Reproduce/open the pilot:

```powershell
python -m tools.melee_anim.catalog
python -m tools.melee_anim.preview_batch --action results-clap --costume all
python -m tools.melee_anim.preview --action victory1 --output build/melee_anim/preview/mario/costume_00/victory1_source
python -m tools.melee_anim.preview --action victory1 --section wait --output build/melee_anim/preview/mario/costume_00/victory1_wait
python -m tools.melee_anim.preview --action taunt --output build/melee_anim/preview/mario/costume_00/taunt_source
python -m tools.melee_anim.preview_gallery
```

Open local `build/melee_anim/preview/player.html` in a normal browser. It has clip/costume selection, play/pause, restart, repeat, scrubbing, and GIF links, with no server/CDN required. The browser connector returned no enabled browser, so the live UI was not driven; player control/timer logic and all frame links passed the Node test. Fifty-seven Python tests passed. All generated models/images/player data remain ignored.

### Stopping point and next implementation

The user requested an immediate handoff to a lighter model. See `AGENTS.md`'s immediate handoff and the top of `TODO.md`. First fix source culling, timing-grid/terminal hold, stale-frame handling, and owning-container bounds. Then add manifest-driven FFmpeg encoding/reference checks and extend renderer/runtime support by fighter family. `TODO.md` includes optional Blender and FFmpeg installation steps for later; no dependency installation was performed here. Do not re-extract or restart the completed catalog investigation.

## 13. Mario animation/color downloads

The next user request was to fill the missing costume variants for the other Mario animations and provide straightforward GIF saving. The implemented batch now supports the full matrix: clapping, taunt, victory entrances 1-3, and their three authored waits, each in Mario's five actual model costumes. Rendering uses the original costume models/textures rather than applying arbitrary tints.

`preview_batch --action all --section all --costume all --resume --jobs 3` generates/reuses those 40 jobs. Resume verifies complete intervals, model hash, size, FPS/camera settings, and exact PNG file sets. Extra stale frames are rejected rather than accidentally included in an encode. Existing clap outputs retain 320-square resolution; the other animations retain 256-square resolution unless `--size` overrides it.

`preview_gallery --require-all` checks the complete action/color matrix and builds the offline player and download packages. Animation and Costume have separate selectors. The selected GIF receives a descriptive filename such as `mario-victory2-source-costume-03-blue.gif`; an animation ZIP contains its five colors, and the full ZIP contains the entire collection. ZIP manifests record filenames, costume/action identity, and hashes. These packages contain generated GIFs/metadata and remain under the ignored `build/melee_anim/preview/downloads` directory.

The player's repeat control remains preview-only: saved GIFs retain their authored one-shot/loop behavior. Explicit wait-loop choices are available independently from victory entrances. The existing CPU shading/script/seam/timing limitations remain unchanged. Regression tests cover selected-color retention, GIF/ZIP link targets, unique saved color filenames, archive hash identity, complete action enumeration, and rejecting incomplete/stale resume data.

Completion checks passed for all **40 GIFs and 2,975 PNG masters**, with five distinct GIF hashes per animation/section. All eight per-animation ZIPs contain five color GIFs, and the full ZIP contains 40; filenames are unique and every stored hash matches its archive entry. GIF decoding, durations, authored loop flags, manifest/frame counts, and all 3,156 generated files' Git exclusion were checked. Sixty Python tests and the Node player/download tests pass. The browser connector is unavailable, so these results do not claim a live browser click test; the download attributes, filenames, paths, and bundle contents are verified.

## 14. Full roster and exact paused-frame downloads

The subsequent request expands that same eight-choice preview to **all 26 selectable character entries and their 123 actual costumes: 984 GIF jobs, 81,369 PNG masters**. Zelda and Sheik have separate selectors/models/motions. Ice Climbers include costume-mapped Popo and Nana in each of their four selections. Game & Watch has four separately rendered runtime colors despite a shared archive. This batch uses the standard right-facing taunt; left-facing/stage taunts and Fox's extra wait remain cataloged extensions. Wait choices retain their actual loop flags, including Falco's unflagged final wait.

[export_model.py](tools/melee_anim/export_model.py) now exports every fighter family and actual costume. It preserves individual bind transforms, rigid/shared joint attachments, envelope palettes, vertex layout/UVs, and texture/material metadata. NBT and absent-normal layouts are handled; vertex colors are consumed but their lighting contribution is still approximate. Bowser's image-animation palettes required choosing the palette associated with each exported image rather than using the first palette for every image.

Source [ftParts_8007487C / ftParts_800750C8](src/melee/ft/ftparts.c) establish that visibility class 2 uses `fp->x203C`, a separate drawable list. Its numeric indices must not filter the primary costume model. Classes 0/1/3 operate on the primary list. [ftGw_Init_OnLoad](src/melee/ft/kinds/ftGameWatch/ftgamewatch.c) additionally installs class 4 from `items[10].visibility`; excluding those initially hidden item alternatives fixes overlapping Game & Watch silhouettes. [roster.py](tools/melee_anim/roster.py) reads verified OnDeath appearance defaults, including Peach/Pichu costume switches. The renderer also applies the motion script's initial visibility prefix, stopping at the first timer; it does not execute the complete timed script.

Source [JObjUpdateFunc](src/sysdolphin/baselib/jobj.c) clamps animated near-zero scale to +0.001 and defines channel 11 node / channel 12 branch visibility. The preview follows those rules; Fox's standard taunt uses node visibility. Joint visibility is separate from drawable alternatives. [preview.load_clip](tools/melee_anim/preview.py) bounds packed results reads by the owning public extent, which allows the compound Popo/Nana archive. Ice Climbers use approximate fixed pair spacing; native results callbacks/placement have not been reproduced.

[native_raster.py](tools/melee_anim/native_raster.py) uses the existing Windows OpenGL runtime on a memory DC/DIB. Pose sampling/skinning stay in Python, while native triangle/depth/texture work makes roster batching practical. It opens no window, captures no desktop, and requires no additional installed package. It honors source culling, texture transforms/mirrored wrapping, and an approximate Game & Watch outline. The slower Python backend remains available and now also honors culling. No Blender importer or MP4 encoder is implemented.

[roster_batch.py](tools/melee_anim/roster_batch.py) renders the full matrix with bounded concurrency, per-job logs/failures, and primary-model/settings/frame-file resume validation. All initial 39 failures (35 Donkey Kong scale/normal errors and four Fox visibility-channel errors) were corrected and rerendered. Resume still needs renderer/evaluator/script/companion fingerprints; changing those requires a deliberate rerender of affected families. No unchecked Mario cache exception remains. All current roster outputs use 256-square masters; the earlier Mario-only pilot's 320-square clapping output was superseded during the full-roster refresh.

The offline player at `build/melee_anim/preview/player.html` has independent Character, Animation, and Costume selectors. GIF saving works for a selected pair, all costumes of one animation, and all 984 GIFs. Pausing or scrubbing reveals **Download paused frame PNG** and **Download paused frame in all colors**. The latter uses precomputed per-frame ZIPs, so the page works locally without a server or ZIP library. There are 208 per-character/animation GIF ZIPs plus the aggregate, and 17,348 per-frame all-costume PNG ZIPs. The displayed frame is one-based: Mario victory 3 at 68/101 links to `frame_0067.png` and `frame-0068.zip`; the source-tick coordinate is shown separately. Both preserve the displayed rendered pose, background, and selected costume. These remain prototype 256-square PNGs, not transparent production stills.

Reproduce and verify:

```powershell
python -m tools.melee_anim.roster_batch --resume --jobs 8
python -m tools.melee_anim.preview_gallery --require-all
python -m tools.melee_anim.verify_previews
python -m unittest discover -s tools/melee_anim/tests
node tools/melee_anim/tests/test_gallery.js
```

[verify_previews.py](tools/melee_anim/verify_previews.py) validates complete actual costume coverage, all GIF durations/loop flags, distinct color hashes, every GIF bundle inventory/hash, every still ZIP frame filename, and exact first/frame-68/final ZIP image bytes for every character/action. It records results in ignored `coverage.json`. Synthetic tests cover HSD scale clamping, node/branch visibility, primary/secondary drawable-list separation, native depth/culling/hidden geometry, and replacing interrupted/stale still bundles. Contact sheets were visually reviewed for all standard taunts and representative clapping/costume edge cases. These checks establish file/playback coverage, not original-game fidelity or perfectly seamless loops. Timed materials/scripts/props/effects/dynamics/audio and emulator-reference comparison remain unfinished.

Completion results: **984/984 jobs, zero missing**, 81,369 PNG masters, 209 GIF bundles, and 17,348 still-frame bundles. All checks above passed, as did 65 Python tests and the Node player/download tests. All 110,447 game-input/generated/bytecode files checked are Git-ignored. Tracked `.gitkeep` directory placeholders are intentional exceptions and contain no game data. No original assets were added to Git or dependencies installed.

## 15. Sized GIF and still downloads

The player now offers Extra small **128×128**, Small **256×256** (default/current), Medium **512×512**, and Large **1024×1024**. The selection affects individual GIFs, paused PNGs, all-costume GIF/PNG bundles, and the full GIF collection. Changing size keeps the selected action, costume, and paused frame. Filenames include the chosen pixel size.

[downloads.py](tools/melee_anim/downloads.py) resamples the existing exports using Pillow Lanczos. Medium/Large are enlargements of the current 256px renders; they do not add model-render detail. GIFs preserve source palette colors, decoded delays, and authored loop metadata; resizing can combine visually identical frames while preserving duration. PNGs retain RGBA and use the exact selected original output frame. Source-byte/version/size/format fingerprints invalidate changed exports; caches and ZIPs use atomic replacement under ignored `downloads/resized`.

[player_server.py](tools/melee_anim/player_server.py) provides on-demand sizing at `http://127.0.0.1:8765/player.html`. Start it with `python -m tools.melee_anim.player_server`. It binds only to loopback and uses the existing Python/Pillow installation. The offline file still provides direct original-size downloads; resized downloads require this service. Serial generation limits memory for long 1024px GIFs and avoids storing every frame at four sizes. The same HTTP options support every cataloged character/costume, including paired exports; invalid identities, sizes, or frame indices are rejected.

Verification: 68 Python tests and Node player/download tests pass. Synthetic checks cover all four dimensions, PNG alpha, GIF delays/one-shot/loop metadata, frame identity across color ZIPs, source-change cache invalidation, and HTTP attachment/error responses. Real Mario victory 3 exports at 68/101 were verified for selected PNGs, five-color PNG ZIPs, and GIFs at all sizes; GIF duration stays 2020ms and remains a one-shot. Four Game & Watch 128px color GIFs retain 500ms looping playback; a paired Ice Climbers 512px GIF retains its loop. The service is running for the current session. No native browser click test or higher-resolution model render is claimed.
