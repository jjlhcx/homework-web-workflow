import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import cx
import setup_deps


class PortableTests(unittest.TestCase):
    def test_cached_wheels_allow_first_setup_without_network(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            cache = project / 'wheelhouse'
            cache.mkdir()
            (cache / 'cached.whl').touch()
            with (patch.object(setup_deps, 'dependencies_ready', side_effect=[False, True]),
                  patch.object(setup_deps.subprocess, 'run') as run):
                self.assertEqual(setup_deps.prepare(project), 'DEPENDENCIES_INSTALLED')
            run.assert_called_once()
            self.assertIn('--no-index', run.call_args.args[0])
            self.assertIn(str(cache), run.call_args.args[0])

    def test_download_timeout_has_a_clear_offline_recovery_path(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            with (patch.object(setup_deps, 'dependencies_ready', return_value=False),
                  patch.object(setup_deps.subprocess, 'run',
                               side_effect=subprocess.TimeoutExpired('pip', 50)) as run):
                self.assertIn('wheelhouse', setup_deps.prepare(project))
            run.assert_called_once()
            self.assertIn('download', run.call_args.args[0])
            self.assertLessEqual(run.call_args.kwargs['timeout'], 60)

    def test_launch_command_uses_selected_local_port_and_project_profile(self):
        self.assertTrue(hasattr(cx, 'browser_command'), 'portable browser command is missing')
        with patch.dict(os.environ, {'CX_BROWSER': sys.executable}):
            command = cx.browser_command('https://i.chaoxing.com/base', 'http://127.0.0.1:9333')
        self.assertIn('--remote-debugging-port=9333', command)
        self.assertIn('--user-data-dir=' + str(ROOT / '.browser-profile'), command)
        self.assertEqual(command[0], sys.executable)

    def test_remote_and_malformed_debugging_endpoints_stop_before_connection(self):
        self.assertTrue(hasattr(cx, 'validate_endpoint'), 'endpoint validation is missing')
        for endpoint in ('http://example.com:9222', 'https://127.0.0.1:9222',
                         'http://localhost:9222/path', 'http://user@localhost:9222',
                         'http://127.0.0.1:0', 'http://127.0.0.1:99999'):
            with self.subTest(endpoint=endpoint), self.assertRaises(cx.TaskError):
                cx.validate_endpoint(endpoint)

    def test_invalid_navigation_does_not_launch_any_process(self):
        self.assertTrue(hasattr(cx, 'browser_command'), 'portable browser command is missing')
        for url in ('javascript:alert(1)', 'https://chaoxing.com.example.org/',
                    'https://user@i.chaoxing.com/', 'https://example.com/'):
            with self.subTest(url=url), self.assertRaises(cx.TaskError):
                cx.browser_command(url, 'http://127.0.0.1:9222')


if __name__ == '__main__':
    unittest.main()
