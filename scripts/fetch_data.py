from __future__ import annotations

import json
import ssl
import subprocess
import sys
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_URL = "https://raw.githubusercontent.com/snap-research/locomo/main/data/locomo10.json"


def main() -> int:
    raw_dir = ROOT / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    target = raw_dir / "locomo10.json"
    temporary = target.with_suffix(".json.part")
    request = urllib.request.Request(
        SOURCE_URL,
        headers={"User-Agent": "system-one-demo-setup"},
    )
    try:
        with urllib.request.urlopen(
            request,
            timeout=120,
            context=ssl.create_default_context(),
        ) as response:
            payload = response.read()
        parsed = json.loads(payload)
        if not isinstance(parsed, list) or not parsed:
            raise ValueError("LoCoMo response is not a non-empty JSON list")
        temporary.write_bytes(payload)
        temporary.replace(target)
        print(f"Downloaded {len(payload)} bytes to {target}")
    except Exception:
        temporary.unlink(missing_ok=True)
        raise

    command = [sys.executable, str(ROOT / "scripts" / "build_cases.py"), str(target)]
    completed = subprocess.run(command, cwd=ROOT, check=False)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
