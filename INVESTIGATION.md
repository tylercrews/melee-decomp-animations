## Current work status (2026-10-12)

The native1024 results/taunt migration, scoped Download All, Kirby batch mode and README update are complete; see section53. The old512 player was replaced after finishing the interrupted render migration. Section54 restores original Game & Watch outline meshes/color/depth passes, including Kirby's copy, with rebuilt downloads and native/resized/rotated checks. The current user-reported storage size is **~67 GB** and further caches can increase it. Prior sections are historical; universal512 and one-pixel outline claims are superseded by these updates.

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

- Mr. Game & Watch's four material colors are RGBA `(0,0,0,255)`, `(110,0,0,255)`, `(0,0,110,255)`, and `(0,110,0,255)`, with outline `(255,255,255,128)` and width approximately `0.01`. Although stored in `fp->x34_scale.z`, this width scales root JObj local X, not world Z (corrected in section 26). They share the same model file and remain four distinct costume jobs.
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

Subsequent clapping-cycle investigation and the minimum-cycle toggle are documented in section 16 below.

The player now offers Extra small **128×128**, Small **256×256** (default/current), Medium **512×512**, and Large **1024×1024**. The selection affects individual GIFs, paused PNGs, all-costume GIF/PNG bundles, and the full GIF collection. Changing size keeps the selected action, costume, and paused frame. Filenames include the chosen pixel size.

[downloads.py](tools/melee_anim/downloads.py) resamples the existing exports using Pillow Lanczos. Medium/Large are enlargements of the current 256px renders; they do not add model-render detail. GIFs preserve source palette colors, decoded delays, and authored loop metadata; resizing can combine visually identical frames while preserving duration. PNGs retain RGBA and use the exact selected original output frame. Source-byte/version/size/format fingerprints invalidate changed exports; caches and ZIPs use atomic replacement under ignored `downloads/resized`.

[player_server.py](tools/melee_anim/player_server.py) provides on-demand sizing at `http://127.0.0.1:8765/player.html`. Start it with `python -m tools.melee_anim.player_server`. It binds only to loopback and uses the existing Python/Pillow installation. The offline file still provides direct original-size downloads; resized downloads require this service. Serial generation limits memory for long 1024px GIFs and avoids storing every frame at four sizes. The same HTTP options support every cataloged character/costume, including paired exports; invalid identities, sizes, or frame indices are rejected.

Verification: 68 Python tests and Node player/download tests pass. Synthetic checks cover all four dimensions, PNG alpha, GIF delays/one-shot/loop metadata, frame identity across color ZIPs, source-change cache invalidation, and HTTP attachment/error responses. Real Mario victory 3 exports at 68/101 were verified for selected PNGs, five-color PNG ZIPs, and GIFs at all sizes; GIF duration stays 2020ms and remains a one-shot. Four Game & Watch 128px color GIFs retain 500ms looping playback; a paired Ice Climbers 512px GIF retains its loop. The service is running for the current session. No native browser click test or higher-resolution model render is claimed.

## 16. Shorter clapping cycles

Luigi's 120-source-tick / 100-output-frame clapping loop contains approximately five repeated claps with small finger/body differences; the skeleton is not exactly periodic every 24 source ticks. The new Minimum cycle toggle therefore exposes an explicitly edited contiguous repeat while leaving the full authored loop as default.

[cycles.py](tools/melee_anim/cycles.py) inspected all 26 families across every actual costume. It compares rendered RGB recurrence at 64px, requires a local repeat minimum with at least 35% improvement over intervening motion and error at most 0.9 times motion variation, then checks the actual unwrapped next image, closing step, and discrete velocity. Endpoint error is limited to 0.8 times mean adjacent-frame change, closing change to 1.25 times the 90th-percentile ordinary step, and velocity mismatch to twice mean change. These heuristic checks select visually close edits, not mathematically perfect periods. The shortest passing length uses a common best seam phase for all costumes; static/gradual/one-shot/poor-repeat candidates are rejected.

| Character | Full frames | Minimum frames | Duration at 50fps | Original PNG interval (zero-based) |
| --- | ---: | ---: | ---: | --- |
| Luigi | 100 | 20 | 0.40s | `[61,81)` |
| Kirby | 134 | 34 | 0.68s | `[17,51)` |
| Link | 50 | 12 | 0.24s | `[26,38)` |

The remaining 23 families retain full loops under these checks; that does not prove no further manually edited cycle exists. Manifest/master size+mtime fingerprints invalidate stale approval after rerendering. The ignored report `minimum-cycles.json` records every family's outcome, source interval, duration, and error metrics. There is no duplicate endpoint, retiming, or blended frame.

The player uses the interval for playback/scrubbing and displays timeline count, FPS, and duration for computing common repeat lengths. [downloads.py](tools/melee_anim/downloads.py) encodes the exact original PNG interval at each chosen size, preserving palette and 20ms ticks with infinite looping. Filenames identify `minimum-cycle`. Individual/color/full GIF ZIPs respect the toggle; unsupported clips retain full intervals in aggregate exports. Paused PNGs map the shortened index to the original master, including all colors. GIF encoders can combine identical pictures into longer holds; displayed uniform timeline counts are the useful basis for combining loops.

Verification: 72 Python tests and Node controls tests passed, including rejection of held/drifting/one-shot or incompatible-costume false repeats, shortened bounds and wrapping, GIF/PNG interval identity, and full-loop fallback. All four Luigi, six Kirby, and five Link costumes were decoded at all four GIF sizes with exact 400/680/240ms looping durations. First-frame all-color 256px PNG downloads match original master bytes. Last-two/first-two closing contact sheets were visually inspected for default costumes. No native browser click test, game-reference comparison, or perfect-loop claim is made.

After changing masters run `python -m tools.melee_anim.cycles`, regenerate `preview_gallery`, and restart `player_server`.

## 17. Dirty/jittery minimum-loop review

Subsequent synchronization feasibility is recorded in section 18; it is a proposal, not an implemented export mode.

The user asked to inspect rejected candidates rather than exclude them. The player now has a separate **Minimum loop (dirty/jittery)** toggle and a clickable **Dirty loop candidates to review** list. It displays the candidate's frame count/duration and specific failed strict checks. Approved minimums remain unchanged, and both edited modes are opt-in.

| Character | Dirty frames at 50fps | Original PNG interval, zero-based | Why it failed strict checks |
| --- | ---: | --- | --- |
| Captain Falcon | 17 | `[24,41)` | Pose/repeat variation; wrap mismatch |
| Dr. Mario | 20 | `[63,83)` | Pose/repeat variation |
| Falco | 21 | `[4,25)` | Pose/repeat variation; wrap mismatch / large closing step |
| Fox | 25 | `[6,31)` | Pose/repeat variation; wrap mismatch / large closing step |
| Ganondorf | 13 | `[27,40)` | Pose/repeat variation; wrap mismatch |
| Jigglypuff | 33 | `[184,217)` | Weak repetition / pose variation |
| Marth | 12 | `[30,42)` | Pose/repeat variation |
| Peach | 17 | `[8,25)` | Pose/repeat variation; wrap mismatch / large closing step |
| Roy | 12 | `[20,32)` | Pose/repeat variation; wrap mismatch |
| Young Link | 12 | `[19,31)` | Pose/repeat variation; wrap mismatch / large closing step |
| Zelda | 17 | `[8,25)` | Pose/repeat variation; wrap mismatch / large closing step |

These 11 families cover 54 actual costumes. The descriptions are analysis failures, not claims that every candidate has an obvious visible twitch. [find_dirty_cycle](tools/melee_anim/cycles.py) uses the earliest relaxed local recurrence minimum across costumes (mean normalized error <=1.3, worst <=1.6, mean recurrence improvement >=10%) and chooses its least-disruptive common seam phase. Strict failures are retained with metrics in ignored `minimum-cycles.json` under `dirty_characters`. Constant/gradual samples and duplicates of approved cycles remain excluded. Master/manifest fingerprints protect these intervals as for approved modes.

Preview, scrubbing, exact paused PNGs, every GIF download size/color bundle, and inline GIF viewing respect dirty mode. Filenames carry `dirty-loop`. Aggregate dirty GIF export prefers the experimental interval, otherwise an approved minimum, otherwise the full clip; individual entries keep their own mode labels. No blending, speed change, endpoint duplication, or automatic promotion to approved status is introduced.

Verification passed: 75 Python tests and Node controls tests, including rejected-repeat labeling, dirty/full/approved interval separation, list navigation, loop wrapping, filenames, and exact source indices. All 54 dirty costume GIFs were decoded at 256px with exact lengths*20ms looping durations, and first-frame all-color PNGs match original master bytes. Captain Falcon inline dirty GIFs were also checked at 128/512/1024px. Last/first/next/middle default-costume contact sheets were inspected for every candidate. The user can now judge these repeats in the local player; no game-reference or seamless-loop claim is made.

## 18. Shared clap timeline feasibility

The user asked how to synchronize these clips in a compact repeating GIF, including buffers and a manually cut Mewtwo segment. Exact LCM using every character's current dirty-preferred/approved/full frame count is 1,112,911,800 frames at 50fps (about 258 days), which is impractical. This is a calculation from current manifests/interval reports, not a proposed output.

A master-timeline search assigns each clip an integer repeat count and rate `segment_frames * repeats / master_frames`. All 26 character entries can meet these bounds:

| Selected intervals | Rate tolerance | First fitting master frames | Duration at 50fps |
| --- | --- | ---: | ---: |
| Approved minimum, otherwise full | +/-10% | 496 | 9.92s |
| Dirty, otherwise approved, otherwise full | +/-10% | 110 | 2.20s |
| Dirty, otherwise approved, otherwise full | +/-15% | 105 | 2.10s |

For the 110-frame case, rates range from 0.90 to 1.0909. Mewtwo's 109-frame clip repeats once at rate 109/110 (about 0.9% slower), and Pichu's 120-frame clip repeats once at 120/110 (about 9.1% faster). Luigi's 20-frame minimum can repeat six times at 120/110, or five at 100/110 (about 9.1% slower); ties can follow a user preference. These rates are relative to the current preview timing preset. The search evaluated master counts on the 20ms output grid. No shared-timeline renderer or controls were implemented.

This solves return-to-start timing, while clap contact synchronization additionally needs one-clap segments and marked contact phases. Brief 1-3-frame holds at a relaxed/hands-apart pose are a possible buffer for small gaps; long holds visibly freeze the character. Larger duration differences are better addressed through explicit speed changes. Source-pose resampling can preserve smooth interpolation; image crossfading may ghost fingers/limbs and should not be the default.

Mewtwo's current authored clip is 130 source ticks / 109 output frames (2.18s). Twelve evenly spaced PNG poses were reviewed: hand movement is subtle, with body and tail variation over the interval. Previous rendered whole-image recurrence checks did not approve a shorter cut. A manual Start/End editor and repeated seam preview could identify a usable one-clap interval, with optional explicit pose blending or secondary-motion treatment. No new Mewtwo segment, seam repair, or exact hand-contact timing is certified here. Dirty-loop discontinuities remain a separate issue from retiming.

## 19. More compact synchronization with limited changes

The user accepts the dirty loops and asked for the shortest shared GIF with few alterations. Further source-pose inspection found shorter hand cycles within the longer Pikachu/Pichu clips. The common archive `PlCo.dat` public `ftLoadCommonData` provides `parts_table` at +0x10 ([fighter.h](src/melee/ft/fighter.h)); each `FighterPartsTable` provides `part_to_joint` at +4 ([types.h](src/melee/ft/types.h)). Semantic LHandN/RHandN indices 21/39 come from [forward.h](src/melee/ft/forward.h). Source pose evaluation and a five-sample smoothed wrist-separation signal in the default costume found Pikachu contacts at output indices 7/22/37/52, exactly 15-frame spacing, and Pichu at 14/29/45/59/74/89/105/119, about 14-16 frames. These are wrist-gap proxies, not certified fingertip collision/contact frames or completed segment edits.

Mewtwo's hands map to joints 32/55, with essentially static folded-arm articulation. Wrist and sampled finger-joint separation is constant to numerical precision; meaningful varying tracks involve body/root, feet, head, and tail. A short idle segment is appropriate rather than imposing a nonexistent ordinary hand-clap period. The source clip remains 109 output frames and no shortened Mewtwo segment has been approved.

A conditional timing search replaces only the three long clips with illustrative lengths: Mewtwo 25 frames, Pikachu 15, Pichu 15. Other dirty-preferred/approved/full lengths remain unchanged. It permits integer repeat counts, 0-3 fixed held output frames per cycle, and moving speed `repeats * segment_frames / (master_frames - repeats * hold_frames)` between 0.9 and 1.1. The first fitting master is **69 frames / 1.38s at 50fps**, suggesting a practical target around 1.4s. The interval assumptions still need manual selection and all-costume seam review; this is not a measured or certified shortest usable animation.

Example least-change schedule choices include Luigi: three 20-frame moving cycles plus three held ticks per cycle (no moving-speed change); Bowser/Kirby: two 34-frame cycles at rate 68/69 (about 1.45% slower); Fox: three 25-frame cycles at 75/69 (about 8.7% faster). Other choices trade a few held ticks for small rate changes. At roughly 1s, the 33/34-frame motions would require more substantial changes under these bounds. The earlier verified 110-frame / 2.2s feasibility remains available without these additional manual cuts. All times refer to the current output preset, not measured emulator timing. No synchronization UI/exporter or new segment was implemented during this estimate.

## 20. Why 1.4 seconds is not the absolute minimum

The current output preset is 50fps: 1.4s equals70 frames, and at60fps it would equal84 rather than90. The prior1.38s calculation imposed a ?10% moving-rate bound and at most3 held output ticks per cycle. Keeping the same illustrative, unapproved manual cuts (Mewtwo25/Pikachu15/Pichu15), a fresh integer-repeat/hold search finds:

| Maximum moving-rate change | Maximum hold ticks per cycle | First fitting master frames at50fps | Duration |
| --- | ---: | ---: | ---: |
| +/-10% | 3 | 69 | 1.38s |
| +/-10% | 4 | 62 | 1.24s |
| +/-15% | 3 | 60 | 1.20s |
| +/-20% | 3 | 42 | 0.84s |
| +/-25% | 3 | 28 | 0.56s |

The longest retained moving intervals are Bowser/Kirby/Yoshi34 and Jigglypuff33. An additional mismatch with the25-frame group (Donkey Kong, Fox, Game & Watch, Ice Climbers, and provisional Mewtwo idle) prevents a short conservative common wrap. Under ?10%/3-hold bounds, omitting the34-frame group yields60 frames/1.2s; omitting the25-frame group yields39/0.78s; omitting33/34 yields47/0.94s. These omission tests explain constraints, not a recommendation to drop characters.

At69 frames, the34 group repeats twice while the25 group repeats three times. Relaxing to42 frames makes the25 group repeat twice while the34 group repeats once, requiring more visible rate adjustment. The0.84s fit's selected rates deviate by up to about19%; the0.56s fit's selected rates by about21.4% (with short holds). All results are arithmetic feasibility under stated assumptions, not completed renders or visual/seam approval. The shared boundary can retain differing character clap counts.

If the aim is fewer GIF data frames, an optional25fps export would yield30 frames at1.2s or21 at0.84s without shortening duration. This is a proposed temporal-quality tradeoff; the current player/download pipeline still uses50fps and no new synchronized/FPS controls were implemented in this advice turn.

## 21. Implemented 0.84-second clapping-sync alteration

The user selected the 0.84s target and requested mutually exclusive radio controls. The player now offers Full animation, Minimum cycle, Minimum loop (dirty/jittery), and Clapping-sync alteration in one clapping-only radio group. Full is default; the group is hidden for taunts/victories. Sync covers all26 selectable forms /123 actual costumes, including paired Nana and separate Zelda/Sheik. All completed sync exports have42 encoded GIF image frames, each20ms, for exactly840ms with infinite looping.

[sync_claps.py](tools/melee_anim/sync_claps.py) selects dirty, otherwise approved, otherwise full intervals. The extra cuts are now concrete: Mewtwo old-output `[49,74)` (25-frame idle), Pikachu `[25,40)` (15), Pichu `[88,103)` (15). Common all-costume rendered seam comparisons select their starts. Wrist-gap minima/maxima in the default skeleton provide contact/open-pose phase proxies; Mewtwo remains an idle with folded arms. Each schedule fits integer repetitions and0-3 fixed hold ticks into42 output samples, with moving rates0.846-1.190. Contact proxies align at timeline zero, while different characters may make different numbers of claps within the master loop.

The renderer evaluates original motion curves at fractional source times, using existing HSD transforms, skinning, textures/visibility, actual costume defaults, and companion handling. Holds reuse the open-pose source time. It samples `[0,42)` output ticks without a duplicate terminal endpoint. The camera fit includes the original whole animation and new samples. This is an edited playback preset, not a claim that source motions were authored with these durations or that existing dirty/manual seams were repaired.

Plans/source fingerprints live in ignored `build/melee_anim/preview/clapping-sync.json`;123 renders,5,166 PNG masters, GIFs and manifests live in `clapping-sync/<character>/costume_##`. Manifests record exact source times, selected interval, rate, repeat/hold counts, phase proxy, source/model provenance and limits. Resume checks plans, primary/companion hashes, file inventories and the uniform GIF policy. Regenerate after relevant renderer/planner changes and bump the planner version when its semantics change.

Pillow's ordinary GIF saver merges identical held images. [gif_export.py](tools/melee_anim/gif_export.py) uses the installed11.1.0 exposed legacy `getheader/getdata` block APIs on copied, shared-palette frames to preserve every time step. Native and resized sync GIFs therefore retain42 separate20ms images, useful for direct frame-by-frame composition. Existing full/minimum/dirty encoding remains unchanged.

Preview, seeking, selected/all-color PNGs, all four GIF sizes, and inline viewing use sync masters. The all-sync ZIP contains123 clapping GIFs; other actions cannot enter sync mode. Verification passed80 Python tests and Node tests for radio exclusivity, clapping-only scope, all123 previews, loop wrapping, filenames, and frame mapping. All123 rendered GIFs and the HTTP aggregate ZIP decoded to42 frames at20ms each. Held-frame Bowser GIFs passed at128/256/512/1024px. Representative all-color final PNG bytes match exact sync masters. Default poses across all26 forms and closing contact sheets for Mewtwo/Pikachu/Pichu/Luigi/Bowser were visually reviewed. These checks do not certify original-game fidelity, exact fingertip contact, or perfectly seamless edited cuts.

Reproduce with `python -m tools.melee_anim.sync_claps --resume`, regenerate the gallery, then restart `python -m tools.melee_anim.player_server`. Source game/decomp code and original master exports remain unchanged; generated data stays ignored.

## 22. Camera rotation feasibility (investigated, not implemented)

This records the advice turn. The user subsequently requested implementation; section 23 supersedes its implementation status.

The renderer retains animated 3D vertices and normals, so arbitrary viewing angles do not require new asset extraction or Blender. [preview.py](tools/melee_anim/preview.py) already has `--yaw` (degrees, default zero), `camera_basis(yaw)`, whole-interval projected bounds, and a `camera_yaw` manifest field. Both its Python rasterizer and [native_raster.py](tools/melee_anim/native_raster.py) accept a 3x3 view basis. Extending that basis to pitch/yaw/roll is a small rendering change; the projection is currently orthographic. Model rotation and camera orbit differ in their lighting behavior: the current light is fixed in world coordinates. For a viewing-angle control, camera orbit preserves the existing world-space animation and normals.

The player is an `<img>` sequence viewer, not a browser 3D scene; [player_server.py](tools/melee_anim/player_server.py) serves masters and constructs downloads from them. New angles require rerendering from model/pose data. Integrating angle controls, bounded on-demand render jobs, stable whole-animation framing/pivot, angle-aware caching/manifests, and matching selected/all-costume PNG/GIF exports is a moderate feature. Continuous mouse-drag 3D playback is a larger follow-up because it needs a live rendering path instead of swapping existing images. Preserve all source times, clapping modes, sizes, and costume identity. Mr. Game & Watch uses intentionally near-flat Z geometry, so edge-on views can appear thin. No rotation controls or new rotated renders were added during this advice turn.

## 23. Implemented X/Y/Z viewing-angle controls

The initial local-file controls were disabled; section 24 records their subsequent correction and the requested review-section removal.

[preview_gallery.py](tools/melee_anim/preview_gallery.py) now supplies X tilt / Y turn / Z roll sliders (-180 to 180 degrees), Apply and Reset, and pending/error status. The local player requests `/rotation` metadata and displays the new PNGs; a paused frame remains selected. Angles persist across character/costume/action/mode changes. Request-generation tokens discard stale results after a later selection or Reset. Downloads and playback controls are unavailable while the required preview is pending or failed; Reset immediately restores default masters. File-based viewing explains that rotation requires the local Python service. No browser 3D library or new dependency was installed.

[preview.py](tools/melee_anim/preview.py) extends `camera_basis` to `Ry(yaw) @ Rx(pitch) @ Rz(roll)`, adds `--pitch/--roll`, and accepts `--samples` for the exact existing source times, including terminal one-shot samples. Original world-space geometry/normals and light stay intact. `fit_camera` uses the whole-animation world bounds center as its angle-independent pivot and symmetric projected extents for a stable frame fit. Each costume retains its own whole-clip fit; this does not promise identical pixel scale between different costume meshes. Sync additionally includes its new samples and preserves its original full-clip fit samples. Projection remains orthographic. Manifests record all angles, rotation order, center and pixel scale.

[rotations.py](tools/melee_anim/rotations.py) renders 256px angle masters under ignored `preview/rotations/<content-hash>`. Cache settings include source times, FPS, sync plan, angles and framing; inputs include source manifests, model/companion/textures, motion report/archives and renderer/evaluator Python modules. A completion marker hashes every PNG, GIF and render manifest; damaged or incomplete outputs rerender. One subprocess runs at a time, with a 600s timeout. The loopback service serializes requests and permits four active/waiting render/export requests, returning a retryable busy response thereafter.

[downloads.py](tools/melee_anim/downloads.py) applies pitch/yaw/roll consistently to selected/all-color GIFs and paused PNGs, aggregate GIF bundles, inline GIFs and all four size presets. File names include `view-x...-y...-z...`. Full/minimum/dirty modes share a rotated full timeline, and interval slicing preserves source frame identity; sync renders its exact 42 fractional samples separately. Existing size policy stays intact: 512/1024 enlarge 256px masters. Exporting additional costumes/animations at an uncached angle renders those serially. The source game/decomp code and original masters remain unchanged. `preview_gallery --require-all --player-only` refreshes controls using already-existing bundles without repackaging them; missing bundles reject that shortcut.

Focused verification passed 87 Python tests and Node controls tests, including basis/axis order, stable pivot and bounds, cache/resource invalidation and corrupt-output repair, companion/sync cache separation, interval-to-PNG mapping, HTTP query validation, Apply/Reset, retained paused index, stale responses, failure states, mode/costume retention and download parameters.

Actual on-demand renders passed for default-costume sync across all 26 characters at X15/Y45/Z10, including separate Zelda/Sheik and paired Ice Climbers. Final live `/rotation` responses and manifests retained all exact source samples; each sync GIF decoded to 42 separate 20ms frames with infinite looping. All eight Mario action timelines were checked. Live frame-68 all-color PNG download bytes matched each of the five Mario rotated preview masters exactly. All five rotated Mario victory-3 GIFs retained one-shot metadata and 2020ms duration. Rotated held-frame Bowser downloads at 128/256/512/1024 retained 42 frames / 840ms. Side-view minimum Luigi, dirty Captain Falcon and sync Ice Climbers/Game & Watch, plus Mario top/underside/back/roll views, were rendered; contact-sheet and top-view visual checks showed coherent geometry without crop jumps in the sampled framing policy. Game & Watch is essentially a thin line at Y90, consistent with its near-flat source width. Ignored `rotation_qa.png`, `rotation_http_qa.json` and render/cache manifests preserve local evidence. New rotation/QA files passed Git-ignore checks and `git diff --check` passed. No live browser click test or original-game material/lighting fidelity validation was performed; browser control behavior was tested through the Node VM and actual HTTP/file outputs.

## 24. Local-file slider fix and review-section removal

The user reported that the angle sliders could not be adjusted. [preview_gallery.py](tools/melee_anim/preview_gallery.py) explicitly set all three sliders and Apply/Reset to disabled whenever `location.protocol` was not `http:`. That made the file-based player unusable for choosing angles. The disabled branch is removed. Local-file sliders update their degree labels normally; nonzero Apply opens the local rendering player with validated selections in a URL fragment, retaining character/action/costume, clapping mode, exact paused frame, playback/repeat state, download size and all angles. The served page restores those before rendering. Reset works in the local file without navigation. The service must be running for the rendered view, as with existing resized downloads; no CORS expansion or renderer changes were needed.

The requested "Dirty loop candidates to review" section and its generated buttons are removed. The dirty-loop radio, all 11 candidate families, intervals, failed-check hints, and downloads remain available through the normal selectors. Node tests now choose dirty candidates through those selectors and cover enabled file controls, slider labels, local-to-served handoff, exact frame/costume/size/repeat restoration, and Reset alongside the existing rotation/download checks. Regenerate with `preview_gallery --require-all --player-only`; refreshing the browser loads the corrected controls.

## 25. Beginner README and Windows command shortcuts

Root [README.md](README.md) now explains the supported Windows workflow: install 64-bit Python 3.13, put a compatible raw dump at root `melee.iso`, run `Import Melee Iso.cmd`, then open `Open Melee Decomp Animation UI.cmd`. Official Python Windows downloads and primary NumPy/Pillow release pages were checked for package/version guidance. Current pinned versions remain NumPy 2.2.4 and Pillow 11.1.0. Python 3.10-3.13 is the allowed range; 3.13 is the tested recommendation. The preview collection in this working checkout occupied about 6.68 GiB including existing angle/cache/export data, so the README explains the need for space without promising a fixed storage amount.

[launcher.py](tools/melee_anim/launcher.py) uses the standard library and preserves the original bounded extractor and existing rendering utilities. It refuses a missing/incompatible ISO before installing packages. Default import extracts, prepares packages if needed inside `.venv`, inspects motions/models, builds the action catalog, runs resumed four-worker roster rendering, analyzes cycles, runs resumed synchronized claps, generates the full gallery/download bundles, and verifies previews. It stops at a failing step. `--extract-only` needs no rendering packages; a positional ISO path and worker count are supported. No global package installation, dependency upgrade or original game-file overwrite is introduced. Exact package pins are in [requirements.txt](tools/melee_anim/requirements.txt).

UI launch validates prepared HTML/motion data, starts or reuses the local player, waits for health and opens the system browser. New servers use Windows `CREATE_NO_WINDOW`, with output in ignored `build/melee_anim/player-server.log`. `/_health` now includes the resolved preview root; mismatched/older services on the same port are rejected with a port-change instruction. Reopening the UI neither reimports assets nor reinstalls packages. `--no-browser` and configurable port support diagnostics. The `.cmd` wrappers resolve their own repository directory (including spaces), prefer `.venv`, then `py -3.13`, then PATH Python, preserve exit codes, and keep import/error output visible.

Focused launcher/server/download tests passed 20 cases using synthetic fixtures and mocked installation/import operations. Both actual root `.cmd` wrappers were exercised using import `--help` and UI `--no-browser`; a real hidden server on a temporary port served the 984-clip player and a second launch reused it. The task-owned temporary server was stopped, leaving the primary UI running. `launcher check` confirms the existing Python 3.13.2/packages/ISO/player without mutations. No new packages were installed, full game reimport/rerender was not repeated, and the first-time package-download path remains mock-tested rather than certified on a fresh computer.

## 26. Game & Watch's flattened profile (2026-10-11)

The user reported that the rendered character did not resemble the game. The original preview had retained the width value but applied `positions[:,2] *= width` after skinning, with no special runtime facing. That squeezed world Z while still showing the unturned model; it is not the game's transform. Prior references to a "Z width" in these notes described the fighter storage field incorrectly as a rendering axis.

Code-confirmed transform sequence:

- [ftGw_Init_OnLoad](src/melee/ft/kinds/ftGameWatch/ftgamewatch.c:523) assigns `x0_GAMEWATCH_WIDTH` to `fp->x34_scale.z` and sets costume diffuse color plus outline color. The extracted attribute is approximately `0.009999999776482582`.
- [Fighter_UpdateModelScale](src/melee/ft/fighter.c:213) assigns that value to **root JObj scale.x**; Y/Z retain model scale. [Fighter_UnkUpdateCostumeJoint_800686E4](src/melee/ft/fighter.c:565) loads the costume joint itself as the GObj root, so this is bone 0 in our exported hierarchy, not an extra guessed wrapper.
- [gm_8017A67C](src/melee/gm/gm_1798.c:504) sets results-facing direction to **-1 for Game & Watch**, while other characters use 0. [Fighter initialization](src/melee/ft/fighter.c:1175) and [ftDemo_SetFacingDirection](src/melee/ft/ftdemo.c:159) set root Y rotation to `pi/2 * facing`. This gives -90 degrees for clapping/victories/waits. The inspector's standard right-facing taunt selects +1, giving +90 degrees there.
- [HSD_JObjMakeMatrix](src/sysdolphin/baselib/jobj.c:138) composes those root SRT values through the joint hierarchy before skin palette evaluation. Keep classical-scale/parent compensation behavior and inverse-transpose normals; do not compress an already posed world-coordinate mesh. The resulting thin local-X plane is turned into the familiar profile in the default camera.

Asset-confirmed material behavior: exported `PlGwNr.dat` materials have render mode **1**, `RENDER_CONSTANT` in [mobj.h](src/sysdolphin/baselib/mobj.h:38), without diffuse/specular lighting. The four source colors remain black `(0,0,0)`, red `(110,0,0)`, blue `(0,0,110)`, green `(0,110,0)`. Our previous directional shading incorrectly darkened the colored variants. [export_model.py](tools/melee_anim/export_model.py) now records `runtime_root_scale=[width,1,1]` and `unlit=True`; the catalog names the attribute `root_x_width`. [preview.py](tools/melee_anim/preview.py) applies root scale/facing before world matrices and records them in manifests. Both raster backends honor unlit materials. Camera orbit remains independent: an edge-on Y90 view becomes very thin rather than inflating the character or billboarding it toward the camera.

All 32 Game & Watch base jobs (eight choices × four actual colors) and four synchronized clap jobs were rerendered. Source periods, output counts, 50fps timing and the sync preset's 42 separate 20ms ticks are retained. Cycle analysis still keeps his full 25-frame clap; other approved/dirty intervals remain unchanged. Full gallery generation refreshes selected/all-color GIF ZIPs, paused-frame ZIPs and the full collection. Download caches hash source bytes, while angle caches hash the changed model, manifests and renderer modules, so old outputs are not reused. The player service was restarted with the refreshed catalog.

The full Python suite passes **97 tests**, including new synthetic checks for root facing/width before child articulation and skinning, transformed normals, unchanged bind defaults, and normal-independent exact colors in both rasterizers. Node player tests pass. Full-roster verification passes all 984 jobs / 123 costumes, 209 GIF bundles and 17,348 still-frame bundles. Contact sheets for all four colors/eight choices and a multi-pose victory entrance were visually inspected; local evidence is ignored under `build/melee_anim/game_watch_qa`.

Twenty live HTTP checks also passed: all-color first PNG bytes match the new masters for each of the eight animation choices; full/sync clap GIF and frame-10 PNG bundles contain all four colors at 128/256/512/1024px; original-size still bytes match exactly. Full claps retain 500ms looping duration and sync GIFs decode to exactly 42 frames / 840ms. Front, X25/Y45/Z10, edge Y90 and back Y180 sync views were requested through `/rotation` and visually reviewed. `verification.json` and `rotations.png` retain that local evidence; 3,228 G&W model/render/QA files passed Git-ignore checks and `git diff --check` passed. The source-constant costume pixels are present in all 32 first-frame masters.

Remaining fidelity boundary: the outline is still an approximately one-pixel image-mask expansion using source RGBA `(255,255,255,128)`. [ftDrawCommon_80080E18](src/melee/ft/ftdrawcommon.c) instead selects the class-4 drawable list for passes around the normal draw; [ftMaterial_800BF6BC](src/melee/ft/ftmaterial.c) supplies outline color when `x2223_b2` is set. Reproducing those geometry/TEV/depth passes and comparing original-game capture remain future work. These checks establish source-derived flattening, visible corrected profiles and costume/export consistency, not exact full-game visual fidelity. No assets were re-extracted, no package installed, and no original decomp/game source changed.

## 27. Attack catalog, on-demand playback, and Animation Type (2026-10-11)

The user requested all attacks and a compact two-level selector: **Animation Type** (Victory Pose, Taunt, Clapping, Attack), with **Animation** shown only when the chosen type has options. [preview_gallery.py](tools/melee_anim/preview_gallery.py) implements that filtering per character, preserves costume IDs, and infers the type when restoring an action through the local-file URL-fragment handoff. Victory has its three entrances and three existing primary authored waits; Taunt and Clapping each hide the single-choice selector. Clapping radios remain exclusive and hidden outside clapping. A pending attack render cannot overwrite a later type/character/costume selection, including a return to a prepared clip with zero camera rotation.

[attacks.py](tools/melee_anim/attacks.py) reads the ordinary `ftData.xC` table with the existing bounded archive helpers. Motion counts/archive names come from the verified [inspect_motions.py](tools/melee_anim/inspect_motions.py) report/DOL tables, and the original DOL hash must still match. Common semantics are taken from the `ftCo_Submotion` enum in [ftCommon/forward.h](src/melee/ft/kinds/ftCommon/forward.h); these disambiguate item swings/throws whose embedded symbols repeat. Character-specific source names come from the packed clip's public symbol. The catalog validates exact offset/size/public, decoded tree type/channels, and actor hierarchy. IDs such as `attack-62_source` mean **ordinary animation/submotion ID 62**, not a demo variant or motion-state ID.

Coverage includes jabs/rapid-jab phases, dash attack, every available tilt/smash angle, aerials and landing recoveries, grounded/aerial special phases, grabs/holds/pummels/throws, face-up/down getup attacks, both ledge-attack variants, and item attacking/throwing poses. Capture/victim reaction clips and `FallSpecial` are excluded. Samus's DAT symbols `Special` and `SpecialAir` are the smash-input side-special missile clips: [ftSamus/forward.h](src/melee/ft/kinds/ftSamus/forward.h) names them `ftSs_SM_SpecialSSmash` and `SpecialAirSSmash`. Tether aerials (`AirCatch` / `AirCatchHit`) are included for their owners. Repeated names get separate variant labels, preserving every animation ID; [ftGameWatch/forward.h](src/melee/ft/kinds/ftGameWatch/forward.h) confirms the nine `SpecialS1..9` / `SpecialAirS1..9` Judge variants. Game & Watch ordinary attacks use right-facing +90 degrees and source local-X width; results still use -90 degrees.

Asset-confirmed counts: **3,183 available attack clip entries** across the 26 selectable forms yield **15,188 actual-costume choices**, plus the existing 984 previews. Zelda and Sheik remain separate. Popo/Nana keep separate model actors, with explicit Popo source reuse for empty Nana ordinary slots, not a default-costume substitution. Available Kirby copy clips are included as isolated poses; **33 other Kirby copy clips** (Jigglypuff, Mewtwo, Falco copies) have incompatible normal-Kirby node counts and are explicitly disabled in the menu. Matching alternate copy bodies exist among `PlKb<costume>CpPr/Mt/Fc.dat`; their rigs/costume mappings/import are future work. Even a copy clip compatible with the normal hierarchy does not establish correct copy hats, equipment, callbacks or procedural appearance.

To avoid pre-rendering over fifteen thousand extra costume jobs, the player uses lazy attack choices with frame counts and no fabricated/preloaded PNG paths. Selecting an attack asks the local service to prepare the selected costume even at zero camera angles. [AttackCache](tools/melee_anim/attacks.py) writes content-addressed PNG/GIF masters under ignored `preview/attacks`, checks hashes of all output files, and fingerprints the catalog, source model/companion/textures, raw animation archives, motion report and Python implementation. Incomplete/corrupt outputs rerender; subprocesses have a 600-second bound, with the existing serialized/bounded HTTP worker policy. Attack selection from a local HTML file hands off to the HTTP player. The generated catalog is ignored `preview/attack-catalog.json`; run `python -m tools.melee_anim.attacks` after exporting roster models, then regenerate the player. ISO preparation now runs that step automatically.

[preview.load_clip](tools/melee_anim/preview.py) resolves the attack's catalog actor and ordinary archive. [downloads.py](tools/melee_anim/downloads.py) prepares virtual clips before exporting or rotating. Selected/all-color GIFs and exact paused PNGs work at 128/256/512/1024, preserving the same source interval and selected output frame. [rotations.py](tools/melee_anim/rotations.py) hashes the ordinary archive/catalog and uses the prepared source manifest for exact resampling. The old aggregate ZIP remains the 984 prebuilt results/taunt collection; its button is hidden for Attack and `scope=all` excludes lazy attacks, so it cannot accidentally launch the entire attack batch. Per-animation all-color downloads do render missing costumes. `collect_clips(..., include_attacks=False)` retains the legacy rendered-job inventory for packaging/verifying existing bundles.

Verification completed:

- **102 Python tests** pass, including synthetic classifier exclusions, shared-file four-color identity, bounded source sampling, catalog actor lookup, cache reuse/input changes/corrupt-frame repair, exact prepared stills, and rejecting invalid frames before rendering. No original bytes were added to tests.
- Node tests pass for the existing playback/sizes/minimum/dirty/sync/rotation features, type filtering, hidden single-choice selectors, color retention, zero-angle attack preparation, paused attack downloads, stale-response suppression, and local-file attack handoff. This is a simulated DOM/control test, not a live browser click test.
- All **3,183 available clip entries** passed finite hierarchy matrices at start, midpoint, the unwrapped near-terminal limit, and exact terminal. This is pose evaluation, not 3,183 rendered/game-reference comparisons.
- **78 full default-costume clips** rendered: forward smash, neutral aerial, and a neutral special for every one of the 26 forms. Paired Ice Climbers rendered both actors. Contact-sheet review includes Mario, Game & Watch, Kirby, Zelda, Sheik and Ice Climbers.
- **16 live HTTP checks** passed: selected exact-frame PNG bytes for Mario/Zelda/Sheik/Game & Watch/Ice Climbers; all five Mario colors in GIF/PNG bundles at each size; and rotated exact-frame downloads for Mario/Game & Watch/Ice Climbers. Mario's 42-source-tick forward smash produces 36 output samples / 720ms at the existing 50fps preset, including its terminal one-shot sample; GIF duration was checked against the manifest rather than assuming source frames equal output frames.
- Legacy verification still passes **984/984 jobs**, 123 costumes, 209 GIF bundles and 17,348 still-frame bundles. Ignored `build/melee_anim/attack_qa` retains render, pose, HTTP and contact-sheet evidence. The attack inventory is cataloged for every costume; it has not been fully pre-rendered.

Remaining fidelity boundary: these are isolated source motion phases. Full moves still need timed part/material scripts, projectiles and spawned items/props, effects, input-dependent charging, state transitions, root/physics behavior, opponents and hit interactions. Initial motion visibility prefixes are used; complete timed scripts are not executed. Source authored-loop flags and separate phases do not certify seamless loops or exact runtime durations. No Blender, FFmpeg, dependency installation, original-source modification, or repeat ISO extraction was required.

## 28. Transparent player images, GIFs and PNGs (2026-10-11)

The user noticed gray backgrounds baked into downloaded GIFs and requested transparency in both saved images and the app, including native right-click saving. The previous renderer cleared RGBA to `(34,38,46,255)`; encoding/resizing then converted frames to RGB, so transparency could not survive. Removing all gray/black pixels would also remove valid character geometry and was not used.

[native_raster.py](tools/melee_anim/native_raster.py) now derives coverage from the depth buffer, independently of RGB. The Win32 memory-DIB pixel format does not reliably provide an alpha attachment, so merely clearing alpha to zero is insufficient. Covered body pixels get alpha 255, uncovered pixels get alpha 0, and the approximate Game & Watch outline retains white alpha 128 in PNG. Hidden transparent PNG pixels may still contain the old gray RGB value; alpha zero makes them invisible. [preview.py](tools/melee_anim/preview.py) clears the background transparently and retains RGBA masters. The Python rasterizer already retains the supplied clear alpha, and both backends are tested with foreground geometry whose RGB exactly equals the background.

[gif_export.py](tools/melee_anim/gif_export.py) adds `quantize_rgba`: palette index 0 is exclusively transparent; all opaque palette colors occupy 1..255. Opaque black must never use the transparent index even if its RGB matches palette entry 0. One shared palette keeps frames consistent. GIF transparency is binary at alpha >=128; PNG retains partial alpha. `encode_frames` writes the transparent/background index and disposal 2 in each full-frame block, so previous poses are cleared, while every sample/held tick and loop/duration metadata is preserved. Native previews, shortened cycles, resized GIFs and `expand_ticks` use those helpers. [downloads.py](tools/melee_anim/downloads.py) resizes RGBA before quantization; Pillow's RGBA resampling avoids gray-matte edge contamination. The resize cache version is now `resize-v3-alpha`.

The player uses a CSS checkerboard to reveal transparency without adding it to asset pixels. Timed PNG playback continues to support exact scrubbed frames and the independent Repeat preview toggle. A same-size, opacity-zero real `saveimage` sits over that view as the native browser image-saving target: its source is the actual inline GIF while playing, and the exact selected-size PNG while paused. Download buttons and this target share the selected action/color/mode/angles/size. Its GIF query omits the irrelevant frame parameter and its source updates only on changes, preventing a new GIF request on every timer tick. Both images hide during pending/failed rendering. The UI explains the GIF/PNG distinction. A native context-menu click was not automated; the actual target resources/bytes and DOM state changes were checked.

All **984 base jobs / 81,369 PNG masters** and **123 sync jobs / 5,166 PNGs** were rerendered. `transparent_background=True` is recorded in render manifests and required by base/sync resume so old opaque files cannot be treated as complete. Angle and attack caches fingerprint the changed implementation and prepare transparent files on demand. Cycles were recomputed; all approved and dirty interval start/length pairs are identical to their prior values. Full gallery packaging replaced the GIF/still ZIP data. The local player was restarted with the updated implementation and catalog. No assets were re-extracted and no dependencies installed.

Verification evidence:

- **105 Python tests pass**, including new synthetic coverage-versus-RGB checks, black/gray foreground preservation, partial outline alpha, GIF disposal after movement, transparency through all four sizes, no gray matte on resized black edges, tick expansion, loop flags and durations.
- Node controls pass, including native save-target GIF selection while playing, exact PNG selection while paused, inline GIF parameters, stable GIF URLs across ticks, all prior types/modes/sizes/rotation and stale-response behavior.
- Every frame of all **1,107 rebuilt base/sync jobs** was decoded: **86,535 GIF masks exactly match the corresponding PNG alpha>=128 masks**, corners remain transparent, and GIF encoded frame counts equal the source sample counts. This detects trails, accidental opaque backgrounds and disappearing black/gray geometry without relying on filenames alone.
- **28 live HTTP checks pass**: full/minimum/dirty/sync inline GIFs at 128/256/512/1024; all four Game & Watch colors in synced GIF/PNG bundles at each size; and rotated exact stills plus transparent GIFs for Mario/Game & Watch/Ice Climbers attacks and Mario victory 3. Sync files retain 42 separate 20ms ticks / 840ms. The source-frame byte identity is preserved for original-size still downloads.
- The default Mario alpha image and Game & Watch composed onto white were visually checked. Ignored `build/melee_anim/transparent_qa` stores frame-mask coverage, old/new cycle comparison and live export results.
- Final `verify_previews` passes all 984 jobs / 123 costumes, transparent GIF/PNG corners, original timing/loop flags, all 209 GIF ZIP inventories/hashes, all 17,348 still ZIP inventories, and exact first/frame-68/final PNG bytes. QA artifacts remain ignored and `git diff --check` passes.

Partial PNG alpha and binary GIF alpha can produce different outline/edge appearance. This is a format boundary, not a promise that GIF supports fractional transparency. Existing material/lighting, outline, script/prop/effect/dynamics and game-reference fidelity limitations remain. Diagnostic contact sheets still have a composited background; they are not the downloadable character masters.

## 29. Clear preview and zero-angle startup (2026-10-11)

The user requested a clear UI instead of the transparency checkerboard and reported X/Y/Z remaining at previous settings when opening the preview. [preview_gallery.py](tools/melee_anim/preview_gallery.py) now uses `.stage{background:transparent}`: the page background shows through the character image. The GIF/PNG alpha pipeline and native right-click targets remain intact.

Code-confirmed cause: local-file Apply transfers the selected angles to the HTTP player in its URL fragment, and `restoreSelection` previously replayed that fragment on every reload. The player now parses it once and clears it with `history.replaceState`, preserving the requested initial transfer while subsequent loads start at zero. Angle inputs disable autocomplete and synchronize with the actual angle state on `pageshow`, overriding late browser form restoration. A persisted back/forward-cache return invokes Reset, clearing both controls and actual camera/export settings and invalidating stale render requests. Angles still persist across character/action/costume changes within the current visit.

Regenerated the 16,172-choice player using `preview_gallery --require-all --player-only`; existing transparent masters and bundles did not need rerendering. Node player controls pass, including clear-stage markup, stale initial/late form values, initial handoff angles, URL consumption, zero-angle reload without a render request, cached history return, exact paused-frame preservation, downloads and prior async/type/rotation regressions. A live HTTP check confirms the running service serves the updated clear stage and fragment-consumption logic. Browser navigation itself was not automated. No package installation, asset extraction or server restart was needed.

## 30. X-Large 2048px downloads (2026-10-11)

The user requested another doubled size for images with a caution in the dropdown about extremely large GIF files. [downloads.py](tools/melee_anim/downloads.py) now accepts 2048 alongside the previous four sizes. [preview_gallery.py](tools/melee_anim/preview_gallery.py) adds `⚠ X-Large (2048 × 2048) — Extremely large GIF files`, updates the resampling hint, and accepts that size in local-file handoffs. The common download path preserves transparency and exact selected frame/timing for GIFs, PNGs and bundles. Small 256 remains default. Native right-click targets use the same selected size. This enlarges existing 256px masters; it does not produce additional source/model detail.

Regenerated only the player HTML and restarted the local service to load its five-size allowlist (task-owned exec session 6047). Nine focused Python tests pass: all-size RGBA/GIF transparency, colors, timing/loop metadata, HTTP 2048px PNG and all-color GIF ZIP outputs, validation and existing cycle/sync behavior. Node controls pass including caution text, selected/all-color/aggregate GIF/PNG links and 2048px handoff restoration. Live requests verify the health/menu, Link's 12-frame transparent minimum GIF (12 × 20ms, 240ms), and all five Mario victory-3 frame-68 RGBA PNGs at 2048px. No assets were rebuilt or extracted and no dependencies installed. Long X-Large GIFs can consume substantial memory and take longer; the existing serialized export queue remains in place. Full-roster X-Large GIF generation was not attempted.

## 31. Conditional X-Large warning (2026-10-11)

At the user's request, the X-Large option is now just `⚠ X-Large (2048 × 2048)`. “Extremely large GIF files” appears in a separate dark-yellow (#b59a19) status element beside the dropdown only while 2048 is selected. [preview_gallery.py](tools/melee_anim/preview_gallery.py) updates visibility on size changes and initial URL restoration, including pending attack/rotation renders. Other sizes hide the warning. The shared export pipeline is unchanged.

Regenerated player HTML only. Node controls pass, checking option wording/color, default hidden state, all size changes, hiding when switching away, and a restored X-Large selection while rendering, plus existing playback/download/type/rotation regressions. The running server serves the updated markup; no asset rebuild, dependency installation or service restart is required.

## 32. Techs, missed techs, lying motions and optional impact effects (2026-10-11)

The new Tech type exposes seven ground motions for every selectable character and actual costume. These use ordinary `ftData.xC` animation IDs verified in [ftCommon/forward.h](src/melee/ft/kinds/ftCommon/forward.h), not results/demo states:

| UI choice | Animation ID / source submotion | Playback |
| --- | --- | --- |
| Tech in place | 199 / Passive | One shot |
| Tech roll towards (forward) | 200 / PassiveStandF | One shot |
| Tech roll away (backward) | 201 / PassiveStandB | One shot |
| Missed tech — face up | 183 / DownBoundU | One shot |
| Missed tech — face down | 191 / DownBoundD | One shot |
| Lying on ground — face up | 184 / DownWaitU | Source loop |
| Lying on ground — face down | 192 / DownWaitD | Source loop |

[ftCo_PassiveStand.c](src/melee/ft/kinds/ftCommon/ftCo_PassiveStand.c), `ftCo_80098928`, chooses forward/backward by stick X multiplied by facing. Towards/away therefore mean relative to facing, not a simulated opponent. Do not substitute DownFowardU/D or DownBackU/D: those are ordinary getup rolls after a missed tech. [ftCo_DownBound.c](src/melee/ft/kinds/ftCommon/ftCo_DownBound.c), `ftCo_8009794C`, selects U/D using the hit pose's hip orientation; `ftCo_80097E8C` transitions into the corresponding lying motion. The player exposes these phases individually rather than simulating the fall, collision, bounce, timer and getup transitions.

Asset-confirmed: all 26 forms have all seven clips, with compatible costume hierarchies and no unavailable Tech entries. This adds **182 character clips / 861 actual-costume choices**. Zelda and Sheik remain separate. Nana's empty slots use the existing explicit Popo fallback while her actual paired costume/model is preserved. Mario impact/in-place clips are 26 source ticks, tech rolls 40, lying clips 70; some other lying clips differ (e.g. Marth face down 180). Source loop flags are retained. The existing 60 source ticks/s and 50 output fps remain explicit presets; one-shot exports include the terminal sample. They are not measured game-runtime durations or proof of perfect looping.

The impacts are separate runtime effects, not embedded in fighter FigaTrees:

- [ftCo_Passive.c](src/melee/ft/kinds/ftCommon/ftCo_Passive.c), `ftCo_800987D0`, and `ftCo_800989D4` in PassiveStand spawn **gfx 1053 / 0x41D** at TopN's world position. [efasync.c](src/melee/ef/efasync.c), `efAsync_Dispatch`, resolves that to common effect descriptor **15**.
- DownBound's `ftCo_800978D4` spawns **gfx 1030 / 0x406**, rotated to the floor normal; the dispatcher resolves it to common descriptor **4**. `ftCo_800976A4` also requests **1031 / 0x407** (or a surface-specific override), which resolves to particle generator **0x3C**, plus camera quake and sounds.
- [ef/types.h](src/melee/ef/types.h), `EffectDataTable` / `EF_EffectDesc`, and [eflib.c](src/melee/ef/eflib.c), `efLib_Create` / `efLib_Create_Attach_Pos`, define the descriptor layout, lifetime, model/animation attachment and fixed world-position behavior.

The supplied ignored `EfCoData.dat` contains the effect table and original assets. Descriptor 4 has three joints / three rigid meshes, a 64px RGB5A3 texture, original vertex colors, source scale/rotation/visibility and animated alpha. Descriptor 15 has six joints / three rigid meshes, IA4/IA8 textures, animated scale/rotation/visibility and color/blend curves. Their lifetimes are 30 and 60 source ticks, respectively; the visible core fades much earlier. The tech root also has a particle callback on joint animation channel **40**: [jobj.c](src/sysdolphin/baselib/jobj.c), `JObjUpdateFunc` case 0x28, reads the FObj value as an integer bitfield and invokes `dptcl_callback`. It is intentionally kept separate from ordinary joint transforms. Additional particle-bank execution is unfinished.

[techs.py](tools/melee_anim/techs.py) defines the seven identities. [attacks.py](tools/melee_anim/attacks.py) reuses the existing ordinary-motion inspection, script prefixes, catalog and bounded lazy cache for both categories. New keys are `tech-<ID>_source`; the existing `attacks` import step builds them too. Attack coverage remains 3,183 available attack clips / 15,188 costume choices. Total UI coverage is now 17,033 costume/action choices / 3,606 animation entries. The prebuilt aggregate GIF collection remains the original 984 results/taunt jobs; its button is hidden for lazy Tech/Attack entries.

[ground_effects.py](tools/melee_anim/ground_effects.py) parses the actual effect descriptor roots, linked animation/material topology, mixed-endian FObj curves, original GX textures and vertex colors. [inspect_models.py](tools/melee_anim/inspect_models.py) now accepts an explicit root descriptor offset; [export_model.py](tools/melee_anim/export_model.py) retains 8-bit RGB vertex colors during mesh decoding. Source joint flags are retained for effect scaling. The focused effect pass evaluates the source visibility/SRT and a limited source texture/TEV color/blend combination, then composites an RGBA layer behind the fighter. Reading the ground-burst texture's raw RGB as final color produced an incorrect neon-green burst; the source custom combiner is necessary. Billboard/layer/depth and full GX blending remain approximations. Effects are not flattened with Game & Watch. Fixed entry anchors use a horizontal floor, and paired placement remains +/-2.8. PNG keeps fractional effect alpha; GIF uses the existing binary alpha cutoff.

Ground-impact effects starts enabled, can be switched off, and is disabled for lying clips. The UI states that extra dust/sparkle particles are not yet included. An explicit effect-state variable plus `pageshow` synchronization prevents late restored checkbox values from disagreeing with rendered assets; a non-Tech handoff must not disable later Tech defaults. The `effects=on|off` setting is validated and carried through preview, rotation, selected/all-color GIF/PNG downloads, all five sizes, exact paused-frame and native right-click targets, and one-time local-file handoffs. Pending/stale-response protections apply to effect switches. Cache fingerprints distinguish variants and include original EfCoData bytes; enabled filenames add `ground-effects`. Render manifests include the source effect hash, IDs, anchors, lifespan and limitations. Both toggle states use identical whole-animation/effect framing and retain the paused frame. Effects are clipped to the selected character interval instead of silently extending its duration.

Verification performed:

- **109 Python tests pass**, including synthetic source identity, malformed tree topology, effect alpha/vertex colors, distinct effect-cache variants and invalid options. Node controls pass for all character/costume choices, both toggle states, exact paused-frame/export URLs, on/off filenames, stale response protection, local handoffs and late checkbox restoration.
- Four finite pose evaluations and exact node-count checks cover **861 actual-costume choices / 889 actor clips**, including Nana.
- **312 complete default-costume renders** cover all 182 choices with effects off and all 130 impact choices with effects on. All **10,479 GIF frames** have 20ms timing and alpha masks identical to the corresponding RGBA PNG at the GIF threshold. Loop metadata, transparent corners, complete frame counts, matching on/off sample times/camera fit and distinct impact GIF bytes pass.
- **22 live HTTP checks** cover rotated on/off GIFs and exact PNG bytes for Mario, Zelda, Sheik, Game & Watch and Ice Climbers; five-Mario-color PNG bundles at all five sizes; and four-Game-&-Watch-color GIF bundles in both settings at 512px. Final live checks also verify the current menu, enabled rendering and effect source-hash provenance after minor UI/provenance refinements.
- Mario/Game & Watch/Ice Climbers/Zelda/Sheik comparison sheets were reviewed. Ignored `build/melee_anim/tech_qa` contains pose, coverage and HTTP evidence. All 861 choices are available lazily; every costume was pose-checked, but every costume/effect combination was not fully rendered.

The catalog/player were regenerated without replacing legacy masters or bundles. The local server was restarted (task-owned exec session 79443) with the expanded catalog/API. No assets were re-extracted, dependencies installed, original decomp code changed or emulator launched. No native browser navigation or original-game fidelity comparison was automated.

Next fidelity work: implement deterministic particle-bank playback for missed-tech dust and the tech joint callback; reproduce exact TEV/billboard/depth/vertex-color blending and surface overrides; compare against a game reference; then add full trajectory/collision and runtime ground-state transitions. Current output is an isolated source-motion asset with optional core effects, not a complete physical knockdown scenario.

## 33. Knockdown label and alphabetical character selection (2026-10-11)

The Animation Type dropdown now displays **Knockdown** for the seven ground-motion choices. This is a presentation change: internal `tech` values, ordinary-motion source IDs, cache keys and effect behavior remain intact. `preview_gallery.py` sorts the generated Character catalog by case-insensitive display name without changing the source-indexed `CHARACTERS` table. All 26 entries remain selectable, including Zelda and Sheik separately, and Mario remains the initial selection.

Regenerated only `player.html` using `preview_gallery --require-all --player-only`. The Node control regressions passed, including the label, alphabetical order, Mario default and separate forms. A live HTTP check verified the new label and all 26 sorted names in the served HTML. No asset rendering, server restart or dependency changes were required.

## 34. Knockdown framing, green impacts and fighter flashes (2026-10-11)

Corrected the earlier missed-tech color conclusion in section 32: the texture really is green. [tobj.h](src/sysdolphin/baselib/tobj.h) defines separate COLOR_TEV and ALPHA_TEV active bits; [tobj.c](src/sysdolphin/baselib/tobj.c), `HSD_TObjMakeTExp` / `MakeColorGenTExp`, only replaces the RGB source when the color bit is enabled. EfCoData descriptor 4 has active `0x8000007F` (alpha only), while descriptor 15 has `0xC0000077` (both). The old renderer incorrectly applied the dormant RGB expression to descriptor 4, making its burst dark/purple. Preserve green RGB while retaining its source alpha/vertex colors; continue applying the active expression to descriptor 15.

The old fit included all effect mesh bounds, including transparent/extreme geometry. This made missed-tech fighters tiny and shifted tech fighters above the image center. [preview.py](tools/melee_anim/preview.py), `fit_knockdown_camera`, first fits visible fighter geometry over the complete sampled clip and centers its projected bounds, before fitting the visible impact at the same pivot. Other categories keep their existing camera policy. One fit is used throughout playback, preserving source movement. The user rejected separately compacting the effects because the impacts became too small, then explicitly selected keeping the entire impact visible even if the fighter must shrink. The final renderer uses the same pixel scale for fighter and source effect geometry, recording `ground_effect_display_scale=1`. `GroundEffect.visible_bounds` measures complete nonzero RGBA coverage with a 512px calibration pass and one-pixel conservative padding; fully transparent geometry/texture padding is excluded. Fit fighter and those effect bounds together with an 88% inset at the fighter-centered pivot. Lying clips without impacts retain the 82% fighter-only fit. Large missed-tech bursts are several times wider than their fighters in these extracted meshes, so their smaller fighter size is expected under the chosen complete-impact policy. Do not reinstate independent effect shrinking or overflow cropping. On/off impacts retain identical camera fit and flash behavior, including rotations and paired fighters.

White fighter flashes are separate from the ground pass. [ftCo_Passive.c](src/melee/ft/kinds/ftCommon/ftCo_Passive.c), `ftCo_800987D0`, requests color animation 120 at entry. [ftaction.c](src/melee/ft/ftaction.c), `ftAction_80071A14`, routes hit-status commands through [ftcoll.c](src/melee/ft/ftcoll.c), `ftColl_8007B62C`, where state 2 requests color animation 2. [fighter.c](src/melee/ft/fighter.c), `Fighter_LoadCommonData`, resolves those scripts from PlCo's `ftLoadCommonData.x18`. [lb_013B.c](src/melee/lb/lb_013B.c), `lb_80014258`, defines waits, color assignment/interpolation and the per-tick color update; [ftmaterial.c](src/melee/ft/ftmaterial.c), `ftMaterial_800BF6BC`, blends the overlay with the fighter's existing color.

[fighter_colors.py](tools/melee_anim/fighter_colors.py) evaluates the bounded color/wait/goto subset from those original bytes. Script 120 gives the in-place entry two source ticks of white at alpha 120/255. Script 2 gives the away-roll white/fade cycle, stopping at the source hit-status reset (including shared script blocks; tick 20 for the cataloged away rolls; Pikachu/Pichu in-place scripts reset at tick 24, after their brief entry overlay has already ended). The requested preview policy keeps towards rolls in normal costume colors and leaves missed/lying motions unchanged. This limited selection does **not** execute the complete hurtbox/color-priority state machine or certify the game's exact flash behavior; full state/reference work remains queued. Applying the overlay before the separate ground pass preserves the fighter's coverage alpha and leaves ground colors untouched. Ground-impact effects off keeps these fighter flashes.

Default and rotation caches include PlCo.dat as well as EfCoData.dat and all evaluator/render modules. Existing hashes select new masters automatically; no original assets, costumes, pose timing, clip IDs or existing results/taunt masters were replaced. The player hint explains full impact visibility, shared scale and independent fighter flashes. Notes, README and checklist were updated, and the running local service was restarted to load the new fingerprints.

Final verification: 116 Python tests and Node controls passed. All 182 default-costume Knockdown jobs (all seven choices for all 26 characters) rendered successfully; 6,865 GIF/PNG frame pairs retained matching transparency, 20ms timing and empty outer borders, confirming no impact cropping at the tested views. Sixteen live on/off previews and 32 exact PNG/GIF exports covered Mario plus rotated Zelda/Sheik/Game & Watch/Ice Climbers. Ten Mario/Game & Watch all-color PNG ZIPs covered all five sizes; two Mario all-five-color GIF ZIPs retained distinct costumes and 700ms timing. Mario and rotated comparison sheets were reviewed. This is prototype validation, not original-game fidelity certification or a full render of every costume. Ignored `build/melee_anim/knockdown_qa/final-coverage.json`, `final-http.json`, `final-mario.png` and `final-rotations.png` hold the final evidence. The running player remains available in task-owned exec session 62431.

## 35. Kirby Power appearances across animations and costumes (2026-10-11)

The player now shows **Kirby Power** only when Kirby is selected. Its 26 choices are None / Kirby followed by all 25 other selectable forms alphabetically, including Zelda and Sheik separately. Power changes the appearance independently of the selected animation. It is carried through zero-angle and rotated previews, full/minimum/dirty/sync claps, optional Knockdown impacts, GIFs, exact paused PNGs, all six actual Kirby costume IDs and all five download sizes. Switching power preserves frame, playback, color and angle; generation tokens reject stale responses. Local-file handoff includes the power, and late restored form values are synchronized to actual state. The aggregate prebuilt normal-appearance collection is hidden when a power is selected; all-color downloads retain the selected power.

Code and asset evidence:

- [ftkirbydata.c](src/melee/ft/kinds/ftKirby/ftkirbydata.c), `ftKb_Init_803CA9D0`, supplies copy DAT/public names by FighterKind; `ftKb_Init_803CB3E8` supplies the costume-specific body tables. Read these from the verified original DOL with the roster's CharacterKind/FighterKind mapping, rather than guessing filenames or tinting a single hat.
- [ftkirby.c](src/melee/ft/kinds/ftKirby/ftkirby.c), `ftKb_SpecialN_800EED50`, loads those assets. Simple hats use `ftKb_LoadHat` and `ftKb_UnkMtxFunc0`: copy the world matrix of **part 6** to the hat root, replacing the root's own transform. The preview reproduces this mounting after skinning, with inverse-transpose normal transformation. Hat child joints remain at their authored bind poses; dynamic-bone simulation is not implemented.
- Donkey Kong, Jigglypuff, Mewtwo, Falco and Game & Watch use `ftKb_LoadHatParts`, which replaces/adds fighter parts rather than attaching one separate hat. Their `ftKbCopyParts` layout starts with FtPartsDesc at +0, reserved-part mask at +0x10 and secondary model at +0x14; ordinary attached-hat descriptions instead start with a joint and FtPartsDesc at +4. The primary normal-visibility costume body is used here; full secondary hurt/morph/runtime behavior remains unfinished. Game & Watch's table deliberately references the same `PlKbNrCpGw.dat` for all six costumes; keep all six IDs. Its source width/color/outline are read from its copy data, using the existing near-flat root transform and approximate outline policy.
- [ftparts.c](src/melee/ft/ftparts.c), `ftParts_8007506C` / `ftParts_80074194`, and PlCo `ftLoadCommonData.x14[4]` define 13 reserved FighterBone slots. Normal Kirby has 46 preorder nodes. Activating masks 0xF / 0x7F0 / 0x1800 yields the 50-node Jigglypuff, 53-node Mewtwo and 48-node Falco rigs. Remap tracks by these canonical slots, preserving common body channels and retaining authored bind poses for extra target bones without source tracks. Drop source-only dynamic tracks when playing a copy move on another appearance. This supports intentional pose retargeting across powers, not execution of the complete copy-state controller.
- The former 33 unavailable alternate-rig copy animations are now retargetable. Kirby has **280 selectable clip choices** (eight results/taunt, 265 attack, seven Knockdown) / 1,680 ordinary costume choices. With 26 powers including None, that describes **43,680 potential power/action/costume jobs**, prepared on demand; they are not eagerly added as separate dropdown animations or pre-rendered on import. Total ordinary roster choices are now 17,231, including 16,247 lazy attack/Knockdown choices. This does not supply copied projectiles/items, charges, opponents, collision or runtime state transitions.

[kirby_powers.py](tools/melee_anim/kirby_powers.py) owns the focused table reader, copy-model cache, track remapping and attachment boundary. [export_model.py](tools/melee_anim/export_model.py) accepts explicit source archive/root/visibility overrides, reusing the existing mesh/texture/material pipeline. Model cache hashes cover original copy/body DATs, DOL, PlCo, symbols and Python implementation; every cached model and used texture is verified. [rotations.py](tools/melee_anim/rotations.py) prepares powers even at zero camera angles and includes power, assets and exact source timelines in cache identity. `/rotation` and `/export` accept `power=none|<character slug>`, validating non-Kirby/unknown values before rendering. Names include the power; exports and native-save targets use the same appearance as playback. No dependencies, replacement assets or original decomp code were changed. All generated models, textures, frames, GIFs and QA remain ignored.

Visual review identified that copy hats' specular-mask textures were overriding their colored diffuse textures. Copy materials now select UV diffuse lightmap textures (source flag 0x10), and full BLEND textures replace the diffuse RGB as specified in [tobj.c](src/sysdolphin/baselib/tobj.c). This restores source-colored helmets/crowns in the native and Python raster paths while leaving the regular prebuilt roster material policy intact. This remains approximate lighting/reflection, not complete GX TEV reproduction. A synthetic native regression verifies diffuse color survives an additional specular mask. Cached model validation requires this material policy; the local service was restarted after importer changes, and an old cached Samus costume-2 model/preview was repaired.

Verification: 121 Python tests and Node controls pass. All 150 non-none power/costume assemblies loaded; all 43,680 power/action/costume combinations passed four finite-pose mapping checks, using the 14 distinct actual bind/flag profiles across 156 power/costume selections. Full claps were rendered for all 150 powered costume jobs. Additional full renders covered victory 3 for every power, all 33 newly supported alternate-rig copy moves on their matching appearances, plus wait/taunt/attack/Knockdown and a cross-rig attached-hat probe: 63 jobs. Live checks covered ten powered previews and exact PNG/GIF exports across modes/types/rigs/angles, all-six-color PNGs at all five sizes, six-color synchronized Mewtwo and Game & Watch GIF ZIPs, and invalid-power rejection. Full runtime dynamics and original-game reference comparison were not tested; these are asset/pose/render checks. Final frame-mask and post-material-fix HTTP evidence are recorded below when complete.

Final evidence: all **20,100** frames across the 150 powered clap jobs have matching GIF/PNG coverage alpha, 20ms delays and authored GIF looping (2,680ms per full clap). The final hat sheet, all six costumes per power, and representative victory/copy/type poses were reviewed. Final source-color live checks additionally passed for Captain Falcon, Peach, Samus costume 2, Game & Watch and Mewtwo, with exact PNG bytes matching their served masters. Ignored `build/melee_anim/kirby_qa/{poses,clap-coverage,frame-validation,actions,http,final-http}.json` and `all-hats-final.png` record the evidence. The restarted player is left available on port 8765 in task-owned exec session 91017. No original-game/Dolphin comparison or full render of all 43,680 jobs was performed.

A final provenance refinement records the actual replacement model hash (rather than the regular Kirby input model), copy archive hash and replacement body archive hash in render manifests. Nineteen focused pose/cache tests and a live Mewtwo source/model hash check passed; this metadata change does not alter the reviewed images.

## 36. Samus and Kirby-Samus green visor reflection (2026-10-11)

Asset-confirmed cause: these visor materials use **TEX_COORD_REFLECTION (1)**, not UV coordinates (0). The renderer previously ignored all non-UV textures and displayed the gray/white diffuse material instead. The original 64px CMPR environment image (decoded cache `89c2472b6f6605376ef1.png`) is green with a bright reflection stripe. Regular Samus uses a REPLACE reflection texture and constant render mode; Kirby's Samus hat uses a MODULATE reflection texture with white diffuse and source material alpha. This differs from the earlier copy-hat diffuse/specular-mask selection bug.

[tobj.h](src/sysdolphin/baselib/tobj.h) defines TEX_COORD_REFLECTION and lightmap roles. [tobj.c](src/sysdolphin/baselib/tobj.c), `TObjSetupMtx`, maps camera-space normal X by +0.5, Y by -0.5 and biases each by 0.5 before the original texture SRT. `setupTextureCoordGen` uses the normalized normal coordinate source. [mobj.c](src/sysdolphin/baselib/mobj.c) applies TEX_LIGHTMAP_EXT textures in the material pipeline.

[export_model.py](tools/melee_anim/export_model.py) now opts ordinary Samus (FighterKind 13) into source diffuse selection and reflection previews; [kirby_powers.py](tools/melee_anim/kirby_powers.py) passes the same option for the actual Samus copy descriptor. Constant reflection materials retain unlit source color. [preview.py](tools/melee_anim/preview.py), `reflection_uv`, generates normalized camera-space normal coordinates; both Python and native rasterizers apply the original texture matrix/wrapping and REPLACE/MODULATE behavior. UV diffuse textures still take priority; other character materials retain their existing opt-out policy. This uses original texels, not a hand-painted green tint. It approximates the game's normal-matrix/lighting path; complete GX rendering remains unverified.

All five ordinary Samus costume models and all eight results/taunt choices were rebuilt (40 full jobs), together with five synchronized clap jobs. Exact source times, loop flags, selected intervals and 42-frame sync timing were retained; Samus has no approved or dirty shortened interval in the current cycle report. Refreshed Samus GIF/still color bundles and the aggregate prebuilt GIF ZIP, then regenerated player HTML. Source/code fingerprints select corrected on-demand attack, Knockdown, rotated and Kirby power masters. Eleven full Kirby-Samus render probes cover all six costume claps plus victory entrance/wait, taunt, attack and Knockdown. The service was stopped before importer edits and restarted afterward, avoiding stale in-memory exporter code repopulating caches. Current task-owned service session is 23055, port 8765.

Verification: 124 Python tests and Node controls passed, including synthetic camera-normal coordinates, an opt-out regression, and green reflection textures in both raster backends. Samus victory poses and Kirby's visor were visually reviewed. Source assets, new outputs and QA stay ignored; no original decomp code, dependencies or game inputs were changed. Live rotated/exact-frame/all-color exports and bundle checks are recorded below when complete.

Final checks: six rotated live previews (Samus full/sync/victory/attack and Kirby-Samus full/sync), matching exact PNG bytes and GIF timing, and four 512px synchronized all-color GIF/PNG ZIPs passed (five Samus / six Kirby costumes; 840ms GIFs). Full legacy verification passed for 984 jobs, 81,369 PNG masters, 209 GIF bundles and 17,348 still bundles. Ignored `build/melee_anim/visor_qa/http.json`, `kirby-jobs.json` and comparison renders hold the local evidence.

## 37. Movement, standing/idles and neutral full/short hops (2026-10-11)

Added the sixth Animation Type, **Movement**. Original ordinary-animation IDs expose standing (2, Wait/Wait1), actual available alternate idles (3/4/5, Wait2/3/4), three walking speeds (7/8/9), dashing (12) and running (13). Held-item Wait and alias slot 6 are excluded. The standing entry includes the usual idle/breathing loop; some fighters have no separate alternate idle. Original loop/one-shot flags are retained. Walking/running/dashing are isolated authored poses played in place at the existing nominal source rate, not input-driven displacement or velocity-scaled game runtime. Source landmarks are [ftCo_Wait.c](src/melee/ft/kinds/ftCommon/ftCo_Wait.c), [ftwaitanim.c](src/melee/ft/ftwaitanim.c) (weighted idle selection), [ftCo_Dash.c](src/melee/ft/kinds/ftCommon/ftCo_Dash.c) and [ftCo_Run.c](src/melee/ft/kinds/ftCommon/ftCo_Run.c). The preview selects each idle explicitly rather than simulating the random wait controller.

Full and short hops are not two separate pose archives. [ftCo_KneeBend.c](src/melee/ft/kinds/ftCommon/ftCo_KneeBend.c), `ftCo_KneeBend_Check_ShortHop`, sets the short-hop flag when jump input is released during startup. [ftCo_Jump.c](src/melee/ft/kinds/ftCommon/ftCo_Jump.c), `ftCo_800CB110`, chooses `hop_v_initial_velocity` or `jump_v_initial_velocity`, with the same forward/back pose selection. Zero horizontal input selects JumpF. `ftCo_Jump_Phys_Inner` skips gravity for its first physics callback; [ftcommon.c](src/melee/ft/ftcommon.c), `ftCommon_Fall`, subtracts gravity and clamps terminal speed. These are code-confirmed rules; the isolated preset's exact height/tick boundary is not emulator-certified.

[movement.py](tools/melee_anim/movement.py) composes original squat (ordinary animation ID 15), JumpF (16), Fall (20), Landing (34) and standing (2) poses with per-actor attributes from ftData.x0: startup +0x38, full velocity +0x40, short velocity +0x4C, gravity +0x5C, terminal +0x60. Squat ID 15 is the common Kneebend submotion, even where its packed symbol says Landing; do not replace it with grounded landing ID 34. Fixed source ticks integrate a neutral vertical trajectory with first-physics grace, terminal clamp and flat ground contact. Fractional output samples interpolate height; the jump pose transitions to looped Fall if its authored interval ends before contact. Play the authored landing and finish at standing. No horizontal input, fast fall, slopes, stage collision environment, state blending, jump/landing effects, held items or procedural systems are run. The source initial pose may visibly switch at phase boundaries; complete game state/reference work remains future work.

Full and short presets share the same union of their complete evaluated geometry, including costumes, Kirby hats and paired actors, so changing hop type does not zoom the short hop into the full hop's apparent height. Timing remains source ticks versus the existing 50fps output preset; jumps are one shots with the existing terminal-sample policy. Mario's supplied attributes are full velocity ~2.3, short ~1.4, gravity ~0.095 and terminal ~1.7; the preset yields 51 versus 31 flight ticks and peak translations ~29 versus ~11 units. These illustrate this preset, not measured game distances. Paired Nana uses her own parameters with the explicit Popo fallback for empty animation slots, and waits on the ground if her scenario finishes sooner. Existing paired placement remains approximate.

The ordinary action catalog/cache now includes `movement-<ID>_source`, `movement-fullhop_source` and `movement-shorthop_source`. The existing import action-catalog step builds them automatically; no new dependency, Blender installation or ISO extraction is required. All previews, selected/all-color GIFs, exact paused PNGs, five sizes, camera angles and Kirby powers use the same prepared clip. UI type filtering and handoff restore recognize movement keys; clapping radios and Knockdown effects remain hidden. Movement jobs are prepared on demand, without multiplying all output paths or rebuilding the legacy results/taunt collection. The actor's source phases/parameters and preset limitations are recorded in render manifests.

Asset-confirmed: **234** Movement clip choices across all 26 forms yield **1,108** actual-costume choices. Total UI choices are 18,339 / 3,840 animation entries, while ordinary attack and Knockdown counts remain intact. All 1,108 choices including paired Nana passed four finite pose/phase samples; all 234 default-costume clips rendered with matching transparent GIF/PNG masks and 20ms timing. Full/short camera center and scale matched for all 26 characters, and all full hops had higher peaks than short hops. Default standing/full/short comparison sheets were reviewed for Mario, Sheik, Game & Watch, Ice Climbers and Kirby. No native browser navigation or original-game reference comparison was performed.

Verification: 127 Python tests and Node controls passed, including source-ID labeling, gravity/grace/terminal integration, fractional phase boundaries, all-character/costume menus, lazy preview and exact-frame download controls. Eight live rotated previews with exact PNG/GIF exports covered Mario full/short hops, Zelda standing, Sheik dash, Game & Watch full hop, paired Ice Climbers short hop, Kirby-Mewtwo full hop and Kirby-Mario run. Mario's five-color short-hop still ZIPs passed at all five sizes; five-Mario-color and six-Kirby-Samus-color full-hop GIF ZIPs passed at 128px. Evidence is ignored `build/melee_anim/movement_qa/{coverage,poses,http}.json` and `comparison.png`. Current task-owned server session is 64487, port 8765. Original game files and original decomp code were unchanged.

The 234 full default-costume renders contain **14,621** verified GIF/PNG frame pairs. Pose coverage records **4,560** finite matrix samples across actual costume and paired-actor choices.

## 38. Fighter-only framing with Knockdown impacts disabled (2026-10-11)

The user requested zooming back in when Ground-impact effects is switched off. [preview.py](tools/melee_anim/preview.py) now expands the camera bounds with `GroundEffect.visible_bounds` only when impacts are enabled. Disabled effects use `fit_knockdown_camera` on the complete visible fighter interval (82% inset), including Kirby accessories and paired fighters. Enabled effects retain complete visible impact coverage at the original shared fighter/effect scale (88% inset). This supersedes the earlier policy of identical camera scale in both settings. Each setting still uses one stable fit across its entire clip; the fighter-centered pivot, animation timeline, selected frame and fighter flash remain unchanged. Lying clips already use fighter-only framing.

The same renderer prepares normal, rotated and powered previews and their GIF/PNG masters; selected/all-color exports and all output sizes consume those masters. Existing effect-state and implementation hashes invalidate old framing caches automatically. Render manifests now identify fighter-only versus full-impact framing. The player hint explains the zoom change; player HTML was regenerated without reimporting game assets. No dependencies or original decomp code changed.

Verification: 24 focused Python tests (techs, action cache and rotations) and Node player controls passed; controls retain a paused frame across the effect toggle. Ten live on/off pairs covered all five Mario impact clips plus rotated Game & Watch, Ice Climbers, Zelda, Sheik and Kirby-Samus. Every pair retained identical source times, center and flash metadata, with greater camera scale when effects were off. Forty selected PNG/GIF exports passed exact master-byte, transparency, frame-count and size checks; two 512px five-Mario-color GIF/PNG ZIPs passed size/transparency checks. The Mario missed-tech on/off comparison was visually reviewed. Local evidence stays ignored under `build/melee_anim/knockdown_zoom_qa/{results.json,comparison.png,check.py}`. Served HTML contains the updated hint. Existing service remains available on port 8765 (session 64487). These are focused renderer/export checks, not original-game reference certification.

## 39. Optional centered full/short hops (2026-10-11)

The user requested a checkbox to keep jumping fighters in the center of the pane. The player now shows **Keep character centered** only for full/short hops, unchecked by default. This is a camera presentation setting: original jump squat/flight/fall/landing poses, source attributes, trajectory and timing remain unchanged. [preview.py](tools/melee_anim/preview.py), `projected_pose_center`, measures the selected projection's visible mesh bounds for each evaluated frame, including Kirby accessories or both Ice Climbers. The camera follows this center rather than holding the ground in view. Normals/material lighting and rotation angles are retained.

To avoid changing size during the hop, compute one 82% camera scale over the union of both full/short scenarios after their per-frame recentering. Both hop choices retain this shared scale for a given costume/appearance/view. Unchecked hops retain the existing complete-trajectory union framing. Center tracking follows the visible geometry bounds, not a screen-space pixel crop or physics edit; transparent texture padding can cause small differences between geometric and raster centers. Paired actors are centered as a group rather than independently repositioned.

[movement.py](tools/melee_anim/movement.py) validates the setting; enabled non-hop requests are rejected. The preview CLI accepts `--center-jump on|off`; `/rotation` and `/export` accept `center=on|off`. [rotations.py](tools/melee_anim/rotations.py) includes this flag in cache settings and prepares centered variants even at zero angles, with camera sample centers and policy in the render manifest. [downloads.py](tools/melee_anim/downloads.py) reuses these same frames for selected/all-color GIFs and paused PNGs in every size, marking filenames `centered`. Player state carries the setting through selection, powers, angles, exact/native saves, stale request protection and one-time local-file handoff. Toggling retains the paused index and playback state.

Regenerated player HTML and restarted the local service for the new request/cache code. Source assets, outputs and QA remain ignored. No dependencies or original decomp sources changed.

Verification: all 128 Python tests and Node controls passed, including synthetic translation/rotation/hidden-geometry camera checks, hop-only validation, paused-frame retention, export links/filenames, local-file handoff and browser form restoration. Seven live previews covered Mario full/short on/off, rotated Kirby-Mewtwo, paired Ice Climbers and Game & Watch. Fourteen selected PNG/GIF exports matched their preview masters byte for byte, with transparent coverage and unchanged frame counts/timelines. Both centered Mario hops retained identical scale; rendered alpha-center travel was at most one pixel, versus 154.5px/full and 67px/short in their normal framing. Two 128px five-color Mario short-hop GIF/PNG ZIPs and selected full-hop PNGs at all five sizes passed. Invalid enabled non-hop requests returned 400 for both routes. The full/short comparison sheet was visually reviewed. Evidence remains ignored under `build/melee_anim/jump_center_qa/{check.py,results.json,comparison.png}`. Current service is task-owned session 22142 on port 8765. These are camera/render/export checks, not new game-runtime fidelity validation.

Presentation follow-up: moved the Keep character centered control above the Movement description, adjacent to the animation options, so users see it before the explanatory text. Regenerated player HTML and checked the served element order; playback/export behavior is unchanged.

## 40. Repeat preview enabled by default (2026-10-11)

The user requested Repeat preview default on. [preview_gallery.py](tools/melee_anim/preview_gallery.py) now checks it in the HTML and on every animation selection instead of deriving its initial state from the authored loop flag. One-shot victory, attack, hop and Knockdown previews therefore repeat until paused or unchecked. Unchecking retains the existing stop-at-end behavior. Explicit file-to-server repeat overrides still restore after selection; exported GIF looping remains determined by the selected source/edited clip. Regenerated player HTML; no asset masters, server code or dependencies were changed.

Verification: Node player controls passed, including one-shot repeat wrapping by default and stopping at the terminal frame when unchecked; existing handoff restoration also passed. Served HTML contains the enabled default. Git diff whitespace checks passed.

## 41. Multi-Man fighters, Sandbag, both hands and Giga Bowser (2026-10-11)

Code- and asset-confirmed: all six requested models are fighters, including Sandbag. [ft/forward.h](src/melee/ft/forward.h) distinguishes external CharacterKind from internal FighterKind; the verified DOL `ftMapping_list`, `CostumeListsForeachCharacter` and `ftData_803C2360` select the following actual archives and one costume for each. They are absent from the 26-playable color-count table and from the supplied results motion tables. No results victory/clapping clips are fabricated.

| UI entry | CharacterKind | FighterKind | Body archive | Fighter data | Packed ordinary animations | Supported clip choices |
|---|---:|---:|---|---|---|---:|
| Master Hand | 26 | 27 | PlMhNr.dat | PlMh.dat | PlMhAJ.dat | 50 |
| Male Wireframe | 27 | 29 | PlBoNr.dat | PlBo.dat | PlBoAJ.dat | 249 |
| Female Wireframe | 28 | 30 | PlGlNr.dat | PlGl.dat | PlGlAJ.dat | 242 |
| Giga Bowser | 29 | 31 | PlGkNr.dat | PlGk.dat | PlGkAJ.dat | 258 |
| Crazy Hand | 30 | 28 | PlChNr.dat | PlCh.dat | PlChAJ.dat | 49 |
| Sandbag | 31 | 32 | PlSbNr.dat | PlSb.dat | PlSbAJ.dat | 41 |

Source costume/root declarations are [ftboy.c](src/melee/ft/kinds/ftZakoBoy/ftboy.c), [ftgirl.c](src/melee/ft/kinds/ftZakoGirl/ftgirl.c), [ftsandbag.c](src/melee/ft/kinds/ftSandbag/ftsandbag.c), [ftmasterhand.c](src/melee/ft/kinds/ftMasterHand/ftmasterhand.c), [ftcrazyhand.c](src/melee/ft/kinds/ftCrazyHand/ftcrazyhand.c) and [ftgkoopa.c](src/melee/ft/kinds/ftGigaKoopa/ftgkoopa.c). Sandbag OnLoad sets `is_sandbag` and adds RObj joint constraints/limits through `ftSb_Init_8014FA30`; these procedural constraints are not yet evaluated by the isolated player. The current raw motion poses look recognizable but have not been certified against game playback.

The existing model exporter successfully handles all six rigs: Master/Crazy Hand 31 joints each, Male Wireframe 63, Female Wireframe 118, Giga Bowser 76 and Sandbag 55. `export_fighter` reads fighter identity from the ordinary tables so results entries are no longer required. Giga Bowser initially showed white bump-map textures instead of colored body textures: leading stages have no diffuse lightmap role, while its actual color textures use flag 0x10. Opt its materials into the existing `diffuse_texture_only` policy, shared by native/Python renderers; this restores the original body colors without manual tints. Exact GX bump/lighting and wireframe glow remain approximate.

[extra_fighters.py](tools/melee_anim/extra_fighters.py) labels hand motions from the **distinct** ftMh/ftCh submotion enums in their source forward headers. They start at `ftCo_SM_Count` (295), which the common reader includes as a sentinel; do not use max(common)+1. For example, animation 297 is Master Hand Entry but Crazy Hand Slap. Ordinary animation IDs differ from boss motion-state IDs starting at 341. Hand standing/idle clips go in Movement; boss attacks (including coordinated clap motion TagApplaud) stay in Attack; entry/damage/cancel clips use Other. These are isolated source poses, without the other hand, projectiles, controller translation or full fight behavior.

Wireframes/Giga Bowser offer their authored ordinary attacks, taunts, Movement/full-short hops and seven Knockdown choices. Sandbag has one standing loop, four Knockdown choices (missed tech/lying up/down), and 36 other reaction/fall/capture/recovery clips. Per the user's follow-up these are displayed under **Hit**, with their individual source names; the bucket also contains available ancillary victim/recovery poses rather than asserting every clip is a hit. Internal keys remain `other-<ID>_source`, with separate animation_type metadata. Extending Hit to normal fighters is future work. Nineteen wireframe/Giga victim clips require other rigs and remain explicitly unavailable; source poses are never mapped to an unrelated model.

`CHARACTERS` remains the original 26-entry external playable table. `ALL_CHARACTERS` appends the six original non-playable external IDs. `costume_catalog`/`roster` add opt-in `include_extra=True`, preserving legacy result batching and Kirby's 25 copy choices. The existing `attacks` preparation step exports extra models and catalogs their clips, so the import launcher needs no extra step/dependency. UI Character now has 32 entries / 129 actual costumes; the player has 19,228 choices / 4,748 animation menu entries (19 extra unavailable entries included), with 889 additional playable clip/costume choices. Existing 984 prebuilt result/taunt jobs and bundles remain intact. Extra poses are lazy and use the common renderer, rotation cache, alpha, paused-frame/native saving and selected/all-color/five-size GIF/PNG paths. Animation Type hides categories with no available clips and falls back to Movement when switching to an extra fighter from Victory/Clapping.

Verification: all 130 Python tests and Node controls passed, including separate boss submotion IDs, preserved playable roster indices, 32-character/one-costume menus, available-type fallback, Sandbag Hit, original Kirby/tech/movement controls, paused-frame and export links. All 889 available extra choices passed four finite pose/phase samples (3,556 total); 19 incompatible rig entries remain disabled. Twelve full renders cover standing plus attack/hit for every extra: 1,160 frames have matching GIF/PNG coverage and 20ms delays, with 24 byte-matching selected exports. Six additional rotated live previews cover both hands, a centered male-wireframe full hop, female-wireframe missed tech without effects, Giga Bowser in-place tech with effects and Sandbag tumble; 12 exact exports and 12 one-color 128px ZIPs passed. Sandbag PNGs passed all five sizes. The final model/action sheet was reviewed after Giga Bowser's texture fix. Source/code hashes refreshed affected caches; the service was stopped/restarted around importer changes. Served menus and Hit option were checked. Evidence remains ignored under `build/melee_anim/extras_qa/{poses.json,renders.json,exports.json,comparison.png}`. Current task-owned service is session 26792, port 8765. No full render of all 889 jobs or original-game reference comparison was performed; no original decomp sources/game data/dependencies were changed.


## 42. Pikachu and Pichu eye material colors (2026-10-11)

**Source-confirmed:** [TObjMakeTExp](src/sysdolphin/baselib/tobj.c) interpolates incoming RGB and texture RGB by tobj->blending for TEX_COLORMAP_BLEND. At 1.0 it replaces incoming RGB. [tobj.h](src/sysdolphin/baselib/tobj.h) defines BLEND=3, MODULATE=4 and REPLACE=5. The old preview multiplied these ordinary eye textures by diffuse gray, dimming the eyes and creating mismatched face patches.

**Asset-confirmed:** verified GALE01 exports show Pikachu kind 12 BLEND eye materials 5/12 in default/red/blue; those eyes use REPLACE in green (costume 3 also has another BLEND material). Default Pichu kind 23 has its eye material at 4; all four variants include BLEND=1. These carry diffuse role 0x10, UV source 4 and original frame-zero image selection. Inspected TEV descriptors have active flags zero: the problem is the outer color-map operation, not an active custom TEV expression. Each has four actual costume IDs, as enumerated from source/verified tables, with roots in [ftpikachu.c](src/melee/ft/kinds/ftPikachu/ftpikachu.c) and [ftpichu.c](src/melee/ft/kinds/ftPichu/ftpichu.c).

**Implementation:** [export_model.py](tools/melee_anim/export_model.py) enables diffuse_texture_only for kinds 12/23. [native_raster.py](tools/melee_anim/native_raster.py) and [preview.py](tools/melee_anim/preview.py) already replace RGB for full BLEND in this path, retaining lighting instead of multiplying gray diffuse. Original textures/UVs/palettes stay unchanged. The correction is scoped to these verified fighters; general partial BLEND/multistage TEV remains approximate. Rebuilt eight models, 64 results/taunt clips / 5,844 transparent PNG masters, eight 42-frame synchronized claps, cycle metadata, all-color GIF/still ZIPs and aggregate bundle. Lazy ordinary/rotated cache keys include model/module hashes.

**Verification:** 131 Python tests and Node controls pass. Synthetic full BLEND matches REPLACE under lighting; the native check covers the ordinary diffuse path. Before/after and all eight costumes were visually reviewed in ignored build/melee_anim/eyes_qa. No emulator reference or new timed eye-image playback was performed; eyes retain frame-zero selection. Actual export and whole-catalog results follow below.


Actual checks passed: eight rotated all-costume previews with 16 exact GIF/PNG exports and original durations, four four-color 128px packs, ten PNG size checks (128/256/512/1024/2048), four lazy Standing/tech-in-place probes with exact PNGs, eight synchronized frame exports and eight corrected costume PNGs served byte-for-byte over HTTP. Rotated contact sheets were visually reviewed. The full legacy verifier passed 984/984 jobs, 81,369 PNGs, 209 GIF bundles and 17,348 still bundles with timing/transparency/hash checks. The UI service was restarted on 127.0.0.1:8765 after rebuilding; refresh the page to discard browser-cached static images. Source game code/assets and dependencies were not changed.


## 43. Remaining characters, Dark Link and wireframe naming (2026-10-11)

User requested an inventory check, then explicitly stopped implementation of additional characters/appearance presets. The only UI change completed before that stop was renaming the two entries to **Wireframe - Female** and **Wireframe - Male**, which now sort adjacently in the alphabetical dropdown. Internal slugs remain female-wireframe/male-wireframe, preserving existing asset paths and export identities. Regenerated the ordinary catalog and player, restarted the service, passed Node controls and verified the served dropdown ordering. No new character, costume, appearance preset or importer was added.

**Fighter inventory:** [FighterKind](src/melee/ft/forward.h) contains 33 valid internal kinds (0..32). The verified expanded roster covers all 33; the UI has 32 character entries because Popo and Nana appear together as Ice Climbers. Nana is included as the paired model with original costume mapping, but has no standalone dropdown entry. Both wireframes, Sandbag, both hands and Giga Bowser are already included. No third, round wireframe appears in the fighter table. The likely remembered character is **Green Alloy from Brawl**, a Kirby-like enemy, documented on the [official Smash Bros. DOJO Multi-Man Brawl page](https://www.smashbros.com/wii/en_us/gamemode/various/various21.html). It is not a Melee fighter asset.

**Dark Link: source and asset confirmed.** Melee's Event 18 opponent is a normal Link with a black runtime color override, not a sixth selectable costume archive. [gmevent.h](src/melee/gm/gmevent.h) defines player initialization offsets: character kind +0, costume color +3, sub_color +5, CPU level +10. [gmevent.c](src/melee/gm/gmevent.c), gm_801BA8FC, loads sqEventInitDataLevelTbl from GmEvent.dat; gm_801BAB40 copies its sub_color to PlayerInitData. Reading the verified archive's table at zero-based event index 17, opponent slot 1, gives CharacterKind 6 (Link), costume ID 4 (white), sub_color 3, CPU level 8.

[ftCommonData](src/melee/ft/types.h) stores sub_colors at +0x6DC. In PlCo.dat, ftLoadCommonData's first pointer is the common data block; its third sub-color entry is original RGBA [0,0,0,255]. [Fighter_UnkInitLoad_80068914](src/melee/ft/fighter.c) loads that sub-color separately from costume_id. [ftmaterial.c](src/melee/ft/ftmaterial.c) applies the runtime color overlay through an additional TEV stage. Thus Dark Link can be reproduced by a source-based appearance override while retaining Link's original model and animations; preserve actual costume enumeration rather than inventing costume ID 5. Link's existing black tunic costume is a different appearance. No Dark Link preview/export option was implemented. [SmashWiki's Dark Link overview](https://www.ssbwiki.com/Dark_Link) corroborates the event appearance and its distinction from the black tunic costume.

**Other candidates outside the fighter roster:** [ItemKind](src/melee/it/forward.h) lists Goomba/Kuriboh, ReDead/Leadead, Octorok/Octarock, Koopa Troopa/Nokonoko, winged Koopa/Patapata and Like Like/Likelike. Additional stage characters include Shy Guy/Heiho, Tingle/Tincle, Birdo/Kyasarin, Polar Bear/Whitebea and Klaptrap/Klap; summoned Pokemon and character props such as Peach's Toad also live outside the fighter table. These are candidates for a separate item/stage asset investigation, not claims of working fighter clips. Their models, archive links, animation formats and runtime controllers need individual verification; do not feed item IDs into the fighter motion/costume pipeline. Giant/tiny and metal/invisible variants are runtime size/material states rather than additional FighterKinds or selectable costume archives, and are not implemented as appearance presets here.

Audit evidence remains ignored in build/melee_anim/eyes_qa/roster-audit.json: all internal kinds, served UI labels and the verified Event 18 initialization values. This investigation does not certify full coverage of every stage/item/trophy model. Further implementation is deferred at the user's explicit request.


## 44. Original held-item props in swing attacks (2026-10-11)

The user requested props and confirmed the six common weapons as the target. **Implemented:** Beam Sword, Home-Run Bat, Parasol, Fan, Star Rod and Lip's Stick appear automatically in their item attacks, including source joint motion where applicable, every actual costume, both actors of Ice Climbers, camera angles, Kirby hats/replacement bodies and GIF/PNG exports. Weapon-specific labels replace ambiguous repeated Swing1 names while preserving existing action keys. Other characters/appearance presets investigated in section 43 remain deferred.

**Source/asset-confirmed mapping:** [ftswing.c](src/melee/ft/ftswing.c), fn_800CCEC4, maps item kinds 12/11/13/24/22/23 to six swing families. [common submotion enums](src/melee/ft/kinds/ftCommon/forward.h) identify their four source submotions as 108..111, 112..115, 116..119, 120..123, 124..127 and 128..131. These are NOT the motion-state IDs 120..143. Packed clip names frequently omit the family, so filename/name-only matching would attach the wrong item. [Captain Falcon enums](src/melee/ft/kinds/ftCaptain/forward.h) add six follow-up submotions 295..300 for internal kind 2. The catalog contains 702 supported action entries / 3,060 costume choices across 29 forms (26 regular plus both wireframes and Giga Bowser).

**Assets:** [iteffect.c](src/melee/it/iteffect.c), it_8027870C, selects ItCo.usd for US language, then itPublicData+4 supplies common Article pointers. [item structures](src/melee/it/types.h) define Article+0x10 model descriptor, +0xC item state array and ItemModelDesc's joint, bone count and attachment ID. All six original weapon hierarchies decode through the existing mesh/texture readers; this does not require new extraction or downloaded assets. The selected item kind, animation timeline, attachment index and item archive hash are retained in provenance. ItCo.dat is a fallback when the USD archive is absent.

**Attachment:** [ftpickupitem_800948A8](src/melee/ft/kinds/ftCommon/ftpickupitem.c) obtains the light-item joint from ftData.x8+0x10. [ftLib_GetPartJObj](src/melee/ft/ftlib.c) directly indexes fp->parts: this value must NOT be fed through ftParts_GetBoneIndex. [it_80274F48](src/melee/it/it_2725.c) constrains the ItemModelDesc attachment joint to that fighter joint; without a dynamic bone table, the item joint is found down the child chain. [lb_8000C2F8](src/melee/lb/lb_00B0.c) adds position and orientation constraints, and [RObj orientation resolution](src/sysdolphin/baselib/robj.c) retains item column scales. The player reproduces that policy; hand squash does not flatten common item props. Kirby body replacements remap the hold joint through the existing reserved-slot mapping. The composed Ice Climbers preset gives each actor its own original attachment.

**Timing/rendering:** [held_items.py](tools/melee_anim/held_items.py) reads HSD_AnimJoint/FObj curves and retains each AObj's end/loop timing. These trees preserve original classical-scaling flags, unlike fighter FigaTree setup. A bounded waits/calls/loops interpreter collects Parasol opcode 42 and Fan opcode 19 command-variable events. [ftCommon_8007E83C](src/melee/ft/ftcommon.c), [Parasol states](src/melee/it/kinds/itparasol.c), and [Fan swing callbacks](src/melee/ft/ft_0CD3.c) provide curve IDs, resets and speeds. Beam Sword uses the settled PickedUp blade/glow scale from [itsword.c](src/melee/it/kinds/itsword.c); attack-driven length changes remain approximate. The Star Rod has a JOBJ_BILLBOARD glow card; its custom color generator mixes original TEV0/KONST yellow using texture intensity, which must not be displayed as grayscale RGB. See [MakeColorGenTExp](src/sysdolphin/baselib/tobj.c).

Translucent item materials render with alpha rather than disappearing at the old alpha-test threshold. Both raster backends blend these layers; the native memory DIB uses two known background mattes to recover true RGBA despite missing hardware alpha. This is coverage recovery, not background RGB matching. Opaque depth still occludes a prop behind a fighter. PNG keeps partial alpha and GIF uses its existing binary threshold/disposal/timing policy. Camera fit includes the whole fighter/item interval, and rotated/five-size/paused/all-color exports share those prepared poses. Item/fighter attachment archives and module hashes participate in lazy/rotation cache fingerprints. No extra UI item selector or installation is required.

**Current evidence:** all 29 forms expose 24 common swing actions, with six additional Falcon follow-ups. 3,156 actor/costume choices (including Nana) passed 12,624 finite hold-matrix samples, and all 150 Kirby power/costume combinations passed attachment bounds. 204 full render probes / 4,824 frames cover six weapons per default form, every Mario swing variant, Falcon follow-ups and six rotated Kirby appearances. Twelve five-color Mario GIF/PNG bundles passed 60 exact byte checks, six rotated/powered/paired PNGs matched live HTTP exports, six GIFs retained timing/transparency, and PNGs passed all five sizes. Final Star Rod color/billboard follow-up validation is recorded below. QA resides in ignored build/melee_anim/held_items_qa.

**Limits:** this is source-attached prop playback, not full item gameplay. It does not simulate projectiles, collisions, random hits, generic throw trajectories, general item scripts/material/shape/dynamic VMs or character-specific spawned props. Generic LightThrow/HeavyThrow clips do not identify a unique item and remain pose-only. Exact additive GX glow and game-reference fidelity remain unverified. The UI and manifests keep these gaps explicit. No original game/decomp source or dependency was changed.


Final follow-up checks: after the Star Rod billboard/color correction, all 204 full probes / 4,824 frames were regenerated and visually reviewed. All 140 Python tests and Node controls passed, including black translucent prop coverage, authored item scaling flags, source event timing, Star Rod color/billboard handling and action-specific UI labels/hints. The twelve five-color bundles, six rotated/powered/paired live exports and five PNG sizes were rechecked successfully against the corrected renderer. The ordinary catalog/player were regenerated and the loopback service restarted. Original inputs and generated QA files remain ignored; git diff whitespace checks passed. No browser click or Dolphin fidelity test was claimed.


## 45. Character-specific attack props and Kirby slot correction (2026-10-11)

**Implemented:** Fox and Falco blasters in grounded/aerial neutral startup/loop/end clips; Sheik held needles during neutral charging and a six-shot release preset; Kirby's Final Cutter blade in eight up-special phases and hammer in both side specials. Additional source profiles cover Mario cape, Dr. Mario sheet, Peach Toad/parasol, Link/Young Link bow phases and Ness forward-smash bat. The catalog adds props to 48 existing action entries / 237 actual-costume choices across ten forms, preserving action keys rather than adding duplicate animations. Shared lazy playback, GIF/PNG, paused frames, colors, sizes, rotations and Kirby appearances use these profiles.

**Source and asset evidence:** [ftData item-slot mapping](src/melee/ft/types.h), DAT_MATCH_FTITEM, identifies character Article slots. [character_props.py](tools/melee_anim/character_props.py) resolves them through ftData.x48 in original fighter archives, separate from the common ItCo item-kind table. All article models were decoded via the existing neutral mesh/FObj/texture readers. [Fox neutral code](src/melee/ft/kinds/ftFox/ftfoxspecialn.c) spawns blaster slot 1 at canonical RThumbNb mapped through ftPartsTable and scales it 0.85; Falco uses his own archive/attributes. Original command-variable events hide the blaster at the neutral ending. The full procedural gun recoil controller remains approximate.

[Sheik neutral code](src/melee/ft/kinds/ftSeak/ftseakspecialn.c) spawns held-needle slot 1 at raw runtime part 23; [held needle callbacks](src/melee/it/kinds/itseakneedleheld.c) expose up to six branches according to stored charge. Isolated charging clips use an explicitly labeled fully charged six-needle preset. Neutral release uses slot 0, with source shot ticks 2,5,8,11,14,17. [it_802AFF08](src/melee/it/kinds/itseakneedlethrown.c) supplies original speed/lifetime and grounded/aerial directions. Verified PlSk attributes give spawn offsets 8/8 grounded, 7/6 aerial, speed 4 units per game tick and lifetime 30 ticks. The preset samples each source spawn pose, flies rightwards in game +X (down 45 degrees in air), and uses center spread rather than source random vertical jitter. It simulates free flight only, without hits, gravity/collision transitions or bounces. Camera fit includes Sheik and the first emission position; outgoing needles leave the square naturally rather than forcing the character to shrink to fit a full trajectory.

**Kirby Cutter is an effect mesh:** [ftkirbyspecialhi.c](src/melee/ft/kinds/ftKirby/ftkirbyspecialhi.c) spawns gfx 0x494. [efalt.c](src/melee/ef/efalt.c) routes it to gfx 5000/5001/5002. The blade is EfKbData.dat / effKirbyDataTable descriptor 0, attached with position/orientation constraints to runtime R3rdNa slot 44. Descriptor 0 has three joints and three meshes with original growth/visibility curves. The implementation includes the blade, not the two supplementary effect/trail objects or the outgoing Cutter wave. Separate animation phases use documented source-time offsets 0/23/58/60; these are isolated-clip presets, not complete state-transition/physics playback. [efLib](src/melee/ef/eflib.c) describes attachment and effect lifetime transitions.

**Correction to the previous held-item work:** [ftParts setup](src/melee/ft/ftparts.c) skips runtime reserved slots while assigning DAT joints. Thus raw Kirby runtime slot 44 is mesh joint 31 in the normal compressed 46-node tree. The previous helper treated ordinary Kirby's runtime index as a mesh index and only attempted mapping on replacement bodies; that attached props incorrectly. The corrected helper maps runtime slots through the existing reserved-slot list for every Kirby model/mask, including the base form. This applies to the six common held weapons, new Cutter/hammer and replacement bodies. Canonical part IDs for other fighters are mapped only when source calls ftParts_GetBoneIndex; source raw indices remain distinct.

Other implemented source landmarks: [Mario cape](src/melee/ft/kinds/ftMario/ftmariospecials.c) and [cape item](src/melee/it/kinds/itmariocape.c), with Dr. Mario's separate sheet slot 3; [Peach neutral](src/melee/ft/kinds/ftPeach/ftpeachspecialn.c) and [up special](src/melee/ft/kinds/ftPeach/ftpeachspecialhi.c), using raw part 109; [Ness forward smash](src/melee/ft/kinds/ftNess/ftnessattacks4.c), bat slot 9 / raw part 42; [Link neutral](src/melee/ft/kinds/ftLink/ftlinkspecialn.c) and [bow item](src/melee/it/kinds/itlinkbow.c), with separate Young Link data; [Kirby side special](src/melee/ft/kinds/ftKirby/ftkirbyspecials.c) and [hammer item](src/melee/it/kinds/itkirbyhammer.c), slot 1 / runtime part 44. Kirby's hammer uses item animation 0 in both ground and air; an initial attempt at air animation 1 failed archive relocation validation and was corrected from the source state table. No failed prop is silently substituted.

**Other candidates investigated, not implemented:** Ness yo-yo (slot 10, procedural position/string/collision behavior), Sheik chain, Link/Young Link hookshot and Samus grapple beam, and Game & Watch's pan, manhole, greenhouse, turtle, parachute, fire/rescue, judge and oil-panic articles. Original item source files confirm separate controllers and meshes; these need their own attachment/state logic. Projectile families also include blaster lasers, arrows, Cutter wave, boomerangs, bombs, turnips and magical effects. Do not classify every projectile as a held prop or imply that this pass supplies all spawned objects. These findings are separate from the deferred actor/appearance requests in section 43.

**Verification:** 146 Python tests pass, with new profile mapping, original archive/root resolution, no unrelated substitutions, base/powered Kirby reserved-slot regression checks, and deterministic needle spawn/velocity/lifetime samples. Node controls verify the four requested action hints and export URLs. All 48 default-costume clips rendered / 1,223 frames; contact sheets, Kirby blade/hammer, Ness bat and visible released-needle frames were reviewed. Actual costume attachment and HTTP/all-color export results are recorded below when complete. QA is ignored under build/melee_anim/character_props_qa. No original game source, input asset or dependency was modified. Exact game-reference fidelity, complete gun/prop dynamics/material scripts, special physics and most emitted projectiles remain future work.


Final validation passed all 237 costume/profile attachment bounds, eight rotated/powered exact live PNG/GIF pairs and 16 all-color packs. After correcting needle game-axis flight and fitting the emission point, final grounded/aerial release and corrected ordinary Kirby bat PNGs matched the live HTTP output; all five PNG sizes passed for those three clips. Released-needle frames were visually checked and were visible before leaving the square. All 48 full prop clips / 1,223 frames were regenerated; tests and Node controls passed. The UI was regenerated and the service restarted with the current catalog. Asset/cache/QA output remains ignored. No Dolphin or browser-click fidelity validation was performed.

## 46. Combined multipart attacks and missed-tech-to-lying playback (2026-10-11)

**Implemented:** [sequences.py](tools/melee_anim/sequences.py) adds 108 combined entries / 488 actual-costume choices through the existing ordinary-action catalog, lazy renderer, player and export caches. Individual clips remain available. Attack labels end in “combined”; Knockdown adds face-up/down “Missed tech → lying on ground”. The generated UI now has 19,716 costume clips / 4,856 animation choices across the same 32 forms. No additional game data, dependency, backend or installation was added. Generated assets and QA remain ignored.

**Selection evidence and scope:** source-confirmed transitions are described below. Other recipes are **asset-derived finite presets**, selected only when a startup, middle and ending are uniquely named and all actors have compatible available clips. Middle candidates are Loop, Hold or the unsuffixed move name; play one original middle cycle, then end. This covers rapid jabs, Fox/Falco blasters/reflectors/side specials, Link/Young Link bows, Sheik needles, Zelda side special, Bowser/Giga Bowser breath, Ness hold families and several Kirby copied neutral specials. Matching filenames alone do not certify full controller behavior. Duplicate packed names (different charge levels, alternate endings, copied rigs), missing phases and branched moves are deliberately skipped pending explicit source/state recipes. Marth/Roy charge endings, Mewtwo charging variants, DK hand-slap endings and side-special branch chains remain individual clips. Numbered phases are not automatically concatenated.

**Fox/Falco:** [ftfoxspecialn.c](src/melee/ft/kinds/ftFox/ftfoxspecialn.c), ftFx_SpecialNStart_Anim / ftFx_SpecialNLoop_Anim, advances startup to the firing loop, then chooses repetition or ending according to isBlasterLoop. The combined preset chooses one loop and ending. Fox ground clips are submotions 295/296/297 with lengths 7/10/24 game ticks (41 total); Falco uses his own clips and timing. Air versions use their separate startup/loop/ending clips. Original blaster attachment, scale and ending visibility scripts are retained per phase; laser projectiles/full recoil remain outside this pass.

**Kirby Final Cutter:** [ftkirbyspecialhi.c](src/melee/ft/kinds/ftKirby/ftkirbyspecialhi.c) confirms grounded Hi1 → SpecialAirHi2 → SpecialAirHi3, with ground contact entering SpecialHi4. Recipes use ground startup 324 or air startup 328, then air phases 329/330 and ground landing 327. Source lengths are 23 + 35 + 5 + 34 = 97 game ticks. The authored TransN channel already contains the large rise/fall arc, so no guessed launch velocity is added. One five-tick descent cycle before landing is an explicit neutral flat-plane preset; the aerial version starts at the same reference plane, without a selectable initial height. Whole-sequence framing fits the entire arc, making Kirby smaller than in a single stationary phase. Real input, ledges, accumulated runtime movement, collision-triggered landing and transition blending remain future work.

**Cutter effect clock:** the blade is still original EfKbData descriptor 0, mapped through Kirby's reserved runtime slots. Combined phases share elapsed effect time rather than resetting blade growth at each boundary. [efalt.c](src/melee/ef/efalt.c), case 0x494, initializes lifetime 65. [eflib.c](src/melee/ef/eflib.c), efLib_Cb_SetRotYAndTransition, keeps frames 60..65 alive when necessary; after expire_flags it requests frame 65 for the finishing animation. Kirby's landing callback fn_800F21E8 sets those flags when command variable 2 fires. The sequence reads that original event at landing tick 1, maintaining the finishing curve across the combined move. The outgoing wave and supplementary trail/effect controllers remain unfinished.

**Missed tech → lying:** [ftCo_DownBound.c](src/melee/ft/kinds/ftCommon/ftCo_DownBound.c), ftCo_DownBound_Anim / ftCo_80097E8C, changes face-up DownBoundU to DownWaitU, and face-down DownBoundD to DownWaitD when no recovery input intervenes. Recipes pair submotions 183→184 and 191→192 for all 26 selectable forms, preserving Zelda/Sheik separately, both Ice Climbers and all actual colors; Sandbag also receives available face-up/down presets. Play one authored lying cycle, then hold its terminal sample. This is a chosen duration, not the full runtime down-wait timer. Ground impacts use sequence time zero once and do not respawn at the lying boundary. The existing toggle fits full impacts when on, and zooms to fighter-only bounds when off. Other extra fighters only receive combinations where their source clips actually exist.

**Playback/export architecture:** every actor stores ordered phase descriptors with original archive, submotion, symbol, skeleton type, script, prop and duration. [preview.py](tools/melee_anim/preview.py) evaluates each phase at its local source time; phase intervals are half-open and the sequence has one terminal sample. Preserve original interpolation without inserting endpoint pauses or invented crossfades. Props have fixed mesh ranges and per-phase visibility/clocks; released needles snapshot the release-phase poses and fit the first emission point while allowing free-flight needles to leave the image. Kirby hats/replacement bodies use the existing reserved-slot retargeter; paired actors keep their own phases. Use one visible-geometry camera fit across the whole sequence. Both caches hash all phase animation/prop archives and rendering modules. Manifests record phase start ticks, source names, policy and prop provenance. GIFs are one-shot; the default Repeat Preview checkbox repeats the entire move only in the UI. All-color GIF/PNG bundles, exact paused PNGs, angles, powers and 128/256/512/1024/2048 sizes use the shared paths.

**Verification completed:** 153 Python tests and Node controls passed. Synthetic checks cover half-open boundaries, terminal holding, ambiguous/missing recipes, source face-up/down pairing, Kirby ground/air selection, later-phase cache dependencies, phase-local prop visibility and prop-free command variables. All 108 default-costume sequences rendered (7,476 frames), with expected sample counts, 20ms GIF timing, transparent PNGs and one-shot GIF metadata. All 488 actual-costume choices passed 4,724 finite boundary-pose checks, including paired actors and Kirby remapping. Reviewed a six-sequence boundary sheet for Fox, Falco, Sheik, Kirby, Mario and paired Ice Climbers. QA scripts, manifests and previews are under ignored build/melee_anim/sequence_qa. Live export results are recorded below after completion. No Dolphin/game-reference or native browser-click validation was performed.

Final export checks passed eight exact live HTTP PNG/source-master comparisons, eight transparent GIF duration checks, sixteen all-color GIF/PNG bundles and forty PNG size checks covering all five sizes. Cases include rotated Fox, Falco air neutral, rotated Sheik charge/release, rotated Kirby-Samus Cutter, Kirby-Mewtwo aerial Cutter, rotated Mario missed tech with impacts, rotated paired Ice Climbers missed tech without impacts, and Zelda side special. All 7,476 GIF/PNG frame masks match and every PNG contains visible geometry. Regenerated player HTML and restarted the service with the current code/catalog; task-owned service session 43139 remains on port 8765. Original data and all QA/generated output are ignored. Git whitespace checks passed. Combined presets retain the documented controller/projectile/branch limitations.

## 47. Reflectors and other attached special effects (2026-10-11)

**Implemented:** [character_effects.py](tools/melee_anim/character_effects.py) adds Fox/Falco reflectors, Ness PSI Magnet and Mario/Dr. Mario/Luigi tornado effect meshes to 28 existing action entries / 116 actual-costume choices. Include them automatically in ground/air phases, applicable combined moves, rotated previews, right-click/native targets, GIFs, exact PNGs, all-color bundles and all five sizes. Existing keys and dropdown categories remain intact; a short effect hint identifies included effects. These are separate from held-item props and the optional Knockdown ground-impact toggle. No additional software or ISO extraction is required.

**Fox/Falco source and assets:** [ftfoxspeciallw.c](src/melee/ft/kinds/ftFox/ftfoxspeciallw.c), ftFx_SpecialLw_CreateStartGFX / CreateLoopGFX / CreateReflectGFX, calls gfx 1161 / 1160 / 1162 on `fp->parts[FtPart_HipN]` (RAW runtime part 4). Falco shares these callbacks and the same effect archive. [efalt.c](src/melee/ef/efalt.c), cases 0x489 / 0x488 / 0x48A, maps them to gfx 3001 / 3000 / 3002. [efasync.c](src/melee/ef/efasync.c) supplies EfFxData.dat / effFoxDataTable. Asset inspection confirms descriptor 1 has four joints/three meshes, descriptor 0 two joints/one mesh, and descriptor 2 two joints/one mesh. Preserve original blue/purple vertex colors and billboard/scale/visibility curves rather than drawing a fabricated circle.

[eflib.c](src/melee/ef/eflib.c), efLib_Create_Attach / efLib_Create_Attach_Scale, uses a position constraint and uniform fighter-root Y scale. It does not inherit hip orientation or squash. The holding descriptor's lifetime is 0.1: efLib_Create truncates this to zero, which means no expiration timer; treating it as 0.1 ticks would hide the reflector immediately. Each original AObj still loops/clamps independently. [ftCommon_8007DB24](src/melee/ft/ftcommon.c) destroys startup graphics when switching to holding. Ending enters with Ft_MF_None and has no reflector. Combined recipes therefore select startup and holding effects separately, then remove them during ending. Reflection-hit clips show their own effect, without fabricating a reflected projectile.

**Other implemented effects:** [ftnessspeciallw.c](src/melee/ft/kinds/ftNess/ftnessspeciallw.c) creates gfx 1264 when PSI Magnet startup finishes, attached at RAW L1stNb part 23. [efsync.c](src/melee/ef/efsync.c), case 0x4F0, maps to gfx 10002, EfNsData.dat / effNessDataTable descriptor 2. Holding and absorption-hit poses display this effect; startup and ending do not. The original asset contains twelve joints/seven rigid/shared meshes. Four animated texture-image tables each contain four images; the reader now decodes those originals and selects them using TIMG tracks, alongside source UV SRT and looping curves. An initial render refused image swaps explicitly; the source reader was extended rather than silently using a static substitute.

[Mario down special](src/melee/ft/kinds/ftMario/ftmariospeciallw.c) spawns gfx 1148 at the fighter root; efalt maps it to gfx 1001, EfMrData.dat descriptor 1. [Dr. Mario's table](src/melee/ft/kinds/ftDrMario/ftdrmario.c) uses those same Mario down-special callbacks, so it uses the same effect. [Luigi down special](src/melee/ft/kinds/ftLuigi/ftluigispeciallw.c) spawns gfx 1289 at the root; efsync maps to gfx 18001, EfLgData.dat descriptor 1. Both archives have five joints/five meshes for these effects, with original animated blend/color textures. efLib_Cb_ftMr_SpecialLw / efLib_Cb_ftLg_SpecialLw hides the second root-child branch on ground and shows it in air; the preview follows this branch rule on a flat surface. Slopes and full move-state physics remain outside the preset.

**Loop timing:** asset-confirmed reflector holding AObjs loop every 6 game ticks, while Fox/Falco's original holding body clip is 28 ticks. The shared GIF interval is their least common multiple, **84 ticks**, with three unchanged body cycles and fourteen unchanged effect cycles. Ness's holding body is 20 ticks and effect AObjs are 40 ticks, so its shared interval is **40 ticks**. Wrap the fighter by its own period while evaluating effects at their source clocks; do not speed either up or wrap both at the body's shorter period. Manifests record this policy. At the existing 50fps grid, these produce 70 and 34 output frames respectively. Combined moves still use one original body middle cycle before ending, preserving their previous prescribed durations.

**Rendering and limits:** reuse [ground_effects.py](tools/melee_anim/ground_effects.py)'s archive/joint/texture reader through an optional effect descriptor; default Knockdown behavior remains the same. Preserve source vertex-only material colors, billboard roll, texture color/alpha BLEND, UV transforms/wrapping, image swaps, and per-AObj timing. Material PEDesc SRC_ALPHA/ONE requests additive RGB for tornado layers and the magnet's core; use premultiplied light addition with union alpha coverage so transparent PNGs retain glow coverage and the fighter stays visible. Other surfaces use normal alpha compositing. Fit the whole animation's fighter/effect geometry at one scale. This foreground compositor approximates source depth/lighting and transparent additive behavior; it does not run particle channels, collisions, reflection/absorption responses, palette/shape/dynamic VMs or full controllers. Exact source-game fidelity remains unverified. Both ordinary and rotated caches include every original effect archive, including effects in later sequence phases.

**Other candidates found, not implemented:** [Zelda neutral special](src/melee/ft/kinds/ftZelda/ftzeldaspecialn.c) creates gfx 1268/1269 for Nayru's Love; efsync maps them to EfZdData descriptors 0/1 using child/orientation attachment. Both assets have twenty joints/twenty-one rigid/shared meshes and a 60-tick lifetime, but their full attachment/state logic remains future work. [Captain Falcon/Ganondorf neutral special](src/melee/ft/kinds/ftCaptain/ftcaptainspecialn.c) triggers gfx 1167/1291 using throw-flag timing and two attachments (root plus raw parts 57/78); source facing/linked-effect callbacks need explicit implementation. Fox's fire effect descriptor 3 includes envelope meshes, exceeding this focused rigid/shared effect renderer. Pikachu/Pichu thunder, teleport particles, spell/projectile families and common particle banks also require their own controllers/generators; do not imply these are provided by this pass.

**Verification completed:** 162 Python tests and Node controls passed. Synthetic cases cover source effect mapping, unrelated/end-phase exclusions, independent AObj looping/clamping, least-common-multiple timing, texture alpha overriding zero material alpha, original color-generator constants, additive transparent coverage, position attachment/root scale, phase-local clocks and effect-archive cache invalidation. All 28 default-costume clips rendered / 1,142 frames, with expected source times, loop metadata and 20ms GIF timing. Every PNG contains visible geometry and all GIF/PNG binary coverage masks match. All 116 actual-costume choices passed 420 finite body/effect-bound checks, and inspected original loop periods match the profiles. Reviewed reflector, magnet and Mario/Luigi effect frames. Live export results follow below when complete. QA files remain ignored under build/melee_anim/effects_qa; no Dolphin or native browser-click fidelity validation was performed.

Final live checks passed nine byte-exact HTTP PNG/source-master comparisons, nine transparent GIF/timing checks, eighteen all-color GIF/PNG bundles and forty-five PNG checks covering all five sizes. Cases include rotated Fox/Falco holding loops, side-view Fox aerial startup, both combined reflector variants, rotated Ness combined magnet, Mario/Dr. Mario tornadoes and aerial Luigi Cyclone. Regenerated catalog/player and restarted the service; task-owned session 47022 remains on port 8765. Original effect archives and all generated QA/cache/export data remain ignored. Git whitespace checks passed. Particle/depth/controller/reference limitations above remain open.

## 48. Selector rows, grouped combined moves and partial filtering (2026-10-11)

**Implemented:** [preview_gallery.py](tools/melee_anim/preview_gallery.py) now shows three control rows in the requested order: Character / conditional Kirby Power / Costume; Animation Type / Animation / Hide partial animations; Pause / Restart / Repeat preview. Labels/selects can shrink and rows wrap on narrower screens. The new checkbox starts checked on fresh loads, with explicit state synchronization after browser form restoration.

`arrange_animation_choices` adds presentation metadata from actual phase submotion IDs in the existing combined-action descriptors, without changing the ordinary catalog, source IDs, clips or export API. Group connected families at their earliest existing position, placing combined choices first beside their partial choices. Shared phases merge into one contiguous family. Kirby's eight Cutter ground/air phase variants belong together because its neutral recipe switches between forms; this also hides the alternate ground phase 2/3 and air landing variants when the filter is on. The current catalog has 108 combined choices and 272 partial choices. Independent actions, such as Fox's reflector response, remain visible; moves without an available combination are not suppressed.

Unchecking **Hide partial animations** reveals the parts beside their combined choices. Checking it while a partial is selected switches to the corresponding combined choice, preserving costume/power/camera and starting that new animation. If the current animation remains available, changing the filter preserves its frame and playing/paused state and does not start another render. The file-to-server handoff includes `partials=hide|show` in the UI fragment only. Existing explicit links to partial actions automatically show their parts unless the link explicitly requests hiding; render/download endpoints continue accepting original action keys.

**Verification:** regenerated only player HTML with `preview_gallery --require-all --player-only`; no asset/model/catalog rerender was needed. Existing Node controls pass, with added assertions for exact row order, default checked state, all-character Attack/Knockdown filtering, contiguous Fox families, shared Kirby variants, independent reflection responses, selected-part fallback, costume preservation, paused-frame retention and partial-link/handoff behavior. Live HTTP player bytes match the generated HTML; Git whitespace checks pass. Player still contains all 19,716 clips / 4,856 choices / 32 forms. Root guidance, plan, checklist and README were updated. Generated player/logs remain ignored. Verification used structural/control tests and served HTML, not native browser clicks or a visual screenshot.

## 49. Sleep eyes, ground dodges, batch preparation and costume names (2026-10-11)

**Implemented and asset-confirmed:** Movement now includes ordinary submotions 41 EscapeN (Spot dodge), 42 EscapeF (Roll forward), 43 EscapeB (Roll backward), and 206 FuraSleepStart / 207 FuraSleepLoop / 208 FuraSleepEnd (falling asleep / sleeping / waking up). IDs come from [ftCommon/forward.h](src/melee/ft/kinds/ftCommon/forward.h), not motion-state IDs. The sleep status states are DamageSong / DamageSongWait / DamageSongRv (297..299) in [ftmotionstates.c](src/melee/ft/ftmotionstates.c). These are original sleep-status clips; Jigglypuff's own Rest remains under Attack, including its facing and aerial variants. All 26 selectable forms, Zelda and Sheik separately, retain every actual costume; Popo/Nana keep their established paired mapping. Wireframes/Giga Bowser have the three sleep slots too; Hands/Sandbag have no supplied sleep clips and none are fabricated. Sleep coverage is 87 action entries / 378 costume choices.

**Source-confirmed dodge assembly:** [ftCo_Escape.c](src/melee/ft/kinds/ftCommon/ftCo_Escape.c), ftCo_80099438 selects Yoshi's egg for rolls; ftCo_80099954 restores his ordinary body for spot dodge. Add Yoshi-only submotion 37 GuardOn as the allowed egg pose; no general shield entries or air dodge were added. His Guard hold slot 38 is empty. Preserve authored roll root travel and rotation. Source script opcode 31 changes model-part visibility over time; Samus rolls select the ball at tick 4 and restore the ordinary model at tick 31. Keep alternate meshes loaded for those transitions and fit only visible geometry. The same source opcode drives Game & Watch sleeping Z symbols (group 10 options 5/4/3), now animated instead of frozen. Dodge/egg coverage is 88 entries / 384 costume choices, including existing extra-fighter slots reclassified as Movement.

**Source-confirmed eye requests:** [ftaction.c](src/melee/ft/ftaction.c), ftAction_800726F4 (opcode 40), calls [ftanim.c](src/melee/ft/ftanim.c), ftAnim_800704F0 / ftAnim_80070458. Costume TObj AObjs run at rate zero (ftAnim_80070200); a script requests an animation **frame**, not an image index. `export_model` now retains image-channel FObj streams; [fighter_textures.py](tools/melee_anim/fighter_textures.py) evaluates those original curves and uses each costume's verified texture_script_map. Read results scripts with the bounded call/goto graph, so shared blink subroutines execute too. Preserve entrance texture requests for standalone victory waits and sleep-start requests for standalone sleep loops/wake clips. Combined actions use phase-local commands on their shared timeline; paired textures have separate names and mappings. Both raster backends and all GIF/PNG export paths use the selected source images. No manual eye tinting or guessed universal closed-eye index.

Pikachu victory 3 requests closed eyes at tick 0; Jigglypuff victory 3 starts closed and reopens later. Rest closes at tick 27 and begins reopening at 180/210. Pichu's supplied three victory entrances/waits are standing/hopping motions, rather than a sleeping victory; their original blinks are now evaluated, and its new sleep loop is visibly curled up with closed eyes. Rebuilt all 104 results/taunt clips for Pikachu/Pichu/Jigglypuff in all 13 costumes, regenerated clapping cycle fingerprints, sync assets and GIF/PNG/aggregate bundles. Other existing prebuilt results frames retain their prior rendering until refreshed; new renders evaluate texture commands. UV/palette/other texture channels and the complete fighter runtime remain outside this focused eye implementation.

**Batch downloads:** [player_server.py](tools/melee_anim/player_server.py) exposes `/prepare-export` with the same validated export options. It prepares the existing cached artifact and returns its local URL/filename; the browser then saves it without buffering an entire large ZIP in JavaScript. All-color GIF, all-color paused PNG and aggregate buttons share a request lock. The clicked button has an animated spinner; batch buttons are disabled for mouse/keyboard requests while preparing. Snapshot the selected action/color interval/frame/size/power/angles at click time, retain busy state through selection changes, and unlock on success or error. Existing static bundles use a HEAD readiness check. File-origin resized batches hand off the exact selection and one-time `batch` UI fragment to the HTTP player, then prepare automatically after the preview is ready; no new API parameters or cross-origin fetch permission is needed. Browser transfer begins after preparation; the UI cannot measure completion of a native browser download.

**Costume audit:** the results viewer had a second, incomplete suffix dictionary. `roster.color_label` is now the shared source for both prebuilt and lazy clips. Correct Fox ID 2 (PlFxLa) to Lavender, Captain Falcon ID 1 (PlCaGy) to Gray, Samus ID 4 (PlSsLa) to Lavender, and Ganondorf ID 4 (PlGnLa) to Lavender. Preserve Mario Red (default), all four runtime-colored Game & Watch jobs, source IDs/counts and archive references. Other normal variants retain Default; every supplied alternate now has a color name. UI labels and downloadable member filenames agree.

**Verification actually run:** 166 synthetic Python tests and Node controls pass. All 175 default-costume dodge/egg/sleep clips rendered completely: 7,313 PNG/GIF frames with expected source sample times, source looping/one-shot flags, 20 ms GIF timing and transparent PNGs. Visual checks include closed Pikachu/Pichu/Jigglypuff eyes, Yoshi egg/roll and Samus normal-to-ball-to-normal transitions. Live HTTP checks compare paused PNG and GIF bytes against their prepared masters, including Rest, powered Kirby, paired Ice Climbers and rotated sleep; 14 live export checks also cover prepared all-color stills for Pikachu/Pichu/Jigglypuff/Kirby/Ice Climbers, a four-color sleeping GIF ZIP and Rest PNGs at all five sizes. All 762 actual dodge/egg/sleep costume choices passed 3,144 finite pose/texture samples over 786 actor clips, including paired Nana. All 129 costume labels agree across existing and lazy clips. Node checks cover duplicate blocking, spinner/disabled state, selection snapshot, error recovery, label consistency and exact file-to-HTTP batch handoff. Evidence remains ignored under build/melee_anim/sleep_qa. Original-game reference validation, complete texture/material callbacks, particles and full game state simulation remain open; no new dependency or Blender installation is required.

Final service restarted on port 8765 (task-owned session 61286); health reports 20,460 clips and served HTML matches the generated player. Final Game & Watch sleep GIF also passes source frame count, 20 ms timing, authored-loop and RGBA transparency checks. Git whitespace checks pass; original assets, generated player, exports and QA remain ignored.

## 50. Original sleep bubbles in sleeping victories (2026-10-11)

**Source/asset confirmed:** results submotion 5 (Victory 3 entrance) for Pikachu FK12 and Jigglypuff FK15 spawns gfx 416 / 0x1A0. No other supplied results clip spawns that effect. [ftaction.c](src/melee/ft/ftaction.c), ftAction_80071028, decodes the five-word gfx command; [lb/types.h](src/melee/lb/types.h) documents its bone/offset fields. [ftCo_09F7.c](src/melee/ft/kinds/ftCommon/ftCo_09F7.c), ftCo_8009F834, and [efasync.c](src/melee/ef/efasync.c) use a world-position snapshot of the specified raw bone plus transformed local offset, rather than following the head after emission. The common range routes through efSync_Spawn to the particle generator.

Pikachu emits at source ticks 77/81/85 from raw joint 19, local offset (0,1.5625,4.6875). Jigglypuff emits at 12/16/20 and 63/67/71 from raw joint 13, local offset (0,0,7.03125). The commands have zero positional jitter and do not destroy particles on the entrance-to-wait transition. Neither wait script emits new bubbles; the standalone wait preset carries only the remaining entrance particles (Pikachu up to wait tick 25, Jigglypuff up to 11). Replaying that exported wait GIF replays its transient tail too, so the bubble-inclusive wait is not a seamless steady-state effect loop. The UI explains this instead of inventing continuous emissions.

**Implemented:** [sleep_bubbles.py](tools/melee_anim/sleep_bubbles.py) reads the original version-0x42 relative-offset particle bank in local EfCoData.dat, emitter 416 and texture group 34. Descriptor: one-tick tornado generator, 60-tick particle lifetime, upward speed 0.2, twist 0.03, radius 1, cone angle pi/6. The original 64x64 IA8 sprite uses PrimEnv color interpolation. The focused bounded decoder implements this emitter's image/wait, size, primary/environment color and end commands. Evaluate original size growth from 0.8 toward 2.0 and the final 20-tick alpha fade; use deterministic azimuth seed 416. Preserve original sprite/colors, world-space spawn origins and source ticks, with explicit fractional interpolation for the output sampling grid. Billboard cards face the selected camera; include their complete geometry in whole-animation framing. Alpha compositing keeps RGBA PNG transparency, with existing binary GIF transparency rules. This does not implement the complete HSD particle VM, and foreground depth/fractional sampling/random azimuth remain approximations pending game-reference comparison.

Script inspection now retains gfx-spawn fields and the bounded event evaluator collects them. Preview automatically includes bubbles for both characters' Victory 3 entrance/wait in every actual costume. All-color/paused-image/resized/rotated/native-save paths share those masters. Rotation cache hashes EfCoData.dat for these actions. Rebuilt 18 entrance/wait costume clips (four Pikachu and five Jigglypuff colors), repackaged exact-frame/all-color and aggregate bundles, and regenerated player HTML. Rest and general Movement sleep effects were not expanded in this task.

**Verification actually run:** 169 synthetic Python tests and Node controls pass, including decoded spawn fields/timing, size/alpha progression, malformed program rejection, snapshot origin, fractional size and camera-facing geometry. All 18 complete costume clips pass frame-count/authored-loop/20ms timing/transparency checks over 1,979 frames; bubble frames were visually reviewed for both characters. Twelve live HTTP checks verify exact PNG/GIF master bytes for entrance/wait at original and rotated views, and prepared all-color rotated PNG ZIPs at 2048 plus GIF ZIPs at 128 for both characters. Player retains 20,460 clips / 5,013 choices / 32 forms. Generated originals, QA, player, PNG/GIF masters and bundles stay ignored; no dependency or Blender install required. Service restarted on port 8765 in task-owned exec session 25406. Evidence: ignored build/melee_anim/bubbles_qa.

## 51. Measured cost of higher-resolution masters (2026-10-11)

User asked why Game & Watch looks pixelated and how changing all native renders from 256 to 512/1024 affects size. Code-confirmed: current masters are256px, UI displays up to512px, larger downloads resample the256px masters, native coverage is binary and the G&W outline is a one-pixel MaxFilter expansion. No renderer/cache/size policy was changed in this benchmark. Higher native resolution and antialiased outlines/supersampling remain proposals, not implemented.

Rendered complete representative animations at each native resolution with identical current model/pose code (not enlarging an existing image). G&W clapping25frames GIF sizes256/512/1024:42,173 /88,605 /214,101bytes; PNG sequences70,933 /153,585 /365,335bytes. Mario Victory3 101frames GIF sizes809,016 /2,459,595 /7,252,445bytes; PNG sequences2,191,573 /7,052,587 /20,912,960bytes. Compressed GIF growth is about2.1?3.0x at512 and5.1?9.0x at1024 in these two examples; PNG growth about2.2?3.2x and5.2?9.5x. This is not a bound for every character/action. Raw pixels/retained RGBA memory are exactly4x and16x for equal frame counts; render time includes significant fixed startup/pose/encoding cost and is not simply proportional to pixels.

Current984 base results/taunt GIFs total731,721,957bytes; their lossless PNG sequences total1,924,517,544bytes (combined2.656GB decimal). Applying only the observed example ratios gives a rough6?9GB at512 or14?25GB at1024 for that base collection, excluding duplicate ZIP bundles, sync/power/rotation/attack caches and every future on-demand action. This is a projection, not a completed full-roster higher-resolution render. All20,460 catalog choices are not presently rendered into masters. Ignored benchmark script/data/renders:build/melee_anim/resolution_qa. Proposed direction:512px routine masters, optional higher-resolution renders and supersampled antialiasing; preserve original assets, costume IDs and GIF transparency limitations.

## 52. Native 512px masters and explicit upsizing (2026-10-11)

User selected 512 as the default native render resolution after section51's benchmark. [render_settings.py](tools/melee_anim/render_settings.py) now owns MASTER_SIZE=512. Preview CLI, Mario pilot/roster batches, ordinary action cache, rotation/powered/centered cache, synchronized claps and default export requests all use it. Retain original poses/timing/costume IDs; 128 and256 downsample, while1024/2048 upscale the512 masters. Larger downloads still do not rerender extra detail. The native-outline approximation and GIF binary transparency are otherwise unchanged; supersampled antialiasing was not introduced by this resolution change.

The UI defaults to the starred Medium option, labeled native render. For1024 or2048, an adjacent notice states that the image is upsized from512 and adds no detail. The existing dark-yellow2048 large-GIF warning remains separate. Update both notices on size changes, URL restoration and pageshow, including while a preview is pending. Native512 default previews/stills/GIF/color bundles use original files; other sizes use the existing server resampling/export routes. File-origin resized batches retain the exact HTTP handoff.

Action cache keys now name the512 policy; rotation settings hash the native size and all evaluator modules. Sync resume explicitly requires the master size. `preview_gallery --require-all` refuses old-resolution masters, and verify_previews enforces native GIF/PNG dimensions. Original input data and prior content-addressed caches stay ignored; old caches are not reused for the new renderer policy. Stop the running service during master migration and restart after packaging so it loads current metadata/modules.

This resolution migration retains the existing human-reviewed clapping cuts and42-frame sync schedules. `cycles --preserve-intervals` validates costume coverage, original source-frame count/FPS and interval endpoints before updating fingerprints. `sync_claps --preserve-timing` validates each costume's complete source timeline and retains the source schedules, refreshing only fingerprints. Fresh imports continue using ordinary cycle analysis; these preservation flags require existing reports and are for matching source timelines. No speed/cadence/contact/buffer edits are needed to change image resolution.

Migration commands: roster_batch --resume (default512; jobs4..8), cycles --preserve-intervals, sync_claps --resume --preserve-timing, preview_gallery --require-all, verify_previews, then restart player_server. No ISO re-extraction or new dependency is required. Native-master checks and migration evidence remain ignored under build/melee_anim/master512_qa. The existing123-costume results collection is being rebuilt natively; lazy attacks, props/effects, rotations, powers and centered hops render512 on demand rather than pre-rendering all20,460 catalog entries.

**Final verification (2026-10-12):** rebuilt all984 base clips / 81,369 PNG frames and123 synchronized claps natively at512. Full coverage verifier passes native dimensions, all GIF timing/loop/transparency flags, actual123-costume coverage, distinct costume GIFs, 209 GIF-bundle inventories/hashes, and first/frame68/final still-bundle bytes across 17,348 frame bundles. Source sync schedules compare equal to the prior plans except refreshed fingerprints.170 Python tests and Node controls pass, including native512 cache commands/default selection, starred option, notices/restoration and all existing selectors/export behavior. Seven live checks cover native default PNG/GIF bytes, ordinary attacks, impacts, powered Kirby, paired centered hops, all five output sizes and all-color512 still ZIPs. Final production player health reports master_size512 /20,460 clips; served HTML matches the generated file and Mario's native512 paused PNG is byte-identical to its master. Service: task-owned session44919, port8765. Base master storage is 8.19GB decimal (2.19GB GIFs + 6.00GB PNGs), excluding ZIP duplicates and other caches. No original assets or generated outputs are tracked; Git whitespace checks pass.
## 53. Scoped export batches, mixed native resolution and public README (2026-10-12)

Download All now selects a semantic action family across characters and actual costumes, rather than every catalog entry. Victory includes all three entrance/wait pairs (738 GIF jobs); Clapping and Taunt remain within their type. Attack families include grounded/aerial variants, preferring available combined presets over their covered partial phases. Independent phases remain when no matching whole preset exists. batch_exports.py derives families from verified labels/categories and phase IDs; fighter-specific numeric animation IDs are not cross-character identities. Held-item families retain weapon/swing variants, copied specials stay distinct, and missed-tech combinations do not hide independent lying loops.

Kirby Mode - include all hats all colors adds None plus all25 copied appearances in each of six real Kirby colors to batch ZIPs. Examples: clapping123 ->273, victories738 ->1638 and neutral special564 ->1764. Individual downloads retain the selected appearance. Batch options travel in UI handoff/API export requests only, never preview rendering parameters. Server exports now share per-render and per-artifact locks, rather than a whole-batch request lock, and yield between clips. A bounded request semaphore remains. Synthetic concurrency checks cover a foreground preview completing while another batch is waiting.

The user's selected native-resolution policy is1024 for Victory Pose, Taunt and Clapping, and512 for other categories. render_settings.native_size governs preview CLI, base/sync batches, lazy attacks including extra-fighter taunts, rotation/power/centered caches, default exports and coverage verification. UI stars the current type's native size, changes the default when moving between policies, retains explicit nonnative choices and states upsizing only above native size. The2048 dark-yellow GIF warning remains independent. Source timings, costume IDs, sync intervals and cut policies are unchanged.

The prior interruption left this1024 migration incomplete: generated player.html still had512 controls even though its Python TEMPLATE had been edited. Existing worker processes continued rendering after the user resumed; do not start competing rebuilds. The finalizer waits for all984 valid native1024 base masters, refreshes cycle fingerprints with --preserve-intervals, rerenders123 sync clips with --preserve-timing, repackages all GIF/still bundles and generates the player, then runs full verification. Completion/live evidence is recorded below after it finishes. Logs and helper scripts are ignored build/melee_anim/results1024_qa.177 synthetic Python tests have passed; final Node controls and live1024 export verification remain pending.

The root README now explains the Windows ISO/import/open workflow, GIF/paused-PNG and batch features,512/1024 size rationale and storage tradeoffs. The user's final correction is an estimated67GB local checkout, not60GB or35GB; that estimate is neither the repository download size nor a fixed total after future renders. More hats/colors/angles and higher native resolution increase storage;25 powers x6 colors add150 extra Kirby variants per animation. .github/README.md took precedence over the root guide on GitHub; it is preserved as .github/UPSTREAM-DECOMPILATION.md so the root guide is primary. Its directory-relative upstream links remain intact. The user requested a few actual samples/screenshots in the README, authorizing a narrow docs/media exception to ignored game-derived output; full original assets, models, sequences, caches, bundles and QA remain ignored. No new runtime dependency or Blender step.

**Section53 completion:** All984 native1024 base clips /81,369 PNG masters and123 sync clips are complete. Full verify_previews passes native dimensions, source costume matrix, GIF timing/authored-loop/transparency,209 GIF bundle inventories/hashes and17,348 still-bundle inventories/sample byte checks. Sync schedules compare equal except fingerprints. Node controls pass type-specific stars/default transitions/notices, scoped batches, hats, retained frames and existing selectors.13 live checks passed exact native defaults and PNG/GIF master bytes for clapping/taunt/victory, five still sizes,42 uniform20ms sync frames, all five Mario costumes' frame68 ZIP,512 movement,1024 extra-fighter taunt, rotated G&W/powered Kirby,123 native clapping GIFs and cross-ID Master/Crazy Hand families. The diagnostic hats API rendered all26 appearances at one actual source pose/costume0 at1024, producing26 unique transparent128 PNGs; all156 full powered/color animations were not rerendered/certified.180 Python tests now pass including the later outline fix. The final user-reported footprint is67GB, replacing prior60/35/40 estimates.

Actual Chrome headless page captures exposed a native-select handoff bug: assigning a requested action absent from the current category clears the select value before its options are rebuilt. actions(preferred_key) now takes the requested key directly during restoration. Native-select regressions cover victory3, a Fox partial special and full hop; paused frame and partial-filter policy survive. Browser connector surfaces were unavailable; installed Chrome rendered only the local page into curated README artifacts, using an ignored separate profile. Windows IPC required automatically approved elevated execution, without disabling browser security. The prior player also required an approved targeted restart because its process denied ordinary termination. Root README is now primary; upstream .github README is archived at the same directory level. Three renderer samples and two real screenshots are curated in docs/media; raw originals/full outputs remain ignored.

## 54. Original Game & Watch outline geometry and passes (2026-10-12)

User supplied a reduced1024->256 export showing a broken hairline and an in-game image with a substantial gray border. The prior native renderer used MaxFilter(3), a fixed one-native-pixel white RGBA128 border. At quarter size this becomes subpixel coverage; binary GIF alpha removes portions. Raising native resolution never corrected that approximation.

Verified source: ftGw_Init_OnLoad in src/melee/ft/kinds/ftGameWatch/ftgamewatch.c installs items[10].visibility as class4. ftDrawCommon_80080E18's first inline pass hides classes0/1/2 and selects class4 with the same fp->x5F4 group alternatives. ftMaterial_800BF6BC interpolates previous material RGB toward outline RGB using outline alpha, preserving APREV opacity. The following source pass uses PE flags0x38; HSD_SetupPEMode shows RGB/alpha update disabled with depth testing/update enabled. The ordinary black costume therefore has opaque gray128 border, rather than half-transparent white. Other colors retain the corresponding overlay tint.

Class4 groups contain expanded geometry for all11 ordinary appearance groups, including alternative head/attack/sleep shapes. Export all supported alternatives, tag outline meshes, then choose only the body-matching alternatives each frame. The old exporter hid class4 wholesale to prevent overlapping unselected silhouettes; showing all its alternatives would reintroduce that bug. export_model now retains outline_groups/outline_pass/outline_geometry and clones outline materials, so shared primary material definitions remain intact. roster.visible_drawables handles both sets, including timed and combined-phase visibility. game_watch.draw_passes and both raster backends implement outline-color without depth update, opaque body, depth-only outline and translucent attachments. Geometry supplies the authored thickness under projection/resolution; no guessed pixel expansion is needed for actual models. Legacy synthetic models retain their image-mask fallback.

Kirby's copy has its own outline lookup at descriptor+0x18, verified in ftKb_SpecialN_800F14B4 / ftKbCopyParts_GameWatch. Retain its separate replacement-body skeleton/visibility and existing color/root-width/outline attributes. A relocated zero pointer is a valid data[0] address; do not mistake its attribute block for a null pointer. Its original class4 meshes now participate in the same passes. Original assets/DOL/symbols are unchanged; no extraction or new dependency.

Validation:180 synthetic Python tests pass, including RGB-versus-opacity, body/outline alternative selection, native/Python depth/color separation and alpha-aware quarter-size GIF retention. Rebuilt four ordinary models,32 complete results/taunt clips /2784 PNG masters and four42-frame sync claps. Retained previous cuts/sync schedules, refreshed fingerprints and repackaged player/bundles. All32 GIFs have native1024 dimensions, timing and transparency; all2784 PNGs have native1024 RGBA and0..255 coverage. All25 clapping GIF frames retain a substantial opaque gray border at128/256/512/1024/2048. The new984-member aggregate validates all32 changed G&W hashes and952 unchanged entries against the previous full verified manifest. Live HTTP checks pass all four costume256 PNGs, all-color256 PNG ZIP,512 standing, rotated1024 clap and Kirby's G&W copy at1024. Node controls pass after regeneration. Current service: task-owned exec session34690, port8765. Evidence stays ignored under build/melee_anim/outline_qa; curated README G&W sample is refreshed separately. This restores source geometry/color/depth behavior; matched original-game camera/pose comparisons, complete PE/TEV/material callbacks and particles remain future fidelity work.

## 55. Missing Game & Watch attack articles, body parts and optional Judgment9 electricity (2026-10-12)

User corrected the scope from all attacks to many attacks with missing objects, specifically jab, forward smash, back air, Oil Panic catch/shoot and all Judgment numbers. Source investigation distinguishes two mechanisms: separate original PlGw.dat Article models and source-timed visibility alternatives already in the fighter model. Profiles are explicit, never a generic prop attached to every attack. GameWatch Article slots:0 Greenhouse spray,1 Manhole,2 Fire/torch,3 Parachute,4 Turtle,5 Breath/air puff,6 Judge/sign,7 Panic/oil,8 Chef/food projectiles,9 Rescue/firemen;10 installs the fighter outline visibility lookup. Slot8 food-flight/controller work was not added. Pan/chair/key/hammer/bucket silhouettes require original opcode31 model-part events and callback state.

Verified attachment call sites in ftgamewatchattack11/attacks4/attacklw3/attackair/specials/speciallw/specialhi and item implementations: raw32 for spray/torch/manhole, raw1 parachute, raw17 turtle, raw21 air puff and raw0 oil/rescue. The Judge spawn explicitly maps canonicalRThumbNb49 through ftParts_GetBoneIndex; preserve that distinction. Item outline callbacks it_8027CE64 / itdraw use separate normal/outline joint lists in specialattrs.x0. Retain their authored mesh/visibility curves and use the fighter's actual RGB plus the source gray outline overlay, without tinting unrelated items. Source limbs/materials/whole-motion framing are shared by all four actual costumes, rotations and exports.

The18 Side-B submotions297..305 grounded /306..314 aerial share packed SpecialS/SpecialAirS names. game_watch_attacks.prop_profile identifies the number from verified IDs, requests original item animation at number1..9 and freezes it as it_80273670 does. Joint branch curves choose the actual digit; no generated numeral artwork. it_802C78B8 sets sign child2 Y rotationpi for facing1. cmd_var1 tick16 spawns the sign. Labels name Judgment1..9 while keys/families remain unchanged. The first prototype used Greenhouse states1/0 for jab/start, but source DecideAction/CheckAttack11 verifies0/1; final profiles use0/1/2/3 for jab/rapid-start/loop/end. Combined rapid jab retains each phase-local prop curve.

G&W attacks now evaluate bounded original timed model-part commands, so the Chef pan, hammer, chair/key and other source alternatives are visible after waits. Bucket callback group5=2 is included at guard activation; standalone catch is explicitly one received charge. ReleaseOil clears charge before UpdateBucketModel, so shoot indicators are empty. The original Panic article supplies the oil geometry/curves. These are isolated animation presets; input-dependent holds/turns/charge values, collision, stage motion and procedural source article controllers remain limitations rather than a full game simulation.

Optional9 effect: conditional checked-by-default Electric hit explosion (9), only305/314. ftcoll.hit_effect_ids maps Electric to gfx1001; efAsync case0x3E9 calls generator12, whose original program spawns13..18. electric_burst.py decodes those bounded original commands/sprites (size/color/pose/random/loop/rotation and supported position/velocity operations) with seed12. It snapshots the source hammer head at tick16 and uses a planar contact preset; no target or actual hit detection. Full fractional particle sampling, dynamic spread/physics/GX depth/blending are not certified. For portable transparent assets the light burst uses emissive alpha, preserving premultiplied radiance and omitting zero-radiance dark cards; this is a documented export approximation. Fit whole visible content per setting; effects off uses fighter/prop framing. API electric=on|off and CLI --judge-electric follow preview, paused frame, every size/color, rotation, batch scopes and file-to-HTTP fragment. Cache identities include setting/EfCo data; off filenames include no-electric. Preview-only option defaults on, not a permanent edit to original assets.

Verification:184 Python tests pass, including source profiles/raw-canonical selection, all18 frozen numbers, bucket callback timing/charge reset, deterministic particle loops and source geometry transparency. Node controls pass default-on/9-only visibility, off URLs and filenames, exact/color exports, paused frame retention and handoff.40 complete targeted default-costume clips rendered (separate articles, body parts, all18 numbered variants, combined rapid jab). Live checks confirm9 on/off both43 frames with identical source times; exact256 paused PNGs; electric-off yaw20 all-four-color128 PNG ZIP with unique no-electric names; and real spray/torch/turtle/catch/oil PNG requests. Final audit passed all40 GIFs' dimensions/timing/transparency and1464 sampled RGBA PNGs, plus default-on electric GIFs in all four source colors at256. Served player.html matches the generated file. No new dependency, source game modification or ISO extraction. Two stale duplicate Python listeners on8765 were verified by repository health/root and restarted; final task-owned service session90173. QA/models/frames/caches remain ignored under build/melee_anim/gw_attacks_qa and the existing caches. Matched original-game reference, full article material/scripts/controllers/physics and projectile effects remain future work.


## 56. Yoshi white cheek/belly texture masks (2026-10-12)

The reported solid-green Yoshi was caused by missing material composition, not missing image assets. All six original costumes (PlYsNr/Re/Bu/Ye/Pi/Aq) have paired UV textures: a base costume skin and an RGBA marking layer. Original mask textures visibly contain white cheek/belly regions and transparent skin regions. Example material0 uses flags0x30010/source4 for skin and0x10010/source5 for markings; multiple other body materials follow this pattern. Source TObjMakeTExp in src/sysdolphin/baselib/tobj.c interpolates incoming RGB and texture RGB using texture alpha for COLORMAP_ALPHA_MASK. ALPHAMAP_NONE keeps the incoming opacity. The prior renderer selected only one texture and multiplied full-BLEND skin by gray diffuse, omitting the white layer entirely.

export_model enables diffuse_texture_only for ordinary FighterKind14 and color_alpha_mask_layers for Yoshi. Kirby Yoshi hats have the same two-texture material; model_for_power passes an explicit color_mask_preview based on the copied fighter kind. Preserve every actual Yoshi/Kirby costume and original image/palette/UV data. This supports the observed RGB mask / alpha-pass material, without broadening other fighters or claiming complete TEV interpretation.

The Python raster samples each overlay using its own UV set, original texture matrix and wrap modes, interpolates RGB before lighting and retains base alpha. The native memory-DIB OpenGL backend uses a matching second surface pass with equal depth, RGB-only writes, no depth update and SRC_ALPHA/ONE_MINUS_SRC_ALPHA blending. Light modulation matches the base surface. Transparent parts of the mask therefore retain skin rather than cutting holes; opaque white regions replace skin. Tests cover a distinct second UV set, opaque/half/zero mask alpha and transparent background in both backends.

186 Python tests and Node controls pass. Rebuilt all six ordinary models and48 full results/taunt clips, totaling3078 native1024 RGBA PNG masters. All48 GIFs passed native dimensions, transparency and accumulated source timing, with sampled first/middle/final PNG coverage checks. Source minimum/dirty intervals and synchronized schedules were preserved; only six42-frame sync jobs required rendering. Refreshed eight six-color GIF/still families, the984-member aggregate and generated player. Source files and QA remain ignored under orig/ and build/melee_anim/yoshi_qa. No installation or ISO extraction is required. General TEV/material callbacks and matched game-reference fidelity remain separate work.

Final live verification: each of six taunt PNG downloads byte-matches its1024 source master and contains opaque white markings. Standing, forward smash, effects-off Knockdown and yaw25 clapping export transparently at256 through the lazy/rotation caches. A full Kirby Yoshi-hat clapping render supplies a transparent512 paused PNG; its white cheek patches were visually reviewed. All five128/256/512/1024/2048 still sizes and six-color256 GIF/PNG ZIPs pass. Six sync GIFs retain42 samples/840ms. Served player.html byte-matches the regenerated file. Current task-owned player service: exec session1315, port8765.


## 57. Original results lighting for clapping and victory poses (2026-10-12)

The comparison sheet shows absent highlights and dark faces in the isolated renderer. It used a generic .6 ambient + .4 directional scalar, did not export material ambient/specular RGB or shininess, and discarded original specular texture maps. The user additionally requested this correction for all victory entrances/waits. Source fn_8017A004 in src/melee/gm/gm_1798.c loads data->pnlsce->lights through lb_80011AC4. The extracted GmRst.usd panel and full results scenes (pnlsce/flmsce) contain identical unanimated lights: ambient flags0x4, RGBA[179,179,179,255]; infinite light flags0xD (diffuse/specular), RGBA[255,255,255,255], position[.57,.57,.57]. Those source values replace the preview's arbitrary rig for results-clap and every victory action. Other categories retain their current preview lighting.

HSD_Material contains ambient/diffuse/specular GXColors, alpha and shininess at +0/+4/+8/+12/+16. inspect_models.material now exports all these fields. state.c HSD_SetupChannelMode multiplies material ambient by ambient-light color, combines directional N dot L and clamps the channel. mobj.c composes diffuse textures before lighting, then adds the independent specular channel. Full-BLEND diffuse stages replace their incoming RGB. Original specular maps use independent UVs and TEX_LIGHTMAP_SPECULAR, with BLEND/MODULATE/REPLACE operations. Inventory across32 default models found zero or one specular map per material, all UV, with125 such maps and inspected custom specular TEV active flags0. Original bump flags occur on some Samus maps; complete hardware bump-coordinate generation is not implemented.

lobj.c HSD_LObjSetup uses specular coefficients(0,0,1) and(shininess/2,0,1-shininess/2). lighting.py evaluates the resulting GX rational attenuation x squared / (shininess/2 + (1-shininess/2)*x squared), using the light/view half-vector. No guessed Phong exponent or universal shine tint is used. Source material RGB and texture masks control the added light. The existing orthographic viewer supplies its direction rather than reproducing the original per-portrait perspective camera; full runtime/TEV/bump/shadow/material-channel fidelity is still not certified.

Python applies supported RGB factors/specular maps without changing source alpha. Native rendering uses source-lit vertex RGB and a same-surface additive specular pass, equal depth, RGB-only writes and no depth update. Texture alpha never punches holes in ALPHAMAP_NONE specular stages. Original unlit G&W and Samus visor policies remain respected; scene lights stay fixed in game axes while camera rotation changes the highlight half-vector. Both ordinary and Kirby appearance materials use the same path; no additional dependency, ISO extraction or manually repainted textures.

Five default-costume matched-pose1024 probes (Marth24, Samus24, Falcon12, Peach30, Mario24, nearest existing source sample) show restored highlights and brighter faces. Before/after images are ignored lighting_qa/comparison.jpg and lighting-detail.jpg. Preserve all original861 results source timelines/framing/loops,123 sync schedules and minimum/dirty source intervals. roster_batch now accepts --action results to rebuild exactly clapping and all victory entrance/wait clips; default all retains the ordinary workflow. Render manifests include light source/hash and supported camera policy. Resume compares light descriptors; rotated/powered caches include original GmRst bytes. Full rebuild/packaging/live completion evidence is recorded below.


**Section57 completion:**192 Python tests and Node controls pass. Rebuilt861 complete actual-costume clapping/victory clips (123 claps plus738 victory entrances/waits), totaling71331 native1024 PNG masters. All source times, FPS, authored-loop flags and camera centers/scales compare equal to the saved pre-change manifests. All five matched-pose before/after probes have byte-identical alpha coverage. Original minimum/dirty cuts and every sync schedule were retained;123 synchronized clips have42 samples and source-light provenance. No original game bytes changed.

Refreshed182 affected six/variable-color GIF/still families, the984-member aggregate and generated player. Full verify_previews passes984 clips /81369 PNG masters,209 GIF ZIP inventories/hashes and17348 still ZIP inventories/first-frame68-final sample byte comparisons. Original taunt pixels were retained; their source model metadata gained ambient/specular/shininess fields, so future resume/rotation hashes may regenerate them despite unchanged lighting. Bulk assets and comparison images remain ignored.

Live HTTP verification passes exact1024 clapping PNGs for all26 selectable forms with Zelda and Sheik separately; all three Marth/Samus victory entrances AND waits; yaw25 Samus clapping/Marth victory; Kirby Samus-hat clapping and Yoshi-hat victory wait with the same source rig; five128/256/512/1024/2048 still sizes; actual Samus all-five-color256 GIF and PNG ZIPs; and minimum/dirty/sync GIFs with the original840ms sync duration. All123 sync manifests carry the rig; schedules compare equal except refreshed fingerprints. Served player.html matches generated HTML. Final task-owned service is exec session54811 on port8765. These checks restore supported source lighting/material channels; exact original perspective, complete bump/TEV/material animation, cast shadows and matched emulator-reference certification remain unfinished.


## 58. Gameplay lighting comparison and one lit preset for all poses (2026-10-12)

The user liked the results lighting, requested it for every animation and asked whether gameplay uses the same lighting. They also explicitly said to omit lighting-off if it requires re-rendering or storing another set of GIFs. The current app displays flattened PNG/GIF frames; switching the 3D light calculation changes rendered RGB and cannot be applied to an existing GIF without rendering new frames. On-demand variants would avoid rendering every clip upfront but retain both variants after use. Therefore no off checkbox/API/CLI option or paired unlit dataset was added. Historical cache revisions can still accumulate under the existing cache policy; this change does not promise a fixed disk size or delete old caches.

**Verified gameplay comparison:** Ground_801C466C in src/melee/gr/ground.c selects a light group from the stage callback flagged as its lighting group, applies Ground_801C20E0 overrides and falls back to Ground_803E06C8 when none is selected. Lights can animate and their positions are stage-scaled. Original DOL default descriptors have ambient RGBA[255,255,255,255] and infinite flags13 white diffuse/specular light at(.57,.57,.57). Results use the same infinite light, with ambient179. Battlefield grNBa_StageCallbacks marks object6; GrNBa.dat group6 has ambient128 and the same white directional light. Thus the mechanism and common direction match, but ambient strength differs. Raw Final Destination groups have ambient76 plus differing directional setups; Fountain groups have ambient128 and colored point lights, with animated groups. These raw values are not certification of the final override/animated gameplay state.

The new reusable command python -m tools.melee_anim.inspect_lighting reads results descriptors, named original-DOL fallback globals and map_head object light arrays in the extracted stage archives, recording source offsets/flags/RGBA/positions/animation counts and explicit limitations. Default archives are GrNBa.dat, GrNLa.dat and GrIz.dat. JSON remains ignored; the current task report is build/melee_anim/all_lighting_qa/gameplay-comparison.json. No disassembly, new dependency or ISO re-extraction is needed.

**Implementation:** preview.main now always supplies the original results rig to every supported action, instead of limiting it to results-clap/victory. This covers all taunts, attacks/combined phases, movement, hops/centering, sleep/dodges, Knockdown/Hit/Other, extra fighters and Kirby appearances. Both raster backends already consume the shared material ambient/specular/shininess/UV masks. Keep source unlit G&W/visor/prop policies and original emissive effect rendering. This is a consistent isolated-asset preset; no stage selector or unspecified live stage environment is being simulated. Exact original perspective/bump/TEV/material animation/shadow fidelity remains unfinished.

Both ordinary AttackCache and RotationCache now include GmRst bytes for every action, retaining all existing model/module/prop/effect fingerprints. Stale ordinary/powered/rotated masters refresh on demand rather than eagerly rendering19476 ordinary costume choices. Prebuilt taunt resume also requires matching light provenance. Refreshed six extra-fighter models and verified ambient/specular/shininess fields across all129 primary actual-costume models. Rebuilt123 native1024 taunts /10038 RGBA PNG masters and26 all-color GIF/still families, refreshed the984-member aggregate and generated player. Existing clapping/victory masters and synchronized schedules retain their original lighting/timing; no off variants were created.

194 Python tests and Node controls pass, including source-light invalidation for ordinary/taunt caches and stale unlit-taunt rejection.51 complete native clips /5941 PNG masters across all32 forms passed source-light provenance, GIF dimensions/timing/transparency and sampled first/middle/final RGBA checks. The examples include six common held weapons, blaster/needles/Cutter, reflector effects, full/short hops, sleep, dodge, Hit and impact-on/off Knockdown. Live exact paused PNG exports byte-match these masters and1024 taunts. Source/game-derived assets, logs and QA remain ignored. Final full bundle/rotated/powered/centered/color/size verification is recorded below.


**Section58 completion:** Full verification passes984 original-roster clips /81369 PNG masters,209 GIF bundle inventories/hashes and17348 still-bundle inventories/sample byte comparisons, including updated taunts and the aggregate. Live exports byte-match paused frames from all51 representative clips across32 forms and selected1024 taunts. Rotated Samus standing/forward smash, Kirby Samus appearance and centered Kirby Yoshi short hop carry the same source-light provenance and export transparently. All five still sizes pass; actual Samus all-five-color256 taunt GIF, forward-smash GIF and forward-smash PNG ZIPs contain the expected unique costumes/sizes. Served player matches regenerated HTML. Final service: exec session83416, port8765. Original source assets and QA remain ignored; the inspection tool/code and notes are the reusable deliverables. Lighting-off remains intentionally omitted per the user's condition.


## 59. Download progress for rendering and size conversion (2026-10-12)

The user reported slow downloads after selecting a different size, with only an indefinite spinner. A size change often resizes/quantizes/encodes existing PNG/GIF masters rather than performing a new3D render. The new UI therefore shows both animations ready X/N and files ready Y/N, a preparation-work progress bar and actual active frame counts. Cached outputs count as ready, avoiding false claims of new rendering. GIF/PNG and color/matching batches share one lock/spinner/progress display and capture the click-time URL/filename. Progress finishes when the artifact is ready; native browser file transfer has its own progress.

The existing synchronous /prepare-export route accepts an optional random progress ID, registers a locked ProgressRegistry record and includes final progress in its ready URL response. /export-progress?id=... polls the record without taking any of the four renderer request slots. Compatibility is retained when no ID is supplied. Registry capacity64 and completed/error TTL600 seconds bound memory; active records cannot be evicted or overwritten by duplicate IDs. IDs remain metadata, never file paths/render settings. Snapshots use Cache-Control:no-store. Failed preparation records an error and the existing HTTP status, without leaving the UI busy.

AttackCache/RotationCache optionally monitor fresh render.log stdout every300ms, interpreting the renderer's reported n/N frames rather than counting stale files from an interrupted cache. After the last frame the phase says Encoding rendered GIF until master preparation finishes. DownloadCatalog reports animation readiness and conversion/file/ZIP progress. resize_gif/cycle_gif, quantize_rgba and encode_frames optionally emit actual per-frame callbacks; GIF bytes/alpha/timing are unchanged. The work bar uses monotonic preparation units across animation readiness, file conversion and ZIP packing, not an estimated time remaining.

Player polling starts after250ms and continues every500ms. Stop/clear it on completion/failure and ignore late responses; a polling outage does not fail an otherwise successful export. The ready response carries final counts for exports completing before the first poll. All five buttons share duplicate protection. Native static downloads retain HEAD validation; file-origin single GIF/PNG handoffs use UI-only single-gif/single-png markers, alongside prior batch markers, preserving exact costume/power/cycle/frame/angles/effects/sizes. Render/export parameters do not acquire these UI markers. Right-click/Open GIF behavior remains unchanged.

Verification:199 Python tests and Node controls pass. Regressions cover bounded/expired/active/duplicate records, independent polling during preparation, actual render-log counts, unchanged GIF bytes with callbacks, real resize/quantize/encode counts, cached repeats, monotonic preparation work, single/batch locks, completion, stale responses and error/timer cleanup. Live HTTP tests pass real Samus all-five-color1024-to512 GIF conversion and ZIP dimensions/transparency, cached reuse without fake conversion counts, a cold69-frame standing render with frame progress and exact128 RGBA PNG output, and invalid-size error reporting. Served HTML byte-matches the regenerated player. Logs/states/assets remain ignored build/melee_anim/progress_qa. Two duplicate listeners were verified as this repo's Python player (one with explicit root/port, one module-only) and restarted; final task-owned service is exec session20971 on port8765. No new dependency or asset/model/master/bundle rebuild.
