"""验证公开类型、调用约定与跨来源降级。"""

import inspect
import json
import unittest
from dataclasses import FrozenInstanceError, fields, is_dataclass
from datetime import date, timedelta
from pathlib import Path

import ashare_data
from ashare_data import Bar, FundNav, FundShares, Observation, OrderLevel, Quote
from ashare_data.exceptions import (
    AllSourcesFailedError,
    ConfigurationError,
    RequestError,
)
from test_sources import client_with, record


def sina_bar():
    return {
        "day": "2026-10-21",
        "open": "1",
        "high": "3",
        "low": "0.5",
        "close": "2",
        "volume": "1000",
    }


def tencent_bar():
    return {
        "code": 0,
        "data": {"sz159941": {"day": [["2026-10-21", "1", "2", "3", "0.5", "10"]]}},
    }


class FallbackTests(unittest.TestCase):
    def test_daily_automatic_fallback(self):
        def handler(url, options):
            if "finance.qq.com" in url:
                raise RequestError("腾讯暂时失败")
            return [sina_bar()]

        client = client_with(handler)
        bars = client.get_etf_history("159941", "2026-10-21", "2026-10-21")
        self.assertEqual(bars[0].source, "sina")
        self.assertEqual(bars[0].adjust, "none")
        self.assertEqual(bars[0].volume, 1000)
        self.assertEqual(len(client.http.calls), 2)

    def test_source_priority(self):
        client = client_with(lambda *_: [sina_bar()])
        bars = client.get_etf_history(
            "159941", "2026-10-21", "2026-10-21", sources=["sina", "tencent"]
        )
        self.assertEqual(bars[0].source, "sina")
        self.assertEqual(len(client.http.calls), 1)

    def test_equal_bar_schema_and_units(self):
        tencent = client_with(lambda *_: tencent_bar()).get_etf_history(
            "159941", "2026-10-21", "2026-10-21"
        )[0]
        sina = client_with(lambda *_: [sina_bar()]).get_etf_history(
            "159941", "2026-10-21", "2026-10-21", sources=["sina"]
        )[0]
        self.assertEqual(type(tencent), Bar)
        self.assertEqual(type(sina), Bar)
        for field in fields(Bar):
            if field.name != "source":
                self.assertEqual(
                    getattr(tencent, field.name), getattr(sina, field.name)
                )

    def test_adjustment_capability_is_preserved(self):
        client = client_with(lambda *_: (_ for _ in ()).throw(RequestError("失败")))
        with self.assertRaises(AllSourcesFailedError) as raised:
            client.get_etf_history("159941", adjust="qfq")
        self.assertEqual([name for name, _ in raised.exception.errors], ["tencent"])
        self.assertEqual(len(client.http.calls), 1)
        with self.assertRaises(ConfigurationError):
            client.get_etf_history("159941", adjust="qfq", sources=["sina"])

    def test_invalid_sources_fail_before_network(self):
        client = client_with(lambda *_: self.fail("来源校验应先于请求"))
        for sources in ([], "sina", ["unknown"], 5, [{}]):
            with self.subTest(sources=sources), self.assertRaises(ConfigurationError):
                client.get_etf_history("159941", sources=sources)
            with self.subTest(sources=sources), self.assertRaises(ConfigurationError):
                client.get_fund_nav_history("159941", sources=sources)

    def test_schema_failure_uses_next_source(self):
        def handler(url, options):
            if "finance.qq.com" in url:
                response = tencent_bar()
                response["data"]["sz159941"]["day"][0][2] = "bad"
                return response
            return [sina_bar()]

        rows = client_with(handler).get_etf_history(
            "159941", "2026-10-21", "2026-10-21"
        )
        self.assertEqual(rows[0].source, "sina")

    def test_all_history_sources_fail(self):
        with self.assertRaises(AllSourcesFailedError) as raised:
            client_with(lambda *_: {}).get_etf_history("159941")
        self.assertEqual(
            [name for name, _ in raised.exception.errors], ["tencent", "sina"]
        )

    def test_fund_source_priority(self):
        client = client_with(
            lambda *_: {
                "ErrCode": 0,
                "TotalCount": 1,
                "Data": {"LSJZList": [{"FSRQ": "2026-10-21", "DWJZ": "1.5"}]},
            }
        )
        nav = client.get_fund_nav_history(
            "159941", sources=["eastmoney_web", "eastmoney_mobile"]
        )
        self.assertEqual(nav[0].source, "eastmoney_web")
        self.assertEqual(len(client.http.calls), 1)

    def test_sina_retention_limit_is_explicit(self):
        with self.assertRaises(AllSourcesFailedError):
            client_with(lambda *_: [sina_bar()]).get_etf_history(
                "159941", "2026-01-01", "2026-10-21", sources=["sina"], datalen=1
            )


class ModelTests(unittest.TestCase):
    def test_models_are_frozen_dataclasses(self):
        for model in (Quote, OrderLevel, Bar, FundNav, FundShares, Observation):
            self.assertTrue(is_dataclass(model))
        quote = client_with(lambda *_: record()).get_etf_quote("159941")
        with self.assertRaises(FrozenInstanceError):
            quote.last = 100
        self.assertEqual(quote.timestamp.utcoffset(), timedelta(hours=8))

    def test_json_serialization(self):
        quote = client_with(lambda *_: record()).get_etf_quote("159941")
        payload = json.loads(json.dumps(quote.to_dict(), ensure_ascii=False))
        self.assertEqual(payload["bids"][0], {"price": 1.99, "volume": 2000})
        self.assertEqual(payload["timestamp"], "2026-10-21T15:00:00+08:00")
        nav = FundNav("159941", date(2026, 10, 21), 1.5, "eastmoney_mobile")
        self.assertEqual(nav.to_dict()["date"], "2026-10-21")
        self.assertEqual(quote.error, None)

    def test_public_docs_and_type_annotations(self):
        for name in ashare_data.__all__:
            obj = getattr(ashare_data, name)
            with self.subTest(name=name):
                self.assertTrue(inspect.getdoc(obj))
                if inspect.isfunction(obj):
                    signature = inspect.signature(obj)
                    self.assertNotEqual(
                        signature.return_annotation, inspect.Signature.empty
                    )
                    for parameter in signature.parameters.values():
                        self.assertNotEqual(
                            parameter.annotation, inspect.Parameter.empty
                        )
        for client in (ashare_data.MarketClient, ashare_data.AsyncMarketClient):
            for name, method in inspect.getmembers(client, inspect.isfunction):
                if name.startswith("get_"):
                    self.assertTrue(inspect.getdoc(method), f"{client.__name__}.{name}")

    def test_api_reference_covers_exports_and_model_fields(self):
        docs = Path(__file__).resolve().parents[1] / "docs" / "api.md"
        text = docs.read_text(encoding="utf-8")
        for name in ashare_data.__all__:
            self.assertIn(f"`{name}`", text, name)
        for model in (Quote, OrderLevel, Bar, FundNav, FundShares, Observation):
            for field in fields(model):
                self.assertIn(f"`{field.name}`", text, f"{model.__name__}.{field.name}")


if __name__ == "__main__":
    unittest.main()
