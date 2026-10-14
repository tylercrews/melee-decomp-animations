#!/bin/sh
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd) || exit 1
/bin/sh "$script_dir/tools/melee_anim/setup_unix.sh" mac import "$@"
status=$?
if [ -t 0 ]; then
    printf '\nPress Return to close this window... '
    read -r answer
fi
exit "$status"
