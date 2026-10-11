"""Finite source-clip sequences, with explicit loop/release/landing presets.

Do not infer an entire controller from numbered clips or duplicate DAT names.
Original phases remain selectable; combined entries are additional presets.
"""
from copy import deepcopy
import math
from pathlib import Path
import re

from .inspect_motions import read_exact_motion
from .motions import read_figatree


def combined_actions(actions, kind):
    available = [a for a in actions if a['available']]
    names = {}
    for action in available:
        names.setdefault(action['name'], []).append(action)
    recipes = []
    # Unambiguous startup/loop/ending families only. Duplicate packed symbols
    # (charge levels, alternate endings, copy rigs) need an explicit recipe.
    for name, matches in names.items():
        if len(matches) != 1 or not name.endswith('Start'):
            continue
        stem = name[:-5]
        if stem != 'Attack100' and not re.fullmatch(r'(?:[A-Z][a-z])?Special(?:Air)?(?:N|S|Hi|Lw)', stem):
            continue
        # Hold is used by Ness; Bowser's breath and Fox's side-special travel
        # use the unsuffixed stem for the middle phase.
        middles = [candidate for candidate in (stem+'Loop', stem+'Hold', stem) if len(names.get(candidate, [])) == 1]
        if len(middles) == 1 and len(names.get(stem+'End', [])) == 1:
            phases = [names[stem+'Start'][0], names[middles[0]][0], names[stem+'End'][0]]
            if all(a['animation_type'] == 'attack' for a in phases):
                title = phases[0]['label'].rsplit(' — ', 1)[0]
                recipes.append((phases, title+' — combined', 'Startup → one middle cycle → ending.'))
    if kind == 4:
        # Ground startup becomes airborne phase 2; ground contact enters Hi4.
        # The arc is authored in TransN. Descent uses one source cycle before
        # the flat-plane landing preset, not a guessed jump velocity.
        for first, title in [('SpecialHi1', 'Up special — grounded'), ('SpecialAirHi1', 'Up special — aerial')]:
            selected = [first, 'SpecialAirHi2', 'SpecialAirHi3', 'SpecialHi4']
            if all(len(names.get(n, [])) == 1 for n in selected):
                recipes.append(([names[n][0] for n in selected], title+' — combined',
                                'Startup → rise/fall → one descent cycle → landing; neutral flat-plane preset.'))
    for bound, wait in [('DownBoundU', 'DownWaitU'), ('DownBoundD', 'DownWaitD')]:
        if len(names.get(bound, [])) == len(names.get(wait, [])) == 1:
            phases = [names[bound][0], names[wait][0]]
            recipes.append((phases, phases[0]['label']+' → lying on ground',
                            'Missed tech → one authored lying cycle; impact occurs once at the start.'))
    result = []
    for phases, title, policy in recipes:
        first = phases[0]
        actors = []
        for original in first['actors']:
            actor = deepcopy(original)
            sequence = []
            for phase in phases:
                member = next(a for a in phase['actors'] if a['fighter_kind'] == original['fighter_kind'])
                sequence.append({'name': phase['name'], 'animation_file': member['animation_file'],
                                 'clip': deepcopy(member['clip']), 'character_prop': deepcopy(member.get('character_prop')),
                                 'duration_ticks': member['clip']['frames']})
            actor['sequence'] = {'phases': sequence, 'policy': policy}
            actor['clip']['effective_loop'] = False
            actor['character_prop'] = None
            actor['render_duration'] = sum(p['duration_ticks'] for p in sequence)
            actors.append(actor)
        duration = max(a['render_duration'] for a in actors)
        for actor in actors:
            actor['render_duration'] = duration
        props = [p['character_prop'] for p in actors[0]['sequence']['phases'] if p['character_prop']]
        result.append({**first, 'key': first['key'].replace('_source', '-combined_source'),
                       'label': title, 'actors': actors, 'duration_ticks': duration,
                       'held_item': props[0] if props else None,
                       'sequence': {'phases': [p['name'] for p in actors[0]['sequence']['phases']], 'policy': policy}})
    return result


def prop_archives(actor):
    props = [actor.get('character_prop')]
    props.extend(p.get('character_prop') for p in actor.get('sequence', {}).get('phases', []))
    return {p['source_archive'] for p in props if p}


class SequenceScene:
    def __init__(self, actor, files, remap=None):
        self.description = actor['sequence']
        self.phases = []
        self.starts = []
        self.duration = 0.
        blobs = {}
        for phase in self.description['phases']:
            filename = phase['animation_file']
            if filename not in blobs:
                blobs[filename] = (Path(files)/filename).read_bytes()
            motion = phase['clip']
            meta, tracks = read_figatree(read_exact_motion(blobs[filename], motion, filename), motion['symbol'])
            if remap:
                tracks = remap(tracks, meta['node_count'])
            duration = phase['duration_ticks']
            if not math.isfinite(duration) or duration <= 0 or meta['frames'] <= 0:
                raise ValueError('Sequence phases require finite positive durations')
            self.starts.append(self.duration)
            self.phases.append((meta, tracks, phase))
            self.duration += duration

    def sample(self, tick):
        if not math.isfinite(tick) or tick < 0:
            raise ValueError('Sequence time must be finite and nonnegative')
        # Half-open phases: a boundary samples the next clip at zero. The
        # terminal sample holds the last pose; it never wraps the whole move.
        index = next((i for i in range(len(self.starts)-1, -1, -1) if tick >= self.starts[i]), 0)
        meta, tracks, phase = self.phases[index]
        elapsed = min(tick-self.starts[index], phase['duration_ticks'])
        time = elapsed % meta['frames'] if phase['clip'].get('effective_loop') and elapsed < phase['duration_ticks'] else min(elapsed, meta['frames'])
        return meta, tracks, time, index, elapsed

    def provenance(self):
        return {'policy': self.description['policy'], 'duration_ticks': self.duration,
                'phases': [{'name': p['name'], 'symbol': p['clip']['symbol'],
                            'animation_file': p['animation_file'], 'start_tick': start,
                            'duration_ticks': p['duration_ticks']}
                           for start, (_, _, p) in zip(self.starts, self.phases)],
                'limitations': ['Finite preset; release/input/ground-contact decisions are prescribed',
                                'Original curves without transition blending; no complete gameplay controller']}


class SequenceProps:
    """Fixed mesh ranges with phase-local scripts and a shared Cutter clock."""
    def __init__(self, scene, files, table, model, repo, matrices_at):
        from .held_items import HeldItem, hold_joint
        self.scene = scene
        self.entries = []
        self.meshes = []
        self.release_meshes = []
        self.materials = []
        self.textures = {}
        from .held_items import script_events
        cutter_expire = next((scene.starts[i]+tick for i,(_,_,phase) in enumerate(scene.phases)
                              for tick,command in script_events(phase['clip'].get('script',{}),phase['duration_ticks'])
                              if command.get('command_variable') == {'index':2,'value':1}
                              and (phase.get('character_prop') or {}).get('behavior') == 'cutter'), None)
        for i, (_, _, phase) in enumerate(scene.phases):
            spec = phase.get('character_prop')
            if not spec:
                continue
            spec = dict(spec)
            if spec.get('behavior') == 'cutter':
                spec['phase_offset'] = scene.starts[i]
                spec['cutter_expire_tick'] = cutter_expire
            item = HeldItem(files, spec, phase['duration_ticks'], phase['clip'].get('script'))
            joint = hold_joint(files, table, model, repo, spec)
            item.anchor_at = lambda tick, start=scene.starts[i], j=joint: matrices_at(start+tick)[j]
            offset = len(self.materials)
            for mesh in item.model['meshes']:
                mesh['material_index'] += offset
            self.materials.extend(item.model['materials'])
            self.textures.update(item.textures)
            self.meshes.extend(item.model['meshes'])
            self.release_meshes.extend([spec.get('behavior') == 'needle-release']*len(item.model['meshes']))
            self.entries.append((i, joint, item))

    def pose(self, matrices, tick, view):
        _, _, _, phase, elapsed = self.scene.sample(tick)
        geometry, mask = [], []
        for index, joint, item in self.entries:
            extra, shown = item.pose(matrices[joint], elapsed if index == phase else 0., view)
            geometry.extend(extra)
            mask.extend(shown if index == phase else [False]*len(shown))
        return geometry, mask

    def emission_geometry(self, view):
        cloud = []
        for _, _, item in self.entries:
            if item.specification.get('behavior') == 'needle-release':
                tick = item.specification['shot_ticks'][0]
                geometry, mask = item.pose(item.anchor_at(tick), tick, view)
                cloud.extend(p for (p, _), shown in zip(geometry, mask) if shown)
        return cloud

    def provenance(self):
        return [{'phase': self.scene.phases[i][2]['name'], 'fighter_hold_joint': joint,
                 **item.provenance()} for i, joint, item in self.entries]


def phase_drawables(model, phase):
    from .roster import visible_drawables
    states = model.get('visibility', {}).get('defaults')
    if states is not None:
        states = states.copy()
        for command in phase['clip'].get('script', {}).get('commands', []):
            if command['opcode'] in (1, 2):
                break
            if 'visibility_group' in command:
                i = command['visibility_group']
                if 0 <= i < len(states):
                    states[i] = command['visibility_value']
    return visible_drawables(model, states)
