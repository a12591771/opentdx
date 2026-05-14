# 底层 Client 高级用法

> 面向熟悉本库的高级量化开发者，介绍 4 个底层 Client 类的手动操作、连接管理、协议直调等高级技巧。

## 一、四个 Client 类的层次结构

```
BaseClient                                # 连接/传输/心跳/重试
├── StandardClient                        # A 股行情（quotation 协议）
│   └── MacStandardClient( + MacMixin)    # A 股 + MAC 板块/K线/分时
└── ExtendedClient                        # 扩展市场（ex_quotation 协议）
    └── MacExtendedClient( + MacMixin)    # 扩展市场 + MAC 协议
```

### 1.1 各自的能力边界

| 类 | 行情协议 | 板块/K线/分时 | 适用市场 |
|---|---|---|---|
| `StandardClient` | quotation (head=0) | 无 MAC | A 股 |
| `ExtendedClient` | ex_quotation (head=1) | 无 MAC | 期货/港股/美股 |
| `MacStandardClient` | quotation + MAC (head=1) | 有 | A 股 |
| `MacExtendedClient` | ex_quotation + MAC (head=1) | 有 | 扩展市场 |

### 1.2 选择建议

- **只做 A 股基础行情** → `StandardClient`
- **A 股 + 板块/资金流向/K线分时** → `MacStandardClient`
- **扩展市场 + MAC 功能** → `MacExtendedClient`
- **全都要** → `TdxClient`（内部持有后两者）

---

## 二、连接与生命周期

### 2.1 手动连接管理

```python
from opentdx.client.standardClient import StandardClient
from opentdx.client.macStandardClient import MacStandardClient

# StandardClient 使用主站地址（main_hosts）
c = StandardClient()
c.connect()       # 随机选择一台主站
c.login()
# ... 使用 ...
c.disconnect()

# MacStandardClient 使用 MAC 行情主站（mac_hosts）
mc = MacStandardClient()
mc.connect()
mc.login()
# ... 使用 ...
mc.disconnect()
```

### 2.2 指定 IP 连接

```python
c = StandardClient()
c.connect(ip='110.41.147.114', time_out=10)  # 指定 IP 和超时
c.login()
```

### 2.3 连接状态检测

```python
c = MacStandardClient()
print(c.connected)    # False
c.connect().login()
print(c.connected)    # True
print(c.ip, c.port)   # 当前连接的主站 IP 和端口
```

### 2.4 心跳机制

```python
# 开启心跳（5 分钟无操作自动断开前发送心跳包）
c = MacStandardClient(heartbeat=True)
c.connect().login()

# 访问心跳线程状态
print(c.heartbeat_thread)
```

### 2.5 多线程支持

```python
# 多线程模式（connect 时绑定 0.0.0.0，允许多个连接）
c = MacStandardClient(multithread=True)
c.connect()
```

### 2.6 自动重试

```python
c = MacStandardClient(auto_retry=True, raise_exception=False)
c.connect().login()

# 默认使用 DefaultRetryStrategy（4 次重试，间隔 0.1s→2s 递增）
# 自定义重试策略（需要实现 gen() 生成器方法）
class MyRetryStrategy:
    def gen(self):
        for _ in range(5):
            yield 15

c.retry_strategy = MyRetryStrategy()
```

---

## 三、StandardClient — A 股基础行情

### 3.1 可用接口

```python
from opentdx.client.standardClient import StandardClient
from opentdx.const import MARKET, PERIOD, ADJUST, CATEGORY, SORT_TYPE, BLOCK_FILE_TYPE
from datetime import date

c = StandardClient()
c.connect().login()

# ---- 概况 ----
c.get_count(MARKET.SZ)                                # 股票总数
c.get_list(MARKET.SZ, start=0, count=100)             # 股票列表

# ---- 行情 ----
c.get_quotes([(MARKET.SZ, '000001')])                 # 简略报价
c.get_stock_quotes_details(MARKET.SZ, '000001')       # 详细报价(5档)
c.get_stock_quotes_list(CATEGORY.A, count=200)        # 行情列表(排序)
c.get_stock_top_board(CATEGORY.A)                     # 排行榜

# ---- K线 ----
c.get_kline(MARKET.SZ, '000001', PERIOD.DAILY, count=100)
c.get_kline(MARKET.SZ, '000001', PERIOD.DAILY, adjust=ADJUST.QFQ)

# ---- 分时/成交 ----
c.get_tick_chart(MARKET.SZ, '000001')                 # 实时分时
c.get_tick_chart(MARKET.SZ, '000001', date=date(2026,3,16))  # 历史分时
c.get_transaction(MARKET.SZ, '000001')                # 逐笔成交
c.get_chart_sampling(MARKET.SZ, '000001')             # 分时缩略
c.get_auction(MARKET.SZ, '300308')                    # 集合竞价
c.get_history_orders(MARKET.SZ, '000001', date(2026,1,7))

# ---- 指数 ----
c.get_index_info([(MARKET.SH, '999999')])
c.get_index_momentum(MARKET.SZ, '399001')

# ---- 其他 ----
c.get_vol_profile(MARKET.SZ, '000001')                # 成交分布
c.get_unusual(MARKET.SZ, count=50)                    # 异动
c.get_company_info(MARKET.SZ, '000001')               # F10
c.get_block_file(BLOCK_FILE_TYPE.GN)                  # 板块文件
c.download_file('block_gn.dat')                       # 文件下载

c.disconnect()
```

### 3.2 价格精度处理

StandardClient 内部自动维护 `_decimal_map`（从股票列表缓存），`quotes_adjustment` 会根据 `decimal_point` 自动除权价格：

```python
# 内部逻辑：
# divisor = 10 ** decimal_point   (A股通常 decimal_point=2, divisor=100)
# price = raw_price / divisor
```

### 3.3 流通股本缓存

获取 K 线或行情时，`finance_cache` 自动缓存流通股本，避免重复请求 F10：

```python
from opentdx.utils.cache import finance_cache
# 缓存键格式: "{market.value}_{code}"
# 如: "0_000001" → float_shares
```

---

## 四、ExtendedClient — 扩展市场

### 4.1 可用接口

```python
from opentdx.client.extendedClient import ExtendedClient
from opentdx.const import EX_MARKET, PERIOD
from datetime import date

c = ExtendedClient()
c.connect().login()

# ---- 概况 ----
c.get_count()
c.get_category_list()
c.get_list(start=0, count=2000)

# ---- 行情 ----
c.get_quotes([(EX_MARKET.US_STOCK, 'TSLA')])
c.get_quotes_single(EX_MARKET.US_STOCK, 'TSLA')       # 单只
c.get_quotes2([(EX_MARKET.US_STOCK, 'TSLA')])          # 备用协议
c.get_quotes_list(EX_MARKET.US_STOCK, count=100)

# ---- K线/分时/成交 ----
c.get_kline(EX_MARKET.US_STOCK, 'TSLA', PERIOD.DAILY)
c.get_tick_chart(EX_MARKET.US_STOCK, 'TSLA')
c.get_history_transaction(EX_MARKET.US_STOCK, 'TSLA', date(2026, 3, 3))
c.get_chart_sampling(EX_MARKET.US_STOCK, 'TSLA')

# ---- 其他 ----
c.get_table()        # 表格数据
c.get_table_detail()
c.download_file('some_file.dat')
c.server_info()      # 服务器信息

c.disconnect()
```

### 4.2 服务器信息

```python
info = c.server_info()
# → {delay, info, version, server_sign, server_sign2, time_now, name}
```

---

## 五、MacStandardClient / MacExtendedClient — MAC 协议增强

这两个类继承 StandardClient/ExtendedClient 并混入 `MacQuotationMixin`，增加了板块、MAC K线、MAC 分时、资金流向等能力。

### 5.1 MAC 新增接口

```python
from opentdx.client.macStandardClient import MacStandardClient
from opentdx.const import MARKET, BOARD_TYPE, SORT_TYPE, SORT_ORDER

mc = MacStandardClient()
mc.connect().login()

# ---- 板块 ----
mc.get_board_list(BOARD_TYPE.ALL, count=10000)                  # 板块列表
mc.get_board_members_quotes("881001", count=200,                # 成分报价
    sort_type=SORT_TYPE.CHANGE_PCT, sort_order=SORT_ORDER.DESC)
mc.top_board_members("881001", count=20)                        # 活跃成分
mc.count_board_members("881001")                                # 成员数量

# ---- 个股归属 ----
mc.get_symbol_belong_board(symbol='000001', market=MARKET.SZ)   # 所属板块(DataFrame)
mc.get_symbol_zjlx(symbol='000001', market=MARKET.SZ)           # 资金流向(DataFrame)

# ---- MAC K线 ----
mc.get_symbol_bars(MARKET.SZ, '000001', PERIOD.DAILY, count=800)

# ---- MAC 行情 ----
mc.get_symbol_quotes([(MARKET.SZ, '000001')])                   # MAC 行情(支持fields)
mc.get_symbol_quotes([(MARKET.SZ, '000001')],
    fields=PresetField.ENHANCED)

# ---- MAC 分时/成交 ----
mc.get_symbol_tick_chart(MARKET.SZ, '000001')
mc.get_symbol_transactions(MARKET.SZ, '000001', count=2000)

# ---- MAC 竞价(字段更完整) ----
mc.get_auction(MARKET.SZ, '300308')

# ---- 多日分时 ----
mc.get_multi_tick_charts(MARKET.SZ, '000001', days=5)

# ---- 个股特征 ----
mc.get_symbol_info(MARKET.SZ, '000001')

# ---- K线偏移 ----
mc.get_kline_offset(count=128000)

# ---- 服务器信息 ----
mc.get_server_info()

# ---- 主力监控 ----
mc.get_market_monitor(MARKET.SZ, count=100)

# ---- 扩展市场品种列表 ----
mc.get_goods_list(market=30, count=600)

# ---- MAC 文件下载 ----
mc.download_mac_file('block_gn.dat')

mc.disconnect()
```

### 5.2 MacExtendedClient 的特殊之处

```python
from opentdx.client.macExtendedClient import MacExtendedClient

# MAC 扩展行情主站（mac_ex_hosts）
mec = MacExtendedClient()
mec.connect().login()

# 扩展市场接口（继承 ExtendedClient）+ MAC 协议（继承 MacMixin）
# 因此可以用 EX_MARKET 调用 MAC K线、MAC 分时等
mec.get_symbol_bars(EX_MARKET.US_STOCK, 'TSLA', PERIOD.DAILY)
mec.get_symbol_tick_chart(EX_MARKET.HK_MAIN_BOARD, '00700')
mec.get_goods_list(market=30)
```

---

## 六、协议直调 — `call()` 方法

所有 Client 类都暴露 `call(parser)` 方法，可以直接使用任何 parser。

```python
from opentdx.client.macStandardClient import MacStandardClient
from opentdx.parser.mac_quotation import SymbolInfo, Auction, TickCharts
from opentdx.const import MARKET

mc = MacStandardClient()
mc.connect().login()

# 直接调用 parser（绕过中间层）
result = mc.call(SymbolInfo(MARKET.SZ, '000001'))
auction = mc.call(Auction(MARKET.SZ, '300308'))
charts = mc.call(TickCharts(MARKET.SZ, '000001', days=5))

mc.disconnect()
```

适合场景：
- 测试新协议
- 需要原始反序列化数据（不经中间层加工）
- parser 参数与中间层默认值不同的场景

---

## 七、自定义行情字段（Fields / PresetField）

MAC 协议的 `SymbolQuotes` 和 `BoardMembersQuotes` 使用 20 字节位图动态选择返回字段，避免不必要的数据传输。

```
from opentdx.utils.bitmap import FieldBit, PresetField

# 使用预设（推荐）
fields = PresetField.COMMON     # 常用字段
fields = PresetField.ENHANCED   # 增强字段（含活跃度）
fields = PresetField.BOARD_STATS  # 板块统计（涨停数、跌停数、上涨家数、下跌家数）
fields = PresetField.HANDICAP   # 五档盘口（买卖5档价格+量）
fields = PresetField.FULL       # 全量字段

# 自定义字段组合（FieldBit 支持 + 运算符）
fields = FieldBit.CLOSE + FieldBit.VOL + FieldBit.AMOUNT + FieldBit.FLOAT_SHARES

# 或用 FieldSelection 直接构造
from opentdx.utils.bitmap import FieldSelection
fields = FieldSelection(FieldBit.CLOSE, FieldBit.VOL, FieldBit.AMOUNT)

# 传入行情请求
mc.get_symbol_quotes([(MARKET.SZ, '000001')], fields=fields)
mc.get_board_members_quotes("881001", fields=fields)
```

常用位值参见 [parser_reference.md](parser_reference.md) 第四节。

---

## 八、文件下载

MAC 协议的文件下载与 quotation/ex_quotation 协议不同，各有独立实现：

```
# StandardClient / ExtendedClient — quotation/ex_quotation 协议
c = StandardClient().connect().login()
data = c.download_file('block_gn.dat')           # → bytearray
text = c.get_text_file('block_gn.dat', sep='|')  # → list[list[str]]

# MacStandardClient / MacExtendedClient — MAC 协议
mc = MacStandardClient().connect().login()
data = mc.download_mac_file('block_gn.dat')      # → bytearray
```

内部机制：
1. `FileMeta` / `FileList` 获取文件元信息（size, hash）
2. 按块（quotation: 0x7530 / MAC: 30000）分段下载
3. `report_hook` 回调报告进度

---

## 九、Transport 层直接操作

Transport 是网络传输层，Client 通过 `_t` 属性暴露：

```python
mc = MacStandardClient()

# 切换服务器
mc._t.hosts = [
    ("自定义主站1", "10.0.0.1", 7709),
    ("自定义主站2", "10.0.0.2", 7709),
]

# 发送原始数据（不经过 parser）
mc._t.connect()
mc._t.send(b'\x0c\x00\x00\x00...')
mc._t.disconnect()

# 下载文件 — 使用 Client 封装，不建议直接调用 _t.download_file
# MAC 协议用 download_mac_file，quotation/ex_quotation 协议用 download_file
data = mc.download_mac_file('block_gn.dat')
```

---

## 十、选中合适的 Client 层次

| 需求 | 推荐类 |
|---|---|
| 简单获取 A 股数据 | `TdxClient` |
| 低频使用，不想管连接 | `TdxClient` (with) |
| A 股 + 板块/资金流向 | `TdxClient` 或 `MacStandardClient` |
| 只做期货/港股/美股 | `TdxClient` 或 `MacExtendedClient` |
| 需要控制连接生命周期 | 直接用底层 Client |
| 自定义心跳/重试策略 | 直接用底层 Client |
| 调试新协议 | 底层 Client + `call(parser)` |
| 高并发（单品种大批量） | `StandardClient` / `ExtendedClient`（轻量无 MAC） |
| 服务端常驻 | `MacStandardClient(heartbeat=True, auto_retry=True)` |

---

## 十一、Mixin 的协议兼容矩阵

`MacQuotationMixin` 中大部分方法同时支持 `MARKET` 和 `EX_MARKET`：

| 方法 | 支持 MARKET | 支持 EX_MARKET | 备注 |
|---|---|---|---|
| `get_symbol_bars` | 是 | 是 | |
| `get_symbol_tick_chart` | 是 | 是 | |
| `get_symbol_transactions` | 是 | 是 | |
| `get_symbol_quotes` | 是 | 是 | |
| `get_board_list` | 是 | 是 (EX_BOARD_TYPE) | |
| `get_symbol_zjlx` | 是 | 否 | 仅 A 股 |
| `get_market_monitor` | 是 | 否 | 仅 A 股 |
| `get_auction` | 是 | 是 | MAC 竞价 |
| `get_multi_tick_charts` | 是 | 是 | |
| `get_symbol_info` | 是 | 是 | |
| `get_goods_list` | — | — | 接收 int |

---

## 十二、线程安全与并发

```
import threading

# 方案1: 每线程一个 Client
def worker():
    c = StandardClient(multithread=True)
    c.connect().login()
    data = c.get_kline(MARKET.SZ, '000001', PERIOD.DAILY)
    c.disconnect()

threads = [threading.Thread(target=worker) for _ in range(4)]

# 方案2: TdxClient 单实例不保证线程安全，多线程各自创建
# 方案3: 单线程 + 批量请求通常已满足需求
```

---

## 十三、调试与日志

```python
from opentdx.utils.log import log
import logging

# 开启 DEBUG 级别日志
log.setLevel(logging.DEBUG)

# 日志会打印每次请求的 parser 名称和往返时间
```

配合 `parser_reference.md` 中的协议细节，可以深入调试网络问题或设计新的数据采集流程。
