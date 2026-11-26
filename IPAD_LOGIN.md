# Sign in with only an iPad and SSH

The app is now named **autodl**. Its default login no longer starts Chromium
on the server. Press Ctrl+C to stop the old stuck command before upgrading.

This flow uses Safari's normal AutoDL sign-in, including any CAPTCHA/SMS step.
A small, local Shortcut copies your own signed-in session, which you paste
into the SSH terminal's hidden prompt. No DevTools, HTTP headers, PC, server
browser, remote desktop, inbound port or SSH port forwarding is needed.

## One-time Shortcut setup

1. Open **Shortcuts** on the iPad and create a shortcut named **AutoDL Login**.
2. Add **Run JavaScript on Web Page**. Its input should be **Shortcut Input**.
3. Replace the sample script with the code printed by:

   ```bash
   autodl auth ipad-script
   ```

   The same code is included in
   `src/autodl_classic_agent/ipad_session.js` in this archive. It contains no
   account credentials. Copy the script itself, not your session output.
4. Add **Copy to Clipboard** after it, taking the JavaScript result as input.
5. In the shortcut's Details, enable **Show in Share Sheet** and set its
   accepted input type to **Safari Web Pages**.
6. If Shortcuts requires it, enable **Allow Running Scripts** in its settings.

Apple's instructions for the two relevant actions/settings:
https://support.apple.com/en-gb/guide/shortcuts/apdb71a01d93/ios

## Log in

1. Open **https://www.autodl.com** in Safari and sign in normally. Stay on the
   signed-in console tab. Use Safari itself, not an in-app browser.
2. Tap **Share → AutoDL Login**. Allow this trusted Shortcut on AutoDL when
   iPadOS asks. It copies a small session JSON to the clipboard.
3. In your SSH terminal, run:

   ```bash
   autodl auth login
   ```

4. Paste the clipboard at the **AutoDL Safari session JSON (hidden)** prompt
   and press Enter. Input is not echoed. Verification has a 20-second deadline;
   a timeout or failure leaves the existing saved session unchanged.
5. Check:

   ```bash
   autodl --json account me
   autodl --json instance list
   ```

The clipboard result is a login secret for your own server. Paste it only into
the local SSH login prompt, never into chat or a log. Copy some ordinary text
afterward to clear it from the clipboard. The Shortcut makes no network
requests: it reads only the AutoDL page's `token` and `app_version` values and
returns those to the native Copy to Clipboard action.

If the Shortcut says no session was found, verify you are signed in in the
same Safari tab and domain. If server verification fails, check the server's
HTTPS/proxy connectivity or sign in again in Safari. Do not repeat rental
creation commands while diagnosing authentication.

## Optional other login methods

`autodl auth login --headless` retains the older server Chromium phone/password
flow. Windows and Ubuntu desktops can use [the desktop login script](docs/DESKTOP_LOGIN.md)
to sign in locally or send a session to the Ubuntu host over SSH.
