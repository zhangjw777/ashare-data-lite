# a-share-data

个人行情接口库，Python 3.10+，运行代码使用 Python 标准库。统一入口返回字典和列表，数据来源与请求细节集中在 `sources/`。

```powershell
python -m pip install -e F:\FinancialData\a-share-data
```

```python
from ashare_data import get_etf_quote

quote = get_etf_quote("159941")
print(quote)
print(quote["last"])
print(quote["etf"]["iopv"])
```

ETF 指交易所交易基金；IOPV 指基金份额参考净值。接口返回的百分率以百分数表示，`2.5` 表示 `2.5%`。

## 公开接口

| 数据 | 函数 | 默认来源 |
| --- | --- | --- |
| 单只 / 批量股票行情 | `get_stock_quote` / `get_stock_quotes` | 腾讯 |
| 单只 / 批量 ETF 行情 | `get_etf_quote` / `get_etf_quotes` | 腾讯 |
| 单只 / 批量指数行情 | `get_index_quote` / `get_index_quotes` | 腾讯 |
| 混合证券行情 | `get_quote` / `get_quotes` | 腾讯 |
| 股票 / ETF / 指数历史 | `get_stock_history` / `get_etf_history` / `get_index_history` | 腾讯日线，可选新浪 |
| 基金历史单位净值 | `get_fund_nav_history` | 东方财富移动端 → 网页 |
| ETF 代码与名称目录 | `get_etf_catalog` | 新浪 |
| 上交所 ETF 份额 | `get_sse_etf_shares` | 上交所 JSON |
| 经济与市场序列 | `get_fred_series` / `get_vix_history` | FRED HTTPS |
| 海外 K 线 / 完整日线 | `get_twelve_bars` / `get_twelve_daily_history` | Twelve Data HTTPS |

所有函数均可从 `ashare_data` 导入；`MarketClient` 提供相同方法。实时行情统一请求腾讯，最多 50 个代码一批，按首次出现的输入顺序返回。

## 常用调用

```python
from ashare_data import (
    get_stock_quote, get_index_quote, get_etf_quotes,
    get_etf_history, get_index_history, get_fund_nav_history,
)

stock = get_stock_quote("600519")
index = get_index_quote("000001")
quotes = get_etf_quotes(["159941", "513100"])
daily = get_etf_history("159941", "2026-09-01", "2026-10-21")
index_daily = get_index_history("000001", "2026-09-01", "2026-10-21")
nav = get_fund_nav_history("159941", "2026-09-01", "2026-10-21")
minute = get_etf_history(
    "159941", "2026-10-21", "2026-10-21",
    source="sina", adjust="", scale=5,
)
```

股票入口的 `000001` 表示深市平安银行，指数入口的 `000001` 表示上证指数。代码支持 `159941`、`sz159941`、`159941.SZ`；混合行情中的指数使用明确前缀，例如 `sh000001`、`sz399001`。代码以字符串传入。

## 客户端配置

```python
from ashare_data import MarketClient, configure

configure(timeout=10, retries=1)
client = MarketClient(timeout=15, fred_api_key="YOUR_KEY", twelve_api_key="YOUR_KEY")
vix = client.get_vix_history("2026-10-01", "2026-10-21")
bars = client.get_twelve_daily_history("SPY", "2026-01-01", "2026-10-21")
```

账户密钥也可设置为环境变量 `FRED_API_KEY`、`TWELVE_DATA_API_KEY`，或在对应方法传入 `api_key=`。客户端默认请求超时 10 秒，网络异常及 HTTP 502/503/504 默认重试 1 次。HTTP 代理、TLS 证书验证使用 Python `urllib` 与操作系统配置。

连续调用复用默认客户端。净值请求共享并发上限 2、0.25 秒请求间隔；移动端单次请求超时为 `min(timeout, 5)` 秒，移动端失败后冷却 60 秒，并立即尝试网页接口。403/429 的 `Retry-After` 可延长冷却；两个入口分别保存冷却状态。网页分页失败时，整个净值查询抛出异常。

## 异步调用

```python
import asyncio
from ashare_data import AsyncMarketClient

async def main():
    client = AsyncMarketClient()
    quotes, nav = await asyncio.gather(
        client.get_etf_quotes(["159941", "513100"]),
        client.get_fund_nav_history("159941", "2026-10-01", "2026-10-21"),
    )
    print(quotes)
    print(nav)

asyncio.run(main())
```

异步客户端用 `asyncio.to_thread` 执行标准库网络请求；同一客户端的协程共享净值限速状态。单次请求由 `timeout` 约束，协程取消后已开始的线程请求会执行至完成或超时。

## 返回值与异常

行情包含 `symbol`、`name`、`source`、`quote_time`、`last`、`prev_close`、`open`、`high`、`low`、`volume_lot`、`amount_yuan`、五档 `order_book`，以及 `etf`、`stock` 或 `index` 扩展。`raw_fields` 保留腾讯原始字段。批量查询中缺失的证券返回含 `error` 的字典；单只查询缺失行情时抛出 `QuoteNotFoundError`。

历史记录按 `datetime` 去重升序返回，包含 `trade_date`、开高低收、`volume`、`volume_unit`、`source`、`adjust`、`raw`。净值记录包含 `code`、`valuation_date`、`nav`、`source`、`raw`。份额记录包含 `code`、`date`、`shares`、`unit`、`source`、`raw`。JSON 数值缺失时使用 `None`；FRED 的缺失观测在序列结果中跳过。

异常统一继承 `MarketDataError`，包括 `InvalidCodeError`、`ConfigurationError`、`RequestError`、`DataFormatError`、`QuoteNotFoundError`、`AllSourcesFailedError`。净值两个来源都失败时，`AllSourcesFailedError.errors` 保存逐源异常。

完整参数、请求地址、返回字段及覆盖范围见 [接口手册](docs/api.md)。

## 开发与验证

```powershell
python -m pip install -e .
python -m unittest discover -s tests -v
python examples/basic.py
```

自动测试使用标准库 `unittest` 和模拟响应，覆盖请求编码、腾讯行情解析、历史分页、净值切换及冷却、账户序列、份额换算和异步入口。GitHub Actions 在 Python 3.10～3.13 执行测试。在线检查单独运行：

```powershell
python examples/smoke_check.py
```

2026-10-23 本地 Python 3.12 验证：38 项自动测试通过，12 项公开数据在线样本检查通过；基金净值移动端与网页样本均返回 `2026-10-21` 单位净值 `1.493`。FRED 与 Twelve Data 的在线数据查询需配置账户密钥。详细结果见 [在线检查记录](docs/live-check.json)。

## 项目结构

```text
src/ashare_data/
  __init__.py       统一导出
  client.py         来源选择与同步客户端
  async_client.py   异步客户端
  stock.py          股票入口
  etf.py            ETF、净值、目录、份额入口
  index.py          指数入口
  sources/          腾讯、东方财富、新浪、交易所、FRED、Twelve Data
  fallback.py       失败切换
  exceptions.py     公开异常
tests/              自动测试
examples/           使用案例与在线检查
docs/api.md         上游协议与公开接口
```

调整来源选择时修改 `client.py` 和对应 `sources/`，同时保持公开函数名、参数含义及返回字段约定稳定。

