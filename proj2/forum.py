#!/usr/bin/env python3
from api.http_server import HttpServer
from database import LoginDatabase
from functools import partial
from html import escape
import utils
import json
import os


CONFIG_KEYS = ("host", "port", "root_dir", "logger_file", "database_file")
FORUM_TITLE = "Unazed's Forum"
ACCEPTABLE_WILDCARDS = ("css", "js")


def index(server, conn, addr, method, params, route, cookies):
    print(cookies)
    username = server._db.get_user(cookies.get("token", None))
    if not (data := utils.read_file("index.html")):
        return server.get_route(conn, addr, "GET", "/404")

    elif not (params["GET"] or params["POST"]):
        return conn.send(utils.construct_http_response(
            200, "OK", {}, utils.determine_template(
                data, username,
                forum_title=FORUM_TITLE,
                body="<p>nothing to see here yet</p>"
                )
            ))

    return conn.send(utils.construct_http_response(
        200, "OK", {}, utils.determine_template(
            data, username,
            forum_title=FORUM_TITLE,
            body=params
            )
        ))


def global_handler(server, conn, addr, method, params, route, cookies):
    path = params['path']
    _, *ext = path.split(".")
    if not ext:
        return server.get_route(conn, addr, "GET", "/404")
    if ext[0] in ACCEPTABLE_WILDCARDS:
        if not (data := utils.read_file(path)):
            return server.get_route(conn, addr, "GET", "/404")
        return conn.send(utils.construct_http_response(
            200, "OK", {}, data
            ))


def register(server, conn, addr, method, params, route, cookies):
    username = server._db.get_user(cookies.get("token", None)) 
    if not (index := utils.read_file("index.html")):
        return server.get_route(conn, addr, "GET", "/404")
    elif not (data := utils.read_file("register.html")):
        return server.get_route(conn, addr, "GET", "/404")
    elif username:
        return conn.send(utils.construct_http_response(
            403, "Forbidden", {}, utils.determine_template(
                index, username,
                forum_title=FORUM_TITLE,
                body=f"""
                <p>You've already registered under {username!r}.</p>
                """
                )
            ))

    if method == "GET":
        error = escape(params["GET"].get("error", ""))
        return conn.send(utils.construct_http_response(
            200, "OK", {}, utils.determine_template(
                index, username,
                forum_title=FORUM_TITLE,
                body=data.format(error=error)
                )
            ))
    elif method == "POST":
        if 'username' not in params['POST'] or 'password' not in params['POST']:
            return server.get_route(conn, addr, "GET", "/400")
        elif not (t := server._db.add_user(params['POST']['username'], params['POST']['password'])):
            return server.get_route(conn, addr, "GET", "/register?error=Username exists.")
        print(f"[WebServer] user registered: {params['POST']['username']!r}")
        return conn.send(utils.construct_http_response(
            301, "Redirect", {
                "Location": "/index",
                "Set-Cookie": f"token={t}"
                }, ""
            ))


def login(server, conn, addr, method, params, route, cookies):
    pass


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
database_file = config['database_file']

utils.read_file = partial(utils.read_file, root_dir)
utils.construct_http_response = partial(utils.construct_http_response, HttpServer.SUPPORTED_HTTP_VERSION)

server = HttpServer(
        root_dir=root_dir,
        host=host,
        port=int(port),
        logger_file=logger_file
        )

server._db = LoginDatabase(database_file)

server.add_route(["GET"], "/", index)
server.add_route(["GET"], "/index", index)

server.add_route(["GET", "POST"], "/login", login)
server.add_route(["GET", "POST"], "/register", register)

server.add_route(["GET"], "/*", global_handler)
server.handle_http_connections()
