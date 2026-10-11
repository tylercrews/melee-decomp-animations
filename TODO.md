# Ordered implementation checklist

Created and updated 2026-10-10. Extraction and asset-backed investigation are now complete; unchecked items remain future implementation work. See [PLAN.md](PLAN.md) for the architecture and [INVESTIGATION.md](INVESTIGATION.md), section 11, for evidence and implemented commands. No rendered animation/video has been produced yet.

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
- [ ] Load the costume skeleton/bind transforms and evaluate a pose at several known frames.
- [ ] Display a diagnostic skeleton or pose contact sheet and compare against game/viewer reference frames.
- [x] Select the working focused Python reader/evaluator as the first importer foundation based on actual asset access; native/HSDRaw remain targeted references/replacements if discrepancies justify them.

Done when: known clapping poses match the reference and the game-authored loop interval is identified. Do not approximate every curve as linear.

## 5. Render the first complete character

- [x] Inspect all five Mario costume GX layouts/display-list indices, envelopes/weights, UV metadata, texture/palette descriptors, and basic material references.
- [ ] Convert GX corners into a mesh with consistent bind-space coordinates; account for single-joint versus mixed-envelope matrix semantics before assigning Blender weights.
- [ ] Decode CMPR and C8/RGB565-palette texture pixels and build basic materials, including reflection/second-UV cases.
- [ ] Import the model and sampled transforms into Blender; handle scale compensation and hierarchy differences explicitly.
- [ ] Add a fixed camera, whole-interval bounds fitting, lighting, and background/alpha settings.
- [ ] Apply required part visibility and appearance animation.
- [ ] Render a few reference poses and review mesh deformation, orientation, textures, normals, and crop.
- [ ] Record remaining shading/TEV or runtime-feature differences and choose acceptable first-milestone fidelity.

Done when: one Mario clapping frame renders correctly and the same importer can render multiple poses consistently.

## 6. Produce the first working MP4 and GIF

- [ ] Render one complete clapping cycle to numbered PNG frames using deterministic sample times.
- [ ] Measure pose/appearance continuity before endpoint wrapping; visually inspect at least three actual repeats.
- [ ] Preserve first-play, endpoint, and rewind rules; avoid inserting a duplicate endpoint frame.
- [ ] Add FFmpeg encoding for MP4 with explicit frame rate/background and for GIF with palette generation, dithering, delays, and loop metadata.
- [ ] Add `ffprobe`/decoded-frame verification for duration, frame count, dimensions, and the encoded seam.
- [ ] Save a reproducibility manifest with inputs, hashes, source interval, timing, camera, versions, and limitations.
- [ ] Document one end-to-end command that produces both formats.

Done when: default Mario clapping exports successfully to both formats and is reviewed for smooth repeating playback. This is the first working solution.

## 7. Record an action in every costume variant

- [ ] Add `--costume all`, expanding each character's actual costume IDs rather than a fixed count or distinct filenames.
- [ ] Export Mario clapping in all five costumes with the same action timing and framing.
- [ ] Verify costume-specific joint/material/visibility/accessory behavior and create a contact sheet labeled by costume ID.
- [ ] Add stable filenames, progress reporting, resumable jobs, source-sensitive caching, and failures associated with specific variants.
- [ ] Verify the `all` path on a four-costume character and a six-costume character.
- [ ] Verify all four Mr. Game & Watch colors despite their shared model archive.
- [ ] Handle the Ice Climbers as a paired roster export and preserve the Popo/Nana costume mapping.
- [ ] Produce a coverage manifest that compares expected jobs with completed, unsupported, and failed exports.

Done when: requesting one supported action with `all` produces exactly one verified artifact set per real costume variant.

## 8. Finish results animation coverage

- [ ] Add victory variants 1, 2, and 3 with explicit mappings to game variants 0, 1, and 2.
- [ ] Determine whether each victory has an entrance and subsequent cyclic section; expose separate sections only where verified.
- [ ] Confirm the unusual variant/state mappings from the demo table; do not interpret reused `Dead*` state labels as death clips.
- [x] Inspect authored result durations and loop flags, including Fox slot 4 and unflagged Falco `Win3Wait`.
- [ ] Validate rendered loop continuity separately for every character/variant; inspect pre-terminal limits and derivatives, and label one-shot or edited output honestly.
- [ ] Add per-character demo callbacks, accessories, dynamics, and visibility behavior needed for accurate results animations.
- [ ] Batch clapping and all three victory variants across every supported roster costume.
- [ ] Review edge cases: paired Ice Climbers, Zelda/Sheik form selection, Mr. Game & Watch orientation/materials, and multiple/team winners.

Done when: a reviewed results-animation coverage matrix has an outcome for every roster/variant/costume combination.

## 9. Extend to taunts and attacks

- [ ] Resolve ordinary action states through their animation IDs and `ftData.xC` motion records into `Pl*AJ.dat` archives.
- [ ] Add taunt actions, including facing variants and character-specific multi-stage taunts.
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

- [ ] Add preview/scrubbing and saved export presets after the CLI pipeline is stable.
- [ ] Consider a small GUI with character/action/costume selection and batch progress.
- [ ] Package setup instructions and reference examples for Windows; document any optional WSL/native helper requirements.
- [ ] Maintain source and dependency attribution for reused code, and keep fixture tests independent of checked-in original game assets.
- [ ] Refresh `INVESTIGATION.md`, `PLAN.md`, and `AGENTS.md` when evidence or architecture changes.

Avoid expanding GUI, packaging, full game porting, or complete results UI work ahead of the first verified clapping MP4/GIF.

Current next step: assemble and skin Mario's default costume from the validated descriptors, apply the decoded `Lose` channels with correct HSD transforms/part defaults, decode its textures, and render reference poses. The 18-frame native loop has preliminary finger-channel seam differences; do not mark the first export perfectly seamless without repeated rendered inspection.
