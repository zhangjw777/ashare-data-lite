"""安装项目后执行 python examples/basic.py。"""

from pprint import pprint

from ashare_data import (
    get_etf_quote,
    get_fund_nav_history,
    get_index_quote,
    get_stock_quote,
)


def main():
    pprint(get_etf_quote("159941"))
    pprint(get_stock_quote("600519"))
    pprint(get_index_quote("000001"))
    pprint(get_fund_nav_history("159941", "2026-10-01", "2026-10-21")[-3:])


if __name__ == "__main__":
    main()
