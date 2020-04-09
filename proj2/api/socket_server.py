#!/usr/bin/env python3
from io import StringIO, FileIO
import socket
import sys


class SocketServer:
    def __init__(self, host, port, *, logger_file=None):
        self.logger_file = logger_file
        if logger_file is not None:
            self.logger = StringIO()
            sys.stdout = self.logger

        self.host = host
        self.port = port

        self.socket = socket.socket()
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((host, port))
        print(f"[{host}:{port}] successfully bound")

    def handle_raw_connection(self, handler, *, buff_size=1, timeout=1):
        self.socket.listen(1)
        conn, addr = self.socket.accept()
        print(f"[{self.host}:{self.port}] received connection from {addr[0]}:{addr[1]}")
        return handler(conn, addr)

#        conn.settimeout(timeout)
#        data = ""
#        try:
#            while (recv := conn.recv(buff_size).decode()):
#                data += recv
#        except socket.timeout:
#            pass
#        conn.settimeout(None)
#        print(f"[{addr[0]}:{addr[1]}] received {len(data)} bytes of data")
#
#        return handler(conn, addr, data)
        
    def __del__(self):
        if self.logger_file is not None:
            sys.stdout = sys.__stdout__
            self.logger.seek(0)
            log = FileIO(self.logger_file, "w")  # odd behaviour at
                                                 # deconstruction
                                                 # prohibits open(...)
            log.write(self.logger.read().encode())
            log.close()
            print(f"written logs to {self.logger_file!r}, exiting ...")


if __name__ == "__main__":
    def handler(conn, addr, data):
        print(data)
        conn.send(b"thanks.\r\n")
        conn.shutdown(socket.SHUT_RDWR)
        conn.close()

    server = SocketServer("localhost", 6969)
    server.handle_raw_connection(handler)
