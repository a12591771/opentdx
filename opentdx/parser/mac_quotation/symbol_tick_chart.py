from datetime import date, datetime, time
import struct

from opentdx.const import EX_MARKET, MARKET
from opentdx.parser.baseParser import BaseParser, register_parser

@register_parser(0x122D, 1)
class SymbolTickChart(BaseParser):
    def __init__(self, market: MARKET | EX_MARKET, code: str, query_date: date = None):
        self.is_ex = isinstance(market, EX_MARKET)
        ymd = query_date.year * 10000 + query_date.month * 100 + query_date.day if query_date else 0
        self.body = struct.pack("<H22sI5H", market.value, code.encode("gbk"), ymd, 1, 0, 0, 0, 0)

    def deserialize(self, data):
        market, code, date_raw, u, price, count = struct.unpack("<H22sIBfH", data[:35])

        charts = []
        for i in range(count):
            minutes, price, avg, vol, momentum = struct.unpack("<HffIf", data[35 + i * 18: 35 + (i + 1) * 18])
            charts.append({
                'time': time(minutes // 60 % 24, minutes % 60),
                "price": price,
                "avg": avg,
                "vol": vol,
                "momentum": momentum
            })

        name, decimal, category, vol_unit, date_raw, time_raw, pre_close, open, high, low, close, momentum, vol, amount, turnover, avg, industry = struct.unpack_from("<44sBHf5x2I5ffIf12x2fI", data, 35 + count * 18)

        return {
            "market": MARKET(market) if not self.is_ex else EX_MARKET(market),
            "code": code.decode("gbk").replace('\x00', ''),
            "name": name.decode("gbk").replace('\x00', ''),
            "decimal": decimal,
            "category": category,
            "vol_unit": vol_unit,
            "time": datetime(date_raw//10000, (date_raw%10000)//100, date_raw%100, time_raw//10000, (time_raw%10000)//100, time_raw%100),
            "pre_close": pre_close,
            "open": open,
            "high": high,
            "low": low,
            "close": close,
            "momentum": momentum,
            "vol": vol,
            "amount": amount,
            "turnover": turnover,
            "avg": avg,
            "industry": industry,
            "charts": charts
        }
