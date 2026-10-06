from __future__ import annotations

import errno
import socket
import sys
import webbrowser
from pathlib import Path

import uvicorn


HOST = "127.0.0.1"
FIRST_PORT = 8000
LAST_PORT = 65535


def _bind_next_port(host: str = HOST, first_port: int = FIRST_PORT) -> tuple[int, socket.socket]:
    """Bind the first available port, keeping it reserved for Uvicorn."""
    for port in range(first_port, LAST_PORT + 1):
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            if sys.platform == "win32" and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            else:
                listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind((host, port))
            listener.listen(socket.SOMAXCONN)
            listener.setblocking(False)
            return port, listener
        except OSError as exc:
            listener.close()
            if exc.errno not in {errno.EADDRINUSE, getattr(errno, "WSAEADDRINUSE", errno.EADDRINUSE)}:
                raise
    raise OSError(f"No available TCP port on {host} from {first_port} through {LAST_PORT}.")


def _static_ui_ready(root: Path) -> bool:
    output = root / "web" / "out"
    if output.is_dir() and (output / "index.html").is_file():
        return True
    print(
        "The exported UI is missing at web/out/. Build it with Node.js using "
        "`npm ci --prefix web` followed by `npm run build --prefix web`.",
        file=sys.stderr,
    )
    return False


def run_demo(root: Path) -> int:
    if not _static_ui_ready(root):
        return 1

    try:
        port, listener = _bind_next_port()
    except OSError as exc:
        print(f"Could not bind a local port: {exc}", file=sys.stderr)
        return 1

    url = f"http://{HOST}:{port}"
    print(f"System-One demo is starting at {url}", flush=True)
    config = uvicorn.Config("backend.app:app", host=HOST, port=port, log_level="info")

    class BrowserOpeningServer(uvicorn.Server):
        async def startup(self, sockets: list[socket.socket] | None = None) -> None:
            await super().startup(sockets=sockets)
            if self.started:
                webbrowser.open(url)
                print(f"System-One demo is running at {url}. Press Ctrl+C to stop it.", flush=True)

    try:
        BrowserOpeningServer(config).run(sockets=[listener])
    except KeyboardInterrupt:
        return 0
    finally:
        listener.close()
    return 0
