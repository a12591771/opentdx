import json
from datetime import date, datetime
from decimal import Decimal

import click
import pandas as pd

from opentdx.commands.doc_demo import run_interactive
from opentdx.commands import run_market_monitor
from opentdx.tdxClient import TdxClient
from opentdx.client.macStandardClient import MacStandardClient
from opentdx.client.macExtendedClient import MacExtendedClient
from opentdx.const import ADJUST, EX_MARKET, MARKET, PERIOD, BOARD_TYPE, EX_BOARD_TYPE


def _json_default(obj):
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    if hasattr(obj, 'value'):
        return obj.value
    return str(obj)


def _output(result, json_fmt):
    if json_fmt:
        click.echo(json.dumps(result, default=_json_default, ensure_ascii=False))
    elif isinstance(result, list):
        if result and isinstance(result[0], dict):
            click.echo(pd.DataFrame(result).to_string())
        else:
            click.echo(str(result))
    elif isinstance(result, dict):
        click.echo(pd.DataFrame([result]).to_string())
    else:
        click.echo(str(result))


def _parse_market(s: str):
    try:
        return getattr(MARKET, s.upper())
    except AttributeError:
        try:
            return getattr(EX_MARKET, s.upper())
        except AttributeError:
            raise click.BadParameter(f"无效市场: {s}")


def _parse_period(s: str):
    try:
        return getattr(PERIOD, s.upper())
    except AttributeError:
        raise click.BadParameter(f"无效周期: {s}")


def _parse_adjust(s: str):
    try:
        return getattr(ADJUST, s.upper())
    except AttributeError:
        raise click.BadParameter(f"无效复权: {s}")


def _parse_codes(s: str):
    """解析 'SZ 000001,SH 600000' 格式"""
    pairs = []
    parts = [p.strip() for p in s.split(',')]
    for part in parts:
        tokens = part.split()
        if len(tokens) != 2:
            raise click.BadParameter(f"格式应为 'MARKET CODE,...' 如 'SZ 000001,SH 600000'")
        pairs.append((_parse_market(tokens[0]), tokens[1]))
    return pairs


@click.group()
def cli():
    """OpenTDX - TDX stock data client CLI"""
    pass


@cli.command()
def doc():
    """交互式接口文档"""
    run_interactive()


@cli.command(name='mm')
@click.option('--search', default='', help='搜索关键词（匹配代码、名称或异动描述）')
@click.option('--interval', default=3, help='查询间隔（秒），默认3秒')
@click.option('--count', default=1000, help='每个市场获取的监控记录数，默认1000条')
@click.option('--split/--no-split', default=False, help='是否使用分隔符显示')
def market_monitor(interval, count, split, search):
    """实时监控市场异动数据（每3秒刷新）"""
    run_market_monitor(interval=interval, count=count, split=split, search=search)


# ==================== A股行情 ====================

@cli.command()
@click.argument('market')
@click.argument('code')
@click.option('--period', default='DAILY', help='周期 (DAILY/WEEKLY/MONTHLY/MIN_5/MIN_15/MIN_30/MIN_60/MINS)')
@click.option('--count', default=10, type=int, help='数量')
@click.option('--adjust', default='NONE', help='复权 (NONE/QFQ/HFQ)')
@click.option('--times', default=1, type=int, help='多周期倍数（MINS/DAYS 时生效）')
@click.option('--json', 'json_fmt', is_flag=True, default=False, help='JSON 输出')
def kline(market, code, period, count, adjust, times, json_fmt):
    """A股K线数据

    opentdx kline SZ 000001 --period DAILY --count 10
    opentdx kline SH 600519 --period MIN_30 --count 50
    opentdx kline SZ 000001 --adjust QFQ
    """
    with TdxClient() as c:
        result = c.stock_kline(_parse_market(market), code, _parse_period(period),
                               count=count, adjust=_parse_adjust(adjust), times=times)
        _output(result, json_fmt)


@cli.command()
@click.argument('codes')
@click.option('--json', 'json_fmt', is_flag=True, default=False, help='JSON 输出')
def quote(codes, json_fmt):
    """股票报价

    opentdx quote "SZ 000001, SH 600000"
    opentdx quote "SZ 000001"
    """
    with TdxClient() as c:
        result = c.stock_quotes(_parse_codes(codes))
        _output(result, json_fmt)


@cli.command()
@click.argument('codes')
@click.option('--json', 'json_fmt', is_flag=True, default=False, help='JSON 输出')
def index(codes, json_fmt):
    """指数信息

    opentdx index "SH 999999, SZ 399001"
    """
    with TdxClient() as c:
        result = c.index_info(_parse_codes(codes))
        _output(result, json_fmt)


@cli.command(name='stock-list')
@click.argument('market')
@click.option('--count', default=20, type=int, help='数量')
@click.option('--json', 'json_fmt', is_flag=True, default=False, help='JSON 输出')
def stock_list(market, count, json_fmt):
    """股票列表

    opentdx stock-list SZ --count 10
    """
    with TdxClient() as c:
        result = c.stock_list(_parse_market(market), count=count)
        _output(result, json_fmt)


@cli.command()
@click.argument('market')
@click.option('--count', default=10, type=int, help='数量')
@click.option('--json', 'json_fmt', is_flag=True, default=False, help='JSON 输出')
def unusual(market, count, json_fmt):
    """异动数据

    opentdx unusual SZ --count 20
    """
    with TdxClient() as c:
        result = c.stock_unusual(_parse_market(market), count=count)
        _output(result, json_fmt)


@cli.command()
@click.argument('market')
@click.argument('code')
@click.option('--date', default=None, help='日期 YYYY-MM-DD（默认实时）')
@click.option('--count', default=20, type=int, help='数量')
@click.option('--json', 'json_fmt', is_flag=True, default=False, help='JSON 输出')
def transaction(market, code, date, count, json_fmt):
    """逐笔成交

    opentdx transaction SZ 000001 --count 50
    opentdx transaction SZ 000001 --date 2026-03-03
    """
    d = date.fromisoformat(date) if date else None
    with TdxClient() as c:
        result = c.stock_transaction(_parse_market(market), code, date=d)
        result = result[:count]
        _output(result, json_fmt)


@cli.command()
@click.argument('market')
@click.argument('code')
@click.option('--date', default=None, help='日期 YYYY-MM-DD（默认实时）')
@click.option('--json', 'json_fmt', is_flag=True, default=False, help='JSON 输出')
def tick(market, code, date, json_fmt):
    """分时图

    opentdx tick SZ 000001
    opentdx tick SH 999999 --date 2026-03-16
    """
    d = date.fromisoformat(date) if date else None
    with TdxClient() as c:
        result = c.stock_tick_chart(_parse_market(market), code, date=d)
        _output(result, json_fmt)


@cli.command()
@click.argument('market')
@click.argument('code')
@click.option('--json', 'json_fmt', is_flag=True, default=False, help='JSON 输出')
def auction(market, code, json_fmt):
    """竞价数据

    opentdx auction SZ 000001
    """
    with TdxClient() as c:
        result = c.stock_auction(_parse_market(market), code)
        _output(result, json_fmt)


# ==================== 扩展市场 ====================

@cli.command(name='g-kline')
@click.argument('market')
@click.argument('code')
@click.option('--period', default='DAILY', help='周期')
@click.option('--count', default=10, type=int, help='数量')
@click.option('--json', 'json_fmt', is_flag=True, default=False, help='JSON 输出')
def g_kline(market, code, period, count, json_fmt):
    """扩展市场K线（港股/美股/期货）

    opentdx g-kline US_STOCK TSLA --period DAILY --count 10
    opentdx g-kline HK_MAIN_BOARD 00700
    """
    with TdxClient() as c:
        result = c.goods_kline(_parse_market(market), code, _parse_period(period), count=count)
        _output(result, json_fmt)


@cli.command(name='g-quote')
@click.argument('codes')
@click.option('--json', 'json_fmt', is_flag=True, default=False, help='JSON 输出')
def g_quote(codes, json_fmt):
    """扩展市场报价

    opentdx g-quote "US_STOCK TSLA, HK_MAIN_BOARD 00700"
    """
    with TdxClient() as c:
        result = c.goods_quotes(_parse_codes(codes))
        _output(result, json_fmt)


# ==================== MAC 协议 ====================

@cli.command()
@click.argument('board_type', default='HY')
@click.option('--count', default=20, type=int, help='数量')
@click.option('--json', 'json_fmt', is_flag=True, default=False, help='JSON 输出')
def board(board_type, count, json_fmt):
    """板块列表

    opentdx board HY --count 10
    opentdx board DQ         (地区板块)
    opentdx board GN         (概念板块)
    opentdx board HK_ALL     (港股板块, 需扩展行情)
    opentdx board US_ALL     (美股板块, 需扩展行情)

    类型: HY/HY2/GN/FG/DQ/OTHER/YJ_LEVEL1/YJ_LEVEL2/YJ_LEVEL3/ALL
          HK_ALL/HK_GN/HK_HY/US_ALL/US_GN/US_HY
    """
    try:
        bt = getattr(BOARD_TYPE, board_type.upper())
        client = MacStandardClient()
    except AttributeError:
        try:
            bt = getattr(EX_BOARD_TYPE, board_type.upper())
            client = MacExtendedClient()
        except AttributeError:
            raise click.BadParameter(f"无效板块类型: {board_type}")

    client.connect()
    try:
        result = client.get_board_list(bt, count=count)
        _output(result, json_fmt)
    finally:
        client.disconnect()


@cli.command(name='board-members')
@click.argument('symbol', default='881001')
@click.option('--count', default=20, type=int, help='数量')
@click.option('--sort', default='CHANGE_PCT', help='排序字段 (CODE/PRICE/VOLUME/AMOUNT/CHANGE_PCT/TURNOVER_RATE/ACTIVITY)')
@click.option('--order', default='DESC', help='排序方向 (ASC/DESC/NONE)')
@click.option('--json', 'json_fmt', is_flag=True, default=False, help='JSON 输出')
def board_members(symbol, count, sort, order, json_fmt):
    """板块成分股行情

    opentdx board-members 880761 --count 10
    opentdx board-members 881394 --sort VOLUME --count 20
    opentdx board-members HK0281            (港股板块)
    opentdx board-members US0495            (美股板块)
    """
    from opentdx.const import SORT_TYPE, SORT_ORDER

    try:
        st = getattr(SORT_TYPE, sort.upper())
    except AttributeError:
        raise click.BadParameter(f"无效排序字段: {sort}")
    try:
        so = getattr(SORT_ORDER, order.upper())
    except AttributeError:
        raise click.BadParameter(f"无效排序方向: {order}")

    # 根据板块代码自动选择客户端
    if symbol.upper().startswith('HK') or symbol.upper().startswith('US'):
        client = MacExtendedClient()
    else:
        client = MacStandardClient()

    client.connect()
    try:
        result = client.get_board_members_quotes(symbol, count=count, sort_type=st, sort_order=so)
        _output(result, json_fmt)
    finally:
        client.disconnect()


@cli.command(name='s-bars')
@click.argument('market')
@click.argument('code')
@click.option('--period', default='DAILY', help='周期')
@click.option('--count', default=10, type=int, help='数量')
@click.option('--adjust', default='NONE', help='复权 (NONE/QFQ/HFQ)')
@click.option('--json', 'json_fmt', is_flag=True, default=False, help='JSON 输出')
def s_bars(market, code, period, count, adjust, json_fmt):
    """统一K线（A股/港股/美股通用）

    opentdx s-bars SZ 000001 --period DAILY --count 10
    opentdx s-bars HK_MAIN_BOARD 00700 --period DAILY
    opentdx s-bars US_STOCK TSLA --period WEEKLY --count 20
    """
    mkt = _parse_market(market)
    client = MacExtendedClient() if isinstance(mkt, EX_MARKET) else MacStandardClient()
    client.connect()
    try:
        result = client.get_symbol_bars(mkt, code, _parse_period(period),
                                        count=count, fq=_parse_adjust(adjust))
        _output(result, json_fmt)
    finally:
        client.disconnect()


@cli.command(name='s-quotes')
@click.argument('codes')
@click.option('--json', 'json_fmt', is_flag=True, default=False, help='JSON 输出')
def s_quotes(codes, json_fmt):
    """统一报价（A股/港股/美股通用，可自定义字段）

    opentdx s-quotes "SZ 000001, SH 600000"
    opentdx s-quotes "US_STOCK TSLA, HK_MAIN_BOARD 00700"
    """
    pairs = _parse_codes(codes)
    # 根据第一个 code 的市场类型选择客户端
    mkt = pairs[0][0]
    client = MacExtendedClient() if isinstance(mkt, EX_MARKET) else MacStandardClient()
    client.connect()
    try:
        result = client.get_symbol_quotes(pairs)
        _output(result['stocks'] if isinstance(result, dict) else result, json_fmt)
    finally:
        client.disconnect()


@cli.command()
@click.argument('market')
@click.option('--count', default=10, type=int, help='数量')
@click.option('--json', 'json_fmt', is_flag=True, default=False, help='JSON 输出')
def monitor(market, count, json_fmt):
    """主力监控

    opentdx monitor SH --count 10
    opentdx monitor SZ --count 20
    """
    client = MacStandardClient()
    client.connect()
    try:
        result = client.get_market_monitor(_parse_market(market), count=count)
        _output(result, json_fmt)
    finally:
        client.disconnect()


if __name__ == '__main__':
    cli()
