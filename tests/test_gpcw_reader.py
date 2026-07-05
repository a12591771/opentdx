"""GPCW 财务数据解析器单元测试。

测试覆盖:
- parse_gpcw: dat / bytes 解析
- GpcwReader.parse / to_df / parse_to_df
- GCW_COLUMNS 完整性
- 与 mootdx Financial 解析结果精确比对
- 集成测试 (需 tdx fixture): 真实网络下载
"""
from __future__ import annotations

import struct
import os
import io
import tempfile
import zipfile

import numpy as np
import pandas as pd
import pytest

from opentdx.utils.gpcw_reader import (
    GCW_COLUMNS,
    HEADER_FORMAT,
    STOCK_ITEM_FORMAT,
    GpcwReader,
    parse_gpcw,
)

# ── 辅助函数 ──────────────────────────────────────────────


def _make_gpcw_raw(stocks_info: list[dict], report_date: int = 20251231) -> bytes:
    """构造一个最小的、合法的 GCW dat 二进制数据。

    Parameters
    ----------
    stocks_info : list[dict]
        每项含 ``code`` (str, 6位) 和 ``fields`` (list[float])。
    report_date : int
        报告日期 YYYYMMDD。

    Returns
    -------
    bytes
    """
    max_count = len(stocks_info)
    fields_per_stock = len(stocks_info[0]["fields"]) if stocks_info else 0
    report_size = fields_per_stock * 4

    header_size = struct.calcsize(HEADER_FORMAT)
    stock_item_size = struct.calcsize(STOCK_ITEM_FORMAT)

    # 计算数据区起始偏移
    data_start = header_size + max_count * stock_item_size

    buf = io.BytesIO()

    # header
    buf.write(struct.pack(HEADER_FORMAT, 1, report_date, max_count, 0, report_size, 0))

    # stock items + data
    for i, info in enumerate(stocks_info):
        code_bytes = info["code"].encode("utf-8")
        market = 1 if info.get("market") == 1 else 0
        data_offset = data_start + i * report_size
        buf.write(struct.pack(STOCK_ITEM_FORMAT, code_bytes, market.to_bytes(1, "little"), data_offset))

    # data blocks
    for info in stocks_info:
        for f in info["fields"]:
            buf.write(struct.pack("<f", f))

    return buf.getvalue()


# ── parse_gpcw ────────────────────────────────────────────


class TestParseGpcw:
    """parse_gpcw 单元测试 —— 构造数据"""

    def test_two_stocks_three_fields(self):
        raw = _make_gpcw_raw(
            [
                {"code": "000001", "fields": [1.0, 2.0, 3.0]},
                {"code": "600000", "fields": [4.0, 5.0, 6.0]},
            ],
            report_date=20250331,
        )
        data = parse_gpcw(raw, fmt="dat")
        assert len(data) == 2
        # (code, report_date, f0, f1, f2)
        assert data[0] == ("000001", 20250331, 1.0, 2.0, 3.0)
        assert data[1] == ("600000", 20250331, 4.0, 5.0, 6.0)

    def test_empty_file(self):
        raw = _make_gpcw_raw([], report_date=20251231)
        data = parse_gpcw(raw, fmt="dat")
        assert data == []

    def test_zero_fields(self):
        """没有财务字段的股票也能解析"""
        raw = _make_gpcw_raw(
            [{"code": "000001", "fields": []}],
            report_date=20251231,
        )
        data = parse_gpcw(raw, fmt="dat")
        assert len(data) == 1
        assert data[0] == ("000001", 20251231)

    def test_nan_values(self):
        """包含 NaN/inf 值的字段"""
        raw = _make_gpcw_raw(
            [{"code": "000001", "fields": [float("nan"), float("inf"), -float("inf")]}],
        )
        data = parse_gpcw(raw, fmt="dat")
        assert len(data) == 1
        c0, c1, c2 = data[0][2], data[0][3], data[0][4]
        assert np.isnan(c0)
        assert np.isposinf(c1)
        assert np.isneginf(c2)

    def test_from_file_path(self, tmp_path):
        """从文件路径解析"""
        raw = _make_gpcw_raw(
            [{"code": "000001", "fields": [2.0, 3.0]}],
            report_date=20231231,
        )
        path = tmp_path / "gpcw20231231.dat"
        path.write_bytes(raw)
        data = parse_gpcw(str(path))
        assert len(data) == 1
        assert data[0][0] == "000001"
        assert data[0][1] == 20231231

    def test_from_bytearray(self):
        raw = _make_gpcw_raw([{"code": "000001", "fields": [1.0]}])
        data = parse_gpcw(bytearray(raw), fmt="dat")
        assert len(data) == 1

    def test_from_file_object(self):
        raw = _make_gpcw_raw([{"code": "000001", "fields": [1.0]}])
        data = parse_gpcw(io.BytesIO(raw), fmt="dat")
        assert len(data) == 1

    def test_invalid_type(self):
        with pytest.raises(TypeError, match="不支持的输入类型"):
            parse_gpcw(12345)

    def test_report_date_in_data(self):
        """report_date 应出现在每条记录的第二个位置"""
        raw = _make_gpcw_raw(
            [
                {"code": "000001", "fields": [1.0]},
                {"code": "600000", "fields": [2.0]},
            ],
            report_date=20240630,
        )
        data = parse_gpcw(raw, fmt="dat")
        assert data[0][1] == 20240630
        assert data[1][1] == 20240630


# ── GpcwReader ────────────────────────────────────────────


class TestGpcwReader:
    """GpcwReader 类方法测试"""

    def test_parse(self):
        raw = _make_gpcw_raw([{"code": "000001", "fields": [10.0, 20.0]}])
        reader = GpcwReader()
        data = reader.parse(raw, fmt="dat")
        assert len(data) == 1
        assert data[0][0] == "000001"

    def test_to_df_zh_header(self):
        raw = _make_gpcw_raw(
            [
                {"code": "000001", "fields": [2.07, 1.5, 3.0]},
                {"code": "600000", "fields": [1.52, 2.0, 4.0]},
            ],
            report_date=20251231,
        )
        reader = GpcwReader()
        data = reader.parse(raw, fmt="dat")
        df = reader.to_df(data, header="zh")
        assert df.shape == (2, 4)  # 1 report_date + 3 fields
        assert df.index.name == "code"
        assert df.loc["000001", "report_date"] == 20251231
        # 中文列名应来自 GCW_COLUMNS
        expected_cols = [GCW_COLUMNS[0], GCW_COLUMNS[1], GCW_COLUMNS[2], GCW_COLUMNS[3]]
        assert list(df.columns) == expected_cols
        assert df.loc["000001", GCW_COLUMNS[1]] == pytest.approx(2.07, rel=1e-5)

    def test_to_df_no_header(self):
        raw = _make_gpcw_raw(
            [
                {"code": "000001", "fields": [2.07, 1.5]},
                {"code": "600000", "fields": [1.52, 2.0]},
            ],
        )
        reader = GpcwReader()
        data = reader.parse(raw, fmt="dat")
        df = reader.to_df(data, header=None)
        assert list(df.columns) == ["report_date", "col1", "col2"]

    def test_to_df_empty(self):
        reader = GpcwReader()
        df = reader.to_df([], header="zh")
        assert df.empty

    def test_parse_to_df(self):
        raw = _make_gpcw_raw(
            [{"code": "000001", "fields": [2.07, 1.5, 3.0]}],
            report_date=20251231,
        )
        reader = GpcwReader()
        df = reader.parse_to_df(raw, fmt="dat", header="zh")
        assert df.shape == (1, 4)
        assert list(df.columns[:3]) == GCW_COLUMNS[:3]

    def test_to_df_column_overflow(self):
        """当 fields 数量超过 GCW_COLUMNS 时，剩余列用 colN"""
        many_fields = list(range(600))
        raw = _make_gpcw_raw(
            [{"code": "000001", "fields": many_fields}],
        )
        reader = GpcwReader()
        data = reader.parse(raw, fmt="dat")
        df = reader.to_df(data, header="zh")
        # GCW_COLUMNS 有 583 个，600 > 583 所以有溢出列
        assert df.shape[1] > len(GCW_COLUMNS)
        # 溢出列名
        assert any(c.startswith("col") for c in df.columns)


# ── GpcwReader zip 解析 ───────────────────────────────────


class TestGpcwReaderZip:
    """GpcwReader zip 格式解析测试"""

    def test_parse_zip_bytes(self):
        """从 zip bytes 解析"""
        raw = _make_gpcw_raw(
            [{"code": "000001", "fields": [2.07, 1.5]}],
            report_date=20251231,
        )
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("gpcw20251231.dat", raw)
        zip_data = buf.getvalue()

        reader = GpcwReader()
        data = reader.parse(zip_data, fmt="zip")
        assert len(data) == 1
        assert data[0][0] == "000001"
        assert data[0][1] == 20251231

    def test_parse_to_df_zip(self):
        raw = _make_gpcw_raw(
            [{"code": "000001", "fields": [2.07, 1.5]}],
            report_date=20251231,
        )
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("gpcw20251231.dat", raw)
        zip_data = buf.getvalue()

        reader = GpcwReader()
        df = reader.parse_to_df(zip_data, fmt="zip", header="zh")
        assert df.shape == (1, 3)
        assert df.loc["000001", GCW_COLUMNS[1]] == pytest.approx(2.07, rel=1e-5)

    def test_parse_zip_file(self, tmp_path):
        raw = _make_gpcw_raw(
            [{"code": "000001", "fields": [2.07, 1.5]}],
            report_date=20251231,
        )
        dat_path = tmp_path / "gpcw20251231.dat"
        dat_path.write_bytes(raw)
        zip_path = tmp_path / "test.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(str(dat_path), arcname="gpcw20251231.dat")

        reader = GpcwReader()
        data = reader.parse(str(zip_path))
        assert len(data) == 1
        assert data[0][0] == "000001"

    def test_zip_no_dat_file(self):
        """zip 内不含 .dat 文件应抛异常"""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("readme.txt", "hello")
        reader = GpcwReader()
        with pytest.raises(ValueError, match="未找到 .dat 文件"):
            reader.parse(buf.getvalue(), fmt="zip")


# ── GCW_COLUMNS ───────────────────────────────────────────


class TestGcwColumns:
    """GCW_COLUMNS 完整性测试"""

    def test_non_empty(self):
        assert len(GCW_COLUMNS) > 0
        assert GCW_COLUMNS[0] == "report_date"

    def test_all_strings(self):
        assert all(isinstance(c, str) for c in GCW_COLUMNS)


# ── 与 mootdx 精确比对 (集成测试) ─────────────────────────


@pytest.mark.integration
class TestGpcwVsMootdx:
    """与 mootdx Financial.parse 结果精确比对"""

    def test_identical_parse_result(self, tdx):
        """opentdx GpcwReader 应与 mootdx Financial 结果完全一致"""
        from mootdx.financial.financial import Financial

        dat = tdx.stock_report_file("tdxfin/gpcw20251231.dat")
        with tempfile.NamedTemporaryFile(suffix=".dat", delete=False) as tmp:
            tmp.write(dat)
            tmp_path = tmp.name

        try:
            # opentdx
            reader = GpcwReader()
            df_o = reader.parse_to_df(tmp_path, header="zh")

            # mootdx
            financial = Financial()
            data_m = financial.parse(open(tmp_path, "rb"))
            df_m = financial.to_df(data_m, header="zh")

            assert len(df_o) == len(df_m)
            assert df_o.shape == df_m.shape
            assert list(df_o.index) == list(df_m.index)
            assert list(df_o.columns) == list(df_m.columns)

            a = df_o.to_numpy(dtype=np.float64)
            b = df_m.to_numpy(dtype=np.float64)
            assert np.allclose(a, b, rtol=1e-5, atol=1e-3), "数值不一致"
        finally:
            os.unlink(tmp_path)

    def test_report_date_parsed(self, tdx):
        """report_date 应正确解析"""
        reader = GpcwReader()
        dat = tdx.stock_report_file("tdxfin/gpcw20251231.dat")
        df = reader.parse_to_df(dat, fmt="dat", header="zh")
        assert (df["report_date"] == 20251231).all()

        dat2 = tdx.stock_report_file("tdxfin/gpcw20250930.dat")
        df2 = reader.parse_to_df(dat2, fmt="dat", header="zh")
        if not df2.empty:
            assert (df2["report_date"] == 20250930).all()


# ── 集成测试 (下载 + 解析) ────────────────────────────────


@pytest.mark.integration
class TestGpcwIntegration:
    """集成测试：真实网络下载 + 解析"""

    def test_download_and_parse_dat(self, tdx):
        """从 opentdx 下载 gpcw dat 并解析"""
        reader = GpcwReader()
        dat = tdx.stock_report_file("tdxfin/gpcw20251231.dat")
        assert len(dat) > 1000, "文件太小，可能下载失败"
        df = reader.parse_to_df(dat, fmt="dat", header="zh")
        assert len(df) > 4000  # 应包含数千只股票
        assert "report_date" in df.columns
        assert "基本每股收益" in df.columns
        assert "资产总计" in df.columns

    def test_parse_bytes_directly(self, tdx):
        """bytes 输入直接解析（不走文件路径）"""
        reader = GpcwReader()
        dat = tdx.stock_report_file("tdxfin/gpcw20251231.dat")
        data = reader.parse(dat, fmt="dat")
        assert len(data) > 4000
        # 每条记录格式: (code, report_date, ...fields...)
        assert isinstance(data[0][0], str)  # code
        assert isinstance(data[0][1], int)  # report_date

    def test_empty_report_package(self, tdx):
        """空财报包（只有 header 无股票数据）能正常处理"""
        reader = GpcwReader()
        # gpcw20260930 等未来/空包只有 20 字节 header
        dat = tdx.stock_report_file("tdxfin/gpcw20260930.dat")
        if len(dat) <= 20:
            df = reader.parse_to_df(dat, fmt="dat", header="zh")
            assert df.empty

    def test_zh_header_matches_columns(self, tdx):
        """中文列名应与 GCW_COLUMNS 对齐"""
        reader = GpcwReader()
        dat = tdx.stock_report_file("tdxfin/gpcw20251231.dat")
        data = reader.parse(dat, fmt="dat")
        df = reader.to_df(data, header="zh")
        # 列数 = GCW_COLUMNS 的前 N 个 + 可能溢出
        assert list(df.columns[: len(GCW_COLUMNS)]) == GCW_COLUMNS[:df.shape[1]] if df.shape[1] <= len(GCW_COLUMNS) else GCW_COLUMNS
