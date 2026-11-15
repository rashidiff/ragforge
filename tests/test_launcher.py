"""Lifecycle regressions; no model downloads or running servers required."""

import subprocess
import unittest
from unittest.mock import MagicMock, patch

import ragforge


class LauncherTests(unittest.TestCase):
    def start_context(self):
        return patch.multiple(
            ragforge,
            node_executable=MagicMock(return_value=("node", "npm")),
        )

    def test_install_stops_before_npm_when_backend_install_fails(self):
        with self.start_context(), patch.object(ragforge.Path, "exists", return_value=True), patch.object(
            ragforge.subprocess, "run", side_effect=subprocess.CalledProcessError(1, "pip")
        ) as run:
            with self.assertRaises(subprocess.CalledProcessError):
                ragforge.install()
            self.assertEqual(run.call_count, 1)

    def test_missing_dependencies_explain_install(self):
        with self.start_context(), patch.object(ragforge.Path, "exists", return_value=False):
            with self.assertRaisesRegex(RuntimeError, "ragforge.py install"):
                ragforge.start()

    def run_start(self, processes):
        return patch.multiple(
            ragforge.subprocess,
            check_output=MagicMock(return_value='[8123, "http://127.0.0.1:5174"]'),
            Popen=MagicMock(side_effect=processes),
        )

    def test_custom_ports_and_peer_failure_stop_both(self):
        backend, frontend = MagicMock(), MagicMock()
        backend.poll.return_value = 7
        backend.returncode = 7
        with self.start_context(), patch.object(ragforge.Path, "exists", return_value=True), self.run_start(
            [backend, frontend]
        ), patch.object(ragforge.socket, "socket"), patch.object(ragforge, "stop") as stop:
            with self.assertRaisesRegex(RuntimeError, "Backend exited"):
                ragforge.start()
            calls = ragforge.subprocess.Popen.call_args_list
            self.assertEqual(calls[1].kwargs["env"]["RAG_API_PROXY"], "http://127.0.0.1:8123")
            self.assertIn("5174", calls[1].args[0])
            self.assertEqual([c.args[0] for c in stop.call_args_list], [frontend, backend])

    def test_second_spawn_failure_cleans_up_backend(self):
        backend = MagicMock()
        with self.start_context(), patch.object(ragforge.Path, "exists", return_value=True), self.run_start(
            [backend, OSError("spawn failed")]
        ), patch.object(ragforge.socket, "socket"), patch.object(ragforge, "stop") as stop:
            with self.assertRaisesRegex(OSError, "spawn failed"):
                ragforge.start()
            stop.assert_called_once_with(backend)

    def test_ctrl_c_stops_both(self):
        backend, frontend = MagicMock(), MagicMock()
        backend.poll.side_effect = KeyboardInterrupt
        with self.start_context(), patch.object(ragforge.Path, "exists", return_value=True), self.run_start(
            [backend, frontend]
        ), patch.object(ragforge.socket, "socket"), patch.object(ragforge, "stop") as stop:
            ragforge.start()
            self.assertEqual(stop.call_count, 2)


if __name__ == "__main__":
    unittest.main()
