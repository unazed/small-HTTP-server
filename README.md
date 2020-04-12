# small-HTTP-server
a little HTTP server in Python

`proj1` contains the initial API implementation with a test-case which hosts a simple website with a semi-realtime chat, DM system and user database. The API consists of the following functions:

- `HttpServer.__init__(root_dir, error_dir, host, port, logger_file=None, logger_folder="")`
- `HttpServer.add_route(path, handlers)`
- `HttpServer.handle_http_requests(worker_thd, *, backlog=5, proxy_worker_thd=lambda fn, *args, **kwargs: fn(*args, **kwargs), halt_on_ret=False, timeout=2)`


`proj2` is the refined API, with the following API functions:

- `HttpServer.__init__(root_dir, host, port, logger_file=None, max_conn=10)`
- `@staticmethod HttpServer.parse_http_request(data)`
- `HttpServer.add_route(methods_supported, path, handler)`
- `HttpServer.redirect_route(src_path, dst_path, *, inherit_methods=False)`
- `HttpServer.remove_route(path)`
- `HttpServer.get_route(conn, addr, method, path)`
- `HttpServer.handle_http_connections()`
- `HttpServer.close_connections()`


Both variants are based from socket-level, using `socket` alone with delegating instances of `threading.Thread` per request, maintaing (probably) a persistent TCP connection, enforcing the `keep-alive` standard where necessary. However, neither projects strictly abide RFC 2616 or any such semantic definitions of grammars such as the URI, GET/POST parameters, etc..

At the moment (4/12/20), both the `proj1` and `proj2` variants have test-cases displaying their usage. `proj2` in particular may be seen below, running locally with the filestructure currently uploaded in this commit.

![](https://i.imgur.com/h5ectT8.mp4)
