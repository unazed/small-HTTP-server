import socket


port = input("port? ")
path = input("path? ")

a = socket.socket()
a.connect(("localhost", int(port)))
a.send(f"GET {path} HTTP/1.1\r\nHost: localhost:{port}\r\n\r\n".encode())
print(a.recv(1024))
a.shutdown(socket.SHUT_RDWR)
a.close()
