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

Initial source investigation: 2026-10-10, source commit `79b13a32467f7c4f91d6f831f0b9f891b7fb1146`. Follow-up work implemented extraction, inspectors, a full roster action/costume inventory, GX pixel decoding, a neutral Mario model exporter, and a Python CPU animation preview renderer. A working offline frame player and animated GIFs now exist. All 26 selectable character entries / 123 costumes now render eight animation choices each (984 GIF jobs and 81,369 PNG masters). Blender integration, faithful timed gameplay scripts/props/dynamics, and MP4 encoding remain unfinished.

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
python -m tools.melee_anim.roster_batch --resume --jobs 8
python -m tools.melee_anim.cycles
python -m tools.melee_anim.preview_gallery --require-all
python -m tools.melee_anim.verify_previews
python -m tools.melee_anim.player_server
python -m unittest discover -s tools/melee_anim/tests -v
node tools/melee_anim/tests/test_gallery.js
```

Extraction/inspection and texture codecs use the standard library. Model export/rendering also use installed NumPy 2.2.4; the preview uses Pillow 11.1.0. Node is used only for player-logic tests. Generated metadata, models, decoded textures, frames, GIFs, and player output remain under ignored `build/melee_anim`. Keep notes in these four documents, as requested. Original asset bytes must remain ignored.

## Design direction to preserve

- Python owns the CLI, catalog, jobs, costume batching, manifests, and FFmpeg export orchestration.
- The full-roster prototype uses NumPy poses, Windows offscreen memory-bitmap OpenGL rasterization (`native_raster.py`), and Pillow PNG/GIF encoding. No window, desktop capture, dependency installation, or Blender is required. The slower Python rasterizer remains available. Blender is an optional planned production backend; setup is in `TODO.md`.
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

## Current handoff after full-roster rendering

Newest feature: **Minimum cycle** is an opt-in checkbox for repeat/seam-checked clapping intervals, with full authored loops default. Across every actual costume, approved intervals are Luigi 100→20 frames / 0.40s / original PNGs `[61,81)`, Kirby 134→34 / 0.68s / `[17,51)`, and Link 50→12 / 0.24s / `[26,38)`, all zero-based at 50fps. These are edited repeats; subtle finger/body motion may differ. The other 23 families retain full loops under conservative checks; this does not prove no other manual edit is possible.

`cycles.py` scans every costume in all 26 clapping families, writes ignored `minimum-cycles.json`, and selects the smallest qualifying rendered-image recurrence lag with a common best seam phase. It checks the real unwrapped next image, closing step, and velocity rather than a wrapped endpoint. Constant/slow/one-shot or incompatible-costume samples are rejected. Manifest/PNG size+mtime fingerprints disable stale approvals after regeneration. Run `cycles` after changing masters, regenerate the gallery, and restart the service.

Playback, every GIF size/color bundle, and mapped paused PNGs share that interval. GIF names include `minimum-cycle`; aggregate GIF exports shorten only approved claps. Ticks stay 20ms; no endpoint duplicate, retiming, or blended frame is introduced. The UI shows count/FPS/duration for computing common repeat lengths. GIF compression can merge identical images into holds; use displayed uniform timeline counts for combining loops. 72 Python tests and Node tests pass. All 15 approved costumes were decoded at all four sizes with exact 400/680/240ms looping duration, and first-frame all-color PNG bytes matched the original masters. Default-costume closing seams were visually inspected, without game-reference or perfect-seam claims.

Latest addition: the player has Download size options **Extra small 128, Small 256 (default), Medium 512, Large 1024**, applying to GIFs, paused PNGs, all-costume bundles, and the full GIF collection. Larger sizes resample the existing 256px exports with Lanczos; they are not new higher-detail renders. Size changes preserve playback/pause state, output frame index, action, and costume. Saved filenames include `-128px` / `-256px` / `-512px` / `-1024px`.

Run `python -m tools.melee_anim.player_server`, then open `http://127.0.0.1:8765/player.html`. The local service is running in the current session. It binds only to 127.0.0.1, serves the preview directory, and uses the already installed Pillow. Direct `player.html` file use still supports the original 256px downloads; other sizes use that local service. Restart the service after regenerating/changing the clip catalog. No new dependency was installed.

`downloads.py` resizes an existing GIF while preserving decoded frame delays and loop metadata, and resizes the exact selected PNG master. Cache keys include source bytes, size, format, and a resizer version; cache/bundle writes are atomic under ignored `build/melee_anim/preview/downloads/resized`. All-color PNG bundles use the same zero-based frame index for every actual costume. The HTTP service validates fixed catalog identities/options and serializes exports to bound 1024px GIF memory. It generates/caches files on demand; do not eagerly generate four complete PNG datasets. 68 Python tests and Node player tests pass, plus real Mario victory-3 GIF/still/all-color downloads at all four sizes, Game & Watch's four 128px looping GIFs, and paired Ice Climbers at 512px.

The latest requests are implemented: all 26 selectable character entries (Zelda/Sheik separate), every one of their 123 actual costumes, and eight preview choices per costume. These are clap, standard right-facing taunt, victory entrances 1/2/3, and their three primary authored waits. There are 984 GIF jobs / 81,369 PNG masters. Left-facing and Fox/Falco stage taunts, plus Fox's extra wait slot 4, remain cataloged extensions.

Open `build/melee_anim/preview/player.html` in a normal browser. Character, Animation, and Costume are independent selectors. Each animation has selected-GIF and all-costume GIF downloads; `downloads/melee-all-characters-all-animations.zip` contains the full collection. Pausing or scrubbing reveals a selected-frame PNG link and the same-frame all-costume ZIP. The display uses one-based output frame numbers: 68/101 selects physical `frame_0067.png`, not source tick 68. Precomputed still ZIPs make this work with `file://` and no browser ZIP library/server. Regenerating the gallery reuses only byte-matching complete still ZIPs; writes use a temporary file and atomic replacement, with bounded parallel packaging.

`export_fighter` / `roster_batch` generalize the former Mario pilot. Skeleton defaults are per costume; rigid/shared meshes, missing normals, NBT attributes, and initial eye palette selection are supported. Source OnDeath defaults plus the initial motion visibility prefix choose normal parts. Game & Watch preserves four actual runtime colors, source Z width, an approximate outline, and hides the class-4 item list installed by `ftGw_Init_OnLoad`. Visibility class 2 addresses **a separate `fp->x203C` drawable list**; never apply its indices to the primary model. Classes 0/1/3/4 use the primary list. This distinction and the class-4 table prevented overlapping silhouettes.

`preview.load_clip` now bounds results containers by `Archive.public_extent` before slicing packed motions; Popo/Nana share a results archive. Ice Climbers render both actual costume-mapped models, using approximate fixed X offsets -2.8/+2.8; original relative scene placement/callback behavior is not proven. `pose_matrices` clamps animated scales with abs(value)<0.001 to +0.001 as `JObjUpdateFunc` does. Channels 11/12 affect node/branch visibility; a hidden node alone does not hide its descendants. Fox's taunt exercises channel 11. Both raster backends honor GX front/back culling. Windows native rasterization uses only a memory DC/DIB and system DLLs; no visible window or native compiler.

Current verification commands are in the block above. `verify_previews.py` checks the actual expected matrix, every GIF duration/loop flag, distinct costume GIF hashes, all GIF ZIP inventories/hashes, all still ZIP frame filenames, and exact first/frame-68/final all-costume PNG bytes per action. It writes ignored `coverage.json`. The synthetic Python suite has 65 passing tests. Node tests exercise controls, every character/action/costume download, paused/resumed link visibility, and Mario victory 3 frame 68/101. Browser inventory is unavailable, so do not claim a live browser click test. All original/generated assets remain ignored.

Latest completion verification passed: 984/984 expected jobs, zero missing, 209 GIF bundles, and 17,348 still-frame bundles. The Node tests passed, including every character/action/costume and the 68/101 example. Git ignore checks covered all 110,447 game-input/generated/bytecode files; only intentionally tracked `.gitkeep` placeholders were excluded from that check.

Resume without re-extracting or restarting the investigation:

1. Review prototype poses and repeated loops against an isolated Slippi/Dolphin reference. Installed executables exist under `%APPDATA%\Slippi Launcher\netplay` and `playback`; no emulator was launched or user configuration modified. Use a separate task-owned user directory for reference capture.
2. Add required timed part/material scripts, eye/face updates, props, effects, procedural systems, and exact paired placement. Current initial-prefix visibility is not full script execution. Preserve the native seams; do not promise perfect loops from authored loop flags alone.
3. Resolve production timing policy: explicit nominal 60 source ticks/s and 50 fps are still presets; GIF rounding and one extra terminal one-shot sample are disclosed in manifests. MP4 must use exact manifest counts and an explicit background.
4. Add manifest-driven FFmpeg MP4 output and ffprobe verification when the user has FFmpeg available. Optional installation instructions remain in `TODO.md`; no installation was performed.
5. Extend resume fingerprints to renderer/evaluator/script versions and companion model hashes. Current cache verifies primary model hash, settings, completeness, and exact frame files; force a re-render after relevant code changes. `roster_batch --character <slug>` limits scope. Do not reintroduce the earlier unchecked Mario cache exception.
6. Add optional Blender rendering using the existing neutral models/poses when justified; no Blender importer exists. Camera rotation, transparency/background settings, attacks/damage actions, and full results-screen composition remain later work.

The current prototype is useful animation/costume coverage, with approximate materials/lighting/reflection and no complete timed scripts, props, effects, dynamics, or audio. All source game/decomp code remains unchanged. Keep these limitations visible while improving fidelity.
