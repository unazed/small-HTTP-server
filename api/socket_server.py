from time import time
from sys import _getframe as _gf
import socket
from .import logger


class SocketServer:
    def __init__(self, host='localhost', port=8080, logger_file=None, logger_folder=""):
        self.server_socket = socket.socket()
        self.host = host
        self.port = port
        self.halted = False
        self.logger = logger.Logger(open(
            "%s/logfile_%d.txt" % (logger_folder, time()),
            "w"
            ) if logger_file is None else logger_file) # simplifiable
        self.server_socket.setsockopt(
                socket.SOL_SOCKET,
                socket.SO_REUSEADDR,
                1
                )
        try:
            self.server_socket.bind((host, port))
        except OSError as exc:
            self.logger.log(
                    _gf(),
                    f"failed to bind, got {exc!r}",
                    True
                    )
        self.logger.log(_gf(), f"bound successfully to "
                f"{host}:{port}")

    def handle_connections(self, worker_thd, *, backlog=5,
            proxy_worker_thd=lambda fn, *args, **kwargs: fn(*args, **kwargs),
            halt_on_ret=False, timeout=2):
        self.server_socket.settimeout(timeout)
        self.server_socket.listen(backlog)
        idx = 0
        while not self.halted:
            try:
                conn, address = self.server_socket.accept()
                self.logger.log(
                        _gf(),
                        f"received connection from {address[0]}"
                        )
                ret = not proxy_worker_thd(worker_thd, self, idx, conn, address)
                if halt_on_ret:
                    self.halted = ret
                idx += 1
            except KeyboardInterrupt:
                self.logger.log(_gf(), "user-interrupt caught", True)
            except socket.timeout:
                pass  # recheck self.halted
            except Exception as exc:
                self.logger.log(_gf(), f"passing unhandled exception caught, {exc!r}")
                print(repr(exc))
        self.server_socket.settimeout(None)

    def __del__(self):
        self.logger.log(_gf(), "garbage collecting SocketServer instance")
        print("successfully destructed SocketServer instance")
        self.server_socket.close()
        self.logger.file_obj.close()
