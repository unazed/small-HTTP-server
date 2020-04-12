#!/usr/bin/env python3
from api.http_server import HttpServer
from database import LoginDatabase
from functools import partial
from forum import Forum
from html import escape
import hashlib
import json
import os
import utils


CONFIG_KEYS = ("host", "port", "root_dir", "logger_file", "database_file")
FORUM_TITLE = "Unazed's Forum"
ACCEPTABLE_WILDCARDS = ("css", "js")


def index(server, conn, addr, method, params, route, cookies):
    username = server._db.get_user(cookies.get("token", None)) or "Guest"
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
                '\n'.join(
                    f"<li> <a href='/index?sid={info['sid']}'>{section}</a> </li>" \
                            for section, info in server._forum.sections.items() \
                            if any((server._db.database[username][1]['role'] == role) for role in info['allowed_roles'])
                    )
                + """
                </ul>
                """
                )
            ))
    elif (g := params["GET"]) and not params["POST"]:
        sid, tid = g.get("sid"), g.get("tid")
        if sid and not tid:
            if not (section := server._forum.get_section(sid)):
                return server.get_route(conn, addr, "GET", "/400")
            threads = []
            for thread in section[1]['threads']:
                with open(os.path.join(server._forum.root_dir, section[0], str(thread), "info")) as info:
                    threads.append(json.load(info))
            threads = sorted(threads, key=lambda k: int(k['tid']), reverse=True)
            return conn.send(utils.construct_http_response(
                200, "OK", {}, utils.determine_template(
                    data, username,
                    forum_title=FORUM_TITLE,
                    body=f"""
                    <h3 id='subtitle'>{section[0]}</h3>
                    <form id="make_thread_div" action="/make_thread" method="get">
                        <input type="hidden" name="sid" value="{sid}" />
                        <input id="thread_btn" type="submit" value="Make thread" />
                    </form>
                    <div id="thd_info_div">
                        <p id="post_count">Posts: n/a</p>
                        <p id="creator_ip">Author: n/a</p>
                    </div>
                    <div style="clear: both;"> </div>
                    <ul class="threads">
                    """ +
                    "\n".join(
                        f"""
                        <li>
                            <a href='/index?sid={sid}&tid={thread['tid']}'
                             onmouseover="show_info({len(server._forum.get_replies(section[0], thread['tid']))}, '{utils.censor_ip(thread['ip'])}')"
                             onmouseout="clear_info()">
                                {thread['title']}
                                <label style="color: {server._forum.roles[server._db.database[thread['username']][1]['role']]['background-color']}" class='username'>
                                    {thread['tid']} {thread['username']}
                                </label>
                            </a>
                        </li>""" \
                                for thread in threads
                        )
                    + """
                    </ul>
                    """
                    )
                ))
        elif (sid := g.get("sid", "")) and (tid := g.get("tid", "")):
            if not (section := server._forum.get_section(sid)):
                return server.get_route(conn, addr, "GET", "/400")
            elif not tid.isdigit() or (tid := int(tid)) not in section[1]['threads']:
                return server.get_route(conn, addr, "GET", "/400")
            replies = server._forum.get_replies(section[0], tid)
            thread_dir = os.path.join(server._forum.root_dir, section[0], str(tid))
            with open(os.path.join(thread_dir, "info")) as info:
                thread = json.load(info)
            if not (author := server._db.database.get((u := thread['username']), "")):
                # invalid author?
                return conn.send(utils.construct_http_response(
                    301, "Redirect", {"Location": f"/index?sid={sid}"}, ""
                    ))
            author = author[1]
            return conn.send(utils.construct_http_response(
                200, "OK", {}, utils.determine_template(
                    data, username,
                    forum_title=FORUM_TITLE,
                    body=f"""
                    <p id="thd_title"><a href="/index?sid={sid}" id="title_sid">{section[0]}</a> > {thread['title']}</p>
                    <div id="thread">
                        <div id="profile">
                            <p id="username"><label id="uid">{author['uid']}</label>{u}</p>
                            <p id="threads">Threads: {author['threads']}</p> 
                            <p id="posts">Posts: {author['posts']}</p> 
                            <p id="reputation">Reputation: {author['reputation']}</p>
                        </div>
                        <div id="post">
                            <p id="content">{thread['content']}</p>
                        </div>
                    </div>
                    <ul class="posts">
                    """ +
                    ''.join(f"""
                        <li id="post">
                            <div id="post_div">
                                <p id="ip_sig">{utils.censor_ip(reply['ip'])}</p>
                                <a style=" """ +
                                ';'.join(f"{k}: {v}" for k, v in server._forum.roles[server._db.database[reply['username']][1]['role']].items())
                                + f""" "id="username" href="/profile?uid={reply['uid']}">{reply['username']}</a>
                                <p id="post_content">{reply['content']}</p>
                            </div>
                        </li>
                        """ for reply in sorted(replies, key=lambda r: r['pid']))
                    + """
                    </ul>
                    <form id="post_form" method="post"
                     onsubmit="postbtn.disabled=true;postbtn.value='Posting...'">
                        <textarea id="postbox" name="post"> </textarea>
                        <input type="hidden" name="action" value="make_reply" />
                        <input name="postbtn" id="postbtn" type="submit" value="Post" />
                    </form>
                    """
                    )
                ))
    elif g and (p := params['POST']):
        tid, sid = g.get("tid", ""), g.get("sid", "")
        if not sid:
            return server.get_route(conn, addr, "GET", "/400")
        elif not sid.isdigit():
            return server.get_route(conn, addr, "GET", "/400")
        sid = int(sid)
        if not (section := server._forum.get_section(sid)):
            return server.get_route(conn, addr, "GET", "/404")
        elif server._db.database[username][1]['role'] not in section[1]['allowed_roles']:
            return server.get_route(conn, addr, "GET", "/403")
        elif not (action := p.get("action", "")):
            return server.get_route(conn, addr, "GET", "/400")

        if action == "make_thread":
            if not (title := p.get("title", "")) or \
                    not (content := p.get("content", "")):
                return server.get_route(conn, addr, "GET", "/400")
            tid = server._forum.make_thread(addr[0], section[0], username, title, content)
            server._db.database[username][1]['threads'] += 1
            return conn.send(utils.construct_http_response(
                301, "Redirect", {"Location": f"/index?sid={sid}&tid={tid}"}, ""
                ))
        elif not tid or not tid.isdigit():
            return server.get_route(conn, addr, "GET", "/400")
        tid = int(tid)
        if tid not in section[1]['threads']:
            return server.get_route(conn, addr, "GET", "/404")

        if action == "make_reply":
            if not (content := p.get("post", "")):
                return server.get_route(conn, addr, "GET", "/400")
            server._forum.make_reply(addr[0], section[0], tid, username, content)
            server._db.database[username][1]['posts'] += 1
            return conn.send(utils.construct_http_response(
                301, "Redirect", {"Location": f"/index?tid={tid}&sid={sid}"}, ""
                ))


def register(server, conn, addr, method, params, route, cookies):
    username = server._db.get_user(cookies.get("token", None)) or "Guest"
    if not (index := utils.read_file("index.html")):
        return server.get_route(conn, addr, "GET", "/404")
    elif not (data := utils.read_file("register.html")):
        return server.get_route(conn, addr, "GET", "/404")
    elif username != "Guest":
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
                    "role": "member"
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
    username = server._db.get_user(cookies.get("token", None)) or "Guest"
    if not (index := utils.read_file("index.html")):
        return server.get_route(conn, addr, "GET", "/404")
    elif not (data := utils.read_file("login.html")):
        return server.get_route(conn, addr, "GET", "/404")
    elif username != "Guest":
        return conn.send(utils.construct_http_response(
            403, "Forbidden", {}, utils.determine_template(
                index, username,
                forum_title=FORUM_TITLE,
                body=f"""
                <p>You're already logged in under {username!r}, did you
                want to <a id="logout" href="/logout">log out</a>?</p>
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
    username = server._db.get_user(cookies.get("token", None)) or "Guest"
    if username == "Guest":
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


def make_thread(server, conn, addr, method, params, route, cookies):
    username = server._db.get_user(cookies.get("token", "")) or "Guest"
    if not (index := utils.read_file("index.html")):
        return server.get_route(conn, addr, "GET", "/404")
    elif not (sid := params["GET"].get("sid", "")):
        return server.get_route(conn, addr, "GET", "/400")
    elif not sid.isdigit() or not (section := server._forum.get_section(sid)):
        return server.get_route(conn, addr, "GET", "/404")
    elif server._db.database[username][1]['role'] not in \
            section[1]['allowed_roles']:
        return server.get_route(conn, addr, "GET", "/403")
    return conn.send(utils.construct_http_response(
        200, "OK", {}, utils.determine_template(
            index, username,
            forum_title=FORUM_TITLE,
            body=f"""
            <form action="/index?sid={sid}" method="post"
             onsubmit="content.disabled=true;content.value="Posting..."">
                <input type="hidden" name="action" value="make_thread" />
                <label>Title: <label>
                <input id="thd_title" type="text" name="title" />
                <label>Content: </label>
                <textarea id="thd_content" name="content"> </textarea>
                <input type="submit" value="Post" />
            </form>
            """
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
            200, "OK", {"Cache-Control": "no-store"}, data
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
server._forum = Forum(server._db, "forum/")

server._db.add_user("Admin", "", properties={
    "uid": 1,
    "role": "admin",
    "threads": 0,
    "posts": 0,
    "reputation": 0
    })

server._db.add_user("Guest", "", properties={
    "uid": 2,
    "role": "guest",
    "threads": 0,
    "posts": 0,
    "reputation": 0
    })

server._forum.add_section("Public", ["guest", "member", "admin"])
server._forum.add_section("Lounge", ["member", "admin"])
server._forum.add_section("Admin-Only", ["admin"])

server.add_route(["GET", "POST"], "/", index)
server.add_route(["GET", "POST"], "/index", index)

server.add_route(["GET", "POST"], "/login", login)
server.add_route(["GET", "POST"], "/register", register)
server.add_route(["GET"], "/logout", logout)
server.add_route(["GET"], "/make_thread", make_thread)

server.add_route(["GET"], "/404", error_handler)
server.add_route(["GET"], "/403", error_handler)
server.add_route(["GET"], "/400", error_handler)
server.add_route(["GET"], "/405", error_handler)

server.add_route(["GET"], "/*", global_handler)
server.handle_http_connections()
