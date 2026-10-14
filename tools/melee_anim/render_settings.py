"""Native master resolution shared by previews, caches and exports."""
import sys

MASTER_SIZE = 512
RESULTS_SIZE = 1024


def default_backend():
    """The memory-bitmap OpenGL context is Win32-only; Python is portable."""
    return 'native' if sys.platform == 'win32' else 'python'


def native_size(action,animation_type=None):
    if animation_type in ('victory','clapping','taunt') or action.startswith(('victory','results-clap')) or action in ('taunt','taunt_source'):
        return RESULTS_SIZE
    return MASTER_SIZE
