import json
from pathlib import Path
import shutil
import subprocess
import unittest


@unittest.skipUnless(shutil.which("node"), "Node.js is optional for JavaScript fixture tests")
class IPadScriptTests(unittest.TestCase):
    def run_script(self, *, origin="https://www.autodl.com", storage=None):
        from importlib.resources import files
        script = files("autodl_classic_agent").joinpath("ipad_session.js").read_text()
        harness = r'''
const vm = require('node:vm');
const input = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));
const reads = [];
let result = null;
try {
  vm.runInNewContext(input.script, {
    location: {origin: input.origin},
    localStorage: {getItem(key) {reads.push(key); return input.storage[key] ?? null;}},
    completion(value) {result = JSON.parse(value);},
    fetch() {throw new Error('Network requests are forbidden');}
  }, {timeout: 1000});
  process.stdout.write(JSON.stringify({ok:true, result, reads}));
} catch (error) {
  process.stdout.write(JSON.stringify({ok:false, error:error.message, reads}));
}
'''
        result = subprocess.run([shutil.which("node"), "-e", harness],
            input=json.dumps({"script": script, "origin": origin, "storage": storage or {}}),
            text=True, capture_output=True, check=True)
        return json.loads(result.stdout)

    def test_exports_exact_verified_frontend_fields(self):
        result = self.run_script(storage={"token":"eyJaaa.bbb.ccc", "app_version":'{"version":"v6.54.0"}',
                                          "user":"private-profile", "other_secret":"ignored"})
        self.assertTrue(result["ok"])
        self.assertEqual(result["result"], {"token":"eyJaaa.bbb.ccc", "app_version":"v6.54.0"})
        self.assertEqual(result["reads"], ["token", "app_version"])

    def test_wrong_origin_is_rejected_before_storage_reads(self):
        for origin in ("https://example.com", "http://www.autodl.com", "https://www.autodl.com:8443"):
            with self.subTest(origin=origin):
                result = self.run_script(origin=origin, storage={"token":"eyJaaa.bbb.ccc"})
                self.assertFalse(result["ok"])
                self.assertEqual(result["reads"], [])

    def test_missing_or_invalid_token_has_no_secret_in_error(self):
        for token in (None, "invalid-private-value"):
            result = self.run_script(storage={"token":token})
            self.assertFalse(result["ok"])
            self.assertNotIn("invalid-private-value", result["error"])

    def test_bad_version_storage_uses_pinned_fallback(self):
        result = self.run_script(storage={"token":"eyJaaa.bbb.ccc", "app_version":"malformed"})
        self.assertTrue(result["ok"])
        self.assertEqual(result["result"]["app_version"], "v6.53.0")
