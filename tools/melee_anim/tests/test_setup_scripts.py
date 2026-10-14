"""Exercise real shell entry points with fake Python/package managers, never installers."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
import uuid


REPO = Path(__file__).resolve().parents[3]
SHELL = os.environ.get('MELEE_TEST_SHELL') or shutil.which('sh')


@unittest.skipUnless(SHELL, 'POSIX shell required')
class SetupScriptTests(unittest.TestCase):
    def setUp(self):
        self.build = REPO/'build/melee_anim_tests'
        self.repo = self.build/f'setup space {uuid.uuid4().hex}'
        self.bin = self.repo/'fake bin'
        self.bin.mkdir(parents=True)
        (self.repo/'tools/melee_anim').mkdir(parents=True)
        shutil.copyfile(REPO/'tools/melee_anim/setup_unix.sh', self.repo/'tools/melee_anim/setup_unix.sh')
        for name in ('Linux Setup - Import Melee Iso.sh', 'Mac Setup - Import Melee Iso.command',
                     'Linux Open Melee Decomp Animation UI.sh', 'Mac Open Melee Decomp Animation UI.command'):
            shutil.copyfile(REPO/name, self.repo/name)
        self.log = self.repo/'python arguments.log'
        self.admin_log = self.repo/'admin arguments.log'
        self.env = {**os.environ, 'PATH': str(self.bin)+os.pathsep+os.environ['PATH'],
                    'MELEE_TEST_LOG': self.log.as_posix(), 'MELEE_TEST_ADMIN_LOG': self.admin_log.as_posix(),
                    'MELEE_TEST_BIN': self.bin.as_posix(),
                    'MELEE_TEST_INSTALLED': (self.repo/'python installed').as_posix(),
                    'MELEE_TEST_BREW_PREFIX': (self.repo/'brew prefix').as_posix(),
                    'MELEE_TEST_OS': 'Linux', 'MELEE_PYTHON': (self.bin/'chosen-python').as_posix()}
        self.script('uname', 'printf "%s\\n" "$MELEE_TEST_OS"\n')
        self.script('id', 'echo 1000\n')
        self.script('sudo', 'printf "%s\\n" "$@" >> "$MELEE_TEST_ADMIN_LOG"\nexec "$@"\n')
        self.python = '''
if [ "$1" = -c ]; then
    case "$2" in
        *struct*)
            if [ "${MELEE_TEST_NEEDS_INSTALL:-0}" = 1 ] && [ ! -e "$MELEE_TEST_INSTALLED" ]; then exit 1; fi
            exit 0 ;;
        'import venv, ensurepip') exit "${MELEE_TEST_ENSUREPIP_STATUS:-0}" ;;
        *) echo 3.13; exit 0 ;;
    esac
fi
printf '%s\\n' "$PWD" "$@" > "$MELEE_TEST_LOG"
exit "${MELEE_TEST_PYTHON_STATUS:-0}"
'''
        self.script('chosen-python', self.python)

    def tearDown(self):
        target = self.repo.resolve()
        if not target.is_relative_to(self.build.resolve()) or not target.name.startswith('setup space '):
            raise RuntimeError('Unexpected cleanup path')
        shutil.rmtree(target)

    def script(self, name, body, parent=None):
        path = (parent or self.bin)/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('#!/bin/sh\n'+body, encoding='utf-8', newline='\n')
        path.chmod(0o755)
        return path

    def run_script(self, name, *args):
        command = [SHELL, (self.repo/name).as_posix(), *args]
        if self.env.get('MELEE_TEST_ONLY_FAKE_PATH') == '1':
            prefix = '$(cygpath -u "$MELEE_TEST_BIN")' if os.name == 'nt' else '$MELEE_TEST_BIN'
            command = [SHELL, '-c', f'PATH="{prefix}"; export PATH; exec /bin/sh "$@"',
                       'setup-test', (self.repo/name).as_posix(), *args]
        elif os.name == 'nt':
            # Git Bash prepends its own /usr/bin at startup; restore the fake
            # tools ahead of it before invoking the same /bin/sh used on Unix.
            command = [SHELL, '-c', 'PATH="$(cygpath -u "$MELEE_TEST_BIN"):$PATH"; export PATH; exec /bin/sh "$@"',
                       'setup-test', (self.repo/name).as_posix(), *args]
        return subprocess.run(command, env=self.env,
                              cwd=self.build, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=15)

    def require_python_install(self):
        self.env['MELEE_TEST_NEEDS_INSTALL'] = '1'
        self.env['MELEE_TEST_ONLY_FAKE_PATH'] = '1'
        self.script('dirname', 'exec /usr/bin/dirname "$@"\n')
        for name in ('python3.13', 'python3.12', 'python3.11', 'python3.10', 'python3'):
            self.script(name, self.python)

    @unittest.skipIf(sys.platform == 'darwin', 'Common absolute Mac Python paths can bypass fake PATH')
    def test_apt_installs_available_compatible_python_instead_of_system_latest(self):
        self.require_python_install()
        self.script('apt-cache', '[ "$2" = python3.12-venv ]\n')
        self.script('apt-get', 'if [ "$1" = install ]; then : > "$MELEE_TEST_INSTALLED"; fi\n')
        result = self.run_script('Linux Setup - Import Melee Iso.sh')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.admin_log.read_text().splitlines(),
                         ['apt-get', 'update', 'apt-get', 'install', '-y', 'python3.12', 'python3.12-venv'])
        self.assertTrue(self.log.exists())

    @unittest.skipIf(sys.platform == 'darwin', 'Common absolute Mac Python paths can bypass fake PATH')
    def test_dnf_and_homebrew_install_python_and_resume_the_launcher(self):
        self.require_python_install()
        self.script('dnf', ': > "$MELEE_TEST_INSTALLED"\n')
        result = self.run_script('Linux Setup - Import Melee Iso.sh')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.admin_log.read_text().splitlines(), ['dnf', 'install', '-y', 'python3.13'])
        Path(self.env['MELEE_TEST_INSTALLED']).unlink()
        self.env['MELEE_TEST_OS'] = 'Darwin'
        self.script('python3.13', self.python, self.repo/'brew prefix/bin')
        self.script('brew', '''
if [ "$1" = install ]; then
    printf '%s\\n' "$@" >> "$MELEE_TEST_ADMIN_LOG"
    : > "$MELEE_TEST_INSTALLED"
else
    printf '%s\\n' "$MELEE_TEST_BREW_PREFIX"
fi
''')
        result = self.run_script('Mac Setup - Import Melee Iso.command')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.admin_log.read_text().splitlines()[-2:], ['install', 'python@3.13'])
        self.assertTrue(self.log.exists())

    @unittest.skipIf(sys.platform == 'darwin', 'Common absolute Mac Python paths can bypass fake PATH')
    def test_unsupported_package_manager_stops_with_manual_instructions(self):
        self.require_python_install()
        result = self.run_script('Linux Setup - Import Melee Iso.sh')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('with your distribution tools', result.stderr)
        self.assertFalse(self.log.exists())

    def test_linux_and_mac_forward_spaced_iso_and_options_from_another_directory(self):
        for platform, name in [('Linux', 'Linux Setup - Import Melee Iso.sh'),
                               ('Darwin', 'Mac Setup - Import Melee Iso.command')]:
            self.env['MELEE_TEST_OS'] = platform
            result = self.run_script(name, '/Game Dumps/My Melee.iso', '--jobs', '1', '--extract-only')
            self.assertEqual(result.returncode, 0, result.stderr)
            lines = self.log.read_text().splitlines()
            self.assertTrue(lines[0].replace('\\', '/').endswith(self.repo.name))
            self.assertEqual(lines[1:], ['-m', 'tools.melee_anim.launcher', 'import',
                                        '/Game Dumps/My Melee.iso', '--jobs', '1', '--extract-only'])
            self.assertFalse(self.admin_log.exists())

    def test_open_reuses_venv_and_never_installs(self):
        self.script('python', self.python, self.repo/'.venv/bin')
        for platform, name in [('Linux', 'Linux Open Melee Decomp Animation UI.sh'),
                               ('Darwin', 'Mac Open Melee Decomp Animation UI.command')]:
            self.env['MELEE_TEST_OS'] = platform
            result = self.run_script(name, '--port', '8766', '--no-browser')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(self.log.read_text().splitlines()[1:],
                             ['-m', 'tools.melee_anim.launcher', 'open', '--port', '8766', '--no-browser'])
            self.assertFalse(self.admin_log.exists())

    def test_missing_or_foreign_venv_and_wrong_os_fail_without_launching(self):
        result = self.run_script('Linux Open Melee Decomp Animation UI.sh')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('setup launcher first', result.stderr)
        (self.repo/'.venv/Scripts').mkdir(parents=True)
        result = self.run_script('Linux Setup - Import Melee Iso.sh')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('from another OS', result.stderr)
        result = self.run_script('Mac Setup - Import Melee Iso.command')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('your operating system', result.stderr)
        self.assertFalse(self.log.exists())
        self.assertFalse(self.admin_log.exists())

    def test_linux_installs_matching_venv_package_when_ensurepip_is_missing(self):
        self.env['MELEE_TEST_ENSUREPIP_STATUS'] = '1'
        self.script('apt-get', 'exit 0\n')
        result = self.run_script('Linux Setup - Import Melee Iso.sh')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.admin_log.read_text().splitlines(),
                         ['apt-get', 'update', 'apt-get', 'install', '-y', 'python3.13-venv'])
        self.assertTrue(self.log.exists())

    def test_package_manager_and_python_failures_propagate(self):
        self.env['MELEE_TEST_PYTHON_STATUS'] = '7'
        result = self.run_script('Linux Setup - Import Melee Iso.sh', '--extract-only')
        self.assertEqual(result.returncode, 7, result.stderr)
        self.env['MELEE_TEST_OS'] = 'Darwin'
        result = self.run_script('Mac Setup - Import Melee Iso.command', '--extract-only')
        self.assertEqual(result.returncode, 7, result.stderr)
        self.env['MELEE_TEST_OS'] = 'Linux'
        self.env['MELEE_TEST_ENSUREPIP_STATUS'] = '1'
        self.script('apt-get', 'exit 9\n')
        self.log.unlink()
        result = self.run_script('Linux Setup - Import Melee Iso.sh')
        self.assertEqual(result.returncode, 9, result.stderr)
        self.assertFalse(self.log.exists())

    def test_help_does_not_install_or_launch(self):
        result = self.run_script('Linux Setup - Import Melee Iso.sh', '--help')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Setup:', result.stdout)
        self.assertFalse(self.log.exists())
        self.assertFalse(self.admin_log.exists())


if __name__ == '__main__':
    unittest.main()
