from contextlib import redirect_stdout
import io
import json
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
    def test_cli_json_survives_legacy_windows_console_decoding(self):
        title = '作业详情'
        for failed in (False, True):
            with self.subTest(failed=failed), patch.object(sys, 'argv', ['cx.py', 'check']), \
                    patch.object(cx, 'execute') as command, redirect_stdout(io.StringIO()) as output:
                if failed:
                    command.side_effect = cx.TaskError(title)
                else:
                    command.return_value = {'title': title}
                self.assertEqual(cx.main(), int(failed))
                received = output.getvalue().encode('utf-8').decode('gbk', errors='replace')
                expected = {'ok': not failed, 'error' if failed else 'title': title}
                self.assertEqual(json.loads(received), expected)

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

    def test_open_reports_not_ready_if_edge_spawns_without_debugger(self):
        url, endpoint = 'https://i.chaoxing.com/base', 'http://127.0.0.1:9222'
        with (patch.object(cx, 'browser_command', return_value=['edge.exe']),
              patch.object(cx.subprocess, 'Popen') as spawn,
              patch.object(cx, 'debugger_is_ready', return_value=False),
              patch.object(cx.time, 'monotonic', side_effect=[0, 1])):
            with self.assertRaisesRegex(cx.TaskError, 'BROWSER_START_NOT_READY'):
                cx.launch_browser(url, endpoint, timeout=1)
        spawn.assert_called_once()

    def test_open_waits_for_local_debugger_and_reuses_an_existing_connection(self):
        url, endpoint = 'https://i.chaoxing.com/base', 'http://127.0.0.1:9222'
        for ready_sequence, reused in (([False, False, True], False), ([True], True)):
            with (self.subTest(reused=reused),
                  patch.object(cx, 'browser_command', return_value=['edge.exe']),
                  patch.object(cx.subprocess, 'Popen') as spawn,
                  patch.object(cx, 'debugger_is_ready', side_effect=ready_sequence),
                  patch.object(cx.time, 'sleep'),
                  patch.object(cx.time, 'monotonic', return_value=0)):
                result = cx.launch_browser(url, endpoint, timeout=1)
                self.assertEqual(result['browser'], 'ready')
                self.assertEqual(result['reused'], reused)
                self.assertEqual(spawn.call_count, int(not reused))

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
