"""OpenTdx 行情服务器轮询调度。"""

from __future__ import annotations

import threading
from collections.abc import Sequence

from opentdx.const import mac_ex_hosts, mac_hosts

Server = tuple[str, str, int]


class ServerRoundRobin:
    """按线路为新连接线程安全地轮询分配服务器。"""

    def __init__(
        self,
        standard_hosts: Sequence[Server] = mac_hosts,
        extended_hosts: Sequence[Server] = mac_ex_hosts,
    ) -> None:
        self._standard_hosts = tuple(standard_hosts)
        self._extended_hosts = tuple(extended_hosts)
        self._standard_index = 0
        self._extended_index = 0
        self._lock = threading.Lock()

    def next_standard(self) -> Server | None:
        """返回下一台 A 股/MAC 行情服务器。"""
        with self._lock:
            if not self._standard_hosts:
                return None
            server = self._standard_hosts[
                self._standard_index % len(self._standard_hosts)
            ]
            self._standard_index += 1
            return server

    def next_extended(self) -> Server | None:
        """返回下一台扩展市场/MAC 行情服务器。"""
        with self._lock:
            if not self._extended_hosts:
                return None
            server = self._extended_hosts[
                self._extended_index % len(self._extended_hosts)
            ]
            self._extended_index += 1
            return server


DEFAULT_SERVER_ROUTER = ServerRoundRobin()
