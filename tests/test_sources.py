"""使用确定的上游响应验证字段、分页和失败切换。"""

import asyncio
import json
import unittest
from datetime import date, timedelta
from unittest.mock import patch

import ashare_data
from ashare_data import AsyncMarketClient, MarketClient
from ashare_data._utils import normalize_symbol
from ashare_data.exceptions import (
    AllSourcesFailedError,
    ConfigurationError,
    DataFormatError,
    InvalidCodeError,
    QuoteNotFoundError,
    RequestError,
)
from ashare_data.sources.eastmoney import MOBILE_URL, WEB_URL
from ashare_data.sources.tencent import HISTORY_URL, QUOTE_URL, parse_quote


def record(symbol="sz159941", tag="ETF", *, amount_summary=True):
    fields = [""] * 83
    values = {
        1: "测试基金",
        2: symbol[2:],
        3: "2",
        4: "1.9",
        5: "1.95",
        6: "10",
        7: "6",
        8: "4",
        30: "20261021150000",
        31: "0.1",
        32: "5.26",
        33: "2.1",
        34: "1.9",
        35: "2/10/2000" if amount_summary else "",
        38: "1.5",
        39: "20",
        44: "100",
        45: "200",
        46: "2.5",
        47: "2.2",
        48: "1.8",
        49: "1.2",
        50: "15",
        51: "2",
        57: "0.2",
        61: tag,
        72: "100000",
        73: "200000",
        77: "25",
        78: "1.6",
        82: "CNY",
    }
    for level in range(5):
        values[9 + level * 2], values[10 + level * 2] = "1.99", "20"
        values[19 + level * 2], values[20 + level * 2] = "2.01", "10"
    for index, value in values.items():
        fields[index] = value
    return f'v_{symbol}="' + "~".join(fields) + '";'


class FakeHttp:
    timeout = 10

    def __init__(self, handler):
        self.handler, self.calls = handler, []

    def get_json(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.handler(url, kwargs)

    def get_text(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.handler(url, kwargs)


def client_with(handler):
    client = MarketClient(http=FakeHttp(handler))
    client._eastmoney.interval = 0
    return client


class QuoteTests(unittest.TestCase):
    def test_symbol_formats_and_index_ambiguity(self):
        self.assertEqual(normalize_symbol("159941"), "sz159941")
        self.assertEqual(normalize_symbol("600519.SH"), "sh600519")
        self.assertEqual(normalize_symbol("SH600519"), "sh600519")
        self.assertEqual(normalize_symbol("000001", "stock"), "sz000001")
        self.assertEqual(normalize_symbol("000001", "index"), "sh000001")
        self.assertEqual(normalize_symbol("399001", "index"), "sz399001")

    def test_invalid_code(self):
        for value in (159941, "hello", "sz000001;other", "123"):
            with self.subTest(value=value), self.assertRaises(InvalidCodeError):
                normalize_symbol(value)

    def test_complete_etf_quote(self):
        quote = parse_quote("sz159941", record().split('"')[1])
        self.assertEqual(quote["source"], "tencent")
        self.assertEqual(quote["etf"]["premium_rate_calculated"], 25)
        self.assertEqual(quote["etf"]["total_units"], 200000)
        self.assertEqual(quote["average_price_calculated"], 2)
        self.assertEqual(quote["order_imbalance_calculated"], 50)
        self.assertEqual(len(quote["order_book"]["bids"]), 5)
        self.assertEqual(quote["quote_time"], "2026-10-21 15:00:00")
        self.assertEqual(len(quote["raw_fields"]), 83)
        json.dumps(quote, ensure_ascii=False)

    def test_stock_and_index_classification(self):
        stock = parse_quote("sh600519", record("sh600519", "GP-A").split('"')[1])
        self.assertEqual(stock["stock"]["pe"], 20)
        index = parse_quote("sh000001", record("sh000001", "ZS").split('"')[1])
        self.assertEqual(index["instrument_type"], "index")
        self.assertIn("index", index)

    def test_amount_fallback(self):
        quote = parse_quote("sz159941", record(amount_summary=False).split('"')[1])
        self.assertEqual(quote["amount_yuan"], 2000)

    def test_batch_dedup_and_missing(self):
        client = client_with(lambda url, options: record())
        quotes = client.get_etf_quotes(["159941", "sz159941", "513100"])
        self.assertEqual(len(quotes), 2)
        self.assertEqual(quotes[0]["symbol"], "sz159941")
        self.assertIn("error", quotes[1])
        with self.assertRaises(QuoteNotFoundError):
            client.get_stock_quote("600519")

    def test_batch_split_at_50(self):
        def handler(url, options):
            symbols = url.removeprefix(QUOTE_URL).split(",")
            self.assertLessEqual(len(symbols), 50)
            return "\n".join(record(symbol) for symbol in symbols)

        client = client_with(handler)
        quotes = client.get_quotes([f"sz{i:06d}" for i in range(51)])
        self.assertEqual(len(quotes), 51)
        self.assertEqual(len(client.http.calls), 2)

    def test_quote_response_validation(self):
        for response in ("<html>bad</html>", 'v_sz159941="a~b";'):
            with self.subTest(response=response), self.assertRaises(DataFormatError):
                client_with(lambda url, options: response).get_etf_quote("159941")

    def test_public_entry(self):
        with patch(
            "ashare_data._default._client", client_with(lambda url, options: record())
        ):
            self.assertEqual(ashare_data.get_etf_quote("159941")["last"], 2)

    def test_batch_argument(self):
        with self.assertRaises(ConfigurationError):
            client_with(lambda *_: None).get_etf_quotes("159941")


class NavTests(unittest.TestCase):
    def test_mobile_priority_pagination_filter_and_dedup(self):
        def handler(url, options):
            self.assertEqual(url, MOBILE_URL)
            page = options["params"]["pageIndex"]
            days = {
                1: ["2026-10-22", "2026-10-23"],
                2: ["2026-10-21", "2026-10-20"],
                3: ["2026-10-20"],
            }[page]
            return {
                "ErrCode": 0,
                "TotalCount": 5,
                "Datas": [{"FSRQ": day, "DWJZ": str(page)} for day in days],
            }

        client = client_with(handler)
        rows = client.get_fund_nav_history("159941", "2026-10-20", "2026-10-21")
        self.assertEqual(
            [row["valuation_date"] for row in rows], ["2026-10-20", "2026-10-21"]
        )
        self.assertEqual(rows[0]["nav"], 3)
        self.assertEqual(rows[0]["source"], "eastmoney_mobile")
        self.assertEqual(client.http.calls[0][1]["timeout"], 5)

    def test_failure_fallback_and_cooldown(self):
        def handler(url, options):
            if url == MOBILE_URL:
                raise RequestError("模拟移动端失败", status_code=429, retry_after=90)
            self.assertEqual(url, WEB_URL)
            return {
                "ErrCode": 0,
                "TotalCount": 1,
                "PageSize": 20,
                "Data": {"LSJZList": [{"FSRQ": "2026-10-20", "DWJZ": "1.5"}]},
            }

        client = client_with(handler)
        for _ in range(2):
            rows = client.get_fund_nav_history("159941", "2026-10-20", "2026-10-21")
            self.assertEqual(rows[0]["source"], "eastmoney_web")
        self.assertEqual(
            [url for url, _ in client.http.calls], [MOBILE_URL, WEB_URL, WEB_URL]
        )

    def test_web_pagination(self):
        def handler(url, options):
            if url == MOBILE_URL:
                return {"ErrCode": -1}
            page = options["params"]["pageIndex"]
            return {
                "ErrCode": 0,
                "TotalCount": 2,
                "PageSize": 1,
                "Data": {"LSJZList": [{"FSRQ": f"2026-10-{22 - page}", "DWJZ": "1.2"}]},
            }

        rows = client_with(handler).get_fund_nav_history(
            "159941", "2026-10-20", "2026-10-21"
        )
        self.assertEqual(len(rows), 2)

    def test_both_fail_preserves_causes(self):
        with self.assertRaises(AllSourcesFailedError) as raised:
            client_with(lambda *_: {"ErrCode": -999}).get_fund_nav_history("159941")
        self.assertEqual(
            [name for name, _ in raised.exception.errors],
            ["eastmoney_mobile", "eastmoney_web"],
        )

    def test_partial_mobile_data_is_discarded_before_web(self):
        def handler(url, options):
            if url == MOBILE_URL:
                if options["params"]["pageIndex"] == 2:
                    raise RequestError("第二页失败")
                return {
                    "ErrCode": 0,
                    "TotalCount": 2,
                    "Datas": [{"FSRQ": "2026-10-20", "DWJZ": "99"}],
                }
            return {
                "ErrCode": 0,
                "TotalCount": 1,
                "Data": {"LSJZList": [{"FSRQ": "2026-10-20", "DWJZ": "1"}]},
            }

        rows = client_with(handler).get_fund_nav_history("159941")
        self.assertEqual(rows[0]["nav"], 1)

    def test_empty_history(self):
        rows = client_with(
            lambda *_: {"ErrCode": 0, "TotalCount": 0, "Datas": []}
        ).get_fund_nav_history("159941")
        self.assertEqual(rows, [])

    def test_invalid_mobile_value_triggers_web(self):
        def handler(url, options):
            row = {"FSRQ": "2026-10-20", "DWJZ": "bad" if url == MOBILE_URL else "1.5"}
            return {
                "ErrCode": 0,
                "TotalCount": 1,
                "Datas": [row],
                "Data": {"LSJZList": [row]},
            }

        rows = client_with(handler).get_fund_nav_history(
            "159941", "2026-10-20", "2026-10-21"
        )
        self.assertEqual(rows[0]["source"], "eastmoney_web")
        self.assertEqual(rows[0]["nav"], 1.5)

    def test_invalid_dates_fail_before_request(self):
        client = client_with(lambda *_: self.fail("日期校验应先于请求"))
        for start, end in (("bad", None), ("2026-10-22", "2026-10-20")):
            with self.subTest(start=start), self.assertRaises(ConfigurationError):
                client.get_fund_nav_history("159941", start, end)

    def test_premature_empty_page(self):
        with self.assertRaises(AllSourcesFailedError):
            client_with(
                lambda *_: {
                    "ErrCode": 0,
                    "TotalCount": 10,
                    "Datas": [],
                    "Data": {"LSJZList": []},
                }
            ).get_fund_nav_history("159941")


class HistoryTests(unittest.TestCase):
    def test_tencent_pagination_and_sort(self):
        pages = [
            [
                [
                    (date(2020, 1, 2) + timedelta(days=i)).isoformat(),
                    "1",
                    "2",
                    "3",
                    "0.5",
                    "10",
                ]
                for i in range(640)
            ],
            [["2020-01-01", "1", "2", "3", "0.5", "10"]],
        ]

        def handler(url, options):
            self.assertEqual(url, HISTORY_URL)
            if len(pages) == 1:
                self.assertIn(",2020-01-01,640,qfq", options["params"]["param"])
            return {"code": 0, "data": {"sz159941": {"qfqday": pages.pop(0)}}}

        rows = client_with(handler).get_etf_history(
            "159941", "2020-01-01", "2026-10-21"
        )
        self.assertEqual(len(rows), 641)
        self.assertEqual(rows[0]["datetime"], "2020-01-01")
        self.assertEqual(rows[0]["volume_unit"], "lot")

    def test_history_adjust_fields_and_page_limit(self):
        client = client_with(lambda *_: {"code": 0, "data": {"sz159941": {"day": []}}})
        with self.assertRaises(DataFormatError):
            client.get_etf_history("159941", adjust="qfq")
        page = [["2026-10-20", "1", "2", "3", "0.5", "10"]] * 640
        client = client_with(
            lambda *_: {"code": 0, "data": {"sz159941": {"qfqday": page}}}
        )
        with self.assertRaises(DataFormatError):
            client.get_etf_history("159941", "2020-01-01", "2026-10-21", max_pages=1)

    def test_index_uses_original_prices(self):
        def handler(url, options):
            self.assertTrue(options["params"]["param"].endswith(",640,"))
            return {"code": 0, "data": {"sh000001": {"day": []}}}

        self.assertEqual(client_with(handler).get_index_history("000001"), [])

    def test_invalid_history_container(self):
        with self.assertRaises(DataFormatError):
            client_with(lambda *_: {"code": 0, "data": None}).get_etf_history("159941")

    def test_sina_minute_filter_and_sort(self):
        rows = [
            {
                "day": day,
                "open": "1",
                "close": "2",
                "high": "3",
                "low": "0.5",
                "volume": "10",
            }
            for day in (
                "2026-10-21 10:00:00",
                "2026-10-20 10:00:00",
                "2026-10-21 09:30:00",
            )
        ]
        result = client_with(lambda *_: rows).get_etf_history(
            "159941", "2026-10-21", "2026-10-21", source="sina", adjust="", scale=5
        )
        self.assertEqual(len(result), 2)
        self.assertTrue(result[0]["datetime"].endswith("09:30:00"))

    def test_catalog_pagination(self):
        def handler(url, options):
            page = options["params"]["page"]
            return (
                [{"code": f"{i:06d}", "name": str(i)} for i in range(100)]
                if page == 1
                else [{"code": "159941", "name": "测试基金"}]
            )

        self.assertEqual(len(client_with(handler).get_etf_catalog()), 101)

    def test_sse_units(self):
        rows = client_with(
            lambda *_: {
                "result": [
                    {"SEC_CODE": "513100", "STAT_DATE": "2026-10-21", "TOT_VOL": "2.5"}
                ]
            }
        ).get_sse_etf_shares("2026-10-21")
        self.assertEqual(rows[0]["shares"], 25000)
        self.assertEqual(rows[0]["unit"], "share")


class AccountSourceTests(unittest.TestCase):
    def test_fred_pagination_and_missing_values(self):
        def handler(url, options):
            offset = options["params"]["offset"]
            return {
                "count": 3,
                "observations": (
                    [
                        {"date": "2026-10-20", "value": "."},
                        {"date": "2026-10-21", "value": "20"},
                    ]
                    if offset == 0
                    else [{"date": "2026-10-22", "value": "21"}]
                ),
            }

        rows = client_with(handler).get_vix_history(
            "2026-10-20", "2026-10-22", api_key="test"
        )
        self.assertEqual([row["value"] for row in rows], [20, 21])

    def test_twelve_full_daily_pagination(self):
        def handler(url, options):
            cursor = options["params"]["end_date"]
            if cursor == "2026-10-21 23:59:59":
                rows = [
                    {
                        "datetime": (date(2000, 1, 2) + timedelta(days=i)).isoformat(),
                        "close": "2",
                    }
                    for i in range(5000)
                ]
            else:
                self.assertEqual(cursor, "2000-01-01 23:59:59")
                rows = [{"datetime": "2000-01-01", "close": "1"}]
            return {"status": "ok", "values": rows, "meta": {"currency": "USD"}}

        rows = client_with(handler).get_twelve_daily_history(
            "SPY", "1999-01-01", "2026-10-21", api_key="test"
        )
        self.assertEqual(len(rows), 5001)
        self.assertEqual(rows[0]["meta"]["currency"], "USD")

    def test_keys_required(self):
        with patch.dict("os.environ", {}, clear=True):
            client = client_with(lambda *_: self.fail("密钥检查应先于请求"))
        for fetch in (
            lambda: client.get_vix_history(),
            lambda: client.get_twelve_bars("SPY"),
        ):
            with self.assertRaises(ConfigurationError):
                fetch()

    def test_account_business_errors(self):
        for fetch in (
            lambda client: client.get_vix_history(api_key="test"),
            lambda client: client.get_twelve_bars("SPY", api_key="test"),
        ):
            with self.assertRaises(DataFormatError):
                fetch(client_with(lambda *_: {"status": "error", "error_code": 400}))


class AsyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_async_entry(self):
        client = AsyncMarketClient(http=FakeHttp(lambda *_: record()))
        quote, quotes = await asyncio.gather(
            client.get_etf_quote("159941"), client.get_etf_quotes(["159941"])
        )
        self.assertEqual(quote["last"], 2)
        self.assertEqual(quotes[0]["symbol"], "sz159941")


if __name__ == "__main__":
    unittest.main()
