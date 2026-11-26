from contextlib import redirect_stdout
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import httpx
from autodl_cli.client import AutoDLClient
from autodl_cli.handlers import instance
from autodl_classic_agent.cli import main, plan_rental
from autodl_classic_agent.server import build_server, scrub


class ContractTests(unittest.TestCase):
    def test_preview_is_classic_rental_not_art_or_pro(self):
        result = plan_rental("machine-test", "base-image-test", gpu_amount=2, expand_data_disk=40)
        self.assertTrue(result["dry_run"])
        self.assertEqual(result["url"], "https://www.autodl.com/api/v1/order/instance/create/payg")
        body = result["body"]
        self.assertEqual(body["instance_info"]["machine_id"], "machine-test")
        self.assertEqual(body["instance_info"]["req_gpu_amount"], 2)
        self.assertEqual(body["instance_info"]["charge_type"], "payg")
        self.assertEqual(body["instance_info"]["base_image_uuid"], "base-image-test")
        self.assertEqual(body["instance_info"]["cg_application_uuid"], "")
        self.assertEqual(body["price_info"]["expand_data_disk"], 40)

    def test_private_image_preview(self):
        result = plan_rental("machine", "image-private", private_image=True)
        self.assertEqual(result["body"]["instance_info"]["private_image_uuid"], "image-private")
        self.assertEqual(result["body"]["instance_info"]["base_image_uuid"], "")

    def test_preview_validation(self):
        for kwargs in ({"gpu_amount": 0}, {"expand_data_disk": -1}, {"gpu_amount": True}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                plan_rental("machine", "base-image", **kwargs)
        for machine, image in (("", "image"), ("machine", "")):
            with self.assertRaises(ValueError):
                plan_rental(machine, image)

    def test_offline_plan_cli(self):
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(["plan", "--machine-id", "machine", "--image", "base-image"]), 0)
        self.assertTrue(json.loads(output.getvalue())["dry_run"])

    def test_classic_creation_uses_reviewed_contract_once(self):
        requests = []
        def response(request):
            requests.append(request)
            return httpx.Response(200, json={"code": "Success", "data": "instance-created"})
        with AutoDLClient("fake-web-session", transport=httpx.MockTransport(response)) as client:
            result = instance.create_instance(client, machine_id="machine", base_image_uuid="image")
        self.assertEqual(result["instance_uuid"], "instance-created")
        self.assertEqual(len(requests), 1)
        self.assertEqual(str(requests[0].url), "https://www.autodl.com/api/v1/order/instance/create/payg")
        self.assertEqual(requests[0].headers["Authorization"], "fake-web-session")
        self.assertEqual(requests[0].headers["AppVersion"], "v6.53.0")

    def test_classic_lifecycle_paths(self):
        requests = []
        def response(request):
            requests.append(request)
            return httpx.Response(200, json={"code": "Success", "data": None})
        with AutoDLClient("fake-web-session", transport=httpx.MockTransport(response)) as client:
            instance.power_on(client, "instance-test")
            instance.power_off(client, "instance-test")
            instance.release_instance(client, "instance-test")
        self.assertEqual([request.url.path for request in requests], [
            "/api/v1/instance/power_on", "/api/v1/instance/power_off", "/api/v1/instance/release"])
        for request in requests:
            self.assertEqual(json.loads(request.content), {"instance_uuid": "instance-test"})

    def test_upstream_does_not_retry_timeout(self):
        attempts = []
        def response(request):
            attempts.append(request)
            raise httpx.ReadTimeout("unknown outcome")
        with AutoDLClient("fake-web-session", transport=httpx.MockTransport(response)) as client:
            with self.assertRaises(Exception):
                instance.create_instance(client, machine_id="machine", base_image_uuid="image")
        self.assertEqual(len(attempts), 1)

    def test_scrub_filters_token_even_when_showing_instance_credentials(self):
        source = {"password": "instance-secret", "nested": [{"token": "web-token", "echo": "web-token"}]}
        masked = scrub(source, token="web-token")
        self.assertNotIn("instance-secret", json.dumps(masked))
        shown = scrub(source, token="web-token", allow_secrets=True)
        self.assertEqual(shown["password"], "instance-secret")
        self.assertNotIn("web-token", json.dumps(shown))


class MCPTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.environment = patch.dict(os.environ, {"AUTODL_CLI_HOME": self.directory.name})
        self.environment.start()
        self.addCleanup(self.environment.stop)

    async def discover(self, **kwargs):
        from mcp import Client
        async with Client(build_server(**kwargs), raise_exceptions=True) as client:
            return (await client.list_tools()).tools

    async def test_readonly_discovery_excludes_auth_config_raw_and_mutations(self):
        tools = await self.discover()
        names = [tool.name for tool in tools]
        self.assertIn("plan_rental", names)
        self.assertTrue(any("gpu_machines" in name for name in names))
        for word in ("auth", "config", "tools", "create", "release", "power_on", "power_off", "autodl_run"):
            self.assertFalse(any(word in name for name in names), (word, names))

    async def test_writes_enabled_but_no_generic_escape_hatches(self):
        names = [tool.name for tool in await self.discover(allow_writes=True)]
        self.assertTrue(any("instance_create" in name for name in names))
        self.assertTrue(any("instance_release" in name for name in names))
        self.assertFalse(any("_run" in name or "_auth" in name or "_config" in name for name in names))

    async def test_preview_over_protocol_without_credentials(self):
        from mcp import Client
        async with Client(build_server(), raise_exceptions=True) as client:
            result = await client.call_tool("plan_rental", {"machine_id": "machine", "image_uuid": "image"})
        self.assertFalse(result.is_error)
        self.assertTrue(result.structured_content["dry_run"])

    async def test_missing_credentials_produces_tool_error(self):
        from mcp import Client
        async with Client(build_server(), raise_exceptions=True) as client:
            tool = next(t for t in (await client.list_tools()).tools if "instance_list" in t.name)
            result = await client.call_tool(tool.name, {"json": True})
        self.assertTrue(result.is_error)
        self.assertIn("Not authenticated", result.content[0].text)

    async def test_generated_cli_json_and_secret_filtering(self):
        from mcp import Client
        process = subprocess.CompletedProcess([], 0, json.dumps({"root_password": "private", "uuid": "instance-test"}), "")
        with patch("autodl_classic_agent.server.subprocess.run", return_value=process) as run:
            async with Client(build_server(), raise_exceptions=True) as client:
                tool = next(t for t in (await client.list_tools()).tools if "instance_list" in t.name)
                result = await client.call_tool(tool.name, {"json": True})
        self.assertFalse(result.is_error)
        self.assertNotIn("private", result.content[0].text)
        self.assertIs(run.call_args.kwargs["stdin"], subprocess.DEVNULL)
        self.assertNotIn("shell", run.call_args.kwargs)

    async def test_timeout_flags_uncertain_mutation(self):
        from mcp import Client
        with patch("autodl_classic_agent.server.subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 1)):
            async with Client(build_server(allow_writes=True), raise_exceptions=True) as client:
                tool = next(t for t in (await client.list_tools()).tools if "instance_power_on" in t.name)
                result = await client.call_tool(tool.name, {"instance_uuid": "instance-test"})
        self.assertTrue(result.is_error)
        self.assertIn("uncertain", result.content[0].text)

    async def test_generated_create_passes_explicit_machine_and_image(self):
        from mcp import Client
        process = subprocess.CompletedProcess([], 0, '{"instance_uuid":"instance-test"}', "")
        with patch("autodl_classic_agent.server.subprocess.run", return_value=process) as run:
            async with Client(build_server(allow_writes=True), raise_exceptions=True) as client:
                tool = next(t for t in (await client.list_tools()).tools if "instance_create" in t.name)
                result = await client.call_tool(tool.name, {
                    "machine_id": "machine-selected", "image": "base-image-selected", "gpu_num": 2,
                })
        self.assertFalse(result.is_error)
        command = run.call_args.args[0]
        self.assertIn("--machine-id=machine-selected", command)
        self.assertIn("--image=base-image-selected", command)
        self.assertIn("--gpu-num=2", command)

    async def test_hidden_terminal_auth_import_stores_no_password(self):
        from autodl_cli.config import load_config, config_path
        token = "eyJaaa.bbb.ccc"
        terminal = io.StringIO()
        terminal.isatty = lambda: True
        output = io.StringIO()
        with patch("sys.stdin", terminal), patch("getpass.getpass", return_value="Authorization: " + token), redirect_stdout(output):
            with self.assertRaises(SystemExit) as caught:
                main(["--json", "auth", "paste", "--no-verify"])
        self.assertEqual(caught.exception.code, 0)
        self.assertEqual(load_config()["token"], token)
        self.assertNotIn("password", load_config())
        self.assertEqual(config_path().stat().st_mode & 0o777, 0o600)
        self.assertNotIn(token, output.getvalue())

    async def test_foreign_host_is_refused_before_subprocess(self):
        from autodl_cli.config import save_config
        from mcp import Client
        save_config({"base_url": "https://example.com", "token": "private-web-token"})
        with patch("autodl_classic_agent.server.subprocess.run", side_effect=AssertionError("Must not run")):
            async with Client(build_server(), raise_exceptions=True) as client:
                tool = next(t for t in (await client.list_tools()).tools if "instance_list" in t.name)
                result = await client.call_tool(tool.name, {})
        self.assertTrue(result.is_error)
        self.assertNotIn("private-web-token", result.content[0].text)

    async def test_real_stdio_subprocess(self):
        from mcp import Client
        from mcp.client.stdio import StdioServerParameters
        params = StdioServerParameters(command=sys.executable, args=["-m", "autodl_classic_agent.server", "--allow-writes"],
            env={**os.environ, "AUTODL_CLI_HOME": self.directory.name})
        async with Client(params, mode="legacy", read_timeout_seconds=15) as client:
            tools = (await client.list_tools()).tools
            self.assertTrue(any("instance_create" in tool.name for tool in tools))
            result = await client.call_tool("plan_rental", {"machine_id": "machine", "image_uuid": "image"})
            self.assertFalse(result.is_error)
