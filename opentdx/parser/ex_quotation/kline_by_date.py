import struct
from typing import override

from opentdx.const import EX_MARKET
from opentdx.parser.baseParser import BaseParser, register_parser


@register_parser(0x240d, 1)
class KLineByDate(BaseParser):
    def __init__(self, market: EX_MARKET, code: str, date1: int, date2: int):
        """
        Parameters
        ----------
        market : EX_MARKET
        code : str
        date1 : int  YYYYMMDD 起始日期
        date2 : int  YYYYMMDD 结束日期
        """
        self.body = struct.pack('<B9sHII', market.value, code.encode('gbk'), 0x0007, date1, date2)

    @override
    def deserialize(self, data):
        (count,) = struct.unpack('<H', data[12:14])
        results = []
        for i in range(count):
            pos = 14 + i * 32
            d1, d2, open_, high, low, close, position, trade, settlement = struct.unpack(
                '<HHffffIIf', data[pos:pos + 32]
            )
            year = d1 // 2048 + 2004
            month = (d1 % 2048) // 100
            day = (d1 % 2048) % 100
            hour = d2 // 60
            minute = d2 % 60
            results.append({
                'datetime': '%d-%02d-%02d %02d:%02d' % (year, month, day, hour, minute),
                'open': open_,
                'high': high,
                'low': low,
                'close': close,
                'position': position,
                'trade': trade,
                'settlementprice': settlement,
            })
        return results
