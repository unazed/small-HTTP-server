#!/usr/bin/env python3
from socket_server import SocketServer
from random import randint
import socket
import sys
import threading

def thd_worker(inst, idx, conn, addr):
    print(f"got {idx} {addr}")

    conn.settimeout(3)
    buff = ""
    try:
        while (_ := conn.recv(512).decode()):
            if not _:
                break
            buff += _
    except socket.timeout:
        pass
    conn.settimeout(None)
    conn.send(b"ok\n")
    inst.halted = buff.strip() == "halt"
    print(inst.halted, buff.strip().encode())
    conn.close()

if __name__ != "__main__":
    raise SystemExit

server = SocketServer(port=randint(49152, 65535), logger_file=sys.stdout)
print(f"started server on address {server.host}:{server.port}")
server.handle_connections(
        thd_worker,
        proxy_worker_thd=lambda fn, *args, **kwargs: threading.Thread(target=fn, args=args, kwargs=kwargs).start()
    )
