"""Native master resolution shared by previews, caches and exports."""
MASTER_SIZE = 512
RESULTS_SIZE = 1024


def native_size(action,animation_type=None):
    if animation_type in ('victory','clapping','taunt') or action.startswith(('victory','results-clap')) or action in ('taunt','taunt_source'):
        return RESULTS_SIZE
    return MASTER_SIZE
