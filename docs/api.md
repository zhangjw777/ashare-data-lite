# API 参考

所有公开入口均可从 `ashare_data` 导入。调用返回 dataclass 对象或其列表，使用 `obj.field` 读取字段、`obj.to_dict()` 转为适合 JSON 的字典。

## 1. 共同约定

| 项目 | 约定 |
| --- | --- |
| 代码 | 字符串，支持 `159941`、`sz159941`、`159941.SZ` |
| 品种 | `instrument="auto" / "stock" / "etf" / "index"` |
| 日期参数 | `YYYY-MM-DD` 字符串或 `datetime.date`，起止日均包含；默认从 `1970-01-01` 到中国时区当天 |
| 代码歧义 | 股票入口 `"000001"` 为平安银行，指数入口为上证指数；混合入口中的指数使用 `"sh000001"`、`"sz399001"` |
| 时间 | `timestamp` 为带时区的 `datetime`；沪深行情为 UTC+08:00，海外 K 线为 UTC |
| 日期字段 | `date` 为 `datetime.date`，表示净值所属日、统计日或观测日 |
| 数量 | 沪深股票按股、ETF 按份；不同来源的上游取整精度可能有差异 |
| 价格与金额 | 按 `currency` 标价币种；市值与成交额使用基本货币单位，如人民币元 |
| 百分率 | `*_pct` 为百分数，`2.5` 表示 `2.5%` |
| 缺失值 | 可选字段为 `None`，成功查询的空区间返回 `[]`；FRED 缺失观测跳过 |
| 列表顺序 | 历史按时间去重升序；批量行情按首次输入顺序去重 |
| 对象 | dataclass 为只读对象；`to_dict()` 递归将日期、时间转为 ISO 8601 字符串，将元组转为列表 |

## 2. 实时行情

| 函数 | 参数 | 返回 |
| --- | --- | --- |
| `get_stock_quote` / `get_etf_quote` / `get_index_quote` | `code: str` | `Quote` |
| `get_stock_quotes` / `get_etf_quotes` / `get_index_quotes` | `codes: Sequence[str]` | `list[Quote]` |
| `get_quote` | `code, *, instrument="auto"` | `Quote` |
| `get_quotes` | `codes, *, instrument="auto"` | `list[Quote]` |

```python
from ashare_data import get_etf_quote, get_quotes

quote = get_etf_quote("159941")
print(quote.last, quote.iopv, quote.premium_rate_pct)
print(quote.bids[0].price, quote.bids[0].volume)

quotes = get_quotes(["sz159941", "sh600519", "sh000001"])
```

实时行情采用腾讯。单只查询缺失时抛出 `QuoteNotFoundError`；批量查询的缺失项为 `Quote`，其 `error` 包含原因，其余可选字段为 `None`。整次网络或响应解析失败时抛出对应异常。

### Quote

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `symbol` / `code` | `str` | 带市场前缀的证券标识 / 六位代码 |
| `instrument` | `str` | `stock`、`etf`、`index`；混合查询缺失项可为 `auto` |
| `source` | `str` | 本次实际数据来源 |
| `name` | `str \| None` | 证券名称 |
| `timestamp` | `datetime \| None` | 行情时间 |
| `currency` | `str \| None` | 标价币种，例如 `CNY` |
| `last` / `prev_close` | `float \| None` | 最新价 / 昨收价 |
| `open` / `high` / `low` | `float \| None` | 当日开盘价 / 最高价 / 最低价 |
| `change` / `change_pct` | `float \| None` | 相对昨收的涨跌额 / 涨跌幅 |
| `volume` / `amount` | `float \| None` | 当日累计成交数量 / 成交金额 |
| `outer_volume` / `inner_volume` | `float \| None` | 外盘 / 内盘成交数量 |
| `turnover_rate_pct` / `amplitude_pct` | `float \| None` | 换手率 / 振幅 |
| `market_cap` / `circulating_market_cap` | `float \| None` | 总市值 / 流通市值 |
| `pe` / `pb` | `float \| None` | 股票市盈率 / 市净率 |
| `limit_up` / `limit_down` | `float \| None` | 涨停价 / 跌停价 |
| `volume_ratio` | `float \| None` | 量比 |
| `order_imbalance` | `float \| None` | 买五档数量合计减卖五档数量合计 |
| `average_price` | `float \| None` | 当日成交均价 |
| `is_suspended` | `bool` | 源端停牌标记 |
| `bids` / `asks` | `tuple[OrderLevel, ...]` | 买 / 卖报价，按一档到五档排列；缺失行情时为空元组 |
| `iopv` | `float \| None` | ETF 份额参考净值 |
| `premium_rate_pct` | `float \| None` | ETF 折溢价率；正数为溢价，负数为折价 |
| `circulating_shares` / `total_shares` | `float \| None` | 流通 / 总股票股数或基金份数 |
| `error` | `str \| None` | 批量缺失项的错误信息；成功时为 `None` |

`OrderLevel` 表示一档买卖报价。

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `price` | `float \| None` | 该档报价 |
| `volume` | `float \| None` | 该档委托数量，股或份 |

ETF 专属字段在其他品种上为 `None`；其余可选字段由品种与数据可用性决定。

## 3. 历史 K 线

`get_stock_history`、`get_etf_history`、`get_index_history` 共用以下签名，返回 `list[Bar]`：

```python
get_etf_history(
    code, start=None, end=None, *,
    sources=None, adjust="none", scale=240, datalen=5049, max_pages=100,
)
```

`get_history` 使用相同参数，并增加 `instrument="auto"`。

| 参数 | 含义 |
| --- | --- |
| `sources` | 按优先级排列的列表；日线默认 `["tencent", "sina"]`，分钟线默认 `["sina"]` |
| `adjust` | `"none"` 原始价格、`"qfq"` 前复权、`"hfq"` 后复权；指数使用 `"none"` |
| `scale` | `240` 日线；`5`、`15`、`30` 分钟线 |
| `datalen` | 新浪最近 K 线数量，1～5049，默认 5049 |
| `max_pages` | 腾讯历史分页上限，正整数，默认 100 |

来源出错后按顺序尝试下一个兼容来源，成功后返回该来源的结果。选择兼容来源时保持周期和复权方式一致：

| 周期、价格方式 | 可用来源 |
| --- | --- |
| 日线，原始价格 | `tencent`、`sina` |
| 日线，前复权或后复权 | `tencent` |
| 5 / 15 / 30 分钟线，原始价格 | `sina` |

`sources` 支持调整顺序或仅保留所需来源。新浪提供最近记录；条数上限截断所请求的起始日期时报告来源失败。所有兼容来源失败时抛出 `AllSourcesFailedError`。请求的周期与复权方式缺少兼容来源时抛出 `ConfigurationError`。

```python
from ashare_data import get_etf_history

daily = get_etf_history("159941", "2026-10-01", "2026-10-23")
minute = get_etf_history("159941", "2026-10-23", "2026-10-23", scale=5)
adjusted = get_etf_history("159941", "2026-01-01", "2026-10-23", adjust="qfq")
preferred = get_etf_history(
    "159941", "2026-10-01", "2026-10-23", sources=["sina", "tencent"],
)
print(daily[-1].close)
```

### Bar

沪深历史与海外历史共用 `Bar`。

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `symbol` | `str` | 沪深为市场前缀代码，海外为服务商证券代码 |
| `timestamp` | `datetime` | K 线记录的日期或时间；日线为所属交易日零点 |
| `interval` | `str` | 周期，如 `1day`、`5min` |
| `source` | `str` | 本次实际来源 |
| `adjust` | `str` | 实际价格方式：`none`、`qfq`、`hfq`、`all`、`splits`、`dividends` |
| `open` / `high` / `low` / `close` | `float \| None` | 开盘 / 最高 / 最低 / 收盘价格；成功记录的收盘价有值 |
| `volume` | `float \| None` | 该周期成交数量 |
| `volume_unit` | `str` | 沪深为 `share`：股或份；海外为 `provider`：服务商对该品种定义的成交量单位 |
| `currency` | `str \| None` | 标价币种；沪深为 `CNY`，海外随品种确定 |

## 4. 基金净值、目录与份额

| 函数 | 签名 | 返回 |
| --- | --- | --- |
| `get_fund_nav_history` | `(code, start=None, end=None, *, sources=None)` | `list[FundNav]` |
| `get_etf_catalog` | `()` | `dict[str, str]`，六位 ETF 代码到名称的映射 |
| `get_sse_etf_shares` | `(day)`，统计日期 | `list[FundShares]`，上交所 ETF 份额 |
| `get_etf_pcf` | `(code)` | `ETFPcf`，最新申购赎回清单 |
| `get_etf_holdings` | `(code)` | `list[ETFHolding]`，最新证券篮子市值占比，降序排列 |

净值的默认来源顺序为 `["eastmoney_mobile", "eastmoney_web"]`，可用 `sources` 调整优先级。移动端失败后，网页接口重新获取完整区间；同一客户端自动管理请求间隔和冷却状态。

```python
from ashare_data import get_fund_nav_history, get_etf_catalog, get_sse_etf_shares

nav = get_fund_nav_history("159941", "2026-10-01", "2026-10-23")
print(nav[-1].date, nav[-1].nav)
catalog = get_etf_catalog()
shares = get_sse_etf_shares("2026-10-23")
```

`FundNav` 与 `FundShares` 的字段如下。

| 字段 | 类型 | 所属类型与含义 |
| --- | --- | --- |
| `code` | `str` | 两者共用，六位基金代码 |
| `date` | `date` | 净值所属日 / 份额统计日 |
| `source` | `str` | 本次实际来源 |
| `nav` | `float` | FundNav 单位净值，币种随基金份额类别确定 |
| `shares` | `float \| None` | FundShares 基金份额，单位份 |

### 最新申赎清单与市值占比

PCF（Portfolio Composition File）是基金每日公布的申购赎回清单。两个接口均只接收 ETF 代码，支持六位代码、市场前缀和后缀；从交易所获取最新清单，在内存中解析和计算，每次调用重新取数。深交所从最近一年公告中选择最新文件，周末和长假使用已公布的最近清单。

公开来源：[上交所申购赎回清单](https://www.sse.com.cn/assortment/fund/list/etfinfo/redemptionlist/index.shtml?FUNDID=510300)、[深交所申购赎回清单](https://www.szse.cn/disclosure/fund/currency/index.html?txtJCorDH=159502)。

美股类别股支持清单中的 `BF/B`、`BRK/B` 及点号格式 `BF.B`、`BRK.B`，查询腾讯行情时统一使用点号，返回的 `code` 保留清单原始代码。

```python
from ashare_data import get_etf_pcf, get_etf_holdings

pcf = get_etf_pcf("159502")
print(pcf.creation_unit, len(pcf.components))
holdings = get_etf_holdings("159502")
for row in holdings[:10]:
    print(row.code, row.quantity, f"{row.weight_pct:.2f}%")
```

`get_etf_holdings` 支持沪深北港美股票。通常按 `market_value = quantity × price × exchange_rate` 计算，其中价格和人民币汇率均取腾讯最新报价。现金替代标志为 `2` 且清单给出固定替代金额的证券，按该人民币金额估值；`valuation` 标明采用 `quote` 或 `cash_substitute`。`weight_pct = market_value / 全部证券的人民币市值之和 × 100`，例如 `2.23` 表示 `2.23%`。返回全部证券，零数量且替代金额为零的证券占比为零；需要按数量估值的正数量证券行情缺失或汇率缺失时抛出 `QuoteNotFoundError`。报价包含数据源提供的延迟，股票占比随行情变化。

这一占比描述申赎证券篮子的市值构成，总和为 100%。清单的证券数量对应一个最小申赎单位；基金净资产还包括现金、应收应付等项目。`159900` 申赎现金单独保存在 `ETFPcf.components`，`is_cash=True`，其现金替代金额用于申赎结算。`get_etf_pcf` 支持读取交易所 XML 中的股票、债券、黄金等成分。

`ETFPcf` 字段：

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `code` | `str` | 六位 ETF 代码 |
| `source` | `str` | `sse` 或 `szse` |
| `creation_unit` | `float` | 最小申赎单位，份 |
| `nav_per_cu` | `float` | 清单公布的最小申赎单位净值，人民币 |
| `cash_component` | `float \| None` | 清单公布的现金差额，人民币，可为负 |
| `components` | `tuple[ETFComponent, ...]` | 完整成分及申赎现金项目 |

`ETFComponent` 字段：

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `code` / `name` | `str` | 成分代码 / 名称，保留交易所原文 |
| `market` | `str` | 交易所市场代码：`101` 沪、`102` 深、`103` 港、`104` 或 `106` 北、`9999` 其他 |
| `quantity` | `float` | 一个最小申赎单位的成分数量 |
| `substitution_flag` | `str` | 交易所原始现金替代标志 |
| `creation_premium_rate` | `float \| None` | 申购现金替代溢价率，小数，`0.1` 表示 10% |
| `redemption_discount_rate` | `float \| None` | 赎回现金替代折价率，小数 |
| `creation_cash_substitute` / `redemption_cash_substitute` | `float \| None` | 申购 / 赎回现金替代金额，人民币；上交所对应同一替代金额字段 |
| `is_cash` | `bool` | 是否为深交所 `159900` 申赎现金项目 |

`ETFHolding` 字段：

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `code` / `name` / `market` | `str` | 成分代码 / 名称 / 交易所市场代码 |
| `quantity` | `float` | 一个最小申赎单位的成分数量 |
| `price` | `float \| None` | 证券最新价格，原币种；现金替代或零数量证券的报价缺失时为 None |
| `currency` | `str` | `CNY`、`HKD` 或 `USD` |
| `exchange_rate` | `float` | 一单位原币兑换人民币的金额 |
| `market_value` | `float` | 一个最小申赎单位内该证券的市值，人民币 |
| `weight_pct` | `float` | 证券市值占整个证券篮子市值的百分数 |
| `valuation` | `str` | `quote` 按行情估值；`cash_substitute` 使用清单固定人民币替代金额 |

## 5. FRED 与海外行情

| 函数 | 签名 | 返回 |
| --- | --- | --- |
| `get_fred_series` | `(series_id, start=None, end=None, *, api_key=None)` | `list[Observation]` |
| `get_vix_history` | `(start=None, end=None, *, api_key=None)` | `list[Observation]`，VIX 日度收盘序列 `VIXCLS` |
| `get_twelve_bars` | `(symbol, *, interval="1day", outputsize=5000, start=None, end=None, adjust="all", api_key=None)` | 一页 `list[Bar]` |
| `get_twelve_daily_history` | `(symbol, start=None, end=None, *, adjust="all", api_key=None, max_pages=100)` | 自动分页的 `list[Bar]` |

FRED 密钥环境变量为 `FRED_API_KEY`，Twelve Data 为 `TWELVE_DATA_API_KEY`。密钥优先级：单次 `api_key` → 客户端配置 → 环境变量。

Twelve Data 的 `outputsize` 为 1～5000；`interval` 按账户支持的周期传入；`adjust` 可为 `none`、`splits`、`dividends`、`all`。`get_twelve_bars` 的起止参数可使用日期或日期时间字符串；完整日线的起止参数使用日期。可用市场、历史长度和调用额度由账户权限决定。

```python
from ashare_data import MarketClient

client = MarketClient(fred_api_key="YOUR_FRED_KEY", twelve_api_key="YOUR_TWELVE_KEY")
vix = client.get_vix_history("2026-10-01", "2026-10-23")
spy = client.get_twelve_daily_history("SPY", "2026-01-01", "2026-10-23")
```

`Observation` 表示序列的单次有效观测。

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `series_id` | `str` | FRED 序列标识 |
| `date` | `date` | 观测日期 |
| `value` | `float` | 有效观测值，单位由该 FRED 序列定义 |
| `source` | `str` | 本次实际来源 |

## 6. 配置、客户端与异常

`configure` 签名为 `(*, timeout=10, retries=1, fred_api_key=None, twelve_api_key=None) -> MarketClient`，设置顶层函数使用的默认客户端。`timeout` 为每次网络请求超时秒数，须大于 0；`retries` 为网络异常及临时网关错误的重试次数，须为非负整数。

`MarketClient` 使用相同配置参数，实例方法与顶层函数同名、同参数、同返回类型。`AsyncMarketClient` 提供对应的 `await` 方法。实例间配置独立；同一客户端复用净值限速和冷却状态。异步取消后，已开始的网络请求由超时约束。

```python
import asyncio
from ashare_data import AsyncMarketClient, configure

configure(timeout=10, retries=1)

async def main():
    client = AsyncMarketClient(timeout=10)
    quote = await client.get_etf_quote("159941")
    print(quote.last)

asyncio.run(main())
```

| 异常 | 含义 |
| --- | --- |
| `MarketDataError` | 全部公开行情异常的父类 |
| `InvalidCodeError` | 代码格式错误 |
| `ConfigurationError` | 参数、来源能力或密钥配置错误 |
| `RequestError` | 网络或 HTTP 错误；`status_code` 为 HTTP 状态码，`retry_after` 为建议等待秒数 |
| `DataFormatError` | 来源响应或分页结果异常 |
| `QuoteNotFoundError` | 单只证券行情缺失 |
| `AllSourcesFailedError` | 所有候选来源失败；`errors` 为按尝试顺序排列的 `(来源名, 异常)` 列表 |

