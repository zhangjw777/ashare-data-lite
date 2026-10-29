"""交易所最新申购赎回清单及证券篮子市值，全部在内存中处理。"""

import re
from dataclasses import replace
from datetime import timedelta
from xml.etree import ElementTree

from .._utils import china_today, normalize_symbol, number
from ..exceptions import DataFormatError, InvalidCodeError, QuoteNotFoundError
from ..models import ETFComponent, ETFHolding, ETFPcf
from .tencent import QUOTE_URL, RECORD

SZSE_REPORT_URL = "https://www.szse.cn/api/report/ShowReport/data"
SZSE_PCF_URL = "https://reportdocs.static.szse.cn/files/text/ETFDown/"
SSE_PCF_URL = "https://query.sse.com.cn/etfDownload/downloadETF2Bulletin.do"


def _required_number(value, label):
    result = number(value)
    if result is None or result < 0:
        raise DataFormatError(f"{label} 应为非负数")
    return result


def parse_pcf(content, code, source):
    """解析沪深 XML；上交所部分文件的实际编码为 GB18030。"""
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("gb18030")
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError as exc:
        raise DataFormatError("申赎清单应为 XML") from exc
    # 深交所 XML 带命名空间，统一标签后共用字段转换。
    for node in root.iter():
        node.tag = node.tag.rsplit("}", 1)[-1]
    szse = source == "szse"
    if root.findtext("SecurityID" if szse else "FundInstrumentID") != code:
        raise DataFormatError("申赎清单基金代码与请求不符")
    components = []
    path = "./Components/Component" if szse else "./ComponentList/Component"
    for row in root.findall(path):
        security = row.findtext(
            "UnderlyingSecurityID" if szse else "InstrumentID", ""
        ).strip()
        if not security:
            raise DataFormatError("申赎清单证券代码缺失")
        components.append(
            ETFComponent(
                code=security,
                name=row.findtext(
                    "UnderlyingSymbol" if szse else "InstrumentName", ""
                ).strip(),
                market=row.findtext(
                    "UnderlyingSecurityIDSource" if szse else "UnderlyingSecurityID", ""
                ).strip(),
                quantity=_required_number(
                    row.findtext("ComponentShare" if szse else "Quantity"),
                    f"{security} 数量",
                ),
                substitution_flag=row.findtext(
                    "SubstituteFlag" if szse else "SubstitutionFlag", ""
                ),
                creation_premium_rate=number(
                    row.findtext("PremiumRatio" if szse else "CreationPremiumRate")
                ),
                redemption_discount_rate=number(
                    row.findtext("DiscountRatio" if szse else "RedemptionDiscountRate")
                ),
                creation_cash_substitute=number(
                    row.findtext(
                        "CreationCashSubstitute" if szse else "SubstitutionCashAmount"
                    )
                ),
                redemption_cash_substitute=number(
                    row.findtext(
                        "RedemptionCashSubstitute" if szse else "SubstitutionCashAmount"
                    )
                ),
                is_cash=szse and security == "159900",
            )
        )
    if not components:
        raise DataFormatError("申赎清单成分列表为空")
    return ETFPcf(
        code=code,
        source=source,
        creation_unit=_required_number(
            root.findtext("CreationRedemptionUnit"), "申赎单位"
        ),
        nav_per_cu=_required_number(root.findtext("NAVperCU"), "申赎单位净值"),
        cash_component=number(
            root.findtext("CashComponent" if szse else "PreCashComponent")
        ),
        components=tuple(components),
    )


def _quote_symbol(component):
    prefixes = {"101": "sh", "102": "sz", "103": "hk", "104": "bj", "106": "bj"}
    prefix = prefixes.get(component.market)
    if prefix:
        return prefix + component.code.zfill(5 if prefix == "hk" else 6)
    if component.market == "9999" and re.fullmatch(r"[A-Z][A-Z0-9.]*", component.code):
        return "us" + component.code.replace(".", "_")
    raise QuoteNotFoundError(
        f"{component.code} 市场 {component.market} 需要对应的行情来源"
    )


class PcfSource:
    def __init__(self, http):
        self.http = http

    def pcf(self, code):
        symbol = normalize_symbol(code, "etf")
        code = symbol[2:]
        if symbol.startswith("sh5"):
            content = self.http.get_bytes(
                SSE_PCF_URL,
                params={"fundCode": code},
                headers={"Referer": "https://www.sse.com.cn/"},
            )
            return parse_pcf(content, code, "sse")
        if not symbol.startswith("sz15"):
            raise InvalidCodeError("ETF 代码使用沪市 5 开头或深市 15 开头代码")
        # 从公告索引选择最新文件，周末、长假和暂停披露时使用已公布的最近清单。
        today = china_today()
        body = self.http.get_json(
            SZSE_REPORT_URL,
            params={
                "SHOWTYPE": "JSON",
                "CATALOGID": "sgshqd",
                "TABKEY": "tab1",
                "txtJCorDH": code,
                "txtStart": (today - timedelta(days=365)).isoformat(),
                "txtEnd": today.isoformat(),
            },
            headers={"Referer": "https://www.szse.cn/"},
        )
        filenames = re.findall(rf"pcf_{code}_(\d{{8}})", str(body))
        if not filenames:
            raise DataFormatError(f"{code} 最新申赎清单公告缺失")
        content = self.http.get_bytes(f"{SZSE_PCF_URL}pcf_{code}_{max(filenames)}.xml")
        return parse_pcf(content, code, "szse")

    def _quotes(self, symbols):
        result = {}
        symbols = list(dict.fromkeys(symbols))
        for offset in range(0, len(symbols), 50):
            text = self.http.get_text(
                QUOTE_URL + ",".join(symbols[offset : offset + 50]), encoding="gbk"
            )
            result.update(
                (symbol, payload.split("~"))
                for symbol, payload in RECORD.findall(text)
                if payload
            )
        return result

    def holdings(self, code):
        pcf = self.pcf(code)
        components = [row for row in pcf.components if not row.is_cash]
        symbols = [_quote_symbol(row) for row in components]
        quotes = self._quotes(symbols)
        currencies = {"sh": "CNY", "sz": "CNY", "bj": "CNY", "hk": "HKD", "us": "USD"}
        needed = {currencies[symbol[:2]] for symbol in symbols} - {"CNY"}
        fx_quotes = self._quotes([f"wh{currency}CNY" for currency in sorted(needed)])
        rates = {"CNY": 1.0}
        for currency in needed:
            fields = fx_quotes.get(f"wh{currency}CNY", [])
            rate = number(fields[3]) if len(fields) > 3 else None
            if rate is None or rate <= 0:
                raise QuoteNotFoundError(f"{currency}/CNY 汇率缺失")
            rates[currency] = rate
        result = []
        for row, symbol in zip(components, symbols):
            fields = quotes.get(symbol, [])
            price = number(fields[3]) if len(fields) > 3 else None
            cash = (
                row.creation_cash_substitute if row.substitution_flag == "2" else None
            )
            if cash is None and row.quantity > 0 and (price is None or price <= 0):
                raise QuoteNotFoundError(f"{symbol} 最新行情缺失")
            currency = currencies[symbol[:2]]
            # 必须现金替代的证券使用清单固定金额，零数量仍可对应正的替代市值。
            value = (
                cash
                if cash is not None
                else row.quantity * (price or 0) * rates[currency]
            )
            result.append(
                ETFHolding(
                    code=row.code,
                    name=row.name,
                    market=row.market,
                    quantity=row.quantity,
                    price=price,
                    currency=currency,
                    exchange_rate=rates[currency],
                    market_value=value,
                    weight_pct=0.0,
                    valuation="cash_substitute" if cash is not None else "quote",
                )
            )
        total = sum(row.market_value for row in result)
        if total <= 0:
            raise DataFormatError("证券篮子总市值应大于零")
        # 占比以全部证券的同币种市值之和为分母，申赎现金项目单独保留在 PCF 中。
        return sorted(
            (replace(row, weight_pct=row.market_value / total * 100) for row in result),
            key=lambda row: row.weight_pct,
            reverse=True,
        )
