import struct
from datetime import datetime

from opentdx.parser.baseParser import BaseParser, register_parser


@register_parser(0x120F, 1)
class ServerInfo(BaseParser):
    """MAC协议服务端初始化（0x120F），返回交易日时段和服务器状态"""
    def __init__(self):
        header = bytes.fromhex('04002d31')
        self.body = header + b'\x00' * 8 + b'\x00\x27\x06\x0e' + b'\x00' * 52

    def deserialize(self, data):
        if len(data) < 87:
            return None

        pos = 0
        count, = struct.unpack_from('<H', data, pos); pos += 2
        # 8 bytes flags
        flags = data[pos:pos + 8]; pos += 8
        # 3 bytes tag ("-1")
        tag = data[pos:pos + 3].decode('ascii', errors='replace').rstrip('\x00'); pos += 3
        # 9 bytes reserved
        pos += 9

        def _parse_session(p):
            """解析8个uint16的交易时段（4组开闭时间）"""
            vals = struct.unpack_from('<8H', data, p)
            p += 16
            sessions = []
            for i in range(0, 8, 2):
                sessions.append({
                    'open': f'{vals[i] // 60}:{vals[i] % 60:02d}',
                    'close': f'{vals[i+1] // 60}:{vals[i+1] % 60:02d}',
                })
            return sessions, p

        def _parse_date(p):
            """解析日期(uint32 YYYYMMDD)"""
            d = struct.unpack_from('<I', data, p)[0]
            p += 4
            return f'{d // 10000}-{d % 10000 // 100:02d}-{d % 100:02d}', p

        # 日期1（当天）
        date1, pos = _parse_date(pos)
        ts1, = struct.unpack_from('<I', data, pos); pos += 4

        # 交易时段 × 2（可能对应A股和期货）
        sessions1, pos = _parse_session(pos)
        sessions2, pos = _parse_session(pos)

        # flag
        flag = data[pos]; pos += 1

        # 日期2-3（上一交易日）
        date2, pos = _parse_date(pos)
        ts2, = struct.unpack_from('<I', data, pos); pos += 4
        date3, pos = _parse_date(pos)
        ts3, = struct.unpack_from('<I', data, pos); pos += 4

        # 市场参数
        val1, = struct.unpack_from('<I', data, pos); pos += 4
        val2, = struct.unpack_from('<I', data, pos); pos += 4

        return {
            'count': count,
            'flags': flags.hex(),
            'tag': tag,
            'today': date1,
            'ts1': ts1,
            'sessions_1': sessions1,
            'sessions_2': sessions2,
            'flag': flag,
            'last_trading_day': date2,
            'ts2': ts2,
            'last_trading_day_2': date3,
            'ts3': ts3,
            'market_param_1': val1,
            'market_param_2': val2,
        }
