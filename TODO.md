# Ordered implementation checklist

Created 2026-10-10. The initial deliverable is planning documentation; the unchecked items below are future implementation work. See [PLAN.md](PLAN.md) for the architecture and [INVESTIGATION.md](INVESTIGATION.md) for source evidence. Update this file as working artifacts are verified.

## 0. Preserve the investigation

- [x] Inspect the actual checkout for animation/model assets and relevant source code.
- [x] Trace results victory selection, loser animation selection, and costume enumeration.
- [x] Identify ordinary action motions and damage/ground animation paths.
- [x] Document the recommended architecture and durable guidance in root Markdown files.

## 1. Make the game data available locally

- [ ] Locate the user's game dump/extraction and determine its revision.
- [ ] Supply extracted assets at `orig/GALE01/files` and the original executable at `orig/GALE01/sys/main.dol`, or configure equivalent external paths.
- [ ] Verify the executable against `config/GALE01/config.yml`; record the revision and hashes of source files.
- [ ] Confirm Mario prerequisites: `PlCo.dat`, `PlMr.dat`, `PlMrAJ.dat`, `GmRstMMr.dat`, and all five costume files listed in `ftmariostrings.c`.
- [ ] Confirm the additional results camera/light/UI archive references needed for comparison captures. Full scene reconstruction comes later.
- [ ] Ensure original assets and generated asset caches/exports stay out of Git. The existing `orig` ignore rules cover original inputs; add output ignores when those directories are created.

Done when: a readiness report lists exact paths, hashes, expected symbols, and missing dependencies without attempting to render.

## 2. Establish a small repeatable toolchain

- [ ] Verify Python, Blender, FFmpeg/ffprobe, and any needed Cargo/CMake tools; pin versions after the first compatibility check.
- [ ] If using the repository's Nix/schema builds, establish the Linux/WSL2 environment and required Aurora/type inputs. Do not assume the current native CMake preset is a runnable viewer.
- [ ] Create a separate Python package for animation tooling; keep ordinary export commands readable and documented.
- [ ] Define explicit inputs, cache/output paths, and a versioned job/catalog schema.
- [ ] Add a minimal CLI with asset readiness and dependency diagnostics.

Done when: one documented command reports readiness and selected versions on the intended development machine.

## 3. Build a verified asset catalog

- [ ] Reuse DAT header/public/relocation parsing from `tools/dat-cli` where practical.
- [ ] Run the existing `symbols check-motions` against the extracted normal fighter animations.
- [ ] Add bounded traversal and validation of embedded results motion-file archives and demo `ftData.x14` references. These are not covered by the existing normal-motion validator.
- [ ] Resolve Mario's result motion-file public symbol, nested `FigaTree` publics, lengths, and offsets; determine whether any entrance/loop sections or transitions exist.
- [ ] Map external roster characters to internal fighter kinds, including Popo/Nana and Zelda/Sheik.
- [ ] Enumerate costume IDs from authoritative tables, then resolve file, joint, material-animation, visibility, and runtime-color references.
- [ ] Keep shared-file costumes distinct; include Mr. Game & Watch's runtime color setup in the schema.
- [ ] Expand the catalog to the 26 roster entries and their real costume counts; validate extracted assets against the source-derived mapping.

Done when: catalog output can explain where each requested clip and costume comes from. Start with Mario; keep unsupported cases visible.

## 4. Prove motion evaluation before batch rendering

- [ ] Decode one Mario clapping `FigaTree`, preserving node traversal and channel assignments.
- [ ] Implement or adapt packed FObj decoding, defaults, step/linear/Hermite behavior, frame progression, and loop semantics from the decomp.
- [ ] Verify mixed byte-order handling and source-to-output timing with small known samples.
- [ ] Load the costume skeleton/bind transforms and evaluate a pose at several known frames.
- [ ] Display a diagnostic skeleton or pose contact sheet and compare against game/viewer reference frames.
- [ ] Compare a focused Python importer against a small native or HSDRaw adapter; document the selected data-reader/evaluator approach.

Done when: known clapping poses match the reference and the game-authored loop interval is identified. Do not approximate every curve as linear.

## 5. Render the first complete character

- [ ] Decode Mario's default costume GX geometry, attachments/envelopes, textures, UVs, and basic materials.
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
- [ ] Validate loop continuity separately for each character/variant; label one-shot or edited output honestly.
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
