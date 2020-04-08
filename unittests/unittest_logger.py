from logger import Logger
from sys import _getframe as _gf


if __name__ != "__main__":
    raise SystemExit

with open("log.txt", "w") as log:
    logger = Logger(file_obj=log)
    logger.log(_gf(), "nigger")
    def f(x=1, y=2, z=3):
        logger.log(_gf(), "nignog")
        return x+y+z
    f(1, z=4)
print("logged")
