#!/usr/bin/env python3
from .socket_server import SocketServer
from urllib.parse import unquote_plus
import os
import socket
import threading

                        
class HttpServer(SocketServer):
    SUPPORTED_HTTP_VERSION = "HTTP/1.1"
    DEFAULT_ERROR = SUPPORTED_HTTP_VERSION \
            + " {status} {reason_phrase}\r\n\r\n<html><body><h1>{status} - {reason_phrase}</h1><p>This resource is inaccessible.</p></body></html>"
    INTERNAL_ERRORS = ("/404", "/405", "/400")

    def __init__(self, root_dir, *args, max_conn=10, **kwargs):
        super().__init__(*args, **kwargs)
        if not os.path.exists(root_dir):
            print(f"[HttpServer] [{self.host}:{self.port}] {root_dir!r} doesn't exist")
            raise FileNotFoundError
        self.root_dir = root_dir
        self.max_conn = max_conn
        self._routes = {}
        self._threads = []

    @staticmethod
    def parse_http_request(data):
        try:
            preamble, content = data.split("\r\n\r\n", 1)
            method_line, *headers = preamble.split("\r\n")
            method, uri, version = method_line.split(" ", 2)
            headers = {
                    hdr.split(": ", 1)[0]: hdr.split(": ", 1)[1]
                    for hdr in headers
                    }
            cookies = {}
            if 'Cookie' in headers:
                for pair in headers['Cookie'].split("&"):
                    pair = pair.split("=")
                    cookies[pair[0]] = unquote_plus(pair[1])
        except (ValueError, IndexError):
            headers = {}
            content = ""
        else:
            headers.update({
                ":method": method,
                ":uri": uri,
                ":version": version,
                ":cookies": cookies
                })
        return headers, content

    def add_route(self, methods_supported, path, handler):
        if path in self._routes:
            print(f"[HttpServer] [{self.host}:{self.port}] tried to ovewrite existing route, {path!r}")
            return False
        if '?' in path:
            print(f"[HttpServer] [{self.host}:{self.port}] invalid character in path '?'")
            return False
        print(f"[HttpServer] [{self.host}:{self.port}] adding route {path!r}")
        self._routes[path] = {
                    "methods_supported": methods_supported,
                    "handler": handler,
                    "host": path,
                    "origin": None
                }

    def redirect_route(self, src_path, dst_path, *, inherit_methods=False):
        if src_path == dst_path:
            return False
        elif src_path not in self._routes or dst_path not in self._routes:
            return False
        print(f"[HttpServer] [{self.host}:{self.port}] redirecting {src_path!r} to {dst_path!r}")
        ms = self._routes[src_path]['methods_supported']
        self._routes[src_path] = self._routes[dst_path]
        self._routes[src_path]["origin"] = src_path
        if not inherit_methods:
            self._routes[src_path]['methods_supported'] = ms
        return True

    def remove_route(self, path):
        if path not in self._routes:
            return False
        print(f"[HttpServer] [{self.host}:{self.port}] removing route {path!r}")
        del self._routes[path]
        return True

    def get_route(self, conn, addr, method, path, *, content=None, cookies={}, _error=False):
        print(f"[HttpServer] [{addr[0]}:{addr[1]}] {method} {path!r}")
        params = {"GET": {}, "POST": {}}
        if '?' in path and not _error:
            try:
                params["GET"] = {pair.split("=")[0]: unquote_plus(pair.split("=")[1]) for pair in path.split("?", 1)[1].split("&")}
            except IndexError:
                return conn.send(self.get_route(conn, addr, "GET", "/400", _error=(400, "Bad Request")).encode())
            path = path.split("?")[0]

        if method == "POST":
            try:
                params["POST"] = {pair.split("=")[0]: unquote_plus(pair.split("=")[1]) for pair in content.split("&")}
            except IndexError:
                return conn.send(self.get_route(conn, addr, "GET", "/400", _error=(400, "Bad Request")).encode())
 
        if path not in self._routes or _error:
            if _error:
                return HttpServer.DEFAULT_ERROR.format(
                        status=_error[0],
                        reason_phrase=_error[1]
                        )
            
            if '/*' in self._routes and path not in HttpServer.INTERNAL_ERRORS:
                return self._routes['/*']['handler'](self, conn, addr, method, {"path": path}, None, cookies)
            return conn.send(self.get_route(conn, addr, "GET", "/404", _error=(404, "Not Found")).encode())

        elif method not in self._routes[path]['methods_supported']:
            return conn.send(self.get_route(conn, addr, "GET", "/405", _error=(405, "Method Unsupported")).encode())
        
        return (route := self._routes[path])['handler'](self, conn, addr, method, params, route, cookies)

    def handle_http_connections(self):
        def handler(conn, addr):
            conn.settimeout(1)
            data = ""
            try:
                while (recv := conn.recv(1).decode()):
                    data += recv
            except socket.timeout:
                pass
            conn.settimeout(None)
            headers, content = self.parse_http_request(data)


            try:
                method = headers[':method']
                uri = headers[':uri']
                cookies = headers[':cookies']
            except KeyError:
                return conn.close()
            
            self.get_route(conn, addr, method, uri, content=content, cookies=cookies)
            return conn.close()

        def delegate_handler(*args, **kwargs):
            self._threads[0] += 1
            self._threads.append(threading.Thread(
                target=handler, args=args, kwargs=kwargs
                ))
            self._threads[-1].start()
            print(f"[HttpServer] [{self.host}:{self.port}] spawned worker thread")
            return True

        self._threads = [0]
        while True:
            while self._threads[0] < self.max_conn:
                print(f"[HttpServer] [{self.host}:{self.port}] delegating new worker thread")
                if not super().handle_raw_connection(delegate_handler, timeout=1):
                    print(f"[HttpServer] [{self.host}:{self.port}] caught keyboard interrupt, exiting...")
                    return self.close_connections()
            print(f"[HttpServer] [{self.host}:{self.port}] idling while active threads exit")
            for idx, thd in enumerate(self._threads[1:]):
                if not thd.is_alive():
                    print(f"[HttpServer] [{self.host}:{self.port}] killing dead thread")
                    self._threads[0] -= 1
                    try:
                        del self._threads[idx+1]
                    except IndexError:
                        continue

    def close_connections(self):
        print(f"[HttpServer] [{self.host}:{self.port}] closing all active connections")
        for idx, thd in enumerate(self._threads[1:]):
            thd.join()
        print(f"[HttpServer] [{self.host}:{self.port}] closed all active connections")
