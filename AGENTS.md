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

Initial investigation: 2026-10-10, source commit `79b13a32467f7c4f91d6f831f0b9f891b7fb1146`. Only documentation was added in the initial task. No player, importer, renderer, capture harness, or video export was implemented or tested.

At investigation time, `orig/GALE01/files` and `orig/GALE01/sys` contained only `.gitkeep`; no DAT archives, disc image, or executable were found in the checkout. Recheck this inventory before claiming anything is playable. The expected original DOL hash is in `config/GALE01/config.yml`; the version currently configured is GALE01. Do not mix revision-specific tables/offsets with an unverified game dump.

## Design direction to preserve

- Python owns the CLI, catalog, jobs, costume batching, manifests, and FFmpeg export orchestration.
- Blender is the recommended initial preview/render backend. Its Melee importer is future work; no working Blender DAT import has been established here.
- Reuse the decomp's tables and HSD animation semantics. Reuse or extend `tools/dat-cli` for archive inspection and validation before building another general type system.
- Keep the importer/evaluator behind a clear interface. A focused Python reader, existing native DAT helper, or small HSDRaw adapter remains a feasibility choice until one real asset is proven. Record the evidence when selecting it.
- Keep native helpers as small subprocess adapters initially. Do not require a complete host game port or Python access to raw game-runtime pointers.
- Use Dolphin as a reference and possible capture backend for runtime-dependent/full-scene fidelity. Do not assume stock Dolphin has a Python scripting API.
- Prioritize default Mario clapping -> PNG sequence -> verified MP4/GIF -> every Mario costume -> wider results coverage.
- Preserve the original decomp source and build purpose. Place new product code in a separate tool/package; make source/type improvements only when required and justified.

These are documented implementation recommendations, not claims that the user selected a particular untested parser or approved a dependency installation. New evidence can change a backend choice; update the plan and rationale instead of silently changing direction.

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
11. Existing `symbols check-motions` validates ordinary motions using the original DOL and extracted files. Embedded demo motion-file archives / demo motion validation remain known gaps. A successful ordinary-motion check is not results-animation validation.
12. The root CMake native preset builds a 32-bit static library and excludes rendering-related files such as `pobj.c`. It is not a ready-made player. The DWARF ELF tolerates unresolved symbols and supplies type information, not runnable-game evidence.

## Animation and export rules

- Separate skeleton-clip playback from full gameplay behavior. Attacks and damage scenarios can depend on scripts, props/items, particles, root motion, hitlag, knockback, collision, procedural bones, and state transitions.
- Do not promise every victory/action is naturally seamless. Expose the authored loop, entrance, one-shot, and explicitly edited loop as distinct modes.
- For a source loop, store samples over `[start, end)`. Inspect the unwrapped terminal pose/limit before wrapping and compare it with `start`, then inspect actual repeats. Evaluating `end` with looping enabled returns the start automatically and can hide discontinuity. Do not add a duplicate endpoint pause.
- Check root movement, derivative continuity where meaningful, materials, visibility, accessories, and procedural state. Warm up dynamic systems when needed and use deterministic seeds/initial conditions.
- Keep source game ticks separate from output frame rate. Record exact timing and source intervals in manifests.
- Preserve PNG sequences as the lossless master; provide explicit background selection for the usual H.264 MP4 preset. GIF has palette, transparency, and timing limits. MP4 playback looping is controlled by the player.
- Batch by actual costume ID and action variant. Use consistent whole-animation framing, stable names, resumable jobs, and explicit unsupported/failure reports. Never silently substitute costume 0.

## Workflow and verification

Keep original game data local and out of Git. Existing `orig` ignores cover game inputs; add ignores for new caches/exports when implementation creates them. Do not download replacement game assets as part of routine implementation.

Update the investigation with concrete relative source links, symbol names, and evidence. Distinguish code-confirmed behavior, asset-confirmed facts, observed runtime behavior, and proposals. Actual clip names, lengths, full costume compatibility, and rendered fidelity cannot be certified from filenames alone.

Run focused checks appropriate to changed code. Useful checks include malformed/packed archive bounds, mixed endian keyframes, interpolation reference samples, skeleton/channel mapping, costume enumeration with shared files, loop timing, and decoded video duration/frame count. Use synthetic fixtures without embedding original assets in repository tests. Review rendered reference poses and repeated seams visually.

For native/type changes, use the repository's documented build/validation checks when the required tools and original files exist. Record which checks were actually run and what could not be run. Do not label a documentation review or type-only build as a successful animation render.

The initial Windows session's default MSYS Git failed to initialize its signal pipe; `C:\Program Files\Git\cmd\git.exe` worked. Use an available working Git executable if that issue recurs. Python and CMake were on PATH; other relevant tools were not detected on PATH, which does not establish that they are uninstalled.

Leave existing user changes intact, keep the checklist current, and describe backend decisions and remaining fidelity gaps in the plan so future work does not repeat this investigation.
