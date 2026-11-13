import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from astra.ui import Handler


def _server():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def test_page_info_and_analyse_example():
    srv, url = _server()
    try:
        assert b"Was this flight jammed or spoofed?" in urllib.request.urlopen(url + "/").read()
        info = json.load(urllib.request.urlopen(url + "/api/info"))
        assert "baseline-v1" in info["packs"] and "spoof-jump.npz" in info["examples"]
        data = Path("examples/jamming-denial.npz").read_bytes()
        req = urllib.request.Request(url + "/api/analyse", data, {"X-Filename": "jamming-denial.npz"})
        res = json.load(urllib.request.urlopen(req, timeout=120))
        assert res["kind"] == "jam"
        assert b"Flight forensics" in urllib.request.urlopen(url + res["report"]).read()
    finally:
        srv.shutdown()


def test_rejects_unknown_file_type():
    srv, url = _server()
    try:
        req = urllib.request.Request(url + "/api/analyse", b"x", {"X-Filename": "a.exe"})
        try:
            urllib.request.urlopen(req)
            raise AssertionError("expected 400")
        except urllib.error.HTTPError as e:
            assert e.code == 400
    finally:
        srv.shutdown()
