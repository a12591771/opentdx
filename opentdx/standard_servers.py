"""行情服务器能力探测、缓存与客户端分配。"""

from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Sequence

from opentdx.const import (
    BOARD_TYPE,
    MARKET,
    PERIOD,
    mac_hosts,
    main_hosts,
)
from opentdx.utils.log import log

if TYPE_CHECKING:
    from opentdx.client.macStandardClient import MacStandardClient
    from opentdx.client.standardClient import StandardClient


Server = tuple[str, str, int]

CAPABILITY_TRANSPORT = "transport.connect"
CAPABILITY_LOGIN = "quotation.login"
CAPABILITY_STANDARD_DAILY_KLINE = "quotation.kline.daily"
CAPABILITY_STANDARD_MINUTE_KLINE = "quotation.kline.minute"
CAPABILITY_STANDARD_AUCTION = "quotation.auction"
CAPABILITY_MAC_SERVER_INFO = "mac.server_info"
CAPABILITY_MAC_SYMBOL_BARS = "mac.symbol_bars"
CAPABILITY_MAC_SYMBOL_TRANSACTIONS = "mac.symbol_transactions"
CAPABILITY_MAC_SYMBOL_QUOTES = "mac.symbol_quotes"
CAPABILITY_MAC_SYMBOL_TICK_CHART = "mac.symbol_tick_chart"
CAPABILITY_MAC_BOARD_LIST = "mac.board_list"
CAPABILITY_MAC_BOARD_MEMBERS = "mac.board_members"
CAPABILITY_MAC_SYMBOL_BELONG_BOARD = "mac.symbol_belong_board"
CAPABILITY_MAC_SYMBOL_INFO = "mac.symbol_info"
CAPABILITY_MAC_CAPITAL_FLOW = "mac.capital_flow"
CAPABILITY_MAC_MARKET_MONITOR = "mac.market_monitor"
CAPABILITY_MAC_AUCTION = "mac.auction"
CAPABILITY_MAC_STANDARD = "mac.standard"

STANDARD_REQUIRED_CAPABILITIES = (
    CAPABILITY_LOGIN,
    CAPABILITY_STANDARD_DAILY_KLINE,
    CAPABILITY_STANDARD_MINUTE_KLINE,
)
MAC_STANDARD_REQUIRED_CAPABILITIES = (
    CAPABILITY_MAC_SERVER_INFO,
    CAPABILITY_MAC_SYMBOL_BARS,
    CAPABILITY_MAC_SYMBOL_TRANSACTIONS,
    CAPABILITY_MAC_SYMBOL_QUOTES,
    CAPABILITY_MAC_SYMBOL_TICK_CHART,
    CAPABILITY_MAC_BOARD_LIST,
    CAPABILITY_MAC_BOARD_MEMBERS,
    CAPABILITY_MAC_SYMBOL_BELONG_BOARD,
    CAPABILITY_MAC_SYMBOL_INFO,
    CAPABILITY_MAC_CAPITAL_FLOW,
    CAPABILITY_MAC_MARKET_MONITOR,
    CAPABILITY_MAC_AUCTION,
)

DEFAULT_CACHE_PATH = Path.home() / ".cache" / "opentdx" / "standard_servers.json"
DEFAULT_CACHE_TTL = timedelta(days=7)
DEFAULT_CANDIDATE_LIMIT: int | None = None
DEFAULT_MAX_WORKERS = 4
_CACHE_VERSION = 2
_PROBE_CODE = "000001"
_PROBE_MARKET = MARKET.SZ


def _merge_candidates(*groups: Sequence[Server]) -> tuple[Server, ...]:
    merged: list[Server] = []
    seen: set[tuple[str, int]] = set()
    for group in groups:
        for server in group:
            key = (server[1], server[2])
            if key in seen:
                continue
            seen.add(key)
            merged.append(server)
    return tuple(merged)


DEFAULT_CANDIDATES = _merge_candidates(main_hosts, mac_hosts)
_MAIN_ADDRESSES = {(server[1], server[2]) for server in main_hosts}
_MAC_ADDRESSES = {(server[1], server[2]) for server in mac_hosts}


@dataclass(frozen=True, slots=True)
class StandardServer:
    """单台行情服务器的完整能力探测记录。"""

    name: str
    host: str
    port: int
    latency_ms: float | None
    capabilities: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    sources: tuple[str, ...] = ()

    @property
    def address(self) -> Server:
        """返回行情客户端可直接绑定的服务器三元组。"""
        return (self.name, self.host, self.port)

    def supports(self, *capabilities: str) -> bool:
        """判断服务器是否同时支持指定能力。"""
        available = set(self.capabilities)
        return all(capability in available for capability in capabilities)

    @classmethod
    def from_mapping(cls, value: object) -> "StandardServer":
        if not isinstance(value, dict):
            raise ValueError("服务器缓存条目必须是对象")
        name = value.get("name")
        host = value.get("host")
        port = value.get("port")
        latency_ms = value.get("latency_ms")
        capabilities = value.get("capabilities", [])
        errors = value.get("errors", [])
        sources = value.get("sources", [])
        if not isinstance(name, str) or not isinstance(host, str):
            raise ValueError("服务器缓存缺少名称或地址")
        if not isinstance(port, int) or isinstance(port, bool):
            raise ValueError("服务器缓存端口无效")
        if latency_ms is not None and (
            not isinstance(latency_ms, (int, float)) or isinstance(latency_ms, bool)
        ):
            raise ValueError("服务器缓存延迟无效")
        for label, items in (
            ("能力", capabilities),
            ("错误", errors),
            ("来源", sources),
        ):
            if not isinstance(items, list) or not all(
                isinstance(item, str) for item in items
            ):
                raise ValueError(f"服务器缓存{label}列表无效")
        return cls(
            name,
            host,
            port,
            float(latency_ms) if latency_ms is not None else None,
            tuple(capabilities),
            tuple(errors),
            tuple(sources),
        )


def _ttl_seconds(cache_ttl: float | timedelta) -> float:
    seconds = (
        cache_ttl.total_seconds() if isinstance(cache_ttl, timedelta) else cache_ttl
    )
    if seconds < 0:
        raise ValueError("cache_ttl 不能为负数")
    return float(seconds)


def _read_cache(
    cache_path: Path, cache_ttl: float | timedelta
) -> tuple[StandardServer, ...] | None:
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        if payload.get("version") != _CACHE_VERSION:
            return None
        created_at = payload["created_at"]
        if not isinstance(
            created_at, (int, float)
        ) or time.time() - created_at > _ttl_seconds(cache_ttl):
            return None
        servers = tuple(
            StandardServer.from_mapping(item) for item in payload["servers"]
        )
        return servers or None
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None


def _write_cache(cache_path: Path, servers: Sequence[StandardServer]) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": _CACHE_VERSION,
        "created_at": time.time(),
        "servers": [asdict(server) for server in servers],
    }
    cache_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _server_sources(server: Server) -> tuple[str, ...]:
    key = (server[1], server[2])
    sources: list[str] = []
    if key in _MAIN_ADDRESSES:
        sources.append("main_hosts")
    if key in _MAC_ADDRESSES:
        sources.append("mac_hosts")
    return tuple(sources or ["custom"])


def _latest_trade_date(rows: Sequence[dict[str, object]]) -> date | None:
    if not rows:
        return None
    row = rows[-1]
    raw_value = row.get("trade_date") or row.get("date") or row.get("datetime")
    if isinstance(raw_value, datetime):
        return raw_value.date()
    if isinstance(raw_value, date):
        return raw_value
    if isinstance(raw_value, str):
        try:
            return date.fromisoformat(raw_value[:10])
        except ValueError:
            return None
    return None


def _call_mac_auction(client: "MacStandardClient") -> object:
    """绕过 StandardClient 同名方法，显式验证 MAC Auction 命令。"""
    from opentdx.client.macMixin import MacQuotationMixin

    return MacQuotationMixin.get_auction(
        client, _PROBE_MARKET, _PROBE_CODE, start=0, count=1
    )


def _mac_probe_calls(
    trade_date: date | None,
) -> tuple[tuple[str, Callable[["MacStandardClient"], object]], ...]:
    calls: list[tuple[str, Callable[["MacStandardClient"], object]]] = [
        (CAPABILITY_MAC_SERVER_INFO, lambda client: client.get_server_info()),
        (
            CAPABILITY_MAC_SYMBOL_BARS,
            lambda client: client.get_symbol_bars(
                _PROBE_MARKET, _PROBE_CODE, PERIOD.DAILY, count=1
            ),
        ),
        (
            CAPABILITY_MAC_SYMBOL_QUOTES,
            lambda client: client.get_symbol_quotes([(_PROBE_MARKET, _PROBE_CODE)]),
        ),
        (
            CAPABILITY_MAC_BOARD_LIST,
            lambda client: client.get_board_list(BOARD_TYPE.HY, count=1),
        ),
        (
            CAPABILITY_MAC_BOARD_MEMBERS,
            lambda client: client.get_board_members_quotes("881001", count=1),
        ),
        (
            CAPABILITY_MAC_SYMBOL_BELONG_BOARD,
            lambda client: client.get_symbol_belong_board(_PROBE_CODE, _PROBE_MARKET),
        ),
        (
            CAPABILITY_MAC_SYMBOL_INFO,
            lambda client: client.get_symbol_info(_PROBE_MARKET, _PROBE_CODE),
        ),
        (
            CAPABILITY_MAC_CAPITAL_FLOW,
            lambda client: client.get_symbol_zjlx(_PROBE_CODE, _PROBE_MARKET),
        ),
        (
            CAPABILITY_MAC_MARKET_MONITOR,
            lambda client: client.get_market_monitor(_PROBE_MARKET, start=0, count=1),
        ),
        (CAPABILITY_MAC_AUCTION, _call_mac_auction),
    ]
    if trade_date is not None:
        calls.extend(
            [
                (
                    CAPABILITY_MAC_SYMBOL_TRANSACTIONS,
                    lambda client: client.get_symbol_transactions(
                        _PROBE_MARKET,
                        _PROBE_CODE,
                        count=1,
                        query_date=trade_date,
                    ),
                ),
                (
                    CAPABILITY_MAC_SYMBOL_TICK_CHART,
                    lambda client: client.get_symbol_tick_chart(
                        _PROBE_MARKET,
                        _PROBE_CODE,
                        query_date=trade_date,
                    ),
                ),
            ]
        )
    return tuple(calls)


def _run_mac_probe(
    server: Server,
    connect_timeout: float,
    call: Callable[["MacStandardClient"], object],
) -> object:
    from opentdx.client.macStandardClient import MacStandardClient

    client = MacStandardClient(server=server, raise_exception=True)
    try:
        if client.connect(ip=server[1], time_out=max(1, int(connect_timeout))) is None:
            raise ConnectionError("连接失败")
        if client.login() is not True:
            raise ConnectionError("登录失败")
        return call(client)
    finally:
        if client.connected:
            client.disconnect()


def _probe_mac_capabilities(
    server: Server, trade_date: date | None, connect_timeout: float
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """逐接口验证 MAC A 股能力；每个接口使用独立连接隔离超时。"""
    capabilities: list[str] = []
    errors: list[str] = []
    calls = _mac_probe_calls(trade_date)
    gates = {
        CAPABILITY_MAC_SERVER_INFO,
        CAPABILITY_MAC_SYMBOL_BARS,
        CAPABILITY_MAC_SYMBOL_TRANSACTIONS,
    }

    def record_probe(
        capability: str, call: Callable[["MacStandardClient"], object]
    ) -> None:
        try:
            result = _run_mac_probe(server, connect_timeout, call)
            if result is None:
                raise ValueError("返回 None")
            capabilities.append(capability)
        except Exception as exc:
            errors.append(f"{capability}: {type(exc).__name__}: {exc}")

    gate_calls = tuple(item for item in calls if item[0] in gates)
    remaining = tuple(item for item in calls if item[0] not in gates)
    for capability, call in gate_calls:
        record_probe(capability, call)

    if not capabilities:
        return (), tuple(errors)

    for capability, call in remaining:
        record_probe(capability, call)

    if all(
        capability in capabilities for capability in MAC_STANDARD_REQUIRED_CAPABILITIES
    ):
        capabilities.append(CAPABILITY_MAC_STANDARD)
    return tuple(capabilities), tuple(errors)


def _probe_standard_server(server: Server, connect_timeout: float) -> StandardServer:
    """独立探测单台服务器的标准协议和 MAC 协议能力。"""
    from opentdx.client.standardClient import StandardClient

    name, host, port = server
    capabilities: list[str] = []
    errors: list[str] = []
    latency_ms: float | None = None
    trade_date: date | None = None
    client = StandardClient(server=server, raise_exception=True)
    started_at = time.perf_counter()
    try:
        if client.connect(time_out=max(1, int(connect_timeout))) is None:
            errors.append("transport.connect: ConnectionError: 连接失败")
            return StandardServer(
                name,
                host,
                port,
                None,
                errors=tuple(errors),
                sources=_server_sources(server),
            )
        capabilities.append(CAPABILITY_TRANSPORT)
        if client.login() is not True:
            errors.append("quotation.login: ConnectionError: 登录失败")
        else:
            capabilities.append(CAPABILITY_LOGIN)
            latency_ms = (time.perf_counter() - started_at) * 1000
            try:
                daily = client.get_kline(
                    _PROBE_MARKET, _PROBE_CODE, PERIOD.DAILY, count=1
                )
                if daily:
                    capabilities.append(CAPABILITY_STANDARD_DAILY_KLINE)
                    trade_date = _latest_trade_date(daily)
                else:
                    errors.append(f"{CAPABILITY_STANDARD_DAILY_KLINE}: 返回空数据")
            except Exception as exc:
                errors.append(
                    f"{CAPABILITY_STANDARD_DAILY_KLINE}: {type(exc).__name__}: {exc}"
                )
            try:
                minute = client.get_kline(
                    _PROBE_MARKET, _PROBE_CODE, PERIOD.MIN_1, count=1
                )
                if minute:
                    capabilities.append(CAPABILITY_STANDARD_MINUTE_KLINE)
                else:
                    errors.append(f"{CAPABILITY_STANDARD_MINUTE_KLINE}: 返回空数据")
            except Exception as exc:
                errors.append(
                    f"{CAPABILITY_STANDARD_MINUTE_KLINE}: {type(exc).__name__}: {exc}"
                )
            try:
                auction = client.get_auction(_PROBE_MARKET, _PROBE_CODE)
                if auction is not None:
                    capabilities.append(CAPABILITY_STANDARD_AUCTION)
                else:
                    errors.append(f"{CAPABILITY_STANDARD_AUCTION}: 返回 None")
            except Exception as exc:
                errors.append(
                    f"{CAPABILITY_STANDARD_AUCTION}: {type(exc).__name__}: {exc}"
                )
    except Exception as exc:
        errors.append(f"transport.connect: {type(exc).__name__}: {exc}")
    finally:
        if client.connected:
            client.disconnect()

    if CAPABILITY_TRANSPORT in capabilities:
        mac_capabilities, mac_errors = _probe_mac_capabilities(
            server, trade_date, connect_timeout
        )
        capabilities.extend(mac_capabilities)
        errors.extend(mac_errors)

    return StandardServer(
        name,
        host,
        port,
        latency_ms,
        tuple(dict.fromkeys(capabilities)),
        tuple(errors),
        _server_sources(server),
    )


def probe_server_capabilities(
    candidates: Sequence[Server] = DEFAULT_CANDIDATES,
    *,
    cache_path: str | Path | None = None,
    cache_ttl: float | timedelta = DEFAULT_CACHE_TTL,
    candidate_limit: int | None = DEFAULT_CANDIDATE_LIMIT,
    max_workers: int = DEFAULT_MAX_WORKERS,
    connect_timeout: float = 3.0,
) -> tuple[StandardServer, ...]:
    """探测完整候选集并缓存每台服务器的实际能力清单。"""
    if candidate_limit is not None and candidate_limit <= 0:
        raise ValueError("candidate_limit 必须为正整数或 None")
    if max_workers <= 0:
        raise ValueError("max_workers 必须为正整数")
    if connect_timeout <= 0:
        raise ValueError("connect_timeout 必须为正数")

    resolved_cache_path = (
        Path(cache_path) if cache_path is not None else DEFAULT_CACHE_PATH
    )
    cached = _read_cache(resolved_cache_path, cache_ttl)
    if cached is not None:
        return cached

    selected_candidates = (
        tuple(candidates[:candidate_limit])
        if candidate_limit is not None
        else tuple(candidates)
    )
    if not selected_candidates:
        return ()

    results: dict[tuple[str, int], StandardServer] = {}
    worker_count = min(max_workers, len(selected_candidates))
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = {
            executor.submit(_probe_standard_server, server, connect_timeout): server
            for server in selected_candidates
        }
        for future in as_completed(futures):
            server = futures[future]
            try:
                result = future.result()
            except Exception as exc:  # 防御性兜底，单台异常不得中止其余探测。
                result = StandardServer(
                    server[0],
                    server[1],
                    server[2],
                    None,
                    errors=(f"probe: {type(exc).__name__}: {exc}",),
                    sources=_server_sources(server),
                )
            results[(server[1], server[2])] = result

    manifest = tuple(results[(server[1], server[2])] for server in selected_candidates)
    try:
        _write_cache(resolved_cache_path, manifest)
    except OSError as exc:
        log.warning("行情服务器能力缓存写入失败 %s: %s", resolved_cache_path, exc)
    return manifest


def select_capability_servers(
    servers: Sequence[StandardServer], *, required_capabilities: Sequence[str]
) -> tuple[StandardServer, ...]:
    """从完整能力清单筛选同时满足调用要求的服务器。"""
    required = tuple(required_capabilities)
    selected = [server for server in servers if server.supports(*required)]
    selected.sort(
        key=lambda server: (
            server.latency_ms is None,
            server.latency_ms if server.latency_ms is not None else float("inf"),
            server.host,
            server.port,
        )
    )
    return tuple(selected)


def probe_standard_servers(
    candidates: Sequence[Server] = DEFAULT_CANDIDATES,
    *,
    cache_path: str | Path | None = None,
    cache_ttl: float | timedelta = DEFAULT_CACHE_TTL,
    candidate_limit: int | None = DEFAULT_CANDIDATE_LIMIT,
    max_workers: int = DEFAULT_MAX_WORKERS,
    connect_timeout: float = 3.0,
) -> tuple[StandardServer, ...]:
    """兼容入口：返回具备日线和分钟线能力的服务器。"""
    manifest = probe_server_capabilities(
        candidates,
        cache_path=cache_path,
        cache_ttl=cache_ttl,
        candidate_limit=candidate_limit,
        max_workers=max_workers,
        connect_timeout=connect_timeout,
    )
    return select_capability_servers(
        manifest, required_capabilities=STANDARD_REQUIRED_CAPABILITIES
    )


class StandardClientPool:
    """以轮询方式分配已筛选普通行情服务器的 StandardClient。"""

    def __init__(self, servers: Sequence[StandardServer]) -> None:
        if not servers:
            raise ValueError("至少需要一台符合能力要求的行情服务器")
        self._servers = tuple(servers)
        self._index = 0
        self._lock = threading.Lock()

    @property
    def servers(self) -> tuple[StandardServer, ...]:
        """返回按探测延迟排序的可用服务器。"""
        return self._servers

    @classmethod
    def from_probe(
        cls,
        candidates: Sequence[Server] = DEFAULT_CANDIDATES,
        *,
        cache_path: str | Path | None = None,
        cache_ttl: float | timedelta = DEFAULT_CACHE_TTL,
        candidate_limit: int | None = DEFAULT_CANDIDATE_LIMIT,
        max_workers: int = DEFAULT_MAX_WORKERS,
        connect_timeout: float = 3.0,
    ) -> "StandardClientPool":
        """探测服务器（优先复用缓存）后创建客户端池。"""
        return cls(
            probe_standard_servers(
                candidates,
                cache_path=cache_path,
                cache_ttl=cache_ttl,
                candidate_limit=candidate_limit,
                max_workers=max_workers,
                connect_timeout=connect_timeout,
            )
        )

    def next_server(self) -> StandardServer:
        """线程安全地分配下一台已验证服务器。"""
        with self._lock:
            server = self._servers[self._index % len(self._servers)]
            self._index += 1
            return server

    def create_client(
        self,
        multithread: bool = False,
        heartbeat: bool = False,
        auto_retry: bool = False,
        raise_exception: bool = False,
        nonblocking: bool = False,
    ) -> "StandardClient":
        """创建绑定到下一台已验证服务器的未连接 StandardClient。"""
        from opentdx.client.standardClient import StandardClient

        return StandardClient(
            multithread=multithread,
            heartbeat=heartbeat,
            auto_retry=auto_retry,
            raise_exception=raise_exception,
            nonblocking=nonblocking,
            server=self.next_server().address,
        )

    acquire = create_client


def create_standard_client_pool(
    candidates: Sequence[Server] = DEFAULT_CANDIDATES,
    *,
    cache_path: str | Path | None = None,
    cache_ttl: float | timedelta = DEFAULT_CACHE_TTL,
    candidate_limit: int | None = DEFAULT_CANDIDATE_LIMIT,
    max_workers: int = DEFAULT_MAX_WORKERS,
    connect_timeout: float = 3.0,
) -> StandardClientPool:
    """按标准日线和分钟线能力筛选并创建 StandardClient 池。"""
    return StandardClientPool.from_probe(
        candidates,
        cache_path=cache_path,
        cache_ttl=cache_ttl,
        candidate_limit=candidate_limit,
        max_workers=max_workers,
        connect_timeout=connect_timeout,
    )


__all__ = [
    "CAPABILITY_TRANSPORT",
    "CAPABILITY_LOGIN",
    "CAPABILITY_STANDARD_DAILY_KLINE",
    "CAPABILITY_STANDARD_MINUTE_KLINE",
    "CAPABILITY_STANDARD_AUCTION",
    "CAPABILITY_MAC_SERVER_INFO",
    "CAPABILITY_MAC_SYMBOL_BARS",
    "CAPABILITY_MAC_SYMBOL_TRANSACTIONS",
    "CAPABILITY_MAC_SYMBOL_QUOTES",
    "CAPABILITY_MAC_SYMBOL_TICK_CHART",
    "CAPABILITY_MAC_BOARD_LIST",
    "CAPABILITY_MAC_BOARD_MEMBERS",
    "CAPABILITY_MAC_SYMBOL_BELONG_BOARD",
    "CAPABILITY_MAC_SYMBOL_INFO",
    "CAPABILITY_MAC_CAPITAL_FLOW",
    "CAPABILITY_MAC_MARKET_MONITOR",
    "CAPABILITY_MAC_AUCTION",
    "CAPABILITY_MAC_STANDARD",
    "STANDARD_REQUIRED_CAPABILITIES",
    "MAC_STANDARD_REQUIRED_CAPABILITIES",
    "DEFAULT_CACHE_PATH",
    "DEFAULT_CACHE_TTL",
    "DEFAULT_CANDIDATE_LIMIT",
    "DEFAULT_MAX_WORKERS",
    "DEFAULT_CANDIDATES",
    "Server",
    "StandardServer",
    "StandardClientPool",
    "probe_server_capabilities",
    "select_capability_servers",
    "probe_standard_servers",
    "create_standard_client_pool",
]
