from io import BytesIO
import json
from pathlib import Path
import shutil
import unittest
from unittest.mock import Mock, patch
from urllib.error import URLError
import uuid

from tools.melee_anim import launcher


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.build = Path('build/melee_anim_tests').resolve()
        self.repo = self.build/f'launcher space {uuid.uuid4().hex}'
        self.repo.mkdir(parents=True)
        self.iso = self.repo/'my game.iso'
        self.iso.write_bytes(b'synthetic placeholder, not game assets')

    def tearDown(self):
        target = self.repo.resolve()
        if not target.is_relative_to(self.build) or not target.name.startswith('launcher space '):
            raise RuntimeError('Unexpected cleanup path')
        shutil.rmtree(target)

    def prepare_ui(self):
        root = self.repo/'build/melee_anim/preview'
        root.mkdir(parents=True)
        (root/'player.html').write_text('synthetic')
        (root.parent/'motions.json').write_text('{}')
        return root

    def test_import_checks_iso_before_packages_and_stops_on_failure(self):
        with patch.object(launcher, 'run_step', side_effect=RuntimeError('incompatible image')) as run, patch.object(launcher, 'environment_python') as environment:
            with self.assertRaisesRegex(RuntimeError, 'incompatible'):
                launcher.import_iso(self.repo, self.iso)
            self.assertEqual(run.call_count, 1)
            self.assertEqual(run.call_args.args[0][-1], str(self.iso))
            environment.assert_not_called()
        with patch.object(launcher, 'run_step') as run, patch.object(launcher, 'environment_python') as environment:
            with self.assertRaisesRegex(ValueError, 'ISO not found'):
                launcher.import_iso(self.repo, self.repo/'missing.iso')
            run.assert_not_called(); environment.assert_not_called()

    def test_import_runs_existing_pipeline_in_order_and_extract_only_never_installs(self):
        with patch.object(launcher, 'run_step') as run, patch.object(launcher, 'environment_python', return_value='venv python'):
            launcher.import_iso(self.repo, self.iso, jobs=3)
            commands = [call.args[0] for call in run.call_args_list]
            self.assertEqual([c[2].rsplit('.', 1)[-1] for c in commands],
                             ['extract_iso', 'inspect_motions', 'inspect_models', 'catalog', 'roster_batch',
                              'attacks', 'cycles', 'sync_claps', 'retarget', 'preview_gallery', 'verify_previews'])
            self.assertTrue(all(call.args[1] == self.repo for call in run.call_args_list))
            self.assertEqual(commands[0][-1], str(self.iso)); self.assertEqual(commands[1][0], 'venv python')
            self.assertIn('--resume', commands[4]); self.assertEqual(commands[4][-1], '3')
            self.assertIn('--resume', commands[7]); self.assertIn('--require-all', commands[9])
        with patch.object(launcher, 'run_step') as run, patch.object(launcher, 'environment_python') as environment:
            launcher.import_iso(self.repo, self.iso, extract_only=True)
            self.assertEqual(run.call_count, 1); environment.assert_not_called()

    def test_environment_reuses_ready_packages_and_installs_only_locally(self):
        with patch.object(launcher.sys, 'prefix', str(self.repo/'.venv')), patch.object(launcher, 'packages_ready', return_value=True), patch.object(launcher, 'run_step') as run:
            self.assertEqual(launcher.environment_python(self.repo), launcher.sys.executable)
            run.assert_not_called()
        with patch.object(launcher, 'packages_ready', return_value=False), patch.object(launcher, 'run_step') as run:
            executable = launcher.environment_python(self.repo)
            self.assertEqual(executable, str(launcher.venv_python(self.repo)))
            create, install = [call.args[0] for call in run.call_args_list]
            self.assertEqual(create[-1], str(self.repo/'.venv'))
            self.assertEqual(install[:4], [executable, '-m', 'pip', 'install'])
            self.assertIn('--only-binary=:all:', install)
            self.assertEqual(install[-1], str(self.repo/'tools/melee_anim/requirements.txt'))

    def test_global_packages_still_create_a_local_environment(self):
        with patch.object(launcher, 'packages_ready', return_value=True), patch.object(launcher, 'run_step') as run:
            self.assertEqual(launcher.environment_python(self.repo), str(launcher.venv_python(self.repo)))
            self.assertEqual(run.call_count, 2)

    def test_supported_platforms_and_posix_venv(self):
        for platform in ('win32', 'darwin', 'linux'):
            with self.subTest(platform=platform), patch.object(launcher.sys, 'platform', platform):
                launcher.check_python()
                suffix = '.venv/Scripts/python.exe' if platform == 'win32' else '.venv/bin/python'
                self.assertEqual(launcher.venv_python(self.repo), self.repo/suffix)
                with patch.object(launcher, 'run_step') as run:
                    self.assertEqual(launcher.environment_python(self.repo), str(self.repo/suffix))
                    self.assertEqual(run.call_args.args[0][0], str(self.repo/suffix))
        with patch.object(launcher.sys, 'platform', 'unsupported'):
            with self.assertRaisesRegex(ValueError, 'support Windows, macOS and Linux'):
                launcher.check_python()
        for version, bits in [((3, 9), 8), ((3, 14), 8), ((3, 13), 4)]:
            with patch.object(launcher.sys, 'version_info', version), patch.object(launcher.struct, 'calcsize', return_value=bits):
                with self.assertRaisesRegex(ValueError, '64-bit Python'):
                    launcher.check_python()

    def test_foreign_or_incomplete_venv_fails_before_installing(self):
        (self.repo/'.venv').mkdir()
        with patch.object(launcher, 'run_step') as run:
            with self.assertRaisesRegex(ValueError, 'another OS'):
                launcher.environment_python(self.repo)
            run.assert_not_called()

    def test_server_identity_and_repository_check(self):
        root = self.repo/'build/melee_anim/preview'
        def response(service='melee-animation-downloads', path=None):
            return BytesIO(json.dumps({'service': service, 'root': str(root) if path is None else path}).encode())
        with patch.object(launcher, 'urlopen', return_value=response()):
            self.assertTrue(launcher.server_status(8765, root))
        with patch.object(launcher, 'urlopen', side_effect=URLError('not running')):
            self.assertFalse(launcher.server_status(8765, root))
        for data in (response(service='other'), response(path=str(self.repo/'other')), BytesIO(b'not json'), BytesIO(b'[]')):
            with patch.object(launcher, 'urlopen', return_value=data):
                with self.assertRaises(ValueError):
                    launcher.server_status(8765, root)

    def test_open_reuses_server_without_installing_or_spawning(self):
        root = self.prepare_ui()
        stat = (root/'player.html').stat()
        expected = f'http://127.0.0.1:8766/player.html?v={stat.st_mtime_ns:x}-{stat.st_size:x}'
        with patch.object(launcher, 'server_status', return_value=True), patch.object(launcher.subprocess, 'Popen') as spawn, patch.object(launcher.webbrowser, 'open') as browser:
            self.assertEqual(launcher.open_ui(self.repo, 'python', port=8766), expected)
            browser.assert_called_once_with(expected); spawn.assert_not_called()
            self.assertEqual(launcher.open_ui(self.repo, 'python', port=8766, browser=False), expected)
            self.assertEqual(browser.call_count, 1)

    def test_rebuilt_player_opens_a_new_url_without_restarting_server(self):
        root = self.prepare_ui()
        with patch.object(launcher, 'server_status', return_value=True), patch.object(launcher.subprocess, 'Popen') as spawn, patch.object(launcher.webbrowser, 'open') as browser:
            original = launcher.open_ui(self.repo, 'python')
            (root/'player.html').write_text('updated controls')
            updated = launcher.open_ui(self.repo, 'python')
            self.assertNotEqual(original, updated)
            self.assertEqual(browser.call_args.args, (updated,))
            spawn.assert_not_called()

    def test_open_starts_hidden_child_with_spaced_paths_and_reports_failed_start(self):
        root = self.prepare_ui()
        child = Mock(pid=123)
        child.poll.return_value = None
        with patch.object(launcher, 'server_status', side_effect=[False, False, True]), patch.object(launcher.subprocess, 'Popen', return_value=child) as spawn, patch.object(launcher.time, 'sleep'), patch.object(launcher.webbrowser, 'open'):
            launcher.open_ui(self.repo, 'python with spaces', browser=False)
            args, kwargs = spawn.call_args
            self.assertEqual(args[0][0], 'python with spaces'); self.assertIn(str(root), args[0])
            self.assertEqual(kwargs['cwd'], self.repo); self.assertEqual(kwargs['stdin'], launcher.subprocess.DEVNULL)
            if launcher.os.name == 'nt':
                self.assertEqual(kwargs['creationflags'], launcher.subprocess.CREATE_NO_WINDOW)
            self.assertEqual(kwargs['start_new_session'], launcher.os.name != 'nt')
            child.terminate.assert_not_called()
        child.poll.return_value = 1
        with patch.object(launcher, 'server_status', return_value=False), patch.object(launcher.subprocess, 'Popen', return_value=child), patch.object(launcher.webbrowser, 'open') as browser:
            with self.assertRaisesRegex(RuntimeError, 'Player did not start'):
                launcher.open_ui(self.repo, 'python')
            browser.assert_not_called()

    def test_unprepared_ui_fails_without_spawning(self):
        with patch.object(launcher.subprocess, 'Popen') as spawn:
            with self.assertRaisesRegex(ValueError, 'not prepared'):
                launcher.open_ui(self.repo, 'python')
            spawn.assert_not_called()
