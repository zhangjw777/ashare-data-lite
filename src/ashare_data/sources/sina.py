"""新浪历史 K 线和场内 ETF 目录。"""

from .._utils import date_range, number, sorted_rows
from ..exceptions import ConfigurationError, DataFormatError

KLINE_URL = "http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"
CATALOG_URL = "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"


class SinaSource:
    def __init__(self, http):
        self.http = http

    def history(self, symbol, start=None, end=None, *, scale=240, datalen=5049):
        if scale not in {5, 15, 30, 240}:
            raise ConfigurationError("scale 使用 5、15、30 或 240")
        if not isinstance(datalen, int) or not 1 <= datalen <= 5049:
            raise ConfigurationError("datalen 使用 1～5049 的整数")
        start, end = date_range(start, end)
        body = self.http.get_json(
            KLINE_URL,
            params={"symbol": symbol, "scale": scale, "ma": "no", "datalen": datalen},
        )
        if not isinstance(body, list):
            raise DataFormatError("新浪 K 线响应应为列表")
        rows = []
        for row in body:
            if not isinstance(row, dict) or any(
                key not in row
                for key in ("day", "open", "high", "low", "close", "volume")
            ):
                raise DataFormatError("新浪 K 线字段异常")
            moment = str(row["day"])
            if start <= moment[:10] <= end:
                values = {
                    key: number(row[key])
                    for key in ("open", "high", "low", "close", "volume")
                }
                if any(value is None for value in values.values()):
                    raise DataFormatError("新浪 K 线数值字段异常")
                rows.append(
                    {
                        "datetime": moment,
                        "trade_date": moment[:10],
                        **values,
                        "volume_unit": "upstream",
                        "source": "sina",
                        "adjust": "",
                        "raw": row,
                    }
                )
        return sorted_rows(rows)

    def etf_catalog(self):
        catalog, previous = {}, None
        for page in range(1, 1001):
            rows = self.http.get_json(
                CATALOG_URL,
                params={
                    "page": page,
                    "num": 100,
                    "sort": "symbol",
                    "asc": 0,
                    "node": "etf_hq_fund",
                },
            )
            if not isinstance(rows, list):
                raise DataFormatError("新浪 ETF 目录响应应为列表")
            if rows and rows == previous:
                raise DataFormatError("新浪 ETF 目录分页应返回新的记录")
            for row in rows:
                if not isinstance(row, dict) or "code" not in row or "name" not in row:
                    raise DataFormatError("新浪 ETF 目录字段异常")
                catalog[str(row["code"]).zfill(6)] = row["name"]
            if len(rows) < 100:
                return catalog
            previous = rows
        raise DataFormatError("新浪 ETF 目录达到 1000 页请求上限")
