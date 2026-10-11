# Guidance for future agents

## Purpose and user requirements

This is a fork of the Super Smash Bros. Melee decompilation used to build an animation asset generator. The intended program loads the game's assets using behavior documented in the decomp, plays selected character animations, and exports MP4, GIF, or both. Smooth looping is a priority where the original motion supports it.

The first targets are the three victory animations and loser clapping animations from the results screen. Extend to taunts, forward smash and other moves, then hit reactions, tumble, knockdown, and ground/recovery motions. Support isolated character assets and, later, the composed results screen with winner(s), loser squares, and results presentation.

The user explicitly clarified that **every color means every actual costume variant available to each character**, whose count varies. Record the selected action for all those variants. Do not use a universal costume count, arbitrary tinting, or distinct archive filenames as the definition of a costume. Python is the user's most comfortable language; keep the ordinary workflow understandable in Python.

## Read these first

- [INVESTIGATION.md](INVESTIGATION.md): verified source paths, identifiers, asset availability, and limitations.
- [PLAN.md](PLAN.md): proposed architecture, playback/export policies, and milestones.
- [TODO.md](TODO.md): ordered work with completion criteria.
- [tools/dat-cli/README.md](tools/dat-cli/README.md) and [tools/dat-cli/TODO.md](tools/dat-cli/TODO.md): existing DAT utilities and known gaps.

Initial source investigation: 2026-10-10, source commit `79b13a32467f7c4f91d6f831f0b9f891b7fb1146`. Follow-up work implemented extraction, inspectors, a full roster action/costume inventory, GX pixel decoding, a neutral Mario model exporter, and a Python CPU animation preview renderer. A working offline frame player and animated GIFs now exist. Full roster rendering, Blender integration, faithful gameplay scripts/props/dynamics, and MP4 encoding remain unfinished.

The supplied `melee.iso` is now extracted to `orig/GALE01`: 1,209 game files plus five system files, all output hashes verified. GALE01 disc revision 2; original DOL SHA-1 `08e0bf20134dfcb260699671004527b2d6bb1a45` matches `config/GALE01/config.yml`. ISO SHA-256 is `0de05981a34156b9cedcef73c73d4244ac05cf6149ab3c9cfed917698819e464`. The local extraction manifest records provenance and all output hashes; reruns are verified/idempotent. ISO, manifest, every output, reports, and bytecode were individually checked as ignored. Recheck provenance for any replacement assets; do not mix revision-specific tables with another executable.

Working commands, from repository root:

```powershell
python tools/melee_anim/extract_iso.py melee.iso
python -m tools.melee_anim.inspect_motions --output build/melee_anim/motions.json
python -m tools.melee_anim.inspect_models --catalog
python -m tools.melee_anim.inspect_models --all-models --output build/melee_anim/all_models.json
python -m tools.melee_anim.inspect_results_scene
python -m tools.melee_anim.catalog
python -m tools.melee_anim.export_model --costume 0
python -m tools.melee_anim.preview_batch --action results-clap --costume all
python -m tools.melee_anim.preview --action taunt --size 256 --output build/melee_anim/preview/mario/costume_00/taunt_source
python -m tools.melee_anim.preview_gallery
python -m unittest discover -s tools/melee_anim/tests -v
node tools/melee_anim/tests/test_gallery.js
```

Extraction/inspection and texture codecs use the standard library. Model export/rendering also use installed NumPy 2.2.4; the preview uses Pillow 11.1.0. Node is used only for player-logic tests. Generated metadata, models, decoded textures, frames, GIFs, and player output remain under ignored `build/melee_anim`. Keep notes in these four documents, as requested. Original asset bytes must remain ignored.

## Design direction to preserve

- Python owns the CLI, catalog, jobs, costume batching, manifests, and FFmpeg export orchestration.
- The first preview is a CPU renderer using already-installed NumPy/Pillow, so Blender is optional for that proof. Blender remains the planned production renderer; setup steps are in `TODO.md`, and no Blender importer is implemented yet.
- Reuse the decomp's tables and HSD animation semantics. Reuse or extend `tools/dat-cli` for archive inspection and validation before building another general type system.
- Build the first importer on the working focused Python reader/evaluator in `tools/melee_anim`. Actual asset inspection succeeded without a native helper. Keep the interface clear; use native/HSDRaw as targeted references or replacements when measured problems justify them. Full matrix/renderer fidelity remains unproven.
- Keep native helpers as small subprocess adapters initially. Do not require a complete host game port or Python access to raw game-runtime pointers.
- Use Dolphin as a reference and possible capture backend for runtime-dependent/full-scene fidelity. Do not assume stock Dolphin has a Python scripting API.
- Prioritize default Mario clapping -> PNG sequence -> verified MP4/GIF -> every Mario costume -> wider results coverage.
- Preserve the original decomp source and build purpose. Place new product code in a separate tool/package; make source/type improvements only when required and justified.

These are documented implementation decisions/recommendations backed by the current inspection, not claims that a complete renderer or dependency installation was approved or verified. No dependencies were installed during extraction. New evidence can change a backend choice; update the plan and rationale explicitly.

## Source landmarks and traps

1. Results archive names are in `src/melee/gm/gm_1601.c`, `lbl_803D53A8` / `gm_80160438`: `GmRstM??.dat`, e.g. `GmRstMMr.dat`. They are separate from normal `Pl??AJ.dat` gameplay animations.
2. `src/melee/gm/gm_1798.c`, `fn_8017A67C`, selects game victory variant 0/1/2 or loser variant 4, sets costume ID, and instantiates demo fighters. User-facing victory numbering 1/2/3 needs an explicit mapping.
3. `src/melee/ft/ftdemo.c` uses a separate demo motion table. Its numeric motion states reuse common `Dead*` enum labels; those names do not make the results motions death animations. Do not substitute the ordinary action table.
4. `ftData.xC` holds ordinary motions; `ftData.x14` holds demo motions. Motion-state ID, animation/submotion ID, packed-file offset, demo variant, and costume ID are different values. Keep them distinct in types/manifests.
5. `src/melee/ft/ftdata.c`, `CostumeListsForeachCharacter` and `ftData_803C2360`, together with each fighter's `*_CostumeList` / `*_Init_CostumeStrings`, supply actual costume counts and asset references. `gm_GetNumCostumesForCKind` supplies the selectable roster view.
6. Mr. Game & Watch has four costumes sharing `PlGwNr.dat`; `ftGw_Init_OnLoad` applies the color indexed by costume ID. Preserve all four jobs. Ice Climbers require paired Popo/Nana mapping. Zelda/Sheik have form-selection behavior in results.
7. `src/melee/lb/lbanim.h` describes `FigaTree` / `FigaTrack`; `lbanim.c` attaches tracks to the joint hierarchy. Preserve node order, count/termination rules, channel defaults, and scaling behavior.
8. DAT descriptors use big-endian structural values and 32-bit offsets. Packed FObj value streams have their own little-endian numeric decoding in `src/sysdolphin/baselib/fobj.c`. Never blanket-byte-swap raw animation blobs.
9. `src/sysdolphin/baselib/aobj.c` and `fobj.c` define first-play, rewind/end frame, and interpolation behavior. Bake evaluated source poses initially; replacing all curves with linear interpolation changes the animation.
10. `tools/dat-cli/native` converts descriptors to host-native objects, but keyframes, texels, scripts, and GX display lists remain raw. Archive externs are left null; required cross-archive links need explicit resolution.
11. The Rust `symbols check-motions` still covers only ordinary motions and was not run here. The new Python inspector checks 8,011 ordinary references and 244 results references within 27 internal fighter regions / 26 archives, including owning public boundaries and exact sizes/names. Do not conflate this with fixing the Rust type walk or running its native tests.
12. The root CMake native preset builds a 32-bit static library and excludes rendering-related files such as `pobj.c`. It is not a ready-made player. The DWARF ELF tolerates unresolved symbols and supplies type information, not runnable-game evidence.
13. The actual results data includes nonlooping `Win1/2/3` and separate `Win1Wait/Win2Wait/Win3Wait` at IDs 1/3/6. Most wait clips loop; Falco's `Win3Wait` does not, and Fox has an extra `Win2Wait2` at ID 4. Authored wait assets do not establish an automatic original-scene transition. All 27 `Lose` clips are motion-loop marked.
14. All 123 selectable costume references plus four Nana entries were validated (124 distinct model archives). Hierarchy matches within all 27 internal fighter families, but 20 have different bind SRT across costumes. Preserve per-costume defaults. Mario's five costumes match in both hierarchy and bind SRT and are the simplest pilot.
15. A single unit-weight envelope entry can use a joint-global matrix directly; mixed weights use joint-global times stored envelope matrices. Raw mesh coordinates need conversion per palette/corner before assigning ordinary Blender weights. Preserve matrix palette indices, rigid attachments, normal transforms, classical-scale flags, and source part mapping.
16. Resolve localized source basenames before opening them: Captain costume 2 is `PlCaRe.`, which becomes `.usd` or `.dat` according to language. Do not create an extra costume job for a language variant. Game & Watch also applies Z width approximately 0.01 and an outline as well as costume material color.
17. Model files include mutually exclusive drawable alternatives and reflection/second-UV textures. Do not show every DObj or treat every TObj as a single base-color image. Mario `Lose` has only an end command; generic state initialization/part defaults supply additional appearance behavior.
18. `inspect_motions.py` now includes 53 taunt clip entries: 40 unique standard clips, 12 Fox/Falco multipart stage clips, and Nana's shared Popo clip record. Zelda and Sheik have separate files, rigs, and durations (90 vs 100 source frames). All taunts are one-shots. Preserve left-facing fallback state plus facing sign when no separate left archive exists.
19. Mario's taunt alone uses FigaTree type 0 and intentional enlargement around 2.25x; results clips use type 1. `preview.pose_matrices` sets/clears classical-scale flag 8 only on animated joints, and reuses the source-guided matrix/skin helpers from `export_model.py`.
20. The hat texture needs authored S repeat 2 plus GX mirrored wrap, not a universal UV flip. Apply the exported texture matrix to `[u,v,1,1]` before wrapping. CMPR uses the GameCube's 3/8 interpolation; transparent CMPR pixels retain RGB. Frame-zero material animation supplies the initial eye images.

## Animation and export rules

- Separate skeleton-clip playback from full gameplay behavior. Attacks and damage scenarios can depend on scripts, props/items, particles, root motion, hitlag, knockback, collision, procedural bones, and state transitions.
- Do not promise every victory/action is naturally seamless. Expose the authored loop, entrance, one-shot, and explicitly edited loop as distinct modes.
- For a source loop, store samples over `[start, end)`. Check both the unwrapped exact terminal key and the limit approaching it, plus derivatives and actual repeats. Looping evaluation wraps at `end`; even a matching unwrapped terminal key can hide a preceding step. Mario `Lose` is 18 source frames with equal exact keys but preliminary four-finger Y-rotation limit differences around 0.084198 radians. Do not claim a perfect seam or silently repair it without rendered verification and an explicit edited mode. Do not add a duplicate endpoint pause.
- Check root movement, derivative continuity where meaningful, materials, visibility, accessories, and procedural state. Warm up dynamic systems when needed and use deterministic seeds/initial conditions.
- Keep source game ticks separate from output frame rate. Record exact timing and source intervals in manifests.
- Preserve PNG sequences as the lossless master; provide explicit background selection for the usual H.264 MP4 preset. GIF has palette, transparency, and timing limits. MP4 playback looping is controlled by the player.
- Batch by actual costume ID and action variant. Use consistent whole-animation framing, stable names, resumable jobs, and explicit unsupported/failure reports. Never silently substitute costume 0.

## Workflow and verification

Keep original game data local and out of Git. Existing `orig` ignores cover game inputs; add ignores for new caches/exports when implementation creates them. Do not download replacement game assets as part of routine implementation.

Update the investigation with concrete relative source links, symbol names, and evidence. Distinguish code-confirmed behavior, asset-confirmed facts, observed runtime behavior, and proposals. Actual clip names, lengths, full costume compatibility, and rendered fidelity cannot be certified from filenames alone.

Run focused checks appropriate to changed code. Useful checks include malformed/packed archive bounds, mixed endian keyframes, interpolation reference samples, skeleton/channel mapping, costume enumeration with shared files, loop timing, and decoded video duration/frame count. Use synthetic fixtures without embedding original assets in repository tests. Review rendered reference poses and repeated seams visually.

For native/type changes, use the repository's documented build/validation checks when the required tools and original files exist. Record which checks were actually run and what could not be run. Do not label a documentation review or type-only build as a successful animation render.

The initial Windows session's default MSYS Git failed to initialize its signal pipe; `C:\Program Files\Git\cmd\git.exe` worked. Use a working executable if that recurs. For programmatic batch ignore checks use NUL-delimited `git check-ignore -z --stdin` with binary input/output; Windows text-mode CRLF can alter paths. Python 3.13, CMake, and .NET were found; Blender/FFmpeg and other tools were not on PATH, which does not establish they are uninstalled. Extraction tests use temporary directories under ignored `build/` because this sandbox could not write Python 3.13's restrictive default temporary-directory ACLs.

Leave existing user changes intact, keep the checklist current, and describe backend decisions and remaining fidelity gaps in the plan so future work does not repeat this investigation.

## Immediate handoff — user requested a stopping point

Update after resuming (2026-10-10): the user requested every Mario preview animation in every costume, with explicit GIF saving. `preview_batch --action all --section all --costume all --resume` now covers eight animation/section choices across five actual costumes (40 jobs), including all three victory entrances/waits and taunt. It supports bounded concurrent rendering and reuses matching complete jobs. `preview_gallery --require-all` requires that full matrix before publishing the completed viewer.

The completed viewer has independent Animation and Costume selectors that preserve the selected color, a uniquely named Download GIF link, one ZIP per animation containing its five colors, and a full 40-GIF ZIP. All 40 jobs/2,975 PNG masters, GIF durations/loop flags, distinct color hashes, ZIP inventories/hashes, and Git exclusion were verified. Outputs stay under ignored `build/melee_anim/preview`; the full bundle is `downloads/mario-all-animations-all-colors.zip`. Download/resume tests bring the Python suite to 60 tests; Node control/download tests pass. Stale extra PNG files are now rejected before rendering; source culling/timing policy and compound clip bounds remain open.

Stop state: investigation is complete for requested victory/clapping/standard-taunt clips and actual costume variants. `catalog.py` joins 26 forms / 123 costumes into 1,123 jobs including primary victory waits, both taunt facings, and optional stage sequences. It does not include Fox's extra `Win2Wait2` as a job yet, although the motion report does contain it. Structural checks found matching clip node/model joint counts for every standard action/costume pair; full visual fidelity is not established.

At the earlier stopping point, twelve Mario clips and 655 PNG masters existed. The resumed batch expands this to all eight animation/section choices for all five costumes. Open `build/melee_anim/preview/player.html` in a normal browser; it needs no server. The browser connector remains unavailable, so do not claim a live browser UI test. Player control/download logic is covered by Node tests and rendered images are inspected directly. No original game executable or source runtime was changed.

Resume in this order, without re-extracting or rebuilding the investigation:

1. Fix the remaining bounded prototype defects in `preview.py`: respect exported PObj cull flags (`0x4000` front / `0x8000` back), and explicitly handle/report GIF time-grid rounding and the extra terminal one-shot hold. Stale extra frame files are already rejected by render/resume/gallery validation. Existing 40 outputs have verified frame counts.
2. Bound `preview.load_clip` to `outer.public_extent(motion_file_symbol)` before supporting compound result archives. Current Mario has one root and is correct, but Popo/Nana share an archive. Add focused tests and rerun the existing suite.
3. Add an FFmpeg encoder consuming the manifest's explicit frame count/fps, with `ffprobe` verification. Manual installation steps and a conversion example are in `TODO.md`; do not install software automatically just to complete this handoff.
4. Verify the current rendered poses against an isolated Slippi/Dolphin reference. Installed binaries exist at `C:\Users\tycre\AppData\Roaming\Slippi Launcher\netplay\Slippi Dolphin.exe` and the sibling `playback` directory. No emulator was launched or its user configuration changed. Use a separate task-owned user directory for a future capture harness.
5. Extend model export/visibility and scripts one fighter family at a time using the catalog. Prioritize separate Zelda/Sheik, a six-costume family, Game & Watch colors/width/visibility, and paired Ice Climbers. Preserve each costume's bind defaults, source fighter fallback, runtime props, and material changes. Do not announce all-roster rendering from catalog coverage alone.
6. Add the planned Blender backend when installed; reuse neutral models/poses, not another DAT parser. Keep the current CPU player as a diagnostic reference. Complete explicit loop QA/edit policy before claiming perfectly seamless production assets.

Remaining limits: approximate CPU shading/reflection, no timed gameplay script execution, props, particles, secondary dynamics, or audio; pilot renderer supports Mario only. The original finger seam is preserved. Source timing is an explicit nominal 60-tick/s preset, not measured emulator timing. Wait GIFs round to 0.84s rather than 50/60s; one-shot taunt is 3.02s including the terminal hold. Leave these facts visible in manifests/notes until resolved.
