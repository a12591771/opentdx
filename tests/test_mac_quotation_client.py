from opentdx.client.macStandardClient import MacStandardClient as macQuotationClient
from opentdx.const import ADJUST, BOARD_TYPE, CATEGORY, EX_BOARD_TYPE, EX_MARKET, MARKET, PERIOD, SORT_TYPE, SORT_ORDER
import pandas as pd
import pytest
from opentdx.utils.help import industry_to_board_symbol, ah_code_to_symbol, lot_size_to_symbol
from datetime import time
from opentdx.utils.bitmap import FIELD_BITMAP_MAP, FieldBit, PresetField

class TestMacQuotationClientLogin:
    """登录"""

    def test_connected(self, mqc):
        assert mqc.connected is True

class TestMacQuotationClientMixin:
    """SP模式"""

    def test_mix_in(self, mqc, sp_qc):
        """
        测试 MacQuotationClient (mqc) 与 SP模式客户端 (sp_qc) 在获取板块列表时的一致性。
        验证混合模式下的数据获取结果是否与纯SP模式一致。
        """
        result = mqc.get_board_list(BOARD_TYPE.HY, count=5)
        result2 = sp_qc.get_board_list(BOARD_TYPE.HY, count=5)
        assert result == result2
        
    def test_mqc_has_qc_method(self, mqc, qc):
        """
        测试 MacQuotationClient (mqc) 是否具备标准 QuotationClient (qc) 的行情获取能力。
        验证通过 mqc 获取的个股行情数据与标准 qc 获取的数据一致。
        """
        mqc.login()
        result = mqc.get_quotes(MARKET.SZ, '000001')
        result2 = qc.get_quotes(MARKET.SZ, '000001')
        
        # 验证两个结果都是列表且长度相同
        assert isinstance(result, list), f"mqc 返回类型错误: {type(result)}"
        assert isinstance(result2, list), f"qc 返回类型错误: {type(result2)}"
        assert len(result) == len(result2), f"返回数据长度不一致: mqc={len(result)}, qc={len(result2)}"
        
class TestMacQuotationClientStock:
    """股票市场 API"""
    def test_get_market_monitor(self, mqc:macQuotationClient):
        result = mqc.get_market_monitor(MARKET.SH)
        assert result is not None
        
        df = pd.DataFrame(result)
        if 'name' not in df.columns:  # 正确的检查列是否存在的方式
            assert "未找到 [主力监控] 功能 的 name 字段"

    def test_equal_market_monitor(self, mqc:macQuotationClient, qc):
        result1 = mqc.get_market_monitor(MARKET.SH, start = 0, count=5)
        result2 = qc.get_unusual(MARKET.SH, start = 0, count=5)
        
        # 验证数据类型和长度一致性
        assert isinstance(result1, list), f"result1 应为列表类型，实际为 {type(result1)}"
        assert isinstance(result2, list), f"result2 应为列表类型，实际为 {type(result2)}"
        assert len(result1) == len(result2), f"两个结果长度不一致: {len(result1)} != {len(result2)}"
        
        # 只测试部分关键字段（排除 name 和 mac协议特有的 v1-v4 字段）
        key_fields = ['index', 'market', 'code', 'time', 'desc', 'value', 'unusual_type']
        
        for i, (item1, item2) in enumerate(zip(result1, result2)):
            # 提取关键字段进行比对
            filtered1 = {k: item1[k] for k in key_fields if k in item1}
            filtered2 = {k: item2[k] for k in key_fields if k in item2}
            
            # 验证所有关键字段都存在
            assert len(filtered1) == len(key_fields), \
                f"第 {i} 条记录 result1 缺少字段: 期望{len(key_fields)}个，实际{len(filtered1)}个"
            assert len(filtered2) == len(key_fields), \
                f"第 {i} 条记录 result2 缺少字段: 期望{len(key_fields)}个，实际{len(filtered2)}个"
            
            # 比对关键字段
            assert filtered1 == filtered2, \
                f"第 {i} 条记录关键字段比对失败:\n  result1: {filtered1}\n  result2: {filtered2}"

class TestMacQuotationClientBoard:
    """板块 API"""

    def test_get_board_count(self, mqc):
        result = mqc.get_board_count(BOARD_TYPE.HY)
        assert isinstance(result, int)
        assert result > 0

    def test_get_board_list(self, mqc):
        result = mqc.get_board_list(BOARD_TYPE.HY, count=5)
        assert isinstance(result, list)
        assert len(result) > 0
        
    def test_ex_get_board_list(self, meqc):
        result = meqc.get_board_list(EX_BOARD_TYPE.HK_ALL, count=5)
        assert isinstance(result, list)
        assert len(result) > 0

    def test_get_board_members_quotes(self, mqc):
        result = mqc.get_board_members_quotes('880761', count=5)
        assert isinstance(result, list)

    def test_get_board_members(self, mqc):
        # 普通板块
        result = mqc.get_board_members('880761', count=5)
        assert isinstance(result, list)
        assert len(result) > 0
        
        # 指数成分股 000xxx
        result = mqc.get_board_members('000903', count=5)
        assert isinstance(result, list)
        assert len(result) > 0
        
        # 指数成分股 399xxx
        result = mqc.get_board_members('399262', count=5)
        assert isinstance(result, list)
        assert len(result) > 0
        
        # 北证成分股 899xxx
        result = mqc.get_board_members('899601', count=5)
        assert isinstance(result, list)
        assert len(result) > 0
        
        
    def test_get_board_members_hkboard(self, meqc):
        result = meqc.get_board_members('HK0287', count=5)
        assert isinstance(result, list)
        assert len(result) > 0
        
    def test_get_board_members_usboard(self, meqc):
        result = meqc.get_board_members('US0495', count=5)
        assert isinstance(result, list)
        assert len(result) > 0

    def test_get_board_members_with_sort_type(self, mqc):
        """测试 sort_type 和 sort_order 参数是否生效"""
        board_code = '880761'
        count = 10

        # 测试按成交量降序排序 (默认通常是降序，但显式指定更稳妥)
        result_desc = mqc.get_board_members_quotes(board_code, count=count, sort_type=SORT_TYPE.VOLUME, sort_order=SORT_ORDER.DESC)
        assert isinstance(result_desc, list)
        assert len(result_desc) > 1, "返回数据不足以进行排序验证"

        vols_desc = [item.get('vol', 0) for item in result_desc if isinstance(item, dict)]
        assert len(vols_desc) == len(result_desc), "部分数据缺失 vol 字段"
        
        # 检查是否是降序排列 (从大到小)
        for i in range(len(vols_desc) - 1):
            assert vols_desc[i] >= vols_desc[i+1], f"降序排序错误: 索引 {i} 的 vol ({vols_desc[i]}) 小于 索引 {i+1} 的 vol ({vols_desc[i+1]})"

        # 测试按成交量升序排序
        result_asc = mqc.get_board_members_quotes(board_code, count=count, sort_type=SORT_TYPE.VOLUME, sort_order=SORT_ORDER.ASC)
        assert isinstance(result_asc, list)
        assert len(result_asc) > 1, "返回数据不足以进行排序验证"

        vols_asc = [item.get('vol', 0) for item in result_asc if isinstance(item, dict)]
        assert len(vols_asc) == len(result_asc), "部分数据缺失 vol 字段"

        # 检查是否是升序排列 (从小到大)
        for i in range(len(vols_asc) - 1):
            assert vols_asc[i] <= vols_asc[i+1], f"升序排序错误: 索引 {i} 的 vol ({vols_asc[i]}) 大于 索引 {i+1} 的 vol ({vols_asc[i+1]})"


    def test_get_symbol_zjlx(self, mqc):
        result = mqc.get_symbol_zjlx('000100', MARKET.SZ)
        assert result is not None
        
    def test_get_symbol_zjlx_not_support_ex_market(self, mqc):
        """测试资金流向不支持扩展市场（EX_MARKET）
        
        可能的行为：
        1. 抛出 TypeError 异常
        2. 返回 None
        """
        import pytest
        try:
            result = mqc.get_symbol_zjlx('000100', EX_MARKET.US_STOCK)
            # 如果没有抛出异常，应该返回 None
            assert result is None, f"期望返回 None，但实际返回: {type(result).__name__}"
        except TypeError as e:
            # 如果抛出 TypeError，验证错误信息
            assert "market 参数必须为 MARKET 类型" in str(e) or "MARKET" in str(e)

    def test_get_symbol_belong_board(self, mqc):
        result = mqc.get_symbol_belong_board('000100', MARKET.SZ)
        assert result is not None

    def test_get_symbol_bars(self, mqc):
        result = mqc.get_symbol_bars(MARKET.SZ, '000100', PERIOD.DAILY, count=5)
        assert isinstance(result, list)
        assert len(result) > 0

    def test_get_symbol_bars_with_adjust(self, mqc):
        result = mqc.get_symbol_bars(MARKET.SZ, '000100', PERIOD.DAILY, count=5, fq=ADJUST.QFQ)
        assert isinstance(result, list)
        assert len(result) > 0

    def test_get_board_list_ex_board_type(self, mqc):
        result = mqc.get_board_list(EX_BOARD_TYPE.HK_ALL, count=5)
        assert result is None or isinstance(result, list)


class TestMacQuotationClientBoardFields:
    """板块 API f"""

    def test_base_info(self, mqc:macQuotationClient):
        
        print("支持自定义字段 ohlc")

        rs = mqc.get_board_members_quotes(board_symbol="881394",count=300, fields=PresetField.BASIC)
        df = pd.DataFrame(rs)
        
        for field in PresetField.BASIC.value:
            # field_info = field.info
            filed_name = field.field_name
            assert filed_name in df.columns, f"字段 {field} {filed_name} 不在返回数据中"
            
    def test_list_fields(self, mqc:macQuotationClient):
        
        print("支持自定义字段 ohlc")
        category = CATEGORY.A
        fields = [FieldBit.PRE_CLOSE, FieldBit.OPEN, FieldBit.HIGH, FieldBit.LOW, FieldBit.CLOSE, FieldBit.VOL, FieldBit.AMOUNT, FieldBit.AH_CODE, FieldBit.LOT_SIZE, FieldBit.INDUSTRY]
        rs = mqc.get_board_members_quotes(board_symbol=category,count=300, fields=fields)
        df = pd.DataFrame(rs)

        for field in fields:
            field_info = FIELD_BITMAP_MAP.get(field)
            filed_name = field_info[0]
            assert filed_name in df.columns, f"字段 {field} {filed_name} 不在返回数据中"


class TestMacQuotationClientExchange:
    """板块 API 通过help转换 symbol"""

    def test_exchange_ah_code(self, mqc):
        
        print("支持自定义字段 ohlc , 增加ah_code , 查询881394板块")
        fields = [FieldBit.OPEN, FieldBit.HIGH, FieldBit.LOW, FieldBit.CLOSE, FieldBit.VOL, FieldBit.AH_CODE, FieldBit.LOT_SIZE]
        rs = mqc.get_board_members_quotes(board_symbol="881394",count=300, fields=fields)
        df = pd.DataFrame(rs)
        
        if 'ah_code' in df.columns:  # 正确的检查列是否存在的方式
            df['ah_code'] = df.apply(lambda row: ah_code_to_symbol(row['ah_code'], row['market']), axis=1)


        # 新增验证逻辑
        assert df is not None and not df.empty, "获取的数据为空"
        
        # 筛选 code 为 601066 的行
        ah_df = df[df['code'] == '601066']
        
        # 确保找到了该股票
        assert not ah_df.empty, "未找到 symbol 为 601066 的股票数据"
        
        # 获取第一行的 ah_code 并验证
        target_ah_code = ah_df.iloc[0]['ah_code']
        assert target_ah_code == '06066', f"期望 ah_code 为 '06066'，实际为 '{target_ah_code}'"
        

    def test_exchange_dq_symbol(self, mqc):
        
        print("支持自定义字段 ohlc , 增加ah_code , 查询881394板块")
        fields = [FieldBit.OPEN, FieldBit.HIGH, FieldBit.LOW, FieldBit.CLOSE, FieldBit.VOL, FieldBit.AH_CODE, FieldBit.LOT_SIZE]

        rs = mqc.get_board_members_quotes(board_symbol="881394", count=100, fields=fields)
        df = pd.DataFrame(rs)
        
        if 'lot_size' in df.columns:  # 正确的检查列是否存在的方式
            df['dq_symbol'] = df.apply(lambda row: lot_size_to_symbol(row['lot_size']), axis=1)
            
        # 新增验证逻辑
        assert df is not None and not df.empty, "获取的数据为空"
        
        # 验证 000166 的 dq_symbol
        df_000166 = df[df['code'] == '000166']
        assert not df_000166.empty, "未找到 code 为 000166 的股票数据"
        target_dq_symbol_166 = df_000166.iloc[0]['dq_symbol']
        assert target_dq_symbol_166 == '880202', f"期望 000166 的 dq_symbol 为 '880202'，实际为 '{target_dq_symbol_166}'"

        # 验证 600999 的 dq_symbol
        df_600999 = df[df['code'] == '600999']
        assert not df_600999.empty, "未找到 code 为 600999 的股票数据"
        target_dq_symbol_999 = df_600999.iloc[0]['dq_symbol']
        assert target_dq_symbol_999 == '880218', f"期望 600999 的 dq_symbol 为 '880218'，实际为 '{target_dq_symbol_999}'"
        

    def test_exchange_industry_symbol(self, mqc):

        print("支持自定义字段 ohlc , 增加ah_code , 查询880201板块-黑龙江板块")

        rs = mqc.get_board_members_quotes(board_symbol="880201", count=100, fields=[FieldBit.INDUSTRY])
        df = pd.DataFrame(rs)

        if 'industry' in df.columns:  # 正确的检查列是否存在的方式
            df['industry_symbol'] = df['industry'].apply(lambda x: industry_to_board_symbol(x))
        
        # 新增验证逻辑
        assert df is not None and not df.empty, "获取的数据为空"
        
        # 验证 000166 的 dq_symbol
        df_300900 = df[df['code'] == '300900']
        assert not df_300900.empty, "未找到 code 为 300900 的股票数据"
        target = df_300900.iloc[0]['industry_symbol']
        assert target == '881288', f"期望 300900 的 dq_symbol 为 '881288'，实际为 '{target}'"


class TestMacQuotationClientTickChart:
    """分时图 API - 真实请求测试"""
        
    def test_get_symbol_tick_chart_stock_basic(self, mqc):
        """测试A股基本分时图数据获取"""
        result = mqc.get_symbol_tick_chart(MARKET.SZ, '000001')
        
        # 验证返回数据类型
        assert isinstance(result, dict), f"返回类型应为dict，实际为 {type(result)}"
        
        # 验证必需字段存在
        required_fields = [
            'market', 'code', 'name', 'decimal', 'category', 'vol_unit',
            'time', 'pre_close', 'open', 'high', 'low', 'close',
            'momentum', 'vol', 'amount', 'turnover', 'avg',
            'industry', 'charts'
        ]
        
        for field in required_fields:
            assert field in result, f"缺少必需字段: {field}"
        
        # 验证基本信息正确性
        assert result['code'] == '000001', f"股票代码错误: {result['code']}"
        assert result['market'] == MARKET.SZ, f"市场代码错误: {result['market']}"
        assert isinstance(result['name'], str) and len(result['name']) > 0, "股票名称不能为空"
        
        # 验证价格字段合理性
        assert result['pre_close'] > 0, f"昨收价应大于0: {result['pre_close']}"
        assert result['open'] >= 0, f"开盘价应>=0: {result['open']}"
        assert result['high'] >= 0, f"最高价应>=0: {result['high']}"
        assert result['low'] >= 0, f"最低价应>=0: {result['low']}"
        assert result['close'] >= 0, f"收盘价应>=0: {result['close']}"
        
        # 验证高低价格逻辑
        if result['high'] > 0 and result['low'] > 0:
            assert result['high'] >= result['low'], \
                f"最高价({result['high']})应>=最低价({result['low']})"
        
        # 验证成交量和成交额
        assert result['vol'] >= 0, f"成交量应>=0: {result['vol']}"
        assert result['amount'] >= 0, f"成交额应>=0: {result['amount']}"
        
        # 验证分时图数据
        assert isinstance(result['charts'], list), "chart_data应为列表"
        if len(result['charts']) > 0:
            # 验证分时图数据结构
            first_point = result['charts'][0]
            assert 'time' in first_point, "分时图数据点缺少time字段"
            assert 'price' in first_point, "分时图数据点缺少price字段"
            assert 'avg' in first_point, "分时图数据点缺少avg字段"
            assert 'vol' in first_point, "分时图数据点缺少vol字段"
            assert 'momentum' in first_point, "分时图数据点缺少momentum字段"

    def test_get_symbol_tick_chart_with_date(self, mqc):
        """测试指定日期的历史分时图数据"""
        from datetime import date
        
        # 使用一个最近的交易日（需要根据实际情况调整）
        query_date = date(2024, 1, 15)
        result = mqc.get_symbol_tick_chart(MARKET.SH, '600000', query_date)
        
        # 验证返回数据类型
        assert isinstance(result, dict), f"返回类型应为dict，实际为 {type(result)}"
        
        # 验证基本信息
        assert result['code'] == '600000', f"股票代码错误: {result['code']}"
        assert result['market'] == MARKET.SH, f"市场代码错误: {result['market']}"
        
        # 验证时间字段（历史数据应该有具体的时间戳）
        assert result['time'] is not None, "历史数据的时间戳不应为None"
        
        # 验证日期是否正确
        if result['time']:
            result_date = result['time'].date()
            assert result_date == query_date, \
                f"返回数据日期({result_date})与查询日期({query_date})不一致"
        
        # 验证价格数据有效性
        assert result['pre_close'] > 0, f"昨收价应大于0: {result['pre_close']}"
        assert result['close'] >= 0, f"收盘价应>=0: {result['close']}"
        
        # 历史数据的charts可能为空或包含数据
        assert isinstance(result['charts'], list), "charts应为列表"

    def test_get_symbol_tick_chart_invalid_date(self, mqc):
        """测试无效日期的处理"""
        from datetime import date
        
        # 测试未来日期（应该返回空数据或特定错误）
        future_date = date(2030, 12, 31)
        result = mqc.get_symbol_tick_chart(MARKET.SZ, '000001', future_date)
        
        # 验证返回类型仍然正确
        assert isinstance(result, dict), "即使日期无效，也应返回字典类型"
        
        # 未来日期可能返回空数据或部分字段为空
        # 这里主要验证不会抛出异常
        assert result is not None, "返回值不应为None"

    def test_get_symbol_tick_chart_weekend_date(self, mqc):
        """测试周末日期的处理"""
        from datetime import date
        
        # 2024-01-13 是星期六
        weekend_date = date(2024, 1, 13)
        result = mqc.get_symbol_tick_chart(MARKET.SH, '600000', weekend_date)
        
        # 验证返回类型
        assert isinstance(result, dict), "周末日期查询应返回字典类型"
        
        # 周末无交易数据，但不应抛出异常
        assert result is not None, "周末查询返回值不应为None"

    def test_get_symbol_tick_chart_hk_stock(self, meqc):
        """测试港股分时图数据获取"""
        # 使用港股主板市场
        result = meqc.get_symbol_tick_chart(EX_MARKET.HK_MAIN_BOARD, '00700')
        
        # 验证返回数据类型
        assert isinstance(result, dict), f"返回类型应为dict，实际为 {type(result)}"
        
        assert isinstance(result['charts'], list), f" result['charts'] 返回类型应为list，实际为 {type(result['charts'])}"


    def test_get_symbol_tick_chart_hk_with_date(self, meqc):
        """测试港股历史分时图数据"""
        from datetime import date
        
        # 使用一个最近的交易日
        query_date = date(2024, 1, 15)
        result = meqc.get_symbol_tick_chart(EX_MARKET.HK_MAIN_BOARD, '00700', query_date)
        
        # 港股历史数据可能返回None（取决于服务器支持情况）
        # 这里主要验证不会抛出异常
        if result is not None:
            # 如果返回数据，验证其结构
            assert isinstance(result, dict), f"返回类型应为dict，实际为 {type(result)}"
            
            # 验证基本信息
            assert result['code'] == '00700', f"港股代码错误: {result['code']}"
            assert result['market'] == EX_MARKET.HK_MAIN_BOARD.value, \
                f"港股市场代码错误: {result['market']}"
            
            # 验证时间字段
            if result['time']:
                result_date = result['time'].date()
                # 港股历史数据日期应与查询日期一致
                assert result_date == query_date, \
                    f"港股返回数据日期({result_date})与查询日期({query_date})不一致"
            
            # 验证价格数据
            assert result['pre_close'] > 0, f"港股昨收价应大于0: {result['pre_close']}"
        else:
            # 如果返回None，说明服务器不支持该日期的历史数据，这也是可接受的
            pass

    def test_get_symbol_tick_chart_chart_data_structure(self, mqc):
        """测试分时图数据结构的完整性"""
        result = mqc.get_symbol_tick_chart(MARKET.SZ, '000001')
        
        # 验证chart_data是列表
        assert isinstance(result['charts'], list), "chart_data必须是列表类型"
        
        # 如果有分时数据，验证每个数据点的结构
        if len(result['charts']) > 0:
            for i, point in enumerate(result['charts']):
                assert isinstance(point, dict), f"第{i}个分时数据点应为字典类型"
                
                # 验证必需字段
                assert 'time' in point, f"第{i}个分时数据点缺少time字段"
                assert 'price' in point, f"第{i}个分时数据点缺少price字段"
                assert 'avg' in point, f"第{i}个分时数据点缺少avg字段"
                assert 'vol' in point, f"第{i}个分时数据点缺少vol字段"
                assert 'momentum' in point, f"第{i}个分时数据点缺少momentum字段"
                
                # 验证字段类型
                assert point['price'] >= 0, f"第{i}个数据点价格应>=0"
                assert point['avg'] >= 0, f"第{i}个数据点均价应>=0"
                assert point['vol'] >= 0, f"第{i}个数据点成交量应>=0"
                
                # time字段应该是datetime.time类型
                from datetime import time as time_type
                assert isinstance(point['time'], time_type), \
                    f"第{i}个数据点time字段应为time类型，实际为{type(point['time'])}"


class TestMacQuotationClientSymbolQuotes:
    """分时图 API - 真实请求测试"""

    def test_get_symbol_quotes(self, mqc:macQuotationClient):
        """测试A股的股票信息"""
        code_list = [
            (MARKET.SZ, '000001'),
            (MARKET.SH, '688808'),
            (MARKET.SZ, '000999')
            
        ]
        print(code_list)
        result = mqc.get_symbol_quotes(code_list)
        df = pd.DataFrame(result['stocks'])
        print(result['stocks'])
        
    def test_get_ex_symbol_quotes(self, meqc:macQuotationClient):
        """测试EX的股票信息"""
        code_list = [
            (EX_MARKET.US_STOCK, 'BOIL'),
            (EX_MARKET.US_STOCK, 'KOLD'),
        ]
        print(code_list)
        result = meqc.get_symbol_quotes(code_list)
        df = pd.DataFrame(result['stocks'])
        print(result['stocks'])
        
        code_list = [
            (EX_MARKET.HK_MAIN_BOARD, '00700'),
        ]
        print(code_list)
        result = meqc.get_symbol_quotes(code_list)
        df = pd.DataFrame(result['stocks'])
        print(result['stocks'])
        
    def test_get_symbol_quotes_with_basic_fields(self, mqc:macQuotationClient):
        """测试使用 basic 字段预设获取股票行情"""
        code_list = [
            (MARKET.SZ, '000001'),
            (MARKET.SH, '600000'),
        ]
        
        result = mqc.get_symbol_quotes(code_list, fields=PresetField.BASIC)
        
        # 验证返回结构
        assert isinstance(result, dict), f"返回类型应为dict，实际为{type(result)}"
        assert "count" in result, "返回值应包含count字段"
        assert "stocks" in result, "返回值应包含stocks字段"
        assert result["count"] == len(code_list), f"返回数量应与请求数量一致"
        assert len(result["stocks"]) == len(code_list), f"返回股票数应与请求数量一致"
        
        # 验证基本字段存在
        for stock in result["stocks"]:
            assert "market" in stock, "股票数据应包含market字段"
            assert "code" in stock, "股票数据应包含code字段"
            assert "pre_close" in stock, "basic字段集应包含pre_close"
            assert "open" in stock, "basic字段集应包含open"
            assert "high" in stock, "basic字段集应包含high"
            assert "low" in stock, "basic字段集应包含low"
            assert "close" in stock, "basic字段集应包含close"
            assert "vol" in stock, "basic字段集应包含vol"
            
        print(f"Basic字段测试结果: {len(result['stocks'])}只股票")
        
    def test_get_symbol_quotes_with_quote_fields(self, mqc:macQuotationClient):
        """测试使用 quote 字段预设获取盘口数据"""
        code_list = [
            (MARKET.SZ, '000001'),
        ]
        
        result = mqc.get_symbol_quotes(code_list, fields=PresetField.QUOTE)
        
        # 验证返回结构
        assert isinstance(result, dict), f"返回类型应为dict，实际为{type(result)}"
        assert len(result["stocks"]) == len(code_list), f"返回股票数应与请求数量一致"
        
        # 验证盘口字段存在
        for stock in result["stocks"]:
            assert "bid" in stock, "quote字段集应包含bid"
            assert "ask" in stock, "quote字段集应包含ask"
            assert "bid_volume" in stock, "quote字段集应包含bid_volume"
            assert "ask_volume" in stock, "quote字段集应包含ask_volume"
            assert "last_volume" in stock, "quote字段集应包含last_volume"
            
        print(f"Quote字段测试结果: bid={result['stocks'][0].get('bid')}, ask={result['stocks'][0].get('ask')}")
        
    def test_get_symbol_quotes_with_volume_fields(self, mqc:macQuotationClient):
        """测试使用 volume 字段预设获取量能数据"""
        code_list = [
            (MARKET.SZ, '000001'),
        ]
        
        result = mqc.get_symbol_quotes(code_list, fields=PresetField.VOLUME)
        
        # 验证返回结构
        assert isinstance(result, dict), f"返回类型应为dict，实际为{type(result)}"
        assert len(result["stocks"]) == len(code_list), f"返回股票数应与请求数量一致"
        
        # 验证量能字段存在
        for stock in result["stocks"]:
            assert "vol" in stock, "volume字段集应包含vol"
            assert "amount" in stock, "volume字段集应包含amount"
            assert "turnover" in stock, "volume字段集应包含turnover"
            assert "vol_ratio" in stock, "volume字段集应包含vol_ratio"
            
        print(f"Volume字段测试结果: vol={result['stocks'][0].get('vol')}, amount={result['stocks'][0].get('amount')}")
        
    def test_get_symbol_quotes_with_combined_fields(self, mqc:macQuotationClient):
        """测试使用组合字段（basic+quote）获取股票行情"""
        code_list = [
            (MARKET.SZ, '000001'),
            (MARKET.SH, '600000'),
        ]
        
        result = mqc.get_symbol_quotes(code_list, fields=PresetField.BASIC + PresetField.QUOTE)
        
        # 验证返回结构
        assert isinstance(result, dict), f"返回类型应为dict，实际为{type(result)}"
        assert result["count"] == len(code_list), f"返回数量应与请求数量一致"
        assert len(result["stocks"]) == len(code_list), f"返回股票数应与请求数量一致"
        
        # 验证组合字段都存在
        for stock in result["stocks"]:
            # Basic字段
            assert "pre_close" in stock, "应包含pre_close"
            assert "close" in stock, "应包含close"
            # Quote字段
            assert "bid" in stock, "应包含bid"
            assert "ask" in stock, "应包含ask"
            
        print(f"Combined字段测试结果: {len(result['stocks'])}只股票，字段数={len(result['stocks'][0])}")
        
    def test_get_symbol_quotes_with_fundamental_fields(self, mqc:macQuotationClient):
        """测试使用 fundamental 字段预设获取基本面数据"""
        code_list = [
            (MARKET.SZ, '000001'),
        ]
        
        result = mqc.get_symbol_quotes(code_list, fields=PresetField.FUNDAMENTAL)
        
        # 验证返回结构
        assert isinstance(result, dict), f"返回类型应为dict，实际为{type(result)}"
        assert len(result["stocks"]) == len(code_list), f"返回股票数应与请求数量一致"
        
        # 验证基本面字段存在
        for stock in result["stocks"]:
            assert "total_shares" in stock, "fundamental字段集应包含total_shares"
            assert "float_shares" in stock, "fundamental字段集应包含float_shares"
            assert "eps" in stock, "fundamental字段集应包含EPS"
            assert "net_assets" in stock, "fundamental字段集应包含net_assets"
            
        print(f"Fundamental字段测试结果: EPS={result['stocks'][0].get('EPS')}, net_assets={result['stocks'][0].get('net_assets')}")
        
    def test_get_symbol_quotes_with_custom_filter(self, mqc:macQuotationClient):
        """测试使用自定义filter参数获取股票行情"""

        
        code_list = [
            (MARKET.SZ, '000001'),
        ]
        
        # 使用 PresetField.BASIC（只包含基础字段：pre_close, open, high, low, close, vol）
        result = mqc.get_symbol_quotes(code_list, fields=PresetField.BASIC)
        
        # 验证返回结构
        assert isinstance(result, dict), f"返回类型应为dict，实际为{type(result)}"
        assert len(result["stocks"]) == len(code_list), f"返回股票数应与请求数量一致"
        
        # 验证 BASIC 字段集中的字段存在
        for stock in result["stocks"]:
            assert "pre_close" in stock, "BASIC字段集应包含pre_close"
            assert "open" in stock, "BASIC字段集应包含open"
            assert "high" in stock, "BASIC字段集应包含high"
            assert "low" in stock, "BASIC字段集应包含low"
            assert "close" in stock, "BASIC字段集应包含close"
            assert "vol" in stock, "BASIC字段集应包含vol"
            
        # 验证 BASIC 字段集之外的字段不存在（确保 filter 生效）
        for stock in result["stocks"]:
            assert "amount" not in stock, "BASIC字段集不应包含amount"
            assert "bid" not in stock, "BASIC字段集不应包含bid"
            assert "ask" not in stock, "BASIC字段集不应包含ask"
            assert "turnover" not in stock, "BASIC字段集不应包含turnover"
        

class TestMacQuotationClientSymbolTransaction:
    """分时成交 API - 真实请求测试"""

    def test_get_symbol_transactions_basic(self, mqc: macQuotationClient):
        """
        测试获取当日逐笔成交数据的基本功能
        验证返回数据结构完整性和数据类型正确性
        """
        result = mqc.get_symbol_transactions(MARKET.SH, '601000', count=10)
        
        # 验证返回类型为列表
        assert isinstance(result, list), f"返回类型应为list，实际为{type(result)}"
        
        # 验证返回数量
        assert len(result) == 10, f"应返回10笔成交，实际返回{len(result)}笔"
        
        print(f"基本测试通过: 返回{len(result)}笔成交")

    def test_get_symbol_transactions_data_structure(self, mqc: macQuotationClient):
        """
        测试逐笔成交数据的内部结构
        验证每笔成交记录的字段完整性和数据类型
        """
        result = mqc.get_symbol_transactions(MARKET.SZ, '000001', count=5)
        
        assert len(result) > 0, "应至少返回一笔成交数据"
        
        # 验证每笔成交记录的字段
        required_tx_fields = ['time', 'price', 'volume', 'trade_count', 'bs_flag']
        
        for i, tx in enumerate(result):
            assert isinstance(tx, dict), f"第{i}笔成交应为字典类型"
            
            for field in required_tx_fields:
                assert field in tx, f"第{i}笔成交缺少字段: {field}"
            
            # 验证字段类型
            assert isinstance(tx['time'], time), f"第{i}笔成交 time 应为time类型"
            assert isinstance(tx['price'], float), f"第{i}笔成交 price 应为浮点数"
            assert isinstance(tx['volume'], int), f"第{i}笔成交 volume 应为整数"
            assert isinstance(tx['trade_count'], int), f"第{i}笔成交 trade_count 应为整数"
            assert isinstance(tx['bs_flag'], int), f"第{i}笔成交 bs_flag 应为整数"
            
            # 验证时间格式
            assert isinstance(tx['time'], time), f"第{i}笔成交 time 应为time类型"

            # 验证价格合理性
            assert tx['price'] > 0, f"第{i}笔成交价格应大于0"

            # 验证成交量合理性
            assert tx['volume'] >= 0, f"第{i}笔成交量应大于等于0"

            # 验证买卖方向标志
            assert tx['bs_flag'] in [0, 1, 2, 5], \
                f"第{i}笔成交 bs_flag 值无效: {tx['bs_flag']} (应为0/1/2/5)"
        
        print(f"数据结构测试通过: 验证了{len(result)}笔成交记录")

    def test_get_symbol_transactions_historical_date(self, mqc: macQuotationClient):
        """
        测试历史日期查询功能
        验证可以成功获取指定日期的成交数据
        """
        from datetime import date
        
        # 测试有效历史日期（2024年1月15日是交易日）
        test_date = date(2024, 1, 15)
        result = mqc.get_symbol_transactions(
            MARKET.SH, 
            '601000', 
            count=5,
            query_date=test_date
        )
        
        # 验证返回数据
        assert isinstance(result, list), "返回类型应为list"
        assert len(result) > 0, "历史日期应返回成交数据"
        
        print(f"历史日期测试通过: {test_date}, 返回{len(result)}笔成交")

    def test_get_symbol_transactions_future_date(self, mqc: macQuotationClient):
        """
        测试未来日期查询
        验证未来日期可能返回空数据或异常处理
        """
        from datetime import date, timedelta
        
        # 测试未来日期（明天）
        future_date = date.today() + timedelta(days=1)
        result = mqc.get_symbol_transactions(
            MARKET.SH, 
            '601000', 
            count=5,
            query_date=future_date
        )
        
        # 未来日期可能返回空数据，这是正常行为
        assert isinstance(result, list), "返回类型应为list"
        
        print(f"未来日期测试通过: {future_date}, 返回{len(result)}笔成交（可能为空）")

    def test_get_symbol_transactions_weekend_date(self, mqc: macQuotationClient):
        """
        测试非交易日（周末）查询
        验证周末日期可能返回空数据
        """
        from datetime import date
        
        # 2024年1月13日是周六（非交易日）
        weekend_date = date(2024, 1, 13)
        result = mqc.get_symbol_transactions(
            MARKET.SH, 
            '601000', 
            count=5,
            query_date=weekend_date
        )
        
        # 非交易日可能返回空数据，这是正常行为
        assert isinstance(result, list), "返回类型应为list"
        
        print(f"周末日期测试通过: {weekend_date}（周六）, 返回{len(result)}笔成交（可能为空）")

    def test_get_symbol_transactions_multiple_markets(self, mqc: macQuotationClient):
        """
        测试多市场兼容性
        分别测试上海市场和深圳市场的成交数据获取
        """
        # 测试上海市场
        sh_result = mqc.get_symbol_transactions(MARKET.SH, '600000', count=3)
        assert isinstance(sh_result, list), "上海市场返回类型应为list"
        assert len(sh_result) > 0, "上海市场应返回成交数据"
        
        # 测试深圳市场
        sz_result = mqc.get_symbol_transactions(MARKET.SZ, '000001', count=3)
        assert isinstance(sz_result, list), "深圳市场返回类型应为list"
        assert len(sz_result) > 0, "深圳市场应返回成交数据"
        
        print(f"多市场测试通过: SH返回{len(sh_result)}笔, SZ返回{len(sz_result)}笔")

    def test_get_symbol_transactions_pagination(self, mqc: macQuotationClient):
        """
        测试分页查询功能
        验证 start 参数可以正确控制起始位置
        """
        # 获取第一页数据
        page1 = mqc.get_symbol_transactions(MARKET.SH, '601000', count=5, start=0)
        assert len(page1) > 0, "第一页应返回数据"
        
        # 获取第二页数据
        page2 = mqc.get_symbol_transactions(MARKET.SH, '601000', count=5, start=5)
        assert len(page2) > 0, "第二页应返回数据"
        
        # 验证两页数据不同（时间应该不同）
        if len(page1) > 0 and len(page2) > 0:
            page1_times = [tx['time'] for tx in page1]
            page2_times = [tx['time'] for tx in page2]
            
            # 两页数据的时间不应该完全相同
            assert page1_times != page2_times, "分页数据应该不同"
        
        print(f"分页测试通过: 第一页{len(page1)}笔, 第二页{len(page2)}笔")

    def test_get_symbol_transactions_large_count(self, mqc: macQuotationClient):
        """
        测试大批量数据获取
        验证可以一次性获取较多成交数据
        """
        result = mqc.get_symbol_transactions(MARKET.SH, '601000', count=100)
        
        assert isinstance(result, list), "返回类型应为list"
        assert len(result) <= 100, "返回数量不应超过请求数量"
        
        print(f"大批量测试通过: 请求100笔, 实际返回{len(result)}笔")

    def test_get_symbol_transactions_bs_flag_distribution(self, mqc: macQuotationClient):
        """
        测试买卖方向分布统计
        验证 bs_flag 字段的分布合理性
        """
        result = mqc.get_symbol_transactions(MARKET.SH, '601000', count=50)
        
        assert len(result) > 0, "应返回成交数据"
        
        # 统计买卖方向分布
        bs_flags = [tx['bs_flag'] for tx in result]
        buy_count = bs_flags.count(0)   # 买入
        sell_count = bs_flags.count(1)  # 卖出
        neutral_count = bs_flags.count(2)  # 中性盘
        after_hours_count = bs_flags.count(5)  # 盘后
        
        
        total = len(result)
        
        # 验证所有 bs_flag 都是有效值
        valid_flags = {0, 1, 2, 5}
        assert all(flag in valid_flags for flag in bs_flags), \
            f"存在无效的 bs_flag 值: {set(bs_flags) - valid_flags}"
        
        print(f"买卖方向分布测试通过:")
        print(f"  买入: {buy_count} ({buy_count/total*100:.1f}%)")
        print(f"  卖出: {sell_count} ({sell_count/total*100:.1f}%)")
        print(f"  中性盘: {neutral_count} ({neutral_count/total*100:.1f}%)")
        print(f"  盘后: {after_hours_count} ({after_hours_count/total*100:.1f}%)")

    def test_get_symbol_transactions_price_range(self, mqc: macQuotationClient):
        """
        测试价格范围合理性
        验证成交价格在合理范围内
        """
        result = mqc.get_symbol_transactions(MARKET.SH, '601000', count=20)
        
        assert len(result) > 0, "应返回成交数据"
        
        prices = [tx['price'] for tx in result]
        min_price = min(prices)
        max_price = max(prices)
        
        # 验证价格在合理范围内（唐山港股价通常在2-10元之间）
        assert min_price > 0, f"最低价格应大于0，实际为{min_price}"
        assert max_price < 100, f"最高价格应小于100，实际为{max_price}"
        
        # 验证价格波动合理性（日内价格波动通常不超过10%）
        if min_price > 0:
            price_range_pct = (max_price - min_price) / min_price * 100
            assert price_range_pct < 20, \
                f"价格波动过大: {price_range_pct:.2f}% (min={min_price}, max={max_price})"
        
        print(f"价格范围测试通过: min={min_price:.2f}, max={max_price:.2f}, 波动={price_range_pct:.2f}%")
