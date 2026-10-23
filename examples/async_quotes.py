"""异步应用中并发查询行情与净值。"""

import asyncio
from pprint import pprint

from ashare_data import AsyncMarketClient


async def main():
    client = AsyncMarketClient(timeout=10)
    quotes, nav = await asyncio.gather(
        client.get_etf_quotes(["159941", "513100"]),
        client.get_fund_nav_history("159941", "2026-10-01", "2026-10-21"),
    )
    pprint(quotes)
    pprint(nav[-3:])


if __name__ == "__main__":
    asyncio.run(main())
