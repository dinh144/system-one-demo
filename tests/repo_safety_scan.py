from __future__ import annotations

import argparse
import re
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_EXTENSIONS = {".py", ".json", ".mjs", ".js", ".ts", ".tsx", ".sh", ".bat", ".md", ".toml"}
SECRET_PATTERNS = {
    "AWS access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "GitHub token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    "OpenAI-style secret": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "Google API key": re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b"),
    "Hugging Face token": re.compile(r"\bhf_[A-Za-z0-9]{30,}\b"),
    "Slack token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
    "GitLab token": re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}\b"),
    "bearer credential": re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~-]{24,}"),
    "assigned API key or secret": re.compile(
        r'''(?i)(?:api[_-]?key|secret)\s*[:=]\s*["'][A-Za-z0-9_./+=-]{16,}["']'''
    ),
}


def _excluded(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    parts = relative.parts
    return (
        ".git" in parts
        or ".venv" in parts
        or "node_modules" in parts
        or ".next" in parts
        or ".agent-prompts" in parts
    )


def _files() -> list[Path]:
    try:
        tracked = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=ROOT,
            check=True,
            capture_output=True,
        ).stdout.split(b"\0")
        paths = [ROOT / os.fsdecode(entry) for entry in tracked if entry]
        paths = [path for path in paths if path.is_file() and not _excluded(path)]
        if paths:
            return paths
    except (OSError, subprocess.SubprocessError):
        pass

    files: list[Path] = []
    for current, directories, names in os.walk(ROOT):
        directories[:] = [
            name
            for name in directories
            if name not in {".git", ".venv", "node_modules", ".next", ".agent-prompts"}
        ]
        files.extend(Path(current) / name for name in names)
    return [path for path in files if not _excluded(path)]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--forbidden-names",
        default="",
        help="comma-separated names to search for in repository text files",
    )
    args = parser.parse_args()
    forbidden_names = [name.strip().casefold() for name in args.forbidden_names.split(",") if name.strip()]

    matches: list[str] = []
    forbidden_matches: list[str] = []
    scanned = 0
    scanned_text = 0
    files = _files()
    for path in files:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        scanned_text += 1
        is_source_file = path.suffix in SOURCE_EXTENSIONS
        if is_source_file:
            scanned += 1
        for number, line in enumerate(lines, 1):
            if is_source_file:
                for label, pattern in SECRET_PATTERNS.items():
                    if pattern.search(line):
                        matches.append(f"{label}: {path.relative_to(ROOT)}:{number}")
            folded_line = line.casefold()
            if any(name in folded_line for name in forbidden_names):
                forbidden_matches.append(f"repository text match: {path.relative_to(ROOT)}:{number}")

    raw_files = [path for path in files if path.name == "locomo10.json"]
    proposal_docs = [
        path
        for path in files
        if path.is_file()
        and ("proposal" in path.name.casefold() or path.suffix.casefold() in {".docx", ".pdf"})
    ]
    print(f"Scanned {scanned} source/document files for key-like credentials.")
    if matches:
        print("FAIL: credential-shaped match(es) found:")
        for match in matches:
            print("- " + match)
    else:
        print("PASS: no key-like credential patterns matched.")
    print(f"Scanned {scanned_text} repository text files for forbidden names.")
    if forbidden_matches:
        print("FAIL: forbidden-name match(es) found:")
        for match in forbidden_matches:
            print("- " + match)
    else:
        print("PASS: no forbidden-name matches found.")
    print("PASS: no locomo10.json file found." if not raw_files else f"FAIL: LoCoMo files: {raw_files}")
    if proposal_docs:
        print("Proposal documents found: " + ", ".join(str(path.relative_to(ROOT)) for path in proposal_docs))
    else:
        print("NOT RUN: proposal author names cannot be compared; no proposal document is present.")
    return int(bool(matches or forbidden_matches or raw_files))


if __name__ == "__main__":
    raise SystemExit(main())
