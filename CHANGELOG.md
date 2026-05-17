# Changelog

所有值得关注的变化均记录于此。格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)。

## [0.2.5]

### Added

- **主力净比%**：`MAIN_NET_RATIO` (0x6C) 主力净比%
- **股息率%**：`DIVIDEND_YIELD_RATE` (0x5B) 股息率%，与每股股息(0x17)区分
- **亮点数**：`HIGHLIGHT_COUNT` (0x8F) 亮点数
- **昨成交额**：`PREV_AMOUNT` (0x7B) 昨成交额(元)
- **封板状态枚举**：`ChangeUpType` 枚举 + `CHANGE_UP_TYPE` (0x8D) 封板状态字段
- **日内时间涨幅**：`CHANGE_AT_1000`~`CHANGE_AT_1430` (0x90-0x96) 各时间节点日内涨幅
- **盘后量**：`AFTER_HOURS_VOLUME` (0x2E) 盘后量
- **过滤类型**：`FILTER_TYPE.HK_CONNECT`(16), `FILTER_TYPE.BJ`(32), `FILTER_TYPE.APPROVAL`(64), `FILTER_TYPE.REGISTRATION`(128)
- **排除位单测**：`test_count_board_members_exclude_bj`、`test_exclude_kc_consistency`

### Changed

- **字段注释**：`AUCTION_VOL_RATIO` (0x7A) 注释改为"竞价昨比"
- **字段注释**：`DIVIDEND_YIELD` (0x17) 注释改为"每股股息(元)"，与股息率%(0x5B)区分
- **统一过滤枚举**：删除 `BoardMemberFilter`，`FILTER_TYPE` 统一用于新旧协议（旧协议5位+MAC8位），修复 `FILTER_TYPE.BJ` 值 16→32
- **重命名**：`STOCK_FLAGS` → `STOCK_TAG_FLAGS`（股票[融][通][创]标签），`decode_stock_flags()` → `decode_stock_tag_flags()`
- **重命名**：`STOCK_ENCODE` → `SAFETY_SCORE`（确认该字段为通达信安全分，float编码范围1~100）
- **注释修正**：`HK_CONNECT` 改为"排除互联互通标的(仅核准制,注册制互联互通不受此位影响)"

### Removed

- **`BoardMemberFilter` 枚举**：合并至 `FILTER_TYPE`

### Changed

- **`goods_kline_by_date` / `get_history_instrument_bars_range` 日期参数柔性化**：`date1`/`date2` 现在同时接受 `int`（20230103）、`str`（`'2023-01-03'`）、`datetime.date` 三种形式，便于直接使用常见日期输入形式；低层 `KLineByDate` parser 仍只接受 int

### Fixed

- **`get_block_file()` 分块循环防护**：原代码直接对 `self.call(...)["data"]` 取值，若服务器单次分块返回 None 会抛出 `TypeError`；现在检查 chunk 合法性后才提取 `data`，失败时返回 `None` 并记录错误日志
- **`BLOCK_FILE_TYPE.HK` / `JJ` 支持网络下载**：`hkblock.dat` / `jjblock.dat` 与其他板块文件格式相同，通过标准 `Meta`(0x2c5) + `Download`(0x6b9) 协议从服务器获取，部分服务器提供，不可用时返回 `None`；`stock_block(BLOCK_FILE_TYPE.HK/JJ)` 同样支持
- **`stock_block()` 文档字段名纠错**：`BlockReader_TYPE_FLAT` 实际返回 `blockname / block_type / code_index / code`（平铺），文档原写的 `block_name / stocks: list[str]`（嵌套格式）已更正

## [0.2.5] - 2026-05-17

### Added

- **TdxClient 新接口（标准行情）**：`stock_xdxr` 除权除息记录、`stock_finance` 财务数据、`stock_company_info_category` F10目录、`stock_company_info_content` F10章节内容、`stock_report_file` 服务器文件下载（tdxfin 等）
- **TdxClient 新接口（扩展行情）**：`goods_kline_by_date` 日期范围 K 线（cmd 0x240d），支持期货/港股/美股
- **StandardClient 新方法**：`get_xdxr_info` / `get_finance_info` / `get_company_info_category` / `get_company_info_content`，将原本仅在 `get_company_info` 内部使用的 parser 独立暴露为公开接口
- **ExtendedClient 新方法**：`get_history_instrument_bars_range(market, code, date1, date2)` 日期范围 K 线
- **新 parser**：`ex_quotation.KLineByDate` (`@register_parser(0x240d, 1)`)，请求体 `B9sHII`（市场+代码+类型+起止日期），响应跳过 12 字节 echo 后读 count
- **BLOCK_FILE_TYPE**：新增 `HK = 'hkblock.dat'`、`JJ = 'jjblock.dat'`，通过网络协议下载，部分服务器提供

### Fixed

- **Bug**：`ex_quotation.HeartBeat` 缺失，扩展行情心跳线程启动后触发 `AttributeError`；在 `ex_quotation/server.py` 新增 `@register_parser(0x4, 1) class HeartBeat`，并导出至 `__init__.py`

## [0.2.4] - 2026-05-15

### Added

- **五档盘口字段**：识别并命名买卖2-5档价格字段 `BID2_PRICE~BID5_PRICE` (0x48,0x80-0x82)、`ASK2_PRICE~ASK5_PRICE` (0x49,0x83-0x85)
- **主力资金流字段**：`MAIN_NET_AMOUNT` (0x38) 今日主力净流入、`MAIN_NET_3D_AMOUNT` (0x6F) 近三日/`MAIN_NET_5D_AMOUNT` (0x70) 近五日/`MAIN_NET_10D_AMOUNT` (0x71) 近十日主力净额、`MAIN_BUY_NET_AMOUNT` (0x72) 今日主买净额
- **其他新字段**：`PREV2_CHANGE_PCT` (0x47) 前日涨幅%、`AUCTION_BUY_LIMIT`/`AUCTION_SELL_LIMIT` (0x66-0x67) 连续竞价上下限
- **新增预设**：`PresetField.HANDICAP` — 五档盘口（20个价格+量字段）、`PresetField.DEBUG` — 全FF位图探测
- **字段别名**：`BID2_VOLUME`/`ASK2_VOLUME`/`BID5_VOLUME`/`ASK5_VOLUME` 语义别名，与板块统计字段同值
- **字段副本**：`MAIN_NET_AMOUNT_COPY` (0x6B) 与 0x38 同值
- **DDX/DDY/DDZ/DDF 字段**：`DDX` (0x73)、`DDY` (0x74)、`DDZ` (0x75)、`DDF` (0x76) 大单动向系列指标
- **5分钟主力净额**：`MAIN_NET_5M_AMOUNT` (0x6E) 5分钟主力净额
- **散户单增比**：`RETAIL_NET_AMOUNT` (0x6D) 散户单增比
- **板块强度**：`BOARD_STRENGTH` (0x16) 板块强度(涨跌家数差)，仅板块指数有效

### Changed

- **字段重命名**：`BID`→`BID_PRICE` (0x11)、`ASK`→`ASK_PRICE` (0x12)、`LOW_COPY`→`BID2_PRICE` (0x48)、`LOW_COPY2`→`ASK2_PRICE` (0x49)、`AVG_PRICE_COPY`→`ASK5_PRICE` (0x85)、`UNKNOWN_CLOSE_PRICE`→`MAIN_NET_AMOUNT` (0x38)、`TODAY_INDICATOR`→`RECENT_INDICATOR` (0x7D)
- **字段注释**：`UP_COUNT/DOWN_COUNT/LIMIT_UP_COUNT/LIMIT_DOWN_COUNT` 更新为板块/个股双语义注释
- **未知字段命名**：从十进制 `unknown_field_71` 改为十六进制 `unknown_field_0x47`
- **单测修复**：`bid`/`ask` → `bid_price`/`ask_price`

---

## [0.2.3] - 2026-05-10

### Added

- **TdxClient 新接口**：`stock_board_list` / `stock_board_members` / `stock_board_top_members` 板块查询，`stock_belong_board` 个股所属板块，`stock_capital_flow` 资金流向，`stock_quotes_fields` 自定义字段行情，`stock_market_monitor` 主力监控增强版，`stock_tick_charts` 多日分时，`stock_kline_offset` K线偏移查询，`stock_symbol_info` 个股简要特征，`server_info` 交易日时段，`download_file` MAC文件下载，`goods_varieties` 扩展市场品种列表
- **MAC 协议解析器**：`GoodsList` (0x2562) 扩展市场品种列表，`ServerInfo` (0x120F) 交易日时段，`KlineOffset` (0x124A) K线偏移，`SymbolInfo` (0x122A) 个股特征，`Auction` (0x123D) MAC竞价，`TickCharts` (0x123E) 多日分时，`FileList` (0x1215) / `FileDownload` (0x1217) MAC文件下载
- **文档**：[TdxClient 使用指南](doc/tdxclient_guide.md)、[高级开发指南](doc/advanced_client_guide.md)

### Changed

- README 全面更新：修复过时 API 引用，补充完整 Python 示例，添加文档索引
- CHANGELOG 补全 0.2.1 以来的所有改动

### Fixed

- 用户文档中的代码示例经真实运行验证，修复 8 处误导性错误（缺少 import、关键字参数错误、错误 API 用法等）

---

## [0.2.2] - 2026-05-05

### Added

- **新协议**：竞价 (`Auction` 0x123D)、多日分时 (`TickCharts` 0x123E)、文件下载 (`FileList` 0x1215 / `FileDownload` 0x1217)、个股特征 (`SymbolInfo` 0x122A)
- **MAC 扩展市场**：`GoodsList` (0x2562) 期货/期权品种列表
- **CLI 命令接口**：新增 `opentdx mm` 主力监控、扩展 `opentdx board` 支持港股美股

### Changed

- **Client 重构**：四层 Client 架构确立 — `StandardClient` → `MacStandardClient`(+MacMixin)，`ExtendedClient` → `MacExtendedClient`(+MacMixin)
- **CLI 重构**：命令模块从 `doc.py` 重命名为 `commands/doc_demo.py`，新增 `commands/market_monitor.py`
- **Bitmap 重构**：`FieldBit` 自带 fmt/desc，`PresetField` 新增 `BOARD_STATS`，新增 15+ 字段映射 (`up_count`/`down_count`/`vol_speed_pct` 等)
- **主力监控增强**：补充 v1~v4 字段，支持异常处理逻辑

### Fixed

- `SymbolBar` 底层返回 dict，中间层同步修改
- 变量名修正：`symbol` → `code`，`bars` → `charts`
- `count_board_members` 多余 `filter` 参数报错修复
- `@register_parser(0x122B, 1)` 必须 `head=1` 才支持扩展市场
- 单位问题：金额字段统一为元
- 分页查询 / 返回 list 格式修正

---

## [0.2.1] - 2026-04-30

### Added

- 新增 bitmap 字段：`limit_up_count`/`limit_down_count` (涨跌停数), `up_count`/`down_count` (上涨/下跌家数), `vol_speed_pct` (量涨速%), `short_turnover_pct` (短换手%), `auction_vol_ratio` (竞价量比) 等
- 新增预设 `PresetField.BOARD_STATS`
- 新增命令 `opentdx mm` 主力监控查询

### Changed

- 金额字段单位说明：`amount`/`open_amount`/`amount_2m` 返回**元**

---

## [0.2.0] - 2026-04-29

### Added

- 统一 K 线接口 `get_symbol_bars`，A 股/港股/美股通用
- 板块查询：`get_board_list` / `get_board_members_quotes` / `count_board_members`
- 资金流向：`get_symbol_zjlx`，日/5 日维度
- 主力监控：`get_market_monitor`，支持 v1~v4 字段
- 统一报价：`get_symbol_quotes`，支持 `FieldBit` 动态字段
- 逐笔成交：`get_symbol_transactions`，支持实时/历史
- 分时图：`get_symbol_tick_chart`，支持实时/历史
- 行业枚举类，5 位行业代码转 `board_symbol`
- `top_board_members` 活跃度排序
- `EX_BOARD_TYPE` 港股/美股板块类型
- `SORT_TYPE` 扩展 60+ 排序字段

### Changed

- `MacQuotationMixin` 混入模式，避免同时维护两份代码
- 板块查询默认 `count` 增加到 100000

---

## [0.1.2] - 2026-04-18

### Added

- 命令行 `opentdx doc` 交互式接口文档
- `BLOCK_FILE_TYPE` 板块文件下载
- `StandardClient` / `ExtendedClient` 标准化接口
- `TdxClient` 统一入口封装
- 类型注解支持

### Changed

- 项目重构为 `opentdx` 基础数据源库
- parser 模块拆分（quotation / ex_quotation / mac_quotation）
- 单元测试改为真实连通测试
- `EX_CATEGORY` 重命名为 `EX_MARKET`

---

## [0.1.0] - 2026-04-10

### Added

- K 线复权支持（前复权/后复权/不复权）
- 换手率自动计算（缓存流通股本）
- 集合竞价协议
- 板块列表协议
- 行情加密解析器 `QuotesEncrypt`
- 成交分布、分时图、历史分时图等协议
- MCP 资源和指标计算工具

### Changed

- 项目结构重组，支持 pip 安装发布到 PyPI
- 统一命名和编码风格

### Fixed

- 心跳线程不能正常结束
- `get_kline()` 成交量单位（股 vs 手）
- IPv6 支持

---

## [0.0.1] - 2026-03-28

### Added

- 初始版本，基于 `pytdx` 协议解析
- A 股行情、K 线、分时、成交等基础协议
- 扩展市场（港股/美股/期货）基础协议
