"""Offline tests for the added console endpoints and their MCP permissions."""

import json
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import httpx
from click.testing import CliRunner
from mcp import Client

from autodl_cli.client import AutoDLClient
from autodl_cli.errors import APIError
from autodl_classic_agent import instance_ops as ops
from autodl_classic_agent.instance_cli import console_cli
from autodl_classic_agent.server import build_server


def response(data):
    return httpx.Response(200, json={"code": "Success", "data": data})


class InstanceOperationTests(unittest.TestCase):
    def setUp(self):
        self.requests = []
        self.source = {"uuid": "source", "status": "shutdown", "machine_id": "source-machine",
                       "expand_data_disk_size": 20 * ops.GIB}
        self.snapshot = {"image": {"image_type": "public", "image_name": "base-image-test"},
                         "expand_data_disk_size": 20 * ops.GIB}
        self.max_growth = 30 * ops.GIB
        self.client = AutoDLClient("synthetic-test-session", transport=httpx.MockTransport(self.handle))
        self.addCleanup(self.client.close)

    def handle(self, request):
        path = request.url.path
        body = json.loads(request.content) if request.content else None
        self.requests.append((request.method, path, body))
        if path == "/api/v1/instance":
            return response({"list": [self.source], "max_page": 1})
        if path == "/api/v1/instance/snapshot":
            self.assertEqual(request.url.params["instance_uuid"], "source")
            return response(self.snapshot)
        if path == "/api/v1/order/price/preview":
            return response({"instance_final": 1000})
        if path == ops.CLONE_PATH:
            return response("new-instance")
        if path == ops.DISK_CHANGE_PATH + "/preview":
            return response({"max_expand_size": self.max_growth, "data_disk_deal_daily_price": 100})
        if path == "/api/v1/instance/monitor":
            self.assertEqual(request.url.params["instance_uuid"], "source")
            return response({"uuid": "source", "UsageInfo": {"mem_usage": 123}})
        if path in ("/api/v1/instance/power_on", "/api/v1/instance/name",
                    "/api/v1/instance/timed/shutdown", "/api/v1/instance/init", ops.DISK_CHANGE_PATH):
            return response(None)
        self.fail(f"Unexpected request {request.method} {path}")

    def test_cli_keeps_default_power_on_and_sends_explicit_no_gpu_mode(self):
        runner = CliRunner()
        with patch("autodl_classic_agent.instance_cli.load_config", return_value={"token": "fixture"}), \
                patch("autodl_classic_agent.instance_cli.build_client", return_value=self.client):
            result = runner.invoke(console_cli, ["--json", "instance", "power-on", "source", "--no-gpu"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(json.loads(result.stdout)["start_mode"], "non_gpu")
        self.assertEqual(self.requests, [("POST", "/api/v1/instance/power_on",
                                        {"instance_uuid": "source", "payload": "non_gpu"})])
        with patch("autodl_cli.commands.instance.load_config", return_value={"token": "fixture"}), \
                patch("autodl_cli.handlers.instance.power_on", return_value={"instance_uuid": "source", "powered_on": True}) as power_on:
            default = runner.invoke(console_cli, ["--json", "instance", "power-on", "source"])
        self.assertEqual(default.exit_code, 0, default.output)
        self.assertTrue(json.loads(default.stdout)["powered_on"])
        self.assertEqual(power_on.call_args.args[1], "source")

    def test_no_gpu_rejection_never_retries_in_gpu_mode(self):
        attempts = []

        def reject(request):
            attempts.append(json.loads(request.content))
            return httpx.Response(200, json={"code": "WrongStartMode", "msg": "Not available"})

        with AutoDLClient(transport=httpx.MockTransport(reject)) as client, self.assertRaises(APIError):
            ops.start_without_gpu(client, "source")
        self.assertEqual(attempts, [{"instance_uuid": "source", "payload": "non_gpu"}])

    def test_clone_plans_without_ordering_and_matches_the_order_body(self):
        options = {"gpu_num": 2, "copy_data_disk": True, "data_disk": None}
        plan = ops.clone_instance(self.client, "source", "destination", preview=True, **options)
        self.assertTrue(plan["dry_run"])
        self.assertEqual([path for _, path, _ in self.requests], [
            "/api/v1/instance", "/api/v1/instance/snapshot", "/api/v1/order/price/preview"])
        self.assertEqual(plan["body"]["price_info"]["num"], 2)
        self.assertEqual(plan["body"]["price_info"]["expand_data_disk"], 20 * ops.GIB)
        info = plan["body"]["instance_info"]
        self.assertEqual(info["base_image_uuid"], "base-image-test")
        self.assertTrue(info["copy_data_disk_after_clone"])
        self.assertFalse(info["keep_src_user_service_address_after_clone"])
        clone = ops.clone_instance(self.client, "source", "destination", preview=False, **options)
        self.assertEqual(self.requests[-1], ("POST", ops.CLONE_PATH, plan["body"]))
        self.assertEqual(clone["instance_uuid"], "new-instance")
        self.assertEqual(sum(path == ops.CLONE_PATH for _, path, _ in self.requests), 1)

    def test_running_clone_source_is_rejected_before_any_order(self):
        self.source["status"] = "running"
        with self.assertRaisesRegex(ValueError, "Shut down"):
            ops.clone_instance(self.client, "source", "destination", gpu_num=1,
                               copy_data_disk=False, data_disk=None, preview=False)
        self.assertEqual([path for _, path, _ in self.requests], ["/api/v1/instance"])

    def test_disk_preview_prices_total_expansion_but_write_uses_only_delta(self):
        ops.grow_data_disk(self.client, "source", 5, preview=True)
        self.assertEqual(self.requests[-1][1], ops.DISK_CHANGE_PATH + "/preview")
        self.assertEqual(self.requests[-1][2]["data_disk_expand_size"], 25 * ops.GIB)
        self.assertFalse(any(path == ops.DISK_CHANGE_PATH for _, path, _ in self.requests))
        ops.grow_data_disk(self.client, "source", 5, preview=False)
        self.assertEqual(self.requests[-1][1], ops.DISK_CHANGE_PATH)
        self.assertEqual(self.requests[-1][2]["data_disk_expand_size"], 5 * ops.GIB)
        self.max_growth = 4 * ops.GIB
        with self.assertRaisesRegex(ValueError, "exceeds"):
            ops.grow_data_disk(self.client, "source", 5, preview=False)
        self.assertEqual(sum(path == ops.DISK_CHANGE_PATH for _, path, _ in self.requests), 1)

    def test_timed_shutdown_converts_offset_and_cancel_sends_null(self):
        ops.timed_shutdown(self.client, "source", "2099-06-20T17:00+09:00")
        self.assertEqual(self.requests[-1][2]["shutdown_at"], "2099-06-20 16:00")
        ops.timed_shutdown(self.client, "source", None)
        self.assertIsNone(self.requests[-1][2]["shutdown_at"])
        with self.assertRaisesRegex(ValueError, "offset"):
            ops.timed_shutdown(self.client, "source", "2099-06-20T17:00")
        self.assertEqual(len(self.requests), 2)

    def test_monitor_queries_live_endpoint_and_rename_uses_put(self):
        stats = ops.monitor_instance(self.client, "source")
        self.assertEqual(stats["UsageInfo"]["mem_usage"], 123)
        ops.rename_instance(self.client, "source", "Experiment 2")
        self.assertEqual(self.requests[-1], ("PUT", "/api/v1/instance/name",
                                            {"instance_uuid": "source", "instance_name": "Experiment 2"}))

    def test_reset_requires_confirmation_and_submits_one_request_for_exact_uuid(self):
        runner = CliRunner()
        with patch("autodl_classic_agent.instance_cli.load_config", return_value={"token": "fixture"}), \
                patch("autodl_classic_agent.instance_cli.build_client", return_value=self.client) as build:
            declined = runner.invoke(console_cli, ["instance", "reset", "source"])
            self.assertEqual(declined.exit_code, 2)
            self.assertIn("erases system disk changes", declined.output)
            build.assert_not_called()
            accepted = runner.invoke(console_cli, ["--json", "instance", "reset", "source", "--yes"])
        self.assertEqual(accepted.exit_code, 0, accepted.output)
        self.assertEqual(json.loads(accepted.stdout), {"instance_uuid": "source", "accepted": True})
        self.assertEqual([path for _, path, _ in self.requests], ["/api/v1/instance", "/api/v1/instance/init"])
        self.assertEqual(self.requests[-1], ("POST", "/api/v1/instance/init", {"instance_uuid": "source"}))

    def test_reset_refuses_running_and_wrong_instances_without_sending_init(self):
        self.source["status"] = "running"
        with self.assertRaisesRegex(ValueError, "stopped instance"):
            ops.reset_instance(self.client, "source")
        with self.assertRaisesRegex(ValueError, "No ordinary instance"):
            ops.reset_instance(self.client, "sour")
        self.assertEqual([path for _, path, _ in self.requests], ["/api/v1/instance"] * 2)


class NewMCPToolsTests(unittest.IsolatedAsyncioTestCase):
    async def test_read_only_previews_and_write_opt_in(self):
        async with Client(build_server(), raise_exceptions=True) as client:
            names = {tool.name for tool in (await client.list_tools()).tools}
            self.assertTrue({"autodl_instance_clone_plan", "autodl_instance_disk_quote",
                             "autodl_instance_monitor"} <= names)
            self.assertTrue({"autodl_instance_clone", "autodl_instance_disk_grow",
                             "autodl_instance_shutdown_at", "autodl_instance_rename",
                             "autodl_instance_reset"}.isdisjoint(names))
        with tempfile.TemporaryDirectory() as directory, \
                patch.dict("os.environ", {"AUTODL_CLI_HOME": directory}), \
                patch("autodl_classic_agent.server.subprocess.run",
                      return_value=subprocess.CompletedProcess([], 0, '{"accepted":true}', "")) as run:
            async with Client(build_server(allow_writes=True), raise_exceptions=True) as client:
                result = await client.call_tool("autodl_instance_power_on", {"instance_uuid": "source", "no_gpu": True})
                self.assertFalse(result.is_error, result)
                self.assertIn("--no-gpu", run.call_args.args[0])
                result = await client.call_tool("autodl_instance_clone", {"instance_uuid": "source",
                    "machine_id": "dest", "gpu_num": 2, "copy_data_disk": True})
                self.assertFalse(result.is_error, result)
                args = run.call_args.args[0]
                self.assertIn("--gpu-num=2", args)
                self.assertIn("--copy-data-disk", args)
                self.assertNotIn("--data-disk", args)
                result = await client.call_tool("autodl_instance_reset", {"instance_uuid": "source", "yes": True})
                self.assertFalse(result.is_error, result)
                self.assertIn("--yes", run.call_args.args[0])
