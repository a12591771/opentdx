"""
市场异动监控模块
提供实时市场异动数据的查询和显示功能
"""
import time
import click
import unicodedata
from datetime import datetime
from contextlib import contextmanager
from opentdx.client.macStandardClient import MacStandardClient as macQuotationClient
from opentdx.const import MARKET
from zoneinfo import ZoneInfo


def is_trading_time() -> bool:
    """
    判断当前是否为A股交易时间（基于中国时区）
    A股交易时间：
    - 上午：9:30 - 11:30
    - 下午：13:00 - 15:00
    Returns:
        bool: True 表示交易时间，False 表示盘后
    """
    # 获取中国时区当前时间
    china_tz = ZoneInfo("Asia/Shanghai")
    now = datetime.now(china_tz)          # 带时区的 datetime
    current_time = now.time()             # time 对象（时区信息已隐含）

    # 定义交易时间段（按照你的代码逻辑，保留原数值）
    morning_start = datetime.strptime("09:15:00", "%H:%M:%S").time()
    morning_end   = datetime.strptime("11:35:00", "%H:%M:%S").time()
    afternoon_start = datetime.strptime("12:55:00", "%H:%M:%S").time()
    afternoon_end   = datetime.strptime("15:05:00", "%H:%M:%S").time()

    # 判断
    if (morning_start <= current_time <= morning_end) or \
       (afternoon_start <= current_time <= afternoon_end):
        return True
    else:
        return False

@contextmanager
def mac_quotation_client():
    """
    macQuotationClient 上下文管理器
    
    自动处理连接和资源释放
    """
    client = macQuotationClient()
    try:
        client.connect()
        yield client
    finally:
        client.disconnect()


def get_display_width(text: str) -> int:
    """
    计算字符串的显示宽度（考虑中英文字符宽度差异）
    
    Args:
        text: 输入字符串
        
    Returns:
        显示宽度（中文字符算2，英文字符算1）
    """
    width = 0
    for char in text:
        if unicodedata.east_asian_width(char) in ('F', 'W', 'A'):
            # F (Full-width), W (Wide), A (Ambiguous) 通常算2个宽度
            width += 2
        else:
            # Na (Narrow), N (Neutral), H (Half-width) 算1个宽度
            width += 1
    return width


def pad_string(text: str, target_width: int, align: str = 'left') -> str:
    """
    根据显示宽度填充字符串
    
    Args:
        text: 原始字符串
        target_width: 目标显示宽度
        align: 对齐方式 ('left', 'right', 'center')
        
    Returns:
        填充后的字符串
    """
    current_width = get_display_width(text)
    padding_needed = target_width - current_width
    
    if padding_needed <= 0:
        return text
    
    if align == 'left':
        return text + ' ' * padding_needed
    elif align == 'right':
        return ' ' * padding_needed + text
    elif align == 'center':
        left_padding = padding_needed // 2
        right_padding = padding_needed - left_padding
        return ' ' * left_padding + text + ' ' * right_padding
    else:
        return text


def run_market_monitor(interval: int = 5, count: int = 100, split: bool = True, search: str = ""):
    """
    运行市场异动监控
    
    Args:
        interval: 正常刷新间隔（秒），默认5秒
        count: 每个市场获取的监控记录数，默认10条
        split: 是否使用分隔符显示，默认True
    """
    markets = [MARKET.SH, MARKET.SZ, MARKET.BJ]
    market_prefix = {
        MARKET.SH: "SH",
        MARKET.SZ: "SZ", 
        MARKET.BJ: "BJ"
    }
    
    # 记录每个市场最后一次的 index，用于增量获取
    last_indices = {market: 0 for market in markets}
    
    wait_time = interval
    
    try:
        with mac_quotation_client() as client:
            click.echo(click.style("=" * 80, fg='cyan', bold=True))
            click.echo(click.style("市场异动监控系统启动,建议结合其他指标进行判断", fg='green', bold=True))
            click.echo(f"刷新间隔: {interval}秒 | 每次获取: {count}条记录/市场")
            click.echo(click.style("=" * 80, fg='cyan', bold=True))
            click.echo()
            time.sleep(1.5)
            
            while True:
                try:
                    all_data = []
                    has_more_data = False  # 标记是否还有更多数据
                    
                    # 循环三个市场，收集所有数据
                    for market in markets:
                        try:
                            # 使用上次的 index 作为起始位置，实现增量获取
                            start_index = last_indices[market]
                            # 首次获取时，设置 count 为 50000. 如果不设置,会导致数BJ/SH的先读取完. 最后仅显示SZ数据
                            if start_index == 0:
                                count = 50000
                            
                            # 获取市场监控数据（直接调用 macQuotationClient 的方法）
                            monitor_data = client.get_market_monitor(market, start=start_index, count=count)
                            
                            if not monitor_data:
                                continue
                            
                            # 判断是否还有更多数据：如果返回数量等于请求数量，说明服务器可能还有数据
                            if len(monitor_data) >= count:
                                has_more_data = True
                            
                            # 将数据添加到总列表，并添加市场前缀
                            for item in monitor_data:
                                item['_market_prefix'] = market_prefix[market]
                                all_data.append(item)
                            
                            # 更新最后一次的 index
                            last_indices[market] += len(monitor_data)
                            
                        except Exception as e:
                            click.echo(click.style(f"【{market_prefix[market]}】获取数据失败: {str(e)}", fg='red'))
                    
                    # 按时间排序（最新的在前）
                    all_data.sort(key=lambda x: x.get('time'), reverse=False)
                    
                    # 打印所有市场的异动记录（统一显示）
                    if all_data:
                        for item in all_data:
                            code = item.get('code', 'N/A')
                            name = item.get('name', 'N/A')
                            desc = item.get('desc', 'N/A').replace(' ', '')
                            prefix = item.get('_market_prefix', '')
                            # 股票代码字段：prefix.code (如 SH.603272) 固定9个字符显示宽度
                            code_field = f"{prefix}.{code}"
                            # 如果设置了搜索条件，进行过滤
                            if search:
                                search_lower = search.lower()
                                code_match = search_lower in code_field.lower()
                                name_match = search_lower in name.lower()
                                desc_match = search_lower in desc.lower()
                                
                                # 如果都不匹配，跳过这条记录
                                if not (code_match or name_match or desc_match):
                                    continue
                            
                            value = item.get('value', 'N/A')
                            t = item.get('time', None)
                            time_str = t.strftime('%H:%M:%S') if t else 'N/A'

                            
                            v2 = item.get('v2', 0)
                            v3 = item.get('v3', 0)
                            value_styled = value
                            
                            # 根据异动类型设置颜色
                            if '涨停' in desc :
                                desc_color = 'red'
                                desc_bold = True
                            elif '主力买入' in desc:
                                desc_color = 'red'
                                desc_bold = True
                                if v3 > 1000000:
                                    value_styled = click.style(value, fg='red', bold=True)
                            elif '跌停' in desc:
                                desc_color = 'green'
                                desc_bold = True
                            elif '主力卖出' in desc:
                                desc_color = 'green'
                                desc_bold = True
                                if v3 > 1000000:
                                    value_styled = click.style(value, fg='green', bold=True)
                            elif '区间放量' in desc:
                                desc_color = 'yellow'
                                desc_bold = True
                                if v2 > 10:
                                    value_styled = click.style(value, fg='yellow', bold=True)
                                    
                            else:
                                desc_color = None
                                desc_bold = False
                            
                            # 使用 Unicode 宽度计算进行对齐

                            code_padded = pad_string(code_field, 10, 'left')
                            
                            # 股票名称字段：固定12个显示宽度
                            name_padded = pad_string(name, 10, 'left')
                            
                            # 异动描述字段：固定14个显示宽度
                            desc_padded = pad_string(desc, 10, 'left')
                            
                            # 应用颜色样式
                            desc_styled = click.style(desc_padded, fg=desc_color, bold=desc_bold) if desc_color else desc_padded
                            time_styled = click.style(f"[{time_str}]", fg='blue')
                            code_styled = click.style(code_padded, fg='white', bold=True)
                            
                            click.echo(f"  {time_styled} {code_styled} {name_padded} | {desc_styled} | {value_styled}")
                    

                    if not all_data and not is_trading_time():
                        # 判断是否为交易时间
                        wait_time = 10
                        trade_txt = "盘后"
                    else:
                        trade_txt = "盘中"
                        
                    if split:
                        click.echo()
                        click.echo(click.style("=" * 80, fg='cyan'))
                        
                    # 根据是否有更多数据和交易时间，动态调整等待时间
                    if has_more_data:
                        # 服务器还有数据，快速连续请求
                        wait_time = 0.1 
                        click.echo(click.style(f"检测到更多数据，{wait_time}秒后继续刷新... (按 Ctrl+C 退出)", fg='yellow'))
                        
                    else:
                        # 交易时间：使用正常间隔
                        wait_time = max(wait_time, 0.1)
                        if split:
                            china_tz = ZoneInfo("Asia/Shanghai")
                            now = datetime.now(china_tz)
                            current_time = now.strftime('%H:%M:%S')
                            click.echo(click.style(f"[{current_time}] 新: {len(all_data)} {trade_txt} 下次刷新: {wait_time}秒后... (按 Ctrl+C 退出)", fg='cyan'))
                            click.echo(click.style("=" * 80, fg='cyan'))

                    if not all_data:
                        # 判断是否为交易时间
                        fg = 'yellow' if is_trading_time() else 'blue'

                        # 获取当前时间作为参考+
                        china_tz = ZoneInfo("Asia/Shanghai")
                        now = datetime.now(china_tz)
                        
                        current_time = now.strftime('%H:%M:%S')
                        
                        click.echo(click.style(f"[{current_time}]  {trade_txt} .下次刷新: {wait_time}秒后... (按 Ctrl+C 退出)", fg=fg))

                    
                    # 等待指定间隔
                    time.sleep(wait_time)
                    
                except KeyboardInterrupt:
                    click.echo("\n\n" + click.style("主力监控系统已停止", fg='red', bold=True))
                    break
                    
    except Exception as e:
        click.echo(click.style(f"错误: {str(e)}", fg='red', bold=True), err=True)
        raise