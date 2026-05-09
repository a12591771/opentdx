from datetime import date

import pandas as pd
from opentdx.client import macQuotationClient, macExQuotationClient
from opentdx.const import ADJUST, CATEGORY, EX_CATEGORY, EX_MARKET, MARKET, PERIOD, EX_BOARD_TYPE, BOARD_TYPE
from opentdx.utils.bitmap import FieldBit, PresetField
from opentdx.parser.ex_quotation import file, goods
from opentdx.parser.quotation import server, stock
from opentdx.utils.help import industry_to_board_symbol, ah_code_to_symbol, lot_size_to_symbol


if __name__ == "__main__":

    test_symbol_bars = True
    test_board = True

    category = CATEGORY.A
    board_symbol = str(CATEGORY.A.value)
    client = macQuotationClient()
    client.connect()
    print("MAC 模式已启用, 支持板块/K线/资金流向接口")

    print("使用get_board_members_quotes查询板块股票")
    rs = client.get_board_members_quotes(board_symbol=board_symbol, count=10)
    df = pd.DataFrame(rs)
    print(df)

    # 测试资金流向
    print("\n***** 测试资金流向 get_symbol_zjlx *****")
    symbol = '603019'
    market = MARKET.SH
    try:
        df_zjlx = client.get_symbol_zjlx(symbol=symbol, market=market)
        if df_zjlx is not None and len(df_zjlx) > 0:
            print(f"股票 {market} {symbol} 资金流向数据:")
            print(df_zjlx.iloc[0])
        else:
            print(f"股票 {market} {symbol} 暂无资金流向数据")
    except Exception as e:
        print(f"获取资金流向数据失败: {e}")
        import traceback
        traceback.print_exc()
    print("***** 资金流向测试结束 *****\n")

    active_stocks = client.top_board_members(board_symbol=category)
    df_active = pd.DataFrame(active_stocks)
    print(df_active)

    print("启用get_board_members_quotes查询板块股票")
    rs = client.get_board_members_quotes(board_symbol=category, count=10)
    df = pd.DataFrame(rs)
    print(df)

    print("支持自定义字段 ohlc , 增加ah_code , 查询881394板块-券商板块")
    rs = client.get_board_members_quotes(board_symbol="881394", count=100, fields=PresetField.OHLC + FieldBit.AH_CODE + FieldBit.LOT_SIZE + FieldBit.INDUSTRY)
    df = pd.DataFrame(rs)

    if 'ah_code' in df.columns:
        df['ah_code'] = df.apply(lambda row: ah_code_to_symbol(row['ah_code'], row['market']), axis=1)

    if 'lot_size' in df.columns:
        df['dq_symbol'] = df.apply(lambda row: lot_size_to_symbol(row['lot_size']), axis=1)

    print(df)

    print("支持自定义字段 ohlc , 增加ah_code , 查询880201板块-黑龙江板块")
    rs = client.get_board_members_quotes(board_symbol="880201", count=100, fields=PresetField.OHLC + FieldBit.INDUSTRY)
    df = pd.DataFrame(rs)

    if 'industry' in df.columns:
        df['industry_symbol'] = df['industry'].apply(lambda x: industry_to_board_symbol(x))

    print(df)

    print("支持自定义字段 ohlc")
    rs = client.get_board_members_quotes(board_symbol=board_symbol, count=10, fields=PresetField.OHLC)
    df = pd.DataFrame(rs)
    print(df)

    exClient = macExQuotationClient()
    exClient.connect()

    print("支持自定义字段 ohlc , 增加ah_code , [HK0266] 反向查询A股代码")
    rs = exClient.get_board_members_quotes(board_symbol="HK0266", count=10, fields=PresetField.OHLC + FieldBit.AH_CODE)
    df = pd.DataFrame(rs)
    print(df)

    board_symbol = "HK0281"
    rs = exClient.get_board_members_quotes(board_symbol=board_symbol)
    df = pd.DataFrame(rs)
    print(f"港股板块 {board_symbol} 成员数量: {len(df)} 展示部分:")
    print(df[:3])

    board_symbol = "US0218"
    rs = exClient.get_board_members_quotes(board_symbol=board_symbol)
    df = pd.DataFrame(rs)
    print(f"美股板块 {board_symbol} 成员数量: {len(df)} 展示部分:")
    print(df[:3])

    print("查询香港主板")
    board_symbol = EX_CATEGORY.HSI
    rs = exClient.get_board_members_quotes(board_symbol=board_symbol, count=10, fields=PresetField.OHLC + FieldBit.AH_CODE)
    df = pd.DataFrame(rs)
    print(f"查询香港主板 {board_symbol} 成员数量: {len(df)} 展示部分:")
    print(df[:3])

    count = 40
    symbol = '600900'
    market = MARKET.SH
    fq = ADJUST.QFQ
    rs = client.get_symbol_bars(market, symbol, PERIOD.DAILY, count=count, fq=fq)
    df = pd.DataFrame(rs)
    df['换手'] = df['vol'] / (df['float_shares'] * 10000) * 100
    df['换手'] = df['换手'].round(2).abs()
    print(f"股票 {market} {symbol} {fq} 的前{count}个交易日行情数据如下:")
    print(df)

    board_symbol = "US0401"
    rs = exClient.get_board_members_quotes(board_symbol=board_symbol, count=2)
    print(rs)

    if client.connect().login():
        symbol = '000100'
        market = MARKET.SZ

        print("无复权   ", symbol, market)
        print(pd.DataFrame(client.get_kline(market, symbol, PERIOD.DAILY, count=3)))
        print("前复权   ", symbol, market)
        print(pd.DataFrame(client.get_kline(market, symbol, PERIOD.DAILY, count=4, adjust=ADJUST.QFQ)))
        print("后复权   ", symbol, market)
        print(pd.DataFrame(client.get_kline(market, symbol, PERIOD.DAILY, count=3, adjust=ADJUST.HFQ)))

    if test_board:
        print("板块列表查询 ")
        market = BOARD_TYPE.DQ
        rs = client.get_board_list(market=market)
        df = pd.DataFrame(rs)
        print(f"地区板块 {market} 查询板块列表: {len(df)} 展示部分:")
        print(df[:3])

        market = BOARD_TYPE.HY
        rs = client.get_board_list(market=market)
        df = pd.DataFrame(rs)
        print(f"行业板块 {market} 查询板块列表: {len(df)} 展示部分:")
        print(df[:3])

        market = EX_BOARD_TYPE.HK_ALL
        rs = exClient.get_board_list(market=market)
        df = pd.DataFrame(rs)
        print(f"港股板块 {market} 查询板块列表: {len(df)} 展示部分:")
        print(df[:3])

        market = EX_BOARD_TYPE.US_ALL
        rs = exClient.get_board_list(market=market)
        df = pd.DataFrame(rs)
        print(f"美股板块 {market} 查询板块列表: {len(df)} 展示部分:")
        print(df[:3])

        print("板块测试 [client.get_board_members] 仅查询关系 ")
        board_symbol = "880761"
        rs = client.get_board_members(board_symbol=board_symbol)
        df = pd.DataFrame(rs)
        print(f"板块测试 {board_symbol} 成员数量: {len(df)} 展示部分:")
        print(df[:3])

        board_symbol = "000683"
        rs = client.get_board_members(board_symbol=board_symbol)
        df = pd.DataFrame(rs)
        print(f"重点指数 {board_symbol} 成员数量: {len(df)} 展示部分:")
        print(df[:3])

        print("***** 板块测试结束 *****")

        symbol = '000100'
        market = MARKET.SZ
        df = client.get_symbol_belong_board(symbol=symbol, market=market)
        print(f"股票 {market} {symbol} 所属板块: {len(df)} 展示部分:")
        print(df[:3])

    if test_symbol_bars:
        count = 3
        print("get_symbol_bars 测试 股票、指数、港股、美股、板块、期货, 理论上所有code均支持")

        symbol = '000100'
        market = MARKET.SZ
        fq = ADJUST.HFQ
        rs = client.get_symbol_bars(market, symbol, PERIOD.DAILY, count=count, fq=fq)
        df = pd.DataFrame(rs)
        print(f"股票 {market} {symbol} {fq} 的前{count}个交易日行情数据如下:")
        print(df)

        symbol = '880310'
        market = MARKET.SH
        fq = ADJUST.QFQ
        rs = client.get_symbol_bars(market, symbol, PERIOD.DAILY, count=count, fq=fq)
        df = pd.DataFrame(rs)
        print(f"指数 {market} {symbol} {fq} 的前{count}个交易日行情数据如下:")
        print(df)

        print("港股 美股 切换到 exClient, 出入参相同, float_shares为流通股,可以自行计算换手率")

        symbol = '00700'
        market = EX_MARKET.HK_MAIN_BOARD
        rs = exClient.get_symbol_bars(market, symbol, PERIOD.DAILY, count=count)
        df = pd.DataFrame(rs)
        print(f"港股 {market} {symbol} 的前{count}个交易日行情数据如下:")
        print(df)

        symbol = 'TSLA'
        market = EX_MARKET.US_STOCK
        rs = exClient.get_symbol_bars(market, symbol, PERIOD.WEEKLY, count=count)
        df = pd.DataFrame(rs)
        print(f"美股 {market} {symbol} 的前{count}个交易日行情数据如下:")
        print(df)

        symbol = 'HK0281'
        market = EX_MARKET.EXTENDED_SECTOR_INDEX
        rs = exClient.get_symbol_bars(market, symbol, PERIOD.WEEKLY, count=count)
        df = pd.DataFrame(rs)
        print(f"港股板块 {market} {symbol} 的前{count}个交易日行情数据如下:")
        print(df)

        symbol = 'US0218'
        market = EX_MARKET.EXTENDED_SECTOR_INDEX
        rs = exClient.get_symbol_bars(market, symbol, PERIOD.DAILY, count=count)
        df = pd.DataFrame(rs)
        print(f"美股板块 {market} {symbol} 的前10个交易日行情数据如下:")
        print(df)

    client.disconnect()
    exClient.disconnect()
