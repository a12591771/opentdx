from __future__ import annotations

from datetime import date
import pandas as pd

from .transport import update_last_ack_time, _paginate
from opentdx.const import (
    ADJUST, BOARD_TYPE, CATEGORY, EX_BOARD_TYPE, EX_CATEGORY,
    EX_MARKET, MARKET, PERIOD, SORT_TYPE, SORT_ORDER,
)
import math

from opentdx.parser.mac_quotation import (
    Auction, BoardList, BoardMembersQuotes, FileDownload, FileList,
    GoodsList, KlineOffset, ServerInfo, SymbolBar, SymbolBelongBoard,
    SymbolCapitalFlow, SymbolInfo, SymbolQuotes, SymbolTickChart,
    SymbolTransaction, TickCharts, Unusual,
)
from opentdx.utils.log import log
from opentdx.utils.bitmap import Fields, PresetField


class MacQuotationMixin:
    """MAC 行情方法集 — 可混入任意 BaseClient 子类"""

    @update_last_ack_time
    def get_board_count(self, market: BOARD_TYPE | EX_BOARD_TYPE):
        result = self.call(BoardList(market))
        return result['total'] if result else 0

    @update_last_ack_time
    def get_board_list(self, market: BOARD_TYPE | EX_BOARD_TYPE, count=10000):
        MAX_LIST_COUNT = 150
        security_list = []
        page_size = min(count, MAX_LIST_COUNT)
        msg = f"TDX 板块列表：{market} 查询总量{count}"
        log.debug(msg)
        for start in range(0, count, page_size):
            current_count = min(page_size, count - start)
            part = self.call(BoardList(board_type=market, start=start, page_size=current_count))
            if not part:
                break
            items = part["items"]
            if len(items) > 0:
                security_list[0:0] = items
            if len(items) < current_count:
                log.debug(f"{msg} 数据量不足，获取结束")
                break
        return security_list

    @update_last_ack_time
    def get_board_members_quotes(
        self, board_symbol: str | CATEGORY | EX_CATEGORY = "881001", count=100000,
        sort_type: SORT_TYPE = SORT_TYPE.CHANGE_PCT,
        sort_order=SORT_ORDER.DESC,
        fields: Fields | None = None,
    ):
        MAX_LIST_COUNT = 80
        security_list = []
        msg = f"TDX 板块成分报价：{board_symbol} 查询总量{count}"
        log.debug(msg)
        for start in range(0, count, MAX_LIST_COUNT):
            current_count = min(MAX_LIST_COUNT, count - start)
            rs = self.call(BoardMembersQuotes(
                board_symbol=board_symbol, start=start, page_size=current_count,
                sort_type=sort_type, sort_order=sort_order,
                fields=fields if fields else PresetField.COMMON,
            ))
            if not rs:
                break
            part = rs["stocks"]
            if len(part) > 0:
                security_list[0:0] = part
            if len(part) < current_count:
                log.debug(f"{msg} 数据量不足，获取结束")
                break
        return security_list

    @update_last_ack_time
    def top_board_members(self, board_symbol: str | CATEGORY | EX_CATEGORY = "881001", count=20):
        return self.get_board_members_quotes(
            board_symbol=board_symbol,
            count=count,
            sort_type=SORT_TYPE.ACTIVITY,
            sort_order=SORT_ORDER.DESC,
            fields=PresetField.ENHANCED,
        )

    @update_last_ack_time
    def get_board_members(self, board_symbol: str | CATEGORY | EX_CATEGORY = "881001",
                          count=100000, sort_type: SORT_TYPE = SORT_TYPE.CODE,
                          sort_order=SORT_ORDER.NONE):
        MAX_LIST_COUNT = 80
        security_list = []
        msg = f"TDX 板块成员：{board_symbol} 查询总量{count}"
        log.debug(msg)
        for start in range(0, count, MAX_LIST_COUNT):
            current_count = min(MAX_LIST_COUNT, count - start)
            rs = self.call(BoardMembersQuotes(
                board_symbol=board_symbol, start=start, page_size=current_count,
                sort_type=sort_type, sort_order=sort_order,
            ))
            if not rs:
                break
            part = rs["stocks"]
            if len(part) > 0:
                security_list[0:0] = part
            if len(part) < current_count:
                log.debug(f"{msg} 数据量不足，获取结束")
                break
        return security_list

    @update_last_ack_time
    def count_board_members(self, board_symbol: str | CATEGORY | EX_CATEGORY = "881001",
                            count=1, sort_type: SORT_TYPE = SORT_TYPE.CODE,
                            sort_order=SORT_ORDER.NONE):
        return self.call(BoardMembersQuotes(
            board_symbol=board_symbol, start=0, page_size=count,
            sort_type=sort_type, sort_order=sort_order,
        ))

    @update_last_ack_time
    def get_symbol_belong_board(self, symbol: str, market: MARKET) -> pd.DataFrame:
        return self.call(SymbolBelongBoard(symbol=symbol, market=market))

    @update_last_ack_time
    def get_symbol_zjlx(self, symbol: str, market: MARKET) -> pd.DataFrame:
        if not isinstance(market, MARKET):
            raise TypeError(f"market 参数必须为 MARKET 类型，当前类型: {type(market).__name__}")
        return self.call(SymbolCapitalFlow(symbol=symbol, market=market))

    @update_last_ack_time
    def get_symbol_bars(
        self, market: MARKET | EX_MARKET, code: str, period: PERIOD,
        times: int = 1, start: int = 0, count: int = 800, fq: ADJUST = ADJUST.NONE,
    ):
        MAX_LIST_COUNT = 700
        page_size = min(count, MAX_LIST_COUNT)
        security_list = []
        msg = f"TDX bar :{market} {code} {period} 查询总量{count} {start}  "
        log.debug(msg)
        for start_pos in range(start, start + count, page_size):
            current_count = min(page_size, start + count - start_pos)
            parser = SymbolBar(market=market, code=code, period=period, times=times,
                               start=start_pos, count=current_count, fq=fq)
            result = self.call(parser)
            if not result:
                break
            part = result.get('charts', [])
            for bar in part:
                fs = (bar.get('float_shares') or 0) * 10000  # 万股→股
                bar['float_shares'] = fs
                bar['turnover'] = round(bar['vol'] / fs * 100, 2) if fs and bar.get('vol') else 0
            if len(part) > 0:
                security_list[0:0] = part
            if len(part) < current_count:
                log.debug(f"{msg} 数据量不足,获取结束")
                break
        return security_list

    @update_last_ack_time
    def get_symbol_tick_chart(
        self, market: MARKET | EX_MARKET, code: str, query_date: date = None,
    ):
        result = self.call(SymbolTickChart(market=market, code=code, query_date=query_date))
        if result:
            result['turnover'] = result['turnover'] / 10000  # 原始值→%
        return result

    @update_last_ack_time
    def get_symbol_quotes(
        self,
        code_list: list[tuple[MARKET | EX_MARKET, str]],
        fields: Fields | None = None,
    ):
        return self.call(SymbolQuotes(
            code_list=code_list,
            fields=fields if fields else PresetField.COMMON,
        ))

    @update_last_ack_time
    def get_symbol_transactions(
        self, market: MARKET | EX_MARKET, code: str, count: int = 100000,
        start: int = 0, query_date: date = None,
    ) -> list:
        MAX_TRANSACTION_COUNT = 1000
        transaction_list = []
        msg = f"TDX 逐笔成交：{market.name}.{code} 查询总量{count}"
        log.debug(msg)
        for current_start in range(start, start + count, MAX_TRANSACTION_COUNT):
            current_count = min(MAX_TRANSACTION_COUNT, start + count - current_start)
            parser = SymbolTransaction(
                market=market, code=code, count=current_count,
                start=current_start, query_date=query_date,
            )
            result = self.call(parser)
            if not result:
                break
            part = result.get('transactions', [])
            if len(part) > 0:
                transaction_list[0:0] = part
            if len(part) < current_count:
                log.debug(f"{msg} 数据量不足，获取结束")
                break
        return transaction_list

    @update_last_ack_time
    def get_market_monitor(self, market: MARKET, start: int = 0, count: int = 10) -> list[dict]:
        return _paginate(
            lambda s, c: self.call(Unusual(market, s, c)),
            600, count, start,
        )

    @update_last_ack_time
    def get_auction(self, market: MARKET, code: str, start: int = 0, count: int = 500) -> dict:
        """MAC竞价数据 — 比旧版竞价协议字段更完整"""
        return self.call(Auction(market, code, start, count))

    @update_last_ack_time
    def get_multi_tick_charts(
        self, market: MARKET, code: str, query_date: date = None, days: int = 5,
    ) -> dict:
        """多日分时图 — 一次获取多天的分时数据"""
        return self.call(TickCharts(market, code, query_date, days))

    @update_last_ack_time
    def get_symbol_info(self, market: MARKET, code: str) -> dict:
        """获取个股简要特征（现价/涨跌/内外盘/换手等）"""
        return self.call(SymbolInfo(market, code))

    @update_last_ack_time
    def get_kline_offset(self, offset: int = 0, count: int = 128000) -> dict:
        """查询K线可用记录总数"""
        return self.call(KlineOffset(offset, count))

    @update_last_ack_time
    def get_server_info(self) -> dict | None:
        """获取服务器交易日时段、状态参数"""
        return self.call(ServerInfo())

    @update_last_ack_time
    def get_goods_list(
        self, market: int, start: int = 0, count: int = 600,
    ) -> list[dict]:
        """MAC扩展市场品种列表（期货/期权等合约信息）"""
        return self.call(GoodsList(market, start, count))

    def download_mac_file(self, filename: str, filesize: int = 0, report_hook=None) -> bytearray:
        """MAC协议文件下载"""
        meta = self.call(FileList(filename))
        if not meta:
            return bytearray()

        size = filesize or meta['size']
        file_content = bytearray()
        one_chunk = 30000

        for seg in range(math.ceil(size / one_chunk)):
            start = seg * one_chunk
            piece = self.call(FileDownload(filename, seg + 1, start, one_chunk))
            if not piece:
                break
            raw = piece['content']
            file_content.extend(raw.encode('gbk', errors='replace') if isinstance(raw, str) else raw)
            if report_hook:
                report_hook(len(file_content), size)

        return file_content
