import socket
import threading
import time
import struct
import zlib
import functools
from concurrent.futures import ThreadPoolExecutor, as_completed
from opentdx.utils.log import log
from opentdx.utils.heartbeat import HeartBeatThread

CONNECT_TIMEOUT = 5.0
RSP_HEADER_LEN = 0x10


def update_last_ack_time(func):
    @functools.wraps(func)
    def wrapper(self, *args, **kw):
        ht = getattr(self, 'heartbeat_thread', None)
        if ht is None:
            t = getattr(self, '_t', None)
            if t is not None:
                ht = getattr(t, 'heartbeat_thread', None)
        if ht and ht.is_alive():
            ht.update_last_ack_time()

        current_exception = None
        try:
            ret = func(self, *args, **kw)
        except Exception as e:
            current_exception = e
            log.debug("hit exception on req exception is " + str(e))
            if self.auto_retry:
                for time_interval in self.retry_strategy.gen():
                    try:
                        time.sleep(time_interval)
                        self.disconnect()
                        self.connect(self.ip, self.port)
                        ret = func(self, *args, **kw)
                        if ret:
                            return ret
                    except Exception as retry_e:
                        current_exception = retry_e
                        log.debug("hit exception on *retry* req exception is " + str(retry_e))
                log.debug("perform auto retry on req ")
            ret = None
            if self.raise_exception:
                to_raise = Exception("calling function error")
                to_raise.original_exception = current_exception if current_exception else None
                raise to_raise
        return ret
    return wrapper


def _paginate(fetch_fn, page_size, count, start=0):
    results = []
    remaining = count if count != 0 else float('inf')
    while remaining > 0:
        req_count = min(remaining, page_size)
        part = fetch_fn(start, req_count)
        results.extend(part)
        if len(part) < req_count:
            break
        remaining -= len(part)
        start += len(part)
    return results


def _normalize_code_list(code_list, code=None):
    if code is not None:
        return [(code_list, code)]
    if (isinstance(code_list, list) or isinstance(code_list, tuple)) \
            and len(code_list) == 2 and isinstance(code_list[0], int):
        return [code_list]
    return code_list


class DefaultRetryStrategy:
    def gen(self):
        for time_interval in [0.1, 0.5, 1, 2]:
            yield time_interval


class Transport:
    hosts = []

    def __init__(self, multithread=False, heartbeat=False, auto_retry=False, raise_exception=False):
        self.client = None
        self.ip = None
        self.port = None

        if multithread or heartbeat:
            self.lock = threading.Lock()
        else:
            self.lock = None
        self.heartbeat = heartbeat
        self.heartbeat_thread = None
        self._stop_event = None
        self.connected = False

        self.auto_retry = auto_retry
        self.retry_strategy = DefaultRetryStrategy()
        self.raise_exception = raise_exception

        self._heartbeat_callback = None

    def set_heartbeat_callback(self, callback):
        self._heartbeat_callback = callback

    def connect(self, ip=None, port=7709, time_out=5, bind_port=None, bind_ip='0.0.0.0'):
        if ip is None:
            infos = []
            def get_latency(target_ip, target_port, timeout):
                client = None
                try:
                    start_time = time.time()
                    family = socket.AF_INET6 if ":" in target_ip else socket.AF_INET
                    client = socket.socket(family, socket.SOCK_STREAM)
                    client.settimeout(timeout)
                    client.connect((target_ip, target_port))
                    infos.append({
                        'ip': target_ip,
                        'port': target_port,
                        'time': time.time() - start_time,
                    })
                except Exception:
                    pass
                finally:
                    if client is not None:
                        try:
                            client.close()
                        except OSError:
                            pass
            max_workers = min(10, len(self.hosts))
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {
                    executor.submit(get_latency, host[1], host[2], 1): host
                    for host in self.hosts
                }
                for f in as_completed(futures):
                    pass

            infos.sort(key=lambda x: x['time'])
            if len(infos) == 0:
                raise Exception("no available server")

            return self._connect(infos[0]['ip'], infos[0]['port'], time_out, bind_port, bind_ip)
        else:
            return self._connect(ip, port, time_out, bind_port, bind_ip)

    def _connect(self, ip, port=7709, time_out=CONNECT_TIMEOUT, bind_port=None, bind_ip='0.0.0.0'):
        if ip.count(":") > 0:
            self.client = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        else:
            self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        self.ip = ip
        self.port = port
        self.client.settimeout(time_out)
        log.debug("connecting to server : %s on port :%d" % (ip, port))

        try:
            if bind_port is not None:
                self.client.bind((bind_ip, bind_port))
            self.client.connect((ip, port))
        except socket.timeout as e:
            self.client = None
            self.connected = False
            log.debug("connection expired")
            if self.raise_exception:
                raise Exception("connection timeout error", e)
            return None
        except Exception as e:
            self.client = None
            self.connected = False
            if self.raise_exception:
                raise Exception("other errors", e)
            return None

        log.debug("connected!")
        self.connected = True

        if self.heartbeat and self._heartbeat_callback and \
                not (self.heartbeat_thread and self.heartbeat_thread.is_alive()):
            self._stop_event = threading.Event()
            self.heartbeat_thread = HeartBeatThread(self.client, self._stop_event, self._heartbeat_callback)
            self.heartbeat_thread.daemon = True
            self.heartbeat_thread.start()
        return self

    def disconnect(self):
        if self.heartbeat_thread and self.heartbeat_thread.is_alive():
            self._stop_event.set()
        self.heartbeat_thread = None
        self._stop_event = None

        if self.client:
            log.debug("disconnecting")
            try:
                self.client.shutdown(socket.SHUT_RDWR)
                self.client.close()
                self.client = None
            except Exception as e:
                log.debug(str(e))
                if self.raise_exception:
                    raise Exception("disconnect err")
            log.debug("disconnected")
            self.connected = False

    def send(self, data):
        if self.lock:
            with self.lock:
                return self._send(data)
        else:
            return self._send(data)

    def _send(self, data):
        if not self.client:
            log.debug("not connected")
            if self.raise_exception:
                raise Exception("not connected")
            return None

        try:
            zipped, customize, control, zipsize, unzip_size, msg_id = struct.unpack('<BIBHHH', data[:12])
            send_data = self.client.send(data)
            if send_data != len(data):
                log.debug("send data error")
                if self.raise_exception:
                    raise Exception("send data error")
            else:
                head_buf = self.client.recv(RSP_HEADER_LEN)
                prefix, zipped, customize, unknown, msg_id, zipsize, unzip_size = struct.unpack('<IBIBHHH', head_buf)
                need_unzip_size = zipsize != unzip_size
                body_buf = bytearray()
                while zipsize > 0:
                    data_buf = self.client.recv(zipsize)
                    if not data_buf:
                        raise Exception("connection closed while receiving data")
                    body_buf.extend(data_buf)
                    zipsize -= len(data_buf)
                if need_unzip_size:
                    body_buf = zlib.decompress(body_buf)
                return body_buf
        except Exception as e:
            log.debug(str(e))
            self.connected = False
            self.client = None
            if self.raise_exception:
                raise Exception("send error")

    def download_file(self, fetch_fn, filename: str, filesize=0, report_hook=None):
        file_content = bytearray()
        current_downloaded_size = 0
        get_zero_length_package_times = 0
        while current_downloaded_size < filesize or filesize == 0:
            response = fetch_fn(filename, current_downloaded_size)
            if not response:
                break
            if response["size"] > 0:
                current_downloaded_size += response["size"]
                file_content.extend(response["data"])
                if report_hook is not None:
                    report_hook(current_downloaded_size, filesize)
            else:
                get_zero_length_package_times += 1
                if filesize == 0:
                    break
                elif get_zero_length_package_times > 2:
                    break
        return file_content
