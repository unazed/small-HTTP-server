# small-HTTP-server
a little HTTP server in Python

There's a simple API: `HttpServer(root_dir, error_dir[, host='localhost', port=8080, logger_file=None, logger_folder=""])`, call `HttpServer.handle_http_requests(worker_thd[, backlog=5, proxy_worker_thd=lambda fn, *args, **kwargs: fn(*args, **kwargs), halt_on_ret=False, timeout=2])`. `proxy_worker_thd` is called over `worker_thd`, thus allowing multithreading or other handlers to perform some procedure before/during/after `worker_thd` is called. `halt_on_ret` evaluates the return of `proxy_worker_thd`, which is usually `worker_thd`, and stops the main loop if `True`.

The logger is accessible through `HttpServer.logger`, having main function `Logger.log(frame, msg[, fatal=False])`. The `frame` parameter is retrieved through `sys._getframe()` and allows better traceback information if used properly (my logging method is a little obscure and untidy). For verbosity, you should set `logger_file=sys.stdout` on initializing `HttpServer`.

The uploaded `unittest_http_server.py` demonstrates basic HTTP authorization. There isn't that much of an abstraction barrier between the socketed layer and the highest layer, but there is some added uniformity and visible interface.


