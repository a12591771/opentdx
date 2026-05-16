import struct

from opentdx.parser.baseParser import register_parser
from opentdx.parser.mac_quotation.symbol_quotes import SymbolQuotes
from opentdx.utils.help import exchange_board_code
from opentdx.const import CATEGORY, EX_CATEGORY, SORT_TYPE, SORT_ORDER, FILTER_TYPE
from opentdx.utils.bitmap import (
    PresetField, Fields, build_bitmap_new,
    CTRL_EXTENDED,
)


@register_parser(0x122C, 1)
class BoardMembersQuotes(SymbolQuotes):
    """板块成分报价 — 请求20字节bitmap = 16字节字段位图 + 4字节控制区

    控制区(后4字节)字节映射:
        byte 0(位128-135): 占位
        byte 1(位136-143): 排除位,  来自 exclude_flags
        byte 2(位144-151): 占位
        byte 3(位152-159): 控制字节, 默认 CTRL_EXTENDED(扩展模式)
    """

    def __init__(self, board_symbol: str | CATEGORY | EX_CATEGORY = "881001",
                 sort_type: SORT_TYPE = SORT_TYPE.CHANGE_PCT, start: int = 0,
                 page_size: int = 80, sort_order: SORT_ORDER = SORT_ORDER.NONE,
                 fields: Fields = PresetField.NONE,
                 exclude_flags: list[FILTER_TYPE] | None = None):
        """
        exclude_flags: 排除条件列表, 如 [FILTER_TYPE.KC, FILTER_TYPE.CY]
        """
        board_code = exchange_board_code(board_symbol) if isinstance(board_symbol, str) else board_symbol.code
        self.body = struct.pack("<I9xHIHBB", board_code, sort_type.value, start, page_size, sort_order.value, 0)

        # ── 20字节 bitmap ──
        # 前16字节: 字段位图(位0-127)
        self.body += build_bitmap_new(fields)

        # 后4字节: 控制区(位128-159), BBBB = byte0盘口 + byte1排除 + byte2日内 + byte3控制
        b0 = 0  # 
        b2 = 0  # 

        # byte1排除位: FILTER_TYPE 值直接对应 byte1 位
        b1 = sum(f.value for f in (exclude_flags or []))

        self.body += struct.pack("<BBBB", b0, b1, b2, CTRL_EXTENDED)