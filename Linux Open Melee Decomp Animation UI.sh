#!/bin/sh
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd) || exit 1
exec /bin/sh "$script_dir/tools/melee_anim/setup_unix.sh" linux open "$@"
