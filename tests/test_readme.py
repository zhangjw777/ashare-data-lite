"""在确定的 HTTP 响应下执行 README 的全部 Python 示例。"""

import contextlib
import io
from pathlib import Path
import re
import unittest
from unittest.mock import patch

from test_sources import FakeHttp, record


def response(url, options):
    if "qt.gtimg.cn/q=" in url:
        return "\n".join(record(symbol) for symbol in url.split("q=", 1)[1].split(","))
    if "newfqkline" in url:
        symbol = options["params"]["param"].split(",")[0]
        return {
            "code": 0,
            "data": {symbol: {"day": [["2026-10-23", "1", "2", "3", "0.5", "10"]]}},
        }
    if "CN_MarketData" in url:
        return [
            {
                "day": "2026-10-23",
                "open": "1",
                "high": "3",
                "low": "0.5",
                "close": "2",
                "volume": "1000",
            }
        ]
    if "FundMNHisNetList" in url:
        return {
            "ErrCode": 0,
            "TotalCount": 1,
            "Datas": [{"FSRQ": "2026-10-22", "DWJZ": "1.4499"}],
        }
    raise AssertionError(f"README 示例访问了新增来源：{url}")


class ReadmeTests(unittest.TestCase):
    def test_python_examples(self):
        readme = Path(__file__).resolve().parents[1] / "README.md"
        blocks = re.findall(
            r"```python\n(.*?)```", readme.read_text(encoding="utf-8"), re.DOTALL
        )
        self.assertTrue(blocks)
        namespace = {"__name__": "readme_examples"}
        with patch(
            "ashare_data.client.HttpClient",
            side_effect=lambda *args: FakeHttp(response),
        ):
            with (
                patch("ashare_data._default._client", None),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                for index, source in enumerate(blocks, 1):
                    exec(
                        compile(source, f"README.md:example-{index}", "exec"), namespace
                    )


if __name__ == "__main__":
    unittest.main()
