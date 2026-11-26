"""Add console operations to the pinned backend's instance command group."""

from copy import copy
from typing import Callable

import click
from autodl_cli import output
from autodl_cli.commands._helpers import build_client, require_token
from autodl_cli.config import get_base_url, load_config
from autodl_cli.errors import AutoDLError
from autodl_cli.main import main as upstream

from . import instance_ops as ops

# Keep the upstream command objects intact for users who also use that module.
console_cli = copy(upstream)
console_cli.commands = upstream.commands.copy()
instance = copy(upstream.commands["instance"])
instance.commands = instance.commands.copy()
console_cli.add_command(instance)
original_power_on = instance.commands["power-on"]


def render(operation: Callable, *args, **kwargs) -> None:
    """Run one console operation with the saved web session and emit JSON."""
    config = load_config()
    if get_base_url(config) != "https://www.autodl.com":
        raise click.ClickException("These console operations require https://www.autodl.com.")
    token = require_token(config)
    try:
        with build_client(token, config) as client:
            result = operation(client, *args, **kwargs)
    except (ValueError, AutoDLError) as exc:
        raise click.ClickException(str(exc).replace(token, "[REDACTED]")) from None
    output.render_json(result)


@instance.command("power-on", help="Start an instance. No-GPU mode is billable and requires a stopped PAYG instance.")
@click.argument("instance_uuid")
@click.option("--no-gpu", is_flag=True, help="Request CPU-only boot. Never falls back to GPU mode.")
@click.pass_context
def power_on(ctx: click.Context, instance_uuid: str, no_gpu: bool) -> None:
    if no_gpu:
        render(ops.start_without_gpu, instance_uuid)
    else:
        ctx.invoke(original_power_on, instance_uuid=instance_uuid)


@instance.command("monitor", help="Read a live instance snapshot with CPU, RAM, GPU count, and disk usage.")
@click.argument("instance_uuid")
def monitor(instance_uuid: str) -> None:
    render(ops.monitor_instance, instance_uuid)


@instance.command("rename", help="Change an ordinary instance's display name.")
@click.argument("instance_uuid")
@click.argument("name")
def rename(instance_uuid: str, name: str) -> None:
    render(ops.rename_instance, instance_uuid, name)


@instance.command("reset", help="Restore a stopped instance from its image, erasing changes on its system disk.")
@click.argument("instance_uuid")
@click.option("--yes", is_flag=True, help="Confirm erasure of system disk changes for this instance.")
def reset(instance_uuid: str, yes: bool) -> None:
    if not yes:
        raise click.UsageError("Reset erases system disk changes. Pass --yes to confirm for this instance.")
    render(ops.reset_instance, instance_uuid)


@instance.command("shutdown-at", help="Schedule a provider-side shutdown at an ISO 8601 time with a UTC offset.")
@click.argument("instance_uuid")
@click.argument("at")
def shutdown_at(instance_uuid: str, at: str) -> None:
    render(ops.timed_shutdown, instance_uuid, at)


@instance.command("cancel-shutdown", help="Cancel an instance's provider-side shutdown timer.")
@click.argument("instance_uuid")
def cancel_shutdown(instance_uuid: str) -> None:
    render(ops.timed_shutdown, instance_uuid, None)


def clone_command(name: str, help: str, *, preview: bool) -> None:
    @instance.command(name, help=help)
    @click.argument("instance_uuid")
    @click.option("--machine-id", required=True, help="Destination machine ID from gpu machines.")
    @click.option("--gpu-num", type=click.IntRange(min=1), default=1, help="Number of GPUs on the new instance.")
    @click.option("--copy-data-disk", is_flag=True, help="Copy the data disk as well as the system disk.")
    @click.option("--data-disk", type=click.IntRange(min=0),
                  help="Extra destination disk GiB. Defaults to the source expansion when copying the data disk.")
    def command(instance_uuid, machine_id, gpu_num, copy_data_disk, data_disk):
        render(ops.clone_instance, instance_uuid, machine_id, gpu_num=gpu_num,
               copy_data_disk=copy_data_disk, data_disk=data_disk, preview=preview)


clone_command("clone-plan", "Preview a clone request and destination PAYG pricing without placing an order.", preview=True)
clone_command("clone", "Place a billable PAYG clone order for a stopped source on an explicit destination machine.", preview=False)


def disk_command(name: str, help: str, *, preview: bool) -> None:
    @instance.command(name, help=help)
    @click.argument("instance_uuid")
    @click.option("--add-gib", required=True, type=click.IntRange(min=1), help="Additional data disk GiB.")
    def command(instance_uuid, add_gib):
        render(ops.grow_data_disk, instance_uuid, add_gib, preview=preview)


disk_command("disk-quote", "Read pricing and the expansion limit for adding space to a data disk.", preview=True)
disk_command("disk-grow", "Expand the data disk after checking capacity. Can incur charges and require a restart.", preview=False)
