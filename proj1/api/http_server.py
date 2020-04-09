from .socket_server import SocketServer
from sys import _getframe as _gf
from urllib.parse import urlparse, unquote
import threading
import socket
import os


HTTP_VERSION = "HTTP/1.1"

SUPPORTED_METHODS = ("GET", "POST")
SUPPORTED_HEADERS = ("host",)

ERROR_PAGES = {
        400: "400.html",
        404: "404.html",
        405: "405.html",
        505: "505.html"
        }

error_page_cache = {}


def parse_cookies(dat):
    # rfc non-compliant
    if not dat: return {}
    cookies = {}
    for cookie in dat.split("; "):
        key, val = cookie.split("=", 1)
        cookies[key] = val
    return cookies


def parse_post(dat):
    # rfc non-compliant
    if not dat: return {}
    data = {}
    for item in dat.split("&"):
        key, val = item.split("=", 1)
        data[key] = unquote(val)
    return data


def parse_http_request(data):
    if not data:
        return 
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
    +      '\r\n'.join(f"{hdr.split('#', 1)[0]}: {line}" for hdr, line in http_resp['headers'].items()) \
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
        if not str(path).startswith("/"):
            path = f"/{path}"
        self.routes[path] = handlers

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
            _, page = self.routes[f"/{code}"]["GET"](conn, {}, "")
            http_resp['status_code'] = code
            http_resp['reason_phrase'] = error
            return construct_http_response(http_resp, page)
        info, content = data
        method = info["method"]
        if (path := "/" + info["request_uri"].path.split("/", 1)[1]) in self.routes:
            if method not in self.routes[path]:
                _, error_page = self.routes["/405"]["GET"](conn, {}, "")
                http_resp['status_code'] = 405
                return construct_http_response(http_resp, error_page)
            headers, page = self.routes[path][method](conn, info, content)
            http_resp['status_code'] = 200
            http_resp['reason_phrase'] = 'OK'
            http_resp['headers'].update(headers)
            print(f"[{addr[0]}:{addr[1]}] [200] {method} {path!r}")
            return construct_http_response(http_resp, page)
        else:
            _, error_page = self.routes["/404"]["GET"](conn, {}, "")
            http_resp['status_code'] = 404
            http_resp['reason_phrase'] = "Not found"
            print(f"[{addr[0]}:{addr[1]}] [404] {method} {path!r}")
            return construct_http_response(http_resp, error_page)

    def handle_http_requests(self, *args, **kwargs):
        def handle_http_requests(inst, idx, conn, addr, **kwargs):
            conn.settimeout(1)
            buff = ""
            try:
                while (dat := conn.recv(512).decode()):
                    buff += dat
            except socket.timeout:
                pass
            if not buff:
                conn.close()
                return
            conn.settimeout(None)
            dat = parse_http_request(buff)
            if not dat:
                conn.shutdown(socket.SHUT_RDWR)
                conn.close()
            self.logger.log(_gf(), f"[{addr[0]}:{addr[1]}] received {buff[:10]!r}")
            conn.send(self._select_page(conn, addr, dat).encode())
            try:
                conn.shutdown(socket.SHUT_RDWR)
                conn.close()
            except OSError:
                self.logger.log(_gf(), f"[{addr[0]}:{addr[1]}] abruptly closed")
        super().handle_connections(
                worker_thd=handle_http_requests,
                proxy_worker_thd=lambda fn, *args_, **kwargs_: \
                        threading.Thread(target=fn, args=args_, kwargs=kwargs_).start(),
                *args, **kwargs
                )
