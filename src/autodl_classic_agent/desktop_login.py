"""Sign in to AutoDL from a desktop and save the session locally or over SSH."""

import argparse
import json
import shutil
import subprocess
import sys

from .login import LoginError, browser_login, capture_browser_session


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="autodl-desktop-login",
        description="Open AutoDL in a fresh browser and save your session after you sign in.",
    )
    parser.add_argument("--ssh", metavar="USER@HOST",
                        help="Save on this Ubuntu SSH host instead of this computer")
    parser.add_argument("--timeout", type=float, default=180, metavar="SECONDS",
                        help="Time to complete sign-in, from 1 to 900 seconds (default: 180)")
    parser.add_argument("--browser-path", metavar="PATH",
                        help="Use this Chromium or Chrome executable")
    options = parser.parse_args(argv)
    if not 1 <= options.timeout <= 900:
        parser.error("--timeout must be between 1 and 900 seconds")

    ssh = None
    if options.ssh is not None:
        if (not options.ssh or options.ssh.startswith("-")
                or any(char.isspace() for char in options.ssh)):
            parser.error("--ssh requires an SSH host alias or USER@HOST")
        ssh = shutil.which("ssh")
        if not ssh:
            parser.error("--ssh requires the OpenSSH client on PATH")

    try:
        print("Sign in to AutoDL in the browser window.", file=sys.stderr, flush=True)
        if ssh is None:
            result = browser_login(visible=True, timeout=options.timeout,
                                   browser_path=options.browser_path)
            print(json.dumps(result))
            return 0

        session = capture_browser_session(visible=True, timeout=options.timeout,
                                          browser_path=options.browser_path)
        print("Sending the session over SSH for verification on the Ubuntu host.",
              file=sys.stderr, flush=True)
        remote_import = ('if command -v autodl >/dev/null 2>&1; then exec autodl auth import; fi; '
                         'exec "$HOME/.local/bin/autodl" auth import')
        result = subprocess.run([ssh, "-T", "--", options.ssh, remote_import],
                                input=json.dumps(session), text=True, check=False)
        return result.returncode
    except LoginError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except OSError:
        print("Could not launch SSH or access the local login configuration.", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Login cancelled.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
