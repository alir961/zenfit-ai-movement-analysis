from __future__ import annotations

import socket
from pathlib import Path

import uvicorn


def _is_port_free(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.connect_ex((host, port)) != 0


def _pick_port(host: str, base_port: int, max_tries: int = 20) -> int:
    for offset in range(max_tries):
        port = base_port + offset
        if _is_port_free(host, port):
            return port
    raise RuntimeError(f"No free port found from {base_port} to {base_port + max_tries - 1}")


if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    host = "127.0.0.1"
    port = _pick_port(host, 8000)
    print(f"[speedy_learning] starting dev server on http://{host}:{port}")
    uvicorn.run(
        "backend.server:app",
        host=host,
        port=port,
        reload=True,
        app_dir=str(root),
        reload_dirs=[str(root / "backend"), str(root / "frontend"), str(root / "docs")],
    )
