"""AutoDL GPU rental CLI with private session input and offline order previews."""

import argparse
import getpass
import json
import sys


def plan_rental(machine_id: str, image_uuid: str, *, private_image: bool = False,
                gpu_amount: int = 1, expand_data_disk: int = 0, name: str = "") -> dict:
    """Capture the pinned upstream create handler's request without HTTP or credentials."""
    from autodl_cli.handlers.instance import create_instance

    if type(gpu_amount) is not int or type(expand_data_disk) is not int:
        raise ValueError("GPU count and extra disk GB must be integers.")
    request = {}

    class CaptureClient:
        def request(self, method, path, **kwargs):
            request.update(method=method, url="https://www.autodl.com" + path, body=kwargs["json"])
            return {"code": "Success", "data": "instance-dry-run", "msg": ""}

    create_instance(CaptureClient(), machine_id=machine_id,
        base_image_uuid="" if private_image else image_uuid,
        private_image_uuid=image_uuid if private_image else "", gpu_amount=gpu_amount,
        expand_data_disk=expand_data_disk, instance_name=name)
    return {"dry_run": True, "product": "classic", "billing": "payg", **request}


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    without_json = [item for item in args if item != "--json"]
    if len(without_json) >= 2 and without_json[0] == "auth" and without_json[1] in {"login", "export", "import", "ipad-script"}:
        from .login import auth_command
        return auth_command(without_json[1:])
    if args == ["--version"]:
        from . import __version__
        print(f"autodl {__version__} (backend autodl-cli 0.1.0)")
        return 0
    if args and args[0] == "plan":
        parser = argparse.ArgumentParser(description="Preview a classic PAYG order; no token or network.")
        parser.add_argument("--machine-id", required=True)
        parser.add_argument("--image", required=True)
        parser.add_argument("--private-image", action="store_true", help="Interpret --image as a private image UUID")
        parser.add_argument("--gpu-num", type=int, default=1)
        parser.add_argument("--data-disk", type=int, default=0)
        parser.add_argument("--name", default="")
        opts = parser.parse_args(args[1:])
        try:
            print(json.dumps(plan_rental(opts.machine_id, opts.image, private_image=opts.private_image,
                gpu_amount=opts.gpu_num, expand_data_disk=opts.data_disk, name=opts.name), ensure_ascii=False))
            return 0
        except ValueError as exc:
            print(json.dumps({"error": str(exc)}))
            return 2
    # The upstream paste command uses stdin.read; hide one-line Authorization input on a terminal.
    if without_json[:2] == ["auth", "paste"] and sys.stdin.isatty():
        import io
        from autodl_cli.main import main as upstream
        header = getpass.getpass("AutoDL WEB Authorization header/token (hidden): ")
        original = sys.stdin
        try:
            sys.stdin = io.StringIO(header + "\n")
            upstream(args=args, prog_name="autodl")
        finally:
            sys.stdin = original
        return 0
    from .instance_cli import console_cli
    console_cli(args=args, prog_name="autodl")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
