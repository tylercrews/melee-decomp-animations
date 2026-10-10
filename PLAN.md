# Implementation plan

Status: proposed architecture, based on the repository investigation on 2026-10-10. No animation player or exporter has been implemented yet. Read [INVESTIGATION.md](INVESTIGATION.md) for the source evidence and [TODO.md](TODO.md) for the execution sequence.

## Recommendation

Build a **Python application that imports Melee assets, plays selected animations in Blender, renders image sequences, and calls FFmpeg to produce MP4 and GIF files**. Use the decompilation as the specification for asset selection, animation evaluation, costumes, and results-screen behavior. Reuse the existing DAT tooling where it saves work.

Python is the easiest language for the user to maintain and is well suited to catalogs, batch jobs, animation sampling, and export settings. Blender supplies meshes, cameras, skinning, materials, a viewport, and scripted rendering. Its command line supports background execution and Python scripts. We still need to build the Melee importer; Blender does not automatically understand these DAT files. See the [Blender command-line documentation](https://docs.blender.org/manual/en/3.6/advanced/command_line/arguments.html).

The largest engineering task is faithfully importing the skeleton, mesh, curves, and costume behavior. Video encoding is a much smaller part of the project. Start by proving one character's clapping loop all the way through to an exported file.

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
| Archive inspection | Existing Rust `melee-dat` tool | Packed archive parsing, normal-motion validation, source-derived types, and evidence for the importer. Extend rather than duplicate useful existing functionality. |
| Optional native adapter | Existing `tools/dat-cli/native` C library behind a small exporter process | Converts archive descriptors into the decomp's host-native types. It does not decode keyframes, textures, or GX meshes, and requires schema/toolchain setup. |
| Focused verification | pytest when implementation begins | Meaningful format, curve, costume, timing, and encoding checks; no tests are needed for these planning documents. |

Do not require the user to learn Rust or C for ordinary exports. Keep any native helper behind a process interface producing versioned metadata and arrays. This also avoids binding the first Python app directly to the game's 32-bit runtime layouts.

Choose and pin actual tool versions after testing the first asset import. Do not assume an arbitrary latest Blender release is compatible with an untested importer. On this Windows machine, the repository's Nix development environments target Linux; WSL2 is a reasonable candidate for those build tools. Verify that setup before making it a requirement. Windows Python, Blender, and FFmpeg can remain the user-facing tools.

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

Accept an extracted files directory and executable path. The defaults should match `orig/GALE01/files` and `orig/GALE01/sys/main.dol`, with path overrides. Check the executable against the version configuration, hash source assets, and report missing files before rendering.

Generate a catalog linking:

- User-visible character name, external `CharacterKind`, internal `FighterKind`, and compound-character members.
- Costume ID, actual source file/public joint, material animation, visibility data, runtime color overrides, and a friendly label when known.
- Results archive, nested demo motion-file symbol, demo variant, motion-state ID, animation ID, and any observed entrance/loop sections or transitions; record their absence explicitly.
- Gameplay action state, animation/submotion ID, packed archive offset and size, public `FigaTree` name, script, and playback flags.
- Frame count, joint/track mapping, evaluator version, source hashes, and supported/unsupported features.

Retain distinct costume IDs even when they share an archive. Record explicit missing/unsupported variants rather than silently substituting the default costume. Generate costume counts from the source tables and check them against extracted assets.

### 2. Import and evaluate

Reuse the existing DAT parser/validator first. For the initial importer, implement only the descriptor and raw formats needed for Mario's default model and one results motion. Compare a focused Python decoder with a small native or HSDRaw adapter on that same input; select the smallest reliable implementation and record the decision.

Preserve joint traversal order, parent relationships, bind transforms, weighted and rigid attachments, scale compensation, channel defaults, frame timing, and original interpolation. DAT descriptors are big-endian, while packed FObj numeric streams use their own decoding rules. Include material/visibility animation and costume setup in the pose result where required.

Sample the source evaluator at each output time and bake the resulting transforms for Blender initially. This avoids approximating HSD curves with Blender's default interpolation. If pose hierarchy flags cannot be expressed faithfully as ordinary Blender bones, evaluate global matrices or deform the vertices directly for the proof of concept. Validate normals and skinning too.

Use a fixed game-tick timeline; keep source ticks and output frames distinct. Establish the exact tick-to-time conversion from reference capture. A 60 fps export preset is a sensible convenience, but it must not overwrite measured source timing.

### 3. Scene and appearance

Start with one fixed camera, simple lighting, and a solid or transparent background. Fit the camera to the bounds of the entire selected interval so limbs do not leave the frame and the crop does not wobble. Preserve the same framing across costumes for a given action.

Convert textures and basic materials first, with documented limitations for GameCube TEV behavior, outlines, blend modes, shadows, and particles. Compare frames against the game. Treat accurate animation motion and exact original shading as separate acceptance criteria.

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

A repeating video is not automatically a seamless animation. A victory may need a one-time introduction distinguished from any cyclic subsection, but this checkout's source does not establish such a transition for every victory. Clapping is the best first candidate because the results screen continuously renders it; its authored loop flags and period still require asset inspection.

Offer these explicit policies:

| Policy | Meaning |
| --- | --- |
| `source` | Preserve the game-authored loop and transition rules. Report whether seam validation passes. |
| `segment` | Export a chosen naturally repeating subsection. Save the exact source interval. |
| `once` | Export the original action once; appropriate for attacks, hit reactions, and noncyclic poses. |
| `blend` | Apply an explicitly requested pose/appearance transition at the seam. Record that the motion was edited. |
| `pingpong` | Play forward then backward as an explicit creative effect; this changes the original motion. |

Compare the unwrapped terminal pose or endpoint limit with the start, including root transform, derivatives where meaningful, material state, accessories, and particles. Inspect this boundary before loop wrapping: sampling `end` through the looping evaluator automatically returns the start and would hide a discontinuity. Also inspect several actual repeats visually. The last stored frame need not equal the first: store samples over `[start, end)` without appending an identical endpoint, which can introduce a pause.

Physics-driven bones or particles may need deterministic initialization and several warm-up cycles before a stable loop is captured. A moving root requires an explicit world-space or in-place policy. Do not silently reverse, reset, or crossfade every victory animation to claim perfect looping.

## Output behavior

Keep PNG sequences as the lossless master, including alpha when requested. From the same samples, generate:

- **MP4:** H.264 with a broadly compatible pixel format, even dimensions, explicit timing, and a chosen background. The normal H.264 MP4 preset does not preserve alpha. Seamless content repeats when the player loops it; MP4 does not guarantee automatic replay in every player.
- **GIF:** a shared generated palette, selected dithering, deliberate frame delays, and infinite loop metadata. GIF has limited colors, binary transparency, and centisecond timing, so its timing and appearance cannot exactly match an arbitrary 60 fps RGBA sequence. Offer a GIF-friendly rate such as 25 or 50 fps and validate actual duration. See [FFmpeg GIF timing and looping](https://ffmpeg.org/ffmpeg-formats.html#gif-2).

Allow both formats in a single job. Inspect decoded output for frame count, duration, dimensions, crop, seam behavior, and transparency/background. Silent output is sufficient for the first milestone; announcer voices, music, and synchronized sound are separate additions.

## Milestones and decision gates

| Milestone | Reviewable result | Gate |
| --- | --- | --- |
| A: asset readiness | Catalog for Mario: five costumes, results archive, nested motions, source provenance | Correct files/version present; no guessed clip locations. |
| B: motion proof | Mario clapping skeleton/poses and one rendered character frame | Curve semantics, skeleton mapping, and costume model match reference. |
| C: first working exporter | Default Mario clapping PNG sequence, MP4, and GIF with seam report | Repeatable export and acceptable animation/render fidelity. |
| D: costume batch | Same action exported for all five Mario costumes | Correct costume ID and appearance in each artifact; shared framing. |
| E: results coverage | Clapping + all three victory variants for every roster costume | Coverage matrix includes exceptions; intros/loops distinguished. |
| F: action coverage | Taunt and forward smash, then damage/ground states | State-to-motion mapping and runtime-dependent features handled explicitly. |
| G: results scene | Composed winner(s), loser squares, and results presentation | Scene timing/cameras/compositing match reference sufficiently. |

If the first Blender import cannot achieve acceptable motion or appearance without excessive custom rendering, keep the Python catalog/batch/export design and switch that renderer to a focused native player or Dolphin harness. Document the evidence before changing the backend. Do not make a full native game port a prerequisite for the first working asset export.
