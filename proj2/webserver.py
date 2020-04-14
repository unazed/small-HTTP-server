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
            elif server._db.database[username][1]['role'] not in section[1]['allowed_roles']:
                return server.get_route(conn, addr, "GET", "/403")
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
                    <form id="make_thread_div" action="/make-thread" method="get">
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
                                ';'.join(f"{k}: {v}" for k, v in server._forum.roles[server._db.database.get(reply['username'], server._db.database["Guest"])[1]['role']].items())
                                + f""" "id="username" href="/profile?uid={reply['uid']}">{reply['username'] if reply['username'] in server._db.database else "<s>" + reply['username'] + "</s>"}</a>
                                <p id="post_content">{reply['content']}</p>
                            </div>
                        </li>
                        """ for reply in sorted(replies, key=lambda r: r['pid']))
                    + """
                    </ul>
                    <form id="post_form" method="post"
                     onsubmit="postbtn.disabled=true;postbtn.value='Posting...'">
                        <textarea id="postbox" name="post"></textarea>
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
        print(sid, p)
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
            server._db.database[username][1]['threads_ref'].append({
                'sid': section[1]['sid'],
                'tid': tid,
                'title': title,
                'content': content
                })
            server._db.write_changes()
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
            pid = server._forum.make_reply(addr[0], section[0], tid, username, content)
            server._db.database[username][1]['posts'] += 1
            server._db.database[username][1]['posts_ref'].append({
                'tid': tid,
                'pid': pid,
                'sid': section[1]['sid'],
                "section": section[0]
                })
            server._db.write_changes()
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
                escape(params['POST']['username']),
                params['POST']['password'],
                properties={
                    "uid": len(server._db.database) + 1,
                    "ip": addr[0],
                    "threads": 0,
                    "threads_ref": [],
                    "posts": 0,
                    "posts_ref": [],
                    "reputation": 0,
                    "reputation_content": {},
                    "role": "member",
                    "biography": "",
                    "inbox": []
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
        elif not server._db.get_user((t := hashlib.sha256(f"{escape(u)}:{params['POST']['password']}".encode()).hexdigest())):
            return server.get_route(conn, addr, "GET", "/403")
        print(u, params['POST']['password'])
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
                <textarea id="thd_content" name="content"></textarea>
                <input type="submit" value="Post" />
            </form>
            """
            )
        ))


def profile(server, conn, addr, method, params, route, cookies):
    username = server._db.get_user(cookies.get("token", "")) or "Guest"
    if not (index := utils.read_file("index.html")):
        return server.get_route(conn, addr, "GET", "/404")
    g = params["GET"].get("uid", "")
    if not g and username == "Guest":
        return server.get_route(conn, addr, "GET", "/403")
    elif not g:
        g = server._db.database[username][1]['uid']
    elif not g.isdigit():
        return server.get_route(conn, addr, "GET", "/400")
    g = int(g)
    for name, prop in server._db.database.items():
        if prop[1]['uid'] == g:
            found = name
            break
    else:
        return server.get_route(conn, addr, "GET", "/404")
    if not (action := params["GET"].get("action")):
        role_color = server._forum.roles[(role := prop[1]['role'])]['background-color']
        return conn.send(utils.construct_http_response(
            200, "OK", {}, utils.determine_template(
                    index, username,
                    forum_title=FORUM_TITLE,
                    body=f"""
                    <p style="background-image: linear-gradient(to right, #2e2e2e, {role_color})" id="profile_username">{name}</p>
                    <div id="profile_content">
                        <div id="column">
                            <div id="profile_info">
                                <p id="profile_uid">UID {g}</p>
                                <p id="profile_threads">Threads: {prop[1]['threads']} <a class="profile_link" href="/profile?uid={g}&action=view_threads">view threads</a></p>
                                <p id="profile_posts">Posts: {prop[1]['posts']} <a class="profile_link" href="/profile?uid={g}&action=view_posts">view posts</a></p>
                                <p id="profile_reputation">Reputation: {prop[1]['reputation']} <a class="profile_link" href="/profile?uid={g}&action=give_reputation">give reputation</a></p>
                                <p id="profile_pm"><a id="profile_pm" href="/profile?uid={g}&action=make_pm">Send Message</a></p>
                                """ +
                                ["", f"""
                                <p id="profile_edit"><a id="profile_edit" href="/profile?uid={g}&action=edit_profile">Edit Profile</a></p>
                                    """
                                    ][username == name]
                                + """
                            </div>
                            """+ ["", f"""
                            <div id="admin_prompt">
                                <p id="profile_ip">IP: {prop[1]['ip']}</p>
                                """ +
                                ["",  (f"""
                                    <p id="profile_delete"><a id="profile_delete" href="/profile?uid={g}&action=delete">Delete {name}</a></p>
                                    """ if server._db.database[name][1]['role'] not in ("guest", "admin") else "") +     
                                    f"""
                                    <p id="profile_aedit"><a id="profile_aedit" href="/profile?uid={g}&action=edit_profile">Edit {name}</a></p>
                                    """
                                    ][username != name]  # fuck ternary
                                + """
                            </div>
                        """][server._db.database[username][1]['role'] == "admin"]
                            + f"""
                        </div>
                        <div id="biography">
                            <p id="biography">{prop[1].get("biography", "No biography") or "No biography"}</p>
                        </div>
                        <div id="reputation">
                            <p id="reputation_title">Reputation</p>
                                """ +
                                    (("<ul id='reputation_list'>" + ''.join(
                                        f"""
                                        <li style="border-left: 1px solid {utils.sign(int(tup[0]))}">
                                            <p class="reputation-item">
                                                <label id="reputation-num" style="color: {utils.sign(int(tup[0]))}">{tup[0]}</label> {given_by}: {tup[1]}
                                            </p>
                                        </li>
                                        """
                                        for given_by, tup in rep.items())
                                        + "</ul>") if (rep := prop[1]['reputation_content']) else "<p id='reputation-empty'>No reputation listing</p>")
                                + """
                        </div>
                    </div>
                    """
                )
            ))

    if action == "give_reputation":
        return conn.send(utils.construct_http_response(
            200, "OK", {}, utils.determine_template(
                index, username,
                forum_title=FORUM_TITLE,
                body=f"""
                <form id="reputation-form" action="/profile_action" method="post"
                 onsubmit="this.give_btn.disabled=true; this.give_btn.value='Giving...';">
                    <input type="hidden" name="uid" value="{g}" />
                    <input type="hidden" name="action" value="give_reputation" />
                    <textarea name="content"></textarea>
                    <label>-1</label>
                    <input type="radio" name="num" value="-1" />

                    <label>0</label>
                    <input type="radio" name="num" value="0" />

                    <label>+1</label>
                    <input type="radio" name="num" value="1" />
                    <input id="give_btn" type="submit" value="Give Reputation" />
                </form>
                """
                )
            ))
    elif action == "delete":
        role = server._db.database[name][1]['role']
        if role in ("admin", "guest"):
            return server.get_route(conn, addr, "GET", "/403")
        elif server._db.database[username][1]['role'] != "admin":
            return server.get_route(conn, addr, "GET", "/400")
        elif not server._db.remove_user(name):
            return server.get_route(conn, addr, "GET", "/404")
        return conn.send(utils.construct_http_response(
            301, "Redirect", {"Location": "/index"}, ""
            ))
    elif action == "edit_profile":
        if server._db.database[username][1]['uid'] != g and \
                server._db.database[username][1]['role'] != "admin":
            return server.get_route(conn, addr, "GET", "/403")
        return conn.send(utils.construct_http_response(
            200, "OK", {}, utils.determine_template(
                index, username,
                forum_title=FORUM_TITLE,
                body=f"""
                <form method="post" action="/profile_action"
                 onsubmit="this.submit_btn.disabled=true;this.submit_btn.value='Updating...';">
                    <input type="hidden" name="uid" value="{g}" />
                    <input type="hidden" name="action" value="edit_profile" />
                    <label>Biography:</label>
                    <textarea name="content"></textarea>
                    <input type="submit" name="submit_btn" value="Update" />
                </form>
                """
                )
            ))
    elif action == "view_posts":
        posts = []
        for reply in server._db.database[name][1]['posts_ref']:
            with open(os.path.join(server._forum.root_dir, reply['section'], str(reply['tid']), f"{reply['pid']}.reply")) as content, \
                    open(os.path.join(server._forum.root_dir, reply['section'], str(reply['tid']), "info")) as info:
                posts.append({
                    'tid': reply['tid'],
                    'sid': reply['sid'],
                    'pid': reply['pid'],
                    'content': json.load(content)['content'],
                    'title': json.load(info)['title']
                    })
        return conn.send(utils.construct_http_response(
            200, "OK", {}, utils.determine_template(
                index, username,
                forum_title=FORUM_TITLE,
                body="<div id='posts'> <p style='font-size: larger'>Posts</p> <ul>" +
                ''.join(f"""
                    <li>
                        <p id="partial">
                             <a id="link" href="/index?sid={reply['sid']}&tid={reply['tid']}">
                                {reply['pid']} {reply['title']}:
                            </a>
                            {reply['content'][:100] + "..." if len(reply['content']) >= 100 else reply['content']}
                        </p>
                    </li>
                    """ for reply in posts)
                + "</ul></div>"
                )
            ))
    elif action == "view_threads":
        return conn.send(utils.construct_http_response(
            200, "OK", {}, utils.determine_template(
                index, username,
                forum_title=FORUM_TITLE,
                body="<div id='posts'> <p style='font-size: larger'>Threads</p> <ul>" +
                ''.join(f"""
                    <li>
                        <p id="partial">
                             <a id="link" href="/index?sid={thread['sid']}&tid={thread['tid']}">
                                {thread['tid']} {thread['title']}:
                            </a>
                            {thread['content'][:100] + "..." if len(thread['content']) >= 100 else thread['content']}
                        </p>
                    </li>
                    """ for thread in server._db.database[name][1]['threads_ref'])
                + "</ul></div>"
                )
            ))
    elif action == "make_pm":
        return conn.send(utils.construct_http_response(
            200, "OK", {}, utils.determine_template(
                index, username,
                forum_title=FORUM_TITLE,
                body=f"""
                <form method="post" action="/profile_action"
                 onsubmit="this.btn.disabled=true;this.btn.value='Sending...';">
                    <input type="hidden" name="action" value="make_pm" />
                    <input type="hidden" name="uid" value="{g}" />
                    <label>Title:</label>
                    <input type="text" name="title" />
                    <label>Content:</label>
                    <textarea name="content"></textarea>
                    <input id="btn" type="submit" value="Send PM" />
                </form>
                """
                )
            ))
    else:
        return server.get_route(conn, addr, "GET", "/400")


def profile_action(server, conn, addr, method, params, route, cookies):
    username = server._db.get_user(cookies.get("token", "")) or "Guest"
    properties = server._db.database[username][1]
    print(params)
    if not (index := utils.read_file("index.html")):
        return server.get_route(conn, addr, "GET", "/404")
    elif not (action := params["POST"].get("action", "")):
        return server.get_route(conn, addr, "GET", "/400")
    
    if not (uid := params['POST'].get("uid", "")):
        return server.get_route(conn, addr, "GET", "/400")
    elif not uid.isdigit():
        return server.get_route(conn, addr, "GET", "/400")
    uid = int(uid)
    for recv_name, recv_properties in server._db.database.items():
        if recv_properties[1]['uid'] == uid:
            break
    else:
        return server.get_route(conn, addr, "GET", "/404")

    if action == "give_reputation":
        if not (rating := params['POST'].get("num", "")):
            return server.get_route(conn, addr, "GET", "/400")
        elif not rating in ("-1", "0", "1"):
            return server.get_route(conn, addr, "GET", "/400")
        elif not (content := params['POST'].get('content', '')):
            return server.get_route(conn, addr, "GET", "/400")
        elif recv_name == username:
            return server.get_route(conn, addr, "GET", "/400")
        rating = int(rating)
        server._db.database[recv_name][1]['reputation_content'][username] = [rating, escape(content[:100]) if content.strip() else "<i>No comment</i>"]
        server._db.database[recv_name][1]['reputation'] = sum(rep[0] for rep in server._db.database[recv_name][1]['reputation_content'].values())
        server._db.write_changes()
        return conn.send(utils.construct_http_response(
            301, "Redirect", {"Location": f"/profile?uid={uid}"}, ""
            ))
    elif action == "edit_profile":
        if not (content := params['POST'].get("content", "")):
            return server.get_route(conn, addr, "GET", "/400")
        elif username != recv_name and not server._db.database[username][1]['role'] == "admin":
            return server.get_route(conn, addr, "GET", "/403")
        server._db.database[recv_name][1]['biography'] = escape(content)
        server._db.write_changes()
        return conn.send(utils.construct_http_response(
            301, "Redirect", {"Location": f"/profile?uid={uid}"}, ""
            )) 
    elif action == "make_pm":
        if not (content := params['POST'].get("content", "")):
            return server.get_route(conn, addr, "GET", "/400")
        elif not (title := params["POST"].get("title", "")):
            return server.get_route(conn, addr, "GET", "/400")
        server._db.database[recv_name][1]['inbox'].append({
            "id": len(server._db.database[recv_name][1]['inbox']) + 1,
            "from": username,
            "title": title,
            "content": content,
            "type": "received"
            })
        server._db.database[username][1]['inbox'].append({
            "id": len(server._db.database[username][1]['inbox']) + 1,
            "to": recv_name,
            "title": title,
            "content": content,
            "type": "sent"
            })
        server._db.write_changes()
        return conn.send(utils.construct_http_response(
            301, "Redirect", {"Location": f"/profile?uid={uid}"}, ""
            ))


def about(server, conn, addr, method, params, route, cookies):
    username = server._db.get_user(cookies.get("token", "")) or "Guest"
    if not (index := utils.read_file("index.html")):
        return server.get_route(conn, addr, "GET", "/400")
    return conn.send(utils.construct_http_response(
        200, "OK", {}, utils.determine_template(
            index, username,
            forum_title=FORUM_TITLE,
            body="""
            <p>As written below, this is a HTTP server written solely in Python from the socket level,
               and one may find the source <a href="https://github.com/unazed/small-http-server" style="color: white; text-decoration: none;">here</a>.
               It is not designed for efficiency, speed nor security, it is simply just a side-project. The web
               design is entirely custom. <br>
               The start date is Apr, 7, 2020; and the completion date is unset.</p>
            """
            )
        ))


def inbox(server, conn, addr, method, params, route, cookies):
    username = server._db.get_user(cookies.get('token', '')) or "Guest"
    if not (index := utils.read_file("index.html")):
        return server.get_route(conn, addr, "GET", "/400")
    sent, received = [], []
    for pm in server._db.database[username][1]['inbox']:
        if pm['type'] == "received":
            received.append(pm)
        elif pm["type"] == "sent":
            sent.append(pm)
    return conn.send(utils.construct_http_response(
        200, "OK", {}, utils.determine_template(
            index, username,
            forum_title=FORUM_TITLE,
            body=f"""
            <div id="received">
                <p id="title">Received PMs</p>
                <div id="pm-list">
                    <ul>
                    """ +
                        ''.join(
                            f"""
                            <li onclick="show_pm('from-pm-view', 'from-pm', {pm['id']});">
                                <p id="from">{pm['from']} <label id="pm-title">{pm['title']}</label></p>
                            </li>
                            """
                            for pm in received
                            )
                    + """
                    </ul>
                    <div id="from-pm-view">
                    """ +
                        ''.join(
                            f"""
                            <div style="display: none;" id="from-pm-{pm['id']}">
                                <p id="content">{pm['content']}</p>
                            </div>
                            """
                            for pm in received
                        )
                    + """
                    </div>
                </div>

           </div>

            <div id="sent">
                <p id="title">Sent PMs</p>
                <div id="pm-list">
                    <ul>
                    """ +
                    ''.join(
                        f"""
                        <li onclick="show_pm('to-pm-view', 'to-pm', {pm['id']});">
                            <p id="to">{pm['to']} <label id="pm-title">{pm['title']}</label></p> 
                        </li>
                        """ for pm in sent
                        )
                    + """
                    </ul>
                    <div id="to-pm-view">
                    """ +
                        ''.join(
                            f"""
                            <div style="display: none;" id="to-pm-{pm['id']}">
                                <p type="hidden" id="content">{pm['content']}</p>
                            </div>
                            """
                            for pm in sent
                        )
                    + """
                    </div>
                </div>
            </div>
            """
            )
        ))


def chat(server, conn, addr, method, params, route, cookies):
    pass


def member_list(server, conn, addr, method, params, route, cookies):
    username = server._db.get_user(cookies.get("token", "")) or "Guest"
    if not (index := utils.read_file("index.html")):
        return server.get_route(conn, addr, "GET", "/404")
    return conn.send(utils.construct_http_response(
        200, "OK", {}, utils.determine_template(
            index, username,
            forum_title=FORUM_TITLE,
            body=f"""
            <div id="member-list">
                <p id="subtitle">Member listing</p>
                <ul id="member-list">
                """ +
                '\n'.join(f"""
                    <li style="background-image: linear-gradient(to right, #2e2e2e, {server._forum.roles[info[1]['role']]['background-color']})">
                        <p class="member-item">
                            <a href="/profile?uid={info[1]['uid']}">{member}</a>
                        </p>
                    </li>
                    """ for member, info in server._db.database.items())
            + """
                </ul>
            </div>
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
    "threads_ref": [],
    "posts": 0,
    "posts_ref": [],
    "reputation": 0,
    "reputation_content": {},
    "ip": "127.0.0.1",
    "biography": "",
    "inbox": []
    })

server._db.add_user("Guest", "", properties={
    "uid": 2,
    "role": "guest",
    "threads": 0,
    "threads_ref": [],
    "posts": 0,
    "posts_ref": [],
    "reputation": 0,
    "reputation_content": {},
    "ip": "127.0.0.1",
    "biography": "",
    "inbox": []
    })

server._forum.add_section("Public", ["guest", "member", "admin"])
server._forum.add_section("Lounge", ["member", "admin"])
server._forum.add_section("Admin-Only", ["admin"])

print(server._forum.sections)

server.add_route(["GET", "POST"], "/", index)
server.add_route(["GET", "POST"], "/index", index)

server.add_route(["GET", "POST"], "/login", login)
server.add_route(["GET", "POST"], "/register", register)
server.add_route(["GET"], "/logout", logout)
server.add_route(["GET"], "/make-thread", make_thread)
server.add_route(["GET"], "/member-list", member_list)
server.add_route(["GET"], "/profile", profile)
server.add_route(["GET"], "/about", about)
server.add_route(["GET"], "/chat", chat)
server.add_route(["POST"], "/profile_action", profile_action)
server.add_route(["GET"], "/inbox", inbox)

server.add_route(["GET"], "/404", error_handler)
server.add_route(["GET"], "/403", error_handler)
server.add_route(["GET"], "/400", error_handler)
server.add_route(["GET"], "/405", error_handler)

server.add_route(["GET"], "/*", global_handler)
server.handle_http_connections()
