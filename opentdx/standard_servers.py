"""普通行情服务器的能力探测、缓存与客户端分配。"""

from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Sequence

from opentdx.const import MARKET, PERIOD, main_hosts
from opentdx.utils.log import log

if TYPE_CHECKING:
    from opentdx.client.standardClient import StandardClient


Server = tuple[str, str, int]
DEFAULT_CACHE_PATH = Path.home() / ".cache" / "opentdx" / "standard_servers.json"
DEFAULT_CACHE_TTL = timedelta(days=7)
DEFAULT_CANDIDATE_LIMIT: int | None = None
DEFAULT_MAX_WORKERS = 4
_PROBE_CODE = "000001"
_PROBE_MARKET = MARKET.SZ


@dataclass(frozen=True, slots=True)
class StandardServer:
    """已通过普通行情协议能力探测的服务器。"""

    name: str
    host: str
    port: int
    latency_ms: float

    @property
    def address(self) -> Server:
        """返回 StandardClient 可直接绑定的服务器三元组。"""
        return (self.name, self.host, self.port)

    @classmethod
    def from_mapping(cls, value: object) -> "StandardServer":
        if not isinstance(value, dict):
            raise ValueError("服务器缓存条目必须是对象")
        name = value.get("name")
        host = value.get("host")
        port = value.get("port")
        latency_ms = value.get("latency_ms")
        if not isinstance(name, str) or not isinstance(host, str):
            raise ValueError("服务器缓存缺少名称或地址")
        if not isinstance(port, int) or isinstance(port, bool):
            raise ValueError("服务器缓存端口无效")
        if not isinstance(latency_ms, (int, float)) or isinstance(latency_ms, bool):
            raise ValueError("服务器缓存延迟无效")
        return cls(name, host, port, float(latency_ms))


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
        "created_at": time.time(),
        "servers": [asdict(server) for server in servers],
    }
    cache_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _probe_standard_server(
    server: Server, connect_timeout: float
) -> StandardServer | None:
    """验证单台服务器能连接、登录并返回日线和分钟线。"""
    from opentdx.client.standardClient import StandardClient

    name, host, port = server
    client = StandardClient(server=server, raise_exception=True)
    started_at = time.perf_counter()
    try:
        if client.connect(time_out=connect_timeout) is None:
            return None
        if client.login() is not True:
            return None
        daily = client.get_kline(_PROBE_MARKET, _PROBE_CODE, PERIOD.DAILY, count=1)
        minute = client.get_kline(_PROBE_MARKET, _PROBE_CODE, PERIOD.MIN_1, count=1)
        if not daily or not minute:
            return None
        return StandardServer(
            name, host, port, (time.perf_counter() - started_at) * 1000
        )
    except Exception as exc:
        log.debug("普通行情服务器能力探测失败 %s:%d: %s", host, port, exc)
        return None
    finally:
        if client.connected:
            client.disconnect()


def probe_standard_servers(
    candidates: Sequence[Server] = main_hosts,
    *,
    cache_path: str | Path | None = None,
    cache_ttl: float | timedelta = DEFAULT_CACHE_TTL,
    candidate_limit: int | None = DEFAULT_CANDIDATE_LIMIT,
    max_workers: int = DEFAULT_MAX_WORKERS,
    connect_timeout: float = 3.0,
) -> tuple[StandardServer, ...]:
    """探测可用普通行情服务器并持久化结果。

    每台候选服务器必须通过 TCP 连接、协议登录、平安银行日线和一分钟线四项验证。
    缓存默认有效期为 7 天；传入 ``cache_path``、``cache_ttl``、``candidate_limit``
    和 ``max_workers`` 可按部署环境调整。
    """
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

    servers: list[StandardServer] = []
    worker_count = min(max_workers, len(selected_candidates))
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = {
            executor.submit(_probe_standard_server, server, connect_timeout): server
            for server in selected_candidates
        }
        for future in as_completed(futures):
            try:
                result = future.result()
            except Exception as exc:  # 防御性兜底，单台异常不得中止其余探测。
                server = futures[future]
                log.debug(
                    "普通行情服务器探测任务异常 %s:%d: %s", server[1], server[2], exc
                )
                continue
            if result is not None:
                servers.append(result)

    servers.sort(key=lambda server: server.latency_ms)
    if servers:
        try:
            _write_cache(resolved_cache_path, servers)
        except OSError as exc:
            log.warning("普通行情服务器缓存写入失败 %s: %s", resolved_cache_path, exc)
    return tuple(servers)


class StandardClientPool:
    """以轮询方式分配已探测普通行情服务器的 StandardClient。"""

    def __init__(self, servers: Sequence[StandardServer]) -> None:
        if not servers:
            raise ValueError("至少需要一台已探测的普通行情服务器")
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
        candidates: Sequence[Server] = main_hosts,
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
    candidates: Sequence[Server] = main_hosts,
    *,
    cache_path: str | Path | None = None,
    cache_ttl: float | timedelta = DEFAULT_CACHE_TTL,
    candidate_limit: int | None = DEFAULT_CANDIDATE_LIMIT,
    max_workers: int = DEFAULT_MAX_WORKERS,
    connect_timeout: float = 3.0,
) -> StandardClientPool:
    """探测普通行情服务器并创建可轮询分配 StandardClient 的池。"""
    return StandardClientPool.from_probe(
        candidates,
        cache_path=cache_path,
        cache_ttl=cache_ttl,
        candidate_limit=candidate_limit,
        max_workers=max_workers,
        connect_timeout=connect_timeout,
    )


__all__ = [
    "DEFAULT_CACHE_PATH",
    "DEFAULT_CACHE_TTL",
    "DEFAULT_CANDIDATE_LIMIT",
    "DEFAULT_MAX_WORKERS",
    "Server",
    "StandardServer",
    "StandardClientPool",
    "probe_standard_servers",
    "create_standard_client_pool",
]
