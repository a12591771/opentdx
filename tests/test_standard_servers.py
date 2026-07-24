from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from opentdx.client.standardClient import StandardClient
from opentdx.const import MARKET, PERIOD
from opentdx.standard_servers import (
    CAPABILITY_LOGIN,
    CAPABILITY_MAC_STANDARD,
    CAPABILITY_MAC_SYMBOL_TRANSACTIONS,
    CAPABILITY_STANDARD_AUCTION,
    CAPABILITY_STANDARD_DAILY_KLINE,
    CAPABILITY_STANDARD_MINUTE_KLINE,
    StandardClientPool,
    StandardServer,
    _call_mac_auction,
    probe_server_capabilities,
    probe_standard_servers,
    select_capability_servers,
)


SERVERS = (
    ("标准 1", "10.0.0.1", 7709),
    ("标准 2", "10.0.0.2", 7711),
)


def test_bound_standard_client_connects_to_allocated_server() -> None:
    client = StandardClient(server=SERVERS[1])
    client._t.connect = MagicMock(return_value=object())

    assert client.connect() is client
    client._t.connect.assert_called_once_with("10.0.0.2", 7711, 5, None, "0.0.0.0")


def test_mac_auction_probe_bypasses_standard_method_shadow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = MagicMock()
    mac_auction = MagicMock(return_value={"items": []})
    monkeypatch.setattr(
        "opentdx.client.macMixin.MacQuotationMixin.get_auction", mac_auction
    )

    result = _call_mac_auction(client)

    assert result == {"items": []}
    mac_auction.assert_called_once_with(client, MARKET.SZ, "000001", start=0, count=1)


def test_lightweight_kline_skips_list_finance_and_turnover() -> None:
    client = StandardClient()
    calls: list[object] = []

    def fake_call(parser: object) -> list[dict[str, int]]:
        calls.append(parser)
        return [
            {"open": 10230, "close": 10450, "high": 10500, "low": 10000, "vol": 120}
        ]

    client.call = fake_call  # type: ignore[method-assign]

    daily = client.get_kline(MARKET.SZ, "000001", PERIOD.DAILY, count=1)
    minute = client.get_kline(MARKET.SZ, "000001", PERIOD.MIN_1, count=1)

    assert daily[0] == {
        "open": 10.23,
        "close": 10.45,
        "high": 10.5,
        "low": 10.0,
        "vol": 120,
    }
    assert minute[0]["close"] == 10.45
    assert "turnover" not in daily[0]
    assert [type(parser).__name__ for parser in calls] == ["K_Line", "K_Line"]


def test_lightweight_index_kline_uses_same_price_scaling() -> None:
    client = StandardClient()
    client.call = MagicMock(  # type: ignore[method-assign]
        return_value=[
            {"open": 3012.34, "close": 3023.45, "high": 3030.0, "low": 3000.0}
        ]
    )

    bars = client.get_index_kline(MARKET.SH, "999999", PERIOD.DAILY, count=1)

    assert bars == [{"open": 3012.34, "close": 3023.45, "high": 3030.0, "low": 3000.0}]


def test_probe_verifies_login_daily_and_minute(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    created: list[FakeStandardClient] = []

    class FakeStandardClient:
        def __init__(
            self, *, server: tuple[str, str, int], raise_exception: bool
        ) -> None:
            self.server = server
            self.raise_exception = raise_exception
            self.connected = False
            self.periods: list[PERIOD] = []
            created.append(self)

        def connect(self, *, time_out: float) -> "FakeStandardClient":
            self.connected = True
            return self

        def login(self) -> bool:
            return True

        def get_kline(
            self, market: MARKET, code: str, period: PERIOD, *, count: int
        ) -> list[dict[str, object]]:
            assert market is MARKET.SZ
            assert code == "000001"
            assert count == 1
            self.periods.append(period)
            return [{"close": 1, "datetime": "2026-07-23"}]

        def get_auction(self, market: MARKET, code: str) -> list[dict[str, int]]:
            assert market is MARKET.SZ
            assert code == "000001"
            return []

        def disconnect(self) -> None:
            self.connected = False

    monkeypatch.setattr(
        "opentdx.client.standardClient.StandardClient", FakeStandardClient
    )
    monkeypatch.setattr(
        "opentdx.standard_servers._probe_mac_capabilities",
        lambda server, trade_date, timeout: (
            (CAPABILITY_MAC_SYMBOL_TRANSACTIONS, CAPABILITY_MAC_STANDARD),
            (),
        ),
    )

    result = probe_server_capabilities(
        SERVERS,
        cache_path=tmp_path / "servers.json",
        cache_ttl=0,
        candidate_limit=1,
        max_workers=1,
    )

    assert len(result) == 1
    assert result[0].address == SERVERS[0]
    assert result[0].supports(
        CAPABILITY_LOGIN,
        CAPABILITY_STANDARD_DAILY_KLINE,
        CAPABILITY_STANDARD_MINUTE_KLINE,
        CAPABILITY_STANDARD_AUCTION,
        CAPABILITY_MAC_SYMBOL_TRANSACTIONS,
        CAPABILITY_MAC_STANDARD,
    )
    assert created[0].periods == [PERIOD.DAILY, PERIOD.MIN_1]
    assert created[0].connected is False


def test_probe_reuses_fresh_custom_cache(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cache_path = tmp_path / "servers.json"
    expected = StandardServer(
        "标准 1",
        "10.0.0.1",
        7709,
        12.5,
        capabilities=(
            CAPABILITY_LOGIN,
            CAPABILITY_STANDARD_DAILY_KLINE,
            CAPABILITY_STANDARD_MINUTE_KLINE,
        ),
    )
    monkeypatch.setattr(
        "opentdx.standard_servers._probe_standard_server",
        lambda server, timeout: expected,
    )

    assert probe_standard_servers(
        SERVERS,
        cache_path=cache_path,
        candidate_limit=1,
        max_workers=1,
    ) == (expected,)

    monkeypatch.setattr(
        "opentdx.standard_servers._probe_standard_server",
        lambda server, timeout: pytest.fail("新鲜缓存不应触发探测"),
    )
    assert probe_standard_servers(
        SERVERS,
        cache_path=cache_path,
        candidate_limit=1,
        max_workers=1,
    ) == (expected,)


def test_probe_refreshes_expired_cache_and_pool_round_robins(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cache_path = tmp_path / "servers.json"
    cache_path.write_text(
        json.dumps(
            {
                "created_at": 0,
                "servers": [
                    {
                        "name": "旧服务器",
                        "host": "10.0.0.9",
                        "port": 7709,
                        "latency_ms": 1,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    standard_capabilities = (
        CAPABILITY_LOGIN,
        CAPABILITY_STANDARD_DAILY_KLINE,
        CAPABILITY_STANDARD_MINUTE_KLINE,
    )
    fresh = [
        StandardServer(
            "标准 2", "10.0.0.2", 7711, 20, capabilities=standard_capabilities
        ),
        StandardServer(
            "标准 1", "10.0.0.1", 7709, 10, capabilities=standard_capabilities
        ),
    ]
    monkeypatch.setattr(
        "opentdx.standard_servers._probe_standard_server",
        lambda server, timeout: fresh[0] if server == SERVERS[0] else fresh[1],
    )

    servers = probe_standard_servers(
        SERVERS,
        cache_path=cache_path,
        cache_ttl=0,
        candidate_limit=2,
        max_workers=2,
    )
    assert [server.latency_ms for server in servers] == [10, 20]

    pool = StandardClientPool(servers)
    assert pool.create_client()._bound_server == servers[0].address
    assert pool.acquire()._bound_server == servers[1].address
    assert pool.create_client()._bound_server == servers[0].address


def test_probe_defaults_to_all_candidates(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    probed: list[tuple[str, str, int]] = []

    def fake_probe(server: tuple[str, str, int], timeout: float) -> StandardServer:
        probed.append(server)
        return StandardServer(
            server[0],
            server[1],
            server[2],
            float(len(probed)),
            capabilities=(
                CAPABILITY_LOGIN,
                CAPABILITY_STANDARD_DAILY_KLINE,
                CAPABILITY_STANDARD_MINUTE_KLINE,
            ),
        )

    monkeypatch.setattr("opentdx.standard_servers._probe_standard_server", fake_probe)

    servers = probe_standard_servers(
        SERVERS,
        cache_path=tmp_path / "servers.json",
        max_workers=1,
    )

    assert probed == list(SERVERS)
    assert len(servers) == len(SERVERS)


def test_capability_selection_keeps_manifest_complete() -> None:
    standard_only = StandardServer(
        "仅标准",
        "10.0.2.1",
        7709,
        10,
        capabilities=(
            CAPABILITY_LOGIN,
            CAPABILITY_STANDARD_DAILY_KLINE,
            CAPABILITY_STANDARD_MINUTE_KLINE,
        ),
    )
    mac_capable = StandardServer(
        "MAC 完整",
        "10.0.2.2",
        7709,
        20,
        capabilities=(
            CAPABILITY_LOGIN,
            CAPABILITY_STANDARD_DAILY_KLINE,
            CAPABILITY_STANDARD_MINUTE_KLINE,
            CAPABILITY_MAC_SYMBOL_TRANSACTIONS,
            CAPABILITY_MAC_STANDARD,
        ),
    )
    unavailable = StandardServer(
        "不可用",
        "10.0.2.3",
        7709,
        None,
        errors=("transport.connect: timeout",),
    )
    manifest = (standard_only, mac_capable, unavailable)

    selected = select_capability_servers(
        manifest, required_capabilities=(CAPABILITY_MAC_SYMBOL_TRANSACTIONS,)
    )

    assert selected == (mac_capable,)
    assert len(manifest) == 3
    assert unavailable.errors == ("transport.connect: timeout",)
