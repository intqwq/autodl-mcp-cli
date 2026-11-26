"""Remove the known original Art tool, preserving all credentials and classic tools."""

import os
from pathlib import Path
import shutil


def uninstall(root: Path, bin_dir: Path) -> list[str]:
    if not root.is_absolute() or root.is_symlink() or root in {Path("/"), Path.home(), bin_dir}:
        raise ValueError("Refusing an unsafe original-install path.")
    messages = []
    environment = root / "venv"
    if environment.exists():
        if environment.is_symlink() or not (environment / "pyvenv.cfg").is_file():
            raise ValueError("The target is not the original installer's virtual environment.")
        metadata = list(environment.glob("lib/python*/site-packages/autodl_agent-*.dist-info/METADATA"))
        if not any("\nName: autodl-agent\n" in "\n" + item.read_text() for item in metadata):
            raise ValueError("The target does not contain the original autodl-agent package; left untouched.")
    for command in ("autodl", "autodl-mcp"):
        link = bin_dir / command
        target = environment / "bin" / command
        if link.is_symlink() and Path(os.readlink(link)) == target:
            link.unlink()
            messages.append(f"Removed {link}")
        elif link.exists() or link.is_symlink():
            messages.append(f"Preserved unrelated command {link}")
    if environment.exists():
        shutil.rmtree(environment)
        messages.append(f"Removed {environment}")
    if root.exists():
        try:
            root.rmdir()
        except OSError:
            messages.append(f"Preserved other files under {root}")
    messages.append("Credential files, classic CLI, and rented instances were not changed.")
    return messages


if __name__ == "__main__":
    try:
        root = Path(os.environ.get("AUTODL_INSTALL_ROOT", str(Path.home() / ".local/share/autodl-agent"))).expanduser()
        bin_dir = Path(os.environ.get("AUTODL_BIN_DIR", str(Path.home() / ".local/bin"))).expanduser()
        print("\n".join(uninstall(root, bin_dir)))
    except (ValueError, OSError) as exc:
        raise SystemExit(str(exc))
