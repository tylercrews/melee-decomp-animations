"""Synthetic phase-boundary/preset checks; original game bytes stay local."""
from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch

from tools.melee_anim.sequences import combined_actions, prop_archives, SequenceScene, SequenceProps
from tools.melee_anim.techs import ground_effect


def action(name, aid, duration=6, kind=1, category='attack', prop=None):
    clip=dict(frames=duration, effective_loop=name.endswith('Loop') or name.startswith('DownWait'),
              symbol=name, offset=0, size=1)
    return dict(name=name, key=f'{category}-{aid}_source', animation_id=aid,
                label='Neutral special — grounded — '+name, available=True, animation_type=category,
                ground_effect='missed' if name.startswith('DownBound') else None,
                actors=[dict(fighter_kind=kind, animation_file='synthetic.dat', clip=clip, character_prop=prop)])


class SequenceTests(unittest.TestCase):
    def test_combined_keeps_individuals_and_finite_duration(self):
        phases=[action('SpecialN'+p, i, n) for p,i,n in [('Start',295,7),('Loop',296,10),('End',297,24)]]
        before=deepcopy(phases)
        combined=combined_actions(phases,1)[0]
        self.assertEqual(phases,before)
        self.assertEqual(combined['key'],'attack-295-combined_source')
        self.assertEqual(combined['duration_ticks'],41)
        self.assertFalse(combined['actors'][0]['clip']['effective_loop'])
        self.assertTrue(combined['actors'][0]['sequence']['phases'][1]['clip']['effective_loop'])

    def test_ambiguous_names_and_missing_middle_are_not_inferred(self):
        phases=[action('SpecialN'+p,i) for i,p in enumerate(['Start','Loop','End','End'])]
        self.assertEqual(combined_actions(phases,18),[])
        self.assertEqual(combined_actions([phases[0],phases[2]],18),[])
        self.assertEqual(combined_actions([action('FuraSleep'+p,i) for i,p in enumerate(['Start','Loop','End'])],1),[])

    def test_kirby_ground_start_uses_air_arc_then_ground_landing(self):
        phases=[action(n,i,kind=4) for i,n in enumerate(['SpecialHi1','SpecialAirHi1','SpecialAirHi2','SpecialAirHi3','SpecialHi4'])]
        combined=combined_actions(phases,4)
        self.assertEqual(len(combined),2)
        self.assertEqual(combined[0]['sequence']['phases'],['SpecialHi1','SpecialAirHi2','SpecialAirHi3','SpecialHi4'])

    def test_missed_tech_face_mapping_and_single_impact(self):
        phases=[action(n,i,kind=0,category='tech') for n,i in [('DownBoundU',183),('DownWaitU',184),('DownBoundD',191),('DownWaitD',192)]]
        combined=combined_actions(phases,0)
        self.assertEqual([a['sequence']['phases'] for a in combined],[['DownBoundU','DownWaitU'],['DownBoundD','DownWaitD']])
        self.assertEqual(ground_effect('tech-183-combined_source'),'missed')
        self.assertEqual(ground_effect('tech-184_source'),None)
        self.assertTrue(all(not a['actors'][0]['clip']['effective_loop'] for a in combined))

    def test_half_open_boundaries_phase_time_and_terminal_hold(self):
        phases=[action('SpecialN'+p,i,n) for i,(p,n) in enumerate([('Start',7),('Loop',10),('End',24)])]
        actor=combined_actions(phases,1)[0]['actors'][0]
        metas=[({'frames':p['duration_ticks'],'node_count':1,'type':0},[p['name']]) for p in actor['sequence']['phases']]
        with patch.object(Path,'read_bytes',return_value=b'synthetic'),patch('tools.melee_anim.sequences.read_exact_motion'),patch('tools.melee_anim.sequences.read_figatree',side_effect=metas):
            scene=SequenceScene(actor,Path('.'),lambda tracks,n:tracks+['mapped'])
        self.assertEqual(scene.sample(6.9)[2:4],(6.9,0))
        self.assertEqual(scene.sample(7)[2:4],(0.,1))
        self.assertEqual(scene.sample(17)[2:4],(0.,2))
        self.assertEqual(scene.sample(41)[2:4],(24.,2))
        self.assertEqual(scene.sample(100)[2:4],(24.,2))
        self.assertEqual(scene.sample(8)[1],['SpecialNLoop','mapped'])
        self.assertEqual([p['start_tick'] for p in scene.provenance()['phases']],[0,7,17])
        for value in [-1,float('nan'),float('inf')]:
            with self.assertRaises(ValueError):scene.sample(value)

    def test_cache_dependencies_cover_props_in_later_phases(self):
        phases=[action('SpecialN'+p,i,prop={'source_archive':p+'.dat'}) for i,p in enumerate(['Start','Loop','End'])]
        actor=combined_actions(phases,1)[0]['actors'][0]
        self.assertEqual(prop_archives(actor),{'Start.dat','Loop.dat','End.dat'})

    def test_props_only_show_active_phase_and_use_local_script_time(self):
        phases=[action('SpecialN'+p,i,prop={'source_archive':p+'.dat','behavior':'blaster'}) for i,p in enumerate(['Start','Loop','End'])]
        actor=combined_actions(phases,1)[0]['actors'][0]
        metas=[({'frames':6,'node_count':1,'type':0},[]) for _ in phases]
        with patch.object(Path,'read_bytes',return_value=b'synthetic'),patch('tools.melee_anim.sequences.read_exact_motion'),patch('tools.melee_anim.sequences.read_figatree',side_effect=metas):
            scene=SequenceScene(actor,Path('.'))
        def item(files,spec,duration,script):
            obj=unittest.mock.Mock()
            obj.model={'meshes':[{'material_index':0}],'materials':[{}]}
            obj.textures={};obj.specification=spec
            obj.pose.side_effect=lambda target,tick,view:([(spec['source_archive'],tick)],[True])
            return obj
        with patch('tools.melee_anim.held_items.HeldItem',side_effect=item),patch('tools.melee_anim.held_items.hold_joint',return_value=0):
            props=SequenceProps(scene,Path('.'),{}, {'bones':[{}]},Path('.'),lambda tick:[tick])
        geometry,mask=props.pose([0],7,None)
        self.assertEqual(mask,[False,True,False])
        self.assertEqual(geometry,[('Start.dat',0.),('Loop.dat',1.),('End.dat',0.)])
        self.assertEqual([m['material_index'] for m in props.meshes],[0,1,2])
        # Later-phase command vars on a prop-free move must not assume a prop.
        scene.phases[0][2]['character_prop']=None
        scene.phases[0][2]['clip']['script']={'commands':[dict(opcode=19,offset=1,first_word='0x4E000001',command_variable={'index':2,'value':1})]}
        with patch('tools.melee_anim.held_items.HeldItem',side_effect=item),patch('tools.melee_anim.held_items.hold_joint',return_value=0):
            self.assertEqual(len(SequenceProps(scene,Path('.'),{}, {'bones':[{}]},Path('.'),lambda tick:[tick]).entries),2)


if __name__=='__main__':unittest.main()
