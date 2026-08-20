from nova.boot import ensure_stdio, prepare


def test_boot_stdio():
    prepare()
    ensure_stdio()
    assert hasattr(__import__("sys").stdout, "write")
