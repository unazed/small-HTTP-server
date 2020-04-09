#!/usr/bin/env python3
from socket_server import SocketServer
from urllib.parse import unquote_plus
import os
import socket
import threading

                        
class HttpServer(SocketServer):
    SUPPORTED_HTTP_VERSION = "HTTP/1.1"
    DEFAULT_ERROR = SUPPORTED_HTTP_VERSION \
            + " {status} {reason_phrase}\r\n\r\n<html><body><h1>{status} - {reason_phrase}</h1><p>This resource is inaccessible.</p></body></html>"

    def __init__(self, root_dir, *args, max_conn=10, **kwargs):
        super().__init__(*args, **kwargs)
        if not os.path.exists(root_dir):
            print(f"[HttpServer] [{self.host}:{self.port}] {root_dir!r} doesn't exist")
            raise OSError
        self.root_dir = root_dir
        self.max_conn = max_conn
        self._routes = {}

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
        except (ValueError, IndexError):
            headers = {}
            content = ""
        else:
            headers.update({
                ":method": method,
                ":uri": uri,
                ":version": version
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
        if src_path not in self._routes or dst_path not in self._routes:
            return False
        print(f"[HttpServer] [{self.host}:{self.port}] redirecting {src_path!r} to {dst_path!r}")
        ms = self._routes[src_path]['methods_supported']
        self._routes[src_path] = self._routes[dst_path]
        if not inherit_methods:
            self._routes[src_path]['methods_supported'] = ms
        return True

    def remove_route(self, path):
        if path not in self._routes:
            return False
        print(f"[HttpServer] [{self.host}:{self.port}] removing route {path!r}")
        del self._routes[path]
        return True

    def get_route(self, conn, addr, method, path, *, _error=False):
        print(f"[HttpServer] [{addr[0]}:{addr[1]}] {method} {path!r}")
        params = None
        if '?' in path and not _error:
            try:
                params = {pair.split("=")[0]: unquote_plus(pair.split("=")[1]) for pair in path.split("?", 1)[1].split("&")}
            except IndexError:
                return conn.send(self.get_route(conn, addr, "GET", "/400", _error=(400, "Bad Request")).encode())
            path = path.split("?")[0]
        if path not in self._routes or _error:
            if _error:
                return HttpServer.DEFAULT_ERROR.format(
                        status=_error[0],
                        reason_phrase=_error[1]
                        )
            return conn.send(self.get_route(conn, addr, "GET", "/404", _error=(404, "Not Found")).encode())
        elif method not in self._routes[path]['methods_supported']:
            return conn.send(self.get_route(conn, addr, "GET", "/405", _error=(405, "Method Unsupported")).encode())
        return (route := self._routes[path])['handler'](self, conn, addr, method, params, route)

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
            self.get_route(conn, addr, headers[":method"], headers[':uri'])
            conn.close()

        def delegate_handler(*args, **kwargs):
            counter[0] += 1
            counter.append(threading.Thread(
                target=handler, args=args, kwargs=kwargs
                ))
            counter[-1].start()
            print(f"[HttpServer] [{self.host}:{self.port}] spawned worker thread")

        counter = [0]
        while True:
            while counter[0] < self.max_conn:
                print(f"[HttpServer] [{self.host}:{self.port}] delegating new worker thread")
                super().handle_raw_connection(delegate_handler, timeout=1)
            print(f"[HttpServer] [{self.host}:{self.port}] idling while active threads exit")
            for idx, thd in enumerate(counter[1:]):
                if not thd.is_alive():
                    print(f"[HttpServer] [{self.host}:{self.port}] killing dead thread")
                    counter[0] -= 1
                    try:
                        del counter[idx+1]
                    except IndexError:
                        continue


if __name__ == "__main__":
    def index(server, conn, addr, method, params, route):
        server.redirect_route("/index", "/meme")
        conn.send(b"""HTTP/1.1 200 OK\r\nConnection: keepa-live\r\n\r\n<html>
                hi bitch, got params=%s host=%s
                </html>
                """ % (str(params).encode(), str(route['host']).encode()))
    server = HttpServer(
            root_dir="html/",
            max_conn=5,
            host="localhost",
            port=6969
            )
    server.add_route(["GET"], "/index", index)
    server.add_route([], "/meme", index)
    server.handle_http_connections()

