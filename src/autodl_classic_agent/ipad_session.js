// Run only on your own signed-in AutoDL page in Safari's share sheet.
// Add a native "Copy to Clipboard" action after "Run JavaScript on Web Page".
// No network request is made. The result is a secret for your own SSH CLI.
(function () {
  if (!["https://www.autodl.com", "https://autodl.com"].includes(location.origin)) {
    throw new Error("Open your signed-in AutoDL console in Safari first.");
  }
  const token = localStorage.getItem("token");
  if (!token || !/^eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$/.test(token)) {
    throw new Error("No AutoDL session found. Sign in in this Safari tab first.");
  }
  let version = "v6.53.0";
  try {
    const candidate = JSON.parse(localStorage.getItem("app_version") || "{}").version;
    if (typeof candidate === "string" && /^v\d+(?:\.\d+)*$/.test(candidate)) version = candidate;
  } catch (_) {}
  completion(JSON.stringify({token: token, app_version: version}));
})();
