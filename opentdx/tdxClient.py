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
    ADJUST, BLOCK_FILE_TYPE, BOARD_TYPE, CATEGORY, EX_BOARD_TYPE, EX_MARKET,
    FILTER_TYPE, MARKET, PERIOD, SORT_ORDER, SORT_TYPE,
)
from opentdx.utils.bitmap import Fields


def _to_date_int(d: int | str | date) -> int:
    """将日期参数统一转为 YYYYMMDD 整数。

    接受:
    - int: 20230103 → 20230103
    - str: '2023-01-03' 或 '20230103' → 20230103
    - date: date(2023, 1, 3) → 20230103
    """
    if isinstance(d, int):
        return d
    if isinstance(d, date):
        return int(d.strftime('%Y%m%d'))
    s = str(d).replace('-', '').replace('/', '')
    return int(s)


class TdxClient:
    """
    通达信行情统一路由。

    内部持有两个自动连接的客户端:
    - ``quotation_client``  : MacStandardClient — A股 + MAC 协议（板块/K线/分时/成交）
    - ``ex_quotation_client`` : MacExtendedClient — 扩展市场 + MAC 协议（期货/港股/美股）
    """

    def __init__(self):
        self._quotation_client = None
        self._ex_quotation_client = None

    # ---- 上下文管理器 ----

    def __enter__(self):
        self.q_client().connect().login()
        self.eq_client().connect().login()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._quotation_client and self._quotation_client.connected:
            self._quotation_client.disconnect()
        if self._ex_quotation_client and self._ex_quotation_client.connected:
            self._ex_quotation_client.disconnect()

    # ---- 内部 ----

    def q_client(self):
        """获取 A股 客户端（首次访问时创建，断开时自动重连并登录）。"""
        if self._quotation_client is None:
            self._quotation_client = MacStandardClient(True, True)
        elif not self._quotation_client.connected:
            self._quotation_client.connect().login()
        return self._quotation_client

    def eq_client(self):
        """获取 扩展市场 客户端（首次访问时创建，断开时自动重连并登录）。"""
        if self._ex_quotation_client is None:
            self._ex_quotation_client = MacExtendedClient(True, True)
        elif not self._ex_quotation_client.connected:
            self._ex_quotation_client.connect().login()
        return self._ex_quotation_client

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
        return self.q_client().get_symbol_bars(market, code, period, times, start, count, adjust)

    def index_kline(
        self,
        market: MARKET,
        code: str,
        period: PERIOD,
        start: int = 0,
        count: int = 800,
        times: int = 1,
        adjust: ADJUST = ADJUST.NONE,
    ) -> list[dict]:
        """获取指数 K 线，保留历史涨跌家数字段（若服务器返回）。"""
        return self.q_client().get_index_kline(market, code, period, start, count, times, adjust)

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

    def stock_xdxr(self, market: MARKET, code: str) -> list[dict]:
        """获取除权除息记录。

        Returns
        -------
        list[dict]
            - ``market`` : MARKET     市场
            - ``code`` : str         股票代码
            - ``date`` : datetime    除权日期
            - ``name`` : str         事件名称（除权除息/送配股上市/…）
            - ``fenhong`` : float    每股分红
            - ``peigujia`` : float   配股价
            - ``songzhuangu`` : float 每股送转股
            - ``peigu`` : float      每股配股
        """
        return self.q_client().get_xdxr_info(market, code)

    def stock_finance(self, market: MARKET, code: str) -> dict:
        """获取财务数据（流通股本/总股本/省份/行业等）。

        Returns
        -------
        dict
            - ``liutongguben`` : float  流通股本（万股）
            - ``zongguben`` : float     总股本（万股）
            - ``province`` : int        省份代码
            - ``industry`` : int        行业代码
            - ``updated_date`` : int    更新日期
            - ``ipo_date`` : int        上市日期
            - 以及其他财务字段
        """
        return self.q_client().get_finance_info(market, code)

    def stock_company_info_category(self, market: MARKET, code: str) -> list[dict]:
        """获取公司资料目录（F10 文件列表）。

        Returns
        -------
        list[dict]
            - ``name`` : str       章节名称
            - ``filename`` : str   文件名
            - ``start`` : int      起始位置
            - ``length`` : int     数据长度
        """
        return self.q_client().get_company_info_category(market, code)

    def stock_company_info_content(self, market: MARKET, code: str, filename: str, start: int, length: int) -> dict:
        """获取公司资料内容（F10 指定章节）。

        Parameters
        ----------
        market : MARKET
        code : str
        filename : str  来自 stock_company_info_category 返回的 filename 字段
        start : int     来自 stock_company_info_category 返回的 start 字段
        length : int    来自 stock_company_info_category 返回的 length 字段

        Returns
        -------
        dict
            - ``content`` : str   章节文本
        """
        return self.q_client().get_company_info_content(market, code, filename, start, length)

    def stock_report_file(self, filename: str, filesize: int = 0, report_hook=None) -> bytearray:
        """下载 TDX 财报文件（标准协议，如 tdxfin/gpcw.txt）。

        Parameters
        ----------
        filename : str
            服务器文件名，如 ``"tdxfin/gpcw.txt"``。
        filesize : int
            文件大小（0 表示自动获取）。
        report_hook : callable, optional
            进度回调 ``(downloaded, total)``。

        Returns
        -------
        bytearray
        """
        return self.q_client().download_file(filename, filesize, report_hook)

    def stock_tdxgp_index(self) -> list[dict]:
        """下载并解析 TDXGP 股网交易事件索引文件。

        一次性获取沪深北三个市场所有可用的 tdkgp 数据文件清单，
        每个条目包含文件名、MD5 和文件大小。
        可用于按需下载特定股票的 tdkgp 数据。

        Returns
        -------
        list[dict]
            - ``filename`` : str   gpsz000001.dat
            - ``hash`` : str       MD5
            - ``filesize`` : int   字节数
        """
        return self.q_client().get_tdxgp_index()

    def stock_tdxgp_file(self, filename: str) -> bytearray:
        """下载指定的 tdkgp 单股数据文件。

        文件名可从 :meth:`stock_tdxgp_index` 中获取，或由代码拼接。

        Parameters
        ----------
        filename : str
            文件名，如 ``"gpsz000001.dat"`` 或 ``"gpsh600000.dat"`` 或 ``"gpbj430001.dat"``。

        Returns
        -------
        bytearray
            二进制内容，可直接传入 :class:`TdxgpReader` 解析。
        """
        return self.q_client().get_tdxgp_file(filename)

    def stock_block(self, block_type: BLOCK_FILE_TYPE) -> list[dict] | None:
        """获取板块文件（板块 → 成分股平铺列表）。

        Parameters
        ----------
        block_type : BLOCK_FILE_TYPE
            ``DEFAULT``（一般）/ ``ZS``（指数）/ ``FG``（风格）/ ``GN``（概念）均可从
            标准行情服务器获取。``HK``（港股）/ ``JJ``（基金）格式相同，部分服务器提供，
            服务器不支持时返回 ``None``。

        Returns
        -------
        list[dict] | None
            每条记录（一支股票在一个板块的关系）含：

            - ``blockname``  : str   板块名称
            - ``block_type`` : int   板块类型（来自文件内部分类字段）
            - ``code_index`` : int   在板块内的序号
            - ``code``       : str   股票代码

            服务器无响应时返回 ``None``。
        """
        return self.q_client().get_block_file(block_type)

    # ================================================================
    #  A股 — 板块 / 资金流向 / 主力监控
    # ================================================================

    def stock_board_list(self, market: BOARD_TYPE | EX_BOARD_TYPE = BOARD_TYPE.ALL, count: int = 10000) -> list[dict]:
        """获取板块列表。

        Parameters
        ----------
        market : BOARD_TYPE
            板块类型。 BOARD_TYPE.ALL / HY / HY2 / GN / FG / DQ / YJ_LEVEL1~3
        count : int
            获取数量，默认 10000。

        Returns
        -------
        list[dict]
            - ``board_symbol`` : str   板块代码
            - ``name`` : str          板块名称
            - ``market`` : int        市场
            - ``total`` : int         成分股数量
        """
        return self.q_client().get_board_list(market, count)

    def stock_board_members(
        self,
        board_symbol: str | CATEGORY = "881001",
        count: int = 100000,
        sort_type: SORT_TYPE = SORT_TYPE.CHANGE_PCT,
        sort_order: SORT_ORDER = SORT_ORDER.DESC,
        fields: Fields | None = None,
    ) -> list[dict]:
        """获取板块成分报价（支持自定义字段和排序）。

        Parameters
        ----------
        board_symbol : str | CATEGORY
            板块代码，如 ``"881001"`` 或 ``CATEGORY.A``。
        count : int
            获取数量。
        sort_type : SORT_TYPE
            排序字段。
        sort_order : SORT_ORDER
            排序方向。
        fields : Fields, optional
            自定义返回字段，默认使用 PresetField.COMMON。

        Returns
        -------
        list[dict]
        """
        return self.q_client().get_board_members_quotes(board_symbol, count, sort_type, sort_order, fields)

    def stock_board_top_members(self, board_symbol: str | CATEGORY = "881001", count: int = 20) -> list[dict]:
        """获取板块活跃度最高的成分股。

        Returns
        -------
        list[dict]
        """
        return self.q_client().top_board_members(board_symbol, count)

    def stock_belong_board(self, market: MARKET, code: str) -> pd.DataFrame:
        """查询个股所属板块。

        Returns
        -------
        pd.DataFrame
            包含所属板块信息的 DataFrame。
        """
        return self.q_client().get_symbol_belong_board(code, market)

    def stock_capital_flow(self, market: MARKET, code: str) -> pd.DataFrame:
        """获取个股资金流向（当日 + 5 日）。

        Returns
        -------
        pd.DataFrame
        """
        return self.q_client().get_symbol_zjlx(code, market)

    def stock_quotes_fields(
        self,
        code_list: list[tuple[MARKET, str]],
        fields: Fields | None = None,
    ) -> list[dict]:
        """获取行情报价（支持自定义字段，MAC 协议）。

        相比 :meth:`stock_quotes`，可自定义返回字段。

        Parameters
        ----------
        code_list : list[tuple[MARKET, str]]
            目标股票列表。
        fields : Fields, optional
            自定义字段组合，默认 PresetField.COMMON。

        Returns
        -------
        list[dict]
        """
        return self.q_client().get_symbol_quotes(code_list, fields)

    def stock_market_monitor(self, market: MARKET, start: int = 0, count: int = 10) -> list[dict]:
        """获取主力监控数据（MAC 协议增强版）。

        Parameters
        ----------
        market : MARKET
            市场。
        start : int
            起始位置。
        count : int
            获取数量。

        Returns
        -------
        list[dict]
        """
        return self.q_client().get_market_monitor(market, start, count)

    # ================================================================
    #  A股 — 多日分时 / K线偏移 / 个股特征 / 服务器信息
    # ================================================================

    def stock_tick_charts(
        self, market: MARKET, code: str, query_date: date = None, days: int = 5,
    ) -> dict:
        """获取多日分时图（一次获取多天）。

        Parameters
        ----------
        market : MARKET
            市场。
        code : str
            股票代码。
        query_date : date, optional
            起始日期，None 为今天。
        days : int
            获取天数，默认 5。

        Returns
        -------
        dict
            - ``market`` : MARKET      市场
            - ``code`` : str          股票代码
            - ``name`` : str          股票名称
            - ``pre_close`` : float   昨收
            - ``open`` : float        开盘价
            - ``high`` : float        最高价
            - ``low`` : float         最低价
            - ``close`` : float       现价
            - ``vol`` : int           总量
            - ``amount`` : float      成交额
            - ``charts`` : list[dict]  每日分时 ``[{date, pre_close, ticks: [{minutes, price, avg, vol}]}]``
        """
        return self.q_client().get_multi_tick_charts(market, code, query_date, days)

    def stock_kline_offset(self, offset: int = 0, count: int = 128000) -> dict:
        """查询 K 线可用记录总数。

        Returns
        -------
        dict
            - ``total`` : int    可用记录总数
            - ``returned`` : int 本次返回数
        """
        return self.q_client().get_kline_offset(offset, count)

    def stock_symbol_info(self, market: MARKET, code: str) -> dict:
        """获取个股简要特征（现价/涨跌/内外盘/换手/平均价等）。

        Returns
        -------
        dict
            - ``market`` : MARKET       市场
            - ``code`` : str           股票代码
            - ``name`` : str           股票名称
            - ``time`` : datetime       行情时间
            - ``pre_close`` : float     昨收
            - ``open`` : float          开盘价
            - ``high`` : float          最高价
            - ``low`` : float           最低价
            - ``close`` : float         现价
            - ``vol`` : int             总量
            - ``amount`` : float        成交额
            - ``inside_volume`` : int   内盘
            - ``outside_volume`` : int  外盘
            - ``turnover`` : float      换手率
            - ``avg`` : float           均价
        """
        return self.q_client().get_symbol_info(market, code)

    def server_info(self) -> dict | None:
        """获取服务器交易日时段和状态参数。

        可用于判断当前是否在交易时段、获取上一交易日等信息。

        Returns
        -------
        dict | None
            - ``today`` : str             当前日期
            - ``last_trading_day`` : str  上一交易日
            - ``sessions_1`` : list       交易时段（开闭时间）
            - ``sessions_2`` : list       交易时段 2
            - ``market_param_1`` : int    市场参数 1
            - ``market_param_2`` : int    市场参数 2
        """
        return self.q_client().get_server_info()

    def download_file(self, filename: str, filesize: int = 0, report_hook=None) -> bytearray:
        """MAC 协议下载服务器文件（如板块文件等）。

        Parameters
        ----------
        filename : str
            服务器文件名。
        filesize : int
            文件大小（0 表示自动获取）。
        report_hook : callable, optional
            进度回调 ``(downloaded, total)``。

        Returns
        -------
        bytearray
        """
        return self.q_client().download_mac_file(filename, filesize, report_hook)

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

    def goods_varieties(self, market: int, start: int = 0, count: int = 600) -> list[dict]:
        """获取扩展市场品种列表（MAC 协议，期货/期权合约品种）。

        Parameters
        ----------
        market : int
            市场代码。
        start : int
            起始位置。
        count : int
            获取数量，最大 1000。

        Returns
        -------
        list[dict]
            - ``name`` : str       品种名称
            - ``category`` : int   分类
            - ``index`` : int      索引
            - ``switch`` : int     开关
            - ``code`` : list      代码列表 ``[v1, v2, v3, c1, c2]``
        """
        return self.eq_client().get_goods_list(market, start, count)

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
        return self.eq_client().get_symbol_bars(market, code, period, times, start, count)

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

    def goods_kline_by_date(
        self,
        market: EX_MARKET,
        code: str,
        date1: int | str | date,
        date2: int | str | date,
    ) -> list[dict]:
        """获取扩展市场日期范围 K 线（期货/港股/美股）。

        Parameters
        ----------
        market : EX_MARKET
            市场。如 EX_MARKET.SH_FUTURES / EX_MARKET.HK_MAIN_BOARD / EX_MARKET.US_STOCK
        code : str
            商品代码。
        date1 : int | str | date
            起始日期。支持 ``20170613``、``'2017-06-13'``、``date(2017, 6, 13)`` 三种形式。
        date2 : int | str | date
            结束日期。同 date1。

        Returns
        -------
        list[dict]
            - ``datetime`` : str          时间字符串（YYYY-MM-DD HH:MM）
            - ``open`` : float            开盘价
            - ``high`` : float            最高价
            - ``low`` : float             最低价
            - ``close`` : float           收盘价
            - ``position`` : int          持仓量
            - ``trade`` : int             成交量
            - ``settlementprice`` : float  结算价
        """
        return self.eq_client().get_history_instrument_bars_range(
            market, code, _to_date_int(date1), _to_date_int(date2)
        )


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
        print(pd.DataFrame(client.goods_quotes_list(EX_MARKET.US_STOCK, sort_type=SORT_TYPE.TOTAL_AMOUNT)))
        print(pd.DataFrame([client.goods_quotes(EX_MARKET.US_STOCK, 'TSLA')]))
        print(pd.DataFrame(client.goods_quotes([(EX_MARKET.US_STOCK, 'TSLA'), (EX_MARKET.HK_MAIN_BOARD, '09988')])))
        print(pd.DataFrame(client.goods_kline(EX_MARKET.US_STOCK, 'TSLA', PERIOD.DAILY)))
        print(pd.DataFrame(client.goods_history_transaction(EX_MARKET.US_STOCK, 'TSLA', date(2026, 3, 3))))
        print(pd.DataFrame(client.goods_tick_chart(EX_MARKET.US_STOCK, 'TSLA')))
        print(pd.DataFrame(client.goods_tick_chart(EX_MARKET.US_STOCK, 'TSLA', date(2026, 3, 3))))
        print(pd.DataFrame(client.goods_chart_sampling(EX_MARKET.US_STOCK, 'TSLA')))
