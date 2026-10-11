# Melee Decomp Animation UI

Preview Super Smash Bros. Melee character animations and download GIFs or paused-frame PNGs in every actual costume color. The player includes clapping, taunts, victory poses, attacks, techs/ground animations, X/Y/Z viewing angles, and 128/256/512/1024/2048px downloads. Zelda and Sheik have separate entries; Ice Climbers include both characters.

This is a Windows prototype built on the Melee decompilation. Rendering, lighting and game effects are approximate. MP4 export is future work.

## 1. Download what you need

- Download and extract this entire repository, or clone it with Git. Keep its folders together and run it from the extracted folder, not inside a ZIP.
- Install **64-bit Python 3.13** from [Python's Windows downloads](https://www.python.org/downloads/windows/). Choose a **Python 3.13 Windows installer (64-bit)** and enable **Add Python to PATH**. The current pinned packages support Python 3.10–3.13; avoid choosing a newer Python for this setup. [NumPy compatibility](https://numpy.org/doc/stable/release/2.2.4-notes.html).
- Have your own compatible Melee game dump. Game files are not included in the repository.
- Use a normal browser such as Edge, Chrome or Firefox.

The import launcher installs **NumPy 2.2.4** and **Pillow 11.1.0** into this folder's `.venv` if the chosen Python does not already have those exact versions. Internet access is needed for that first package installation. Package versions are pinned in [requirements.txt](tools/melee_anim/requirements.txt); see [NumPy](https://pypi.org/project/numpy/2.2.4/) and [Pillow](https://pypi.org/project/pillow/11.1.0/).

Blender, Dolphin, FFmpeg, Node and a game compiler are **not required for the current UI or GIF/PNG exports**. Windows supplies the OpenGL rasterizer used by the current renderer. Node is only needed for developer UI tests. Leave enough free disk space for the ISO, extracted files, tens of thousands of PNG frames and download bundles; these are generated locally.

## 2. Put the ISO beside this README

Name the file **`melee.iso`** and put it in the root folder:

```text
melee-decomp-animations/
    README.md
    Import Melee Iso.cmd
    Open Melee Decomp Animation UI.cmd
    melee.iso                         <-- your game dump goes here
    tools/
    src/
    config/
```

Turn on **File Explorer → View → Show → File name extensions** so you can check the actual name is `melee.iso`, not `melee.iso.iso`.

The current tables require the **GALE01 NTSC-U revision 2 / Melee 1.02** executable, whose SHA-1 is `08e0bf20134dfcb260699671004527b2d6bb1a45`. The importer checks the executable before extraction and rejects incompatible images. Use a raw ISO/GCM image; compressed RVZ/GCZ/NKit images are not supported. Renaming a compressed image to `.iso` does not convert it.

The ISO and extracted/rendered assets are ignored by Git. They remain on your computer.

## 3. Double-click “Import Melee Iso”

Open **[Import Melee Iso.cmd](Import%20Melee%20Iso.cmd)** from File Explorer. A command window shows progress and any errors. There is no separate extraction app to open.

The launcher:

1. Checks `melee.iso` and extracts it into `orig/GALE01/files` and `orig/GALE01/sys`.
2. Prepares the Python packages when needed.
3. Builds the character, costume and animation catalogs.
4. Renders the 984 original animation/costume previews and the 123 synchronized clapping previews.
5. Builds the HTML player, GIF/PNG download bundles and verification report.

The first preparation takes time. Keep the progress window open until **“Import complete”** appears. If a step fails, read the error above it. Run the same launcher again after fixing the issue; extraction verifies existing files and rendering resumes completed jobs. Different existing game files are refused rather than overwritten automatically.

To extract files only, open PowerShell in this folder and run:

```powershell
& '.\Import Melee Iso.cmd' --extract-only
```

Extraction alone does not create the UI; run the full import afterward.

## 4. Double-click “Open Melee Decomp Animation UI”

Open **[Open Melee Decomp Animation UI.cmd](Open%20Melee%20Decomp%20Animation%20UI.cmd)**. It starts the local player quietly, or reuses the running player for this repository, and opens your default browser at:

**[http://127.0.0.1:8765/player.html](http://127.0.0.1:8765/player.html)**

Use this launcher whenever you want the UI. It does not reimport or rerender the whole collection. Its command window can close after the browser opens; the background server keeps running until stopped or Windows shuts down. A later launch after a restart starts it again.

Select a character from the alphabetical dropdown, **Animation Type**, and costume. Types are **Victory Pose, Taunt, Clapping, Attack, Knockdown, Movement**. An Animation dropdown appears when the type has multiple choices. Victory includes entrances and their authored loops. Attack includes normal attacks, aerials, grounded/aerial specials and their separate phases, grabs/throws, getup/ledge attacks, and item attacks. Selecting an attack or tech renders that costume once and saves it for reuse; an all-color download renders any remaining colors. For Kirby, a **Kirby Power** dropdown appears with **None / Kirby** and every other character's copy appearance. Choose any power independently of the animation; it carries through to previews, viewing angles, clapping modes, GIFs, exact stills, every costume color and all five sizes. Hats and replacement bodies are rendered on demand from the original assets. Hat dynamics and copied props/projectiles still need work. Beam Sword, Home-Run Bat, Parasol, Fan, Star Rod and Lip's Stick now appear automatically in their item swing attacks, including all costume colors and GIF/PNG downloads. Item labels identify the weapon. Parasol and Fan use source-timed prop curves; full projectile/collision behavior, attack-driven Beam Sword extension and character-specific spawned props remain unfinished. No additional installation or ISO import is needed. Character props now include Fox/Falco blasters, Sheik held/released needles, Kirby Final Cutter/hammer, Mario/Dr. Mario cape/sheet, Peach Toad/parasol, Link/Young Link bows and Ness's bat. Sheik uses a six-needle preset with deterministic free flight; hits and bounces are not simulated. Other projectiles and procedural props remain unfinished.

**Knockdown** includes tech in place, towards/forward and away/backward tech rolls, missed-tech landings face up/down, and lying on the ground face up/down, for all 26 characters and every costume. Towards/away mean relative to the character's facing. **Ground-impact effects** starts enabled and can be switched off; lying animations have no impact effect. Preview, right-click saving, GIFs, exact paused PNGs, all colors, sizes and viewing angles use that same setting. The game’s core tech flash and ground burst are rendered from extracted meshes/textures/curves; extra dust/sparkle particles and exact effect blending still need work. Knockdown fighters are centered across the whole motion, with the complete visible impact fitted at the same scale. Larger bursts make the character smaller; impacts are not independently shrunk or cropped. In-place and away rolls include a white fighter flash; towards rolls retain their normal colors. Turning ground effects off zooms in to fit the character alone, while keeping the fighter flash, timing and paused frame. Turning them on fits the entire impact again. This also applies to GIF/PNG downloads. Individual motion clips and missed-tech-to-lying presets are available; full fall → impact → recovery scenarios remain future work.

**Movement** includes standing, available alternate idle animations, walking speeds, running, dashing, and full/short hops. Ground movement plays in place. For full and short hops, **Keep character centered** follows the character with a fixed zoom, so it stays in the middle of the pane. The setting also applies to GIFs, paused PNGs, all colors, sizes and viewing angles; leave it unchecked to show the vertical trajectory. Hops are neutral presets with original squat/jump/fall/landing poses and character movement attributes; their shared framing shows the different heights. Stage collision, horizontal drift, fast fall and movement effects remain future work.

For multipart attacks, select a **“combined”** animation to play startup, one middle cycle, and the ending together. These include Kirby's up special, Fox/Falco blasters, supported charging/holding specials and rapid jabs. Individual phases remain available. In **Knockdown**, select **“Missed tech → lying on ground”** (face up or down) to play the landing and one lying cycle; Ground-impact effects still toggles the initial impact. Combined choices support every costume color, Kirby hats, viewing angles, GIFs and paused PNGs at all sizes. **Repeat Preview** repeats the entire sequence. These are finite playback presets; branching/alternate endings and exact game physics are still being developed. No additional software or ISO extraction is needed.

The Character list also includes **Wireframe - Male**, **Wireframe - Female**, **Sandbag**, **Master Hand**, **Crazy Hand**, and **Giga Bowser**. These use original fighter assets and each has one actual costume. Animation Type shows only available categories. Sandbag has **Movement**, **Knockdown**, and **Hit**; the hands have boss attacks, idles and **Other** entry/damage motions. The wireframes and Giga Bowser also have attacks, taunts and full/short hops. No results-screen victory/clapping clips are supplied for these models. They support the same transparent GIF/PNG exports, camera angles and sizes; projectiles, coordinated two-hand scenes and Sandbag's procedural joint constraints remain unfinished. The existing import attack-catalog step prepares these models automatically. To update an already imported checkout, run `python -m tools.melee_anim.attacks`, then `python -m tools.melee_anim.preview_gallery --require-all --player-only`, and restart the UI server.


GIFs and PNG stills have transparent backgrounds. The preview is clear, showing the page background through the image. Right-click the character to save its GIF while playing or its exact PNG while paused. The download buttons also save one costume or all colors at the selected size.

Download sizes are Extra small (128), Small (256, default), Medium (512), Large (1024), and **⚠ X-Large (2048)**. Selecting X-Large shows a dark-yellow “Extremely large GIF files” warning beside the dropdown. Sizes above 256 enlarge existing renders rather than adding detail.

Pause or scrub to download a still. Clapping has exclusive full, minimum, dirty/jittery and 0.84-second sync modes. Adjust the viewing-angle sliders and click **Apply**; a new angle needs rendering and is then cached. **Reset** returns to the original view. The aggregate results/taunt GIF collection remains available for those types; attacks and techs use per-animation downloads so one click does not trigger thousands of renders.

The generated HTML is `build/melee_anim/preview/player.html`. Opening that file directly supports the original previews; selecting an attack/tech or applying a rotation opens the local player with your selection preserved. This transfer applies once; reopening or refreshing the player starts X/Y/Z at 0. The HTTP player provides attack/tech playback and all on-demand rotated/resized exports.

## Troubleshooting and manual commands

- **Python was not found:** install 64-bit Python 3.13 with PATH enabled, then retry the launcher. It searches `.venv`, then `py -3.13`, then `python`.
- **Unsupported Python:** use Python 3.13. If an old `.venv` was made with another version, rename that folder before running the import launcher again.
- **Packages fail to install:** check the internet connection and the error in the progress window. You can install them manually with the commands below.
- **ISO not found / wrong revision:** check the name and location in step 2. The importer prints why a game image was rejected.
- **Animations not prepared:** run the full import, not just `--extract-only`.
- **UI fails to start:** check `build/melee_anim/player-server.log`. If port 8765 belongs to another program or another checkout, use `& '.\Open Melee Decomp Animation UI.cmd' --port 8766` in PowerShell.
- **Controls look outdated:** refresh the browser with Ctrl+Shift+R.

To use the terminal instead of double-clicking, open the repository folder in File Explorer, type `powershell` in its address bar and press Enter. These commands create a local environment and install the packages:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --only-binary=:all: -r tools/melee_anim/requirements.txt
.\.venv\Scripts\python.exe -m tools.melee_anim.launcher import
.\.venv\Scripts\python.exe -m tools.melee_anim.launcher open
```

No environment activation or PowerShell execution-policy changes are required. You can pass another ISO path to import: `& '.\Import Melee Iso.cmd' 'D:\Game Dumps\Melee.iso'`.

For a foreground server that you can stop with **Ctrl+C**, run:

```powershell
.\.venv\Scripts\python.exe -m tools.melee_anim.player_server --port 8766
```

Then open `http://127.0.0.1:8766/player.html`. To stop a background server started by the shortcut, use its printed PID (also visible as the repository's `tools.melee_anim.player_server` command in Task Manager). Closing a browser tab alone does not stop it.

If import reused matching packages already installed in your regular Python and did not create `.venv`, use `py -3.13` in place of `.\.venv\Scripts\python.exe` in the foreground command.

Local assets, masters, caches, bundles and server logs remain under ignored `orig/`, `build/` and `.venv/`. Development notes and limitations are in [INVESTIGATION.md](INVESTIGATION.md), [PLAN.md](PLAN.md), [TODO.md](TODO.md) and [AGENTS.md](AGENTS.md).
