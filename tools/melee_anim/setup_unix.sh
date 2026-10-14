#!/bin/sh
# Standard-library launcher bootstrap; third-party packages stay in .venv.
set -eu
platform=$1
mode=$2
shift 2
repo=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
cd "$repo"

case "$platform:$(uname -s)" in
    mac:Darwin|linux:Linux) ;;
    *) printf '%s\n' 'Use the setup/opener for your operating system.' >&2; exit 1 ;;
esac

case "${1-}" in
    -h|--help)
        printf '%s\n' 'Setup: [path/to/melee.iso] [--jobs 1..8] [--extract-only]' \
            'Open UI: [--port 8765] [--no-browser]' \
            'Setup installs Python if needed using Homebrew (Mac), apt or dnf (Linux).' \
            'Otherwise install 64-bit Python 3.10-3.13 yourself; see README.md.'
        exit 0 ;;
esac

compatible() {
    "$1" -c 'import struct, sys; sys.exit(not ((3,10) <= sys.version_info[:2] <= (3,13) and struct.calcsize("P") == 8))' >/dev/null 2>&1
}

find_python() {
    for candidate in "${MELEE_PYTHON-}" python3.13 python3.12 python3.11 python3.10 python3 \
        /opt/homebrew/bin/python3.13 /usr/local/bin/python3.13 \
        /Library/Frameworks/Python.framework/Versions/3.13/bin/python3.13; do
        if [ -n "$candidate" ] && compatible "$candidate"; then
            python=$(command -v "$candidate")
            return 0
        fi
    done
    return 1
}

as_admin() {
    if [ "$(id -u)" -eq 0 ]; then
        "$@"
    elif command -v sudo >/dev/null 2>&1; then
        sudo "$@"
    else
        printf '%s\n' 'Installing Python needs administrator access. Ask your administrator, then rerun setup.' >&2
        exit 1
    fi
}

install_python() {
    if [ "$platform" = mac ]; then
        brew_cmd=$(command -v brew || true)
        if [ -z "$brew_cmd" ]; then
            for candidate in /opt/homebrew/bin/brew /usr/local/bin/brew; do
                if [ -x "$candidate" ]; then brew_cmd=$candidate; break; fi
            done
        fi
        if [ -z "$brew_cmd" ]; then
            printf '%s\n' 'Install 64-bit Python 3.13 from https://www.python.org/downloads/macos/' \
                'or install Homebrew from https://brew.sh and rerun setup. See README.md.' >&2
            exit 1
        fi
        "$brew_cmd" install python@3.13
        python="$("$brew_cmd" --prefix python@3.13)/bin/python3.13"
    elif command -v apt-get >/dev/null 2>&1; then
        as_admin apt-get update
        # Do not replace the system Python or add third-party repositories.
        version=
        for candidate in 3.13 3.12 3.11 3.10; do
            if apt-cache show "python$candidate-venv" >/dev/null 2>&1; then
                version=$candidate
                break
            fi
        done
        if [ -z "$version" ]; then
            printf '%s\n' 'Your configured repositories have no supported Python 3.10-3.13 with venv.' \
                'Install a compatible 64-bit Python yourself, then rerun setup. See README.md.' >&2
            exit 1
        fi
        as_admin apt-get install -y "python$version" "python$version-venv"
        python=$(command -v "python$version")
    elif command -v dnf >/dev/null 2>&1; then
        as_admin dnf install -y python3.13
        python=$(command -v python3.13)
    else
        printf '%s\n' 'Automatic Python installation supports Homebrew, apt and dnf.' \
            'Install 64-bit Python 3.10-3.13 including venv/ensurepip with your distribution tools, then rerun setup.' >&2
        exit 1
    fi
}

if [ -e .venv ] || [ -L .venv ]; then
    if ! compatible "$repo/.venv/bin/python"; then
        printf '%s\n' 'The existing .venv is incompatible, incomplete or from another OS. Rename it and rerun setup.' >&2
        exit 1
    fi
    python="$repo/.venv/bin/python"
elif [ "$mode" = open ]; then
    printf '%s\n' 'Run your platform setup launcher first to create .venv and prepare the player.' >&2
    exit 1
elif ! find_python; then
    printf '%s\n' 'A compatible Python was not found; installing Python using the available package manager.'
    install_python
fi

if ! compatible "$python"; then
    printf '%s\n' 'Setup requires 64-bit Python 3.10-3.13. See README.md.' >&2
    exit 1
fi

# Debian/Ubuntu split ensurepip into a separate package, even when Python exists.
# Extract-only stays standard-library-only and never installs NumPy/Pillow.
extract_only=false
for argument in "$@"; do
    if [ "$argument" = --extract-only ]; then extract_only=true; fi
done
if [ "$mode" = import ] && [ "$extract_only" = false ] && ! "$python" -c 'import venv, ensurepip' >/dev/null 2>&1; then
    version=$("$python" -c 'import sys; print("%s.%s" % sys.version_info[:2])')
    if [ "$platform" = linux ] && command -v apt-get >/dev/null 2>&1; then
        as_admin apt-get update
        as_admin apt-get install -y "python$version-venv"
    else
        printf '%s\n' 'This Python lacks venv/ensurepip. Install those modules for this interpreter and rerun setup.' >&2
        exit 1
    fi
fi
exec "$python" -m tools.melee_anim.launcher "$mode" "$@"
