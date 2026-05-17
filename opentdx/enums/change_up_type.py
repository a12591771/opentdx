# coding=utf-8
from __future__ import annotations
from enum import IntEnum


class ChangeUpType(IntEnum):
    """
    涨跌停封板状态（对应 Level-2 行情 CHANGE_UP_TYPE 字段，数值不可变）
    """

    # ---------- 未触碰涨跌停 ----------
    无 = 0                     # 未触碰涨跌停

    # ---------- 跌停相关 ----------
    一字跌停 = 3               # 开盘即封死跌停，全天未打开
    倒T跌停 = 4                # 跌停板开后回封（倒T形态）
    换手跌停 = 5               # 换手跌停，始终未封死

    # ---------- 大幅波动 / 异动 ----------
    大幅波动 = 7               # 盘中振幅巨大，未封板
    冲涨停 = 8                 # 盘中曾触及涨停但未封板
    炸板 = 9                   # 曾封涨停，后被打开
    近跌停 = 15                # 接近跌停但未封死
    拉洗板 = 19                # 拉高洗盘形态
    近涨停 = 24                # 接近涨停但未封死

    # ---------- 涨停相关 ----------
    一字板 = 21                # 一字涨停板（开盘即封死）
    T字板 = 22                 # T字板（一字开板后回封涨停）
    换手板 = 23                # 充分换手后封板
    厂字板 = 25                # 厂字形态（早盘快速封板后不再打开）
    地天板 = 32                # 从跌停板拉升至涨停板
    天地板 = 33                # 从涨停板跌至跌停板
    回封板 = 41                # 涨停板打开后再次封回

    def 是否封死涨停(self) -> bool:
        """最终封死涨停（一字板、T字板、换手板、厂字板、回封板、地天板）"""
        return self in {
            self.一字板, self.T字板, self.换手板,
            self.厂字板, self.回封板, self.地天板,
        }

    def 是否封死跌停(self) -> bool:
        """最终封死跌停（一字跌停、倒T跌停、换手跌停、天地板）"""
        return self in {
            self.一字跌停, self.倒T跌停, self.换手跌停, self.天地板,
        }

    def 是否触碰涨停(self) -> bool:
        """盘中曾触及涨停（包括炸板、冲涨停、各封板类型）"""
        return self in {
            self.冲涨停, self.炸板, self.一字板, self.T字板,
            self.换手板, self.近涨停, self.厂字板,
            self.回封板, self.地天板,
        }

    def 是否触碰跌停(self) -> bool:
        """盘中曾触及跌停（包括跌停相关、天地板）"""
        return self in {
            self.一字跌停, self.倒T跌停, self.换手跌停,
            self.近跌停, self.天地板,
        }

    @property
    def is_sealed_up(self) -> bool:
        return self.是否封死涨停()

    @property
    def is_sealed_down(self) -> bool:
        return self.是否封死跌停()

    @property
    def has_touched_up(self) -> bool:
        return self.是否触碰涨停()

    @property
    def has_touched_down(self) -> bool:
        return self.是否触碰跌停()
