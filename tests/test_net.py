import socket

from jarvis.net import find_free_port


def test_find_free_port_returns_open_port():
    busy = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    busy.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    busy.bind(("127.0.0.1", 0))
    busy.listen(1)
    occupied = busy.getsockname()[1]
    try:
        port = find_free_port("127.0.0.1", occupied, span=5)
        assert port != occupied
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(("127.0.0.1", port))
    finally:
        busy.close()


def test_find_free_port_fallback_when_span_exhausted():
    assert find_free_port("127.0.0.1", 1, span=0) == 1
