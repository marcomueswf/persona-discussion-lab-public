from __future__ import annotations

import socket
import sys
import threading
import webbrowser

import uvicorn
from uvicorn.config import LOGGING_CONFIG

from backend.app import app


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as socket_handle:
        socket_handle.bind(("127.0.0.1", 0))
        return int(socket_handle.getsockname()[1])


def main() -> None:
    port = _find_free_port()
    url = f"http://127.0.0.1:{port}/"
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=port,
        reload=False,
        log_level="info",
        log_config=None if sys.stdout is None else LOGGING_CONFIG,
    )


if __name__ == "__main__":
    main()