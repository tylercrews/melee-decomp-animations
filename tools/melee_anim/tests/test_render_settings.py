import unittest
from tools.melee_anim.render_settings import native_size


class RenderSettingsTests(unittest.TestCase):
    def test_results_use_1024_and_other_types_keep_512(self):
        for action in ('victory1','victory3_wait','results-clap','results-clap_source','taunt','taunt_source'):
            self.assertEqual(native_size(action),1024)
        self.assertEqual(native_size('other-274_source','taunt'),1024)
        for action in ('attack-62_source','tech-199_source','movement-fullhop_source','other-3_source'):
            self.assertEqual(native_size(action),512)
        self.assertEqual(native_size('other-3_source','hit'),512)


if __name__=='__main__':unittest.main()
