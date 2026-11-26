#!/usr/bin/env python3
"""Build the installer archive and checksums from a clean, committed checkout."""

import argparse
import ast
import gzip
import hashlib
from pathlib import Path
import re
import subprocess
import tomllib


ROOT = Path(__file__).resolve().parents[1]


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(ROOT), *args])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    version = project["version"]
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
        raise SystemExit("Release version must have the form MAJOR.MINOR.PATCH.")
    module = ast.parse((ROOT / "src/autodl_classic_agent/__init__.py").read_text())
    module_versions = [ast.literal_eval(node.value) for node in module.body
                       if isinstance(node, ast.Assign)
                       and any(isinstance(t, ast.Name) and t.id == "__version__" for t in node.targets)]
    if module_versions != [version]:
        raise SystemExit("Package and module versions disagree.")
    if git("status", "--porcelain").strip():
        raise SystemExit("Commit the source changes before creating release assets.")
    git("rev-parse", "--verify", "HEAD")
    tracked = git("ls-files", "-z").decode().split("\0")
    for item in filter(None, tracked):
        name = Path(item).name
        if (name in {".env", ".pypirc", "config.toml"} or name.endswith(".pem")
                or (name.startswith("session") and name.endswith(".json"))):
            raise SystemExit(f"Refusing to publish a credential-like file: {item}")
    args.dist.mkdir(parents=True, exist_ok=True)
    stem = re.sub(r"[-_.]+", "_", project["name"])
    assets = [args.dist / f"{stem}-{version}-py3-none-any.whl",
              args.dist / f"{stem}-{version}.tar.gz"]
    for asset in assets:
        if not asset.is_file() or asset.is_symlink():
            raise SystemExit(f"Build and check the wheel and sdist first; missing {asset.name}")
    archive = args.dist / f"autodl-{version}.tar.gz"
    payload = git("archive", "--format=tar", f"--prefix=autodl-{version}/", "HEAD")
    archive.write_bytes(gzip.compress(payload, mtime=0))
    assets.append(archive)
    checksums = args.dist / "SHA256SUMS"
    checksums.write_text("".join(
        f"{hashlib.sha256(asset.read_bytes()).hexdigest()}  {asset.name}\n"
        for asset in sorted(assets)), encoding="utf-8")
    for asset in [*assets, checksums]:
        print(f"{asset.name} ({asset.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
