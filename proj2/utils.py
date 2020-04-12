from html import escape


def sign(num):
    if num > 0:
        return "#38ff38"
    elif num < 0:
        return "#e25555"
    return "white"


def censor_ip(ip):
    a, *_, d = ip.split(".")
    return f"{a}.x.x.{d}"


def determine_template(data, username, *args, **kwargs):
    return data.format(
            items=f"""
            <li>
                <a href="/logout">Logout</a>
            </li>
            <li>
                <a href="/member-list">Member list</a>
            </li>
            <li>
                <a href="/chat">Chatbox</a>
            </li>
            <li>
                <a href="/about">About</a>
            </li>
            <li id="username">
                <a href="/profile">{escape(username)}</a>
            </li>""" if username != "Guest" else """
            <li>
                <a href="/login">Login</a>
            </li>
            <li>
                <a href="/register">Register</a>
            </li>
            <li>
                <a href="/member-list">Member list</a>
            </li>
            <li>
                <a href="/about">About</a>
            </li>
            """,
            *args, **kwargs)


def construct_http_response(version, status_code, reason_phrase, headers, content):
    a= (f"{version} {status_code} {reason_phrase}\r\n"
        + "".join(f"{k.split('#', 1)[0]}: {v}\r\n" for k, v in headers.items()) + "\r\n"
        + content).encode()
    return a


def read_file(root_dir, name):
    try:
        with open(f"{root_dir}/{name}") as file_:
            return file_.read()
    except FileNotFoundError:
        return False
