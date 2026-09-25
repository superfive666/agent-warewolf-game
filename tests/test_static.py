"""编排端托管前端构建产物（web/dist）：入口页、带 hash 的资源、越权路径、没构建时的提示。"""
from __future__ import annotations

import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

from werewolf import server


class TestStaticFrontend(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.dist = root / "dist"
        (self.dist / "assets").mkdir(parents=True)
        (self.dist / "index.html").write_text("<!doctype html><title>t</title>", encoding="utf-8")
        (self.dist / "assets" / "index-abc.js").write_text("console.log(1)", encoding="utf-8")
        (root / "secret.txt").write_text("nope", encoding="utf-8")

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.tmp.cleanup()

    def get(self, path: str):
        try:
            with urllib.request.urlopen(self.base + path) as r:
                return r.status, dict(r.headers), r.read().decode()
        except urllib.error.HTTPError as e:
            return e.code, dict(e.headers), e.read().decode()

    def test_serves_index_and_assets(self):
        with mock.patch.object(server, "WEB_DIR", self.dist.resolve()):
            code, headers, body = self.get("/")
            self.assertEqual(code, 200)
            self.assertIn("<title>t</title>", body)
            self.assertEqual(headers["Cache-Control"], "no-cache")

            code, headers, _ = self.get("/assets/index-abc.js")
            self.assertEqual(code, 200)
            self.assertIn("javascript", headers["Content-Type"])
            self.assertIn("immutable", headers["Cache-Control"])

            self.assertEqual(self.get("/assets/missing.js")[0], 404)

    def test_no_path_traversal(self):
        with mock.patch.object(server, "WEB_DIR", self.dist.resolve()):
            for p in ("/../secret.txt", "/assets/../../secret.txt", "/%2e%2e/secret.txt"):
                code, _, body = self.get(p)
                self.assertNotIn("nope", body, p)
                self.assertEqual(code, 404, p)

    def test_api_still_routed(self):
        with mock.patch.object(server, "WEB_DIR", self.dist.resolve()):
            code, headers, _ = self.get("/api/options")
            self.assertEqual(code, 200)
            self.assertIn("application/json", headers["Content-Type"])

    def test_hint_when_frontend_not_built(self):
        with mock.patch.object(server, "WEB_DIR", (Path(self.tmp.name) / "missing").resolve()):
            code, _, body = self.get("/")
            self.assertEqual(code, 200)
            self.assertIn("npm run build", body)


if __name__ == "__main__":
    unittest.main()
