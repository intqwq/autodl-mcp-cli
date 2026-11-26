"""Additional classic instance operations from the ordinary web console."""

from datetime import datetime, timedelta, timezone

from autodl_cli.client import AutoDLClient
from autodl_cli.errors import APIError
from autodl_cli.handlers._common import require_success, require_success_any
from autodl_cli.handlers.instance import get_instance, list_instances

GIB = 1024 ** 3
CHINA_TIME = timezone(timedelta(hours=8))
CLONE_PATH = "/api/v1/order/instance/clone/payg"
DISK_CHANGE_PATH = "/api/v1/order/data_disk/change"
RESETTABLE_STATES = {
    "shutdown", "shutdown_by_starting_error", "shutdown_by_running_error",
    "re_init_failed",
}
STOPPED = RESETTABLE_STATES | {"create_failed"}


def identifier(value: str, label: str = "Instance UUID") -> str:
    value = value.strip()
    if not value:
        raise ValueError(f"{label} must not be blank.")
    return value


def find_instance(client: AutoDLClient, instance_uuid: str) -> dict:
    for entry in list_instances(client, query=instance_uuid):
        if entry.get("uuid") == instance_uuid:
            return entry
    raise ValueError(f"No ordinary instance with UUID {instance_uuid} was found in your account.")


def submit(client: AutoDLClient, method: str, path: str, body: dict, action: str) -> object:
    return require_success_any(client.request(method, path, json=body), action=action)


def start_without_gpu(client: AutoDLClient, instance_uuid: str) -> dict:
    instance_uuid = identifier(instance_uuid)
    submit(client, "POST", "/api/v1/instance/power_on",
           {"instance_uuid": instance_uuid, "payload": "non_gpu"}, "start without GPU")
    return {"instance_uuid": instance_uuid, "start_mode": "non_gpu", "accepted": True}


def monitor_instance(client: AutoDLClient, instance_uuid: str) -> dict:
    instance_uuid = identifier(instance_uuid)
    response = client.request("GET", "/api/v1/instance/monitor", params={"instance_uuid": instance_uuid})
    return require_success(response, action="instance monitor")


def rename_instance(client: AutoDLClient, instance_uuid: str, name: str) -> dict:
    instance_uuid = identifier(instance_uuid)
    name = name.strip()
    if not name or len(name.encode("utf-16-le")) // 2 > 32:
        raise ValueError("Instance name must be nonempty and fit the console's 32-character limit.")
    body = {"instance_uuid": instance_uuid, "instance_name": name}
    submit(client, "PUT", "/api/v1/instance/name", body, "rename instance")
    return {**body, "accepted": True}


def reset_instance(client: AutoDLClient, instance_uuid: str) -> dict:
    """Restore a stopped ordinary instance's system disk from its configured image."""
    instance_uuid = identifier(instance_uuid)
    entry = find_instance(client, instance_uuid)
    if entry.get("status") not in RESETTABLE_STATES:
        raise ValueError("Reset requires a stopped instance or an instance whose previous reset failed.")
    submit(client, "POST", "/api/v1/instance/init", {"instance_uuid": instance_uuid}, "reset instance system disk")
    return {"instance_uuid": instance_uuid, "accepted": True}


def timed_shutdown(client: AutoDLClient, instance_uuid: str, at: str | None) -> dict:
    instance_uuid = identifier(instance_uuid)
    shutdown_at = None
    if at is not None:
        try:
            timestamp = datetime.fromisoformat(at)
        except ValueError:
            raise ValueError("Use an ISO 8601 time with an offset, for example 2027-01-01T20:30+08:00.") from None
        if timestamp.utcoffset() is None or timestamp.second or timestamp.microsecond:
            raise ValueError("Include a UTC offset and specify the time to the minute.")
        china_timestamp = timestamp.astimezone(CHINA_TIME)
        if china_timestamp <= datetime.now(CHINA_TIME):
            raise ValueError("Shutdown time must be in the future.")
        shutdown_at = china_timestamp.strftime("%Y-%m-%d %H:%M")
    submit(client, "POST", "/api/v1/instance/timed/shutdown",
           {"instance_uuid": instance_uuid, "shutdown_at": shutdown_at}, "update timed shutdown")
    return {"instance_uuid": instance_uuid, "shutdown_at": shutdown_at,
            "timezone": "UTC+08:00", "accepted": True}


def expanded_bytes(record: dict) -> int:
    size = record.get("expand_data_disk_size")
    if type(size) is not int or size < 0:
        raise APIError("AutoDL did not return the current data disk expansion size.")
    return size


def clone_instance(client: AutoDLClient, instance_uuid: str, machine_id: str, *, gpu_num: int,
                   copy_data_disk: bool, data_disk: int | None, preview: bool) -> dict:
    instance_uuid = identifier(instance_uuid)
    machine_id = identifier(machine_id, "Destination machine ID")
    source = find_instance(client, instance_uuid)
    if source.get("status") not in STOPPED:
        raise ValueError("Shut down the source instance and verify its status before cloning.")
    if source.get("disk_health_status") == "alert":
        raise ValueError("AutoDL reports a system disk warning on the source. Clear space before cloning.")
    snapshot = get_instance(client, instance_uuid)
    image = snapshot.get("image")
    if not isinstance(image, dict):
        raise APIError("AutoDL did not return the source image metadata needed for cloning.")
    if data_disk is not None:
        disk_bytes = data_disk * GIB
    else:
        disk_bytes = expanded_bytes(source) if copy_data_disk else 0
    price_info = {
        "coupon_id_list": [], "machine_id": machine_id, "charge_type": "payg",
        "duration": 1, "num": gpu_num, "expand_data_disk": disk_bytes,
    }
    body = {
        "instance_uuid": instance_uuid,
        "instance_info": {
            "machine_id": machine_id,
            "charge_type": "payg",
            "req_gpu_amount": gpu_num,
            "base_image_uuid": (image.get("image_name") or "") if image.get("image_type") == "public" else "",
            "instance_name": "",
            "private_image_uuid": source.get("private_image_uuid") or "",
            "reproduction_uuid": source.get("reproduction_uuid") or "",
            "cg_application_uuid": snapshot.get("cg_application_uuid") or "",
            "cg_application_info": snapshot.get("cg_application_info") or {},
            "expand_data_disk": disk_bytes,
            "copy_data_disk_after_clone": copy_data_disk,
            "keep_src_user_service_address_after_clone": False,
            "reproduction_id": source.get("reproduction_id") or 0,
            "ft_sparse": False,
        },
        "price_info": price_info,
    }
    if preview:
        price = client.request("POST", "/api/v1/order/price/preview", json=price_info)
        return {"dry_run": True, "body": body,
                "destination_price_preview": require_success(price, action="destination price preview")}
    new_uuid = submit(client, "POST", CLONE_PATH, body, "clone instance")
    if not isinstance(new_uuid, str) or not new_uuid.strip():
        raise APIError("AutoDL accepted the clone but returned no destination UUID. Check instance list before retrying.")
    return {"source_instance_uuid": instance_uuid, "instance_uuid": new_uuid.strip(),
            "machine_id": machine_id, "copy_data_disk": copy_data_disk, "accepted": True}


def grow_data_disk(client: AutoDLClient, instance_uuid: str, add_gib: int, *, preview: bool) -> dict:
    instance_uuid = identifier(instance_uuid)
    entry = find_instance(client, instance_uuid)
    machine_id = entry.get("machine_id")
    if not isinstance(machine_id, str) or not machine_id:
        raise APIError("AutoDL did not return the instance's machine ID.")
    current = expanded_bytes(get_instance(client, instance_uuid))
    delta = add_gib * GIB
    body = {"instance_uuid": instance_uuid, "machine_id": machine_id, "opt_type": "data_disk_expand",
            "change_size": delta, "data_disk_expand_size": current + delta}
    quote = require_success(client.request("POST", f"{DISK_CHANGE_PATH}/preview", json=body),
                            action="data disk expansion quote")
    if preview:
        return {"instance_uuid": instance_uuid, "add_gib": add_gib, "quote": quote}
    max_expand = quote.get("max_expand_size")
    if type(max_expand) is not int or delta > max_expand:
        raise ValueError("The requested growth exceeds the available expansion, or AutoDL did not report a limit.")
    # The preview uses the total expansion for pricing; the write uses only the delta.
    body["data_disk_expand_size"] = delta
    submit(client, "POST", DISK_CHANGE_PATH, body, "expand data disk")
    return {"instance_uuid": instance_uuid, "add_gib": add_gib, "accepted": True}
