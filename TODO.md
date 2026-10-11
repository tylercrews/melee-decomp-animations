# Ordered implementation checklist

Updated 2026-10-10 after full-roster rendering and paused-frame downloads. All 26 selectable character entries / 123 actual costumes have clapping, standard taunt, three victory entrances, and three primary wait clips: 984 GIFs and 81,369 PNG masters. Production fidelity and MP4 remain future work. See `AGENTS.md`'s current handoff for the resume order.

## Current workflow and remaining work

- [x] Preserve approved minimums while exposing rejected near-repeat candidates through a separate Minimum loop (dirty/jittery) toggle.
- [x] Add a clickable review list for all 11 experimental families / 54 actual costumes, with failed-check explanations.
- [x] Apply dirty intervals to GIF/PNG/color/aggregate exports and inline GIF viewing, keeping timing and source-frame mapping intact.
- [x] Verify all 54 dirty costume GIF durations/loops and exact all-color still bytes, plus sized inline previews; 75 Python tests and Node controls pass.
- [ ] Review the experimental loops with the user and record which dirty candidates they consider usable; do not promote them automatically.

- [x] Investigate repeated claps across all 26 character families and every actual costume.
- [x] Add opt-in Minimum cycle playback/download mode, keeping authored loops default.
- [x] Approve shared edited intervals: Luigi 20 frames / 0.40s, Kirby 34 / 0.68s, Link 12 / 0.24s, at 50fps.
- [x] Apply shortened intervals to all GIF sizes/bundles and map paused PNGs to exact original masters.
- [x] Show count/FPS/duration, preserve tick spacing, and omit a duplicate endpoint.
- [x] Invalidate stale analysis after master/manifest changes and record outcomes in ignored `minimum-cycles.json`.
- [x] Verify every approved costume at all four sizes and exact all-color still bytes; 72 Python tests and Node controls pass.
- [ ] Evaluate further edited clap cycles manually or with improved source-space checks; the other 23 families currently retain full loops.
- [ ] Compare shortened seams over actual repeats with game-reference footage before claiming production loop fidelity.

- [x] Expand batch selection to all eight Mario animation/section choices for every actual costume ID, including taunt and victory waits.
- [x] Add independent animation/color selectors that preserve the chosen color.
- [x] Add uniquely named single-GIF downloads, per-animation color ZIPs, and a full GIF ZIP.
- [x] Add validated resume and strict full-matrix gallery checks; regression tests cover color/file identity and ZIP contents.

Rebuild the full roster and download bundles with:

```powershell
python -m tools.melee_anim.roster_batch --resume --jobs 8
python -m tools.melee_anim.cycles
python -m tools.melee_anim.preview_gallery --require-all
python -m tools.melee_anim.verify_previews
node tools/melee_anim/tests/test_gallery.js
python -m tools.melee_anim.player_server
```

The target is 984 GIFs across all actual costume selections. The viewer provides the selected GIF, an animation's costume ZIP, and the full collection. Pause or scrub to expose the selected-frame PNG and an all-costume ZIP for that exact displayed frame. A one-based displayed frame 68 is `frame_0067.png`; it is independent of the source-tick number shown beside it.

For sized downloads, open `http://127.0.0.1:8765/player.html` while the Python player service is running. Extra small is 128px, Small/default 256px, Medium 512px, and Large 1024px. This applies to GIF/PNG and color/full-GIF bundles. Medium/Large currently upscale existing masters; there is no new software to install. Original-size file downloads still work without the service.

- [x] Add download-size selection without resetting the selected costume, animation, or paused frame.
- [x] Add cached on-demand GIF/PNG resizing, preserving GIF timing/loops and PNG RGBA.
- [x] Apply size selection to individual and all-color downloads; serialize local-service generation to bound memory.
- [x] Verify all four sizes with synthetic tests and real Mario exports, plus Game & Watch and paired Ice Climbers loop checks (68 Python tests and Node tests pass).
- [ ] Add an explicit higher-detail render option later; current 512/1024px exports resample 256px masters.

- [x] Honor exported front/back PObj culling flags in both raster backends; review rendered roster contact sheets.
- [ ] Make source/output duration rounding explicit and decide one-shot terminal hold behavior. Current 50-frame waits become 42 GIF frames at 50 fps (0.84s); taunt includes one final frame (3.02s).
- [x] Reject stale extra PNG frames before rendering, and refuse them in resume/gallery validation; preserve unrelated files.
- [x] Bound results clip reads to their owning public region for compound Popo/Nana archives.
- [x] Add source scale clamping and joint node/branch visibility; correct Game & Watch's class-4 item visibility.
- [x] Run 65 Python tests, including synthetic native raster depth/culling and paused-frame ZIP invalidation checks.
- [x] Render all 984 jobs; retain all 123 costume selections, four Game & Watch runtime colors, and paired Nana models.
- [x] Add character selection and selected/all-color paused-frame PNG downloads.
- [x] Verify all 984 GIF jobs, 209 GIF bundle inventories/hashes, 17,348 still ZIP frame filenames, and exact first/frame-68/final images per action.
- [x] Run Node tests for every character/action/costume and paused-frame 68/101; retain the no-live-browser-test limitation.
- [ ] Compare rendered poses/loops with original game reference, including props, material changes, and paired placement.
- [ ] Include evaluator/renderer/script and companion hashes in resume fingerprints; current resume verifies model/settings/file sets.
- [ ] Add manifest-driven MP4 encoding and `ffprobe` validation after FFmpeg is available.

## Optional installation steps for later

**The current CPU preview does not require Blender or FFmpeg.** Python 3.13, NumPy 2.2.4, and Pillow 11.1.0 are already working here. Node is only needed for the optional player-logic test.

For the planned production renderer:

- [ ] Download the stable **Windows x64 ZIP** from [Blender's download page](https://www.blender.org/download/), record the exact version, and extract it to a stable directory such as `C:\Tools\Blender`. The ZIP can run without an installer; use the [Windows installation instructions](https://docs.blender.org/manual/en/4.2/getting_started/installing/windows.html).
- [ ] Locate `blender.exe`, launch it once to confirm it works, and run `& 'C:\Tools\Blender\blender.exe' --version` using the actual extracted path.
- [ ] Record that executable path/version in task configuration. Adding it to PATH is optional; an explicit path is sufficient. Blender provides its own Python/`bpy`; do not assume the system Python can import `bpy`.
- [ ] Implement/test the Blender importer/backend using the existing exported model/poses. Installation alone does not add DAT import or make the current CPU command use Blender.

For MP4 encoding:

- [ ] Follow the **Windows EXE Files** links on [FFmpeg's official download page](https://ffmpeg.org/download.html) to a prebuilt Windows package, such as Gyan's [release essentials ZIP](https://www.gyan.dev/ffmpeg/builds/). Extract it to a stable directory such as `C:\Tools\FFmpeg`.
- [ ] Locate both `bin\ffmpeg.exe` and `bin\ffprobe.exe`; verify with `ffmpeg -version` / `ffprobe -version` or their full paths. Record the tested versions and confirm `ffmpeg -encoders` lists `libx264`.
- [ ] Configure their full paths or add the package's `bin` directory to PATH. No FFmpeg Python wrapper is needed.
- [ ] Test one current clapping sequence, then verify duration/dimensions/frame count with ffprobe. Example future command (not run yet):

```powershell
& 'C:\Tools\FFmpeg\bin\ffmpeg.exe' -framerate 50 -i 'build/melee_anim/preview/mario/costume_00/results-clap_source/frame_%04d.png' -frames:v 15 -c:v libx264 -pix_fmt yuv420p -movflags +faststart 'build/melee_anim/preview/mario/costume_00/results-clap_source/preview.mp4'
```

Use actual extracted executable paths and each job manifest's frame count/fps. The current preview background is opaque; production transparent PNG/alternative video formats remain separate work.

## 0. Preserve the investigation

- [x] Inspect the actual checkout for animation/model assets and relevant source code.
- [x] Trace results victory selection, loser animation selection, and costume enumeration.
- [x] Identify ordinary action motions and damage/ground animation paths.
- [x] Document the recommended architecture and durable guidance in root Markdown files.

## 1. Make the game data available locally

- [x] Locate `melee.iso`: GALE01 disc revision 2.
- [x] Create a reusable stdlib extraction tool and extract 1,209 game + five system files under `orig/GALE01`.
- [x] Verify the original DOL SHA-1 against configuration; record ISO SHA-256 and verify every output hash in the extraction manifest. Verify idempotent reruns.
- [x] Confirm Mario prerequisites and all five costume model/material roots.
- [x] Inspect both `GmRst.dat` / `.usd` panel/film camera, light, and UI model descriptors; confirm `SdRst.dat` is extracted.
- [x] Verify Git ignores the ISO, extraction manifest, all 1,214 outputs, generated reports, and bytecode. Existing rules already cover them.

Done when: a readiness report lists exact paths, hashes, expected symbols, and missing dependencies without attempting to render.

## 2. Establish a small repeatable toolchain

- [x] Establish working dependency-free extraction/inspection under Python 3.13 with focused synthetic `unittest` coverage.
- [ ] Verify/pin Blender and FFmpeg/ffprobe for rendering/encoding; native toolchains remain optional.
- [ ] If using the repository's Nix/schema builds, establish the Linux/WSL2 environment and required Aurora/type inputs. Do not assume the current native CMake preset is a runnable viewer.
- [x] Create the separate `tools/melee_anim` package and document its implemented extraction/inspection commands.
- [ ] Define explicit inputs, cache/output paths, and a versioned job/catalog schema.
- [x] Add extraction/list and motion/model/scene inspection CLIs with format/hash validation.
- [ ] Add renderer/encoder readiness diagnostics when those components are introduced.

Done when: one documented command reports readiness and selected versions on the intended development machine.

## 3. Build a verified asset catalog

- [x] Add a focused bounded DAT/DOL reader using the existing source layouts; preserve relocated zero pointers.
- [x] Validate 8,011 ordinary motion references across 33 internal tables with the Python inspector. The existing Rust `symbols check-motions` was not run; leave Rust integration for when useful/available.
- [x] Validate all 27 packed results regions, 244 nonempty references, owning public bounds, sizes, publics, flags, and keyframe packet structures.
- [x] Resolve actual Mario result clip names/offsets/durations and separate `Win*Wait` assets; automatic original-scene transitions remain unverified.
- [x] Read actual DOL external/internal mappings, including Popo/Nana and Zelda/Sheik.
- [x] Validate 123 selectable costume records plus four Nana member records and every referenced joint/material-animation public.
- [x] Inspect Mario's costume visibility tables; retain shared-file Game & Watch IDs and extract its runtime RGBA/width data.
- [x] Validate all 26 roster entries' costume counts and skeleton hierarchies; inspect all 124 unique model archives and supported raw mesh/texture formats.

Done when: catalog output can explain where each requested clip and costume comes from. Start with Mario; keep unsupported cases visible.

## 4. Prove motion evaluation before batch rendering

- [x] Decode Mario clapping: 61 nodes, 47 animated nodes, 142 tracks, 18 source frames, motion-loop flag enabled.
- [x] Implement a preliminary packed scalar decoder/evaluator covering step/linear/Hermite/slope/key packets, signed starts, and unwrapped endpoints.
- [x] Verify mixed byte-order and interpolation/terminal edge cases with synthetic samples; report exact endpoint, left-limit, and finite-slope differences.
- [ ] Compare scalar and matrix results against native HSD/game reference samples; the current evaluator uses Python double precision and is not a complete runtime.
- [ ] Establish source tick-to-output timing against reference capture.
- [x] Load Mario's costume bind transforms and evaluate/render poses for clapping, all three victories/waits, and taunt.
- [x] Create and visually inspect contact sheets; preserve intentional type-0 taunt enlargement.
- [ ] Compare rendered poses against original game/viewer reference frames; this native-fidelity check remains open.
- [x] Select the working focused Python reader/evaluator as the first importer foundation based on actual asset access; native/HSDRaw remain targeted references/replacements if discrepancies justify them.

Done when: known clapping poses match the reference and the game-authored loop interval is identified. Do not approximate every curve as linear.

## 5. Render the first complete character

- [x] Inspect all five Mario costume GX layouts/display-list indices, envelopes/weights, UV metadata, texture/palette descriptors, and basic material references.
- [x] Export Mario meshes with consistent bind geometry, exact source palettes/coordinates, bone transforms, normals, UVs, and initial visibility.
- [x] Decode CMPR and C8/RGB565-palette pixels and export all five costume models/185 PNG textures; preserve texture matrices and mirrored wrap.
- [x] Implement a first NumPy/Pillow CPU renderer with skinning, depth, basic textures, PNG/GIF output, and whole-interval camera fitting.
- [ ] Complete accurate TEV/reflection, timed material/visibility scripts, props, effects, and native reference checks.
- [ ] Import the model and sampled transforms into Blender; handle scale compensation and hierarchy differences explicitly.
- [ ] Add a fixed camera, whole-interval bounds fitting, lighting, and background/alpha settings.
- [ ] Apply required part visibility and appearance animation.
- [ ] Render a few reference poses and review mesh deformation, orientation, textures, normals, and crop.
- [ ] Record remaining shading/TEV or runtime-feature differences and choose acceptable first-milestone fidelity.

Done when: one Mario clapping frame renders correctly and the same importer can render multiple poses consistently.

## 6. Produce the first working MP4 and GIF

- [x] Render Mario clapping cycles in all five costumes to numbered PNGs and looping GIFs; also render three victory entrances, three waits, and taunt in default costume.
- [ ] Measure pose/appearance continuity before endpoint wrapping; visually inspect at least three actual repeats.
- [ ] Preserve first-play, endpoint, and rewind rules; avoid inserting a duplicate endpoint frame.
- [x] Add pilot GIF encoding with shared palette, explicit delays, and authored-loop metadata. Twelve completed jobs' durations and file counts were checked.
- [ ] Add FFmpeg production MP4/GIF encoding and decoded-output verification.
- [ ] Add `ffprobe`/decoded-frame verification for duration, frame count, dimensions, and the encoded seam.
- [ ] Save a reproducibility manifest with inputs, hashes, source interval, timing, camera, versions, and limitations.
- [ ] Document one end-to-end command that produces both formats.

Done when: default Mario clapping exports successfully to both formats and is reviewed for smooth repeating playback. This is the first working solution.

## 7. Record an action in every costume variant

- [x] Add Mario `preview_batch --costume all` using actual DOL costume IDs; full roster action/costume inventory is generated separately.
- [x] Export Mario clapping in all five costumes with shared source timing and framing; review costume contact sheets.
- [ ] Verify costume-specific joint/material/visibility/accessory behavior and create a contact sheet labeled by costume ID.
- [ ] Add stable filenames, progress reporting, resumable jobs, source-sensitive caching, and failures associated with specific variants.
- [x] Render the `all` path on all four/five/six-costume families; validate expected costume counts.
- [x] Render all four Mr. Game & Watch colors despite their shared model archive.
- [x] Add paired Ice Climbers exports with actual Popo/Nana costume mapping; exact game placement remains open.
- [x] Add `verify_previews.py` producing a full expected/completed coverage report for the current eight-choice scope.

Done when: requesting one supported action with `all` produces exactly one verified artifact set per real costume variant.

## 8. Finish results animation coverage

- [x] Add victory variants 1, 2, and 3 with explicit mappings to game variants 0, 1, and 2.
- [x] Expose verified entrance/primary wait clips independently, preserving each wait's actual loop flag.
- [ ] Confirm the unusual variant/state mappings from the demo table; do not interpret reused `Dead*` state labels as death clips.
- [x] Inspect authored result durations and loop flags, including Fox slot 4 and unflagged Falco `Win3Wait`.
- [ ] Validate rendered loop continuity separately for every character/variant; inspect pre-terminal limits and derivatives, and label one-shot or edited output honestly.
- [ ] Add per-character demo callbacks, accessories, dynamics, and visibility behavior needed for accurate results animations.
- [x] Batch clapping and all three victory entrances/waits across all 123 roster costumes.
- [ ] Review edge cases: paired Ice Climbers, Zelda/Sheik form selection, Mr. Game & Watch orientation/materials, and multiple/team winners.

Done when: a reviewed results-animation coverage matrix has an outcome for every roster/variant/costume combination.

## 9. Extend to taunts and attacks

- [x] Resolve all standard taunt states/clips through verified DOL callbacks and motion records, keeping Zelda/Sheik separate.
- [x] Catalog directional fallback, Dr. Mario/Young Link overrides, Nana's Popo source, and Fox/Falco multipart stage taunts.
- [x] Join these actions to all 123 real costume selections; record runtime caveats and primary waits in the 1,123-job inventory.
- [ ] Execute required taunt scripts/props/effects and render the other fighters; metadata coverage is not rendering coverage.
- [ ] Add forward smash, including supported angle variants, charge timing, and character-specific follow-ups/accessories.
- [ ] Distinguish source skeleton playback from full gameplay behavior requiring subaction commands, particles, items, root motion, hitlag, or physics.
- [ ] Support source, segment, once, and explicitly requested edited-loop modes.
- [ ] Export each supported action across all costumes using the same batch infrastructure.
- [ ] Add a Dolphin/native capture path only where the required runtime behavior cannot be reproduced sufficiently by the importer; verify its deterministic setup.

Done when: taunt and forward-smash exports are repeatable, correctly identified, and explicit about runtime features and loop behavior.

## 10. Extend to damage, tumble, and ground states

- [ ] Catalog grounded/aerial directional hit reactions and severity variants.
- [ ] Add tumble (`DamageFall`) and distinguish its pose cycle from knockback trajectory/rotation.
- [ ] Add knockdown/bounce, downed wait, downed damage, getup, getup attack, rolls, and tech-related motions.
- [ ] Define scenario parameters for trajectory-dependent recordings: starting state, facing, velocity/rotation, floor contact, hitlag, and transitions.
- [ ] Validate facing and face-up/face-down variants against reference playback.
- [ ] Batch supported pose clips/scenarios across every costume.

Done when: these are usable named exports with documented scenario dependencies, rather than mislabeled isolated poses.

## 11. Reconstruct the composed results screen

- [ ] Load results camera, light, layout, UI, and transition assets.
- [ ] Reproduce winner placement, per-character scale, variant-specific framing, and team/paired-character behavior.
- [ ] Render animated loser squares and reproduce their compositing/placement.
- [ ] Add results presentation timing, text/stats inputs, and optional sound as a separate scope.
- [ ] Compare a composed sequence with original game capture, then export through the existing image/encoding pipeline.

Done when: both isolated character assets and a composed results scene can be exported from reproducible jobs.

## 12. Make the working tool comfortable to use

- [x] Add offline character/action/costume preview, scrubbing, GIF saving, and selected/all-costume paused PNG downloads.
- [ ] Add saved export presets and production settings.
- [ ] Consider a small GUI with character/action/costume selection and batch progress.
- [ ] Package setup instructions and reference examples for Windows; document any optional WSL/native helper requirements.
- [ ] Maintain source and dependency attribution for reused code, and keep fixture tests independent of checked-in original game assets.
- [ ] Refresh `INVESTIGATION.md`, `PLAN.md`, and `AGENTS.md` when evidence or architecture changes.

Avoid expanding GUI, packaging, full game porting, or complete results UI work ahead of the first verified clapping MP4/GIF.

Current reviewable output: `build/melee_anim/preview/player.html` with 984 character/animation/color choices and exact paused-frame downloads. The full GIF bundle is `downloads/melee-all-characters-all-animations.zip`. Masters, bundles, player, and verification report stay ignored under `build/melee_anim/preview`. Regenerate with the commands above. Native shader/scripts and loop perfection remain unverified; continue with reference/fidelity and MP4 work, avoiding repeated extraction/catalog work.


[ ] want more sizes for the produced gifs - extra small (128), medium (512), large (1024)
- [ ] Add user-controlled camera rotation around the model's 3D axes (current CLI has yaw only).
