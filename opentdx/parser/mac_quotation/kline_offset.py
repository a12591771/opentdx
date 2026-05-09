import struct
from opentdx.parser.baseParser import BaseParser, register_parser


@register_parser(0x124A, 1)
class KlineOffset(BaseParser):
    """MAC协议K线偏移查询（0x124A）
    
    请求: struct.pack('<II5x', offset, count) — offset必须为0
    响应: 8字节 — uint32_BE(total) + uint32_LE(returned)
    
    注意: 该协议仅返回可用记录总数(大端序)，不返回K线数据。
    响应的total字段为请求count的大端序回显，returned为0。
    """
    def __init__(self, offset: int = 0, count: int = 128000):
        self.body = struct.pack('<II5x', offset, count)

    def deserialize(self, data):
        print(f"[DEBUG] KlineOffset响应原始数据: {data.hex()}")
        if len(data) < 8:
            return {'total': 0, 'returned': 0}

        total = struct.unpack('>I', data[:4])[0]
        returned = struct.unpack('<I', data[4:8])[0]
        return {
            'total': total,
            'returned': returned,
        }
