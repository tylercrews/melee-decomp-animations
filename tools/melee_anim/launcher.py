"""Windows double-click setup/UI orchestration, using only the standard library.

python -m tools.melee_anim.launcher import [path/to/melee.iso]
python -m tools.melee_anim.launcher import --extract-only
python -m tools.melee_anim.launcher open [--port 8765] [--no-browser]
python -m tools.melee_anim.launcher check
"""
import argparse
from importlib import metadata
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import urlopen
import webbrowser


REPO = Path(__file__).resolve().parents[2]
PACKAGES = {'numpy': '2.2.4', 'Pillow': '11.1.0'}


def check_python():
    if os.name != 'nt':
        raise ValueError('These launchers require Windows. The current full-roster raster backend uses Windows OpenGL.')
    if not (3, 10) <= sys.version_info[:2] <= (3, 13) or struct.calcsize('P') != 8:
        raise ValueError('Use 64-bit Python 3.13 (compatible range: 3.10-3.13). See README.md for the download link.')


def packages_ready():
    try:
        return all(metadata.version(name) == version for name, version in PACKAGES.items())
    except metadata.PackageNotFoundError:
        return False


def run_step(command, repo, label):
    print(f'\n{label}', flush=True)
    result = subprocess.run(command, cwd=repo,
                            env={**os.environ, 'OPENBLAS_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1'})
    if result.returncode:
        raise RuntimeError(f'{label} failed (exit {result.returncode}). Fix the error above and run Import Melee Iso again.')


def environment_python(repo):
    """Install only inside this checkout's ignored .venv, never globally."""
    if packages_ready():
        return sys.executable
    executable = repo/'.venv/Scripts/python.exe'
    if not executable.is_file():
        run_step([sys.executable, '-m', 'venv', str(repo/'.venv')], repo, 'Creating local Python environment')
    run_step([str(executable), '-m', 'pip', 'install', '--only-binary=:all:', '-r',
              str(repo/'tools/melee_anim/requirements.txt')], repo,
             'Installing NumPy and Pillow in .venv (internet access needed on first setup)')
    return str(executable)


def preparation_steps(python, iso, jobs=4):
    return [
        ('Checking the ISO and extracting game files', [python, '-m', 'tools.melee_anim.extract_iso', str(iso)]),
        ('Inspecting motions', [python, '-m', 'tools.melee_anim.inspect_motions', '--output', 'build/melee_anim/motions.json']),
        ('Inspecting costume models', [python, '-m', 'tools.melee_anim.inspect_models', '--catalog']),
        ('Building the action catalog', [python, '-m', 'tools.melee_anim.catalog']),
        ('Rendering all characters and costumes (resumes completed jobs)',
         [python, '-m', 'tools.melee_anim.roster_batch', '--resume', '--jobs', str(jobs)]),
        ('Finding minimum and dirty clapping intervals', [python, '-m', 'tools.melee_anim.cycles']),
        ('Rendering 0.84-second synchronized claps',
         [python, '-m', 'tools.melee_anim.sync_claps', '--resume', '--jobs', str(jobs)]),
        ('Building the player and download bundles', [python, '-m', 'tools.melee_anim.preview_gallery', '--require-all']),
        ('Verifying the prepared animations and downloads', [python, '-m', 'tools.melee_anim.verify_previews']),
    ]


def import_iso(repo, iso, jobs=4, extract_only=False):
    iso = iso.resolve()
    if not iso.is_file():
        raise ValueError(f'ISO not found: {iso}\nPut your game dump beside README.md and name it melee.iso, then run Import Melee Iso.cmd.')
    if extract_only:
        run_step([sys.executable, '-m', 'tools.melee_anim.extract_iso', str(iso)], repo, 'Checking and extracting the ISO')
        print('Extraction complete. Run the full Import Melee Iso launcher to prepare the UI.', flush=True)
        return
    # Reject incompatible images before installing packages or rendering.
    steps = preparation_steps(sys.executable, iso, jobs)
    label, command = steps[0]
    run_step(command, repo, label)
    python = environment_python(repo)
    for label, command in preparation_steps(python, iso, jobs)[1:]:
        run_step(command, repo, label)
    print('\nImport complete. Double-click Open Melee Decomp Animation UI.cmd.', flush=True)


def server_status(port, root):
    """Distinguish an absent server from another program/checkout on the port."""
    try:
        with urlopen(f'http://127.0.0.1:{port}/_health', timeout=2) as response:
            status = json.load(response)
    except HTTPError as error:
        raise ValueError(f'Port {port} is used by another service. Use open --port 8766 or close that service.') from error
    except (URLError, TimeoutError):
        return False
    except (ValueError, UnicodeError) as error:
        raise ValueError(f'Port {port} is used by an unrecognized service.') from error
    if not isinstance(status, dict) or status.get('service') != 'melee-animation-downloads':
        raise ValueError(f'Port {port} is used by another service.')
    if not status.get('root') or Path(status['root']).resolve() != root.resolve():
        raise ValueError(f'A player for another checkout or an older server is on port {port}. Close it or run open --port 8766.')
    return True


def open_ui(repo, python, port=8765, browser=True):
    root = repo/'build/melee_anim/preview'
    if not (root/'player.html').is_file() or not (repo/'build/melee_anim/motions.json').is_file():
        raise ValueError('The animations are not prepared yet. Run Import Melee Iso.cmd first.')
    # Do not install or regenerate anything merely to reopen an existing UI.
    process = None
    if not server_status(port, root):
        log_path = repo/'build/melee_anim/player-server.log'
        with log_path.open('ab') as log:
            process = subprocess.Popen([python, '-m', 'tools.melee_anim.player_server', '--root', str(root), '--port', str(port)],
                                       cwd=repo, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                       creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                                       env={**os.environ, 'OPENBLAS_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1'})
        deadline = time.monotonic()+60
        try:
            while not server_status(port, root):
                if process.poll() is not None or time.monotonic() >= deadline:
                    raise RuntimeError(f'Player did not start. See {log_path}')
                time.sleep(.2)
        except Exception:
            if process.poll() is None:
                process.terminate()
            raise
    url = f'http://127.0.0.1:{port}/player.html'
    if browser:
        webbrowser.open(url)
    print(f'Player ready: {url}', flush=True)
    if process:
        print(f'Background server PID: {process.pid}. Log: {repo / "build/melee_anim/player-server.log"}', flush=True)
    return url


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    importing = sub.add_parser('import', help='extract the ISO and prepare all animations')
    importing.add_argument('iso', nargs='?', type=Path, default=REPO/'melee.iso')
    importing.add_argument('--extract-only', action='store_true')
    importing.add_argument('--jobs', type=int, choices=range(1, 9), default=4)
    opening = sub.add_parser('open', help='start/reuse the local player and open the browser')
    opening.add_argument('--port', type=int, default=8765)
    opening.add_argument('--no-browser', action='store_true')
    sub.add_parser('check', help='report setup readiness without installing, importing or opening anything')
    args = parser.parse_args()
    try:
        check_python()
        if args.command == 'import':
            import_iso(REPO, args.iso, args.jobs, args.extract_only)
        elif args.command == 'open':
            if not 1024 <= args.port <= 65535:
                raise ValueError('Port must be 1024-65535')
            if not packages_ready():
                raise ValueError('NumPy/Pillow are not ready in this Python environment. Run Import Melee Iso.cmd first, or install requirements.txt as described in README.md.')
            open_ui(REPO, sys.executable, args.port, not args.no_browser)
        else:
            print(f'Python: {sys.version.split()[0]} (64-bit Windows)\nRequired packages ready: {packages_ready()}\n'
                  f'ISO: {(REPO / "melee.iso").is_file()}\nPlayer: {(REPO / "build/melee_anim/preview/player.html").is_file()}')
    except (OSError, ValueError, RuntimeError) as error:
        parser.exit(1, f'\n{error}\n')
    except KeyboardInterrupt:
        parser.exit(130, '\nStopped. Run the import launcher again to resume completed render jobs.\n')


if __name__ == '__main__':
    main()
