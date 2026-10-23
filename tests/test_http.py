"""验证标准库传输层的查询、编码、重试和异常行为。"""

import ast
import gzip
import sys
import unittest
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError, URLError
from unittest.mock import patch

from ashare_data._http import HttpClient, retry_seconds
from ashare_data.exceptions import DataFormatError, RequestError


class Response(BytesIO):
    def __init__(self, content, headers=None):
        super().__init__(content)
        self.headers = headers or {}


class HttpTests(unittest.TestCase):
    def test_query_and_json(self):
        with patch(
            "ashare_data._http.urlopen", return_value=Response(b'{"value":1}')
        ) as opened:
            value = HttpClient().get_json(
                "https://example.com/data", params={"q": "沪深", "empty": None}
            )
        request = opened.call_args.args[0]
        self.assertIn("q=%E6%B2%AA%E6%B7%B1", request.full_url)
        self.assertNotIn("empty", request.full_url)
        self.assertEqual(value, {"value": 1})

    def test_gbk_and_gzip(self):
        content = gzip.compress("测试基金".encode("gbk"))
        with patch(
            "ashare_data._http.urlopen",
            return_value=Response(content, {"Content-Encoding": "gzip"}),
        ):
            self.assertEqual(
                HttpClient().get_text("https://example.com", encoding="gbk"), "测试基金"
            )

    def test_http_error_keeps_status_and_redacts_query(self):
        error = HTTPError(
            "https://example.com/data?apikey=secret",
            429,
            "blocked",
            {"Retry-After": "120"},
            BytesIO(),
        )
        with (
            patch("ashare_data._http.urlopen", side_effect=error),
            self.assertRaises(RequestError) as raised,
        ):
            HttpClient().get_json(
                "https://example.com/data", params={"apikey": "secret"}
            )
        self.assertEqual(raised.exception.status_code, 429)
        self.assertEqual(raised.exception.retry_after, 120)
        self.assertNotIn("secret", str(raised.exception))

    def test_retry_network_and_gateway_errors(self):
        for error in (
            URLError("network"),
            HTTPError("https://example.com", 503, "busy", {}, BytesIO()),
        ):
            with self.subTest(error=type(error).__name__):
                with patch(
                    "ashare_data._http.urlopen", side_effect=[error, Response(b"{}")]
                ) as opened:
                    with patch("ashare_data._http.time.sleep"):
                        self.assertEqual(
                            HttpClient(retries=1).get_json("https://example.com"), {}
                        )
                    self.assertEqual(opened.call_count, 2)

    def test_json_and_encoding_errors(self):
        for content in (b"<html>error</html>", b"\xff"):
            with patch("ashare_data._http.urlopen", return_value=Response(content)):
                with self.assertRaises(DataFormatError):
                    HttpClient().get_json("https://example.com")

    def test_retry_after(self):
        self.assertEqual(retry_seconds("120"), 120)
        self.assertEqual(retry_seconds("invalid"), 0)

    def test_runtime_imports_use_standard_library(self):
        import ashare_data

        root = Path(ashare_data.__file__).parent
        for path in root.rglob("*.py"):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                names = []
                if isinstance(node, ast.Import):
                    names = [alias.name.split(".")[0] for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0:
                    names = [(node.module or "").split(".")[0]]
                for name in names:
                    self.assertIn(name, sys.stdlib_module_names, f"{path}: {name}")


if __name__ == "__main__":
    unittest.main()
