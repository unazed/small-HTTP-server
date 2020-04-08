#!/usr/bin/env python3
from api.http_server import HttpServer
from api.http_server import parse_cookies
from api.http_server import parse_post
from random import randint
from hashlib import sha512
from html import escape
import datetime
import json


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


def index(conn, headers, data):
    cookies = parse_cookies(headers['ignored'].get("Cookie", ""))
    has_valid_token = (token := cookies.get("token", "")) in db.database
    with open("root/public/index.html") as index:
        return ({}, index.read().format(
                    if_logged_in_head="<a href='/login'>login</a> - <a href='/register'>register</a>" if not has_valid_token \
                            else f"logged in as <b>{db.database[token]}</b> - <a href='/logout'>logout</a>",
                    if_logged_in_body="" if not has_valid_token \
                            else "Since you're logged in, do you wanna <a href='/members'>look</a> at the user-list?",
                    time=datetime.datetime.now()
                ))


def members(conn, headers, data, *, method):
    cookies = parse_cookies(headers['ignored'].get("Cookie", ""))
    has_valid_token = cookies.get("token", "") in db.database
    if method == "GET":
        if not has_valid_token:
            with open("root/errors/403.html") as error:
                return ({"Status-code": 403, "Reason-phrase": "Forbidden"}, error.read())
        with open("root/public/members.html") as members:
            return ({}, members.read().format(
                body='<br>'.join(f"<p>{user} -- {hash_}</p>" for hash_, user in db.database.items())
                ))
    elif method == "POST":
        post = parse_post(data)
        if 'uname' not in post:
            return ({"Status-code": 301, "Location": "/members?error=invalid post data"}, "")
        elif post['uname'] not in db.database.values():
            return ({"Status-code": 301, "Location": "/members?error=user doesn't exist"}, "")
        db.remove_user(post['uname'])
        return ({"Status-code": 301, "Location": "/members"}, "")


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
        if "uname" not in post or "pword" not in post:
            return ({"Status-code": 301, "Location": "/register?error=invalid login data"}, "")
        elif post['uname'] in db.database.values():
            return ({"Status-code": 301, "Location": "/register?error=already existing username"}, "")
        t = db.add_user(escape(post['uname']), post['pword'])
        print(f"[localhost:{port}] user {post['uname']} registered")
        return ({"Status-code": 301, "Set-Cookie": f"token={t}", "Location": "/"}, "")


def logout(conn, headers, data):
    cookies = parse_cookies(headers['ignored'].get("Cookie", ""))
    has_valid_token = (token := cookies.get("token")) in db.database
    if not has_valid_token:
        return ({"Status-code": 301, "Location": "/"}, "")
    return ({
        "Status-code": 301,
        "Location": "/",
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
        port=(port := randint(49152, 65535))
        )
print(f"[localhost:{port}] address bound")
server.add_route("/", handlers={
    "GET": index
    })
server.add_route("/logout", handlers={
    "GET": logout
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
print(f"[localhost:{port}] added routes")
print(f"[localhost:{port}] listening for connections")
server.handle_http_requests()
