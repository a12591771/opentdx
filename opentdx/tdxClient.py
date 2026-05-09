"""
TdxClient — 通达信行情统一入口。

内置 MacStandardClient (A股 + MAC协议) 和 MacExtendedClient (扩展市场 + MAC协议)，
一个实例覆盖所有行情接口，自动管理连接/登录/断开。

用法::

    # 上下文管理器（推荐）
    with TdxClient() as client:
        kline = client.stock_kline(MARKET.SZ, '000001', PERIOD.DAILY, count=10)
        print(pd.DataFrame(kline))

    # 手动管理
    client = TdxClient()
    client.quotation_client.connect().login()
    data = client.stock_count(MARKET.SZ)
    client.quotation_client.disconnect()

单位约定
--------
价格      — 元 (float)，如 11.36 表示 11.36 元/股
成交量    — 股 (int)，如 121638752 表示约 1.22 亿股
成交额    — 元 (float)，如 1380730880 表示约 13.8 亿元
换手率    — % (float)，如 5.23 表示 5.23%
涨跌幅    — % (float)，如 2.15 表示上涨 2.15%
时间      — datetime / time 对象（非字符串）
"""

from __future__ import annotations

from datetime import date

from opentdx.client.macStandardClient import MacStandardClient
from opentdx.client.macExtendedClient import MacExtendedClient
from opentdx.const import (
    ADJUST, BLOCK_FILE_TYPE, CATEGORY, EX_MARKET,
    FILTER_TYPE, MARKET, PERIOD, SORT_TYPE,
)


class TdxClient:
    """
    通达信行情统一路由。

    内部持有两个自动连接的客户端:
    - ``quotation_client``  : MacStandardClient — A股 + MAC 协议（板块/K线/分时/成交）
    - ``ex_quotation_client`` : MacExtendedClient — 扩展市场 + MAC 协议（期货/港股/美股）
    """

    def __init__(self):
        self.quotation_client = MacStandardClient(True, True)
        self.ex_quotation_client = MacExtendedClient(True, True)

    # ---- 上下文管理器 ----

    def __enter__(self):
        self.quotation_client.connect().login()
        self.ex_quotation_client.connect().login()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.quotation_client.connected:
            self.quotation_client.disconnect()
        if self.ex_quotation_client.connected:
            self.ex_quotation_client.disconnect()

    # ---- 内部 ----

    def q_client(self):
        """获取 A股 客户端（断开时自动重连并登录）。"""
        if not self.quotation_client.connected:
            self.quotation_client.connect().login()
        return self.quotation_client

    def eq_client(self):
        """获取 扩展市场 客户端（断开时自动重连并登录）。"""
        if not self.ex_quotation_client.connected:
            self.ex_quotation_client.connect().login()
        return self.ex_quotation_client

    # ================================================================
    #  A股 — 市场概况
    # ================================================================

    def stock_count(self, market: MARKET) -> int:
        """获取市场股票总数。

        Parameters
        ----------
        market : MARKET
            市场。 MARKET.SZ / MARKET.SH / MARKET.BJ

        Returns
        -------
        int
            当前在市的股票数量。
        """
        return self.q_client().get_count(market)

    def stock_list(self, market: MARKET, start: int = 0, count: int = 0) -> list[dict]:
        """获取股票列表。

        Parameters
        ----------
        market : MARKET
            市场。
        start : int
            起始位置，默认 0。
        count : int
            获取数量，0 表示全部。

        Returns
        -------
        list[dict]
            - ``code`` : str      股票代码
            - ``name`` : str      股票名称
            - ``vol`` : int       成交量
            - ``pre_close`` : int 昨收（需 /100 得元）
            - ``decimal_point`` : int  小数位数
        """
        return self.q_client().get_list(market, start, count)

    def stock_top_board(self, category: CATEGORY = CATEGORY.A) -> dict:
        """获取排行榜。

        Parameters
        ----------
        category : CATEGORY
            市场分类，默认 CATEGORY.A。

        Returns
        -------
        dict
            九个榜单，每个榜单为 ``[{market, code, price, value}]`` 列表:

            - ``increase``           涨幅榜
            - ``decrease``           跌幅榜
            - ``amplitude``          振幅榜
            - ``rise_speed``         涨速榜
            - ``fall_speed``         跌速榜
            - ``vol_ratio``          量比榜
            - ``pos_commission_ratio`` 委比正序
            - ``neg_commission_ratio`` 委比倒序
            - ``turnover``           换手率榜
        """
        return self.q_client().get_stock_top_board(category)

    # ================================================================
    #  A股 — 行情报价
    # ================================================================

    def stock_quotes(self, code_list: MARKET | list[tuple[MARKET, str]], code: str = None) -> list[dict]:
        """获取简略报价（1 档盘口）。

        三种调用形式::

            client.stock_quotes(MARKET.SZ, '000001')
            client.stock_quotes((MARKET.SZ, '000001'))
            client.stock_quotes([(MARKET.SZ, '000001'), (MARKET.SH, '600000')])

        Parameters
        ----------
        code_list : MARKET | tuple | list[tuple]
            目标股票，支持三种传入形式。
        code : str, optional
            当 ``code_list`` 为 MARKET 时，传递股票代码。

        Returns
        -------
        list[dict]
            - ``market`` : MARKET        市场
            - ``code`` : str            股票代码
            - ``open`` : float          开盘价
            - ``high`` : float          最高价
            - ``low`` : float           最低价
            - ``close`` : float         现价
            - ``pre_close`` : float     昨收
            - ``vol`` : int             总量
            - ``cur_vol`` : int         现量
            - ``amount`` : float        总成交额
            - ``in_vol`` : int          内盘（主动买）
            - ``out_vol`` : int         外盘（主动卖）
            - ``rise_speed`` : str      涨速
            - ``short_turnover`` : str  短换手
            - ``active`` : int          活跃度
            - ``handicap`` : dict       1 档盘口 ``{bid: [{price, vol}], ask: [{price, vol}]}``
        """
        return self.q_client().get_quotes(code_list, code)

    def stock_quotes_detail(self, code_list: MARKET | list[tuple[MARKET, str]], code: str = None) -> list[dict]:
        """获取详细报价（5 档盘口）。

        Parameters
        ----------
        code_list : MARKET | tuple | list[tuple]
            目标股票，支持三种传入形式（同 :meth:`stock_quotes`）。
        code : str, optional
            当 ``code_list`` 为 MARKET 时，传递股票代码。

        Returns
        -------
        list[dict]
            ``market`` : MARKET        市场
            ``code`` : str            股票代码
            ``open`` : float          开盘价
            ``high`` : float          最高价
            ``low`` : float           最低价
            ``close`` : float         现价
            ``pre_close`` : float     昨收
            ``vol`` : int             总量
            ``cur_vol`` : int         现量
            ``amount`` : float        总成交额
            ``in_vol`` : int          内盘（主动买）
            ``out_vol`` : int         外盘（主动卖）
            ``s_amount`` : float      卖盘总额
            ``open_amount`` : float   开盘金额
            ``rise_speed`` : float    涨速
            ``active`` : int          活跃度
            ``handicap`` : dict       5 档盘口 ``{bid: [{price, vol}*5], ask: [{price, vol}*5]}``
        """
        return self.q_client().get_stock_quotes_details(code_list, code)

    def stock_quotes_list(
        self,
        category: CATEGORY,
        start: int = 0,
        count: int = 80,
        sort_type: SORT_TYPE = SORT_TYPE.CODE,
        reverse: bool = False,
        filter: list[FILTER_TYPE] | None = None,
    ) -> list[dict]:
        """获取行情列表（支持排序和过滤）。

        Parameters
        ----------
        category : CATEGORY
            市场分类。 CATEGORY.A / CYB / KCB / BJ / SZ / SH
        start : int
            起始位置，默认 0。
        count : int
            获取数量，默认 80。
        sort_type : SORT_TYPE
            排序字段。常用: CODE / PRICE / VOLUME / AMOUNT / CHANGE_PCT / TURNOVER_RATE / ACTIVITY
        reverse : bool
            True 为升序，默认 False（降序）。
        filter : list[FILTER_TYPE], optional
            排除项。如 ``[FILTER_TYPE.ST, FILTER_TYPE.BJ]`` 排除 ST 股和北证。

        Returns
        -------
        list[dict]
            - ``market`` : MARKET        市场
            - ``code`` : str            股票代码
            - ``open`` : float          开盘价
            - ``high`` : float          最高价
            - ``low`` : float           最低价
            - ``close`` : float         现价
            - ``pre_close`` : float     昨收
            - ``vol`` : int             总量
            - ``cur_vol`` : int         现量
            - ``amount`` : float        总成交额
            - ``in_vol`` : int          内盘（主动买）
            - ``out_vol`` : int         外盘（主动卖）
            - ``rise_speed`` : str      涨速
            - ``short_turnover`` : str  短换手
            - ``active`` : int          活跃度
            - ``handicap`` : dict       1 档盘口 ``{bid: [{price, vol}], ask: [{price, vol}]}``
        """
        return self.q_client().get_stock_quotes_list(category, start, count, sort_type, reverse, filter)

    # ================================================================
    #  A股 — K 线
    # ================================================================

    def stock_kline(
        self,
        market: MARKET,
        code: str,
        period: PERIOD,
        start: int = 0,
        count: int = 800,
        times: int = 1,
        adjust: ADJUST = ADJUST.NONE,
    ) -> list[dict]:
        """获取 A 股 K 线。

        用法::

            # 日线
            client.stock_kline(MARKET.SZ, '000001', PERIOD.DAILY, count=10)
            # 10 分钟线
            client.stock_kline(MARKET.SH, '999999', PERIOD.MINS, times=10, count=20)
            # 前复权周线
            client.stock_kline(MARKET.SZ, '000001', PERIOD.WEEKLY, adjust=ADJUST.QFQ)

        Parameters
        ----------
        market : MARKET
            市场。
        code : str
            股票代码。
        period : PERIOD
            周期。

            ============  ================
            PERIOD.DAILY        日线
            PERIOD.WEEKLY       周线
            PERIOD.MONTHLY      月线
            PERIOD.QUARTERLY    季线
            PERIOD.YEARLY       年线
            PERIOD.MIN_1        1 分钟
            PERIOD.MIN_5        5 分钟
            PERIOD.MIN_15       15 分钟
            PERIOD.MIN_30       30 分钟
            PERIOD.MIN_60       60 分钟
            PERIOD.MINS         多分钟（配合 ``times``）
            PERIOD.DAYS         多日（配合 ``times``）
            PERIOD.SECONDS      多秒（配合 ``times``）
            ============  ================

        start : int
            起始偏移，默认 0（最新）。
        count : int
            获取根数，默认 800。
        times : int
            多周期倍数。仅 ``MINS`` / ``DAYS`` / ``SECONDS`` 时生效。
            如 ``period=PERIOD.MINS, times=10`` 表示 10 分钟 K 线。
        adjust : ADJUST
            复权类型。 NONE（默认）/ QFQ（前复权）/ HFQ（后复权）。

        Returns
        -------
        list[dict]
            - ``datetime`` : datetime    时间（按日期倒序，最新在前）
            - ``open`` : float          开盘价（元）
            - ``high`` : float          最高价（元）
            - ``low`` : float           最低价（元）
            - ``close`` : float         收盘价（元）
            - ``vol`` : int             成交量（股）
            - ``amount`` : float        成交额（元）
            - ``float_shares`` : float  流通股本（股），仅个股有效
            - ``turnover`` : float      换手率（%），仅个股有效
        """
        bars = self.q_client().get_symbol_bars(market, code, period, times, start, count, adjust)
        for bar in bars:
            bar['turnover'] = (
                round(bar['vol'] / bar['float_shares'] * 100, 2)
                if bar.get('float_shares') and bar.get('vol') else 0
            )
        return bars

    # ================================================================
    #  A股 — 分时 / 成交 / 竞价
    # ================================================================

    def stock_tick_chart(self, market: MARKET, code: str, date: date = None, start: int = 0, count: int = 0xBA00) -> list[dict]:
        """获取分时图。

        Parameters
        ----------
        market : MARKET
            市场。
        code : str
            股票代码。
        date : date, optional
            历史日期，None 为实时。
        start : int
            采样偏移。
        count : int
            采样点数，默认 0xBA00（47616）。

        Returns
        -------
        list[dict]
            - ``time`` : time           时间
            - ``price`` : float         成交价（元）
            - ``avg`` : float           均价（元）
            - ``vol`` : int             累计成交量
            - ``momentum`` : float      动量
        """
        result = self.q_client().get_symbol_tick_chart(market, code, date)
        return result['charts'] if result else []

    def stock_chart_sampling(self, market: MARKET, code: str) -> list[float]:
        """获取分时缩略数据（240 个采样点）。

        Returns
        -------
        list[float]
            各采样点价格（元）。
        """
        return self.q_client().get_chart_sampling(market, code)

    def stock_transaction(self, market: MARKET, code: str, date: date = None) -> list[dict]:
        """获取逐笔成交。

        Parameters
        ----------
        market : MARKET
            市场。
        code : str
            股票代码。
        date : date, optional
            None 为实时，传入日期查询历史成交。

        Returns
        -------
        list[dict]
            - ``time`` : time          成交时间
            - ``price`` : float        成交价（元）
            - ``vol`` : int            成交量（股）
            - ``trade_count`` : int    成交笔数
            - ``bs_flag`` : int        方向: 0=买入 / 1=卖出 / 2=中性盘 / 5=盘后
        """
        return self.q_client().get_symbol_transactions(market, code, count=2000 if date else 1800, query_date=date)

    def stock_auction(self, market: MARKET, code: str) -> list[dict]:
        """获取集合竞价数据（9:15–9:25）。

        Returns
        -------
        list[dict]
            - ``time`` : time         时间
            - ``price`` : float       撮合价（元）
            - ``matched`` : int       匹配量
            - ``unmatched`` : int     未匹配量
        """
        return self.q_client().get_auction(market, code)

    def stock_history_orders(self, market: MARKET, code: str, date: date) -> list[dict]:
        """获取历史委托分布（各价位挂单量）。

        Returns
        -------
        list[dict]
            - ``price`` : float   价位（元）
            - ``vol`` : int       该价位的成交量（股）
        """
        return self.q_client().get_history_orders(market, code, date)

    # ================================================================
    #  A股 — 指数
    # ================================================================

    def index_info(self, code_list: MARKET | list[tuple[MARKET, str]], code: str = None) -> list[dict]:
        """获取指数概况。

        三种调用::

            client.index_info(MARKET.SH, '999999')
            client.index_info((MARKET.SZ, '399001'))
            client.index_info([(MARKET.SH, '999999'), (MARKET.SZ, '399001')])

        Parameters
        ----------
        code_list : MARKET | tuple | list[tuple]
            目标指数，支持三种传入形式。
        code : str, optional
            当 ``code_list`` 为 MARKET 时，传递指数代码。

        Returns
        -------
        list[dict]
            - ``market`` : MARKET        市场
            - ``code`` : str            指数代码
            - ``open`` : float          开盘（元）
            - ``high`` : float          最高（元）
            - ``low`` : float           最低（元）
            - ``close`` : float         现价（元）
            - ``pre_close`` : float     昨收（元）
            - ``diff`` : float          涨跌（元）
            - ``vol`` : int             成交量
            - ``amount`` : float        成交额（元）
            - ``up_count`` : int        上涨家数
            - ``down_count`` : int      下跌家数
            - ``active`` : int          活跃度
        """
        return self.q_client().get_index_info(code_list, code)

    def index_momentum(self, market: MARKET, code: str) -> list[int]:
        """获取指数动量（各分钟动量值）。

        Returns
        -------
        list[int]
        """
        return self.q_client().get_index_momentum(market, code)

    # ================================================================
    #  A股 — 其他
    # ================================================================

    def stock_vol_profile(self, market: MARKET, code: str) -> list[dict]:
        """获取成交分布（各价位的买卖档位）。

        Returns
        -------
        list[dict]
            - ``market`` : MARKET        市场
            - ``code`` : str            股票代码
            - ``close`` : float         现价
            - ``pre_close`` : float     昨收
            - ``vol`` : int             总量
            - ``handicap`` : dict       3 档盘口 ``{bid, ask}``
            - ``vol_profile`` : list    各价位分布 ``[{price, vol, buy, sell}]``
        """
        return self.q_client().get_vol_profile(market, code)

    def stock_unusual(self, market: MARKET, start: int = 0, count: int = 0) -> list[dict]:
        """获取异动数据（主力监控精灵）。

        Parameters
        ----------
        market : MARKET
            市场。 MARKET.SZ / MARKET.SH / MARKET.BJ
        start : int
            起始位置。
        count : int
            获取数量，0 为全部。

        Returns
        -------
        list[dict]
            - ``index`` : int          序号
            - ``market`` : MARKET      市场
            - ``code`` : str          股票代码
            - ``name`` : str          股票名称
            - ``time`` : time          触发时间
            - ``desc`` : str          异动描述（涨停板/大幅下跌/拉升/封单…）
            - ``value`` : str          异动值
            - ``unusual_type`` : int   异动类型代码
        """
        return self.q_client().get_unusual(market, start, count)

    def stock_f10(self, market: MARKET, code: str) -> list[dict]:
        """获取 F10 公司资料。

        Returns
        -------
        list[dict]
            - ``name`` : str           资料名称（'公司概况'/'财务指标'/'股本结构'/'除权分红'/'财报' 等）
            - ``content`` : str|dict   具体内容
        """
        return self.q_client().get_company_info(market, code)

    def stock_block(self, block_type: BLOCK_FILE_TYPE) -> list[dict]:
        """获取板块文件（板块 → 成分股对照表）。

        Parameters
        ----------
        block_type : BLOCK_FILE_TYPE
            DEFAULT（一般）/ ZS（指数）/ FG（风格）/ GN（概念）

        Returns
        -------
        list[dict]
            - ``block_name`` : str     板块名称
            - ``stocks`` : list[str]   成分股代码列表
        """
        return self.q_client().get_block_file(block_type)

    # ================================================================
    #  扩展市场 — 概况
    # ================================================================

    def goods_count(self) -> int:
        """获取扩展市场商品总数。"""
        return self.eq_client().get_count()

    def goods_category_list(self) -> list[dict]:
        """获取商品分类列表。

        Returns
        -------
        list[dict]
            - ``goods_type`` : int      商品类型
            - ``name`` : str           分类名称
            - ``code`` : str           分类代码
            - ``abbr`` : str           缩写
        """
        return self.eq_client().get_category_list()

    def goods_list(self, start: int = 0, count: int = 2000) -> list[dict]:
        """获取商品列表。

        Returns
        -------
        list[dict]
            - ``market`` : int          市场号
            - ``category`` : int        分类
            - ``code`` : str           商品代码
            - ``desc`` : str           描述
            - ``name`` : str           商品名称
        """
        return self.eq_client().get_list(start, count)

    # ================================================================
    #  扩展市场 — 行情
    # ================================================================

    def goods_quotes(self, code_list: EX_MARKET | list[tuple[EX_MARKET, str]], code: str = None) -> list[dict]:
        """获取商品报价（期货 / 港股 / 美股）。

        三种调用::

            client.goods_quotes(EX_MARKET.US_STOCK, 'TSLA')
            client.goods_quotes([(EX_MARKET.US_STOCK, 'TSLA'), (EX_MARKET.HK_MAIN_BOARD, '00700')])

        Parameters
        ----------
        code_list : EX_MARKET | tuple | list[tuple]
            目标商品，支持三种传入形式。
        code : str, optional
            当 ``code_list`` 为 EX_MARKET 时，传递商品代码。

        Returns
        -------
        list[dict]
            - ``market`` : EX_MARKET      市场
            - ``code`` : str             商品代码
            - ``open`` : float           开盘价
            - ``high`` : float           最高价
            - ``low`` : float            最低价
            - ``close`` : float          现价
            - ``pre_close`` : float      昨收
            - ``vol`` : int              总量
            - ``curr_vol`` : int         现量
            - ``amount`` : float         总成交额
            - ``in_vol`` : int           内盘
            - ``out_vol`` : int          外盘
            - ``open_position`` : int    持仓量（开仓）
            - ``hold_position`` : int    持仓量
            - ``settlement`` : float     结算价
            - ``avg`` : float            均价
            - ``handicap`` : dict        5 档盘口
        """
        return self.eq_client().get_quotes(code_list, code)

    def goods_quotes_list(self, market: EX_MARKET, start: int = 0, count: int = 100, sortType: SORT_TYPE = SORT_TYPE.CODE, reverse: bool = False) -> list[dict]:
        """获取商品行情列表（支持排序）。

        Parameters
        ----------
        market : EX_MARKET
            市场。如 EX_MARKET.US_STOCK / EX_MARKET.HK_MAIN_BOARD / EX_MARKET.SH_FUTURES
        count : int
            获取数量。
        sortType : SORT_TYPE
            排序字段，默认按代码。
        reverse : bool
            True 为升序。

        Returns
        -------
        list[dict]
            - ``market`` : EX_MARKET      市场
            - ``code`` : str             商品代码
            - ``open`` : float           开盘价
            - ``high`` : float           最高价
            - ``low`` : float            最低价
            - ``close`` : float          现价
            - ``pre_close`` : float      昨收
            - ``vol`` : int              总量
            - ``curr_vol`` : int         现量
            - ``amount`` : float         总成交额
            - ``in_vol`` : int           内盘
            - ``out_vol`` : int          外盘
            - ``open_position`` : int    持仓量（开仓）
            - ``hold_position`` : int    持仓量
            - ``settlement`` : float     结算价
            - ``avg`` : float            均价
            - ``handicap`` : dict        5 档盘口
        """
        return self.eq_client().get_quotes_list(market, start, count, sortType, reverse)

    # ================================================================
    #  扩展市场 — K线 / 分时 / 成交
    # ================================================================

    def goods_kline(self, market: EX_MARKET, code: str, period: PERIOD, start: int = 0, count: int = 800, times: int = 1) -> list[dict]:
        """获取商品 K 线（期货 / 港股 / 美股）。

        Parameters
        ----------
        market : EX_MARKET
            市场。如 EX_MARKET.US_STOCK / EX_MARKET.HK_MAIN_BOARD
        code : str
            商品代码。
        period : PERIOD
            周期，参见 :meth:`stock_kline`。
        count : int
            获取根数。

        Returns
        -------
        list[dict]
            - ``datetime`` : datetime    时间
            - ``open`` : float          开盘价
            - ``high`` : float          最高价
            - ``low`` : float           最低价
            - ``close`` : float         收盘价
            - ``vol`` : int             成交量
            - ``amount`` : float        成交额
            - ``float_shares`` : float  流通股本（仅个股有效）
            - ``turnover`` : float      换手率（%），仅个股有效
        """
        bars = self.eq_client().get_symbol_bars(market, code, period, times, start, count)
        for bar in bars:
            bar['turnover'] = (
                round(bar['vol'] / bar['float_shares'] * 100, 2)
                if bar.get('float_shares') and bar.get('vol') else 0
            )
        return bars

    def goods_tick_chart(self, market: EX_MARKET, code: str, date: date = None) -> list[dict]:
        """获取商品分时图。

        Returns
        -------
        list[dict]
            - ``time`` : time        时间
            - ``price`` : float      成交价
            - ``avg`` : float        均价
            - ``vol`` : int          累计成交量
        """
        result = self.eq_client().get_symbol_tick_chart(market, code, date)
        return result['charts'] if result else []

    def goods_chart_sampling(self, market: EX_MARKET, code: str) -> list[float]:
        """获取商品分时缩略。

        Returns
        -------
        list[float]
            各采样点价格。
        """
        return self.eq_client().get_chart_sampling(market, code)

    def goods_history_transaction(self, market: EX_MARKET, code: str, date: date) -> list[dict]:
        """获取商品历史成交。

        Returns
        -------
        list[dict]
            - ``time`` : time        时间
            - ``price`` : float      成交价
            - ``vol`` : int          成交量
            - ``trade_count`` : int  成交笔数
            - ``bs_flag`` : int      方向: 0=买入 / 1=卖出 / 2=中性盘 / 5=盘后
        """
        return self.eq_client().get_symbol_transactions(market, code, count=2000, query_date=date)


if __name__ == '__main__':
    import pandas as pd

    with TdxClient() as client:
        print(client.stock_count(MARKET.SZ))
        print(pd.DataFrame(client.stock_list(MARKET.SZ)))
        print(pd.DataFrame(client.index_momentum(MARKET.SZ, '399001')))
        print(pd.DataFrame(client.index_momentum(MARKET.SH, '999999')))
        print(pd.DataFrame(client.index_info([(MARKET.SZ, '399001'), (MARKET.SH, '999999')])))
        print(pd.DataFrame(client.stock_kline(MARKET.SH, '999999', PERIOD.DAILY)))
        print(pd.DataFrame(client.stock_kline(MARKET.SH, '999999', PERIOD.MINS, times=10)))
        print(pd.DataFrame(client.stock_tick_chart(MARKET.SH, '999999')))
        print(pd.DataFrame(client.stock_tick_chart(MARKET.SZ, '000001')))
        print(pd.DataFrame(client.stock_tick_chart(MARKET.SZ, '000001', date(2026, 3, 16))))
        print(pd.DataFrame(client.stock_quotes_detail(MARKET.SZ, '000001')))
        print(pd.DataFrame(client.stock_top_board()))
        print(pd.DataFrame(client.stock_quotes_list(CATEGORY.A, count=0, sort_type=SORT_TYPE.TOTAL_AMOUNT)))
        print(pd.DataFrame(client.stock_quotes(MARKET.SZ, '000001')))
        print(pd.DataFrame(client.stock_unusual(MARKET.SZ)))
        print(pd.DataFrame(client.stock_auction(MARKET.SZ, '300308')))
        print(pd.DataFrame(client.stock_history_orders(MARKET.SZ, '000001', date(2026, 1, 7))))
        print(pd.DataFrame(client.stock_transaction(MARKET.SZ, '000001')))
        print(pd.DataFrame(client.stock_transaction(MARKET.SZ, '000001', date(2026, 3, 3))))
        print(pd.DataFrame(client.stock_chart_sampling(MARKET.SZ, '000001')))
        print(pd.DataFrame(client.stock_f10(MARKET.SZ, '000001')))

        print(client.goods_count())
        print(pd.DataFrame(client.goods_category_list()))
        print(pd.DataFrame(client.goods_list()))
        print(pd.DataFrame(client.goods_quotes_list(EX_MARKET.US_STOCK, sortType=SORT_TYPE.TOTAL_AMOUNT)))
        print(pd.DataFrame([client.goods_quotes(EX_MARKET.US_STOCK, 'TSLA')]))
        print(pd.DataFrame(client.goods_quotes([(EX_MARKET.US_STOCK, 'TSLA'), (EX_MARKET.HK_MAIN_BOARD, '09988')])))
        print(pd.DataFrame(client.goods_kline(EX_MARKET.US_STOCK, 'TSLA', PERIOD.DAILY)))
        print(pd.DataFrame(client.goods_history_transaction(EX_MARKET.US_STOCK, 'TSLA', date(2026, 3, 3))))
        print(pd.DataFrame(client.goods_tick_chart(EX_MARKET.US_STOCK, 'TSLA')))
        print(pd.DataFrame(client.goods_tick_chart(EX_MARKET.US_STOCK, 'TSLA', date(2026, 3, 3))))
        print(pd.DataFrame(client.goods_chart_sampling(EX_MARKET.US_STOCK, 'TSLA')))
