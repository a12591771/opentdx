from datetime import time
import struct
from typing import override

from opentdx.const import MARKET
from opentdx.parser.baseParser import BaseParser, register_parser
from opentdx.utils.help import unpack_by_type

@register_parser(0x1237)
class Unusual(BaseParser): # 主力监控，不需要Login()
    def __init__(self, market: MARKET, start: int, count: int = 600):
        self.body = struct.pack('<H H 2x H 2x H 5H', market.value, start, count, 1, 200, 30, 40, 50, 200)

    @override
    def deserialize(self, data):
        count, = struct.unpack('<H', data[:2])
        results = []
        for i in range(count):
            market, code, _, unusual_type, _, index, z = struct.unpack('<H6sBBBHH', data[32 * i + 2: 32 * i + 17])
            #TODO 临时补充 v1~v4 字段, 现在二次unpack了.
            v1, v2, v3, v4 = struct.unpack('<B3f', data[32 * i + 17: 32 * i + 30])
            desc, value = unpack_by_type(unusual_type, data[32 * i + 17: 32 * i + 30])
            hour, minute_sec = struct.unpack('<BH', data[32 * i + 31: 32 * i + 34])
            
            results.append({
                'index': index,
                'market': MARKET(market),
                'code': code.decode('gbk').replace('\x00', ''),
                'time': time(hour, minute_sec // 100, minute_sec % 100),
                'desc': desc,
                'value': value,
                'unusual_type': unusual_type,
                'v1': v1,
                'v2': v2,
                'v3': v3,
                'v4': v4,
            })

        binary_length = 2 + count * 32
        text_bytes = data[binary_length:]
        text_list = text_bytes.decode('gbk', errors='ignore').strip(',').split(',')

        for i in range(len(results)):
            if i < len(text_list):
                results[i]['name'] = text_list[i]
        
        return results
