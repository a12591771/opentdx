from .standardClient import StandardClient
from .macMixin import MacQuotationMixin
from opentdx.const import mac_hosts


class MacStandardClient(StandardClient, MacQuotationMixin):
    """MAC 版标准行情客户端 — A股行情 + MAC 板块/K线/分时/成交方法"""

    def __init__(self, multithread=False, heartbeat=False, auto_retry=False,
                 raise_exception=False):
        super().__init__(multithread, heartbeat, auto_retry, raise_exception)
        self._t.hosts = mac_hosts
