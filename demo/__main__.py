"""Cross-platform command line entry point for the demo."""

from __future__ import annotations

import argparse
import importlib
import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from backend.hardware import diagnostic_missing, hardware_report, physical_core_count
from backend.engines import model_availability


ROOT = Path(__file__).resolve().parents[1]


def doctor() -> int:
    redirected = _run_project_venv("doctor")
    if redirected is not None:
        return redirected
    report = hardware_report()
    threads, thread_source = physical_core_count()
    report["thread_count_default"] = threads
    report["thread_count_source"] = thread_source
    report["python_executable"] = sys.executable
    report["python_version"] = sys.version
    report["python_prefix"] = sys.prefix
    report["project_root"] = str(ROOT)
    report["project_venv"] = str(ROOT / "backend" / ".venv")
    report["project_venv_exists"] = (ROOT / "backend" / ".venv").exists()
    report["cache_paths"] = {
        "hf_home": os.environ.get("HF_HOME", str(Path.home() / ".cache" / "huggingface")),
        "hf_hub_cache": os.environ.get(
            "HF_HUB_CACHE",
            str(Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface")) / "hub"),
        ),
    }
    report["commands"] = {
        name: _command_report(name, version_args)
        for name, version_args in (
            ("uv", ["--version"]),
            ("node", ["--version"]),
            ("npm", ["--version"]),
            ("ollama", ["--version"]),
            ("nvidia-smi", ["--version"]),
        )
    }
    report["packages"] = {
        name: _package_version(name)
        for name in ("fastapi", "uvicorn", "psutil", "torch", "laya", "kev", "transformers", "accelerate", "peft")
    }
    report["torch_runtime"] = _torch_runtime()
    report["engines"] = {
        engine: {"status": status, "detail": detail}
        for engine, (status, detail) in model_availability().items()
    }
    report["acceleration_optional"] = {
        "flash_linear_attention": _import_report("fla"),
        "causal_conv1d": _import_report("causal_conv1d"),
    }
    print("System-One backend doctor")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    missing = diagnostic_missing()
    print("Missing or unavailable:")
    if missing:
        for item in missing:
            print(f"- {item}")
    else:
        print("- none")
    return 0


def _command_report(name: str, version_args: list[str]) -> dict[str, object]:
    executable = shutil.which(name)
    if executable is None:
        return {"available": False, "path": None, "version": None, "error": "not found on PATH"}
    try:
        completed = subprocess.run(
            [executable, *version_args],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
        output = (completed.stdout or completed.stderr).strip().splitlines()
        return {
            "available": completed.returncode == 0,
            "path": executable,
            "version": output[0] if output else None,
            "error": None if completed.returncode == 0 else f"exit {completed.returncode}",
        }
    except (OSError, subprocess.SubprocessError) as exc:
        return {"available": True, "path": executable, "version": None, "error": str(exc).splitlines()[0]}


def _package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _import_report(module_name: str) -> dict[str, object]:
    try:
        module = importlib.import_module(module_name)
        return {"imported": True, "version": getattr(module, "__version__", None), "error": None}
    except Exception as exc:
        return {"imported": False, "version": None, "error": str(exc).splitlines()[0]}


def _torch_runtime() -> dict[str, object]:
    try:
        import torch

        available = bool(torch.cuda.is_available())
        return {
            "cuda_build": torch.version.cuda,
            "cuda_available": available,
            "cuda_device_count": torch.cuda.device_count() if available else 0,
            "threads": torch.get_num_threads(),
        }
    except Exception as exc:
        return {"cuda_build": None, "cuda_available": False, "cuda_device_count": 0, "error": str(exc).splitlines()[0]}


def setup() -> int:
    from backend.setup import setup_project

    return setup_project(ROOT)


def run() -> int:
    redirected = _run_project_venv("run")
    if redirected is not None:
        return redirected
    from backend.launcher import run_demo

    return run_demo(ROOT)


def selftest() -> int:
    redirected = _run_project_venv("selftest")
    if redirected is not None:
        return redirected
    from backend.selftest import run_selftest

    return run_selftest()


def _run_project_venv(command: str) -> int | None:
    venv = ROOT / "backend" / ".venv"
    python = venv / "Scripts" / "python.exe" if platform.system() == "Windows" else venv / "bin" / "python"
    if not python.exists():
        print("Project environment is missing. Run python -m demo setup first.", file=sys.stderr)
        return 1
    if Path(sys.prefix).resolve() == venv.resolve():
        return None
    return subprocess.run([str(python), "-m", "demo", command], cwd=ROOT, check=False).returncode


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m demo")
    parser.add_argument("command", choices=("setup", "doctor", "run", "selftest"))
    args = parser.parse_args()
    return {"setup": setup, "doctor": doctor, "run": run, "selftest": selftest}[args.command]()


if __name__ == "__main__":
    raise SystemExit(main())
