import hashlib
import json
import os


class LoginDatabase:
    def __init__(self, filename):
        self.filename = filename
        if os.path.isfile(filename):
            with open(filename) as db:
                self.database = json.load(db)
        else:
            with open(filename, "w") as db:
                db.write("{}")
            self.database = {}

    def write_changes(self):
        with open(self.filename, "w") as db:
            json.dump(self.database, db)

    def add_user(self, username, password, *, properties={}, replace=False):
        if username in self.database and not replace:
            return False
        elif not username:
            return False
        self.database[username] = (
                (t := hashlib.sha256(f"{username}:{password}".encode()).hexdigest()),
                properties
                )
        self.write_changes()
        return t

    def get_user(self, token):
        for uname, tok in self.database.items():
            if token == tok[0]:
                return uname
        return False

    def remove_user(self, username):
        if username not in self.database:
            return False
        del self.database[username]
        self.write_changes()
        return True
