"""上交所 ETF 份额 JSON 查询。"""

from .._utils import date_text, number
from ..exceptions import DataFormatError

SSE_URL = "https://query.sse.com.cn/commonQuery.do"


class ExchangeSource:
    def __init__(self, http):
        self.http = http

    def sse_shares(self, day):
        day = date_text(day)
        body = self.http.get_json(
            SSE_URL,
            params={
                "isPagination": "true",
                "pageHelp.pageSize": 10000,
                "pageHelp.pageNo": 1,
                "pageHelp.beginPage": 1,
                "pageHelp.cacheSize": 1,
                "pageHelp.endPage": 1,
                "sqlId": "COMMON_SSE_ZQPZ_ETFZL_XXPL_ETFGM_SEARCH_L",
                "STAT_DATE": day,
            },
            headers={"Referer": "https://www.sse.com.cn/"},
        )
        if not isinstance(body, dict) or not isinstance(body.get("result"), list):
            raise DataFormatError("上交所 ETF 份额响应格式异常")
        result = []
        for row in body["result"]:
            if not isinstance(row, dict) or "SEC_CODE" not in row:
                raise DataFormatError("上交所 ETF 份额记录字段异常")
            shares = number(row.get("TOT_VOL"))
            result.append(
                {
                    "code": str(row["SEC_CODE"]).zfill(6),
                    "date": row.get("STAT_DATE") or day,
                    "shares": shares * 10000 if shares is not None else None,
                    "unit": "share",
                    "source": "sse",
                    "raw": row,
                }
            )
        return result
