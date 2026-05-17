# opentdx — Python TDX 量化行情数据接口

项目创意来自 [`pytdx`](https://github.com/rainx/pytdx)

感谢 [@rainx](https://github.com/rainx) 迈出的第一步。

### ✨ 声明

> 本项目为个人**学习项目，并非已完成的开箱即用的产品**，仅用于学习交流。
>
> 对于数据有迫切需求的朋友，通达信新推出了[官方量化平台](https://help.tdx.com.cn/quant/)，建议食用。

> 由于项目连接的是通达信客户端明文公开的服务器，是财富趋势科技公司既有的行情软件兼容行情服务器，只是简单整理便于大家学习，**严禁**用于任何**商业用途**，更**严禁滥用接口**，对此造成的任何问题本人概不负责。

又因本项目在持续推进中，接口**难免会有大幅改动，带来的不便请予宽宥**。

> 应 biner 建议，本项目精简为基础数据接口库，MCP 相关将移动到 [tdx_mcp](https://github.com/LisonEvf/tdx_mcp)。

> 又因pytdx2库名rainx已经用了，因此本库改名为opentdx，再次致敬rainx。

> 又又，协议基本完成解析，后期着力于 MCP 和少量组合技接口。

---

## 安装

```bash
pip install opentdx
```

## 命令行

```bash
opentdx doc                              # 交互式接口文档（推荐入门）
opentdx mm                               # 实时市场异动监控
```

### A 股行情

```bash
opentdx kline SZ 000001                  # K线（默认日线、10条）
opentdx kline SH 600519 --period DAILY --count 50 --adjust QFQ
opentdx kline SZ 000001 --period MIN_30 --count 20

opentdx quote "SZ 000001, SH 600000"     # 批量报价
opentdx index "SH 999999, SZ 399001"     # 指数信息
opentdx stock-list SZ --count 20         # 股票列表
opentdx unusual SZ --count 20            # 异动数据

opentdx transaction SZ 000001 --count 50          # 逐笔成交（实时）
opentdx transaction SZ 000001 --date 2026-03-03   # 历史成交

opentdx tick SZ 000001                   # 分时图
opentdx tick SH 999999 --date 2026-03-16 # 历史分时
opentdx auction SZ 000001                # 竞价数据
```

### 扩展市场（港股 / 美股 / 期货）

```bash
opentdx g-kline US_STOCK TSLA --period DAILY --count 10
opentdx g-kline HK_MAIN_BOARD 00700
opentdx g-quote "US_STOCK TSLA, HK_MAIN_BOARD 00700"
```

### MAC 协议（板块 / 统一K线 / 主力监控）

```bash
opentdx board HY --count 10              # 行业板块
opentdx board GN                          # 概念板块
opentdx board HK_ALL                      # 港股板块
opentdx board US_ALL                      # 美股板块

opentdx board-members 880761 --count 10   # 板块成分股行情
opentdx board-members 881394 --sort VOLUME --count 20

opentdx s-bars SZ 000001 --period DAILY --adjust QFQ   # 统一K线
opentdx s-bars US_STOCK TSLA --period WEEKLY

opentdx s-quotes "SZ 000001, SH 600000"   # 统一报价
opentdx monitor SH --count 10             # 主力监控
```

> 所有命令支持 `--json` 参数输出结构化数据，便于 AI / 脚本消费。

---

## 快速上手（Python）

> 完整接口说明见 **[TdxClient 使用指南](doc/tdxclient_guide.md)**

> 底层 Client 高级用法见 **[高级开发指南](doc/advanced_client_guide.md)**。

```python
from datetime import date
import pandas as pd
from opentdx.tdxClient import TdxClient
from opentdx.const import MARKET, PERIOD, ADJUST, CATEGORY, SORT_TYPE, EX_MARKET

with TdxClient() as client:
    # ── A 股行情 ──
    df = pd.DataFrame(client.stock_kline(MARKET.SZ, '000001', PERIOD.DAILY, count=100))
    quotes = pd.DataFrame(client.stock_quotes(
        [(MARKET.SZ, '000001'), (MARKET.SH, '600000')]
    ))
    index = pd.DataFrame(client.index_info(MARKET.SH, '999999'))

    # 行情列表（排序 + 过滤）
    top = pd.DataFrame(client.stock_quotes_list(
        CATEGORY.A, count=50, sort_type=SORT_TYPE.CHANGE_PCT
    ))

    # ── 分时 / 成交 ──
    ticks = pd.DataFrame(client.stock_tick_chart(MARKET.SZ, '000001'))
    trades = pd.DataFrame(client.stock_transaction(MARKET.SZ, '000001'))
    history = pd.DataFrame(client.stock_tick_chart(
        MARKET.SZ, '000001', date=date(2026, 3, 16)
    ))

    # ── 多日分时 ──
    multi = client.stock_tick_charts(MARKET.SZ, '000001', days=5)

    # ── 板块 ──
    from opentdx.const import BOARD_TYPE, SORT_ORDER
    members = pd.DataFrame(client.stock_board_members(
        "881001", count=200,
        sort_type=SORT_TYPE.CHANGE_PCT, sort_order=SORT_ORDER.DESC,
    ))

    # ── 资金流向 ──
    flow = client.stock_capital_flow(MARKET.SZ, '000001')
    print(flow[['今日主力净流入', '5日主力净流入']])

    # ── 所属板块 ──
    boards = client.stock_belong_board(MARKET.SZ, '000001')

    # ── 主力监控 ──
    monitor = pd.DataFrame(client.stock_market_monitor(MARKET.SZ, count=50))

    # ── F10 / 异动 / 竞价 ──
    f10 = client.stock_f10(MARKET.SZ, '000001')
    unusual = client.stock_unusual(MARKET.SZ)
    auction = pd.DataFrame(client.stock_auction(MARKET.SZ, '300308'))

    # ── 扩展市场 ──
    us_kline = pd.DataFrame(client.goods_kline(
        EX_MARKET.US_STOCK, 'TSLA', PERIOD.DAILY, count=100
    ))
    hk_quotes = pd.DataFrame(client.goods_quotes(
        [(EX_MARKET.HK_MAIN_BOARD, '00700')]
    ))
```

---

## 文档

| 文档 | 面向 | 说明 |
|---|---|---|
| [TdxClient 使用指南](doc/tdxclient_guide.md) | 新接触本库的量化开发者 | TdxClient 全部接口、使用姿势、批量请求、pandas 配合 |
| [高级开发指南](doc/advanced_client_guide.md) | 熟悉本库的高级开发者 | 四个底层 Client 手动管理、协议直调、自定义字段、Transport 层 |
| [Parser 协议参考](doc/parser_reference.md) | 协议研究者 | 全部 parser 的命令号、输入输出字段、编码约定 |

---

## 架构

```
opentdx/
    tdxClient.py          TdxClient — 统一入口（一行代码覆盖所有市场）
    const.py              常量枚举（MARKET / PERIOD / CATEGORY / EX_MARKET …）

    client/
        transport.py          Transport — 网络传输层（连接/收发/心跳/重试）
        baseClient.py         BaseClient — 通用基础设施
        standardClient.py     StandardClient — A 股行情（quotation 协议）
        extendedClient.py     ExtendedClient — 扩展市场（ex_quotation 协议）
        macMixin.py           MacQuotationMixin — MAC 板块/K线/分时/成交方法集
        macStandardClient.py  MacStandardClient — A 股 + MAC
        macExtendedClient.py  MacExtendedClient — 扩展市场 + MAC

    parser/
        quotation/            标准行情协议解析器（~30 个）
        ex_quotation/         扩展行情协议解析器（~15 个）
        mac_quotation/        MAC 协议解析器（~17 个）

    utils/
        bitmap.py             FieldBit / PresetField — 动态字段选择
        help.py               辅助工具
        cache.py              流通股本缓存
```

- `TdxClient` 内部持有 `MacStandardClient` + `MacExtendedClient`，一个实例覆盖所有市场
- MAC 协议方法（板块/K线/分时/资金流向/主力监控）全部可用，无需额外配置
- 四层 Client 可独立使用，详见 [高级开发指南](doc/advanced_client_guide.md)

### 亮点

- **统一入口**：`TdxClient` 一行代码覆盖 A 股 + 期货 + 港股 + 美股
- **CLI 工具**：`opentdx doc` 交互式文档，`opentdx mm` 实时异动监控
- **MAC 协议**：统一 K线/分时/成交/板块接口，A 股港股美股通用
- **主力监控**：市场异动实时推送
- **板块行情**：行业/地区/概念板块成分股行情，支持任意字段排序
- **资金流向**：主力/散户资金流向，日/5 日维度
- **扩展市场**：期货、期权、港股、美股等行情获取
- **自动分页**：大批量数据自动分页请求，无需手动处理
- **自动选服**：自动检测服务器延迟，选择最快的主站
- **动态字段**：MAC 行情支持 `FieldBit` 按需选择返回字段，减少数据传输

#量化交易 #TDX接口 #Python金融

---

[![Star History Chart](https://api.star-history.com/svg?repos=LisonEvf/opentdx&type=Date)](https://star-history.com/#LisonEvf/opentdx&Date)
