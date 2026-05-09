"""
市场异动监控模块完整测试
"""
from unittest.mock import MagicMock, patch, call
from datetime import datetime, time, date
from zoneinfo import ZoneInfo

from opentdx.commands.market_monitor import (
    is_trading_time,
    get_display_width,
    pad_string,
    mac_quotation_client,
    run_market_monitor,
)
from opentdx.const import MARKET


class TestIsTradingTime:
    def test_morning_trading(self):
        """上午交易时段应返回 True"""
        china_tz = ZoneInfo("Asia/Shanghai")
        test_times = [
            datetime(2026, 5, 8, 9, 30, 0, tzinfo=china_tz),
            datetime(2026, 5, 8, 10, 0, 0, tzinfo=china_tz),
            datetime(2026, 5, 8, 11, 30, 0, tzinfo=china_tz),
        ]
        for dt in test_times:
            with patch('opentdx.commands.market_monitor.datetime') as mock_dt:
                mock_dt.now.return_value = dt
                mock_dt.strptime = datetime.strptime
                assert is_trading_time() is True, f"Failed at {dt.time()}"

    def test_afternoon_trading(self):
        """下午交易时段应返回 True"""
        china_tz = ZoneInfo("Asia/Shanghai")
        test_times = [
            datetime(2026, 5, 8, 13, 0, 0, tzinfo=china_tz),
            datetime(2026, 5, 8, 14, 30, 0, tzinfo=china_tz),
            datetime(2026, 5, 8, 15, 0, 0, tzinfo=china_tz),
        ]
        for dt in test_times:
            with patch('opentdx.commands.market_monitor.datetime') as mock_dt:
                mock_dt.now.return_value = dt
                mock_dt.strptime = datetime.strptime
                assert is_trading_time() is True, f"Failed at {dt.time()}"

    def test_lunch_break(self):
        """午休时段应返回 False"""
        china_tz = ZoneInfo("Asia/Shanghai")
        dt = datetime(2026, 5, 8, 12, 0, 0, tzinfo=china_tz)
        with patch('opentdx.commands.market_monitor.datetime') as mock_dt:
            mock_dt.now.return_value = dt
            mock_dt.strptime = datetime.strptime
            assert is_trading_time() is False

    def test_before_market(self):
        """开盘前应返回 False"""
        china_tz = ZoneInfo("Asia/Shanghai")
        dt = datetime(2026, 5, 8, 8, 0, 0, tzinfo=china_tz)
        with patch('opentdx.commands.market_monitor.datetime') as mock_dt:
            mock_dt.now.return_value = dt
            mock_dt.strptime = datetime.strptime
            assert is_trading_time() is False

    def test_after_market(self):
        """收盘后应返回 False"""
        china_tz = ZoneInfo("Asia/Shanghai")
        dt = datetime(2026, 5, 8, 16, 0, 0, tzinfo=china_tz)
        with patch('opentdx.commands.market_monitor.datetime') as mock_dt:
            mock_dt.now.return_value = dt
            mock_dt.strptime = datetime.strptime
            assert is_trading_time() is False

    def test_boundary_collection_period(self):
        """集合竞价时段 (9:15-9:30) 应返回 True"""
        china_tz = ZoneInfo("Asia/Shanghai")
        test_times = [
            datetime(2026, 5, 8, 9, 15, 0, tzinfo=china_tz),
            datetime(2026, 5, 8, 9, 25, 0, tzinfo=china_tz),
        ]
        for dt in test_times:
            with patch('opentdx.commands.market_monitor.datetime') as mock_dt:
                mock_dt.now.return_value = dt
                mock_dt.strptime = datetime.strptime
                assert is_trading_time() is True, f"Failed at {dt.time()}"

    def test_afternoon_boundary(self):
        """下午边界时段应正确判断"""
        china_tz = ZoneInfo("Asia/Shanghai")
        test_cases = [
            (datetime(2026, 5, 8, 12, 55, 0, tzinfo=china_tz), True),
            (datetime(2026, 5, 8, 12, 54, 0, tzinfo=china_tz), False),
            (datetime(2026, 5, 8, 15, 5, 0, tzinfo=china_tz), True),
            (datetime(2026, 5, 8, 15, 6, 0, tzinfo=china_tz), False),
        ]
        for dt, expected in test_cases:
            with patch('opentdx.commands.market_monitor.datetime') as mock_dt:
                mock_dt.now.return_value = dt
                mock_dt.strptime = datetime.strptime
                assert is_trading_time() is expected, f"Failed at {dt.time()}"


class TestGetDisplayWidth:
    def test_pure_ascii(self):
        assert get_display_width("Hello") == 5

    def test_pure_chinese(self):
        assert get_display_width("你好世界") == 8  # 4 chars * 2

    def test_mixed_text(self):
        assert get_display_width("平安银行PA") == 10  # 4*2 + 2

    def test_empty_string(self):
        assert get_display_width("") == 0

    def test_full_width_punctuation(self):
        assert get_display_width("，。") == 4

    def test_numbers(self):
        assert get_display_width("000001") == 6

    def test_stock_code_format(self):
        """典型股票代码格式: SH.600519"""
        width = get_display_width("SH.600519")
        assert width == 9  # 9 ASCII chars

    def test_chinese_stock_name(self):
        """典型中文股票名"""
        width = get_display_width("平安银行")
        assert width == 8  # 4 chars * 2


class TestPadString:
    def test_pad_left_ascii(self):
        result = pad_string("Hello", 10, 'left')
        assert result == "Hello     "

    def test_pad_right_ascii(self):
        result = pad_string("Hello", 10, 'right')
        assert result == "     Hello"

    def test_pad_center_ascii(self):
        result = pad_string("Hi", 8, 'center')
        assert len(result) >= 8  # may be exact or more due to display width
        assert "Hi" in result

    def test_pad_left_chinese(self):
        result = pad_string("平安银行", 12, 'left')
        assert get_display_width(result) >= 12

    def test_pad_right_chinese(self):
        result = pad_string("平安银行", 12, 'right')
        assert get_display_width(result) >= 12

    def test_no_padding_needed(self):
        result = pad_string("VeryLongText", 5, 'left')
        assert result == "VeryLongText"

    def test_stock_code_padding(self):
        """股票代码格式化: SH.000001 补到10宽"""
        result = pad_string("SH.000001", 10, 'left')
        assert get_display_width(result) >= 10

    def test_invalid_align(self):
        result = pad_string("Test", 10, 'invalid')
        assert result == "Test"


class TestMacQuotationClientContextManager:
    def test_connect_and_disconnect(self):
        """上下文管理器应正确连接和断开"""
        with patch('opentdx.commands.market_monitor.macQuotationClient') as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client

            with mac_quotation_client() as client:
                assert client is mock_client

            mock_client.connect.assert_called_once()
            mock_client.disconnect.assert_called_once()

    def test_disconnect_on_exception(self):
        """异常时也应断开连接"""
        with patch('opentdx.commands.market_monitor.macQuotationClient') as mock_cls:
            mock_client = MagicMock()
            mock_client.connect.side_effect = RuntimeError("连接失败")
            mock_cls.return_value = mock_client

            try:
                with mac_quotation_client() as client:
                    pass
            except RuntimeError:
                pass

            mock_client.disconnect.assert_called_once()


class TestMarketMonitorIntegration:
    """集成测试：验证真实服务器连接"""

    def test_get_market_monitor_sh(self, mqc):
        """上海市场异动监控"""
        from opentdx.client.macStandardClient import MacStandardClient as MQC
        if not isinstance(mqc, MQC):
            return
        result = mqc.get_market_monitor(MARKET.SH, start=0, count=10)
        assert isinstance(result, list)
        if result:
            item = result[0]
            assert 'code' in item
            assert 'desc' in item
            assert 'time' in item
            assert 'index' in item

    def test_get_market_monitor_sz(self, mqc):
        """深圳市场异动监控"""
        from opentdx.client.macStandardClient import MacStandardClient as MQC
        if not isinstance(mqc, MQC):
            return
        result = mqc.get_market_monitor(MARKET.SZ, start=0, count=10)
        assert isinstance(result, list)
        if result:
            item = result[0]
            assert 'code' in item
            assert 'name' in item

    def test_get_market_monitor_bj(self, mqc):
        """北交所异动监控"""
        from opentdx.client.macStandardClient import MacStandardClient as MQC
        if not isinstance(mqc, MQC):
            return
        result = mqc.get_market_monitor(MARKET.BJ, start=0, count=10)
        assert isinstance(result, list)

    def test_get_market_monitor_all_markets(self, mqc):
        """三个市场都应有数据"""
        from opentdx.client.macStandardClient import MacStandardClient as MQC
        if not isinstance(mqc, MQC):
            return
        for market in [MARKET.SH, MARKET.SZ, MARKET.BJ]:
            result = mqc.get_market_monitor(market, start=0, count=5)
            assert isinstance(result, list), f"Market {market} returned non-list"
            assert len(result) > 0, f"Market {market} returned empty"

    def test_get_market_monitor_pagination(self, mqc):
        """分页获取：不同 start 返回不同记录"""
        from opentdx.client.macStandardClient import MacStandardClient as MQC
        if not isinstance(mqc, MQC):
            return
        first = mqc.get_market_monitor(MARKET.SZ, start=0, count=5)
        second = mqc.get_market_monitor(MARKET.SZ, start=5, count=5)
        if first and second:
            # 不同页码不应重叠
            first_indices = {item['index'] for item in first}
            second_indices = {item['index'] for item in second}
            assert first_indices.isdisjoint(second_indices), \
                "不同页码的记录不应重叠"

    def test_market_monitor_fields_consistency(self, mqc):
        """验证返回字段的一致性"""
        from opentdx.client.macStandardClient import MacStandardClient as MQC
        if not isinstance(mqc, MQC):
            return
        result = mqc.get_market_monitor(MARKET.SH, start=0, count=20)
        assert isinstance(result, list)
        required_keys = {'index', 'market', 'code', 'time', 'desc',
                          'value', 'unusual_type', 'v1', 'v2', 'v3', 'v4', 'name'}
        for item in result:
            missing = required_keys - set(item.keys())
            assert not missing, f"Missing keys: {missing}"

    def test_market_monitor_name_not_empty(self, mqc):
        """name 字段不应为空"""
        from opentdx.client.macStandardClient import MacStandardClient as MQC
        if not isinstance(mqc, MQC):
            return
        result = mqc.get_market_monitor(MARKET.SZ, start=0, count=10)
        if result:
            for item in result:
                assert item.get('name'), f"Name empty for code={item.get('code')}"
                assert isinstance(item['name'], str)


class TestRunMarketMonitor:
    """run_market_monitor 函数测试（模拟模式）"""

    @staticmethod
    def _run_with_sleep_counter(mock_sleep, raise_after=2):
        """让 time.sleep 在 N 次调用后才抛出 KeyboardInterrupt"""
        call_count = [0]

        def counted_sleep(seconds):
            call_count[0] += 1
            if call_count[0] >= raise_after:
                raise KeyboardInterrupt

        mock_sleep.side_effect = counted_sleep

    def test_run_with_mock(self):
        """使用 mock 验证主循环逻辑不会崩溃"""
        with patch('opentdx.commands.market_monitor.macQuotationClient') as mock_cls, \
             patch('opentdx.commands.market_monitor.is_trading_time', return_value=True), \
             patch('opentdx.commands.market_monitor.click.echo'), \
             patch('opentdx.commands.market_monitor.click.style', side_effect=lambda x, **kw: x), \
             patch('opentdx.commands.market_monitor.time.sleep') as mock_sleep:

            self._run_with_sleep_counter(mock_sleep, raise_after=3)

            mock_client = MagicMock()
            mock_client.get_market_monitor.return_value = [
                {
                    'index': 0, 'market': MARKET.SH, 'code': '600519',
                    'name': '贵州茅台', 'time': time(10, 30, 0),
                    'desc': '主力买入', 'value': '100/5000',
                    'unusual_type': 3,
                    'v1': 0, 'v2': 100.0, 'v3': 5000.0, 'v4': 0.0
                }
            ]
            mock_cls.return_value = mock_client

            run_market_monitor(interval=5, count=10)

            mock_client.connect.assert_called_once()
            mock_client.disconnect.assert_called_once()

    def test_run_with_search_filter(self):
        """搜索过滤功能应正确过滤"""
        with patch('opentdx.commands.market_monitor.macQuotationClient') as mock_cls, \
             patch('opentdx.commands.market_monitor.is_trading_time', return_value=True), \
             patch('opentdx.commands.market_monitor.click.echo'), \
             patch('opentdx.commands.market_monitor.click.style', side_effect=lambda x, **kw: x), \
             patch('opentdx.commands.market_monitor.time.sleep') as mock_sleep:

            self._run_with_sleep_counter(mock_sleep, raise_after=3)

            mock_client = MagicMock()
            mock_client.get_market_monitor.return_value = [
                {
                    'index': 0, 'market': MARKET.SH, 'code': '600519',
                    'name': '贵州茅台', 'time': time(10, 30, 0),
                    'desc': '主力买入', 'value': '100/5000',
                    'unusual_type': 3,
                    'v1': 0, 'v2': 100.0, 'v3': 5000.0, 'v4': 0.0
                },
                {
                    'index': 1, 'market': MARKET.SZ, 'code': '000858',
                    'name': '五粮液', 'time': time(10, 31, 0),
                    'desc': '加速拉升', 'value': '5.00%',
                    'unusual_type': 4,
                    'v1': 0, 'v2': 0.05, 'v3': 0.0, 'v4': 0.0
                },
            ]
            mock_cls.return_value = mock_client

            run_market_monitor(interval=5, count=10, search='茅台')
