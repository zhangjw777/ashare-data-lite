# ashare-data-lite

轻量、免费的 Python 行情工具，提供沪深股票、ETF、指数、基金净值及海外市场数据。Python 3.10+，运行代码使用标准库，采用 MIT 许可证。

## 安装与使用

从 PyPI 安装：

```shell
pip install ashare-data-lite
```

```python
from ashare_data import get_etf_quote, get_etf_history, get_fund_nav_history

quote = get_etf_quote("159941")
print(quote.name, quote.last, quote.iopv)

bars = get_etf_history("159941", "2026-09-01", "2026-10-23")
print(bars[-1].timestamp, bars[-1].close, bars[-1].volume)

nav = get_fund_nav_history("159941", "2026-09-01", "2026-10-23")
print(nav[-1].date, nav[-1].nav)
```

ETF 指交易所交易基金，IOPV 指基金份额参考净值。查询结果采用 dataclass，支持属性访问和 `to_dict()`。股票数量以股计，ETF 数量以份计；百分率 `2.5` 表示 `2.5%`。

## 支持的数据

| 数据 | 入口 |
| --- | --- |
| 股票、ETF、指数实时行情及五档买卖报价 | `get_stock_quote`、`get_etf_quote`、`get_index_quote`，批量方法以 `_quotes` 结尾 |
| 日线与 5 / 15 / 30 分钟 K 线 | `get_stock_history`、`get_etf_history`、`get_index_history` |
| 基金历史单位净值 | `get_fund_nav_history` |
| ETF 目录、上交所 ETF 份额 | `get_etf_catalog`、`get_sse_etf_shares` |
| FRED 经济序列及 VIX | `get_fred_series`、`get_vix_history` |
| Twelve Data 海外 K 线 | `get_twelve_bars`、`get_twelve_daily_history` |

沪深行情、基金净值、目录和份额可直接查询。FRED 和 Twelve Data 使用服务商账户密钥，支持环境变量 `FRED_API_KEY`、`TWELVE_DATA_API_KEY`。

## 自动降级

日线默认原始价格，依次尝试腾讯、新浪；基金单位净值依次尝试东方财富移动端、网页。使用默认配置即可查询，也可设置来源优先级：

```python
bars = get_etf_history(
    "159941", "2026-10-01", "2026-10-23",
    sources=["sina", "tencent"],
)
```

降级过程保持周期与复权方式一致。分钟线由新浪提供；前复权、后复权日线由腾讯提供。来源的覆盖日期与账户权限决定实际可用数据范围。

## 批量、序列化与异步

```python
import json
from ashare_data import get_etf_quotes

quotes = get_etf_quotes(["159941", "513100"])
for quote in quotes:
    print(quote.symbol, quote.last, quote.error)

print(json.dumps(quotes[0].to_dict(), ensure_ascii=False))
```

```python
import asyncio
from ashare_data import AsyncMarketClient

async def main():
    client = AsyncMarketClient(timeout=10)
    quotes = await client.get_etf_quotes(["159941", "513100"])
    print(quotes[0].last)

asyncio.run(main())
```

同步客户端 `MarketClient` 与异步客户端 `AsyncMarketClient` 提供相同的方法和返回类型。完整参数、返回字段、单位及异常见 [API 文档](https://github.com/zhangjw777/ashare-data-lite/blob/main/docs/api.md)。

## 数据来源与使用范围

实时行情来自腾讯；历史 K 线来自腾讯、新浪；基金净值来自东方财富；基金份额来自上交所；经济序列与海外行情来自 FRED、Twelve Data。数据源的覆盖范围、延迟、接口格式及访问额度可能变化，使用方应做好超时处理并校验关键数据。账户接口遵循对应服务商的套餐和调用限制。

本项目的 MIT 许可证适用于程序代码。行情数据的使用、存储和再分发遵循各来源的使用条款；交易分析需要结合其他信息校验，并自行承担决策风险。

## 开发

```shell
python -m pip install -e ".[dev]"
python -m unittest discover -s tests -v
```

使用案例位于 `examples/`。在线样本检查运行 `python examples/smoke_check.py`，记录保存在 `docs/live-check.json`。GitHub Actions 在 Python 3.10～3.13 执行自动测试。

## 发布新版本

在 `main` 分支审阅并提交功能改动后执行：

```shell
python scripts/release.py 0.1.1
```

脚本检查 PyPI 与 Git 标签、更新版本、构建并安装测试，然后推送提交与 `v0.1.1` 标签。GitHub Actions 使用 `pypi` Environment 和 OIDC（开放身份连接）可信发布到 PyPI。工作流运行记录见 [Publish to PyPI](https://github.com/zhangjw777/ashare-data-lite/actions/workflows/publish.yml)。

仅执行发布前验证：`python scripts/release.py 0.1.1 --check-only`。项目内的发布指导位于 [.agents/skills/publish-pypi/SKILL.md](https://github.com/zhangjw777/ashare-data-lite/blob/main/.agents/skills/publish-pypi/SKILL.md)。

