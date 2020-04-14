from os import urandom
import socket


def deconcat(num, pad):
    k = ""
    while num:
        k += chr(num & 0xff)
        num >>= 8
    return k[::-1].rjust(pad, "\x00")


def encode_websocket(data):
    if len(data) <= 125:
        payload_len = deconcat(len(data), 1)
        payload_len_extra = ""
    elif 126 <= len(data) <= 2**16:
        payload_len = chr(126)
        payload_len_extra = deconcat(len(data), 2)
    elif 2**16 < len(data) <= 2**64:
        payload_len = chr(127)
        payload_len_extra = deconcat(len(data), 8)
    a = f"\x81{payload_len}{payload_len_extra}{data}".encode()
    print(a)
    return a


def concat(seq):
    num = seq[0] << 0x08
    for n in seq:
        num |= n
        num <<= 0x08
    num >>= 0x08
    return num


def decode_websocket(conn, timeout=None):
    conn.settimeout(timeout)
    try:
        initial = conn.recv(2)
    except socket.timeout:
        return True
    except ConnectionResetError:
        return False
    if not initial:
        return False
    fin = initial[0] & 0b10000000
    opcode = initial[0] & 0b00001111
    mask = initial[1] & 0b10000000
    payload_len = initial[1] & 0b01111111
    if payload_len == 126:
        payload_len = concat(conn.recv(2))
    elif payload_len == 127:
        payload_len = concat(conn.recv(8))
    if mask:
        masking_key = conn.recv(4)
    payload = conn.recv(payload_len)
    decrypted = ''
    for idx, char in enumerate(payload):
        decrypted += chr(char ^ masking_key[idx % 4])
    return decrypted


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
                <a href="/profile">{username}</a>
            </li>
            <li id="inbox">
                <a href="/inbox">Inbox</a>
            </li>
            """ if username != "Guest" else """
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
