from .extendedClient import ExtendedClient
from .macMixin import MacQuotationMixin
from opentdx.const import mac_ex_hosts
from opentdx.server_router import Server


class MacExtendedClient(ExtendedClient, MacQuotationMixin):
    """MAC 版扩展行情客户端 — 扩展市场行情 + MAC 板块/K线/分时/成交方法"""

    def __init__(
        self,
        multithread=False,
        heartbeat=False,
        auto_retry=False,
        raise_exception=False,
        nonblocking=False,
        server: Server | None = None,
    ):
        super().__init__(multithread, heartbeat, auto_retry, raise_exception, nonblocking)
        self._t.hosts = mac_ex_hosts
        self._bound_server = server
        if server is not None:
            self._port = server[2]

    def connect(self, ip=None, time_out=5, bind_port=None, bind_ip='0.0.0.0'):
        """优先连接绑定服务器，失败时切换到同线路其他候选。"""
        if ip is not None or self._bound_server is None:
            return super().connect(ip, time_out, bind_port, bind_ip)

        candidates = [self._bound_server]
        candidates.extend(
            server for server in mac_ex_hosts if server != self._bound_server
        )
        for server in candidates:
            self._port = server[2]
            connected = super().connect(
                server[1], time_out, bind_port, bind_ip
            )
            if connected is not None:
                self._bound_server = server
                return connected
        return None
