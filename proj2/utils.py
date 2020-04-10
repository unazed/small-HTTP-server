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
