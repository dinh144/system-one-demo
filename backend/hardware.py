from __future__ import annotations

import importlib.util
import os
import platform
import shutil
import sys
import json
from pathlib import Path
import subprocess
from urllib.request import Request, urlopen
from typing import Any

from backend.config import OLLAMA_URL, OLLAMA_TAGS


def physical_core_count() -> tuple[int, str]:
    try:
        import psutil

        count = psutil.cpu_count(logical=False)
        if count:
            return count, "psutil physical core count"
    except Exception:
        pass
    logical = os.cpu_count() or 1
    return max(1, logical // 2), "os.cpu_count() // 2 fallback; may differ from physical cores"


def memory_gb() -> float:
    try:
        import psutil

        return round(psutil.virtual_memory().total / (1024**3), 2)
    except Exception:
        if hasattr(os, "sysconf"):
            try:
                return round(
                    os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / (1024**3),
                    2,
                )
            except (ValueError, OSError):
                pass
        return 0.0


def ollama_info() -> dict[str, Any]:
    try:
        request = Request(f"{OLLAMA_URL}/api/tags")
        with urlopen(request, timeout=2.0) as response:
            payload = json.loads(response.read().decode("utf-8"))
        models = sorted(
            model.get("name", "")
            for model in payload.get("models", [])
            if model.get("name")
        )
        return {"reachable": True, "models": models}
    except Exception:
        return {"reachable": False, "models": []}


def torch_info() -> tuple[str, dict[str, Any] | None]:
    try:
        import torch

        if torch.cuda.is_available():
            props = torch.cuda.get_device_properties(0)
            return torch.__version__, {
                "name": props.name,
                "vram_gb": round(props.total_memory / (1024**3), 2),
                "cuda": True,
            }
        return torch.__version__, _nvidia_smi_gpu()
    except Exception:
        return "not installed", _nvidia_smi_gpu()


def _nvidia_smi_gpu() -> dict[str, Any] | None:
    executable = shutil.which("nvidia-smi")
    if executable is None:
        return None
    try:
        result = subprocess.run(
            [executable, "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            check=True,
            capture_output=True,
            text=True,
            timeout=4,
        )
        first = result.stdout.strip().splitlines()[0]
        name, vram = [part.strip() for part in first.split(",", 1)]
        return {"name": name, "vram_gb": round(float(vram) / 1024, 2), "cuda": False}
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        return None


def hardware_report() -> dict[str, Any]:
    torch_version, gpu = torch_info()
    return {
        "os": f"{platform.system()} {platform.release()}",
        "cpu": _cpu_name(),
        "ram_gb": memory_gb(),
        "gpu": gpu,
        "python": platform.python_version(),
        "torch": torch_version,
        "ollama": ollama_info(),
    }


def _cpu_name() -> str:
    if platform.system() == "Linux":
        try:
            for line in Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines():
                if line.lower().startswith("model name") and ":" in line:
                    return line.split(":", 1)[1].strip()
        except OSError:
            pass
    return platform.processor() or platform.machine() or "unknown CPU"


def engine_availability() -> dict[str, tuple[str, str | None]]:
    """Return engine id -> status/reason without initializing model weights."""
    result: dict[str, tuple[str, str | None]] = {}
    torch_version, gpu = torch_info()
    has_torch = torch_version != "not installed"
    for engine, module in (("laya", "laya"), ("kev-0.8b", "kev")):
        if not has_torch:
            result[engine] = ("unavailable", "PyTorch is not installed")
        elif importlib.util.find_spec(module) is None:
            result[engine] = ("unavailable", f"Python package {module} is not installed")
        elif not _weights_cached(engine):
            result[engine] = ("unavailable", f"Weights for {engine} are not in the Hugging Face cache; run python -m demo setup")
        else:
            device = "cuda" if gpu and gpu.get("cuda") else "cpu"
            result[engine] = ("ready", device)

    ollama = ollama_info()
    for tag in OLLAMA_TAGS:
        if not ollama["reachable"]:
            result[f"llm:{tag}"] = ("unavailable", "Ollama is not reachable")
            continue
        present = any(name == tag or name.startswith(f"{tag}-") for name in ollama["models"])
        result[f"llm:{tag}"] = (
            ("ready", "ollama") if present else ("unavailable", f"Ollama model {tag} is not installed")
        )
    return result


def _weights_cached(engine: str) -> bool:
    home = Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface"))
    cache = Path(os.environ.get("HF_HUB_CACHE", home / "hub"))
    if engine == "laya":
        repos = ("models--convaiinnovations--laya",)
    else:
        repos = (
            "models--jaredpalmer--kev-0.8b",
            "models--Qwen--Qwen3.5-0.8B-Base",
        )
    files: list[Path] = []
    for repo in repos:
        snapshots = cache / repo / "snapshots"
        for snapshot in snapshots.glob("*"):
            files.extend(path for path in snapshot.rglob("*") if path.is_file())
    names = {path.name for path in files}
    if engine == "laya":
        return any(name.startswith("model") and name.endswith(".safetensors") for name in names)
    return "head.pt" in names and "adapter_model.safetensors" in names and any(
        name.startswith("model") and name.endswith(".safetensors") for name in names
    )


def diagnostic_missing() -> list[str]:
    missing: list[str] = []
    if shutil.which("ollama") is None:
        missing.append("Ollama executable")
    root = Path(__file__).resolve().parents[1]
    for relative in ("data/cases.json", "data/scenario.json"):
        if not (root / relative).is_file():
            missing.append(f"{relative} is missing; run setup or restore the repository file")
    if not (root / "web" / "out" / "index.html").is_file():
        missing.append(
            "web/out/index.html is missing; rebuild it with `npm ci --prefix web` "
            "and `npm run build --prefix web`"
        )
    for engine, (status, reason) in engine_availability().items():
        if status != "ready":
            missing.append(f"{engine}: {reason}")
    return missing
