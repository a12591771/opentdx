import struct

from typing import override
from opentdx.parser.baseParser import BaseParser, register_parser
from opentdx.const import MARKET, EX_MARKET
from opentdx.utils.log import log
from opentdx.utils.bitmap import (
    FieldBit, PresetField, Fields,
    build_bitmap, get_active_fields_from_bitmap,
    FIELD_POSTPROCESS, FIELD_BITMAP_MAP,
)

@register_parser(0x122B, 1)
class SymbolQuotes(BaseParser):

    def __init__(self, code_list: list[tuple[MARKET | EX_MARKET, str]], fields: Fields = PresetField.COMMON):
        self.body = build_bitmap(fields) + struct.pack('H', len(code_list))
        for market, code in code_list:
            self.body.extend(struct.pack('<H22s', market.value, code.encode('gbk')))

    @override
    def deserialize(self, data):
        field_bitmap = data[:20]
        total, row_count = struct.unpack("<IH", data[20:26])

        active_bits = get_active_fields_from_bitmap(field_bitmap)

        # 检测服务端返回了本地未知的字段位
        known_max = max(FIELD_BITMAP_MAP.keys()) if FIELD_BITMAP_MAP else -1
        for bit_pos in active_bits:
            if bit_pos > known_max:
                log.debug(f"[DEBUG] 位图中检测到未知字段 位{bit_pos}，需要分析其含义")

        stocks = []
        quotes_field_count = len(active_bits)
        row_len = 68 + 4 * quotes_field_count
        for i in range(row_count):
            row_data = data[26 + i * row_len : 26 + (i + 1) * row_len]

            market, symbol, name = struct.unpack("<H22s44s", row_data[:68])
            try:
                market = MARKET(market) if market <= 3 else EX_MARKET(market)
            except Exception:
                log.error(f"解析市场信息出错: market={market}")
                market = EX_MARKET.TEMP_STOCK

            stock_dict = {
                "market": market,
                "code": symbol.decode("gbk", errors="ignore").replace("\x00", ""),
                "name": name.decode("gbk", errors="ignore").replace("\x00", ""),
            }

            if quotes_field_count:
                for idx, bit_pos in enumerate(active_bits):
                    value_bytes = row_data[68 + idx * 4 : 68 + (idx + 1) * 4]

                    try:
                        field_def = FieldBit(bit_pos)
                        field_name = field_def.name.lower()
                        field_format = field_def.fmt
                    except ValueError:
                        field_name = f"unknown_field_{bit_pos}"
                        field_format = '<f'
                        # 尝试用小值整型解释接近0的浮点
                        if field_format == '<f':
                            fval, = struct.unpack('<f', value_bytes)
                            if fval != 0.0 and abs(fval) < 1e-6:
                                try:
                                    value, = struct.unpack('<i', value_bytes)
                                    stock_dict[field_name] = value
                                    continue
                                except Exception:
                                    pass

                    value, = struct.unpack(field_format, value_bytes)

                    # 后处理钩子
                    if bit_pos in FIELD_POSTPROCESS:
                        value = FIELD_POSTPROCESS[bit_pos](value, stock_dict)

                    stock_dict[field_name] = value

            stocks.append(stock_dict)

        return {
            "count": row_count,
            "total": total,
            "stocks": stocks,
        }
