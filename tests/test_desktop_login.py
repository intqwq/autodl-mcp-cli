from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from autodl_classic_agent.desktop_login import main
from autodl_classic_agent.login import LoginError
from autodl_cli.config import load_config


class DesktopLoginTests(unittest.TestCase):
    session = {"token": "test-session", "app_version": "v6.53.0"}

    def test_local_login_saves_a_verified_session_without_printing_it(self):
        output = io.StringIO()
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(os.environ, {"AUTODL_CLI_HOME": directory}),
            patch("autodl_classic_agent.login.capture_browser_session", return_value=self.session) as capture,
            patch("autodl_cli.client.AutoDLClient"),
            patch("autodl_cli.handlers.auth.get_current_user"),
            redirect_stdout(output),
            redirect_stderr(io.StringIO()),
        ):
            self.assertEqual(main(["--timeout", "60"]), 0)
            self.assertEqual(load_config()["token"], self.session["token"])
        capture.assert_called_once_with(phone=None, password=None, visible=True, timeout=60, browser_path=None)
        self.assertTrue(json.loads(output.getvalue())["authenticated"])
        self.assertNotIn(self.session["token"], output.getvalue())

    def test_remote_login_streams_the_new_session_without_saving_it_locally(self):
        output, errors = io.StringIO(), io.StringIO()
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(os.environ, {"AUTODL_CLI_HOME": directory}),
            patch("autodl_classic_agent.desktop_login.shutil.which", return_value="ssh-client"),
            patch("autodl_classic_agent.desktop_login.capture_browser_session", return_value=self.session),
            patch("autodl_classic_agent.desktop_login.subprocess.run",
                  return_value=subprocess.CompletedProcess([], 0)) as ssh,
            redirect_stdout(output),
            redirect_stderr(errors),
        ):
            self.assertEqual(main(["--ssh", "user@host"]), 0)
            self.assertEqual(load_config(), {})
        args = ssh.call_args.args[0]
        self.assertEqual(args[:4], ["ssh-client", "-T", "--", "user@host"])
        self.assertIn("autodl auth import", args[4])
        self.assertNotIn(self.session["token"], str(args) + output.getvalue() + errors.getvalue())
        self.assertEqual(json.loads(ssh.call_args.kwargs["input"]), self.session)

    def test_capture_failure_does_not_connect_to_ssh(self):
        with (
            patch("autodl_classic_agent.desktop_login.shutil.which", return_value="ssh-client"),
            patch("autodl_classic_agent.desktop_login.capture_browser_session",
                  side_effect=LoginError("Login timed out.")),
            patch("autodl_classic_agent.desktop_login.subprocess.run") as ssh,
            redirect_stderr(io.StringIO()),
        ):
            self.assertEqual(main(["--ssh", "user@host"]), 1)
        ssh.assert_not_called()
