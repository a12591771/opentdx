from datetime import date

import pandas as pd
from opentdx.client import macQuotationClient, macExQuotationClient
from opentdx.const import (
    ADJUST, BLOCK_FILE_TYPE, CATEGORY, EX_CATEGORY, EX_MARKET, FILTER_TYPE,
    MARKET, PERIOD, EX_BOARD_TYPE, BOARD_TYPE, SORT_TYPE,
)
from opentdx.parser.ex_quotation import file, goods
from opentdx.parser.quotation import server, stock
from opentdx.utils.bitmap import FieldBit, PresetField
from opentdx.utils.help import industry_to_board_symbol
import time

if __name__ == "__main__":

    test_symbol_bars = True
    test_board = True

    category = CATEGORY.CYB
    client = macQuotationClient(raise_exception=True)
    client.connect()

    for i in range(0, 15):
        rs = client.count_board_members(str(i))
        time.sleep(0.1)
        print(i, rs)
    exit()
    # rs = client.get_stock_quotes_list(category=category,count=10,sortType=SORT_TYPE.CHANGE_PCT)
    # df1 = pd.DataFrame(rs)
    # print(df1.iloc[3])
    rs = client.get_board_members_quotes(board_symbol="10000", count=300, fields=PresetField.ALL)
    df = pd.DataFrame(rs)
    df.to_csv("bk.csv")
    print(df)

    board_symbol = "880548"
    rs = client.get_board_members_quotes(board_symbol=board_symbol, count=20, fields=PresetField.AH_CODE)
    df = pd.DataFrame(rs)

    df.to_csv("test.csv")
    if 'industry' in df.columns:
        df['board_symbol'] = df['industry'].apply(lambda x: industry_to_board_symbol(x))
        df = df[['symbol', 'industry', 'board_symbol']]

    print(df)
