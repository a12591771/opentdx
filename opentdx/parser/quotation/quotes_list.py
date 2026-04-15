import struct
from typing import override

from opentdx.const import CATEGORY, FILTER_TYPE, MARKET, SORT_TYPE
from opentdx.parser.baseParser import BaseParser, register_parser
from opentdx.utils.help import format_time, get_price

@register_parser(0x54b)
class QuotesList(BaseParser):
    def __init__(self, category: CATEGORY, start: int = 0, count: int = 0x50, sort_type: SORT_TYPE = SORT_TYPE.CODE, reverse: bool = False, filter: list[FILTER_TYPE] | None = None):
        sort_reverse = 0 if sort_type == SORT_TYPE.CODE else 2 if reverse else 1

        filter_raw = 0
        if filter_types is None:
            filter_types = []
        for filter_type in filter_types:
            filter_raw |= filter_type.value

        self.body = struct.pack('<9H', category.value, sort_type.value, start, count,  sort_reverse, 5, filter_raw, 1, 0)
    @override
    def deserialize(self, data):
        block, count = struct.unpack('<HH', data[:4])
        pos = 4

        stocks = []
        for _ in range(count):
            market, code, active1 = struct.unpack('<B6sH', data[pos: pos + 9])
            pos += 9
            price, pos = get_price(data, pos)
            pre_close, pos = get_price(data, pos)
            open, pos = get_price(data, pos)
            high, pos = get_price(data, pos)
            low, pos = get_price(data, pos)
            server_time, pos = get_price(data, pos)
            neg_price, pos = get_price(data, pos)
            vol, pos = get_price(data, pos)
            cur_vol, pos = get_price(data, pos)

            amount, = struct.unpack('<f', data[pos: pos + 4])
            pos += 4

            in_vol, pos = get_price(data, pos)
            out_vol, pos = get_price(data, pos)
            s_amount, pos = get_price(data, pos)
            open_amount, pos = get_price(data, pos)

            bids = []
            asks = []
            for _ in range(1):
                bid, pos = get_price(data, pos)
                ask, pos = get_price(data, pos)
                bid_vol, pos = get_price(data, pos)
                ask_vol, pos = get_price(data, pos)

                bid += price
                ask += price

                bids.append({
                    'price': bid,
                    'vol': bid_vol,
                })
                asks.append({
                    'price': ask,
                    'vol': ask_vol,
                })

            unknown, rise_speed, short_turnover, min2_amount, opening_rush, extra_pair, vol_rise_speed, depth, extra_meta, active2 = struct.unpack('<Hhhfh10sff24sH', data[pos: pos + 56])
            pos += 56
            # extra_pair(10s): 前2字节为 active_flag + decimal，后8字节为附加数据
            active_flag, decimal = struct.unpack('<BB', extra_pair[:2])

            stocks.append({
                'market': MARKET(market),
                'code': code.decode('gbk'),
                'close': price,
                'open': open + price,
                'high': high + price,
                'low': low + price,
                'pre_close': pre_close + price,
                'server_time': format_time(server_time),
                'neg_price': neg_price,
                'vol': vol,
                'cur_vol': cur_vol,
                'amount': amount,
                'in_vol': in_vol,
                'out_vol': out_vol,
                's_amount': s_amount,
                'open_amount': open_amount,
                'handicap': {
                    'bid': bids,
                    'ask': asks,
                },
                'unknown': format(unknown, '016b'),
                'rise_speed': rise_speed,
                'short_turnover': short_turnover,
                'min2_amount': min2_amount,
                'opening_rush': opening_rush,
                'active_flag': active_flag,
                'decimal': decimal,
                'extra_meta': extra_meta.hex(),
                'vol_rise_speed': vol_rise_speed,
                'depth': depth,
                'active': active1,
            })
        return stocks
