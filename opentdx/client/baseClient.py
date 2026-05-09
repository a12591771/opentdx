from .transport import Transport


class BaseClient:
    """基础客户端，持有 Transport 实例并提供通用基础设施"""

    def __init__(self, hosts, port=7709, multithread=False, heartbeat=False,
                 auto_retry=False, raise_exception=False):
        self._t = Transport(multithread, heartbeat, auto_retry, raise_exception)
        self._t.hosts = hosts
        self._port = port

    @property
    def heartbeat_thread(self):
        return self._t.heartbeat_thread

    @property
    def ip(self):
        return self._t.ip

    @property
    def port(self):
        return self._t.port

    @property
    def connected(self):
        return self._t.connected

    @property
    def heartbeat(self):
        return self._t.heartbeat

    @property
    def auto_retry(self):
        return self._t.auto_retry

    @auto_retry.setter
    def auto_retry(self, value):
        self._t.auto_retry = value

    @property
    def retry_strategy(self):
        return self._t.retry_strategy

    @retry_strategy.setter
    def retry_strategy(self, value):
        self._t.retry_strategy = value

    @property
    def raise_exception(self):
        return self._t.raise_exception

    @raise_exception.setter
    def raise_exception(self, value):
        self._t.raise_exception = value

    def connect(self, ip=None, time_out=5, bind_port=None, bind_ip='0.0.0.0'):
        self._t.set_heartbeat_callback(self._do_heartbeat if hasattr(self, '_do_heartbeat') else None)
        result = self._t.connect(ip, self._port, time_out, bind_port, bind_ip)
        return self if result is not None else None

    def disconnect(self):
        return self._t.disconnect()

    def call(self, parser):
        resp = self._t.send(parser.serialize())
        if resp is None:
            return None
        return parser.deserialize(resp)

    def _download_file_impl(self, fetch_cls, filename: str, filesize=0, report_hook=None):
        def fetch(fn, offset):
            return self.call(fetch_cls(fn, offset))
        return self._t.download_file(fetch, filename, filesize, report_hook)
