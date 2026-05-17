from datetime import date

from .baseClient import BaseClient


def _to_date_int(d: int | str | date) -> int:
    if isinstance(d, int):
        return d
    if isinstance(d, date):
        return int(d.strftime('%Y%m%d'))
    return int(str(d).replace('-', '').replace('/', ''))
from .transport import update_last_ack_time, _paginate, _normalize_code_list
from opentdx.const import EX_MARKET, PERIOD, SORT_TYPE, ex_hosts
from opentdx.parser import ex_quotation
from opentdx.utils.log import log


class ExtendedClient(BaseClient):
    """扩展行情客户端 (港股/美股/期货)"""

    def __init__(self, multithread=False, heartbeat=False, auto_retry=False,
                 raise_exception=False, nonblocking=False):
        super().__init__(ex_hosts, 7727, multithread, heartbeat, auto_retry, raise_exception, nonblocking)

    def _do_heartbeat(self):
        return self.call(ex_quotation.HeartBeat())

    def login(self, show_info=False) -> bool:
        try:
            info = self.call(ex_quotation.Login())
            if show_info:
                log.info("login info: %s", info)
            return True
        except Exception as e:
            log.error("login failed: %s", e)
            return False

    def server_info(self):
        try:
            return self.call(ex_quotation.ServerInfo())
        except Exception as e:
            log.error("get server info failed: %s", e)
            return None

    @update_last_ack_time
    def get_count(self) -> int:
        return self.call(ex_quotation.Count())

    @update_last_ack_time
    def get_category_list(self) -> list[dict]:
        return self.call(ex_quotation.CategoryList())

    @update_last_ack_time
    def get_list(self, start: int = 0, count: int = 2000) -> list[dict]:
        return self.call(ex_quotation.List(start, count))

    @update_last_ack_time
    def get_quotes_list(self, market: EX_MARKET, start: int = 0, count: int = 100,
                        sortType: SORT_TYPE = SORT_TYPE.CODE, reverse: bool = False) -> list[dict]:
        return _paginate(
            lambda s, c: self.call(ex_quotation.QuotesList(market, s, c, sortType, reverse)),
            100, count, start,
        )

    @update_last_ack_time
    def get_quotes_single(self, market: EX_MARKET, code) -> dict:
        return self.call(ex_quotation.QuotesSingle(market, code))

    @update_last_ack_time
    def get_quotes(self, code_list, code=None) -> list[dict]:
        code_list = _normalize_code_list(code_list, code)
        return self.call(ex_quotation.Quotes(code_list))

    @update_last_ack_time
    def get_quotes2(self, code_list, code=None) -> list[dict]:
        code_list = _normalize_code_list(code_list, code)
        return self.call(ex_quotation.Quotes2(code_list))

    @update_last_ack_time
    def get_kline(self, market: EX_MARKET, code: str, period: PERIOD, start: int = 0,
                  count: int = 800, times: int = 1) -> list[dict]:
        return self.call(ex_quotation.K_Line(market, code, period, times, start, count))

    @update_last_ack_time
    def get_history_transaction(self, market: EX_MARKET, code: str, date: date) -> list[dict]:
        return self.call(ex_quotation.HistoryTransaction(market, code, date))

    @update_last_ack_time
    def get_table(self):
        return self._fetch_all_text(ex_quotation.Table)

    @update_last_ack_time
    def get_table_detail(self):
        return self._fetch_all_text(ex_quotation.TableDetail)

    def _fetch_all_text(self, fetch_cls):
        start, result = 0, ''
        while True:
            _, count, context = self.call(fetch_cls(start))
            start += count
            result += context
            if count <= 0:
                break
        return result

    @update_last_ack_time
    def get_tick_chart(self, market: EX_MARKET, code: str, date: date = None) -> list[dict]:
        if date is None:
            return self.call(ex_quotation.TickChart(market, code))
        else:
            return self.call(ex_quotation.HistoryTickChart(market, code, date))

    @update_last_ack_time
    def get_chart_sampling(self, market: EX_MARKET, code: str) -> list[float]:
        return self.call(ex_quotation.ChartSampling(market, code))

    @update_last_ack_time
    def get_history_instrument_bars_range(
        self,
        market: EX_MARKET,
        code: str,
        date1: int | str | date,
        date2: int | str | date,
    ) -> list[dict]:
        """获取扩展市场日期范围 K 线（期货/港股/美股）。

        Parameters
        ----------
        market : EX_MARKET
        code : str
        date1 : int | str | date  起始日期，支持 20170613、'2017-06-13'、date(2017,6,13)
        date2 : int | str | date  结束日期，同 date1
        """
        d1 = _to_date_int(date1)
        d2 = _to_date_int(date2)
        return self.call(ex_quotation.KLineByDate(market, code, d1, d2)) or []

    @update_last_ack_time
    def download_file(self, filename: str, filesize=0, report_hook=None):
        return self._download_file_impl(ex_quotation.FileDownload, filename, filesize, report_hook)
