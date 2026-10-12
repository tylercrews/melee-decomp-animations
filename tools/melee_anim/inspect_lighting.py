"""Compare extracted stage light descriptors with the results/default rigs.

Stage groups are raw descriptors, not a simulation of stage callbacks,
overrides or animated light state. See Ground_801C466C/801C20E0.
"""
import argparse
import json
from pathlib import Path
import struct

from .hsd import Archive, Dol, FormatError, load_symbols
from .inspect_results_scene import pointer_list, vector
from .lighting import results_lighting


def stage_light_groups(path):
    ar = Archive(Path(path).read_bytes(), str(path))
    head = ar.public('map_head')
    objects, count = ar.pointer(head+8), ar.u32(head+12)
    ar.read(objects, count*0x34)
    groups = []
    for index in range(count):
        at = ar.pointer(objects+index*0x34+0x18)
        if at is None:continue
        lights = []
        for entry in pointer_list(ar, at):
            desc, seen = ar.pointer(entry), set()
            while desc is not None:
                if desc in seen:raise FormatError('Cycle in stage light descriptors')
                seen.add(desc)
                position, interest = ar.pointer(desc+16), ar.pointer(desc+20)
                lights.append({'descriptor_offset':desc, 'flags':ar.u16(desc+8),
                               'rgba':list(ar.read(desc+12, 4)),
                               'position':vector(ar, position+4) if position is not None else None,
                               'interest':vector(ar, interest+4) if interest is not None else None,
                               'animation_count':len(pointer_list(ar, ar.pointer(entry+4)))})
                desc = ar.pointer(desc+4)
        groups.append({'object_index':index, 'lights':lights})
    return {'archive':Path(path).name, 'raw_light_groups':groups,
            'limitations':['Fighter selection is controlled by source stage callbacks',
                           'Ground light overrides, animation and stage scaling are not evaluated']}


def gameplay_default(repo):
    repo = Path(repo)
    dol = Dol((repo/'orig/GALE01/sys/main.dol').read_bytes())
    symbols = load_symbols(repo/'config/GALE01/symbols.txt')
    base = symbols['Ground_803E06C8'][0]
    lights = []
    for index in range(9):
        entry = dol.u32(base+index*4)
        if not entry:break
        desc = dol.u32(entry)
        flags = struct.unpack('>H', dol.read(desc+8, 2))[0]
        pos = dol.u32(desc+16)
        lights.append({'flags':flags, 'rgba':list(dol.read(desc+12, 4)),
                       'position':list(struct.unpack('>3f', dol.read(pos+4, 12))) if pos else None})
    else:raise FormatError('Gameplay default light list is unterminated')
    return {'source':'Ground_803E06C8 in original DOL', 'lights':lights}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--files', type=Path, default=Path('orig/GALE01/files'))
    parser.add_argument('--stage', action='append', help='extracted stage filename; repeat for multiple archives')
    parser.add_argument('--output', type=Path, default=Path('build/melee_anim/lighting-comparison.json'))
    args = parser.parse_args()
    stages = [stage_light_groups(args.files/name) for name in (args.stage or ['GrNBa.dat','GrNLa.dat','GrIz.dat'])]
    result = {'results':results_lighting(args.files), 'gameplay_default':gameplay_default(Path.cwd()), 'stages':stages}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print('Results:',result['results']['lights'])
    print('Gameplay default:',result['gameplay_default']['lights'])
    for stage in stages:print(stage['archive'],len(stage['raw_light_groups']),'raw light groups')
    print('Report:',args.output)


if __name__=='__main__':main()
