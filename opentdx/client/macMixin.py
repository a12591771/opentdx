from __future__ import annotations

from datetime import date
import pandas as pd

from .transport import update_last_ack_time, _paginate
from opentdx.const import (
    ADJUST, BOARD_TYPE, CATEGORY, EX_BOARD_TYPE, EX_CATEGORY,
    EX_MARKET, MARKET, PERIOD, SORT_TYPE, SORT_ORDER,
)
from opentdx.parser.mac_quotation import (
    BoardList, BoardMembersQuotes, SymbolBar, SymbolBelongBoard,
    SymbolCapitalFlow, SymbolTickChart, SymbolQuotes, SymbolTransaction, Unusual,
)
from opentdx.utils.log import log
from opentdx.utils.bitmap import Fields, PresetField


class MacQuotationMixin:
    """MAC 行情方法集 — 可混入任意 BaseClient 子类"""

    @update_last_ack_time
    def get_board_count(self, market: BOARD_TYPE | EX_BOARD_TYPE):
        return self.call(BoardList(market))['total']

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
            items = part["items"]
            if len(items) > 0:
                security_list.extend(items)
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
            part = rs["stocks"]
            if len(part) > 0:
                security_list.extend(part)
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
            part = rs["stocks"]
            if len(part) > 0:
                security_list.extend(part)
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
        for start_pos in range(0, count, page_size):
            current_count = min(page_size, count - start_pos)
            parser = SymbolBar(market=market, code=code, period=period, times=times,
                               start=start_pos, count=current_count, fq=fq)
            result = self.call(parser)
            part = result.get('charts', [])
            if len(part) > 0:
                security_list.extend(part)
            if len(part) < current_count:
                log.debug(f"{msg} 数据量不足,获取结束")
                break
        return security_list

    @update_last_ack_time
    def get_symbol_tick_chart(
        self, market: MARKET | EX_MARKET, code: str, query_date: date = None,
    ):
        return self.call(SymbolTickChart(market=market, code=code, query_date=query_date))

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
            part = result.get('transactions', [])
            if len(part) > 0:
                transaction_list.extend(part)
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
