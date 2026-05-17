# Parser 模块解析器参考

> 所有解析器继承 `BaseParser`，通过 `@register_parser(msg_id, head)` 注册。
> `serialize()` 打包为 `header(11B) + msg_id(2B) + body`，`deserialize()` 解包响应。

---

## 一、quotation（标准行情协议，head=0）

### 1.1 连接与认证

| 文件 | 类名 | 命令 | 输入参数 | 输出字段 |
|---|---|---|---|---|
| [server.py](opentdx/parser/quotation/server.py) | `Login` | `0x000D` | 无（body: `\x01`） | `date_time: str`, `server_name: str(16s,GBK)`, `web_site: str(16s,GBK)`, `category: str(64s,GBK)` |
| | `Info` | `0x0015` | 无 | `delay: I`, `info: str(8s,GBK)`, `content: str(55s,GBK)`, `server_sign: str(10s,GBK)`, `time_now: datetime` |
| | `HeartBeat` | `0x0004` | 无 | `date: I(YYYYMMDD)` |
| | `ExchangeAnnouncement` | `0x0002` | 无 | `v: B`, `content: str(GBK)` |
| | `Announcement` | `0x000A` | 无（body: 54B填充） | `expire_date: date`, `title: str`, `author: str`, `content: str` |
| | `UpgradeTip` | `0x0FDB` | 无（body: 'tdxlevel'+22B） | `had: B`, `tips: str`, `link: str`, `msg: str` |
| | `TodoB` | `0x000B` | 无（body: 固定232B） | 原始数据（未解析） |
| | `TodoFDE` | `0x0FDE` | 无 | `unknown: [u1:I, u2:H, u4:hex]` |
| | `f264b` | `0x264B` | 无（body: 0,100） | 未实现 |
| | `f26ac` | `0x26AC` | 无（body: MAC地址） | 未实现 |
| | `f26ad` | `0x26AD` | 无（body: 含密钥） | 未实现 |
| | `f26ae` | `0x26AE` | 无（body: 0,100） | 未实现 |
| | `f26b1` | `0x26B1` | 无（body: 0,100,0） | 未实现 |

### 1.2 行情

| 文件 | 类名 | 命令 | 输入参数 | 输出字段 |
|---|---|---|---|---|
| [quotes.py](opentdx/parser/quotation/quotes.py) | `Quotes` | `0x054C` | `stocks: list[tuple[MARKET,str]]` | 继承 QuotesList 输出 |
| [quotes_list.py](opentdx/parser/quotation/quotes_list.py) | `QuotesList` | `0x054B` | `category: CATEGORY`<br>`start: int=0`<br>`count: int=80`<br>`sort_type: SORT_TYPE=CODE`<br>`reverse: bool=False`<br>`filter: list[FILTER_TYPE]=None` | `market: MARKET`, `code: str(GBK)`, `close: f(基价)`, `open=f(基价+delta)`, `high=f`, `low=f`, `pre_close=f`, `server_time: time`, `vol: 变长`, `cur_vol: 变长`, `amount: f`, `in_vol`, `out_vol`, `s_amount`, `open_amount`, `handicap.bid[1]: [{price,vol}]`, `handicap.ask[1]`, `rise_speed: h`, `short_turnover: h`, `min2_amount: f`, `opening_rush: h`, `vol_rise_speed: f`, `depth: f` |
| [quotes_detail.py](opentdx/parser/quotation/quotes_detail.py) | `QuotesDetail` | `0x053E` | `stocks: list[tuple[MARKET,str]]` | `market`, `code`, `close`, `open`, `high`, `low`, `pre_close`, `server_time`, `vol`, `cur_vol`, `amount`, `s_vol`, `b_vol`, `s_amount`, `open_amount`, `handicap.bid[5]`, `handicap.ask[5]`, `rise_speed: H`, `active1: H`, `active2: H` |
| [quotes_encrypt.py](opentdx/parser/quotation/quotes_encrypt.py) | `QuotesEncrypt` | `0x0547` | `stocks: list[tuple[MARKET,str]]` | 响应 XOR 0x93 解密。`market`, `code`, `active`, `close(基价)`, `pre_close`, `open`, `high`, `low`, `time: time`, `vol`, `cur_vol`, `amount: f`, `in_vol`, `out_vol`, `s_amount`, `open_amount`, `handicap.bid[5]`, `handicap.ask[5]`，末尾6组×4字段被丢弃 |

### 1.3 K线

| 文件 | 类名 | 命令 | 输入参数 | 输出字段 |
|---|---|---|---|---|
| [kline.py](opentdx/parser/quotation/kline.py) | `K_Line` | `0x0523` | `market: MARKET`<br>`code: str`<br>`period: PERIOD`<br>`times: int=1`<br>`start: int=0`<br>`count: int=800`<br>`adjust: ADJUST=NONE` | `datetime: datetime`, `open: 变长`, `close: 变长`, `high: 变长`, `low: 变长`, `vol: f`, `amount: f`, `up_count: H(可选)`, `down_count: H(可选)` |
| [kline_offset.py](opentdx/parser/quotation/kline_offset.py) | `K_Line_Offset` | `0x052D` | 参数同 K_Line | 指数专用差分解码：`datetime`, `open`, `close`, `high`, `low`, `vol`, `amount`, `up_count`, `down_count` |

### 1.4 分时与成交

| 文件 | 类名 | 命令 | 输入参数 | 输出字段 |
|---|---|---|---|---|
| [tick_chart.py](opentdx/parser/quotation/tick_chart.py) | `TickChart` | `0x0537` | `market: MARKET`<br>`code: str`<br>`start: int=0`<br>`count: int=0xba00` | `price: 变长(累积delta)`, `avg: 变长(累积delta)`, `vol: 变长` |
| [history_tick_chart.py](opentdx/parser/quotation/history_tick_chart.py) | `HistoryTickChart` | `0x0FEB` | `market: MARKET`<br>`code: str`<br>`date: date`（编码为**负**YYYYMMDD） | `price: 变长(累积delta)`, `avg: 变长(累积delta)`, `vol: 变长` |
| [transaction.py](opentdx/parser/quotation/transaction.py) | `Transaction` | `0x0FC5` | `market: MARKET`<br>`code: str`<br>`start: int`<br>`count: int` | `time: time`, `price: 变长(累积delta)`, `vol: 变长`, `trans: 变长`, `action: str(BUY/SELL/NEUTRAL)`, `unknown: 变长` |
| [history_transaction.py](opentdx/parser/quotation/history_transaction.py) | `HistoryTransaction` | `0x0FB5` | `market: MARKET`<br>`code: str`<br>`date: date`<br>`start: int`<br>`count: int` | `time: time`, `price: 变长(累积delta)`, `vol: 变长`, `action: str(BUY/SELL/NEUTRAL)`, `unknown: 变长` |
| [history_transaction_with_trans.py](opentdx/parser/quotation/history_transaction_with_trans.py) | `HistoryTransactionWithTrans` | `0x0FC6` | 同上 | 同上 + `num: 变长`（成交笔数），`buy_sell` 用 `<H` 解码 |
| [auction.py](opentdx/parser/quotation/auction.py) | `Auction` | `0x056A` | `market: MARKET`<br>`code: str`<br>`start: int=0`<br>`count: int=500` | `time: time`, `price: f`, `matched: I`, `unmatched: I` |
| [history_orders.py](opentdx/parser/quotation/history_orders.py) | `HistoryOrders` | `0x0FB4` | `market: MARKET`<br>`code: str`<br>`date: date` | `price: 变长(累积delta)`, `unknown: 变长(大单笔数?)`, `vol: 变长` |

### 1.5 列表与统计

| 文件 | 类名 | 命令 | 输入参数 | 输出字段 |
|---|---|---|---|---|
| [list.py](opentdx/parser/quotation/list.py) | `List` | `0x044D` | `market: MARKET`<br>`start: int=0`<br>`count: int=1600` | `code: str(6s,GBK)`, `vol: H`, `name: str(16s,GBK)`, `decimal_point: B`, `pre_close: f`, `unknown1: [H,H,H]` |
| [list2.py](opentdx/parser/quotation/list2.py) | `List2` | `0x0450` | `market: MARKET`<br>`start: int` | `code: str(6s,GBK)`, `vol: H`, `name: str(8s,GBK)`, `decimal_point: B`, `pre_close: f`, `unknown1: [H,H,H]` |
| [count.py](opentdx/parser/quotation/count.py) | `Count` | `0x044E` | `market: MARKET` | `count: H` |
| [stock.py](opentdx/parser/quotation/stock.py) | `f452` | `0x0452` | `start: int=0`<br>`count: int=2000` | `market: B→MARKET`, `code: str(从int)`, `p1: f`, `p2: f` |

### 1.6 指数

| 文件 | 类名 | 命令 | 输入参数 | 输出字段 |
|---|---|---|---|---|
| [index_info.py](opentdx/parser/quotation/index_info.py) | `IndexInfo` | `0x051D` | `market: MARKET`<br>`code: str` | `market: MARKET`, `code: str`, `active: H`, `pre_close: f`, `diff: f`, `close: f`, `open: f`, `high: f`, `low: f`, `vol: 变长`, `amount: f`, `up_count: 变长`, `down_count: 变长` |
| [index_momentum.py](opentdx/parser/quotation/index_momentum.py) | `IndexMomentum` | `0x051C` | `market: MARKET`<br>`code: str` | `[float,...]` 累积动量值列表 |

### 1.7 盘口与分析

| 文件 | 类名 | 命令 | 输入参数 | 输出字段 |
|---|---|---|---|---|
| [volume_profile.py](opentdx/parser/quotation/volume_profile.py) | `VolumeProfile` | `0x051A` | `market: MARKET`<br>`code: str` | `market`, `code`, `active`, `close(基价)`, `open`, `high`, `low`, `pre_close`, `server_time`, `vol`, `cur_vol`, `amount`, `in_vol(s_vol)`, `out_vol(b_vol)`, `s_amount`, `open_amount`, `handicap.bid[3]`, `handicap.ask[3]`, `vol_profile: [{price(累积delta), vol, buy, sell}]` |
| [top_board.py](opentdx/parser/quotation/top_board.py) | `TopBoard` | `0x053F` | `category: CATEGORY`<br>`size: int=20` | 8个排行榜：`increase`, `decrease`, `amplitude`, `rise_speed`, `fall_speed`, `vol_ratio`, `pos_commission_ratio`, `neg_commission_ratio`, `turnover`。每项：`{market, code: str, price: f, value: f}` |
| [chart_sampling.py](opentdx/parser/quotation/chart_sampling.py) | `ChartSampling` | `0x0FD1` | `market: MARKET`<br>`code: str` | `[float,...]` 采样价格点列表 |
| [unusual.py](opentdx/parser/quotation/unusual.py) | `Unusual` | `0x0563` | `market: MARKET`<br>`start: int`<br>`count: int=600` | `index: H`, `market: MARKET`, `code: str(GBK)`, `time: time`, `desc: str`, `value: str`, `unusual_type: B`, `v1: B`, `v2: f`, `v3: f`, `v4: f` |

### 1.8 公司信息

| 文件 | 类名 | 命令 | 输入参数 | 输出字段 |
|---|---|---|---|---|
| [company_info.py](opentdx/parser/quotation/company_info.py) | `Category` | `0x02CF` | `market: MARKET`<br>`code: str(UTF-8)` | `name: str(64s,GBK)`, `filename: str(80s,GBK)`, `start: I`, `length: I` |
| | `Content` | `0x02D0` | `market: MARKET`<br>`code: str(UTF-8)`<br>`filename: str`<br>`start: int`<br>`length: int` | `market: H`, `code: str`, `length: H`, `content: str(GBK)` |
| | `Finance` | `0x0010` | `market: MARKET`<br>`code: str(UTF-8)` | `liutongguben: f`, `province: H`, `industry: H`, `updated_date: I`, `ipo_date: I`, `zongguben: I`, `guojiagu: I`, `FaQiRenFaRenGu: f`, `FaRenGu: f`, `BGu: f`, `HGu: f`, `MeiGuShouYi: f`, `ZiChanZongJi: f`, `LiuDongZiChanZongJi: f`, `GuDingZiChanJinE: f`, `WuXingZiChan: f`, `GuDongRenShu: f`, `LiuDongFuZhaiHeJi: f`, `changqifuzhai: f`, `ZiBenGongJiJin: f`, `GuiMuQuanYiHeJi: f`, `YinYeZongShouRu: f`, `YinYeChengBen: f`, `YingShouZhangKuan: f`, `YinYeLiRun: f`, `TouZiShouYi: f`, `JingYinXianJinLiuJinE: f`, `zongxianjinliu: f`, `CunHuo: f`, `LiRunZongE: f`, `ShuiHouLiRun: f`, `GuiMuJinLiRun: f`, `WeiFenLiRun: f`, `MeiGuJinZiChan: f` |
| | `XDXR` | `0x000F` | `market: MARKET`<br>`code: str(UTF-8)` | `market: MARKET`, `code: str`, `date: datetime`, `name: str(类别)`, `fenhong: f(可选)`, `peigujia: f`, `songzhuangu: f`, `peigu: f`, `suogu: f`, `xingquanjia: f`, `fenshu: f`, `panqianliutong: f`, `qianzongguben: f`, `panhouliutong: f`, `houzongguben: f` |

### 1.9 文件传输

| 文件 | 类名 | 命令 | 输入参数 | 输出字段 |
|---|---|---|---|---|
| [file.py](opentdx/parser/quotation/file.py) | `Meta` | `0x02C5` | `file_name: str(GBK,40B)` | `size: I`, `hash_value: str(32s)`, `unknown1: 1s`, `unknown2: 1s` |
| | `Download` | `0x06B9` | `file_name: str(GBK)`<br>`start: int=0`<br>`size: int=0x7530` | `size: I`, `data: bytes` |

---

## 二、ex_quotation（扩展行情协议，head=1）

### 2.1 连接

| 文件 | 类名 | 命令 | 输入参数 | 输出字段 |
|---|---|---|---|---|
| [server.py](opentdx/parser/ex_quotation/server.py) | `Login` | `0x2454` | 无（body: 40B固定hex） | `date_time: str`, `server_name: str(21s,GBK)`, `desc: str(151s,GBK)`, `ip: str(52s,GBK)`, `unknown: [f,B,H,H,H,B,B,B]` |
| | `Info` | `0x2455` | 无 | `delay: I`, `info: str(25s,GBK)`, `version: str(29s,GBK)`, `server_sign: str(13s,GBK)`, `time_now: datetime`, `server_sign2: str(13s,GBK)`, `name: str(30s,GBK)` |

### 2.2 行情

| 文件 | 类名 | 命令 | 输入参数 | 输出字段 |
|---|---|---|---|---|
| [quotes.py](opentdx/parser/ex_quotation/quotes.py) | `Quotes` | `0x248A` | `code_list: list[tuple[EX_MARKET,str]]` | 每只股票314B，使用 `unpack_futures`：`market: B`, `code: str(23s,GBK)`, `active: I`, `pre_close: f`, `open: f`, `high: f`, `low: f`, `close: f`, `open_position: f(期货)`, `add_position: f`, `vol: I`, `curr_vol: I`, `amount: f`, `in_vol: I`, `out_vol: I`, `hold_position: I`, `handicap: {bid[5]:[{price,vol}], ask[5]}`, `settlement: f`, `avg: f`, `pre_settlement: f`, `pre_vol: f`, `day3_raise: f`, `date: I`, `raise_speed: f` |
| [quotes_single.py](opentdx/parser/ex_quotation/quotes_single.py) | `QuotesSingle` | `0x23FA` | `market: EX_MARKET`<br>`code: str(9B)` | 同上（code_len=9, 总301B） |
| [quotes_list.py](opentdx/parser/ex_quotation/quotes_list.py) | `QuotesList` | `0x2484` | `market: EX_MARKET`<br>`start: int=0`<br>`count: int=100`<br>`sortType: SORT_TYPE=CODE`<br>`reverse: bool=False` | 同上（继承 Quotes） |
| [quotes2.py](opentdx/parser/ex_quotation/quotes2.py) | `Quotes2` | `0x23FB` | `futures: list[tuple[EX_MARKET,str]]` | 同上（body含3148字段） |
| [goods.py](opentdx/parser/ex_quotation/goods.py) | `F23F6` | `0x23F6` | 无（body: 0,0,500） | 返回 `None`（仅日志） |
| | `F2487` | `0x2487` | `market: EX_MARKET`<br>`code: str(23B)` | `market`, `code`, `active: I`, `pre_close: f`, `open: f`, `high: f`, `low: f`, `vol: I`, `curr_vol: I`, `amount: f` |
| | `f2488` | `0x2488` | `market: EX_MARKET`<br>`code: str(23B)` | 返回 `None`（仅日志） |
| | `F2562` | `0x2562` | `market: int`<br>`start: int=0`<br>`count: int=600` | `name: str(23s,GBK)`, `category: H`, `index: I`, `switch: B`, `code: [f,f,f,H,H]` |

### 2.3 K线

| 文件 | 类名 | 命令 | 输入参数 | 输出字段 |
|---|---|---|---|---|
| [kline.py](opentdx/parser/ex_quotation/kline.py) | `K_Line` | `0x23FF` | `market: EX_MARKET`<br>`code: str(9B)`<br>`period: PERIOD`<br>`times: int=1`<br>`start: int=0`<br>`count: int=800` | `date_time: datetime`, `open: f`, `high: f`, `low: f`, `close: f`, `amount: f`, `vol: I`, `position: I`, `trade: I`, `price: f` |
| [kline2.py](opentdx/parser/ex_quotation/kline2.py) | `K_Line2` | `0x2489` | 同上（code: 23B, body含16B填充） | `time: datetime`, `open: f`, `high: f`, `low: f`, `close: f`, `amount: f`, `vol: I` |

### 2.4 分时与成交

| 文件 | 类名 | 命令 | 输入参数 | 输出字段 |
|---|---|---|---|---|
| [tick_chart.py](opentdx/parser/ex_quotation/tick_chart.py) | `TickChart` | `0x248B` | `market: EX_MARKET`<br>`code: str(23B)` | `time: time`, `price: f`, `avg: f`, `vol: I` |
| [history_tick_chart.py](opentdx/parser/ex_quotation/history_tick_chart.py) | `HistoryTickChart` | `0x248C` | `market: EX_MARKET`<br>`code: str(23B)`<br>`date: date` | `time: time`, `price: f`, `avg: f`, `vol: I` |
| [history_transaction.py](opentdx/parser/ex_quotation/history_transaction.py) | `HistoryTransaction` | `0x2412` | `market: EX_MARKET`<br>`code: str(43B)`<br>`date: date` | `time: time`, `price: I`, `vol: I`, `action: str(BUY/SELL/NEUTRAL)` |

### 2.5 列表与数据

| 文件 | 类名 | 命令 | 输入参数 | 输出字段 |
|---|---|---|---|---|
| [category_list.py](opentdx/parser/ex_quotation/category_list.py) | `CategoryList` | `0x23F4` | 无 | `goods_type: str(STOCK/HK/FUTURES/...)`, `name: str(32s,GBK)`, `code: B`, `abbr: str(30s,GBK)` |
| [list.py](opentdx/parser/ex_quotation/list.py) | `List` | `0x23F5` | `start: int`<br>`count: int` | `market: B`, `category: B`, `code: str(9s,GBK)`, `name: str(26s,GBK)`, `desc: [B,H,f,f,H,H,H,H,H,H,H,H]` |
| [count.py](opentdx/parser/ex_quotation/count.py) | `Count` | `0x23F0` | 无 | `count: I` |
| [chart_sampling.py](opentdx/parser/ex_quotation/chart_sampling.py) | `ChartSampling` | `0x254D` | `market: EX_MARKET`<br>`code: str(22B)` | `[float,...]` 采样价格点 |
| [table.py](opentdx/parser/ex_quotation/table.py) | `Table` | `0x2422` | `start: int=0`<br>`mode: int=1` | `(start: I, count: I, ctx: str(GBK))` |
| [table_detail.py](opentdx/parser/ex_quotation/table_detail.py) | `TableDetail` | `0x2423` | `start: int=0`<br>`mode: int=0` | 同上 |

### 2.6 文件传输

| 文件 | 类名 | 命令 | 输入参数 | 输出字段 |
|---|---|---|---|---|
| [file.py](opentdx/parser/ex_quotation/file.py) | `Meta` | `0x2458` | `file_name: str(40B,GBK)` | 同 quotation `Meta`：`size: I`, `hash: 32s` |
| | `Download` | `0x2459` | `file_name: str(40B,GBK)`<br>`start: int=0`<br>`size: int=0x7530` | 同 quotation `Download`：`size: I`, `data: bytes` |

---

## 三、mac_quotation（Mac平台协议，head=1）

### 3.1 初始化

| 文件 | 类名 | 命令 | 输入参数 | 输出字段 |
|---|---|---|---|---|
| [server_init.py](opentdx/parser/mac_quotation/server_init.py) | `ServerInit` | `0x120F` | 无（body: 固定hex+填充） | `today: date(YYYYMMDD)`, `sessions_1: [{open,close}×4]`（A股时段）, `sessions_2: [{open,close}×4]`（期货时段）, `last_trading_day: date`, `last_trading_day_2: date`, `market_param_1: I`, `market_param_2: I` |

### 3.2 行情

| 文件 | 类名 | 命令 | 输入参数 | 输出字段 |
|---|---|---|---|---|
| [symbol_quotes.py](opentdx/parser/mac_quotation/symbol_quotes.py) | `SymbolQuotes` | `0x122B` | `code_list: list[tuple[MARKET\|EX_MARKET,str]]`<br>`fields: FieldBit\|PresetField\|list=PresetField.COMMON` | `total: I`, `row_count: H`。每行：`market`, `code: str(22s,GBK)`, `name: str(44s,GBK)` + N个动态字段（由20B位图决定）。常用字段见位图表 |
| [symbol_info.py](opentdx/parser/mac_quotation/symbol_info.py) | `SymbolInfo` | `0x122A` | `market: MARKET\|EX_MARKET`<br>`code: str(22B)` | `name: str(44s,GBK)`, `date: date`, `time: time`, `activity: I`, `pre_close: f`, `open: f`, `high: f`, `low: f`, `close: f`, `momentum: f`, `vol: I`, `amount: I`, `inside_volume: I`, `outside_volume: I`, `decimal: H`, `turnover: f`, `avg: f` |
| [board_members_quotes.py](opentdx/parser/mac_quotation/board_members_quotes.py) | `BoardMembersQuotes` | `0x122C` | `board_symbol: str=881001`<br>`sort_type: SORT_TYPE=0xe`<br>`start: int=0`<br>`page_size: int=80`<br>`sort_order: SORT_ORDER=NONE`<br>`fields: 同上` | 每行 68B(`market+H22s+code+44s+name`) + 4B×N 动态字段。继承 SymbolQuotes 反序列化 |

### 3.3 K线

| 文件 | 类名 | 命令 | 输入参数 | 输出字段 |
|---|---|---|---|---|
| [symbol_bar.py](opentdx/parser/mac_quotation/symbol_bar.py) | `SymbolBar` | `0x122E` | `market: MARKET\|EX_MARKET`<br>`code: str(22B)`<br>`period: PERIOD`<br>`times: int=1`<br>`start: int=0`<br>`count: int=700`<br>`fq: ADJUST=NONE` | 头部：`name`, `decimal`, `category`, `vol_unit`, `industry`, `pre_close`, `open`, `high`, `low`, `close`, `momentum`, `vol`, `amount`, `turnover`, `avg`。每根K线：`datetime`, `open: f`, `high: f`, `low: f`, `close: f`, `vol: f`, `amount: f`, `float_shares: f` |
| [kline_offset.py](opentdx/parser/mac_quotation/kline_offset.py) | `KlineOffset` | `0x124A` | `offset: int(必须0)`<br>`count: int=128000` | `total: >I(大端序)`, `returned: <I`（返回为0，仅查询总数） |

### 3.4 分时与成交

| 文件 | 类名 | 命令 | 输入参数 | 输出字段 |
|---|---|---|---|---|
| [symbol_tick_chart.py](opentdx/parser/mac_quotation/symbol_tick_chart.py) | `SymbolTickChart` | `0x122D` | `market: MARKET\|EX_MARKET`<br>`code: str(22B)`<br>`query_date: date=None` | 每笔：`time: time(minutes)`, `price: f`, `avg: f`, `vol: I`, `momentum: f`。尾部：`name`, `decimal`, `category`, `vol_unit`, `pre_close`, `open`, `high`, `low`, `close`, `momentum`, `vol`, `amount`, `turnover`, `avg`, `industry` |
| [symbol_tick_charts.py](opentdx/parser/mac_quotation/symbol_tick_charts.py) | `TickCharts` | `0x123E` | `market: MARKET\|EX_MARKET`<br>`code: str(22B)`<br>`query_date: date=None`<br>`days: int=5` | 按日期分组：`date`, `pre_close`, `ticks: [{time, price: f, avg: f, vol: H}]`。尾部摘要同上 |
| [symbol_transaction.py](opentdx/parser/mac_quotation/symbol_transaction.py) | `SymbolTransaction` | `0x122F` | `market: MARKET\|EX_MARKET`<br>`code: str(22B)`<br>`count: int=1000`<br>`start: int=0`<br>`query_date: date=None` | `market`, `code`, `query_date`, `count: H`, `start: I`, `total: I`。每笔：`time: time(秒)`, `price: f`, `volume: I`, `trade_count: I`, `bs_flag: H`（0=买,1=卖,2=中性,5=盘后） |
| [symbol_auction.py](opentdx/parser/mac_quotation/symbol_auction.py) | `Auction` | `0x123D` | `market: MARKET\|EX_MARKET`<br>`code: str(22B)`<br>`start: int=0`<br>`count: int=500` | `market`, `code`, `count`。每笔：`time: time(秒)`, `price: f`, `matched: I`, `unmatched: i` |

### 3.5 板块

| 文件 | 类名 | 命令 | 输入参数 | 输出字段 |
|---|---|---|---|---|
| [board_list.py](opentdx/parser/mac_quotation/board_list.py) | `BoardList` | `0x1231` | `board_type: BOARD_TYPE\|EX_BOARD_TYPE=ALL`<br>`start: int=0`<br>`page_size: int=150` | `total: H`。每板块：`market`, `code: str(6s,GBK)`, `name: str(44s,GBK)`, `price: f`, `rise_speed: f`, `pre_close: f`。含顶部成分股：`symbol_market`, `symbol_code`, `symbol_name`, `symbol_price`, `symbol_rise_speed`, `symbol_pre_close` |
| [symbol_belong_board.py](opentdx/parser/mac_quotation/symbol_belong_board.py) | `SymbolBelongBoard` | `0x1218` | `symbol: str(8B)`<br>`market: MARKET` | JSON→DataFrame。9列：`board_type`, `market`, `board_symbol`, `board_symbol_name`, `close`, `pre_close`, `涨停数`, `跌停数`, `最相似`。13列模式含成分股信息 |

### 3.6 资金流向

| 文件 | 类名 | 命令 | 输入参数 | 输出字段 |
|---|---|---|---|---|
| [symbol_capital_flow.py](opentdx/parser/mac_quotation/symbol_capital_flow.py) | `SymbolCapitalFlow` | `0x1218`<br>(head=2) | `symbol: str(8B)`<br>`market: MARKET` | JSON→DataFrame：`今日主力流入`, `今日主力流出`, `今日散户流入`, `今日散户流出`, `5日主买`, `5日主卖`, `5日超大单净额`, `5日大单净额`, `5日中单净额`, `5日小单净额`。计算：`今日主力净流入`, `今日散户净流入`, `5日主力净流入` |

### 3.7 异动监控

| 文件 | 类名 | 命令 | 输入参数 | 输出字段 |
|---|---|---|---|---|
| [unusual.py](opentdx/parser/mac_quotation/unusual.py) | `Unusual` | `0x1237` | `market: MARKET`<br>`start: int`<br>`count: int=600` | `market: H`, `code: str(6s,GBK)`, `name: str(GBK,逗号分隔)`, `unusual_type: B`, `index: H`, `time: time`, `desc: str`, `value: str`, `v1: B`, `v2: f`, `v3: f`, `v4: f` |

### 3.8 文件传输

| 文件 | 类名 | 命令 | 输入参数 | 输出字段 |
|---|---|---|---|---|
| [file_query.py](opentdx/parser/mac_quotation/file_query.py) | `FileList` | `0x1215` | `filename: str(70B,GBK)`<br>`offset: int=0` | `offset: I`, `size: I`, `flag: b`, `hash: str(32s)` |
| | `FileDownload` | `0x1217` | `filename: str(70B,GBK)`<br>`index: int=1`<br>`offset: int=0`<br>`size: int=30000` | `index: I`, `size: I`, `content: str(GBK)\|hex` |

---

## 四、SymbolQuotes 字段位图参考

`symbol_quotes.py` 使用 20 字节位图动态选择返回字段。常用位：

| 位 | 名称 | 格式 | 说明 |
|---|---|---|---|
| 0x00 | pre_close | `<f` | 昨收 |
| 0x01 | open | `<f` | 开盘价 |
| 0x02 | high | `<f` | 最高价 |
| 0x03 | low | `<f` | 最低价 |
| 0x04 | close | `<f` | 收盘价 |
| 0x05 | vol | `<I` | 成交量 |
| 0x06 | vol_ratio | `<f` | 量比 |
| 0x07 | amount | `<f` | 成交额(万元) |
| 0x08 | inside_volume | `<I` | 内盘 |
| 0x09 | outside_volume | `<I` | 外盘 |
| 0x0A | total_shares | `<f` | 总股本(万) |
| 0x0B | float_shares | `<f` | 流通股(万) |
| 0x0C | eps | `<f` | 每股收益 |
| 0x0D | net_assets | `<f` | 净资产 |
| 0x0E | unknown_action_price | `<f` | 未知价 |
| 0x0F | total_market_cap_ab | `<f` | AB股总市值 |
| 0x10 | pe_dynamic | `<f` | 市盈率(动) |
| 0x11 | bid_price | `<f` | 买一价 |
| 0x12 | ask_price | `<f` | 卖一价 |
| 0x13 | server_update_date | `<I` | 服务器更新日期 |
| 0x14 | server_update_time | `<I` | 服务器更新时间 |
| 0x16 | board_strength | `<f` | 板块强度(涨跌家数差) |
| 0x17 | dividend_yield | `<f` | 每股股息(元) |
| 0x18 | bid_volume | `<I` | 买量 |
| 0x19 | ask_volume | `<I` | 卖量 |
| 0x1A | last_volume | `<I` | 现量 |
| 0x1B | turnover | `<f` | 换手率 |
| 0x1C | industry | `<I` | 行业代码 |
| 0x1F | decimal_point | `<I` | 数据精度 |
| 0x20 | buy_price_limit | `<f` | 涨停价 |
| 0x21 | sell_price_limit | `<f` | 跌停价 |
| 0x23 | lot_size | `<I` | 每手股数 |
| 0x25 | speed_pct | `<f` | 涨速 |
| 0x26 | avg_price | `<f` | 均价 |
| 0x27 | ipov | `<f` | IPOV |
| 0x28 | pe_ttm_vol_related | `<f` | 市盈率TTM（与vol相关） |
| 0x29 | ex_price_placeholder | `<f` | 收盘价占位（与amount相关） |
| 0x2A | operating_revenue | `<f` | 营业收入(万) |
| 0x2B | flag_kcb | `<I` | 科创板标志 |
| 0x2C | flag_bj | `<I` | 北交所标志 |
| 0x2E | after_hours_volume | `<i` | 盘后量 |
| 0x30 | pe_ttm | `<f` | 市盈率TTM |
| 0x31 | pe_static | `<f` | 市盈率(静) |
| 0x38 | main_net_amount | `<f` | 今日主力净流入 |
| 0x39 | bid_ask_ratio | `<f` | 委比（(买量-卖量)/(买量+卖量)*100%） |
| 0x3B | change_20d_pct | `<f` | 20日涨幅% |
| 0x3C | ytd_pct | `<f` | 年初至今% |
| 0x41 | change_1y_pct | `<f` | 一年涨幅% |
| 0x42 | prev_change_pct | `<f` | 昨涨幅% |
| 0x47 | prev2_change_pct | `<f` | 前日涨幅% |
| 0x4A | ah_code | `<I` | AH股对应代码 |
| 0x57 | open_amount | `<f` | 开盘金额 |
| 0x5B | dividend_yield_rate | `<f` | 股息率% |
| 0x5C | consecutive_up_days | `<i` | 连涨天（正数连涨，负数连跌） |
| 0x5D | limit_up_count / bid2_volume | `<I` | 涨停数(板块) / 买二量(个股) |
| 0x5E | limit_down_count / ask2_volume | `<I` | 跌停数(板块) / 卖二量(个股) |
| 0x5F | industry_sub | `<I` | 行业二级分类 |
| 0x66 | auction_buy_limit | `<f` | 连续竞价买入上限 |
| 0x67 | auction_sell_limit | `<f` | 连续竞价卖出下限 |
| 0x68 | vol_speed_pct | `<f` | 量涨速% |
| 0x69 | short_turnover_pct | `<f` | 短换手% |
| 0x6A | amount_2m | `<f` | 2分钟金额(元) |
| 0x6B | main_net_amount_copy | `<f` | 今日主力净流入(副本) |
| 0x6C | main_net_ratio | `<f` | 主力净比% |
| 0x6D | retail_net_amount | `<f` | 散户单增比 |
| 0x6E | main_net_5m_amount | `<f` | 5分钟主力净额 |
| 0x6F | main_net_3d_amount | `<f` | 近三日主力净额 |
| 0x70 | main_net_5d_amount | `<f` | 近五日主力净额 |
| 0x71 | main_net_10d_amount | `<f` | 近十日主买金额(待确定) |
| 0x72 | main_buy_net_amount | `<f` | 今日主买净额 |
| 0x73 | ddx | `<f` | DDX |
| 0x74 | ddy | `<f` | DDY |
| 0x75 | ddz | `<f` | DDZ |
| 0x76 | ddf | `<f` | DDF |
| 0x7A | auction_vol_ratio | `<f` | 竞价昨比 |
| 0x7B | prev_amount | `<f` | 昨成交额(元) |
| 0x7D | recent_indicator | `<f` | 近日指标提示(6:KDJ死叉, 92:阶段放量等) |
| 0x80 | bid3_price | `<f` | 买三价 |
| 0x81 | bid4_price | `<f` | 买四价 |
| 0x82 | bid5_price | `<f` | 买五价 |
| 0x83 | ask3_price | `<f` | 卖三价 |
| 0x84 | ask4_price | `<f` | 卖四价 |
| 0x85 | ask5_price | `<f` | 卖五价 |
| 0x86 | bid3_volume | `<I` | 买三量 |
| 0x87 | bid4_volume | `<I` | 买四量 |
| 0x88 | up_count / bid5_volume | `<I` | 上涨家数(板块) / 买五量(个股) |
| 0x89 | ask3_volume | `<I` | 卖三量 |
| 0x8A | ask4_volume | `<I` | 卖四量 |
| 0x8B | down_count / ask5_volume | `<I` | 下跌家数(板块) / 卖五量(个股) |
| 0x8C | bid_ask_diff | `<i` | 委差（买量-卖量） |
| 0x8D | change_up_type | `<i` | 封板状态(见 ChangeUpType 枚举) |
| 0x8E | stock_encode | `<i` | 股票特征编码(位图) |
| 0x8F | highlight_count | `<i` | 亮点数 |
| 0x90 | change_at_1000 | `<f` | 日内涨幅% 10:00 |
| 0x91 | change_at_1030 | `<f` | 日内涨幅% 10:30 |
| 0x92 | change_at_1100 | `<f` | 日内涨幅% 11:00 |
| 0x93 | change_at_1130 | `<f` | 日内涨幅% 11:30 |
| 0x94 | change_at_1330 | `<f` | 日内涨幅% 13:30 |
| 0x95 | change_at_1400 | `<f` | 日内涨幅% 14:00 |
| 0x96 | change_at_1430 | `<f` | 日内涨幅% 14:30 |

---

## 五、公共编码约定

| 类别 | 说明 |
|---|---|
| **文本编码** | 股票代码/名称/服务器字段均用 **GBK** 编码，解码后 `rstrip('\x00')` |
| **变长价格** | `get_price(data, pos)` 类似 UTF-8 的变长编码：6位数据 + 符号位 + 继续位 |
| **累积delta** | 逐笔成交/分时图的价格为累积差值：`last_price += delta`，首次非零时初始化 |
| **OHLC偏移** | quotes_list/quotes_detail 中 open/high/low/pre_close 相对于 close(基价) 编码 |
| **XOR加密** | 仅 `quotes_encrypt` 使用 `0x93` XOR 整个响应体 |
| **日期编码** | 通常为 YYYYMMDD 整数；`history_tick_chart` 使用**负**YYYYMMDD |
| **大端序** | 仅 `mac_quotation/kline_offset` 的 `total` 字段为 `>I` |
| **JSON响应** | `mac_quotation` 的 `symbol_belong_board` 和 `symbol_capital_flow` 返回 GBK JSON |
