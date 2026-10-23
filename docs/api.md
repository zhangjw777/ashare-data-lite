# 行情源接口手册

更新日期：2026-10-23。项目路径：`F:\FinancialData\a-share-data`。安装：`python -m pip install -e F:\FinancialData\a-share-data`。运行代码使用 Python 标准库，返回 Python 字典和列表。

实现参考 `F:\excellent-opensource-dev\global_asset_history\backend\app\providers`，请求与解析代码位于 `src/ashare_data/sources/`。公开入口统一由 `ashare_data/__init__.py` 导出。

## 1. 调用约定

```python
from ashare_data import get_etf_quote, get_fund_nav_history

quote = get_etf_quote("159941")
nav = get_fund_nav_history("159941", "2026-10-01", "2026-10-21")
```

日期使用 `YYYY-MM-DD` 字符串或 `datetime.date`，起止日期均包含。默认起始日 `1970-01-01`，默认截止日为中国时区当天；新浪历史的实际返回范围遵循最近记录上限。代码以字符串传入，支持 `159941`、`sz159941`、`159941.SZ`。指数通过指数入口调用，或使用带市场前缀的代码。

ETF 为交易所交易基金，NAV 为基金单位净值，IOPV 为基金份额参考净值，OHLC 为开盘、最高、最低、收盘价格。复权表示对拆股、分红等事件调整历史价格。

| 公共函数 | 参数要点 | 返回 |
| --- | --- | --- |
| `get_stock_quote` / `get_etf_quote` / `get_index_quote` | `code` | 单只行情字典 |
| `get_stock_quotes` / `get_etf_quotes` / `get_index_quotes` | `codes` 字符串列表 | 行情列表 |
| `get_quote` / `get_quotes` | `code` / `codes`，`instrument="auto"` | 混合品种行情 |
| `get_stock_history` / `get_etf_history` | `code, start=None, end=None, source="tencent", adjust="qfq", scale=240, datalen=5049, max_pages=100` | 历史 K 线列表 |
| `get_index_history` | 同上，默认 `adjust=""` | 指数历史列表 |
| `get_history` | 历史参数及 `instrument="auto"` | 通用历史列表 |
| `get_fund_nav_history` | `code, start=None, end=None` | 历史单位净值列表 |
| `get_etf_catalog` | 空参数 | 代码到名称的字典 |
| `get_sse_etf_shares` | `day` | 上交所 ETF 份额列表 |
| `get_fred_series` | `series_id, start=None, end=None, api_key=None` | 有效观测列表 |
| `get_vix_history` | `start=None, end=None, api_key=None` | `VIXCLS` 序列 |
| `get_twelve_bars` | `symbol, interval="1day", outputsize=5000, start=None, end=None, adjust="all", api_key=None` | 一页 K 线 |
| `get_twelve_daily_history` | `symbol, start=None, end=None, adjust="all", api_key=None, max_pages=100` | 完整日期范围日线 |

所有函数均有对应的 `MarketClient` 方法与 `AsyncMarketClient` 方法。异步客户端使用 `await client.get_etf_quote("159941")`；线程执行网络请求，限速状态由客户端共享。

## 2. 腾讯：全部实时行情

请求：`GET https://qt.gtimg.cn/q=sz159941,sh600519,sh000001`。响应使用 GBK 编码，以 `v_证券代码="字段~字段~...";` 表示每只证券。每批最多 50 个代码，输入按首次出现顺序去重。单只行情缺失时抛出 `QuoteNotFoundError`，批量缺失项返回 `{"symbol": "...", "source": "tencent", "error": "行情缺失"}`。

股票入口的 `000001` 对应 `sz000001`；指数入口的 `000001` 对应 `sh000001`。`399xxx` 指数使用深市；其他指数使用明确市场前缀。沪深股票、ETF、指数的实时行情全部由同一腾讯入口获取。

### 2.1 文本字段与单位

下标从 0 开始，解析实现沿用参考项目的腾讯 provider。

| 下标 | 返回字段 / 含义 |
| --- | --- |
| 1 / 2 | `name` / `code` |
| 3 / 4 / 5 | `last` / `prev_close` / `open` |
| 6 / 7 / 8 | `volume_lot` / `outer_volume_lot` / `inner_volume_lot`，单位手 |
| 9～18 / 19～28 | 买五档 / 卖五档，价格和手数交替 |
| 29 / 30 | `recent_trades_raw` / 行情时间 `YYYYMMDDHHMMSS` |
| 31 / 32 / 33 / 34 | `change` / `change_pct` / `high` / `low` |
| 35 | 成交摘要第 3 项为成交额（元） |
| 38 / 39 / 40 | `turnover_rate`（百分数）/ 股票 `pe` / `S` 停牌标记 |
| 43 / 44 / 45 / 46 | `amplitude`（百分数）/ 流通市值（亿元）/ 总市值（亿元）/ `pb` |
| 47 / 48 / 49 / 50 / 51 | `limit_up` / `limit_down` / `volume_ratio` / `order_imbalance_lot` / `average_price` |
| 57 | `amount_10k`，单位万元 |
| 60 / 61 | `market_status_code` / `type_tag` |
| 72 / 73 | 流通份额或股数 / 总份额或股数 |
| 77 / 78 | ETF `premium_rate`（百分数）/ `iopv` |
| 82 | `currency` |

`order_book.bids`、`order_book.asks` 各含 5 档，每档包括 `level`、`price`、`volume_lot`。`amount_yuan` 优先采用成交摘要，备用读取字段 57 乘 10000。`average_price_calculated = amount_yuan / (volume_lot * 100)`；`order_imbalance_calculated` 为买五档手数合计减卖五档手数合计。

`source="tencent"`；`symbol` 保留市场前缀，`market` 为 `sh` 或 `sz`；`quote_time` 为 `YYYY-MM-DD HH:MM:SS`，`quote_time_raw` 保留原始时间。`raw_fields` 保存全部字段。字段含义随品种确定，扩展原文用于逐项核对。

### 2.2 品种扩展

ETF 以 `etf` 返回 `iopv`、`premium_rate`、`premium_rate_calculated`、`circulating_units`、`total_units`、`nav_reference_candidate`。计算溢价率为 `(last / iopv - 1) * 100`。

股票以 `stock` 返回 `pe`、`pe_candidate_1`、`pe_candidate_2`、`circulating_shares`、`total_shares`。指数以 `index` 保存扩展字段。`instrument_type` 为 `etf`、`stock` 或 `index`。

各品种扩展均包含 `statistics_candidates` 和 `raw_extension`。字段 67/68、69～71、79 分别保留为年内高低、短期收益及年度收益候选值；52/53 为股票市盈率候选值；81 为 ETF 净值参考候选值。`raw_extension` 保存 62 起的原始字符串字段。

## 3. 腾讯：历史日线

请求：`GET https://proxy.finance.qq.com/ifzqgtimg/appstock/app/newfqkline/get`。

| 参数 | 示例 | 含义 |
| --- | --- | --- |
| `param` | `sz159941,day,,2026-10-21,640,qfq` | 代码、周期、起始日期、截止日期、条数、复权方式 |

`adjust="qfq"` 为前复权，`"hfq"` 为后复权，`""` 为原始价格。按所选方式读取 `data[证券代码].qfqday`、`hfqday` 或 `day`。指数使用原始价格。

每条记录前六项为 `[日期, 开盘, 收盘, 最高, 最低, 成交量]`。返回记录的 `volume_unit="lot"`，`source="tencent"`；扩展列保存在 `raw`。日期向前分页，每页 640 条，下一页截止日期为本页最早日期的前一天，取得起始日后结束。结果按 `datetime` 去重升序排列；达到 `max_pages` 时抛出 `DataFormatError`。

## 4. 新浪：历史 K 线与 ETF 目录

### 4.1 K 线

请求：`GET http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData`。

| 参数 | 值示例 |
| --- | --- |
| `symbol` | `sz159941` |
| `scale` | `240` 日线；`5` / `15` / `30` 分钟线 |
| `ma` | `no` |
| `datalen` | `5049`，允许 1～5049 |

响应数组包含 `day`、`open`、`close`、`high`、`low`、`volume`。公开历史接口选择 `source="sina", adjust=""`，按 `day` 筛选目标区间，保留实际返回的最近记录。日期跨度与 5049 条上限共同决定覆盖范围。`volume_unit="upstream"` 表示采用上游数值与单位，`raw` 保存原始记录；时间采用中国交易市场时间。

### 4.2 ETF 目录

请求：`GET https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData`。

| 参数 | 值 |
| --- | --- |
| `page` / `num` | `1` 起的页码 / `100` |
| `sort` / `asc` | `symbol` / `0` |
| `node` | `etf_hq_fund` |

从数组记录的 `code`、`name` 构建字典，少于 100 条时结束。重复页或达到 1000 页时抛出 `DataFormatError`。

## 5. 东方财富：基金历史单位净值

`get_fund_nav_history` 优先调用移动端；移动端请求、业务状态、字段解析或分页失败后，从网页接口重新获取完整结果。两个来源都失败时抛出 `AllSourcesFailedError`，其 `errors` 保存逐源异常。

### 5.1 移动端

请求：`GET https://fundmobapi.eastmoney.com/FundMNewApi/FundMNHisNetList`。

| 参数 | 值 |
| --- | --- |
| `FCODE` | 六位基金代码 |
| `pageIndex` / `pageSize` | `1` 起的页码 / `40000` |
| `appType` / `cToken` / `deviceid` | `ttjj` / `1` / `1` |
| `plat` / `product` | `Iphone` / `EFund` |
| `serverVersion` / `version` | `6.2.8` / `6.2.8` |

请求头：

```text
User-Agent: EMProjJijin/6.2.8 (iPhone; iOS 13.6; Scale/2.00)
GTOKEN: 98B423068C1F4DEF9842F82ADF08C5db
clientInfo: ttjj-iPhone10,1-iOS-iOS13.6
Referer: https://mpservice.com/516939c37bdb4ba2b1138c50cf69a2e1/release/pages/FundHistoryNetWorth
```

成功状态 `ErrCode=0`，从 `Datas` 读取记录，按 `TotalCount` 完成分页；累计计数使用日期筛选前的条数。按响应 `FSRQ` 的真实日期筛选区间，`DWJZ` 转为 `nav`。`source="eastmoney_mobile"`。

### 5.2 网页接口

请求：`GET https://api.fund.eastmoney.com/f10/lsjz`，请求头 `Referer: https://fundf10.eastmoney.com/jjjz_159941.html`，代码随查询变化。

| 参数 | 值 |
| --- | --- |
| `fundCode` | 六位基金代码 |
| `pageIndex` / `pageSize` | `1` 起的页码 / `20` |
| `startDate` / `endDate` | `YYYY-MM-DD` 起止日期 |

成功状态 `ErrCode=0`，记录位于 `Data.LSJZList`，按 `TotalCount` 继续分页；`FSRQ` 为日期，`DWJZ` 为单位净值。`source="eastmoney_web"`。

结果统一为 `{"code": "159941", "valuation_date": "2026-10-21", "nav": 1.5, "source": "eastmoney_mobile", "raw": {...}}`，示例数值用于说明结构。按真实日期去重升序排列，空区间返回空列表。

同一客户端共享并发上限 2、0.25 秒请求间隔。移动端单次超时为 `min(timeout, 5)` 秒，失败后冷却 60 秒；403/429 同时参考 `Retry-After`。网页冷却独立保存；源端空页导致条数尚未达到 `TotalCount`、重复页或达到 1000 页时报告分页错误。

## 6. 上交所：ETF 份额

请求：`GET https://query.sse.com.cn/commonQuery.do`，请求头 `Referer: https://www.sse.com.cn/`。

| 参数 | 值 |
| --- | --- |
| `isPagination` | `true` |
| `pageHelp.pageSize` / `pageHelp.pageNo` | `10000` / `1` |
| `pageHelp.beginPage` / `pageHelp.endPage` / `pageHelp.cacheSize` | `1` / `1` / `1` |
| `sqlId` | `COMMON_SSE_ZQPZ_ETFZL_XXPL_ETFGM_SEARCH_L` |
| `STAT_DATE` | `YYYY-MM-DD` |

读取 `result` 数组，`SEC_CODE` → `code`，`STAT_DATE` → `date`，`TOT_VOL * 10000` → `shares`。返回 `unit="share"`（份）、`source="sse"`、原始 `raw`。查询范围沿用参考项目的第一页、10000 条配置。

## 7. FRED：经济序列和 VIX

请求：`GET https://api.stlouisfed.org/fred/series/observations`。

| 参数 | 值 |
| --- | --- |
| `api_key` | 账户密钥 |
| `series_id` | 例如 `VIXCLS` |
| `file_type` / `sort_order` | `json` / `asc` |
| `observation_start` / `observation_end` | 起止日期 |
| `limit` / `offset` | `100000` / 从 `0` 起累加实际页长度 |

读取 `observations`，累计条数达到 `count` 时结束。有效记录返回 `date`、UTC 零点的 Unix 秒时间戳 `timestamp`、数值 `value`、`series_id`、`source="fred"`、`raw`；`"."` 缺失值跳过。`get_vix_history` 使用同一接口查询 `VIXCLS`。

账户配置使用 `FRED_API_KEY` 环境变量、客户端 `fred_api_key=` 或单次调用的 `api_key=`。单次参数优先。

## 8. Twelve Data：海外 K 线

请求：`GET https://api.twelvedata.com/time_series`。

| 参数 | 值 |
| --- | --- |
| `apikey` | 账户密钥 |
| `symbol` | 例如 `SPY`、`AAPL` |
| `interval` | 默认 `1day`，按服务商支持的周期传入 |
| `outputsize` | 1～5000，默认 5000 |
| `start_date` / `end_date` | 日期或时间，可选 |
| `timezone` / `order` | `UTC` / `desc` |
| `adjust` | `none` / `splits` / `dividends` / `all`，默认 `all` |

读取 `values`，`status="error"` 转为 `DataFormatError`。每条返回 `datetime`、`trade_date`、UTC Unix 秒时间戳 `timestamp`、OHLC、`volume`、`volume_unit="upstream"`、`source="twelvedata"`、`adjust`、响应 `meta` 和原始 `raw`。

`get_twelve_bars` 获取一页；`get_twelve_daily_history` 每页 5000 条，下一页截止时间为本页最早时间前一秒，按时间去重升序排列。`max_pages=100` 为默认上限，达到上限时抛出分页错误。

账户配置使用 `TWELVE_DATA_API_KEY` 环境变量、客户端 `twelve_api_key=` 或单次调用的 `api_key=`。覆盖市场、历史长度与调用额度由账户权限确定。

## 9. 公开行为与验证

网络请求由 `urllib.request` 完成，JSON 与 GBK 文本由标准库解析。默认请求超时 10 秒；网络错误及 HTTP 502/503/504 重试 1 次，退避间隔从 0.5 秒开始。HTTP 错误的 `RequestError` 保存 `status_code` 和 `retry_after`，异常消息仅输出主机及路径。

模拟测试覆盖公开入口、代码格式、分页推进、净值失败切换与冷却、原始字段保留、份额单位换算、账户接口及异步调用。在线请求结果另存于项目 `docs/live-check.json`，以记录的检查时间、样本和状态为准。

来源选择由 `client.py` 管理，来源协议由 `sources/` 管理。修改内部实现时维持本手册的公开函数、参数含义和返回字段。
