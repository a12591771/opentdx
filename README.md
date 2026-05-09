# opentdx — Python TDX 量化行情数据接口

项目创意来自[`pytdx`](https://github.com/rainx/pytdx)

感谢[@rainx](https://github.com/rainx)迈出的第一步

### ✨ 声明

> 本项目为个人**学习项目，并非已完成的开箱即用的产品**，仅用于学习交流
>
> 对于数据有迫切需求的朋友，通达信新推出了[官方量化平台](https://help.tdx.com.cn/quant/)，建议食用。

> 由于项目连接的是通达信客户端明文公开的服务器，是财富趋势科技公司既有的行情软件兼容行情服务器，只是简单整理便于大家学习，**严禁**用于任何**商业用途**，更**严禁滥用接口**，对此造成的任何问题本人概不负责。

又因本项目在持续推进中，接口**难免会有大幅改动，带来的不便请予宽宥**。

> ### 应biner建议，本项目精简为基础数据接口库，mcp相关将移动到 [tdx_mcp](https://github.com/LisonEvf/tdx_mcp)
> ### 又因pytdx2库名rainx已经用了，因此本库改名为opentdx，再次致敬rainx
> ### 又又，协议基本完成解析了，后期就着力于 [tdx_mcp](https://github.com/LisonEvf/tdx_mcp)了和少量组合技接口


## 主要功能

| 功能 | 说明 |
|------|------|
| 股票行情 | A股、创业板、科创板、北交所 |
| 扩展行情 | 期货、港股、美股、期权等 |
| K线数据 | 多周期（1分/5分/日线/周线等），支持复权、即时换手率 |
| 分时图 | 实时/历史分时数据 |
| 排行榜 | 涨跌幅、振幅、换手率等 |
| 板块数据 | 行业/地区/概念板块列表及成分股，板块K线 |
| 异动监控 | 主力监控精灵数据 |
| F10资料 | 公司基本信息、财报、除权分红 |

## 安装

```bash
pip install opentdx
```

## 命令行

```bash
# 安装后即可使用 opentdx 命令
opentdx doc                              # 交互式接口文档（推荐入门）
opentdx mm                               # 实时市场异动监控
```

### A股行情

```bash
opentdx kline SZ 000001                  # K线（默认日线、10条）
opentdx kline SH 600519 --period DAILY --count 50 --adjust QFQ
opentdx kline SZ 000001 --period MIN_30 --count 20

opentdx quote "SZ 000001, SH 600000"     # 批量报价

opentdx index "SH 999999, SZ 399001"     # 指数信息

opentdx stock-list SZ --count 20         # 股票列表

opentdx unusual SZ --count 20            # 异动数据

opentdx transaction SZ 000001 --count 50 # 逐笔成交（实时）
opentdx transaction SZ 000001 --date 2026-03-03 --count 50  # 历史

opentdx tick SZ 000001                   # 分时图
opentdx tick SH 999999 --date 2026-03-16 # 历史分时

opentdx auction SZ 000001                # 竞价数据
```

### 扩展市场（港股/美股/期货）

```bash
opentdx g-kline US_STOCK TSLA --period DAILY --count 10
opentdx g-kline HK_MAIN_BOARD 00700

opentdx g-quote "US_STOCK TSLA, HK_MAIN_BOARD 00700"
```

### MAC 协议（板块 / 统一K线 / 主力监控）

```bash
opentdx board HY --count 10              # 行业板块
opentdx board DQ                          # 地区板块
opentdx board GN                          # 概念板块
opentdx board HK_ALL                      # 港股板块
opentdx board US_ALL                      # 美股板块

opentdx board-members 880761 --count 10   # 板块成分股行情
opentdx board-members 881394 --sort VOLUME --count 20
opentdx board-members HK0281              # 港股板块
opentdx board-members US0495              # 美股板块

opentdx s-bars SZ 000001 --period DAILY --adjust QFQ   # 统一K线（A股/港股/美股通用）
opentdx s-bars HK_MAIN_BOARD 00700 --period DAILY
opentdx s-bars US_STOCK TSLA --period WEEKLY

opentdx s-quotes "SZ 000001, SH 600000"   # 统一报价
opentdx s-quotes "US_STOCK TSLA, HK_MAIN_BOARD 00700"

opentdx monitor SH --count 10             # 主力监控
```

> 所有命令支持 `--json` 参数输出结构化数据，便于 AI / 脚本消费。

## 快速上手（Python）

```python
from datetime import date
import pandas as pd
from opentdx.tdxClient import TdxClient
from opentdx.const import MARKET, CATEGORY, EX_MARKET, PERIOD, SORT_TYPE

with TdxClient() as client:
    # 指数信息
    print(pd.DataFrame(client.index_info([(MARKET.SH, '999999'), (MARKET.SZ, '399001')])))
    # 股票列表（带排序过滤）
    print(pd.DataFrame(client.stock_quotes_list(CATEGORY.A, sortType=SORT_TYPE.TOTAL_AMOUNT)))
    # 股票报价
    print(pd.DataFrame(client.stock_quotes(MARKET.SZ, '000001')))
    # 获取行情全景
    for name, board in client.stock_top_board().items():
        print(f"榜单：{name}")
        print(pd.DataFrame(board))
    # 获取K线
    print(pd.DataFrame(client.stock_kline(MARKET.SZ, '000001', PERIOD.DAILY)))
    # 多分钟K线
    print(pd.DataFrame(client.stock_kline(MARKET.SH, '999999', PERIOD.MINS, times=10)))
    # 历史分时
    print(pd.DataFrame(client.stock_tick_chart(MARKET.SZ, '000001', date(2026, 3, 16))))
    # 个股F10
    print(pd.DataFrame(client.stock_f10(MARKET.SZ, '000001')))
    # 历史成交
    print(pd.DataFrame(client.stock_transaction(MARKET.SZ, '000001', date(2024, 1, 15))))

    # 期货K线
    print(pd.DataFrame(client.goods_kline(EX_MARKET.SH_FUTURES, 'AUL8', PERIOD.DAILY)))
    # 扩展市场行情列表
    print(pd.DataFrame(client.goods_quotes_list(EX_MARKET.SH_FUTURES, count=5)))
    # 美股K线
    print(pd.DataFrame(client.goods_kline(EX_MARKET.US_STOCK, 'TSLA', PERIOD.DAILY)))
    # 美股行情
    print(pd.DataFrame(client.goods_quotes(EX_MARKET.US_STOCK, 'TSLA')))
```

### MAC 协议（板块 / K线 / 逐笔成交 / 资金流向）

```python
from opentdx.client import macQuotationClient
from opentdx.const import MARKET, PERIOD, BOARD_TYPE, ADJUST

client = macQuotationClient()
client.connect()

# 板块列表
boards = client.get_board_list(BOARD_TYPE.HY)

# 板块成分股行情（按涨跌幅排序）
stocks = client.get_board_members_quotes('880761', count=10)

# 统一K线接口（A股/港股/美股通用）
bars = client.get_symbol_bars(MARKET.SZ, '000001', PERIOD.DAILY, count=100, fq=ADJUST.QFQ)

# 分时图
chart = client.get_symbol_tick_chart(MARKET.SZ, '000001')

# 多股实时行情
quotes = client.get_symbol_quotes([(MARKET.SZ, '000001'), (MARKET.SH, '600000')])

# 逐笔成交
tx = client.get_symbol_transactions(MARKET.SZ, '000001', count=50)

# 资金流向
flow = client.get_symbol_zjlx('000001', MARKET.SZ)

# 股票所属板块
belong = client.get_symbol_belong_board('000001', MARKET.SZ)

# 主力监控
monitor = client.get_market_monitor(MARKET.SH, count=10)

client.disconnect()
```

## 架构

```
opentdx/client/
    transport.py          Transport — 纯网络传输层 (连接/收发/心跳/重试)
    baseClient.py         BaseClient — 通用基础设施
    standardClient.py     StandardClient — A股行情
    extendedClient.py     ExtendedClient — 扩展市场行情
    macMixin.py           MacQuotationMixin — MAC 板块/K线/分时/成交方法
    macStandardClient.py  MacStandardClient — A股 + MAC 方法
    macExtendedClient.py  MacExtendedClient — 扩展市场 + MAC 方法
```

- `TdxClient` 内部使用 `MacStandardClient` + `MacExtendedClient`，一个连接覆盖所有接口
- MAC 方法直接可用，无需手动启用
- 旧类名（`QuotationClient` / `macQuotationClient` 等）保持兼容

### 亮点

- ✅ **CLI 工具**：`opentdx doc` 交互式接口文档，`opentdx mm` 实时异动监控
- ✅ **自动选服**：自动检测服务器连接速度，选择最快的服务器
- ✅ **MAC 协议**：统一 K线/分时/成交/板块接口，A股港股美股通用
- ✅ **主力监控**：市场异动实时推送
- ✅ **板块行情**：行业/地区/概念板块成分股行情，支持任意字段排序
- ✅ **扩展市场**：期货、期权、港股、美股等行情获取
- ✅ **资金流向**：主力/散户资金流向，日/5日维度


#量化交易 #TDX接口 #Python金融

---

[![Star History Chart](https://api.star-history.com/svg?repos=LisonEvf/opentdx&type=Date)](https://star-history.com/#LisonEvf/opentdx&Date)
