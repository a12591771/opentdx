from __future__ import annotations

import os
from pathlib import Path

import pytest

from opentdx import MARKET, PERIOD, StandardClientPool, probe_standard_servers
from opentdx.const import main_hosts


_LIVE_ENABLED = os.getenv("OPENTDX_LIVE_TESTS", "").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
pytestmark = pytest.mark.skipif(
    not _LIVE_ENABLED,
    reason="仅在 OPENTDX_LIVE_TESTS=1 时访问真实通达信服务器",
)

# 集成测试只取前三台候选服务器，并将探测并发限制为两条连接。
_CANDIDATES = tuple(main_hosts[:3])
_MAX_WORKERS = 2
_CACHE_TTL_SECONDS = 3600.0


def test_live_probe_cache_and_bound_client_kline(tmp_path: Path) -> None:
    """验证真实探测、缓存复用，以及绑定服务器的客户端 K 线请求。"""
    assert _CANDIDATES
    assert len(_CANDIDATES) <= 3

    cache_path = tmp_path / "standard_servers.json"
    servers = probe_standard_servers(
        _CANDIDATES,
        cache_path=cache_path,
        cache_ttl=_CACHE_TTL_SECONDS,
        candidate_limit=len(_CANDIDATES),
        max_workers=_MAX_WORKERS,
        connect_timeout=3.0,
    )

    assert servers, "没有候选服务器通过普通行情协议探测"
    assert len(servers) <= len(_CANDIDATES)
    assert cache_path.is_file()

    # 传入空候选集，只有读取新鲜缓存才能成功，从而确认没有再次访问网络。
    cached_servers = probe_standard_servers(
        (),
        cache_path=cache_path,
        cache_ttl=_CACHE_TTL_SECONDS,
        candidate_limit=1,
        max_workers=1,
        connect_timeout=3.0,
    )
    assert cached_servers == servers

    pool = StandardClientPool.from_probe(
        (),
        cache_path=cache_path,
        cache_ttl=_CACHE_TTL_SECONDS,
        candidate_limit=1,
        max_workers=1,
        connect_timeout=3.0,
    )
    assert pool.servers == servers

    client = pool.acquire(raise_exception=True)
    assert client._bound_server == pool.servers[0].address
    try:
        assert client.connect(time_out=3.0) is not None
        assert client.login() is True
        # 使用周线样本，避免重复探测阶段的日线和一分钟线请求。
        bars = client.get_kline(MARKET.SZ, "000001", PERIOD.WEEKLY, count=1)
        assert bars
    finally:
        if client.connected:
            client.disconnect()
