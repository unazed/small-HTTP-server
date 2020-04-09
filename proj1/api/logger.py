from time import time
import sys


class Logger:
    def __init__(self, file_obj, folder=""):
        self.timestamp = time()
        self.file_obj = file_obj
    
    def log(self, frame, msg, fatal=False):
        self.file_obj.write(
f"on ln. {frame.f_lineno-1}, +{round(time() - self.timestamp, 2)}\n" +
f"\tof {frame.f_code.co_name}(...)\n" +
f"\t| {msg}\n"
     + ("\t| fatal error, exiting ...\n" if fatal else "")
        )
        if fatal:
            print("error logs saved to disk, exiting ...")
            raise SystemExit(msg)

