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
        self._routes[path] = {
                    "methods_supported": methods_supported,
                    "handler": handler,  # handler(conn, addr, method, params)
                }

    def get_route(self, conn, addr, method, path, *, _error=False):
        print(f"[HttpServer] [{addr[0]}:{addr[1]}] {method} {path!r}")
        if path not in self._routes:
            if _error == 404:
                return HttpServer.DEFAULT_ERROR.format(
                        status=404,
                        reason_phrase="Not Found"
                        )
            return conn.send(self.get_route(conn, addr, "GET", "/404", _error=404).encode())
        elif method not in self._routes[path]['methods_supported']:
            if _error == 405:  # prevent recursion
                return HttpServer.DEFAULT_ERROR.format(
                        status=405,
                        reason_phrase="Method Unsupported"
                        )
            return conn.send(self.get_route(conn, addr, "GET", "/405", _error=405).encode())
        params = None
        if '?' in path:
            params = [{pair.split("=")[0], pair.split("=")[1]} for pair in path.split("?", 1)[1].split("&")]
            path = path.split("?")[0]
        return self._routes[path]['handler'](conn, addr, method, params)

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
            print(headers)
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
    def index(conn, addr, method, params):
        conn.send(b"""HTTP/1.1 200 OK\r\n\r\n
                <html>
                hi bitch
                </html>
                """)
    server = HttpServer(
            root_dir="html/",
            max_conn=5,
            host="localhost",
            port=6969
            )
    server.add_route(["GET"], "/index", index)
    server.handle_http_connections()

