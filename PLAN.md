# Implementation plan

The requested fixed synchronization preset is now implemented: **Clapping-sync alteration**, 42 frames / 0.84s at 50fps, across all 123 costumes. Clapping options are mutually exclusive radio buttons, with Full animation default and the group hidden for other actions. The prior feasibility proposals below are retained as history; no general duration or FPS selector was added.

Current status, 2026-10-10: all 26 selectable character entries, including separate Zelda and Sheik, have eight animation choices in every actual costume: **984 GIF jobs across 123 costumes, with 81,369 PNG masters**. The offline player supports character/animation/costume selection, GIF downloads, and exact paused-frame PNG downloads for one costume or all costumes. Rendering fidelity, Blender integration, and MP4 remain open. Read `AGENTS.md`'s updated handoff before continuing.

Download sizes are implemented as 128/256/512/1024px presets for GIFs, exact paused PNGs, and bundles. Use the local Python player service for resized downloads; original 256px files still work offline. Sizes use Lanczos resampling of existing masters, preserving pose/timing/color identity; Medium/Large add dimensions rather than new detail. On-demand caching avoids multiplying all 81,369 frames into four datasets. A later high-resolution renderer should be a separate explicit quality option, using the same size presets and frame/timing contract.

## Recommendation

Camera rotation is implemented through the existing pose/mesh pipeline: X tilt, Y turn, Z roll sliders, Apply and Reset. Use `Ry(yaw) @ Rx(pitch) @ Rz(roll)` for the camera-to-world basis. Preserve world lighting and source skeleton transforms. A camera-independent world bounds center and symmetric projected fit prevent frame-to-frame crop movement; each costume fits its own entire original animation (plus sync samples when applicable). The local service renders 256px angle masters on demand; preview, selected/all-costume GIF/PNG exports, all-GIF bundles, and the four size presets share that camera. Larger downloads still resample 256px masters. Apply retains a paused frame; new character/costume/mode selections retain the angles, and stale async responses cannot overwrite the selection or Reset. Hide downloads until that preview succeeds. New-angle all-color/all-GIF exports may take longer because their remaining costumes render serially.

`rotations.py` stores outputs under ignored `preview/rotations/<hash>` and fingerprints camera/timeline/framing settings, model and companion data/textures, source manifests, motion report/archives, and Python renderer/evaluator modules. Verify completion through exact output inventories and hashes; a damaged output rerenders. Minimum and dirty intervals select the same rotated full-clip masters; sync uses its separate exact 42-sample plan and explicit GIF frame writer. Serialize render/export work and bound active/waiting requests to four, with a 600s subprocess timeout. No new dependency or Blender is needed. Continuous mouse-drag 3D playback remains a separate larger milestone; the browser still displays saved images. Refresh gallery controls with `preview_gallery --require-all --player-only` when bundles already exist, and restart the service for server changes.

Rotation validation passed 87 Python tests, Node async/control tests, live sync rendering for all 26 default characters, all eight Mario action timelines, exact frame-68 downloads in all five Mario costumes, and four-size sync GIF tick checks. Side/back/top/underside/roll poses and paired/flat special cases were visually reviewed. Every angle/costume combination is generated lazily rather than pre-rendering the unbounded angle space. Native materials/lighting remain approximate and a live browser click test was unavailable; see investigation section 23 for the actual evidence.

The sync backend evaluates original FigaTree curves at scheduled fractional source times, retaining per-costume binds/materials and the paired Ice Climbers. Use dirty/approved/full source intervals plus the three discussed extra cuts, wrist-gap contact/open-pose proxies, integer repetitions, and 0–3 held output ticks. Keep full/minimum/dirty exports unchanged. Whole-original-clip framing prevents per-frame crop changes. One character plan applies to every real costume, with model/companion hashes and source-master fingerprints for resume/attachment. Render outputs are separate under ignored `clapping-sync`, and manifests record cuts, rates, holds, markers, source times, and limitations.

Sync GIFs deliberately preserve all 42 encoded image frames (20ms each), including held duplicates, for frame-by-frame composition. Use the tested Pillow GIF block writer for native-size and resized sync exports; ordinary encoding may retain its existing merge behavior. PNG stills come from the exact selected sync sample. The sync aggregate ZIP contains all 123 claps, while other modes keep their existing download scope. Shared loop boundaries and proxy first-contact phase do not certify identical clap frequencies, exact fingertip collision, or repaired dirty seams.

Latest compact-timeline tradeoff: 1.4s was a conservative constraint fit, not an absolute minimum. On the same provisional cuts, 0–3 held output ticks and rate limits ±15/20/25% admit 60/42/28 frames (1.20/0.84/0.56s) respectively. Keeping ±10% but permitting four hold ticks admits 62 frames / 1.24s. The 34-frame group is Bowser/Kirby/Yoshi; Jigglypuff is 33. Their timing conflicts with the 25-frame group (Donkey Kong/Fox/Game & Watch/Ice Climbers/provisional Mewtwo), which is the strongest combinatorial constraint. Do not call those calculations visual approval. A proposed 25fps export would halve data-frame counts for these even-duration fits while preserving playback duration, trading temporal smoothness for size; no FPS selector or synchronized output is implemented yet.

Least-change compact synchronization estimate: aim for approximately 1.4s after manual one-clap cuts for Pikachu/Pichu and a short idle cut for folded-arm Mewtwo. An illustrative 69-frame / 1.38s schedule exists with moving rates within ±10% and 0–3 held output frames per cycle, assuming lengths 15/15/25 respectively and all other current dirty/approved/full choices retained. Holds are fixed output ticks: rate is `repeats * moving_segment_frames / (master_frames - repeats * hold_frames)`. Prefer this explicit constrained schedule to an arbitrary universal clap speed; retain exact hand-contact alignment as a separate phase/beat constraint. Treat 69 frames as a conditional arithmetic result pending visual approval of the new cuts, not a promise. Bowser/Kirby's 34-frame motions limit more aggressive shortening under these rate bounds.

Next proposed feature, requested as advice rather than an implemented control: a shared-timeline synchronization exporter. Choose a master duration on the 50fps/20ms grid, an allowed speed adjustment, selected full/approved/dirty segments, and integer repeat counts. Search the smallest master frame count whose per-clip rate `segment_frames * repeats / master_frames` lies within the tolerance. Evaluate original pose curves at the resulting source phases rather than relying on GIF compression frame counts or large frame holds. Samples cover `[0, master_duration)` without a duplicate endpoint. Keep this explicitly edited timing separate from source/full/minimum/dirty exports.

Current all-26 feasibility: with approved-or-full choices and ±10% rate change, the first matching period is 496 frames / 9.92s; with dirty candidates preferred, then approved, then full, it is 110 frames / 2.20s (rates 0.90–1.0909). ±15% reduces the latter to 105 frames / 2.10s. These calculations synchronize the overall wrap; they do not make every hand contact simultaneous or repair dirty seams. True shared beats need one-clap segmentation and per-character contact markers/phase offsets. Optional 1–3-frame holds at a relaxed/open-hand pose can bridge small timing gaps; larger holds freeze the motion. Manual segment Start/End, repeated seam preview, and optional source-pose seam blending are proposals for Mewtwo and other long secondary-motion clips. Avoid default image crossfades that ghost the character.

The user's requested dirty-loop review is implemented as an independent opt-in mode, never as relaxed approval. Preserve all strict minimum results. Expose the shortest plausible rejected recurrence and least-disruptive phase, show its failed checks, and allow preview/download for all costume variants and sizes. A clickable candidate list makes the 11 review families discoverable. Label files `dirty-loop` and retain full/approved/dirty mode identity through scrubbing, exact PNG mapping, GIF timing, and bundles. Dirty aggregate exports use experimental intervals where present, approved minimums otherwise, and full clips for the remainder.

The opt-in Minimum cycle mode now shortens checked clapping repeats: Luigi 20 frames, Kirby 34, Link 12 at 50fps. Full loops remain default. Use one original PNG interval across all actual costumes, with rendered recurrence and unwrapped seam checks, preserving 20ms ticks and labeling these as edited repeats. Other clips keep full intervals until a shorter candidate passes. Playback, sized GIF/bundle exports, and mapped paused PNGs share interval metadata. Show timeline count/FPS/duration for combining loops; do not base common lengths on GIF compression's merged-image count. Regenerate analysis after master changes and invalidate stale cuts through source fingerprints.

The full-roster preview milestone uses [roster_batch.py](tools/melee_anim/roster_batch.py), followed by the offline gallery and [verify_previews.py](tools/melee_anim/verify_previews.py). Its saved PNGs are the still-image source; the gallery packages the same frame across actual costume IDs rather than rerendering a different pose. Precomputed ZIPs support direct local-file use. A temporary-file replacement and byte-checked reuse make still packaging resumable, with eight bounded worker threads.

The Windows memory-bitmap backend is a speed improvement for the prototype, not a new requirement to port the game engine. Preserve the neutral model/pose interface for a later Blender renderer. Initial visibility defaults, source near-zero scale handling, node/branch visibility, and owning packed-container bounds are implemented. Native material/lighting fidelity, timed appearance/props, exact Ice Climbers placement, and game-reference validation remain separate milestones.

The current full-roster verification passed: 984/984 expected jobs, 209 GIF bundles, and 17,348 paused-frame bundles; 65 Python tests and Node player tests pass. Generated `coverage.json` records the precise checks and remaining limits. The same exported PNG bytes are used by the player and still downloads; source ticks and displayed output-frame numbers stay distinct.

Build a **Python application that imports Melee assets, plays selected animations in Blender, renders image sequences, and calls FFmpeg to produce MP4 and GIF files**. Use the decompilation as the specification for asset selection, animation evaluation, costumes, and results-screen behavior. Reuse the existing DAT tooling where it saves work.

Blender is a planned production backend, not a requirement for the current prototype. The full roster uses Python/NumPy pose evaluation and the Windows system OpenGL rasterizer in a memory bitmap, with Pillow for PNG/GIF output. It opens no window and needs no additional graphics package. The slower NumPy/Pillow triangle renderer remains available for diagnostics. `TODO.md` contains optional Blender setup and FFmpeg installation/verification steps for later.

Python is the easiest language for the user to maintain and is well suited to catalogs, batch jobs, animation sampling, and export settings. Blender supplies meshes, cameras, skinning, materials, a viewport, and scripted rendering. Its command line supports background execution and Python scripts. We still need to build the Melee importer; Blender does not automatically understand these DAT files. See the [Blender command-line documentation](https://docs.blender.org/manual/en/3.6/advanced/command_line/arguments.html).

The largest remaining engineering task is faithfully combining the now-readable skeleton, mesh, curves, textures, and costume behavior into a render. Video encoding is a much smaller part. Mario's actual `Lose` is an 18-source-frame loop and all five costumes have matching bind topology, making it the first rendering target; preliminary finger-channel discontinuities mean smoothness still needs explicit verification.

## Scope and priorities

1. Isolated clapping animation for each roster character, in every costume variant actually available to that character.
2. Each of the three victory animations; identify any entrance and cyclic subsection and expose verified sections separately. Support every costume for these too.
3. Taunts and selected attacks, starting with forward smash, across all costumes.
4. Hit reactions, tumble, knockdown, downed loops, recovery, and other gameplay motions.
5. Results-screen composition: winner(s), camera behavior, animated loser squares, and results presentation.

The initial exporter should produce useful character assets before the complete results interface is reconstructed. Keep a separate results-scene mode so we can reproduce the original composition later.

"All costumes" means enumerate the character's supported costume IDs and record the requested action once for each. It does not mean a fixed color count, an arbitrary tint, or a requirement for a distinct DAT filename for every costume. This checkout describes 4, 5, or 6 selectable costumes per roster entry. Costume-specific geometry, accessories, visibility, and runtime material colors matter.

## Language and library choices

| Component | Choice | Reason and boundary |
| --- | --- | --- |
| User-facing tool | Python; start with `argparse`, `pathlib`, `json`, `subprocess`, and `dataclasses` | A small readable CLI with minimal dependencies. A GUI can follow once export works. |
| Matrix/pose work | NumPy, when array operations are needed | Joint transforms, sampled poses, skinning checks, and seam measurements. See [NumPy linear algebra](https://numpy.org/doc/stable/reference/routines.linalg.html). |
| Image inspection | Pillow | Contact sheets, alpha handling, bounds checks, and visual QA. See [Pillow image-format support](https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html). |
| Rendering and preview | Blender Python API (`bpy`) inside a pinned Blender release | Scripted scene creation and offscreen PNG rendering; avoids writing an entire graphics engine. Launch Blender as a subprocess for the first version. |
| MP4/GIF encoding | FFmpeg executable, invoked with an argument list | Explicit frame timing and encoding settings. Use `ffprobe` for output verification. See [FFmpeg CLI](https://ffmpeg.org/ffmpeg.html) and [palette filters](https://ffmpeg.org/ffmpeg-filters.html#palettegen). |
| Extraction/initial inspection | Implemented stdlib tools in `tools/melee_anim` | Portable ISO extraction, focused DAT/DOL reads, nested motion/costume/model catalogs, and preliminary scalar evaluation. These are already working on the supplied files. |
| General archive typing | Existing Rust `melee-dat` tool | Source-derived types, type walks, samples, and native schemas remain useful as needed. Its Rust commands were not run in this task. |
| Optional native adapter | Existing `tools/dat-cli/native` C library behind a small exporter process | Converts archive descriptors into the decomp's host-native types. It does not decode keyframes, textures, or GX meshes, and requires schema/toolchain setup. |
| Focused verification | Python `unittest`, already used | Synthetic extraction/format/curve/model checks run without original asset fixtures. Extend for matrix, skinning, and output validation as those features are built. |

Do not require the user to learn Rust or C for ordinary exports. Keep any native helper behind a process interface producing versioned metadata and arrays. This also avoids binding the first Python app directly to the game's 32-bit runtime layouts.

The current extraction/inspection path works with Python 3.13 and requires no third-party packages, .NET, native compiler, Cargo, or WSL. Choose and pin Blender/FFmpeg versions after testing the first render. The repository's optional Nix/schema environments target Linux, so WSL2 remains an option for those builds, not a prerequisite for the current tools.

## Compare the implementation routes

| Route | Strength | Main cost | Decision |
| --- | --- | --- | --- |
| Python + focused DAT adapter + Blender | Understandable automation; arbitrary cameras/backgrounds; alpha-capable source frames; batch exports | Custom mesh/curve/material importer; Blender materials will initially approximate GameCube rendering | Recommended first standalone program. |
| Python + a small C adapter using decomp routines | Can reuse original interpolation and descriptor logic | Isolate runtime dependencies, create schema, resolve externs, bridge raw formats and pointer assumptions | Use selectively if it reduces importer risk. |
| C#/HSDRaw adapter + Python + Blender | Existing HSD parsing, keyframe, vertex, and texture utilities | Additional runtime and integration; nested results clips and full character behavior still need proof | Evaluate as an alternative during the importer spike, not a mandatory dependency yet. |
| Dolphin + capture harness + Python/FFmpeg | Original game rendering, physics, effects, and full results UI | Deterministic scene/state setup, chosen variant/costume, framing, automation, and transparent isolation | Reference renderer and practical fallback for full-fidelity gameplay capture. |
| Port the complete game/GX engine or write a new renderer | Maximum runtime control and possible original rendering fidelity | Much larger project; existing host library is incomplete as a renderer | Defer until a concrete fidelity requirement justifies it. |

[HSDLib/HSDRaw](https://github.com/Ploaj/HSDLib) provides a .NET DAT library and a viewer whose authors describe it as a work in progress. Its source includes [FOBJ decoding](https://github.com/Ploaj/HSDLib/blob/master/HSDRaw/Tools/FOBJ_Decoder.cs), [curve playback](https://github.com/Ploaj/HSDLib/blob/master/HSDRaw/Tools/FOBJ_Player.cs), [GX vertex access](https://github.com/Ploaj/HSDLib/blob/master/HSDRaw/Tools/GX_VertexAccessor.cs), and [texture utilities](https://github.com/Ploaj/HSDLib/tree/master/HSDRaw/Tools/Textures). These are candidates for reuse or cross-checking, not evidence that the requested export workflow already exists.

Dolphin's own [frame dumper source](https://github.com/dolphin-emu/dolphin/blob/master/Source/Core/VideoCommon/FrameDumper.cpp) and [FFmpeg dump backend](https://github.com/dolphin-emu/dolphin/blob/master/Source/Core/VideoCommon/FrameDumpFFMpeg.cpp) support the capture route. Its automation interface must be verified for the selected build; do not assume stock Dolphin exposes a Python API. Cropping a loser square is useful as reference footage but does not provide a reusable character model or clean alpha.

## Data and playback architecture

```text
Local GALE01 files + original main.dol + decomp source tables
                         |
          asset inspection and catalog generation
                         |
    versioned model / costume / motion intermediate data
                         |
        source-compatible pose and appearance sampling
                         |
     Blender character scene or results-scene composition
                         |
            numbered PNG frames + job manifest
                         |
                FFmpeg -> MP4 and/or GIF
```

### 1. Input and catalog

The supplied ISO was extracted to `orig/GALE01/files` and `orig/GALE01/sys/main.dol`; defaults and overrides are implemented in the inspection tools. `extract_iso.py` verifies revision compatibility, writes a hash manifest, and supports verified reruns. Inspectors that use DOL addresses require the matching executable. Preserve this validation boundary when adding rendering.

Generate a catalog linking:

- User-visible character name, external `CharacterKind`, internal `FighterKind`, and compound-character members.
- Costume ID, actual source file/public joint, material animation, visibility data, runtime color overrides, and a friendly label when known.
- Results archive, nested demo motion-file symbol, demo variant, motion-state ID, animation ID, and any observed entrance/loop sections or transitions; record their absence explicitly.
- Gameplay action state, animation/submotion ID, packed archive offset and size, public `FigaTree` name, script, and playback flags.
- Frame count, joint/track mapping, evaluator version, source hashes, and supported/unsupported features.

Retain distinct costume IDs even when they share an archive. The implemented model catalog checks the actual DOL mappings for all 123 selectable jobs plus four Nana member records. It resolves language-specific filenames such as `PlCaRe.` before opening and preserves per-costume bind defaults. Add action/render support states to this catalog rather than silently substituting costume 0.

### 2. Import and evaluate

**Decision after the asset inspection:** use the working focused Python DAT reader and scalar evaluator as the first importer foundation. They expose Mario's skeleton, all meshes/weights, texture formats, and selected results clip with no native toolchain setup. This selects the initial inspection/import path; complete HSD matrix/evaluator fidelity and Blender rendering remain to be proven. Use native/HSDRaw code as a reference or targeted replacement if measured discrepancies justify it, rather than requiring another runtime upfront.

Preserve joint traversal order, parent relationships, per-costume bind transforms, weighted and rigid attachments, scale compensation, channel defaults, frame timing, and original interpolation. The inspected 27 fighter families have matching hierarchy across costumes, but 20 have differing local bind SRT; topology alone is not permission to reuse defaults. DAT descriptors are big-endian, while FObj numeric streams use little-endian formats. Include material/visibility animation and costume setup where required.

Mesh conversion needs a specific HSD skinning boundary: palette entries with a single unit-weight joint can use that joint's global matrix directly, while mixed envelopes combine joint-global times stored envelope matrices. Raw positions can therefore use different coordinate spaces within an envelope mesh. Convert per-corner palette references into a consistent bind-space mesh before assigning conventional Blender weights. Add reference-matrix/vertex checks rather than assuming every raw position is already in a common bind space.

Sample the source evaluator at each output time and bake the resulting transforms for Blender initially. This avoids approximating HSD curves with Blender's default interpolation. If pose hierarchy flags cannot be expressed faithfully as ordinary Blender bones, evaluate global matrices or deform the vertices directly for the proof of concept. Validate normals and skinning too.

Use a fixed game-tick timeline; keep source ticks and output frames distinct. Establish the exact tick-to-time conversion from reference capture. A 60 fps export preset is a sensible convenience, but it must not overwrite measured source timing.

### 3. Scene and appearance

Start with one fixed camera, simple lighting, and a solid or transparent background. Fit the camera to the bounds of the entire selected interval so limbs do not leave the frame and the crop does not wobble. Preserve the same framing across costumes for a given action.

Convert Mario's CMPR and C8/RGB565-palette textures and basic materials first. His model includes alternate drawables, reflection texture coordinates, and some second-UV meshes, so loading every drawable and treating every texture as a single base-color image will be wrong. Preserve visibility choices and document remaining TEV, outline, blend, shadow, and particle differences. Compare reference poses separately for motion, skinning, and shading. Later extend decoding to the additional C4, I4, I8, and RGB5A3 formats found elsewhere in the roster.

Later add results camera/light data, per-character scales, Ice Climbers pairing, team winner layout, loser render targets, and interface animations. The source results screen renders characters into image buffers for the little squares; a standalone high-resolution character export can bypass those low-resolution buffers.

### 4. Export jobs

Each job selects character, action/variant, costume or `all`, source interval, intro inclusion, output dimensions, frame rate, camera preset, background, and formats. Store a manifest beside the frames with exact inputs and settings. Cache by source hashes plus importer/render settings, and resume completed work safely.

Batch generation should expand the actual supported costume list first, then action variants. Use stable names such as `mario/costume-00/results-clap/` and `mario/costume-00/victory-01/`. Keep user-facing victory numbering 1-3 and the game's variant numbering 0-2 explicitly mapped.

The following is a **proposed interface**, not a command available today:

```text
python -m melee_anim catalog --files orig/GALE01/files
python -m melee_anim export --character mario --action results-clap --costume all --format mp4 gif
python -m melee_anim export --character mario --action victory --variant 1 --costume all --section loop
python -m melee_anim export --character fox --action taunt --costume all --loop-mode source
```

## Looping policy

A repeating video is not automatically seamless. Actual assets confirm separate nonlooping victory clips and `Win*Wait` candidates, but automatic original-scene transitions into those waits are unverified. Most waits are loop-marked; Falco's `Win3Wait` is an exception, and Fox has an extra `Win2Wait2`. Keep clip selection and transition policy data-driven. All 27 internal `Lose` clips are loop-marked and their periods are now known.

Offer these explicit policies:

| Policy | Meaning |
| --- | --- |
| `source` | Preserve the game-authored loop and transition rules. Report whether seam validation passes. |
| `segment` | Export a chosen naturally repeating subsection. Save the exact source interval. |
| `once` | Export the original action once; appropriate for attacks, hit reactions, and noncyclic poses. |
| `blend` | Apply an explicitly requested pose/appearance transition at the seam. Record that the motion was edited. |
| `pingpong` | Play forward then backward as an explicit creative effect; this changes the original motion. |

Compare **both** the unwrapped exact terminal pose and the limit approaching the end with the start, including root transform, derivatives, materials, accessories, and particles. Sampling `end` through a looping evaluator wraps immediately; even an unwrapped terminal key can restore a start value that differs from the preceding limit. Mario's clapping tracks show this in four finger rotations. The current Python report includes these preliminary channel/finite-slope checks; full matrix and rendered checks remain required. Inspect several actual repeats and store samples over `[start, end)` without appending a duplicate endpoint.

Physics-driven bones or particles may need deterministic initialization and several warm-up cycles before a stable loop is captured. A moving root requires an explicit world-space or in-place policy. Do not silently reverse, reset, or crossfade every victory animation to claim perfect looping.

## Output behavior

Keep PNG sequences as the lossless master, including alpha when requested. From the same samples, generate:

- **MP4:** H.264 with a broadly compatible pixel format, even dimensions, explicit timing, and a chosen background. The normal H.264 MP4 preset does not preserve alpha. Seamless content repeats when the player loops it; MP4 does not guarantee automatic replay in every player.
- **GIF:** a shared generated palette, selected dithering, deliberate frame delays, and infinite loop metadata. GIF has limited colors, binary transparency, and centisecond timing, so its timing and appearance cannot exactly match an arbitrary 60 fps RGBA sequence. Offer a GIF-friendly rate such as 25 or 50 fps and validate actual duration. See [FFmpeg GIF timing and looping](https://ffmpeg.org/ffmpeg-formats.html#gif-2).

Allow both formats in a single job. Inspect decoded output for frame count, duration, dimensions, crop, seam behavior, and transparency/background. Silent output is sufficient for the first milestone; announcer voices, music, and synchronized sound are separate additions.

## Milestones and decision gates

| Milestone | Reviewable result | Gate |
| --- | --- | --- |
| A: asset readiness — complete | Verified extraction/hash manifest, results/ordinary motion metadata, and all selectable costume references | Original DOL matches; actual packed boundaries/publics and model roots checked. |
| B: motion/assembly proof — prototype complete | Mario meshes, decoded textures, source poses, and 12 rendered PNG/GIF clips | Synthetic/reference-math checks and visual contact sheets pass; original-game reference/fidelity comparison remains open. |
| C: first working exporter | Default Mario clapping PNG sequence, MP4, and GIF with seam report | Repeatable export and acceptable animation/render fidelity. |
| D: costume batch | Same action exported for all five Mario costumes | Correct costume ID and appearance in each artifact; shared framing. |
| E: results coverage | Clapping + all three victory variants for every roster costume | Coverage matrix includes exceptions; intros/loops distinguished. |
| F: action coverage | Taunt and forward smash, then damage/ground states | State-to-motion mapping and runtime-dependent features handled explicitly. |
| G: results scene | Composed winner(s), loser squares, and results presentation | Scene timing/cameras/compositing match reference sufficiently. |

If the first Blender import cannot achieve acceptable motion or appearance without excessive custom rendering, keep the Python catalog/batch/export design and switch that renderer to a focused native player or Dolphin harness. Document the evidence before changing the backend. Do not make a full native game port a prerequisite for the first working asset export.

The runnable commands at the current stage are `extract_iso.py`, `inspect_motions`, `inspect_models --catalog` / `--all-models`, and `inspect_results_scene` as documented in `INVESTIGATION.md`. The proposed `melee_anim export` interface above is still future work.

Additional implemented commands are `catalog`, `export_model`, `preview`, `preview_batch`, and `preview_gallery`. The current job inventory includes all 26 forms/123 costumes with primary victory waits and both taunt facings (1,123 jobs including stage sequences). Rendering is presently Mario-only; Fox's extra `Win2Wait2` exists in the motion report but is not a job in that inventory yet.

Resume priorities are bounded prototype fixes, manifest-driven FFmpeg encoding, game-reference comparison, and one-family-at-a-time renderer expansion. Honor source culling, report timing-grid/terminal hold behavior, and avoid stale PNG sequence files before calling the pilot a production exporter. Keep native and explicitly edited loops separate.

Mario color coverage/download update (2026-10-10): the batch can now generate all eight available animation/section choices in all five costumes, with resume and concurrent workers. The viewer separates animation and color selection, keeps the selected color when changing animation, and exposes individual GIF saving plus per-animation and full-collection ZIPs. `preview_gallery --require-all` verifies the 40-pair matrix before finalizing it. Each ZIP uses stable unique filenames and a SHA-256 inventory. All generated data remains ignored; no Blender/FFmpeg install is needed for these GIF downloads.
