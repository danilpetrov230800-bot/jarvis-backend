from __future__ import annotations

import socket


def find_free_port(host: str, start: int, span: int = 20) -> int:
    """Return the first free TCP port in [start, start+span)."""
    if span < 1:
        return start
    for port in range(start, start + span):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((host, port))
            except OSError:
                continue
            return port
    return start
