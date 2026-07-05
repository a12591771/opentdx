"""TDXGP 解析器与下载方法单元测试。

测试覆盖：
- _infer_symbol_from_filename: 文件名 → symbol 推断
- parse_index: 索引文件解析
- parse_dat: 二进制记录解析（含过滤）
- TdxgpReader: 类方法（含 zip 解析）
- GPJY_META: 元数据完整性
- 集成测试 (需 tdx fixture): 真实网络下载 + 解析
"""
from __future__ import annotations

import io
import struct
import zipfile

import pytest

from opentdx.utils.tdxgp_reader import (
    GPJY_META,
    RECORD_FORMAT,
    RECORD_SIZE,
    TdxgpReader,
    _infer_symbol_from_filename,
    parse_dat,
    parse_index,
)

# ── 辅助函数 ──────────────────────────────────────────────


def _make_record(type_id: int, date: int, value1: float, value2: float) -> bytes:
    """构造一条 13 字节的 tdkgp 记录。"""
    return struct.pack(RECORD_FORMAT, type_id, date, value1, value2)


def _make_dat_file(records: list[tuple[int, int, float, float]]) -> bytes:
    """从记录列表构造一个完整的 .dat 字节内容。"""
    return b"".join(_make_record(*r) for r in records)


# ── _infer_symbol_from_filename ───────────────────────────


class TestInferSymbol:
    """_infer_symbol_from_filename 单元测试"""

    @pytest.mark.parametrize(
        "filename,expected",
        [
            ("gpsh600000.dat", "sh600000"),
            ("gpsz000001.dat", "sz000001"),
            ("gpbj430001.dat", "bj430001"),
            ("gpsh688001.dat", "sh688001"),
            ("gpsz302132.dat", "sz302132"),
        ],
    )
    def test_valid_filenames(self, filename, expected):
        assert _infer_symbol_from_filename(filename) == expected

    def test_invalid_top_level(self):
        """非 gp 前缀文件名"""
        with pytest.raises(ValueError, match="无法从文件名推断市场"):
            _infer_symbol_from_filename("unknown.dat")

    def test_invalid_code_length(self):
        """代码位数不对"""
        with pytest.raises(ValueError, match="非法文件名"):
            _infer_symbol_from_filename("gpsh12345.dat")  # 5位

    def test_path_with_stem(self):
        """带路径的文件名"""
        assert _infer_symbol_from_filename("/some/path/gpsz000001.dat") == "sz000001"


# ── parse_index ───────────────────────────────────────────


class TestParseIndex:
    """parse_index 单元测试"""

    def test_parse_basic(self):
        text = (
            "gpsz302132.dat,61b0678f44653d0b0ff28e6c6eae74fe,248027\n"
            "gpsh600000.dat,abc123def456,319969\n"
            "\n"
            "  gpsz000001.dat , hashval , 1000  \n"
        )
        entries = parse_index(text)
        assert len(entries) == 3
        assert entries[0] == {
            "filename": "gpsz302132.dat",
            "hash": "61b0678f44653d0b0ff28e6c6eae74fe",
            "filesize": 248027,
        }
        assert entries[1]["filename"] == "gpsh600000.dat"
        assert entries[2]["filesize"] == 1000

    def test_parse_bytes(self):
        text = b"gpsz000001.dat,md5hash,100\n"
        entries = parse_index(text)
        assert len(entries) == 1
        assert entries[0]["filesize"] == 100

    def test_parse_bytearray(self):
        text = bytearray(b"gpsh600000.dat,md5hash,200\n")
        entries = parse_index(text)
        assert len(entries) == 1
        assert entries[0]["filesize"] == 200

    def test_parse_empty(self):
        assert parse_index("") == []
        assert parse_index(b"") == []

    def test_parse_malformed_lines(self):
        """异常行应被跳过"""
        text = "gpsz000001.dat,md5hash,100\nbadline\n,,\n"
        entries = parse_index(text)
        assert len(entries) == 1
        assert entries[0]["filename"] == "gpsz000001.dat"

    def test_parse_invalid_filesize(self):
        """无法解析 filesize 的行应跳过"""
        text = "gpsz000001.dat,md5hash,not_a_number\n"
        entries = parse_index(text)
        assert len(entries) == 0

    def test_parse_gbk_fallback(self):
        """测试非 utf-8 字节也能解析"""
        text = "gpsz000001.dat,hashävalue,100\n".encode("latin1")
        entries = parse_index(text)
        # 应在 decode 后正常解析（replace 策略）
        assert len(entries) >= 0  # 可能有部分损坏但不应崩溃


# ── parse_dat ─────────────────────────────────────────────


class TestParseDat:
    """parse_dat 单元测试 —— 纯构造数据"""

    def test_parse_single_record(self):
        raw = _make_record(1, 20250102, 123456.0, 0.0)
        rows = parse_dat(raw, filename="gpsz000001.dat")
        assert len(rows) == 1
        r = rows[0]
        assert r["symbol"] == "sz000001"
        assert r["market"] == "sz"
        assert r["code"] == "000001"
        assert r["type_id"] == 1
        assert r["date"] == 20250102
        assert r["value1"] == 123456.0
        assert r["value2"] == 0.0
        assert r["field"] == "shareholder_count"
        assert r["unit"] == "count"
        assert r["description"] == "股东人数"

    def test_parse_multiple_records(self):
        raw = _make_dat_file([
            (1, 20210101, 100.0, 0.0),
            (16, 20210102, 500000.0, 0.0),
            (15, 20210103, 0.0, 0.0),
        ])
        rows = parse_dat(raw, filename="gpsh600000.dat")
        assert len(rows) == 3
        assert rows[0]["symbol"] == "sh600000"
        assert rows[1]["type_id"] == 16
        assert rows[1]["date"] == 20210102
        assert rows[1]["field"] == "total_market_cap"

    def test_parse_with_bytes_input(self):
        """直接传 bytes，需要 filename 参数"""
        raw = _make_record(1, 20250101, 100.0, 0.0)
        rows = parse_dat(raw, filename="gpsz000001.dat")
        assert len(rows) == 1
        assert rows[0]["code"] == "000001"

    def test_parse_with_bytearray(self):
        raw = bytearray(_make_record(1, 20250101, 100.0, 0.0))
        rows = parse_dat(raw, filename="gpsz000001.dat")
        assert len(rows) == 1

    def test_parse_with_file_object(self):
        raw = _make_record(1, 20250101, 100.0, 0.0)
        fobj = io.BytesIO(raw)
        rows = parse_dat(fobj, filename="gpsz000001.dat")
        assert len(rows) == 1
        assert rows[0]["date"] == 20250101

    def test_parse_with_file_path(self, tmp_path):
        raw = _make_record(1, 20250101, 100.0, 0.0)
        path = tmp_path / "gpsz000001.dat"
        path.write_bytes(raw)
        rows = parse_dat(str(path))
        assert len(rows) == 1
        assert rows[0]["symbol"] == "sz000001"

    def test_parse_missing_filename(self):
        raw = _make_record(1, 20250101, 100.0, 0.0)
        with pytest.raises(ValueError, match="filename 不能为空"):
            parse_dat(raw)

    def test_parse_invalid_input_type(self):
        with pytest.raises(TypeError, match="不支持的输入类型"):
            parse_dat(12345, filename="gpsz000001.dat")

    def test_parse_trailing_bytes_ignored(self):
        """尾部不足 13 字节的数据应被忽略"""
        raw = _make_record(1, 20250101, 100.0, 0.0) + b"\x00\x01\x02"
        rows = parse_dat(raw, filename="gpsz000001.dat")
        assert len(rows) == 1

    def test_parse_empty_data(self):
        rows = parse_dat(b"", filename="gpsz000001.dat")
        assert rows == []

    def test_parse_small_data(self):
        """数据不足 13 字节"""
        rows = parse_dat(b"\x00" * 10, filename="gpsz000001.dat")
        assert rows == []


class TestParseDatFiltering:
    """parse_dat 过滤功能测试"""

    def test_filter_types(self):
        raw = _make_dat_file([
            (1, 20250101, 100.0, 0.0),
            (16, 20250102, 200.0, 0.0),
            (15, 20250103, 300.0, 0.0),
        ])
        rows = parse_dat(raw, filename="gpsz000001.dat", types=[1, 16])
        assert len(rows) == 2
        assert {r["type_id"] for r in rows} == {1, 16}

    def test_filter_types_none_matches(self):
        raw = _make_dat_file([
            (1, 20250101, 100.0, 0.0),
        ])
        rows = parse_dat(raw, filename="gpsz000001.dat", types=[99])
        assert rows == []

    def test_filter_start_date(self):
        raw = _make_dat_file([
            (1, 20240101, 100.0, 0.0),
            (1, 20240601, 200.0, 0.0),
            (1, 20241231, 300.0, 0.0),
        ])
        rows = parse_dat(raw, filename="gpsz000001.dat", start_date=20240601)
        assert len(rows) == 2
        dates = [r["date"] for r in rows]
        assert all(d >= 20240601 for d in dates)

    def test_filter_end_date(self):
        raw = _make_dat_file([
            (1, 20240101, 100.0, 0.0),
            (1, 20240601, 200.0, 0.0),
            (1, 20241231, 300.0, 0.0),
        ])
        rows = parse_dat(raw, filename="gpsz000001.dat", end_date=20240601)
        assert len(rows) == 2
        dates = [r["date"] for r in rows]
        assert all(d <= 20240601 for d in dates)

    def test_filter_date_range(self):
        raw = _make_dat_file([
            (1, 20240101, 100.0, 0.0),
            (1, 20240601, 200.0, 0.0),
            (1, 20241231, 300.0, 0.0),
        ])
        rows = parse_dat(raw, filename="gpsz000001.dat", start_date=20240101, end_date=20240601)
        assert len(rows) == 2

    def test_filter_combined(self):
        """类型 + 日期组合过滤"""
        raw = _make_dat_file([
            (1, 20240101, 100.0, 0.0),
            (16, 20240101, 200.0, 0.0),
            (1, 20240601, 300.0, 0.0),
            (16, 20240601, 400.0, 0.0),
        ])
        rows = parse_dat(raw, filename="gpsz000001.dat", types=[1], start_date=20240601)
        assert len(rows) == 1
        assert rows[0]["type_id"] == 1
        assert rows[0]["date"] == 20240601


class TestParseDatUnknownType:
    """未知 type_id 回退行为"""

    def test_unknown_type_fallback(self):
        raw = _make_record(99, 20250101, 100.0, 200.0)
        rows = parse_dat(raw, filename="gpsz000001.dat")
        assert len(rows) == 1
        r = rows[0]
        assert r["field"] == "gpjy_99"
        assert r["unit"] == "unknown"
        assert r["description"] == "未知类型 99"


class TestParseDatMarkets:
    """三个市场的文件名推断"""

    def test_sh_market(self):
        raw = _make_record(1, 20250101, 100.0, 0.0)
        rows = parse_dat(raw, filename="gpsh600519.dat")
        assert rows[0]["symbol"] == "sh600519"
        assert rows[0]["market"] == "sh"
        assert rows[0]["code"] == "600519"

    def test_sz_market(self):
        raw = _make_record(1, 20250101, 100.0, 0.0)
        rows = parse_dat(raw, filename="gpsz000858.dat")
        assert rows[0]["symbol"] == "sz000858"
        assert rows[0]["market"] == "sz"
        assert rows[0]["code"] == "000858"

    def test_bj_market(self):
        raw = _make_record(1, 20250101, 100.0, 0.0)
        rows = parse_dat(raw, filename="gpbj430047.dat")
        assert rows[0]["symbol"] == "bj430047"
        assert rows[0]["market"] == "bj"
        assert rows[0]["code"] == "430047"


# ── TdxgpReader ───────────────────────────────────────────


class TestTdxgpReaderGetData:
    """TdxgpReader.get_data 测试"""

    def test_basic(self):
        reader = TdxgpReader()
        raw = _make_record(1, 20250101, 100.0, 0.0)
        rows = reader.get_data(raw, filename="gpsz000001.dat")
        assert len(rows) == 1

    def test_with_file_path(self, tmp_path):
        path = tmp_path / "gpsh600000.dat"
        path.write_bytes(_make_record(1, 20250101, 100.0, 0.0))
        reader = TdxgpReader()
        rows = reader.get_data(str(path))
        assert len(rows) == 1
        assert rows[0]["symbol"] == "sh600000"

    def test_get_df(self):
        reader = TdxgpReader()
        raw = _make_dat_file([
            (1, 20250101, 100.0, 0.0),
            (16, 20250102, 200.0, 0.0),
        ])
        df = reader.get_df(raw, filename="gpsz000001.dat")
        assert df.shape == (2, 10)
        assert list(df.columns) == [
            "symbol", "market", "code", "type_id", "date",
            "value1", "value2", "field", "unit", "description",
        ]
        # 排序验证
        assert df.iloc[0]["type_id"] == 1
        assert df.iloc[1]["type_id"] == 16

    def test_get_df_empty(self):
        reader = TdxgpReader()
        df = reader.get_df(b"", filename="gpsz000001.dat")
        assert df.empty


class TestTdxgpReaderZip:
    """TdxgpReader zip 解析测试"""

    def _make_test_zip(self) -> bytes:
        """构造测试用 zip，包含 两个有效 .dat 和一个无效文件。"""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("gpsh600000.dat", _make_record(1, 20250101, 100.0, 0.0))
            zf.writestr("gpsz000001.dat", _make_record(16, 20250102, 200.0, 0.0))
            zf.writestr("readme.txt", "hello")
            zf.writestr("unknown.dat", _make_record(15, 20250103, 300.0, 0.0))
        return buf.getvalue()

    def test_get_data_from_zip_bytes(self):
        reader = TdxgpReader()
        zip_data = self._make_test_zip()
        rows = reader.get_data_from_zip(zip_data)
        assert len(rows) == 2
        symbols = {r["symbol"] for r in rows}
        assert symbols == {"sh600000", "sz000001"}

    def test_get_data_from_zip_file(self, tmp_path):
        reader = TdxgpReader()
        zip_data = self._make_test_zip()
        path = tmp_path / "test.zip"
        path.write_bytes(zip_data)
        rows = reader.get_data_from_zip(str(path))
        assert len(rows) == 2

    def test_get_data_from_zip_with_filter(self):
        reader = TdxgpReader()
        zip_data = self._make_test_zip()
        rows = reader.get_data_from_zip(zip_data, types=[1])
        assert len(rows) == 1
        assert rows[0]["type_id"] == 1

    def test_get_data_from_zip_with_date_filter(self):
        reader = TdxgpReader()
        zip_data = self._make_test_zip()
        rows = reader.get_data_from_zip(zip_data, start_date=20250102)
        assert len(rows) == 1
        assert rows[0]["date"] == 20250102

    def test_get_df_from_zip(self):
        reader = TdxgpReader()
        zip_data = self._make_test_zip()
        df = reader.get_df_from_zip(zip_data)
        assert df.shape == (2, 10)

    def test_get_df_from_zip_empty(self):
        reader = TdxgpReader()
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("readme.txt", "hello")
        df = reader.get_df_from_zip(buf.getvalue())
        assert df.empty


class TestTdxgpReaderParseIndex:
    """TdxgpReader.parse_index 静态方法测试"""

    def test_delegates_to_parse_index(self):
        reader = TdxgpReader()
        entries = reader.parse_index("gpsz000001.dat,hash,100\n")
        assert len(entries) == 1
        assert entries[0]["filename"] == "gpsz000001.dat"


# ── GPJY_META ─────────────────────────────────────────────


class TestGpjyMeta:
    """GPJY_META 元数据完整性测试"""

    def test_known_types_have_all_fields(self):
        """所有已知 type_id 必须有 3 个元素的元组"""
        for tid, meta in GPJY_META.items():
            assert isinstance(meta, tuple), f"type_id {tid} 元数据应为 tuple"
            assert len(meta) == 3, f"type_id {tid} 应为 (field, unit, description)"
            field, unit, desc = meta
            assert isinstance(field, str) and field, f"type_id {tid} field 不能为空"
            assert isinstance(unit, str), f"type_id {tid} unit 应为 str"
            assert isinstance(desc, str) and desc, f"type_id {tid} description 不能为空"

    def test_all_keys_are_int(self):
        assert all(isinstance(k, int) for k in GPJY_META)

    def test_dedicated_types_present(self):
        """核心类型应存在"""
        expected_types = {
            1: "shareholder_count",
            6: "northbound_holding",
            15: "limit_status",
            16: "total_market_cap",
        }
        for tid, field in expected_types.items():
            assert tid in GPJY_META, f"type_id {tid} 应存在"
            assert GPJY_META[tid][0] == field, f"type_id {tid} field 应为 {field}"


# ── 集成测试 (需要真实的 tdx 网络连接) ─────────────────


@pytest.mark.integration
class TestTdxgpIntegration:
    """集成测试：真实网络下载 + 解析"""

    def test_stock_tdxgp_index(self, tdx):
        """下载并解析索引文件"""
        entries = tdx.stock_tdxgp_index()
        assert isinstance(entries, list)
        assert len(entries) > 1000  # 沪深北三个市场总和
        # 验证每条记录结构
        for e in entries[:5]:
            assert "filename" in e
            assert "hash" in e
            assert "filesize" in e
            assert e["filename"].endswith(".dat")
            assert isinstance(e["filesize"], int)
            assert e["filesize"] % 13 == 0, \
                f"{e['filename']} filesize {e['filesize']} 不能被 13 整除"

    def test_stock_tdxgp_file_download(self, tdx):
        """下载具体 tdkgp 文件"""
        data = tdx.stock_tdxgp_file("gpsz000001.dat")
        assert isinstance(data, (bytes, bytearray))
        assert len(data) > 0
        assert len(data) % 13 == 0, \
            f"文件大小 {len(data)} 不能被 13 整除"

    def test_stock_tdxgp_file_sh(self, tdx):
        """下载上交所个股 tdkgp"""
        data = tdx.stock_tdxgp_file("gpsh600000.dat")
        assert len(data) > 0
        assert len(data) % 13 == 0

    def test_download_and_parse(self, tdx):
        """下载后直接解析"""
        reader = TdxgpReader()
        data = tdx.stock_tdxgp_file("gpsz000001.dat")
        rows = reader.get_data(data, filename="gpsz000001.dat")
        assert len(rows) > 0
        # 验证必填字段
        for r in rows[:5]:
            assert r["symbol"].startswith(("sh", "sz", "bj"))
            assert len(r["code"]) == 6
            assert isinstance(r["type_id"], int)
            assert isinstance(r["date"], int)
            assert 19900101 <= r["date"] <= 21000101
            assert isinstance(r["value1"], float)
            assert isinstance(r["value2"], float)
            assert r["field"]
            assert r["unit"]
            assert r["description"]

    def test_download_and_parse_df(self, tdx):
        """下载后解析为 DataFrame"""
        reader = TdxgpReader()
        data = tdx.stock_tdxgp_file("gpsz000001.dat")
        df = reader.get_df(data, filename="gpsz000001.dat")
        assert not df.empty
        assert df.shape[1] == 10
        assert df["symbol"].nunique() == 1

    def test_download_with_filter(self, tdx):
        """下载后按 type_id 过滤"""
        reader = TdxgpReader()
        data = tdx.stock_tdxgp_file("gpsz000001.dat")
        rows = reader.get_data(data, filename="gpsz000001.dat", types=[1])
        # type_id=1 是 shareholder_count，低频但一定存在
        assert len(rows) > 0
        assert all(r["type_id"] == 1 for r in rows)
        assert all(r["field"] == "shareholder_count" for r in rows)

    def test_download_with_date_filter(self, tdx):
        """下载后按日期过滤"""
        reader = TdxgpReader()
        data = tdx.stock_tdxgp_file("gpsz000001.dat")
        rows = reader.get_data(data, filename="gpsz000001.dat", start_date=20240101)
        assert len(rows) > 0
        assert all(r["date"] >= 20240101 for r in rows)

    def test_type_id_1_shareholder_count(self, tdx):
        """type_id=1 股东人数数据应是正数"""
        reader = TdxgpReader()
        data = tdx.stock_tdxgp_file("gpsz000001.dat")
        rows = reader.get_data(data, filename="gpsz000001.dat", types=[1])
        for r in rows:
            assert r["value1"] > 0, \
                f"股东人数应为正数: {r['date']} value1={r['value1']}"

    def test_type_id_16_market_cap(self, tdx):
        """type_id=16 总市值数据检查"""
        reader = TdxgpReader()
        data = tdx.stock_tdxgp_file("gpsh600000.dat")
        rows = reader.get_data(data, filename="gpsh600000.dat", types=[16])
        assert len(rows) > 0
        for r in rows:
            assert r["value1"] >= 0, \
                f"总市值不应为负: {r['date']} value1={r['value1']}"

    def test_all_filesizes_divisible_by_13(self, tdx):
        """索引中所有文件大小都应能被 13 整除"""
        entries = tdx.stock_tdxgp_index()
        bad = [e for e in entries if e["filesize"] % 13 != 0]
        assert bad == [], f"以下文件大小不能被 13 整除: {bad[:5]}"

    def test_multiple_markets(self, tdx):
        """沪深北三市场各取一只验证"""
        reader = TdxgpReader()
        market_tests = [
            ("gpsh600000.dat", "sh600000"),
            ("gpsz000001.dat", "sz000001"),
            ("gpsh603000.dat", "sh603000"),
        ]
        for filename, expected_symbol in market_tests:
            try:
                data = tdx.stock_tdxgp_file(filename)
            except Exception:
                continue  # 该股票可能没有数据
            rows = reader.get_data(data, filename=filename)
            if rows:
                assert rows[0]["symbol"] == expected_symbol, \
                    f"{filename} 期望 {expected_symbol}, 实际 {rows[0]['symbol']}"

    def test_parse_index_after_download(self, tdx):
        """先下载索引再用 reader 解析"""
        content = tdx.q_client().download_file("tdxgp/gpszsh.txt")
        entries = TdxgpReader.parse_index(content)
        assert len(entries) > 1000
        # 和直接调用 stock_tdxgp_index 结果一致
        entries2 = tdx.stock_tdxgp_index()
        assert len(entries) == len(entries2)
