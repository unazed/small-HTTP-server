#!/usr/bin/env python3
from http_server import HttpServer
from random import randint
import sys
import base64


def index(conn, headers, data):
    if 'Authorization' not in headers['ignored']:
        with open("www/error/401.html") as error:
            return (
                    {
                        "Status-code": 401,
                        "Reason-phrase": "Unauthorized",
                        "WWW-Authenticate": "Basic realm=\"Login\""
                        },
                    error.read()
                    )
    type_, auth = headers['ignored']['Authorization'].split(" ", 1)
    if type_ != "Basic":
        with open("www/error/501.html") as error:
            return (
                    {
                        "Status-code": 501,
                        "Reason-phrase": "Not Implemented"
                        },
                    error.read()
                    )
    uname, pword = base64.b64decode(auth.encode()).split(b":")
    if uname == pword:
        with open("www/index.html") as index:
            return ({}, index.read())
    else:
        with open("www/error/403.html") as error:
            return (
                    {
                        "Status-code": 403,
                        "Reason-phrase": "Forbidden",
                        },
                    error.read()
                    )


if __name__ != "__main__":
    raise SystemExit

http_server = HttpServer("/home/dev/python/webserver/www",
        "www/error", port=randint(49152,65535),
        logger_folder="logs")  # , logger_file=sys.stdout)
print(f"hosting HTTP server on {http_server.host}:{http_server.port}")
http_server.add_route("/", {"GET": index})
http_server.add_route("/index", {"GET": index})
http_server.handle_http_requests()
