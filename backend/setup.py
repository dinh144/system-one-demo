from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from pathlib import Path


KEV_REVISION = "5e42a7a03f28134853dd3ff77461457e921e5ec1"


def _run(command: list[str], root: Path) -> int:
    print("$ " + " ".join(command), flush=True)
    return subprocess.run(command, cwd=root, check=False).returncode


def _python_path(venv: Path) -> Path:
    if platform.system() == "Windows":
        return venv / "Scripts" / "python.exe"
    return venv / "bin" / "python"


def setup_project(root: Path) -> int:
    uv = shutil.which("uv")
    if uv is None:
        print("uv is required. Install uv, then run python -m demo setup again.", file=sys.stderr)
        return 1
    venv = root / "backend" / ".venv"
    if _run([uv, "venv", "--python", "3.11", str(venv)], root) != 0:
        return 1
    python = _python_path(venv)
    if platform.system() == "Linux":
        torch_install = [
            uv, "pip", "install", "--python", str(python),
            "--index-url", "https://download.pytorch.org/whl/cpu", "torch>=2.6,<2.9",
        ]
    else:
        torch_install = [uv, "pip", "install", "--python", str(python), "torch>=2.6,<2.9"]
    commands = [
        [uv, "pip", "install", "--python", str(python), "-e", str(root)],
        torch_install,
        [
            uv, "pip", "install", "--python", str(python),
            "laya>=0.3.28", "transformers>=5.17,<6", "accelerate>=1.15", "peft>=0.21",
        ],
        [
            uv, "pip", "install", "--no-deps", "--python-version", "3.12",
            "--python", str(python),
            f"kev @ git+https://github.com/jaredpalmer/kev.git@{KEV_REVISION}",
        ],
        [str(python), str(root / "scripts" / "fetch_data.py")],
    ]
    for command in commands:
        if _run(command, root) != 0:
            return 1

    download_script = (
        "from huggingface_hub import snapshot_download; "
        "snapshot_download('convaiinnovations/laya'); "
        "from kev.checkpoint import Checkpoint; "
        "checkpoint=Checkpoint('jaredpalmer/kev-0.8b'); "
        "snapshot_download(checkpoint.meta.base, revision=checkpoint.meta.base_revision); "
        "print('Laya, Kev, and Kev base weights are available in the Hugging Face cache.')"
    )
    return _run([str(python), "-c", download_script], root)
