from socket_server import SocketServer
from sys import _getframe as _gf
from urllib.parse import urlparse
import threading
import socket
import os


HTTP_VERSION = "HTTP/1.1"

SUPPORTED_METHODS = ("GET",)
SUPPORTED_HEADERS = ("host",)

ERROR_PAGES = {
        400: "400.html",
        404: "404.html",
        405: "405.html",
        505: "505.html"
        }

error_page_cache = {}


def parse_http_request(data):
    info = {
            "method": None,
            "request_uri": None,
            "http_version": None,
            "ignored": {},
            **{hdr: None for hdr in SUPPORTED_HEADERS}
            }
    try:
        data, content = data.split("\r\n\r\n", 1)
    except ValueError:
        return (False, (400, "invalid HTTP header"))
    data = data.split("\r\n")
    if not data:
        return (False, "empty data")
    try:
        method, uri, version, *extra = data[0].split(" ", 2)
    except ValueError:
        return (False, (400, f"invalid request-line `{_}`"))
    if method not in SUPPORTED_METHODS:
        return (False, (405, f"unsupported method `{method}`"))
    info["method"] = method
    info["request_uri"] = urlparse(uri)
    if version == "HTTP/1.1":
        info["http_version"] = version
    else:
        return (False, (505, f"unsupported HTTP version {version!r}"))
    info["http_version"] = version
    for line in data[1:]:
        header = (dat := line.split(":", 1))[0]
        dat[1] = dat[1].lstrip()
        if len(dat) != 2:
            return (False, (400, f"invalid header-line on {dat[0]}"))
        if header.lower() in SUPPORTED_HEADERS:
            info[header.lower()] = dat[1]
        else:
            info["ignored"][dat[0]] = dat[1]
    return (True, (info, content))


def construct_http_response(http_resp, data):
    if 'Status-code' in http_resp['headers']:
        http_resp['status_code'] = http_resp['headers']['Status-code']
        del http_resp['headers']['Status-code']
    if 'Reason-phrase' in http_resp['headers']:
        http_resp['reason_phrase'] = http_resp['headers']['Reason-phrase']
        del http_resp['headers']['Reason-phrase']
    return f"{http_resp['http_version']} {http_resp['status_code']} {http_resp['reason_phrase']}\r\n" \
    +      '\r\n'.join(f"{hdr}: {line}" for hdr, line in http_resp['headers'].items()) \
    +     f"\r\n\r\n{data}"


class HttpServer(SocketServer):
    def __init__(self, root_dir, error_dir="", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.root_dir = root_dir
        self.routes = {}
        self.error_dir = error_dir
        if not os.path.exists(root_dir):
            self.logger.log(_gf(), f"root dir. {root_dir!r} doesn't exist", True)
        elif not os.path.exists(error_dir):
            self.logger.log(_gf(), f"error dir. {error_dir!r} doesn't exist", True)
        error_dir = os.listdir(error_dir)
        for page in ERROR_PAGES.values():
            if page not in error_dir:
                self.logger.log(_gf(), f"{page!r} doesn't exist in {self.error_dir!r}", True)

    def add_route(self, path, handlers):
        # handlers = {"method": lambda conn, headers, data: ...}
        if not path.startswith("/"):
            path = f"/{path}"
        self.routes[path] = handlers

    def _get_error_page(self, code):
        if error_page_cache.get(code, None) is None:
            with open(f"{self.error_dir}/{ERROR_PAGES[code]}") as error_file:
                error_page_cache[code] = error_file.read()
        return error_page_cache[code]

    def _select_page(self, conn, addr, data):
        global error_page_cache
        success, data = data
        http_resp = {
                "http_version": HTTP_VERSION,
                "status_code": None,
                "reason_phrase": "General Error",  # tbd
                "headers": {
                    "server": "Unazed/1.0"
                    }
                }
        if not success:
            code, error = data
            error_page = self._get_error_page(code)
            http_resp['status_code'] = code
            http_resp['reason_phrase'] = error
            return construct_http_response(http_resp, error_page)
        info, content = data
        if info["method"] == "GET":
            if (path := "/" + info["request_uri"].path.split("/", 1)[1]) in self.routes:
                if "GET" not in self.routes[path]:
                    error_page = self._get_error_page(405)
                    http_resp['status_code'] = 405
                    return construct_http_response(http_resp, error_page)
                headers, page = self.routes[path]['GET'](conn, info, content)
                http_resp['status_code'] = 200
                http_resp['reason_phrase'] = 'OK'
                http_resp['headers'].update(headers)
                print(f"[{addr[0]}:{addr[1]}] [200] GET {path!r}")
                return construct_http_response(http_resp, page)
            else:
                error_page = self._get_error_page(404)
                http_resp['status_code'] = 404
                http_resp['reason_phrase'] = "Not found"
                print(f"[{addr[0]}:{addr[1]}] [404] GET {path!r}")
                return construct_http_response(http_resp, error_page)
        else:
            error_page = self._get_error_page(405)    
            http_resp['status_code'] = 405
            http_resp["reason_phrase"] = "Method Not Allowed"
            return construct_http_response(http_resp, error_page)


    def handle_http_requests(self, *args, **kwargs):
        def handle_http_requests(inst, idx, conn, addr, **kwargs):
            conn.settimeout(kwargs.get('timeout', 2))
            buff = ""
            try:
                while (dat := conn.recv(512).decode()):
                    buff += dat
            except socket.timeout:
                pass
            conn.settimeout(None)
            dat = parse_http_request(buff)
            self.logger.log(_gf(), f"[{addr[0]}:{addr[1]}] received {buff[:10]!r}")
            conn.send(self._select_page(conn, addr, dat).encode())
            conn.shutdown(socket.SHUT_RDWR)
            conn.close()
        super().handle_connections(
                worker_thd=handle_http_requests,
                proxy_worker_thd=lambda fn, *args_, **kwargs_: \
                        threading.Thread(target=fn, args=args_, kwargs=kwargs_).start(),
                *args, **kwargs
                )
