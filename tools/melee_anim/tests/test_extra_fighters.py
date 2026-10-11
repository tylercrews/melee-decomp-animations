"""Non-playable fighter identities/labels from source, with no game fixtures."""
from pathlib import Path
import unittest
from tools.melee_anim.catalog import CHARACTERS, EXTRA_CHARACTERS, ALL_CHARACTERS
from tools.melee_anim.extra_fighters import hand_submotions, hand_action
from tools.melee_anim.attacks import common_submotions


class ExtraFighterTests(unittest.TestCase):
    def test_nonplayable_external_order_preserves_selectable_indices(self):
        self.assertEqual(len(CHARACTERS),26)
        self.assertEqual(len(EXTRA_CHARACTERS),6)
        self.assertEqual(ALL_CHARACTERS[26][0],'master-hand')
        self.assertEqual(ALL_CHARACTERS[30][0],'crazy-hand')
        self.assertEqual(ALL_CHARACTERS[31][0],'sandbag')
        self.assertEqual(ALL_CHARACTERS[:26],CHARACTERS)

    def test_hands_have_distinct_submotion_tables_not_common_or_state_ids(self):
        repo=Path(__file__).resolve().parents[3]
        common=common_submotions(repo)
        count=next(k for k,v in common.items() if v=='Count')
        master=hand_submotions(repo,27,count);crazy=hand_submotions(repo,28,count)
        self.assertEqual(master[295],'Wait1_0')
        self.assertEqual(master[297],'Entry')
        self.assertEqual(crazy[297],'Slap')
        self.assertEqual(len(master),50);self.assertEqual(len(crazy),49)
        self.assertEqual(hand_action('TagApplaud')[0],'attack')
        self.assertEqual(hand_action('Wait1_0')[0],'movement')
        self.assertEqual(hand_action('Damage2')[0],'other')


if __name__=='__main__':unittest.main()
