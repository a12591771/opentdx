from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock

from opentdx.client.macExtendedClient import MacExtendedClient
from opentdx.client.macStandardClient import MacStandardClient
from opentdx.const import mac_hosts
from opentdx.server_router import ServerRoundRobin
from opentdx.tdxClient import TdxClient

STANDARD_HOSTS = (
    ("标准1", "10.0.0.1", 7709),
    ("标准2", "10.0.0.2", 7709),
    ("标准3", "10.0.0.3", 7709),
)
EXTENDED_HOSTS = (
    ("扩展1", "10.0.1.1", 7727),
    ("扩展2", "10.0.1.2", 7727),
)


def test_server_router_round_robins_each_lane_independently() -> None:
    router = ServerRoundRobin(STANDARD_HOSTS, EXTENDED_HOSTS)

    assert [router.next_standard() for _ in range(5)] == [
        STANDARD_HOSTS[0],
        STANDARD_HOSTS[1],
        STANDARD_HOSTS[2],
        STANDARD_HOSTS[0],
        STANDARD_HOSTS[1],
    ]
    assert [router.next_extended() for _ in range(4)] == [
        EXTENDED_HOSTS[0],
        EXTENDED_HOSTS[1],
        EXTENDED_HOSTS[0],
        EXTENDED_HOSTS[1],
    ]


def test_server_router_is_thread_safe() -> None:
    router = ServerRoundRobin(STANDARD_HOSTS, EXTENDED_HOSTS)

    with ThreadPoolExecutor(max_workers=12) as executor:
        allocated = list(executor.map(lambda _: router.next_standard(), range(30)))

    assert {server: allocated.count(server) for server in STANDARD_HOSTS} == {
        server: 10 for server in STANDARD_HOSTS
    }


def test_tdx_clients_share_injected_router_across_facades() -> None:
    router = ServerRoundRobin(STANDARD_HOSTS, EXTENDED_HOSTS)
    facades = [TdxClient(server_router=router) for _ in range(4)]

    assert [client.q_client()._bound_server for client in facades] == [
        STANDARD_HOSTS[0],
        STANDARD_HOSTS[1],
        STANDARD_HOSTS[2],
        STANDARD_HOSTS[0],
    ]
    assert [client.eq_client()._bound_server for client in facades] == [
        EXTENDED_HOSTS[0],
        EXTENDED_HOSTS[1],
        EXTENDED_HOSTS[0],
        EXTENDED_HOSTS[1],
    ]


def test_mac_clients_reuse_bound_server_for_no_arg_connect() -> None:
    standard = MacStandardClient(server=STANDARD_HOSTS[1])
    extended = MacExtendedClient(server=EXTENDED_HOSTS[1])
    standard._t.connect = MagicMock(return_value=object())
    extended._t.connect = MagicMock(return_value=object())

    assert standard.connect() is standard
    assert extended.connect() is extended

    standard._t.connect.assert_called_once_with(
        STANDARD_HOSTS[1][1], STANDARD_HOSTS[1][2], 5, None, "0.0.0.0"
    )
    extended._t.connect.assert_called_once_with(
        EXTENDED_HOSTS[1][1], EXTENDED_HOSTS[1][2], 5, None, "0.0.0.0"
    )


def test_bound_client_falls_back_and_keeps_successful_server() -> None:
    client = MacStandardClient(server=STANDARD_HOSTS[0])
    client._t.connect = MagicMock(side_effect=[None, object()])

    assert client.connect() is client
    assert client._bound_server == mac_hosts[0]
    assert client._t.connect.call_args_list[0].args[:2] == (
        STANDARD_HOSTS[0][1],
        STANDARD_HOSTS[0][2],
    )
    assert client._t.connect.call_args_list[1].args[:2] == (
        mac_hosts[0][1],
        mac_hosts[0][2],
    )


def test_tdx_client_can_opt_out_to_original_auto_selection() -> None:
    client = TdxClient(server_router=None)

    assert client.q_client()._bound_server is None
    assert client.eq_client()._bound_server is None
