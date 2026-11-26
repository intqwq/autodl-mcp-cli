from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from autodl_classic_agent.login import (LoginError, SessionCapture, auth_command,
                                        browser_login, browser_proxy, verify_and_save)
from autodl_classic_agent.cli import main


class CaptureTests(unittest.TestCase):
    def test_captures_only_successful_official_passport(self):
        capture = SessionCapture()
        for url in ("http://www.autodl.com/api/v1/passport", "https://example.com/api/v1/passport",
                    "https://www.autodl.com:444/api/v1/passport"):
            capture.response(SimpleNamespace(url=url, json=lambda: {"code": "Success", "data": {"token": "wrong"}}))
        self.assertEqual(capture.token, "")
        capture.response(SimpleNamespace(url="https://www.autodl.com/api/v1/passport",
            json=lambda: {"code": "Success", "data": {"token": "valid-session"}}))
        self.assertEqual(capture.token, "valid-session")

    def test_normal_browser_metadata_without_password_retention(self):
        capture = SessionCapture()
        capture.request(SimpleNamespace(url="https://www.autodl.com/api/v1/new_login",
            headers={"appversion": "v6.53.0"}, post_data_json={"phone": "private-phone",
                "password": "private-password", "device_fingerprint": "a" * 32}))
        self.assertEqual(capture.fingerprint, "a" * 32)
        self.assertEqual(capture.app_version, "v6.53.0")
        self.assertNotIn("private-password", str(vars(capture)))
        self.assertNotIn("private-phone", str(vars(capture)))

    def test_challenge_is_detected_without_returning_server_message(self):
        capture = SessionCapture()
        capture.response(SimpleNamespace(url="https://www.autodl.com/api/v1/new_login",
            json=lambda: {"code": "CaptchaRequired", "msg": "验证码 private-password"}))
        self.assertTrue(capture.rejected)
        self.assertTrue(capture.needs_verification)
        self.assertNotIn("private-password", str(vars(capture)))

    def test_manual_login_session_can_be_captured_from_normal_authenticated_traffic(self):
        capture = SessionCapture()
        capture.request(SimpleNamespace(url="https://www.autodl.com/api/v1/user/detail",
            headers={"authorization": "Bearer eyJaaa.bbb.ccc", "appversion": "v6.54.0"}))
        self.assertEqual(capture.token, "eyJaaa.bbb.ccc")
        self.assertEqual(capture.app_version, "v6.54.0")


class BrowserFlowTests(unittest.TestCase):
    def fake_runtime(self, *, challenge=False, visible=False):
        events, fields = {}, {}
        page = MagicMock()
        page.url = "https://www.autodl.com/login"
        page.on.side_effect = lambda name, callback: events.update({name: callback})
        page.is_closed.return_value = False
        page.get_by_placeholder.side_effect = lambda name, **kwargs: SimpleNamespace(fill=lambda value: fields.update({name: value}))
        def submit():
            if challenge:
                events["response"](SimpleNamespace(url="https://www.autodl.com/api/v1/new_login",
                    json=lambda: {"code": "CaptchaRequired"}))
            else:
                events["request"](SimpleNamespace(url="https://www.autodl.com/api/v1/new_login",
                    headers={"appversion": "v6.53.0"}, post_data_json={"device_fingerprint": "a" * 32}))
                events["response"](SimpleNamespace(url="https://www.autodl.com/api/v1/passport",
                    json=lambda: {"code": "Success", "data": {"token": "session-test"}}))
        page.get_by_role.return_value.click.side_effect = submit
        if visible:
            page.wait_for_timeout.side_effect = lambda amount: submit()
        browser = MagicMock()
        browser.new_context.return_value.new_page.return_value = page
        runtime = MagicMock()
        runtime.chromium.launch.return_value = browser
        manager = MagicMock()
        manager.__enter__.return_value = runtime
        module = SimpleNamespace(sync_playwright=lambda: manager, Error=type("FakeBrowserError", (Exception,), {}))
        return module, runtime, browser, page, fields

    def test_headless_phone_password_submits_once_and_saves_only_session(self):
        module, runtime, browser, page, fields = self.fake_runtime()
        with patch.dict("sys.modules", {"playwright.sync_api": module}), patch("autodl_classic_agent.login.system_browser", return_value=None), patch("autodl_classic_agent.login.verify_and_save", return_value={"authenticated": True}) as save:
            result = browser_login(phone="phone-local", password="password-local")
        self.assertTrue(result["authenticated"])
        self.assertTrue(runtime.chromium.launch.call_args.kwargs["headless"])
        page.get_by_role.return_value.click.assert_called_once()
        self.assertEqual(fields["请输入密码"], "password-local")
        self.assertNotIn("password-local", str(save.call_args))
        self.assertEqual(save.call_args.args[0]["token"], "session-test")
        browser.close.assert_called_once()

    def test_captcha_stops_headless_flow_without_retries(self):
        module, runtime, browser, page, fields = self.fake_runtime(challenge=True)
        with patch.dict("sys.modules", {"playwright.sync_api": module}), patch("autodl_classic_agent.login.system_browser", return_value=None), patch("autodl_classic_agent.login.verify_and_save") as save:
            with self.assertRaises(LoginError) as caught:
                browser_login(phone="phone", password="password")
        self.assertIn("interactive verification", str(caught.exception))
        page.get_by_role.return_value.click.assert_called_once()
        save.assert_not_called()
        browser.close.assert_called_once()

    def test_visible_browser_leaves_credential_entry_to_user(self):
        module, runtime, browser, page, fields = self.fake_runtime(visible=True)
        with patch.dict("sys.modules", {"playwright.sync_api": module}), patch("autodl_classic_agent.login.system_browser", return_value=None), patch("autodl_classic_agent.login.verify_and_save", return_value={"authenticated": True}):
            browser_login(visible=True)
        self.assertFalse(runtime.chromium.launch.call_args.kwargs["headless"])
        self.assertEqual(fields, {})
        page.get_by_role.assert_not_called()


class SessionStorageTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.environment = patch.dict(os.environ, {"AUTODL_CLI_HOME": self.directory.name})
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def test_verification_then_private_storage_no_password(self):
        from autodl_cli.config import load_config, config_path
        with patch("autodl_cli.client.AutoDLClient"), patch("autodl_cli.handlers.auth.get_current_user", return_value={"id": 1}):
            result = verify_and_save({"token": "session-test", "password": "not-saved", "base_url": "https://example.com"})
        self.assertTrue(result["authenticated"])
        config = load_config()
        self.assertEqual(config["base_url"], "https://www.autodl.com")
        self.assertEqual(config["token"], "session-test")
        self.assertNotIn("password", config)
        self.assertEqual(config_path().stat().st_mode & 0o777, 0o600)

    def test_browser_preserves_proxy_settings_without_putting_password_in_server_url(self):
        with patch.dict(os.environ, {"HTTPS_PROXY": "http://user:proxy-secret@proxy.example:8080", "NO_PROXY": "localhost"}):
            proxy = browser_proxy()
        self.assertEqual(proxy["server"], "http://proxy.example:8080")
        self.assertEqual(proxy["password"], "proxy-secret")
        self.assertNotIn("proxy-secret", proxy["server"])
        self.assertEqual(proxy["bypass"], "localhost")

    def test_failed_verification_does_not_overwrite_existing_session(self):
        from autodl_cli.config import save_config, load_config
        save_config({"token": "old-session"})
        with patch("autodl_cli.handlers.auth.get_current_user", side_effect=RuntimeError("new-session")):
            with self.assertRaises(LoginError) as caught:
                verify_and_save({"token": "new-session"})
        self.assertNotIn("new-session", str(caught.exception))
        self.assertEqual(load_config()["token"], "old-session")

    def test_import_does_not_reflect_invalid_secret_input(self):
        output, errors = io.StringIO(), io.StringIO()
        with patch("sys.stdin", io.StringIO("invalid-secret-input")), redirect_stdout(output), redirect_stderr(errors):
            self.assertEqual(auth_command(["import"]), 1)
        self.assertNotIn("invalid-secret-input", errors.getvalue())
        self.assertEqual(output.getvalue(), "")

    def test_import_verifies_then_reports_only_success(self):
        output = io.StringIO()
        source = {"token": "private-session", "app_version": "v6.53.0"}
        with patch("sys.stdin", io.StringIO(json.dumps(source))), patch("autodl_classic_agent.login.verify_and_save", return_value={"authenticated": True}) as save, redirect_stdout(output):
            self.assertEqual(auth_command(["import"]), 0)
        self.assertEqual(save.call_args.args[0], source)
        self.assertNotIn("private-session", output.getvalue())

    def test_export_refuses_terminal(self):
        from autodl_cli.config import save_config
        save_config({"token": "session-test"})
        output = io.StringIO()
        output.isatty = lambda: True
        with redirect_stdout(output), redirect_stderr(io.StringIO()):
            self.assertEqual(auth_command(["export"]), 1)
        self.assertEqual(output.getvalue(), "")

    def test_export_pipe_contains_only_session_metadata(self):
        from autodl_cli.config import save_config
        save_config({"token": "session-test", "device_fingerprint": "a" * 32, "password": "legacy-not-exported"})
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(auth_command(["export"]), 0)
        self.assertEqual(set(json.loads(output.getvalue())), {"token", "device_fingerprint"})

    def test_terminal_login_uses_hidden_password_and_clean_output(self):
        terminal = io.StringIO()
        terminal.isatty = lambda: True
        output = io.StringIO()
        with patch("sys.stdin", terminal), patch("builtins.input", return_value="phone-local"), patch("getpass.getpass", return_value="private-password"), patch("autodl_classic_agent.login.browser_login", return_value={"authenticated": True}) as login, redirect_stdout(output):
            self.assertEqual(main(["auth", "login", "--headless"]), 0)
        self.assertEqual(login.call_args.kwargs["password"], "private-password")
        self.assertNotIn("private-password", output.getvalue())

    def test_default_login_imports_ipad_session_without_launching_browser(self):
        terminal = io.StringIO()
        terminal.isatty = lambda: True
        output, errors = io.StringIO(), io.StringIO()
        session = {"token": "private-session", "app_version": "v6.54.0"}
        with patch("sys.stdin", terminal), patch("getpass.getpass", return_value=json.dumps(session)), patch("autodl_classic_agent.login.verify_and_save", return_value={"authenticated": True}) as save, patch("autodl_classic_agent.login.browser_login", side_effect=AssertionError("Default iPad login must not start Chromium")), redirect_stdout(output), redirect_stderr(errors):
            self.assertEqual(main(["auth", "login"]), 0)
        self.assertEqual(save.call_args.args[0], session)
        self.assertNotIn("private-session", output.getvalue() + errors.getvalue())
        self.assertIn("Safari", errors.getvalue())

    def test_ipad_import_rejects_bad_json_without_echo(self):
        terminal = io.StringIO()
        terminal.isatty = lambda: True
        output, errors = io.StringIO(), io.StringIO()
        with patch("sys.stdin", terminal), patch("getpass.getpass", return_value="not-json-private-value"), redirect_stdout(output), redirect_stderr(errors):
            self.assertEqual(main(["auth", "login", "--ipad"]), 1)
        self.assertNotIn("not-json-private-value", output.getvalue() + errors.getvalue())

    def test_verification_deadline_cannot_save_a_late_result(self):
        from autodl_cli.config import load_config
        def slow_user(client):
            time.sleep(0.15)
            return {"id": 1}
        started = time.monotonic()
        with patch("autodl_cli.client.AutoDLClient"), patch("autodl_cli.handlers.auth.get_current_user", side_effect=slow_user):
            with self.assertRaises(LoginError) as caught:
                verify_and_save({"token": "session-test"}, timeout=0.01)
        self.assertIn("timed out", str(caught.exception))
        self.assertLess(time.monotonic() - started, 0.12)
        time.sleep(0.17)
        self.assertNotIn("token", load_config())

    def test_script_printing_needs_no_credentials_or_browser(self):
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(["auth", "ipad-script"]), 0)
        self.assertIn('localStorage.getItem("token")', output.getvalue())


class UninstallTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).resolve().parents[1] / "uninstall_old.py"
        spec = importlib.util.spec_from_file_location("uninstall_old", path)
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.base = Path(self.directory.name)
        self.root = self.base / "autodl-agent"
        self.bins = self.base / "bin"
        self.bins.mkdir()

    def original_install(self):
        environment = self.root / "venv"
        metadata = environment / "lib/python3.12/site-packages/autodl_agent-0.1.0.dist-info/METADATA"
        metadata.parent.mkdir(parents=True)
        metadata.write_text("Name: autodl-agent\nVersion: 0.1.0\n")
        (environment / "pyvenv.cfg").write_text("home = /usr/bin\n")
        for command in ("autodl", "autodl-mcp"):
            (self.bins / command).symlink_to(environment / "bin" / command)
        return environment

    def test_removes_only_original_install_and_preserves_credentials(self):
        environment = self.original_install()
        credentials = self.base / "private-credentials"
        credentials.write_text("preserve")
        classic = self.bins / "autodl-classic"
        classic.write_text("preserve")
        self.module.uninstall(self.root, self.bins)
        self.assertFalse(environment.exists())
        self.assertFalse((self.bins / "autodl").is_symlink())
        self.assertEqual(credentials.read_text(), "preserve")
        self.assertEqual(classic.read_text(), "preserve")

    def test_preserves_unrelated_commands_and_files(self):
        self.original_install()
        (self.bins / "autodl").unlink()
        (self.bins / "autodl").write_text("different-tool")
        extra = self.root / "notes.txt"
        extra.write_text("preserve")
        self.module.uninstall(self.root, self.bins)
        self.assertEqual((self.bins / "autodl").read_text(), "different-tool")
        self.assertEqual(extra.read_text(), "preserve")

    def test_refuses_unverified_environment(self):
        environment = self.root / "venv"
        environment.mkdir(parents=True)
        with self.assertRaises(ValueError):
            self.module.uninstall(self.root, self.bins)
        self.assertTrue(environment.exists())

    def test_refuses_symlink_root(self):
        target = self.base / "other"
        target.mkdir()
        self.root.symlink_to(target)
        with self.assertRaises(ValueError):
            self.module.uninstall(self.root, self.bins)
        self.assertTrue(target.exists())

    def test_already_removed_is_idempotent(self):
        self.module.uninstall(self.root, self.bins)
        self.module.uninstall(self.root, self.bins)
