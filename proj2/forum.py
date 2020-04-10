from api.http_server import HttpServer


if __name__ != "__main__":
    raise SystemExit("run at top-level")

server = HttpServer(
        host="",
        port=6969,
        # logger_file=...
        )
