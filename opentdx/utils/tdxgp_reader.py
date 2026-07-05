"""TDXGP 股网交易事件解析器。

解析通达信 gpszsh.txt / gpsh...dat / gpsz...dat / gpbj...dat 文件，
将二进制 gpjvalue 数据转为标准 DataFrame。

数据格式
--------
每条记录固定 13 字节，小端序::

    类型(uint8) | 日期(uint32, YYYYMMDD) | 值1(float32) | 值2(float32)

文件名编码规则
--------------
- ``gpshXXXXXX.dat`` → 上海 (sh)
- ``gpszXXXXXX.dat`` → 深圳 (sz)
- ``gpbjXXXXXX.dat`` → 北交所 (bj)

索引文件格式 (gpszsh.txt / gpsh.txt / gpbj.txt)
-----------------------------------------------
每行 ``文件名,md5,文件大小``，例如::

    gpsz302132.dat,61b0678f44653d0b0ff28e6c6eae74fe,248027

用法
----
.. code-block:: python

    from opentdx.utils.tdxgp_reader import TdxgpReader

    reader = TdxgpReader()
    df = reader.get_df(b"path/to/gpsz000001.dat")

    # 解析索引文件
    entries = reader.parse_index(text_bytes)
"""

from __future__ import annotations

import struct
import io
import zipfile
from collections import OrderedDict
from pathlib import Path
from typing import BinaryIO

import pandas as pd

# ── 记录格式 ──────────────────────────────────────────────
RECORD_SIZE = 13
RECORD_FORMAT = "<BIff"

# ── type_id → (字段名, 单位, 描述) ─────────────────────────
# 推测来源：社区脚本分析与样本数据比对。非通达信官方文档。
GPJY_META: dict[int, tuple[str, str, str]] = {
    1:  ("shareholder_count", "count", "股东人数"),
    2:  ("lhb_total_amount", "10k_cny", "龙虎榜买卖总额"),
    3:  ("margin_balance", "10k_cny", "融资余额 / 融券余额"),
    4:  ("margin_balance_change", "10k_cny", "融资余额变化 / 融券余额变化"),
    5:  ("lhb_detail", "mixed", "龙虎榜成交明细"),
    6:  ("northbound_holding", "share", "北向持股"),
    7:  ("northbound_net_buy", "share", "北向净买入"),
    8:  ("northbound_net_buy_amount", "10k_cny", "北向净买入金额"),
    9:  ("lhb_broker_detail", "mixed", "龙虎榜营业部明细"),
    10: ("lhb_institution_detail", "mixed", "龙虎榜机构明细"),
    11: ("margin_finance", "10k_cny", "融资买入 / 融资偿还"),
    12: ("margin_securities", "10k_cny", "融券卖出 / 融券偿还"),
    13: ("margin_net", "10k_cny", "融资净额 / 融券净额"),
    14: ("margin_collateral", "mixed", "融资融券担保品"),
    15: ("limit_status", "status", "涨跌停状态"),
    16: ("total_market_cap", "10k_cny", "总市值"),
    17: ("lhb_institution_count", "count", "龙虎榜机构数量"),
    18: ("lhb_hgt_amount", "10k_cny", "龙虎榜沪股通金额"),
}


def _infer_symbol_from_filename(filename: str) -> str:
    """从 tdkgp 文件名推断 stock symbol。

    >>> _infer_symbol_from_filename("gpsz302132.dat")
    'sz302132'
    >>> _infer_symbol_from_filename("gpsh600000.dat")
    'sh600000'
    >>> _infer_symbol_from_filename("gpbj430001.dat")
    'bj430001'
    """
    stem = Path(filename).stem
    market = ""
    # 文件名格式: gp + 市场标识(sh/sz/bj) + 6位代码
    # gpsh → sh, gpsz → sz, gpbj → bj, code 从第 4 字符开始
    if stem.startswith("gpsh"):
        market = "sh"
    elif stem.startswith("gpsz"):
        market = "sz"
    elif stem.startswith("gpbj"):
        market = "bj"
    if not market:
        raise ValueError(f"无法从文件名推断市场: {filename}")

    code = stem[4:]
    if len(code) != 6:
        raise ValueError(f"非法文件名 (code 长度异常, 期望 6 位, 实际 {len(code)}): {filename}")

    return market + code


def parse_index(text_or_bytes: bytes | bytearray | str) -> list[dict]:
    """解析 tdxgp 索引文件（如 gpszsh.txt）。

    每行格式::

        文件名,md5,文件大小

    Parameters
    ----------
    text_or_bytes : bytes | bytearray | str
        索引文件内容。

    Returns
    -------
    list[dict]
        - ``filename`` : str   文件名 (gpsz000001.dat)
        - ``hash`` : str       MD5
        - ``filesize`` : int   文件大小 (字节)
    """
    if isinstance(text_or_bytes, (bytes, bytearray)):
        text = bytes(text_or_bytes).decode("utf-8", errors="replace")
    else:
        text = text_or_bytes

    entries: list[dict] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 3:
            continue
        try:
            entries.append({
                "filename": parts[0],
                "hash": parts[1],
                "filesize": int(parts[2]),
            })
        except (ValueError, IndexError):
            continue
    return entries


def parse_dat(
    fobj: BinaryIO | bytes | bytearray | str,
    filename: str | None = None,
    types: list[int] | None = None,
    start_date: int | None = None,
    end_date: int | None = None,
) -> list[dict]:
    """解析单个 .dat tdkgp 文件。

    Parameters
    ----------
    fobj : BinaryIO | bytes | bytearray | str
        文件对象、字节内容或文件路径。
    filename : str, optional
        用于推断 symbol 的文件名。必填于 bytes 输入；路径时间从路径名推导。
    types : list[int], optional
        只返回匹配的 type_id。None 表示全部。
    start_date : int, optional
        只返回 date >= start_date 的记录 (YYYYMMDD)。
    end_date : int, optional
        只返回 date <= end_date 的记录 (YYYYMMDD)。

    Returns
    -------
    list[dict]
        - ``symbol`` : str        stock symbol (sh000001)
        - ``market`` : str        市场 (sh/sz/bj)
        - ``code`` : str          6位代码
        - ``type_id`` : int       指标类型
        - ``date`` : int          YYYYMMDD
        - ``value1`` : float      值1
        - ``value2`` : float      值2
        - ``field`` : str         推测字段名
        - ``unit`` : str          推测单位
        - ``description`` : str   推测描述
    """
    if isinstance(fobj, str):
        with open(fobj, "rb") as fh:
            raw = fh.read()
        if filename is None:
            filename = Path(fobj).name
    elif isinstance(fobj, (bytes, bytearray)):
        raw = bytes(fobj)
    elif hasattr(fobj, "read"):
        raw = fobj.read()
    else:
        raise TypeError(f"不支持的输入类型: {type(fobj)}")

    if filename is None:
        raise ValueError("filename 不能为空（用于推断 symbol）")

    symbol = _infer_symbol_from_filename(filename)
    market = symbol[:2]

    meta = GPJY_META

    results: list[dict] = []
    count = len(raw) // RECORD_SIZE
    offset = 0

    # 预编译类型集合加速过滤
    type_set = set(types) if types else None

    for _ in range(count):
        try:
            type_id, dt, v1, v2 = struct.unpack_from(RECORD_FORMAT, raw, offset)
        except struct.error:
            break

        offset += RECORD_SIZE

        if type_set is not None and type_id not in type_set:
            continue
        if start_date is not None and dt < start_date:
            continue
        if end_date is not None and dt > end_date:
            continue

        field_name, unit, desc = meta.get(
            type_id,
            (f"gpjy_{type_id}", "unknown", f"未知类型 {type_id}"),
        )

        results.append({
            "symbol": symbol,
            "market": market,
            "code": symbol[2:],
            "type_id": type_id,
            "date": dt,
            "value1": v1,
            "value2": v2,
            "field": field_name,
            "unit": unit,
            "description": desc,
        })

    return results


class TdxgpReader:
    """TDXGP 事件数据解析器。

    支持输入路径、字节或 zip 文件。

    .. code-block:: python

        reader = TdxgpReader()
        df = reader.get_df("gpsz000001.dat")
        rows = reader.get_data(b"...")

        # 带过滤
        rows = reader.get_data("gpsz000001.dat", types=[1, 16], start_date=20240101)

        # 从 zip 解析
        rows = reader.get_data_from_zip("tdxgp.zip")
    """

    def get_data(
        self,
        fobj: BinaryIO | bytes | bytearray | str,
        filename: str | None = None,
        types: list[int] | None = None,
        start_date: int | None = None,
        end_date: int | None = None,
    ) -> list[dict]:
        """解析单个 tdkgp .dat 文件，返回 dict 列表。

        Parameters
        ----------
        fobj : BinaryIO | bytes | bytearray | str
            文件对象、字节内容或文件路径。
        filename : str, optional
            文件名 (用于符号推断)。对 bytes 输入为必填。
        types : list[int], optional
            type_id 过滤。None 表示所有类型。
        start_date : int, optional
            起始日期 YYYYMMDD，闭区间。
        end_date : int, optional
            结束日期 YYYYMMDD，闭区间。

        Returns
        -------
        list[dict]
        """
        return parse_dat(fobj, filename=filename, types=types, start_date=start_date, end_date=end_date)

    def get_df(
        self,
        fobj: BinaryIO | bytes | bytearray | str,
        filename: str | None = None,
        types: list[int] | None = None,
        start_date: int | None = None,
        end_date: int | None = None,
    ) -> pd.DataFrame:
        """解析单个 tdkgp .dat 文件，返回 DataFrame。

        参数同 :meth:`get_data`。
        """
        rows = self.get_data(fobj, filename=filename, types=types, start_date=start_date, end_date=end_date)
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        # 排序
        df.sort_values(["symbol", "type_id", "date"], inplace=True)
        df.reset_index(drop=True, inplace=True)
        return df

    def get_data_from_zip(
        self,
        fobj: BinaryIO | bytes | bytearray | str,
        types: list[int] | None = None,
        start_date: int | None = None,
        end_date: int | None = None,
    ) -> list[dict]:
        """从 zip 文件中解析所有 .dat。

        Parameters
        ----------
        fobj : BinaryIO | bytes | bytearray | str
            zip 文件对象、字节内容或文件路径。
        types : list[int], optional
        start_date : int, optional
        end_date : int, optional

        Returns
        -------
        list[dict]
            所有有效 .dat 文件的合并结果。
        """
        if isinstance(fobj, str):
            with open(fobj, "rb") as fh:
                raw = fh.read()
        elif isinstance(fobj, (bytes, bytearray)):
            raw = bytes(fobj)
        elif hasattr(fobj, "read"):
            raw = fobj.read()
        else:
            raise TypeError(f"不支持的输入类型: {type(fobj)}")

        all_rows: list[dict] = []
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            for name in zf.namelist():
                stem = Path(name).stem
                if not (stem.startswith("gpsh") or stem.startswith("gpsz") or stem.startswith("gpbj")):
                    continue
                if not name.endswith(".dat"):
                    continue
                try:
                    dat_bytes = zf.read(name)
                    rows = parse_dat(dat_bytes, filename=name, types=types,
                                     start_date=start_date, end_date=end_date)
                    all_rows.extend(rows)
                except ValueError:
                    continue
        return all_rows

    def get_df_from_zip(
        self,
        fobj: BinaryIO | bytes | bytearray | str,
        types: list[int] | None = None,
        start_date: int | None = None,
        end_date: int | None = None,
    ) -> pd.DataFrame:
        """从 zip 文件中解析所有 .dat，返回 DataFrame。

        参数同 :meth:`get_data_from_zip`。
        """
        rows = self.get_data_from_zip(fobj, types=types, start_date=start_date, end_date=end_date)
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        df.sort_values(["symbol", "type_id", "date"], inplace=True)
        df.reset_index(drop=True, inplace=True)
        return df

    @staticmethod
    def parse_index(text_or_bytes: bytes | bytearray | str) -> list[dict]:
        """解析 tdxgp 索引文件。

        Parameters
        ----------
        text_or_bytes : bytes | bytearray | str
            gpszsh.txt 等索引文件内容。

        Returns
        -------
        list[dict]
            - ``filename`` : str
            - ``hash`` : str
            - ``filesize`` : int
        """
        return parse_index(text_or_bytes)
