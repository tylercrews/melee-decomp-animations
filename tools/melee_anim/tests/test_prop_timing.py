import struct
import unittest
from tools.melee_anim.hsd import Archive
from tools.melee_anim.prop_timing import item_script_events, fighter_prop_visibility, blaster_slide
from tools.melee_anim.character_props import character_prop, resolve_profile
from tools.melee_anim.movement import movement_visibility_timeline
from tools.melee_anim.sequences import sequence_visibility


def var(tick,index,value):
    return tick,{'command_variable':{'index':index,'value':value}}


def visible(events,tick):
    return next(value for time,value in reversed(events) if time<=tick)


class PropTimingTests(unittest.TestCase):
    def test_both_blaster_holster_values_and_correct_phase_animation(self):
        for kind,hide in ((1,2),(22,0)):
            report={'normal_tables':[dict(fighter_kind=kind,fighter_archive='synthetic',fighter_root='root')]}
            for air in (False,True):
                for phase,aid in [('Start',0),('Loop',1),('End',2)]:
                    spec=resolve_profile(None,report,character_prop(kind,'Special'+('Air' if air else '')+'N'+phase))
                    self.assertEqual(spec['animation_id'],aid+(3 if air else 0))
                    events=fighter_prop_visibility(spec,24,[var(15,1,hide)])
                    self.assertTrue(visible(events,14.99))
                    self.assertEqual(visible(events,15),phase!='End')
                    if phase!='End':self.assertTrue(visible(events,24))

    def test_milk_source_attachment_and_spawn_local_clock_boundaries(self):
        spec=character_prop(20,'AppealR')
        self.assertEqual((spec['article_slot'],spec['canonical_part']),(5,31))
        events=fighter_prop_visibility(spec,200,[var(13,1,1),var(193,1,2)])
        self.assertEqual([visible(events,t) for t in (0,12.99,13,192.99,193,200)],
                         [False,False,True,True,False,False])
        self.assertIsNone(character_prop(6,'AppealR'))
        self.assertIsNone(character_prop(24,'AppealR'))

    def test_item_commands_have_separate_namespace_and_skip_multword_hitboxes(self):
        data=struct.pack('>13I',17<<26|1,2<<26|4,11<<26,*([0]*6),17<<26,18<<26|7,19<<26|9,0)
        ar=Archive.__new__(Archive);ar.data=memoryview(data);ar.data_size=len(data);ar.label='synthetic'
        self.assertEqual(item_script_events(ar,0,20),[(0,0,1),(4,0,0),(4,1,7),(4,2,9)])
        self.assertEqual(item_script_events(ar,0,3),[(0,0,1)])

    def test_toad_torch_parachute_and_retained_common_items(self):
        for spec,duration,checks in [
            ({'behavior':'toad','animation_id':0},70,[(6.99,False),(7,True),(52.99,True),(53,False)]),
            ({'behavior':'game-watch','phase':62},45,[(2.99,False),(3,True),(44.99,True),(45,False)]),
            ({'behavior':'game-watch','phase':68},45,[(29.99,True),(30,False)]),
            ({'item_kind':11},50,[(0,True),(50,True)]),
            ({'behavior':'cape'},36,[(0,True),(6,True),(34,True),(36,False)]),
        ]:
            events=fighter_prop_visibility(spec,duration,[var(6,1,1),var(34,1,0)])
            for tick,want in checks:self.assertEqual(visible(events,tick),want)

    def test_blaster_uses_original_open_and_close_slide_positions(self):
        self.assertEqual(blaster_slide('SpecialNStart',[],0),-.425)
        opening=[var(2,3,1)]
        self.assertEqual([blaster_slide('SpecialNLoop',opening,t) for t in (1,2,3,4,5,10)],
                         [-.425,-.595,-.765,-.935,-.85,-.85])
        self.assertEqual([blaster_slide('SpecialNEnd',[var(2,3,2)],t) for t in (0,2,3,4,5)],
                         [-.85,-.935,-.765,-.595,-.425])

    def test_animation_wrap_wait_does_not_spin_zero_time_goto(self):
        from tools.melee_anim.held_items import script_events
        script={'commands':[dict(offset=0,opcode=31,first_word=hex(31<<26),visibility_group=0,visibility_value=1),
                            dict(offset=4,opcode=8,first_word=hex(8<<26)),
                            dict(offset=8,opcode=7,first_word=hex(7<<26),target=0)]}
        self.assertEqual([tick for tick,_ in script_events(script,20)],[0])

    def test_companion_own_initial_script_and_late_phase_commands(self):
        model={'visibility':{'defaults':[0,0]}}
        def command(offset,op,**kw):return dict(offset=offset,opcode=op,first_word=hex(op<<26),**kw)
        motion={'frames':30,'script':{'commands':[command(0,31,visibility_group=1,visibility_value=-1),
                  command(4,2,timer_ticks=10),command(8,31,visibility_group=1,visibility_value=0),command(12,0)]}}
        self.assertEqual(movement_visibility_timeline(model,motion),[(0,[0,0]),(0,[0,-1]),(10,[0,0])])
        from types import SimpleNamespace
        scene=SimpleNamespace(phases=[({},[],{'name':'SpecialNStart','clip':motion,'character_prop':{'behavior':'bow'}}),
                                     ({},[],{'name':'SpecialNLoop','clip':{'frames':5},'character_prop':{'behavior':'bow'}})])
        self.assertEqual(sequence_visibility(model,scene)[1],[(0,[0,0])])
        motion['frames']=5
        # Events after a source phase's boundary are not carried forward.
        self.assertEqual(sequence_visibility(model,scene)[1],[(0,[0,-1])])


if __name__=='__main__':unittest.main()
