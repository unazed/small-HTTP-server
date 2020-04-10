#!/usr/bin/env python3
from api.http_server import HttpServer
from functools import partial
import utils
import json
import os


CONFIG_KEYS = ("host", "port", "root_dir", "logger_file")


def index(server, conn, addr, method, params, route):
    if not (data := utils.read_file("index.html")):
        return server.get_route(conn, addr, "GET", "/404")
    elif not params:
        return conn.send(utils.construct_http_response(
            200, "OK", {}, data
            ))
    return conn.send(utils.construct_http_response(
        200, "OK", {}, f"{params}"
        ))


def global_handler(server, conn, addr, method, params, route):
    path = params['path']
    return conn.send(utils.construct_http_response(
        200, "OK", {}, f"{path}"
        ))


if __name__ != "__main__":
    raise SystemExit("run at top-level")

if not os.path.isfile("./config.json"):
    raise FileNotFoundError("[WebServer] 'config.json' must exist")
    
with open("./config.json") as config:
    config = json.load(config)
    
for key in CONFIG_KEYS:
    if key not in config:
        raise KeyError(f"[WebServer] key {key!r} not in 'config.json'")

host, port = config['host'], config['port']
root_dir = config['root_dir']
logger_file = config['logger_file'] or None

utils.read_file = partial(utils.read_file, root_dir)
utils.construct_http_response = partial(utils.construct_http_response, HttpServer.SUPPORTED_HTTP_VERSION)

server = HttpServer(
        root_dir=root_dir,
        host=host,
        port=int(port),
        logger_file=logger_file
        )

server.add_route(["GET"], "/", index)
server.add_route(["GET"], "/index", index)
server.add_route(["GET"], "/*", global_handler)
server.handle_http_connections()
