from html import escape


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
            </li>""" if username else """
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
    return (f"{version} {status_code} {reason_phrase}\r\n"
        + "\r\n".join(f"{k}: {v}" for k, v in headers.items()) + "\r\n"
        + content).encode()


def read_file(root_dir, name):
    try:
        with open(f"{root_dir}/{name}") as file_:
            return file_.read()
    except FileNotFoundError:
        return False
