import struct

from opentdx.parser.baseParser import register_parser
from opentdx.parser.mac_quotation.symbol_quotes import SymbolQuotes
from opentdx.utils.help import exchange_board_code
from opentdx.const import CATEGORY, EX_CATEGORY, SORT_TYPE, SORT_ORDER
from opentdx.utils.bitmap import PresetField, Fields, build_bitmap

@register_parser(0x122C, 1)
class BoardMembersQuotes(SymbolQuotes):
    def __init__(self, board_symbol: str | CATEGORY | EX_CATEGORY = "881001", sort_type: SORT_TYPE = 0xe, start: int = 0, page_size: int = 80, sort_order: SORT_ORDER = SORT_ORDER.NONE, fields: Fields = PresetField.NONE):
        board_code = exchange_board_code(board_symbol) if isinstance(board_symbol, str) else board_symbol.code
        self.body = struct.pack("<I9xHIBBBB", board_code, sort_type.value, start, page_size, 0, sort_order.value, 0)
        self.body = self.body + build_bitmap(fields)