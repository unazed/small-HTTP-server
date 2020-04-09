#!/usr/bin/env python3
from api.http_server import HttpServer
from api.http_server import parse_cookies
from api.http_server import parse_post
from random import randint
from hashlib import sha512
from html import escape
from urllib.parse import unquote, unquote_plus
import datetime
import json
import os, shutil, sys


class Database:
    def __init__(self, filename):
        self.filename = filename
        with open(filename) as database:
            self.database = json.load(database)

    def add_user(self, username, password):
        digest = sha512()
        digest.update(f"{username}:{password}".encode())
        self.database[(t := digest.hexdigest())] = username
        with open(self.filename, "w") as db:
            json.dump(self.database, db)
        return t

    def remove_user(self, username):
        for tok, name in self.database.items():
            if name == username:
                break
        else:
            return False
        del self.database[tok]
        with open(self.filename, "w") as db:
            json.dump(self.database, db)
        return True


def conv_uname(uname):
    b = ""
    for char in uname:
        b += format(ord(char), 'x').rjust(2, '0')
    return b

def error(conn, headers, data, *, error):
    return ({}, f"""
<html>
    <head>
        <title>HTTP: {error}</title>
    </head>
    <body>
        <h1>HTTP: {error}</h2> <hr> <br>
        <p> An error has been encountered during the retrieval of this resource. </p>
    </body>
</html>
            """)


def index(conn, headers, data):
    cookies = parse_cookies(headers['ignored'].get("Cookie", ""))
    has_valid_token = (token := cookies.get("token", "")) in db.database
    error = parse_post(headers['request_uri'].query).get("error", "")
    unread = 0
    if has_valid_token and os.path.exists(f"root/users/{conv_uname(db.database[token])}"):
        unread = len(os.listdir(f"root/users/{conv_uname(db.database[token])}")) - 1
    with open("root/public/index.html") as index:
        return ({}, index.read().format(
                    if_logged_in_head="<a href='/login'>login</a> - <a href='/register'>register</a>" if not has_valid_token \
                            else f"logged in as <b>{db.database[token]}</b> - <a href='/logout'>logout</a> - <a href='/profile'>profile ({unread})</a>",
                    if_logged_in_body="" if not has_valid_token \
                            else "Since you're logged in, do you wanna <a href='/members'>look</a> at the user-list?",
                            timer="""window.onload = function() {
  var fn = function() {
    var frameElement = document.getElementById("chat");
    frameElement.contentWindow.location.href = frameElement.src + "?_=" + Math.ceil(Math.random() * 10000);
    };
  setInterval (fn, 2500);
}""",
                    error=error
                ))


def profile(conn, headers, data, *, method):
    cookies = parse_cookies(headers['ignored'].get("Cookie", ""))
    has_valid_token = (token := cookies.get("token", "")) in db.database
    if not has_valid_token:
        _, page = server.routes["/403"]["GET"](conn, {}, "")
        return ({"Status-code": 403, "Reason-phrase": "Forbidden"}, page)
    if method == "GET":
        username = conv_uname(db.database[token])
        messages = []
        error = parse_post(headers['request_uri'].query).get("error", "")
        for file_ in os.listdir(f"root/users/{username}"):
            if not os.path.isfile(f"root/users/{username}/{file_}"):
                continue
            with open(f"root/users/{username}/{file_}") as msg:
                messages.append(unquote(msg.read()))
            shutil.move(f"root/users/{username}/{file_}", f"root/users/{username}/seen/{file_}")
        with open("root/public/profile.html") as profile:
            return ({}, profile.read().format(
                username=db.database[token],
                inbox=f"<h3>{len(messages)} unread messages </h3><hr>" + '<hr>'.join(messages),
                error=error
                ))
    elif method == "POST":
        post = parse_post(data)
        if "recipient" not in post or "msg" not in post:
            return ({"Status-code": 301, "Location": "/profile?error=invalid input"}, "")
        post['recipient'] = escape(post['recipient'])
        post['msg'] = escape(unquote_plus(post['msg']))
        if post['recipient'] not in db.database.values():
            return ({"Status-code": 301, "Location": "/profile?error=user doesn't exist"}, "")
        with open(f"root/users/{conv_uname(post['recipient'])}/{randint(0, 4294967296)}", "w") as msg:
            msg.write(f"<p style='padding-left:5em'>{post['msg']}</p><br>sent from <i>{db.database[token]}</i>")
        return ({"Status-code": 301, "Location": "/profile"}, "")


def members(conn, headers, data, *, method):
    cookies = parse_cookies(headers['ignored'].get("Cookie", ""))
    has_valid_token = cookies.get("token", "") in db.database
    if method == "GET":
        if not has_valid_token:
            _, page = server.routes["/403"]["GET"](conn, {}, "")
            return ({"Status-code": 403, "Reason-phrase": "Forbidden"}, page)
        error = parse_post(headers['request_uri'].query).get("error", "")
        with open("root/public/members.html") as members:
            return ({}, members.read().format(
                body='<br>'.join(f"<p>{user} -- {hash_}</p>" for hash_, user in db.database.items()),
                error=error
                ))
    elif method == "POST":
        post = parse_post(data)
        if 'uname' not in post:
            return ({"Status-code": 301, "Location": "/members?error=invalid post data"}, "")
        post['uname'] = escape(post['uname'])
        if post['uname'] not in db.database.values():
            return ({"Status-code": 301, "Location": "/members?error=user doesn't exist"}, "")
        db.remove_user(post['uname'])
        shutil.rmtree(f"root/users/{conv_uname(post['uname'])}")
        return ({"Status-code": 301, "Location": "/members"}, "")


def get_replies(conn, headers, data):
    template = """
<html>
    <head>
        <meta http-Equiv="Cache-Control" Content="no-cache" />
        <meta http-Equiv="Pragma" Content="no-cache" />
        <meta http-Equiv="Expires" Content="0" />
    </head>
    <body>
        {chat}
    </body>
</html>"""
    with open("root/public/chat") as chat:
        a = ({
            "Connection": "close",
            'Cache-Control': 'no-cache',
            "Cache-Control#1": "no-cache, max-age=0",
            "Cache-Control#2": "no-cache, max-age=0, stale-while-revalidate=300"
            }, template.format(chat='<br>'.join(f"{msg}" for msg in reversed([*chat]))))
        return a


def make_reply(conn, headers, data):
    cookies = parse_cookies(headers['ignored'].get("Cookie", ""))
    has_valid_token = (token := cookies.get("token", "")) in db.database
    if not has_valid_token:
        return ({"Status-code": 301, "Location": "/?error=you must log-in to chat"}, "")
    elif 'reply' not in (msg := parse_post(data)):
        return ({"Status-code": 301, "Location": "/?error=invalid post parameters"}, "")
    data = escape(unquote_plus(msg['reply']))
    with open("root/public/chat", "a") as chat:
        chat.write(f"[{datetime.datetime.now()!s}] {db.database[token]}: {data}\r\n")
    return ({"Status-code": 301, "Location": "/"}, "")


def register(conn, headers, data, *, method):
    cookies = parse_cookies(headers['ignored'].get("Cookie", ""))
    has_valid_token = cookies.get("token", "") in db.database
    if method == "GET":
        with open("root/public/register.html") as register:
            return ({}, register.read().format(
                is_registered=f"You are already registered<br>" if has_valid_token \
                        else """<form action="/register" method="post">
<label>Username:</label>
<input type="text" id="uname" name="uname"><br>
<label>Password:</label>
<input type="text" id="pword" name="pword"><br><br>
<input type="submit" value="Register">
</form>
""",
                error=parse_post(q)['error'] if (q := headers["request_uri"].query) \
                        else ""
            ))
    elif method == "POST":
        if has_valid_token:
            return ({"Status-code": 301, "Location": "/register?error=already logged in"}, "")
        post = parse_post(data)
        post['uname'] = escape(post['uname'])
        if "uname" not in post or "pword" not in post:
            return ({"Status-code": 301, "Location": "/register?error=invalid login data"}, "")
        elif post['uname'] in db.database.values():
            return ({"Status-code": 301, "Location": "/register?error=already existing username"}, "")
        t = db.add_user(post['uname'], post['pword'])
        os.mkdir(f"root/users/{conv_uname(post['uname'])}")
        os.mkdir(f"root/users/{conv_uname(post['uname'])}/seen")
        print(f"[localhost:{port}] user {post['uname']} registered")
        return ({"Status-code": 301, "Set-Cookie": f"token={t}", "Location": "/"}, "")


def logout(conn, headers, data):
    cookies = parse_cookies(headers['ignored'].get("Cookie", ""))
    has_valid_token = (token := cookies.get("token")) in db.database
    if not has_valid_token:
        return ({"Status-code": 301, "Location": "/", "Cache-Control": "no-store"}, "")
    return ({
        "Status-code": 301,
        "Location": "/",
        "Cache-Control": "no-store",
        "Set-Cookie": "token=; Expires=Sat, 1 Jan 2000 00:00:00 GMT"
        }, "")


def login(conn, headers, data, *, method):
    cookies = parse_cookies(headers['ignored'].get("Cookie", ""))
    has_valid_token = cookies.get("token", "") in db.database
    if method == "GET":
        error = parse_post(headers['request_uri'].query).get("error", "")
        with open("root/public/login.html") as login:
            return ({}, login.read().format(
                    error=error,
                    is_logged="You're already logged in, do you want to <a href='/logout'>logout</a>?" if has_valid_token \
                            else """<form action="/login" method="post">
<label>Username:</label>
<input type="text" id="uname" name="uname"><br>
<label>Password:</label>
<input type="text" id="pword" name="pword"><br><br>
<input type="submit" value="Login">
</form>"""
                ))
    elif method == "POST":
        if has_valid_token:
            return ({"Status-code": 301, "Location": "/login?error=already logged in"}, "")
        post = parse_post(data)
        if "uname" not in post or "pword" not in post:
            return ({"Status-code": 301, "Location": "/login?error=invalid login data"}, "")
        digest = sha512()
        digest.update(f"{post['uname']}:{post['pword']}".encode())
        if digest.hexdigest() in db.database:
            return ({"Status-code": 301, "Set-Cookie": f"token={digest.hexdigest()}", "Location": "/"}, "")
        return ({"Status-code": 301, "Location": "/login?error=invalid credentials"}, "")


db = Database("root/logins.db")

server = HttpServer(
        root_dir="root/public/",
        error_dir="root/errors/",
        logger_folder="root/logs/",
        host='',
        port=(port := 6969),
        )
print(f"[localhost:{port}] address bound")

server.add_route(404, handlers={
    "GET": lambda *args, **kwargs: error(*args, **kwargs, error=404)
    })
server.add_route(400, handlers={
    "GET": lambda *args, **kwargs: error(*args, **kwargs, error=400)
    })
server.add_route(403, handlers={
    "GET": lambda *args, **kwargs: error(*args, **kwargs, error=403)
    })
server.add_route(405, handlers={
    "GET": lambda *args, **kwargs: error(*args, **kwargs, error=405)
    })
server.add_route(505, handlers={
    "GET": lambda *args, **kwargs: error(*args, **kwargs, error=505)
    })

server.add_route("/", handlers={
    "GET": index
    })
server.add_route("/logout", handlers={
    "GET": logout
    })
server.add_route("/get_replies", handlers={
    "GET": get_replies
    })
server.add_route("/make_reply", handlers={
    "POST": make_reply
    })
server.add_route("/members", handlers={
    "GET": lambda *args, **kwargs: members(*args, **kwargs, method="GET"),
    "POST": lambda *args, **kwargs: members(*args, **kwargs, method="POST")
    })
server.add_route("/register", handlers={
    "GET": lambda *args, **kwargs: register(*args, **kwargs, method="GET"),
    "POST": lambda *args, **kwargs: register(*args, **kwargs, method="POST")
    })
server.add_route("/login", handlers={
    "GET": lambda *args, **kwargs: login(*args, **kwargs, method="GET"),
    "POST": lambda *args, **kwargs: login(*args, **kwargs, method="POST")
    })
server.add_route("/profile", handlers={
    "GET": lambda *args, **kwargs: profile(*args, **kwargs, method="GET"),
    "POST": lambda *args, **kwargs: profile(*args, **kwargs, method="POST")
    })
print(f"[localhost:{port}] added routes")
print(f"[localhost:{port}] listening for connections")
server.handle_http_requests()
