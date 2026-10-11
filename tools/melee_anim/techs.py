"""Ground recovery identities from ftCo_Submotion, not motion-state guesses."""

TECH_LABELS = {
    'Passive': ('Tech in place', 'tech'),
    'PassiveStandF': ('Tech roll towards (forward)', 'tech'),
    'PassiveStandB': ('Tech roll away (backward)', 'tech'),
    'DownBoundU': ('Missed tech — face up', 'missed'),
    'DownBoundD': ('Missed tech — face down', 'missed'),
    'DownWaitU': ('Lying on ground — face up', None),
    'DownWaitD': ('Lying on ground — face down', None),
}


def tech_label(name):
    return TECH_LABELS.get(name)


def ground_effect(action):
    """Common ordinary animation IDs verified against ftCommon/forward.h."""
    return {183: 'missed', 191: 'missed', 199: 'tech', 200: 'tech', 201: 'tech'}.get(
        int(action.removeprefix('tech-').removesuffix('_source').removesuffix('-combined'))) if action.startswith('tech-') else None
