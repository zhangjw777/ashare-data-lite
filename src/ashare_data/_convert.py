"""将来源数据转换为统一的公开类型与计量单位。"""

from datetime import date, datetime, timedelta, timezone

from .exceptions import DataFormatError
from .models import Bar, FundNav, FundShares, Observation, OrderLevel, Quote

CHINA_TZ = timezone(timedelta(hours=8))


def scaled(value, factor):
    return value * factor if value is not None else None


def quote_model(row, instrument="auto"):
    kind = row.get("instrument_type", instrument)
    extension = row.get("etf", row.get("stock", {}))
    time = row.get("quote_time")
    book = row.get("order_book", {})

    def levels(side):
        return tuple(
            OrderLevel(level["price"], scaled(level["volume_lot"], 100))
            for level in book.get(side, [])
        )

    premium = extension.get("premium_rate")
    if premium is None:
        premium = extension.get("premium_rate_calculated")
    average = row.get("average_price")
    if average is None:
        average = row.get("average_price_calculated")
    return Quote(
        symbol=row["symbol"],
        code=row.get("code", row["symbol"][2:]),
        instrument=kind,
        source=row["source"],
        name=row.get("name"),
        timestamp=datetime.fromisoformat(time).replace(tzinfo=CHINA_TZ)
        if time
        else None,
        currency=row.get("currency"),
        **{
            key: row.get(key)
            for key in (
                "last",
                "prev_close",
                "open",
                "high",
                "low",
                "change",
                "change_pct",
                "pb",
                "limit_up",
                "limit_down",
                "volume_ratio",
            )
        },
        pe=extension.get("pe"),
        volume=scaled(row.get("volume_lot"), 100),
        amount=row.get("amount_yuan"),
        outer_volume=scaled(row.get("outer_volume_lot"), 100),
        inner_volume=scaled(row.get("inner_volume_lot"), 100),
        turnover_rate_pct=row.get("turnover_rate"),
        amplitude_pct=row.get("amplitude"),
        market_cap=scaled(row.get("total_market_cap_100m"), 100000000),
        circulating_market_cap=scaled(
            row.get("circulating_market_cap_100m"), 100000000
        ),
        order_imbalance=scaled(row.get("order_imbalance_calculated"), 100),
        average_price=average,
        is_suspended=row.get("is_suspended", False),
        bids=levels("bids"),
        asks=levels("asks"),
        iopv=extension.get("iopv"),
        premium_rate_pct=premium,
        circulating_shares=extension.get(
            "circulating_units", extension.get("circulating_shares")
        ),
        total_shares=extension.get("total_units", extension.get("total_shares")),
        error=row.get("error"),
    )


def bar_models(rows, symbol, interval):
    result = []
    for row in rows:
        try:
            moment = datetime.fromisoformat(row["datetime"])
        except (KeyError, TypeError, ValueError) as exc:
            raise DataFormatError("K 线时间字段异常") from exc
        if row.get("close") is None:
            raise DataFormatError("K 线收盘价字段异常")
        overseas = row["source"] == "twelvedata"
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc if overseas else CHINA_TZ)
        volume = row.get("volume")
        if row.get("volume_unit") == "lot":
            volume = scaled(volume, 100)
        result.append(
            Bar(
                symbol=symbol,
                timestamp=moment,
                interval=interval,
                source=row["source"],
                adjust=row.get("adjust") or "none",
                open=row.get("open"),
                high=row.get("high"),
                low=row.get("low"),
                close=row.get("close"),
                volume=volume,
                volume_unit="provider" if overseas else "share",
                currency=row.get("meta", {}).get("currency") if overseas else "CNY",
            )
        )
    return result


def nav_models(rows):
    return [
        FundNav(
            row["code"],
            date.fromisoformat(row["valuation_date"]),
            row["nav"],
            row["source"],
        )
        for row in rows
    ]


def shares_models(rows):
    return [
        FundShares(
            row["code"],
            date.fromisoformat(row["date"][:10]),
            row["shares"],
            row["source"],
        )
        for row in rows
    ]


def observation_models(rows):
    return [
        Observation(
            row["series_id"],
            date.fromisoformat(row["date"]),
            row["value"],
            row["source"],
        )
        for row in rows
    ]
