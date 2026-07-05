# coding=utf-8

from datetime import date, datetime, timedelta
import struct

from opentdx.const import EX_MARKET, MARKET
from opentdx.enums import IndustryCode
from opentdx.utils.log import log

def combine_to_datetime(ymd, date_num, format_tdx_time=False):
    """将 TDX 日期数字和时间偏移合并为 datetime；ymd=0 时返回 None。"""
    if ymd is None or ymd == 0:
        return None
    date_str = str(ymd)
    year, month, day = int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8])
    hours = date_num // 3600
    minutes = (date_num % 3600) // 60
    if year == 0:
        return None
    dt = datetime(year, month, day, hours, minutes)
    if format_tdx_time and 0 <= dt.hour <= 5:
        dt += timedelta(days=1)
    return dt

def query_market(code) -> MARKET | None:
    """
    0 - 深圳， 1 - 上海
    """
    if code.startswith(("50", "51", "60", "68", "90", "110", "113", "132", "204")):
        return MARKET.SH
    elif code.startswith(("00", "12", "13", "15", "16", "18", "20", "30", "39", "115", "1318")):
        return MARKET.SZ
    elif code.startswith(("5", "6", "7", "9")):
        return MARKET.SH
    elif code.startswith(("4", "8")):
        return MARKET.BJ
    log.error("unknown market code: %s", code)
    return None


# 根据可视化的板块id获取到系统需要的真实板块code
def exchange_board_code(board_symbol):
    if board_symbol.startswith("US"):
        # US0401 => 30401
        board_code = 30000 + int(board_symbol.replace("US", ""))
    elif board_symbol.startswith("HK"):
        # HK0283 => 20283
        board_code = 20000 + int(board_symbol.replace("HK", ""))
    elif board_symbol.startswith("000"):
        # 000686 => 31686
        board_code = 31000 + int(board_symbol)
    elif board_symbol.startswith("399") and len(board_symbol) == 6:
        # 399372 => 30399
        board_code = int(board_symbol) - 399000 + 30000
    elif board_symbol.startswith("899") and len(board_symbol) == 6:
        # 899050 => 32050
        board_code = int(board_symbol) - 899000 + 32000
    elif board_symbol.startswith("88") and len(board_symbol) == 6:
        # 880686 => 20686
        board_code = int(board_symbol) - 880000 + 20000
    else:
        # 由于数字过大,可能查询到其他的板块
        board_code = int(board_symbol)

    return board_code

def industry_to_board_symbol(industry_value) -> str:
    """将 industry 原始值转换为板块代码，兼容已转换的板块代码直接透传"""
    industry_str = str(industry_value).strip()
    if not industry_str:
        return ""

    # 已经是板块代码（88xxxx），直接返回
    if industry_str.startswith("88") and len(industry_str) == 6:
        return industry_str

    # 从原始值（如 83005）提取后4位，拼接为 X3005 查找
    suffix = industry_str[-4:]
    key = f"X{suffix}"
    try:
        return str(IndustryCode[key].value)
    except KeyError:
        return ""
    
def ah_code_to_symbol(ah_code:str, market:str) -> str:
    """
        将ah_code转换为symbol, 补齐0
                        
        Example:
            >>> rs = client.get_board_members_quotes(board_symbol="881394",count=100, fields=PresetField.AH_CODE)
                df = pd.DataFrame(rs)
                df['ah_symbol'] = df.apply(lambda row: ah_code_to_symbol(row['ah_code'], row['market']), axis=1)
    """
    
    if ah_code == 0:
        return ""
    
    if market in [MARKET.SZ, MARKET.SH, MARKET.BJ]:
        # 国内市场（A股）：ah_code 对应的是港股，需要格式化为5位，不足前面补0
        ah_symbol = str(ah_code).zfill(5)
    else:
        # 港股市场：ah_code 对应的是A股，需要格式化为6位，不足前面补0
        ah_symbol = str(ah_code).zfill(6)
    
    return ah_symbol
    
def lot_size_to_symbol(lotsize:str) -> str:
    """
        将lotsize转换为symbol, 补齐前缀
                        
    """
    if lotsize == 0:
        return ""
    
    dq_symbol = 880200 + int(lotsize)
    
    return str(dq_symbol)

#### XXX: 分析了一下，貌似是类似utf-8的编码方式保存有符号数字
def get_price(data, pos):
    pos_byte = 6
    bdata = data[pos]
    int_data = bdata & 0x3f
    if bdata & 0x40:
        sign = True
    else:
        sign = False

    if bdata & 0x80:
        max_iter = 8
        while max_iter > 0:
            pos += 1
            bdata = data[pos]
            int_data += (bdata & 0x7f) << pos_byte
            pos_byte += 7
            max_iter -= 1

            if bdata & 0x80:
                pass
            else:
                break

    pos += 1

    if sign:
        int_data = -int_data

    return int_data, pos

def seconds_to_time_str(secs: int) -> str:
    """将从0点开始的秒数转换为 HH:MM:SS"""
    h = secs // 3600
    m = (secs % 3600) // 60
    s = secs % 60
    return f"{h:02d}:{m:02d}:{s:02d}"

def to_datetime(num, with_time=False) -> datetime:
    year = 0
    month = 0
    day = 0
    hour = 15
    minute = 0
    if with_time:
        zip_data = num & 0xFFFF
        year = (zip_data >> 11) + 2004
        month = int((zip_data & 0x7FF) / 100)
        day = (zip_data & 0x7FF) % 100

        minutes = num >> 16
        hour = int(minutes / 60)
        minute = minutes % 60
    else:
        year = num // 10000
        month = num % 10000 // 100
        day = num % 100
    if year > datetime.now().year:
        raise ValueError("year is too large")

    return datetime(year, month, day, hour, minute)

_TDX_EPOCH = datetime(2004, 1, 1)

def to_datetime_seconds(seconds: int) -> datetime:
    """解析秒级K线时间戳 (seconds from 2004-01-01 00:00:00)"""
    return _TDX_EPOCH + timedelta(seconds=seconds)

def format_time(time_stamp):
    if time_stamp == 0 or time_stamp == 100:
        return '00:00:00.000'

    time_stamp = str(time_stamp)
    if len(time_stamp) < 7:
        return '00:00:00.000'

    time_str = time_stamp[:-6] + ':'
    if int(time_stamp[-6:-4]) < 60:
        time_str += '%s:' % time_stamp[-6:-4]
        time_str += '%06.3f' % (
            int(time_stamp[-4:]) * 60 / 10000.0
        )
    else:
        time_str += '%02d:' % (
            int(time_stamp[-6:]) * 60 / 1000000
        )
        time_str += '%06.3f' % (
            (int(time_stamp[-6:]) * 60 % 1000000) * 60 / 1000000.0
        )
    return time_str

def unpack_futures(data, code_len: int = 23):
    if len(data) < 291 + code_len:
        raise Exception(f"futures data too short: {len(data)} < {291 + code_len}")
    
    market, code = struct.unpack(f'<B{code_len}s', data[:1 + code_len])
    active, pre_close, open, high, low, close, open_position, add_position, vol, curr_vol, amount, in_vol, out_vol, u14, hold_position = struct.unpack(f'<I5f4If4I', data[1 + code_len: 61 + code_len])
    handicap_list = struct.unpack('<5f5I5f5I', data[61 + code_len: 141 + code_len])
    handicap = {
        'bid': [{'price': handicap_list[i], 'vol': handicap_list[i + 5]} for i in range(5)],
        'ask': [{'price': handicap_list[i], 'vol': handicap_list[i + 5]} for i in range(10, 15)]
    }
    u1, settlement, u2, avg, pre_settlement, u3, u4, u5, u6, pre_close  = struct.unpack('<HfIffIIIIf', data[141 + code_len: 179 + code_len])
    s1, pre_vol, u7, s2, u8, day3_raise, s3, settlement2, date_raw, u9, raise_speed, u10, s4, u11, u12 = struct.unpack('<12sff12sff25sfIIff24sHB', data[179 + code_len: 291 + code_len])

    # 当没有 date_raw 数据时,会报错
    # goods.Futures_QuotesList(ExtMarketCategory.港股.value, 1895, 2)  02632没有date_raw数据
    if date_raw // 10000 == 0:
        date_obj = date(1900, 1, 1)
    else:
        date_obj = date(date_raw // 10000, date_raw % 10000 // 100, date_raw % 100)

    return {
            'market': EX_MARKET(market), 
            'code': code.decode('gbk').replace('\x00', ''), 
            'active': active, 
            'pre_close': pre_close, 
            'open': open, 
            'high': high, 
            'low': low, 
            'close': close, 
            'open_position': open_position, 
            'add_position': add_position, 
            'vol': vol, 
            'cur_vol': curr_vol, 
            'amount': amount, 
            'in_vol': in_vol, 
            'out_vol': out_vol, 
            'u14': u14, 
            'hold_position': hold_position,
            'handicap': handicap,
            'settlement': settlement,
            'avg': avg,
            'pre_settlement': pre_settlement,
            'pre_close': pre_close,
            'pre_vol': pre_vol,
            'day3_raise': day3_raise,
            'settlement2': settlement2,
            'date': date_obj,
            'rise_speed': raise_speed,
            'u1': u1,
            'u2': u2,
            'u3': [u3, u4, u5, u6],
        }

def unpack_by_type(unusual_type: int, data: bytearray) -> tuple[str, str, int, float, float, float]:
    v1, v2, v3, v4 = struct.unpack('<B3f', data)
    desc = ""
    val = ""
    if unusual_type == 0x03:
        desc = f"主力{'买入' if v1 == 0x00 else '卖出'}"
        val = f"{v2:.2f}/{v3:.2f}"
    elif unusual_type == 0x04:
        desc = "加速拉升"
        val = f"{v2*100:.2f}%"
    elif unusual_type == 0x05:
        desc = "加速下跌"
    elif unusual_type == 0x06:
        desc = "低位反弹"
        val = f"{v2*100:.2f}%"
    elif unusual_type == 0x07:
        desc = "高位回落"
        val = f"{v2*100:.2f}%"
    elif unusual_type == 0x08:
        desc = "撑杆跳高"
        val = f"{v2*100:.2f}%"
    elif unusual_type == 0x09:
        desc = "平台跳水"
        val = f"{v2*100:.2f}%"
    elif unusual_type == 0x0a:
        desc = f"单笔冲{'跌' if v2 < 0 else '涨'}"
        val = f"{v2*100:.2f}%"
    elif unusual_type == 0x0b:
        desc = f"区间放量{'平' if v3 == 0 else '跌' if v3 < 0 else '涨'}"
        val = f"{v2:.1f}倍{'' if v3 == 0 else f'{v3*100:.2f}%'}"
    elif unusual_type == 0x0c:
        desc = "区间缩量"
    elif unusual_type == 0x10:
        desc = "大单托盘"
        val = f"{v4:.2f}/{v3:.2f}"
    elif unusual_type == 0x11:
        desc = "大单压盘"
        val = f"{v2:.2f}/{v3:.2f}"
    elif unusual_type == 0x12:
        desc = "大单锁盘"
    elif unusual_type == 0x13:
        desc = "竞价试买"
        val = f"{v2:.2f}/{v3:.2f}"
    elif unusual_type == 0x14:
        sub_type, v2, v3 = struct.unpack('<Bff', data[1:10])
        direction = "涨" if v1 == 0x00 else "跌"
        if sub_type == 0x01:
            desc = f"逼近{direction}停"
        elif sub_type == 0x02:
            desc = f"封{direction}停板"
        elif sub_type == 0x04:
            desc = f"封{direction}大减"
        elif sub_type == 0x05:
            desc = f"打开{direction}停"
        val = f"{v2:.2f}/{v3:.2f}"
    elif unusual_type == 0x15:
        if v1 == 0x00:
            desc = "尾盘??"
        elif v1 == 0x01:
            desc = "尾盘对倒"
        elif v1 == 0x02:
            desc = "尾盘拉升"
        else:
            desc = "尾盘打压"
        val = f"{v2*100:.2f}%/{v3:.2f}"
    elif unusual_type == 0x16:
        desc = f"盘中{'弱' if v2 < 0x00 else '强'}势"
        val = f"{v2*100:.2f}%"
    elif unusual_type == 0x1d:
        desc = "急速拉升"
        val = f"{v2*100:.2f}%"
    elif unusual_type == 0x1e:
        desc = "急速下跌"
        val = f"{v2*100:.2f}%"
    return desc, val, v1, v2, v3, v4


STOCK_TAG_FLAGS_LABELS: dict[int, str] = {
    1 << 0:  '沪深港通大盘',
    1 << 1:  '融资融券',
    1 << 2:  '沪港通',
    1 << 3:  '深港通',
    1 << 14: '含GDR',
    1 << 15: '沪深港通小盘',
    1 << 17: '沪深港通中盘',
    1 << 20: 'ST/*ST',
}


def decode_stock_tag_flags(flags: int) -> list[str]:
    """将 STOCK_TAG_FLAGS 位图解码为可读标签列表"""
    return [label for bit, label in STOCK_TAG_FLAGS_LABELS.items() if flags & bit]



