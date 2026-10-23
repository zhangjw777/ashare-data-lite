"""在线样本检查，结果写入 docs/live-check.json。"""

import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ashare_data import MarketClient
from ashare_data._utils import china_today


def main():
    client = MarketClient(timeout=6, retries=0)
    end = (china_today() - timedelta(days=1)).isoformat()
    start = (china_today() - timedelta(days=21)).isoformat()
    cases = {
        "etf_quote": lambda: client.get_etf_quote("159941"),
        "stock_quote": lambda: client.get_stock_quote("600519"),
        "index_quote": lambda: client.get_index_quote("000001"),
        "mixed_quotes": lambda: client.get_quotes(["sz159941", "sh600519", "sh000001"]),
        "etf_daily": lambda: client.get_etf_history("159941", start, end),
        "index_daily": lambda: client.get_index_history("000001", start, end),
        "sina_daily": lambda: client.get_etf_history(
            "159941", start, end, source="sina", adjust=""
        ),
        "sina_minute": lambda: client.get_etf_history(
            "159941", start, end, source="sina", adjust="", scale=5
        ),
        "etf_catalog": client.get_etf_catalog,
        "fund_nav": lambda: client.get_fund_nav_history("159941", start, end),
        "fund_nav_web": lambda: client._eastmoney._history("web", "159941", start, end),
        "sse_shares": lambda: client.get_sse_etf_shares(end),
    }
    credentials = []
    for name, env, fetch in (
        ("fred", "FRED_API_KEY", lambda: client.get_vix_history(start, end)),
        (
            "twelvedata",
            "TWELVE_DATA_API_KEY",
            lambda: client.get_twelve_bars("SPY", outputsize=5),
        ),
    ):
        if os.getenv(env):
            cases[name] = fetch
        else:
            credentials.append(
                {"case": name, "status": "credential_required", "environment": env}
            )

    def check(name, fetch):
        try:
            value = fetch()
            if not value:
                return {"case": name, "status": "empty", "count": 0}
            if isinstance(value, list):
                failures = [
                    row for row in value if isinstance(row, dict) and "error" in row
                ]
                if failures:
                    return {
                        "case": name,
                        "status": "failed",
                        "error": "批量行情缺失",
                        "items": failures,
                    }
                sample = value[-1]
            else:
                sample = value
            if isinstance(sample, dict):
                keys = (
                    "symbol",
                    "name",
                    "last",
                    "source",
                    "quote_time",
                    "datetime",
                    "valuation_date",
                    "nav",
                    "shares",
                    "code",
                )
                sample = {key: sample[key] for key in keys if key in sample}
            return {
                "case": name,
                "status": "passed",
                "count": 1
                if isinstance(value, dict) and "symbol" in value
                else len(value),
                "sample": sample,
            }
        except Exception as exc:
            return {
                "case": name,
                "status": "failed",
                "error_type": type(exc).__name__,
                "error": str(exc),
            }

    results = list(credentials)
    with ThreadPoolExecutor(max_workers=4) as pool:
        pending = {
            pool.submit(check, name, fetch): name for name, fetch in cases.items()
        }
        for task in as_completed(pending):
            result = task.result()
            results.append(result)
            print(json.dumps(result, ensure_ascii=False), flush=True)
    report = {
        "checked_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
        "start": start,
        "end": end,
        "results": sorted(results, key=lambda row: row["case"]),
    }
    path = Path(__file__).resolve().parents[1] / "docs" / "live-check.json"
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"结果：{path}")
    return int(any(row["status"] in {"failed", "empty"} for row in results))


if __name__ == "__main__":
    raise SystemExit(main())
