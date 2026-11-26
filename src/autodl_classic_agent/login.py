"""Login on AutoDL's own page, with automatic local session capture."""

import argparse
import getpass
from importlib.resources import files
import json
import os
import queue
import re
import shutil
import sys
import threading
import time
from urllib.parse import unquote, urlsplit

HOST = "https://www.autodl.com"
MAX_IMPORT = 65536


class LoginError(Exception):
    pass


class SessionCapture:
    """Observe normal page traffic; never synthesize a fingerprint or solve challenges."""
    def __init__(self):
        self.token = ""
        self.fingerprint = ""
        self.app_version = ""
        self.rejected = False
        self.needs_verification = False

    @staticmethod
    def _path(url):
        parsed = urlsplit(url)
        if parsed.scheme == "https" and parsed.hostname in {"www.autodl.com", "autodl.com"} and parsed.port in {None, 443}:
            return parsed.path
        return ""

    def request(self, request):
        path = self._path(request.url)
        if not path.startswith("/api/v1/"):
            return
        # Copy only non-password metadata. Do not persist request bodies or headers.
        version = request.headers.get("appversion", "")
        if re.fullmatch(r"v\d+(?:\.\d+)*", version):
            self.app_version = version
        # Covers interactive SMS/WeChat flows that authenticate without this
        # browser observing the password flow's passport response.
        if path in {"/api/v1/user/detail", "/api/v1/instance"}:
            authorization = request.headers.get("authorization", "")
            token = authorization.removeprefix("Bearer ").strip()
            if re.fullmatch(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", token):
                self.token = token
        if path not in {"/api/v1/new_login", "/api/v1/login_failed/count", "/api/v1/passport"}:
            return
        try:
            data = request.post_data_json
        except Exception:
            return
        if isinstance(data, dict):
            fingerprint = data.get("device_fingerprint", "")
            if isinstance(fingerprint, str) and re.fullmatch(r"[0-9a-f]{32}", fingerprint):
                self.fingerprint = fingerprint

    def response(self, response):
        path = self._path(response.url)
        if path not in {"/api/v1/new_login", "/api/v1/passport"}:
            return
        try:
            body = response.json()
        except Exception:
            return
        if not isinstance(body, dict):
            return
        if body.get("code") != "Success":
            # Do not reflect potentially sensitive server error bodies into logs.
            message = str(body.get("code", "")) + str(body.get("msg", ""))
            self.needs_verification = bool(re.search(r"captcha|验证|人机|滑块", message, re.I))
            self.rejected = True
            return
        if path == "/api/v1/passport":
            data = body.get("data")
            if isinstance(data, dict) and isinstance(data.get("token"), str) and data["token"]:
                self.token = data["token"]


def verify_and_save(session: dict, *, timeout: float = 20) -> dict:
    from autodl_cli.client import AutoDLClient, APP_VERSION
    from autodl_cli.config import load_config, save_config, config_path
    from autodl_cli.handlers.auth import get_current_user
    token = session.get("token")
    if not isinstance(token, str) or not token or len(token) > 16384 or any(ord(c) < 33 or ord(c) > 126 for c in token):
        raise LoginError("Invalid session token; nothing was saved.")
    app_version = session.get("app_version", APP_VERSION)
    if not isinstance(app_version, str) or not re.fullmatch(r"v\d+(?:\.\d+)*", app_version):
        raise LoginError("Invalid session metadata; nothing was saved.")
    if not 0 < timeout <= 120:
        raise LoginError("Invalid verification timeout.")
    results = queue.Queue(maxsize=1)
    def verify():
        try:
            with AutoDLClient(token, base_url=HOST, app_version=app_version, timeout=timeout) as client:
                get_current_user(client)
            results.put(True)
        except Exception:
            results.put(False)
    # A daemon plus bounded queue wait also bounds DNS/proxy stalls. Only the
    # main thread below can write credentials; a late result cannot save them.
    threading.Thread(target=verify, daemon=True).start()
    try:
        verified = results.get(timeout=timeout)
    except queue.Empty:
        raise LoginError("AutoDL session verification timed out. Check the server's HTTPS/proxy access. Nothing was saved.") from None
    if not verified:
        raise LoginError("AutoDL could not verify the session; nothing was saved.")
    config = load_config()
    config.update(token=token, base_url=HOST, app_version=app_version)
    fingerprint = session.get("device_fingerprint")
    if fingerprint:
        if not isinstance(fingerprint, str) or not re.fullmatch(r"[0-9a-f]{32}", fingerprint):
            raise LoginError("Invalid device metadata; nothing was saved.")
        config["device_fingerprint"] = fingerprint
    save_config(config)
    return {"authenticated": True, "config_path": str(config_path())}


def system_browser() -> str | None:
    for command in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        path = shutil.which(command)
        if path:
            return path
    return None


def browser_proxy() -> dict | None:
    """Honor the inherited outbound proxy instead of silently connecting directly."""
    address = next((os.environ[name] for name in ("HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy")
                    if os.environ.get(name)), "")
    if not address:
        return None
    parsed = urlsplit(address)
    if parsed.scheme not in {"http", "https", "socks5", "socks5h"} or not parsed.hostname:
        raise LoginError("Unsupported browser proxy configuration.")
    try:
        port = parsed.port
    except ValueError:
        raise LoginError("Invalid browser proxy port.") from None
    scheme = "socks5" if parsed.scheme == "socks5h" else parsed.scheme
    host = f"[{parsed.hostname}]" if ":" in parsed.hostname else parsed.hostname
    proxy = {"server": f"{scheme}://{host}" + (f":{port}" if port else "")}
    if parsed.username:
        proxy["username"] = unquote(parsed.username)
    if parsed.password:
        proxy["password"] = unquote(parsed.password)
    bypass = os.environ.get("NO_PROXY") or os.environ.get("no_proxy")
    if bypass:
        proxy["bypass"] = bypass
    return proxy


def capture_browser_session(*, phone: str | None = None, password: str | None = None,
                            visible: bool = False, timeout: float = 180,
                            browser_path: str | None = None) -> dict:
    try:
        from playwright.sync_api import sync_playwright, Error as BrowserError
    except ImportError:
        raise LoginError("Install browser support with install.sh --with-browser or python -m pip install \".[login]\".") from None
    if not visible and (not phone or not password):
        raise LoginError("Phone number and password are required for terminal login.")
    capture = SessionCapture()
    stage = "starting Chromium"
    started = time.monotonic()
    def progress(message):
        print(f"[{int(time.monotonic() - started)}s] {message}", file=sys.stderr, flush=True)
    try:
        with sync_playwright() as playwright:
            executable = browser_path or system_browser()
            proxy = browser_proxy()
            progress("Starting Chromium (30-second limit)...")
            browser = playwright.chromium.launch(headless=not visible, timeout=30000,
                **({"executable_path": executable} if executable else {}),
                **({"proxy": proxy} if proxy else {}))
            try:
                context = browser.new_context()
                page = context.new_page()
                page.set_default_timeout(15000)
                page.on("request", capture.request)
                page.on("response", capture.response)
                stage = "loading AutoDL's login page"
                progress("Loading AutoDL login (30-second limit)...")
                page.goto(HOST + "/login", wait_until="domcontentloaded", timeout=30000)
                if not visible:
                    if SessionCapture._path(page.url) != "/login":
                        raise LoginError("Unexpected login destination; credentials were not entered.")
                    # Selectors verified on the public AutoDL login page.
                    page.get_by_placeholder("请输入手机号", exact=True).fill(phone)
                    page.get_by_placeholder("请输入密码", exact=True).fill(password)
                    stage = "submitting the login form"
                    progress("Submitting once. Interactive verification requires the iPad/Safari flow.")
                    page.get_by_role("button", name="登录", exact=True).click()
                deadline = time.monotonic() + timeout
                stage = "waiting for an authenticated session"
                progress("Waiting for login result...")
                next_progress = time.monotonic() + 10
                while not capture.token:
                    if page.is_closed():
                        raise LoginError("Browser closed before login completed; nothing was saved.")
                    if not visible and capture.rejected:
                        if capture.needs_verification:
                            raise LoginError("AutoDL requires interactive verification. Log in in iPad Safari, run the session Shortcut, then use autodl auth login --ipad.")
                        raise LoginError("AutoDL rejected the login. Check your credentials, or use the iPad/Safari login flow.")
                    if time.monotonic() >= deadline:
                        raise LoginError("Login timed out. On iPad, use Safari login plus the session Shortcut, then autodl auth login --ipad.")
                    if time.monotonic() >= next_progress:
                        progress("Still waiting; use --ipad if the server cannot complete interactive verification.")
                        next_progress = time.monotonic() + 10
                    # Pumps browser events; no retry, reload, challenge solving or device rotation.
                    page.wait_for_timeout(250)
            finally:
                browser.close()
    except BrowserError:
        raise LoginError(f"Browser login failed while {stage}. Use autodl auth login --ipad to avoid server-browser dependencies. No session was saved.") from None
    return {"token": capture.token, "app_version": capture.app_version or "v6.53.0",
            "device_fingerprint": capture.fingerprint}


def browser_login(*, phone: str | None = None, password: str | None = None,
                  visible: bool = False, timeout: float = 180, browser_path: str | None = None) -> dict:
    session = capture_browser_session(phone=phone, password=password, visible=visible,
                                      timeout=timeout, browser_path=browser_path)
    print("Verifying the session (20-second limit)...", file=sys.stderr, flush=True)
    return verify_and_save(session)


def auth_command(args: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="autodl auth", description="iPad/Safari login by default; no server browser or DevTools needed.")
    sub = parser.add_subparsers(dest="action", required=True)
    login = sub.add_parser("login", help="Import your own Safari session using the iPad Shortcut")
    modes = login.add_mutually_exclusive_group()
    modes.add_argument("--ipad", action="store_true", help="Default: hidden paste of the Safari Shortcut output")
    modes.add_argument("--headless", action="store_true", help="Optional: phone/password through server Chromium")
    modes.add_argument("--browser", action="store_true", help="Optional: visible browser on a machine with a display")
    login.add_argument("--phone", help="Account phone number; prompted when omitted")
    login.add_argument("--browser-path", help="Use an installed Chromium/Chrome executable")
    login.add_argument("--timeout", type=float, default=180)
    sub.add_parser("export", help="Write the session to a pipe; refuses a terminal")
    sub.add_parser("import", help="Verify and save a session received through stdin")
    sub.add_parser("ipad-script", help="Print the JavaScript to copy into iPad Shortcuts; contains no credentials")
    opts = parser.parse_args(args)
    try:
        if opts.action == "ipad-script":
            print(files("autodl_classic_agent").joinpath("ipad_session.js").read_text())
            return 0
        if opts.action == "export":
            from autodl_cli.config import load_config
            if sys.stdout.isatty():
                raise LoginError("Session export contains a secret. Pipe it directly to SSH/auth import, not a terminal.")
            config = load_config()
            if not config.get("token"):
                raise LoginError("No saved session to export.")
            print(json.dumps({key: config[key] for key in ("token", "device_fingerprint", "app_version") if key in config}))
            return 0
        if opts.action == "import":
            if sys.stdin.isatty():
                raise LoginError("For an interactive paste, use autodl auth login --ipad. Import accepts a pipe only.")
            data = sys.stdin.read(MAX_IMPORT + 1)
            if len(data) > MAX_IMPORT:
                raise LoginError("Session import is too large.")
            try:
                session = json.loads(data)
            except ValueError:
                raise LoginError("Invalid session JSON; nothing was saved.") from None
            if not isinstance(session, dict):
                raise LoginError("Session must be a JSON object.")
            result = verify_and_save(session)
        else:
            if opts.ipad or not (opts.headless or opts.browser or opts.phone):
                if not sys.stdin.isatty():
                    raise LoginError("Use a terminal for hidden session input, or pipe session JSON into autodl auth import.")
                print("1. Sign in at https://www.autodl.com in iPad Safari.\n"
                      "2. Run your AutoDL session Shortcut from Safari's Share menu.\n"
                      "   Setup/code: IPAD_LOGIN.md or autodl auth ipad-script.\n"
                      "3. Paste its clipboard output here. It will not be echoed.\n"
                      "   Keep this session out of chats and logs.", file=sys.stderr, flush=True)
                value = getpass.getpass("AutoDL Safari session JSON (hidden): ")
                if len(value) > MAX_IMPORT:
                    raise LoginError("Session import is too large.")
                try:
                    session = json.loads(value)
                except ValueError:
                    raise LoginError("Paste the Shortcut's full JSON output; nothing was saved.") from None
                if not isinstance(session, dict):
                    raise LoginError("Session must be a JSON object.")
                print("Verifying with AutoDL (20-second limit)...", file=sys.stderr, flush=True)
                result = verify_and_save(session)
                print(json.dumps(result))
                return 0
            if not 0 < opts.timeout <= 900:
                raise LoginError("Login timeout must be greater than 0 and at most 900 seconds.")
            if not opts.browser and not sys.stdin.isatty():
                raise LoginError("Run phone/password login in a terminal. For unattended use, import an existing session through SSH.")
            phone = opts.phone
            password = None
            if not opts.browser:
                phone = phone or input("AutoDL phone number (+86): ").strip()
                password = getpass.getpass("AutoDL password (hidden, never saved): ")
            else:
                print("Complete login in the browser. Its session will be captured automatically; do not copy any headers.", file=sys.stderr)
            result = browser_login(phone=phone, password=password, visible=opts.browser,
                timeout=opts.timeout, browser_path=opts.browser_path)
        print(json.dumps(result))
        return 0
    except LoginError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except (OSError, EOFError):
        print("Local login/config operation failed; check file permissions and terminal access.", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Login cancelled.", file=sys.stderr)
        return 130
