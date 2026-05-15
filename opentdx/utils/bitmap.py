# coding=utf-8
from __future__ import annotations
from enum import Enum, IntEnum
from typing import Iterable, TypeAlias
from opentdx.utils.log import log

# 统一的字段选择类型
Fields: TypeAlias = 'FieldBit | PresetField | FieldSelection | Iterable[FieldBit]'


class FieldBit(IntEnum):
    """字段位定义，自带格式和描述，单一数据源"""

    def __new__(cls, value, fmt='<f', desc=''):
        if isinstance(value, tuple):
            value, fmt, desc = value
        obj = int.__new__(cls, value)
        obj._value_ = value
        obj.fmt = fmt
        obj.desc = desc
        return obj

    @property
    def field_name(self):
        """返回英文字段名，用于 DataFrame 列名等"""
        return self.name.lower()

    # ── 基础字段 (0x00-0x05) ──
    PRE_CLOSE              = 0x00, '<f', '昨收'
    OPEN                   = 0x01, '<f', '开盘价'
    HIGH                   = 0x02, '<f', '最高价'
    LOW                    = 0x03, '<f', '最低价'
    CLOSE                  = 0x04, '<f', '收盘价'
    VOL                    = 0x05, '<I', '成交量'
    VOL_RATIO              = 0x06, '<f', '量比'
    AMOUNT                 = 0x07, '<f', '总金额(元)'  # CSV显示为万元，需÷10000

    # ── 扩展字段 (0x08-0x0F) ──
    INSIDE_VOLUME          = 0x08, '<I', '内盘'
    OUTSIDE_VOLUME         = 0x09, '<I', '外盘'
    TOTAL_SHARES           = 0x0A, '<f', '总股数(单位万)'
    FLOAT_SHARES           = 0x0B, '<f', '流通股(单位万)'  # 港股为H股数
    EPS                    = 0x0C, '<f', '每股收益'
    NET_ASSETS             = 0x0D, '<f', '净资产'
    UNKNOWN_ACTION_PRICE   = 0x0E, '<f', '未知价'  # 国内通常为3/9/12, 美股港股与close相等
    TOTAL_MARKET_CAP_AB    = 0x0F, '<f', 'AB股总市值'  # 港股代表H市值

    # ── 0x10-0x1F ──
    PE_DYNAMIC             = 0x10, '<f', '市盈率(动)'
    BID_PRICE              = 0x11, '<f', '买一价'
    ASK_PRICE              = 0x12, '<f', '卖一价'
    SERVER_UPDATE_DATE     = 0x13, '<I', '服务器更新日期 YYYYMMDD'
    SERVER_UPDATE_TIME     = 0x14, '<I', '服务器更新时间 HHMMSS'
    LOT_SIZE_INFO          = 0x15, '<I', '未确定'  # 港股:240000500 美股:550000001
    BOARD_STRENGTH         = 0x16, '<f', '板块强度(涨跌家数差)'
    DIVIDEND_YIELD         = 0x17, '<f', '每股股息(元)'
    BID_VOLUME             = 0x18, '<I', '买量'
    ASK_VOLUME             = 0x19, '<I', '卖量'
    LAST_VOLUME            = 0x1A, '<I', '现量'
    TURNOVER               = 0x1B, '<f', '换手'
    INDUSTRY               = 0x1C, '<I', '行业分类代码'
    INDUSTRY_CHANGE_UP     = 0x1D, '<f', '行业涨跌幅'
    SOME_BITMAP            = 0x1E, '<I', '位图'
    DECIMAL_POINT          = 0x1F, '<I', '数据精度'

    # ── 0x20-0x2F ──
    BUY_PRICE_LIMIT        = 0x20, '<f', '涨停价'
    SELL_PRICE_LIMIT       = 0x21, '<f', '跌停价'
    UNKNOWN_34             = 0x22, '<I', '（港股通常为15）'
    LOT_SIZE               = 0x23, '<I', '所属地区板块(A股)/每手股数(港股)'
    PRE_IPOV               = 0x24, '<f', '昨IPOV'
    SPEED_PCT              = 0x25, '<f', '涨速'
    AVG_PRICE              = 0x26, '<f', '均价'
    IPOV                   = 0x27, '<f', 'IPOV'
    PE_TTM_VOL_RELATED     = 0x28, '<f', '市盈率TTM（与vol相关）'
    EX_PRICE_PLACEHOLDER   = 0x29, '<f', '收盘价占位（与amount相关）'
    OPERATING_REVENUE      = 0x2A, '<f', '营业收入(万)'
    FLAG_KCB               = 0x2B, '<I', '科创板标志'  # 688开头→30101 300开头→50101
    FLAG_BJ                = 0x2C, '<I', '北交所标志'
    CIRCULATING_CAPITAL_Z  = 0x2D, '<f', '流通股本Z（单位：万股）'
    # 0x2E-0x2F 保留

    # ── 0x30-0x3F ──
    PE_TTM                 = 0x30, '<f', '市盈率TTM'
    PE_STATIC              = 0x31, '<f', '市盈率静'
    # 0x32-0x37 保留
    MAIN_NET_AMOUNT        = 0x38, '<f', '今日主力净流入'
    BID_ASK_RATIO          = 0x39, '<f', '委比'  # (买量-卖量)/(买量+卖量)*100%
    # 0x3A 保留
    CHANGE_20D_PCT         = 0x3B, '<f', '20日涨幅%'
    YTD_PCT                = 0x3C, '<f', '年初至今%'
    # 0x3D-0x3F 保留

    # ── 0x40-0x4F ──
    MTD_PCT                = 0x40, '<f', '月初至今%'
    CHANGE_1Y_PCT          = 0x41, '<f', '一年涨幅%'
    PREV_CHANGE_PCT        = 0x42, '<f', '昨涨幅%'
    CHANGE_3D_PCT          = 0x43, '<f', '3日涨幅%'
    CHANGE_60D_PCT         = 0x44, '<f', '60日涨幅%'
    CHANGE_5D_PCT          = 0x45, '<f', '5日涨幅%'
    CHANGE_10D_PCT         = 0x46, '<f', '10日涨幅%'
    PREV2_CHANGE_PCT       = 0x47, '<f', '前日涨幅%'
    BID2_PRICE             = 0x48, '<f', '买二价'
    ASK2_PRICE             = 0x49, '<f', '卖二价'
    AH_CODE                = 0x4A, '<I', '对应A/H股code,不足位数前面补0'
    UNKNOWN_CODE           = 0x4B, '<I', '少部分有数据,6位数字'

    # ── 0x50-0x6F ──
    OPEN_AMOUNT            = 0x57, '<f', '开盘金额(元)'  # CSV显示为万元，需÷10000
    ANNUAL_LIMIT_UP_DAYS   = 0x58, '<i', '年涨停天数'
    ACTIVITY               = 0x59, '<I', '活跃度'
    # 0x5A 保留
    DIVIDEND_YIELD_RATE    = 0x5B, '<f', '股息率%'
    CONSECUTIVE_UP_DAYS    = 0x5C, '<i', '连涨天'  # 正数连涨，负数连跌
    LIMIT_UP_COUNT         = 0x5D, '<I', '涨停数(板块) / 买二量(个股)'
    BID2_VOLUME            = 0x5D, '<I', '买二量(个股)'  # LIMIT_UP_COUNT 别名
    LIMIT_DOWN_COUNT       = 0x5E, '<I', '跌停数(板块) / 卖二量(个股)'
    ASK2_VOLUME            = 0x5E, '<I', '卖二量(个股)'  # LIMIT_DOWN_COUNT 别名
    INDUSTRY_SUB           = 0x5F, '<I', '行业二级分类'
    # 0x60-0x65 保留
    AUCTION_BUY_LIMIT      = 0x66, '<f', '连续竞价买入上限'
    AUCTION_SELL_LIMIT     = 0x67, '<f', '连续竞价卖出下限'
    VOL_SPEED_PCT          = 0x68, '<f', '量涨速%'
    SHORT_TURNOVER_PCT     = 0x69, '<f', '短换手%'
    AMOUNT_2M              = 0x6A, '<f', '2分钟金额(元)'
    MAIN_NET_AMOUNT_COPY   = 0x6B, '<f', '今日主力净流入(副本)'  # 与 0x38 相同
    MAIN_NET_RATIO         = 0x6C, '<f', '主力净比%'
    RETAIL_NET_AMOUNT      = 0x6D, '<f', '散户单增比'
    MAIN_NET_5M_AMOUNT     = 0x6E, '<f', '5分钟主力净额'
    MAIN_NET_3D_AMOUNT     = 0x6F, '<f', '近三日主力净额'
    MAIN_NET_5D_AMOUNT     = 0x70, '<f', '近五日主力净额'
    MAIN_NET_10D_AMOUNT    = 0x71, '<f', '近十日主买金额(待确定)'
    MAIN_BUY_NET_AMOUNT    = 0x72, '<f', '今日主买净额'
    DDX                    = 0x73, '<f', 'DDX'
    DDY                    = 0x74, '<f', 'DDY'
    DDZ                    = 0x75, '<f', 'DDZ'
    DDF                    = 0x76, '<f', 'DDF'

    # ── 0x77-0x8F ──
    PREV_AMOUNT            = 0x7B, '<f', '昨成交额(元)'
    AUCTION_VOL_RATIO      = 0x7A, '<f', '竞价昨比'
    RECENT_INDICATOR       = 0x7D, '<f', '近日指标提示' #6:KDJ死叉 92:阶段放量 #TODO导出TDX数据分析这个字段的所有枚举值
    # 0x7E-0x7F 保留
    BID3_PRICE             = 0x80, '<f', '买三价'
    BID4_PRICE             = 0x81, '<f', '买四价'
    BID5_PRICE             = 0x82, '<f', '买五价'
    ASK3_PRICE             = 0x83, '<f', '卖三价'
    ASK4_PRICE             = 0x84, '<f', '卖四价'
    ASK5_PRICE             = 0x85, '<f', '卖五价'
    BID3_VOLUME            = 0x86, '<I', '买三量'
    BID4_VOLUME            = 0x87, '<I', '买四量'
    UP_COUNT               = 0x88, '<I', '上涨家数(板块) / 买五量(个股)'
    BID5_VOLUME            = 0x88, '<I', '买五量(个股)'  # UP_COUNT 别名
    ASK3_VOLUME            = 0x89, '<I', '卖三量'
    ASK4_VOLUME            = 0x8A, '<I', '卖四量'
    DOWN_COUNT             = 0x8B, '<I', '下跌家数(板块) / 卖五量(个股)'
    ASK5_VOLUME            = 0x8B, '<I', '卖五量(个股)'  # DOWN_COUNT 别名
    BID_ASK_DIFF           = 0x8C, '<i', '委差'  # 买量-卖量
    CHANGE_UP_TYPE         = 0x8D, '<i', '封板状态(见 enums.ChangeUpType)'
    CONSTANT_NEG_ONE       = 0x8E, '<i', '恒为-1'
    HIGHLIGHT_COUNT        = 0x8F, '<i', '亮点数'

    # ── 0x90-0x96: 日内时间涨幅(从昨收算) ──
    CHANGE_AT_1000         = 0x90, '<f', '日内涨幅% 10:00'
    CHANGE_AT_1030         = 0x91, '<f', '日内涨幅% 10:30'
    CHANGE_AT_1100         = 0x92, '<f', '日内涨幅% 11:00'
    CHANGE_AT_1130         = 0x93, '<f', '日内涨幅% 11:30'
    CHANGE_AT_1330         = 0x94, '<f', '日内涨幅% 13:30'
    CHANGE_AT_1400         = 0x95, '<f', '日内涨幅% 14:00'
    CHANGE_AT_1430         = 0x96, '<f', '日内涨幅% 14:30'


# 从 FieldBit 自动生成，保持向后兼容
FIELD_BITMAP_MAP: dict[int, tuple[str, str, str]] = {
    bit.value: (bit.name.lower(), bit.fmt, bit.desc)
    for bit in FieldBit
}


# ── 字段后处理钩子 ──
# 对需要二次加工的字段注册回调: (value, stock_dict) -> processed_value
def _post_ah_code(value, stock):
    """A/H股代码补齐位数"""
    if not value:
        return ''
    from opentdx.const import MARKET
    width = 5 if stock.get('market') in (MARKET.SZ, MARKET.SH, MARKET.BJ) else 6
    return str(value).zfill(width)


FIELD_POSTPROCESS = {
    0x4A: _post_ah_code,  # AH_CODE: 补齐0
}


# ── 预定义字段集合 ──

class PresetField(Enum):
    """预定义字段集合，支持 + / | 链式组合

    Usage:
        PresetField.BASIC + PresetField.VOLUME          # 两个预设合并
        PresetField.OHLC + FieldBit.AH_CODE             # 预设 + 单字段
        FieldBit.OPEN + FieldBit.HIGH + FieldBit.LOW    # 纯字段组合
    """
    NONE = ()
    OHLC = (FieldBit.OPEN, FieldBit.HIGH, FieldBit.LOW, FieldBit.CLOSE)
    BASIC = OHLC + (FieldBit.PRE_CLOSE, FieldBit.VOL)
    QUOTE = (FieldBit.BID_PRICE, FieldBit.ASK_PRICE, FieldBit.BID_VOLUME, FieldBit.ASK_VOLUME, FieldBit.LAST_VOLUME)
    VOLUME = (FieldBit.VOL, FieldBit.AMOUNT, FieldBit.TURNOVER, FieldBit.VOL_RATIO)
    FUNDAMENTAL = (FieldBit.TOTAL_SHARES, FieldBit.FLOAT_SHARES, FieldBit.EPS, FieldBit.NET_ASSETS)
    ENHANCED = OHLC + (FieldBit.VOL, FieldBit.FLOAT_SHARES, FieldBit.ACTIVITY)
    AH_CODE = OHLC + (FieldBit.VOL, FieldBit.AH_CODE, FieldBit.LOT_SIZE, FieldBit.INDUSTRY)
    BOARD_STATS = (FieldBit.LIMIT_UP_COUNT, FieldBit.LIMIT_DOWN_COUNT, FieldBit.UP_COUNT, FieldBit.DOWN_COUNT)  # 板块统计
    HANDICAP = (FieldBit.BID_PRICE, FieldBit.BID2_PRICE, FieldBit.BID3_PRICE, FieldBit.BID4_PRICE, FieldBit.BID5_PRICE,
                FieldBit.ASK_PRICE, FieldBit.ASK2_PRICE, FieldBit.ASK3_PRICE, FieldBit.ASK4_PRICE, FieldBit.ASK5_PRICE,
                FieldBit.BID_VOLUME, FieldBit.BID2_VOLUME, FieldBit.BID3_VOLUME, FieldBit.BID4_VOLUME, FieldBit.BID5_VOLUME,
                FieldBit.ASK_VOLUME, FieldBit.ASK2_VOLUME, FieldBit.ASK3_VOLUME, FieldBit.ASK4_VOLUME, FieldBit.ASK5_VOLUME)  # 五档盘口
    COMMON = (FieldBit.PRE_CLOSE, FieldBit.OPEN, FieldBit.HIGH, FieldBit.LOW, FieldBit.CLOSE, FieldBit.VOL,
               FieldBit.VOL_RATIO, FieldBit.AMOUNT, FieldBit.TOTAL_SHARES, FieldBit.FLOAT_SHARES, FieldBit.EPS,
               FieldBit.NET_ASSETS, FieldBit.UNKNOWN_ACTION_PRICE, FieldBit.TOTAL_MARKET_CAP_AB, FieldBit.PE_DYNAMIC,
               FieldBit.LOT_SIZE_INFO, FieldBit.DIVIDEND_YIELD, FieldBit.LAST_VOLUME,
               FieldBit.TURNOVER, FieldBit.SOME_BITMAP, FieldBit.DECIMAL_POINT, FieldBit.BUY_PRICE_LIMIT,
               FieldBit.SELL_PRICE_LIMIT, FieldBit.UNKNOWN_34, FieldBit.LOT_SIZE, FieldBit.PRE_IPOV,
                FieldBit.SPEED_PCT, FieldBit.FLAG_KCB, FieldBit.PE_TTM, FieldBit.PE_STATIC, FieldBit.MAIN_NET_AMOUNT,
               FieldBit.VOL_SPEED_PCT, FieldBit.SHORT_TURNOVER_PCT, FieldBit.CIRCULATING_CAPITAL_Z)
    DEBUG = ()
    ALL = tuple(FieldBit)

    def __add__(self, other) -> FieldSelection:
        if isinstance(other, (FieldBit, PresetField, FieldSelection)):
            return FieldSelection(self, other)
        return NotImplemented

    def __or__(self, other) -> FieldSelection:
        return self.__add__(other)

    def __radd__(self, other) -> FieldSelection:
        if isinstance(other, (FieldBit, FieldSelection)):
            return FieldSelection(other, self)
        return NotImplemented

    def __ror__(self, other) -> FieldSelection:
        return self.__radd__(other)


class FieldSelection:
    """字段选择器，支持 PresetField + FieldBit 组合

    Usage:
        PresetField.BASIC + FieldBit.AH_CODE
        PresetField.BASIC | FieldBit.INDUSTRY
        FieldBit.OPEN + FieldBit.HIGH + FieldBit.LOW
    """
    __slots__ = ('_fields',)

    def __init__(self, *parts: FieldBit | PresetField | FieldSelection):
        seen = set()
        result = []
        for part in parts:
            source = (part.value if isinstance(part, PresetField)
                      else (part,) if isinstance(part, FieldBit)
                      else part._fields)
            for bit in source:
                if bit not in seen:
                    seen.add(bit)
                    result.append(bit)
        self._fields = tuple(result)

    def __add__(self, other) -> FieldSelection:
        if isinstance(other, (FieldBit, PresetField, FieldSelection)):
            return FieldSelection(self, other)
        return NotImplemented

    def __or__(self, other) -> FieldSelection:
        return self.__add__(other)

    def __radd__(self, other) -> FieldSelection:
        if isinstance(other, (FieldBit, PresetField)):
            return FieldSelection(other, self)
        return NotImplemented

    def __ror__(self, other) -> FieldSelection:
        return self.__radd__(other)

    def __iter__(self):
        return iter(self._fields)

    def __len__(self):
        return len(self._fields)

    def __bool__(self):
        return bool(self._fields)

    def __contains__(self, item):
        return item in self._fields

    def __repr__(self):
        names = [bit.name for bit in self._fields]
        return f"FieldSelection([{', '.join(names)}])"


def normalize_fields(fields: Fields) -> FieldSelection:
    """将任意字段选择形式归一化为 FieldSelection"""
    if isinstance(fields, FieldSelection):
        return fields
    if isinstance(fields, PresetField):
        return FieldSelection(*fields.value)
    if isinstance(fields, FieldBit):
        return FieldSelection(fields)
    return FieldSelection(*fields)


def get_active_fields_from_bitmap(bitmap_bytes: bytes) -> list[int]:
    """从响应位图中提取活跃位（按位序升序）"""
    bitmap_int = int.from_bytes(bitmap_bytes, 'little')
    active_bits = []
    while bitmap_int:
        lowbit = bitmap_int & -bitmap_int
        bit_pos = lowbit.bit_length() - 1
        active_bits.append(bit_pos)
        bitmap_int ^= lowbit
    return active_bits


def build_bitmap(fields: Fields) -> bytearray:
    """将字段选择转换为 20 字节请求位图"""
    if isinstance(fields, PresetField) and fields is PresetField.DEBUG:
        return bytearray(b'\xff' * 20)
    selection = normalize_fields(fields)
    bitmap_int = 0
    for bit in selection:
        bitmap_int |= (1 << bit.value)
    return bytearray(bitmap_int.to_bytes(20, 'little'))
