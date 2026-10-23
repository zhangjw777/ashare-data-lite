"""东方财富基金历史单位净值：移动端优先，网页接口兜底。"""

import threading
import time

from .._utils import date_range, date_text, fund_code, number, sorted_rows
from ..exceptions import DataFormatError, MarketDataError
from ..fallback import first_success

MOBILE_URL = "https://fundmobapi.eastmoney.com/FundMNewApi/FundMNHisNetList"
WEB_URL = "https://api.fund.eastmoney.com/f10/lsjz"
MOBILE_HEADERS = {
    "User-Agent": "EMProjJijin/6.2.8 (iPhone; iOS 13.6; Scale/2.00)",
    "GTOKEN": "98B423068C1F4DEF9842F82ADF08C5db",
    "clientInfo": "ttjj-iPhone10,1-iOS-iOS13.6",
    "Referer": "https://mpservice.com/516939c37bdb4ba2b1138c50cf69a2e1/release/pages/FundHistoryNetWorth",
}


class EastmoneySource:
    def __init__(self, http, *, interval=0.25, cooldown=60):
        self.http = http
        self.interval = interval
        self.cooldown = cooldown
        self._lock = threading.Lock()
        self._semaphore = threading.BoundedSemaphore(2)
        self._next_request = 0.0
        self._blocked = {"mobile": 0.0, "web": 0.0}

    def _request(self, source, code, params):
        with self._semaphore:
            with self._lock:
                if time.monotonic() < self._blocked[source]:
                    raise DataFormatError(f"东方财富 {source} 接口处于冷却期")
                time.sleep(max(0, self._next_request - time.monotonic()))
                self._next_request = time.monotonic() + self.interval
            headers = (
                MOBILE_HEADERS
                if source == "mobile"
                else {"Referer": f"https://fundf10.eastmoney.com/jjjz_{code}.html"}
            )
            try:
                options = (
                    {"timeout": min(self.http.timeout, 5)} if source == "mobile" else {}
                )
                body = self.http.get_json(
                    MOBILE_URL if source == "mobile" else WEB_URL,
                    params=params,
                    headers=headers,
                    **options,
                )
                if not isinstance(body, dict) or body.get("ErrCode") != 0:
                    raise DataFormatError(f"东方财富 {source} 净值业务状态异常")
                return body
            except MarketDataError as exc:
                if (
                    source == "mobile"
                    or getattr(exc, "status_code", None) in {403, 429}
                    or isinstance(exc, DataFormatError)
                ):
                    delay = max(self.cooldown, getattr(exc, "retry_after", 0))
                    with self._lock:
                        self._blocked[source] = time.monotonic() + delay
                raise

    @staticmethod
    def _normalize(records, code, start, end, source):
        result = []
        for row in records:
            if not isinstance(row, dict):
                raise DataFormatError("东方财富净值记录应为字典")
            try:
                day = date_text(row.get("FSRQ"))
            except ValueError as exc:
                raise DataFormatError("东方财富净值日期字段异常") from exc
            nav = number(row.get("DWJZ"))
            if nav is None and start <= day <= end:
                raise DataFormatError("东方财富单位净值字段异常")
            if nav is not None and start <= day <= end:
                result.append(
                    {
                        "code": code,
                        "valuation_date": day,
                        "nav": nav,
                        "source": source,
                        "raw": row,
                    }
                )
        return sorted_rows(result, "valuation_date")

    def _history(self, source, code, start, end):
        records, received, previous = [], 0, None
        page_size = 40000 if source == "mobile" else 20
        for page in range(1, 1001):
            if source == "mobile":
                params = dict(
                    FCODE=code,
                    pageIndex=page,
                    pageSize=page_size,
                    appType="ttjj",
                    cToken="1",
                    deviceid="1",
                    plat="Iphone",
                    product="EFund",
                    serverVersion="6.2.8",
                    version="6.2.8",
                )
            else:
                params = dict(
                    fundCode=code,
                    pageIndex=page,
                    pageSize=page_size,
                    startDate=start,
                    endDate=end,
                )
            body = self._request(source, code, params)
            container = body if source == "mobile" else body.get("Data")
            key = "Datas" if source == "mobile" else "LSJZList"
            batch = container.get(key) if isinstance(container, dict) else None
            if not isinstance(batch, list):
                raise DataFormatError(f"东方财富 {source} 净值列表字段异常")
            if batch and batch == previous:
                raise DataFormatError("东方财富净值分页应返回新的记录")
            records.extend(batch)
            received += len(batch)
            try:
                total = int(body["TotalCount"])
            except (KeyError, TypeError, ValueError) as exc:
                raise DataFormatError("东方财富净值总条数字段异常") from exc
            if received >= total:
                return self._normalize(records, code, start, end, f"eastmoney_{source}")
            if not batch:
                raise DataFormatError("东方财富净值分页提前结束")
            previous = batch
        raise DataFormatError("东方财富净值达到 1000 页请求上限")

    def nav_history(self, code, start=None, end=None):
        code = fund_code(code)
        start, end = date_range(start, end)

        def mobile():
            try:
                return self._history("mobile", code, start, end)
            except MarketDataError as exc:
                with self._lock:
                    self._blocked["mobile"] = max(
                        self._blocked["mobile"],
                        time.monotonic() + self.cooldown,
                        time.monotonic() + getattr(exc, "retry_after", 0),
                    )
                raise

        return first_success(
            [
                ("eastmoney_mobile", mobile),
                ("eastmoney_web", lambda: self._history("web", code, start, end)),
            ]
        )
