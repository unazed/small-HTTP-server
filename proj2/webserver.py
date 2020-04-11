#!/usr/bin/env python3
from api.http_server import HttpServer
from database import LoginDatabase
from functools import partial
from forum import Forum
from html import escape
import hashlib
import utils
import json
import os


CONFIG_KEYS = ("host", "port", "root_dir", "logger_file", "database_file")
FORUM_TITLE = "Unazed's Forum"
ACCEPTABLE_WILDCARDS = ("css", "js")


def index(server, conn, addr, method, params, route, cookies):
    username = server._db.get_user(cookies.get("token", None))
    if not (data := utils.read_file("index.html")):
        return server.get_route(conn, addr, "GET", "/404")

    elif not (params["GET"] or params["POST"]):
        return conn.send(utils.construct_http_response(
            200, "OK", {}, utils.determine_template(
                data, username,
                forum_title=FORUM_TITLE,
                body=f"""
                <ul class="sections">
                """ +
                '\n'.join("<li> <a href='/index?section=%d'>%s</a> </li>" % (info['sid'], section) for section, info in server._forum.sections.items())
                + """
                </ul>
                """
                )
            ))

    return conn.send(utils.construct_http_response(
        200, "OK", {}, utils.determine_template(
            data, username,
            forum_title=FORUM_TITLE,
            body=params
            )
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
        elif not (t := server._db.add_user(
                params['POST']['username'],
                params['POST']['password'],
                properties={
                    "uid": len(server._db.database) + 1,
                    "threads": 0,
                    "posts": 0,
                    "reputation": 0,
                    "rank": None
                    }
                )):
            return server.get_route(conn, addr, "GET", "/register?error=The username entered is either invalid or taken.")
        print(f"[WebServer] user registered: {params['POST']['username']!r}")
        return conn.send(utils.construct_http_response(
            301, "Redirect", {
                "Location": "/index",
                "Set-Cookie": f"token={t}"
                }, ""
            ))


def login(server, conn, addr, method, params, route, cookies):
    username = server._db.get_user(cookies.get("token", None))
    if not (index := utils.read_file("index.html")):
        return server.get_route(conn, addr, "GET", "/404")
    elif not (data := utils.read_file("login.html")):
        return server.get_route(conn, addr, "GET", "/404")
    elif username:
        return conn.send(utils.consruct_http_response(
            403, "Forbidden", {}, utils.determine_template(
                index, username,
                forum_title=FORUM_TITLE,
                body=f"""
                <p>You're already logged in under {username!r}, did you
                want to <a href="/logout">log out</a>?</p>
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
        if not ('username' in params['POST'] or 'password' in params['POST']):
            return server.get_route(conn, addr, "GET", "/400")
        elif (u := params['POST']['username']) not in server._db.database:
            return server.get_route(conn, addr, "GET", "/403")
        elif not server._db.get_user((t := hashlib.sha256(f"{u}:{params['POST']['password']}".encode()).hexdigest())):
            return server.get_route(conn, addr, "GET", "/403")
        return conn.send(utils.construct_http_response(
            301, "Redirect", {
                "Set-Cookie": f"token={t}",
                "Location": "/"
                }, ""
            ))


def logout(server, conn, addr, method, param, route, cookies):
    username = server._db.get_user(cookies.get("token", None))
    if not username:
        return conn.send(utils.construct_http_response(
            301, "Redirect", {
                "Location": "/",
                "Cache-Control": "no-store"
                }, ""
            ))
    return conn.send(utils.construct_http_response(
        301, "Redirect", {
            "Location": "/",
            "Set-Cookie": "token=; expires=Thu, 01 Jan 1970 00:00:00 GMT",
            "Cache-Control": "no-store"
            }, ""
        ))


def error_handler(server, conn, addr, method, param, route, cookies):
    host = route['host']
    if not (index := utils.read_file("index.html")):
        index = """
        <html>
            <head>
                <title>Forum Index</title>
            </head>
            <body>
                <h1>{forum_title} - Error</h1>
                <hr>
                {body}
            </body>
        </html>
        """
    status = 400
    if host[1:].isdigit():
        status = int(host[1:])

    return conn.send(utils.construct_http_response(
        status, "Error", {}, index.format(
                forum_title=FORUM_TITLE,
                body="<p>An error has been encountered during the processing of this request.<br>" \
                    f"Code: {host}</p>",
                items=""
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
server._forum = Forum("forum/")

server._forum.add_section("Lounge", ["member", "admin"])

server.add_route(["GET"], "/", index)
server.add_route(["GET"], "/index", index)

server.add_route(["GET", "POST"], "/login", login)
server.add_route(["GET", "POST"], "/register", register)
server.add_route(["GET"], "/logout", logout)

server.add_route(["GET"], "/404", error_handler)
server.add_route(["GET"], "/403", error_handler)
server.add_route(["GET"], "/400", error_handler)
server.add_route(["GET"], "/405", error_handler)

server.add_route(["GET"], "/*", global_handler)
server.handle_http_connections()
