"""验证清单解析、完整证券估值和跨市场汇率换算。"""

import asyncio
import json
import unittest
from dataclasses import replace
from datetime import date
from unittest.mock import patch

from test_sources import FakeHttp

import ashare_data
from ashare_data import AsyncMarketClient, MarketClient
from ashare_data.exceptions import DataFormatError, InvalidCodeError, QuoteNotFoundError
from ashare_data.sources.pcf import parse_pcf

SZSE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<PCFFile xmlns="http://ts.szse.cn/Fund">
  <SecurityID>159502</SecurityID><CreationRedemptionUnit>1000000</CreationRedemptionUnit>
  <NAVperCU>1500000</NAVperCU><CashComponent>-2000</CashComponent>
  <Components>
    <Component><UnderlyingSecurityID>159900</UnderlyingSecurityID><UnderlyingSymbol>申赎现金</UnderlyingSymbol>
      <UnderlyingSecurityIDSource>102</UnderlyingSecurityIDSource><ComponentShare>0</ComponentShare>
      <SubstituteFlag>2</SubstituteFlag><CreationCashSubstitute>1650000</CreationCashSubstitute></Component>
    <Component><UnderlyingSecurityID>MRNA</UnderlyingSecurityID><UnderlyingSymbol>Moderna</UnderlyingSymbol>
      <UnderlyingSecurityIDSource>9999</UnderlyingSecurityIDSource><ComponentShare>25</ComponentShare>
      <SubstituteFlag>1</SubstituteFlag><PremiumRatio>0.1</PremiumRatio><DiscountRatio>0.05</DiscountRatio><CreationCashSubstitute>0</CreationCashSubstitute></Component>
    <Component><UnderlyingSecurityID>NTRA</UnderlyingSecurityID><UnderlyingSymbol>Natera</UnderlyingSymbol>
      <UnderlyingSecurityIDSource>9999</UnderlyingSecurityIDSource><ComponentShare>10</ComponentShare>
      <SubstituteFlag>1</SubstituteFlag></Component>
    <Component><UnderlyingSecurityID>ZERO</UnderlyingSecurityID><UnderlyingSymbol>零数量</UnderlyingSymbol>
      <UnderlyingSecurityIDSource>9999</UnderlyingSecurityIDSource><ComponentShare>0</ComponentShare>
      <SubstituteFlag>1</SubstituteFlag></Component>
  </Components>
</PCFFile>"""

SSE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<SSEPortfolioCompositionFile>
  <FundInstrumentID>510300</FundInstrumentID><CreationRedemptionUnit>900000</CreationRedemptionUnit>
  <NAVperCU>3600000</NAVperCU><PreCashComponent>1200</PreCashComponent>
  <ComponentList>
    <Component><InstrumentID>600519</InstrumentID><InstrumentName>贵州茅台</InstrumentName>
      <UnderlyingSecurityID>101</UnderlyingSecurityID><Quantity>100</Quantity><SubstitutionFlag>1</SubstitutionFlag>
      <CreationPremiumRate>0.1</CreationPremiumRate><SubstitutionCashAmount>160000</SubstitutionCashAmount></Component>
    <Component><InstrumentID>000001</InstrumentID><InstrumentName>平安银行</InstrumentName>
      <UnderlyingSecurityID>102</UnderlyingSecurityID><Quantity>1000</Quantity><SubstitutionFlag>1</SubstitutionFlag></Component>
  </ComponentList>
</SSEPortfolioCompositionFile>"""


class PcfHttp(FakeHttp):
    def get_bytes(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.handler(url, kwargs)


def response(url, options):
    if "ShowReport" in url:
        return [
            {"data": [{"jjdm": "pcf_159502_20261023"}, {"jjdm": "pcf_159502_20261026"}]}
        ]
    if "ETFDown" in url:
        return SZSE_XML.encode()
    if "downloadETF" in url:
        return SSE_XML.encode("gb18030")
    if "whUSDCNY" in url:
        return 'v_whUSDCNY="310~美元人民币~USDCNY~7";'
    return "\n".join(
        f'v_{symbol}="1~证券~{symbol}~{price}";'
        for symbol, price in {
            "usMRNA": 200,
            "usNTRA": 400,
            "sh600519": 1600,
            "sz000001": 10,
        }.items()
        if symbol in url.split("q=", 1)[-1].split(",")
    )


class PcfTests(unittest.TestCase):
    def setUp(self):
        self.http = PcfHttp(response)
        self.client = MarketClient(http=self.http)

    def test_latest_index_across_weekend_and_fresh_requests(self):
        with patch(
            "ashare_data.sources.pcf.china_today", return_value=date(2026, 11, 1)
        ):
            first = self.client.get_etf_pcf("159502.SZ")
            second = self.client.get_etf_pcf("sz159502")
        self.assertIsNot(first, second)
        self.assertEqual(len(self.http.calls), 4)
        self.assertIn("pcf_159502_20261026.xml", self.http.calls[1][0])
        self.assertEqual(self.http.calls[0][1]["params"]["txtEnd"], "2026-11-01")
        self.assertEqual(len(first.components), 4)
        self.assertTrue(first.components[0].is_cash)
        self.assertEqual(first.components[1].quantity, 25)
        self.assertEqual(first.components[1].creation_premium_rate, 0.1)
        self.assertEqual(first.components[1].redemption_discount_rate, 0.05)
        self.assertEqual(first.cash_component, -2000)
        self.assertNotIn("date", json.dumps(first.to_dict()))

    def test_us_full_basket_uses_prices_and_preserves_zero_quantity(self):
        with patch("builtins.open", side_effect=AssertionError("计算应在内存中执行")):
            rows = self.client.get_etf_holdings("159502")
        self.assertEqual([row.code for row in rows], ["MRNA", "NTRA", "ZERO"])
        self.assertAlmostEqual(sum(row.weight_pct for row in rows), 100)
        self.assertAlmostEqual(rows[0].weight_pct, 5000 / 9000 * 100)
        self.assertEqual(rows[0].market_value, 35000)
        self.assertEqual(rows[0].currency, "USD")
        self.assertEqual(rows[2].market_value, 0)

    def test_sse_actual_encoding_and_market_prefixes(self):
        pcf = self.client.get_etf_pcf("510300")
        self.assertEqual(pcf.components[0].name, "贵州茅台")
        rows = self.client.get_etf_holdings("510300")
        self.assertEqual(len(rows), 2)
        self.assertAlmostEqual(rows[0].weight_pct, 160000 / 170000 * 100)
        self.assertEqual(rows[0].exchange_rate, 1)
        self.assertTrue(all("wh" not in url for url, _ in self.http.calls))

    def test_missing_price_or_fx_fails_complete_valuation(self):
        for missing in ("usMRNA", "whUSDCNY"):

            def handler(url, options, missing=missing):
                value = response(url, options)
                if "qt.gtimg" in url:
                    return "\n".join(
                        line
                        for line in value.splitlines()
                        if f"v_{missing}=" not in line
                    )
                return value

            with self.subTest(missing=missing), self.assertRaises(QuoteNotFoundError):
                MarketClient(http=PcfHttp(handler)).get_etf_holdings("159502")

    def test_mixed_currencies_share_one_cny_denominator(self):
        pcf = self.client.get_etf_pcf("159502")
        us = replace(pcf.components[1], quantity=1)
        hk = replace(us, code="700", market="103", quantity=2)
        cn = replace(us, code="600519", market="101", quantity=1)

        def handler(url, options):
            if "qt.gtimg" in url:
                return (
                    response(url, options)
                    + '\nv_hk00700="1~腾讯~00700~100";\nv_whHKDCNY="310~港币~HKDCNY~0.9";'
                )
            return response(url, options)

        self.http.handler = handler
        with patch.object(
            self.client._pcf, "pcf", return_value=replace(pcf, components=(us, hk, cn))
        ):
            rows = self.client.get_etf_holdings("159502")
        self.assertEqual([row.market_value for row in rows], [1600, 1400, 180])
        self.assertAlmostEqual(rows[0].weight_pct, 1600 / 3180 * 100)
        self.assertAlmostEqual(sum(row.weight_pct for row in rows), 100)

    def test_mandatory_cash_substitution_keeps_positive_value(self):
        pcf = self.client.get_etf_pcf("159502")
        cash_stock = replace(
            pcf.components[3], substitution_flag="2", creation_cash_substitute=1000
        )
        with patch.object(
            self.client._pcf,
            "pcf",
            return_value=replace(pcf, components=(pcf.components[1], cash_stock)),
        ):
            rows = self.client.get_etf_holdings("159502")
        self.assertEqual(rows[1].market_value, 1000)
        self.assertIsNone(rows[1].price)
        self.assertEqual(rows[1].valuation, "cash_substitute")
        self.assertAlmostEqual(rows[1].weight_pct, 1000 / 36000 * 100)

    def test_malformed_and_wrong_fund_responses(self):
        for content in (
            b"<html>",
            b"<PCFFile/>",
            SZSE_XML.replace("25</ComponentShare>", "NaN</ComponentShare>").encode(),
        ):
            with self.subTest(content=content[:40]), self.assertRaises(DataFormatError):
                parse_pcf(content, "159502", "szse")
        with self.assertRaises(InvalidCodeError):
            self.client.get_etf_pcf("600519")
        self.http.handler = lambda *_: [{"data": []}]
        with self.assertRaises(DataFormatError):
            self.client.get_etf_pcf("159502")

    def test_public_sync_and_async_interfaces(self):
        with patch("ashare_data._default._client", self.client):
            self.assertIsInstance(ashare_data.get_etf_pcf("159502"), ashare_data.ETFPcf)
            self.assertIsInstance(
                ashare_data.get_etf_holdings("159502")[0], ashare_data.ETFHolding
            )

        async def fetch():
            client = AsyncMarketClient(http=self.http)
            pcf = await client.get_etf_pcf("159502")
            rows = await client.get_etf_holdings("159502")
            self.assertEqual(pcf.code, "159502")
            self.assertAlmostEqual(sum(row.weight_pct for row in rows), 100)

        asyncio.run(fetch())
