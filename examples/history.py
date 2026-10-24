"""历史行情及账户 API 示例；密钥读取环境变量。"""

from pprint import pprint

from ashare_data import MarketClient


def main():
    client = MarketClient()
    pprint(client.get_etf_history("159941", "2026-09-01", "2026-10-24")[-3:])
    pprint(client.get_index_history("000001", "2026-09-01", "2026-10-24")[-3:])
    # 账户接口按所需数据调用。
    # pprint(client.get_vix_history("2026-10-01", "2026-10-21"))
    # pprint(client.get_twelve_daily_history("SPY", "2026-10-01", "2026-10-21"))


if __name__ == "__main__":
    main()
