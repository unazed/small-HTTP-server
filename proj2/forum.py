from html import escape
import json
import os
import shutil


class Forum:
    def __init__(self, database, root_dir):
        if not os.path.exists(root_dir):
            os.mkdir(root_dir)
            with open(f"{root_dir}/roles.json", "w") as roles:
                roles.write("{}")
            self.roles = {}
        else:
            with open(f"{root_dir}/roles.json") as roles:
                self.roles = json.load(roles)
        self.database = database
        self.root_dir = root_dir
        self.sections = {name: {
            "sid": idx,
            "allowed_roles": json.load(open(p)) \
                    if os.path.isfile((p := os.path.join(root_dir, name, "allowed_roles.json"))) else [],
            "threads": list(map(int, filter(str.isdigit, os.listdir(os.path.join(root_dir, name)))))
            } for idx, name in enumerate(os.listdir(root_dir)) \
                    if name != "roles.json"}

    def get_section(self, sid):
        if isinstance(sid, str):
            if not sid.isdigit():
                return False
            sid = int(sid)
        for section, info in self.sections.items():
            if info['sid'] == sid:
                return section, info
        return False

    def add_section(self, name, allowed_roles):
        if name in self.sections:
            return False
        print(allowed_roles)
        self.sections[name] = {"sid": len(self.sections)+1, "allowed_roles": allowed_roles, "threads": []}
        os.mkdir(f"{self.root_dir}/{name}")
        with open(os.path.join(self.root_dir, name, "allowed_roles.json"), "w") as roles:
            json.dump(self.sections[name]['allowed_roles'], roles)
        return True

    def remove_section(self, name):
        if name not in self.sections:
            return False
        del self.sections[name]
        shutil.rmtree(f"{self.root_dir}/{name}")
        return True

    def make_thread(self, section, username, title, content):
        if section not in self.sections:
            return False
        self.sections[section]['threads'].append((c := {
            "tid": (tid := len(self.sections[section]['threads']) + 1),
            "uid": self.database.database[username][1]['uid'],
            "username": username,
            "title": escape(title),
            "content": escape(content)
            })['tid'])
        os.mkdir(f"{self.root_dir}/{section}/{tid}")
        with open(f"{self.root_dir}/{section}/{tid}/info", "w") as info:
            json.dump(c, info)
        return tid

    def delete_thread(self, section, tid):
        if section not in self.sections:
            return False
        elif len(self.sections[section]['threads']) < tid:
            return False
        del self.sections[section]['threads'][tid-1]
        shutil.rmtree(f"{self.root_dir}/{section}/{tid}")
        return True

    def make_reply(self, section, tid, username, content):
        if section not in self.sections:
            return False
        elif len(self.sections[section]['threads']) < tid:
            return False
        pid = len(os.listdir(f"{self.root_dir}/{section}/{tid}"))
        with open(f"{self.root_dir}/{section}/{tid}/{pid}.reply", "w") as post:
            json.dump({"uid": self.database.database[username][1]['uid'], "username": username, "content": escape(content)}, post)
        return True

    def delete_reply(self, section, tid, pid):
        if section not in self.sections:
            return False
        elif len(self.sections[section]['threads']) < tid:
            return False
        elif len(os.listdir(f"{self.root_dir}/{section}/{tid}")) - 1 < pid:
            return False
        os.remove(f"{self.root_dir}/{section}/{tid}/{pid}.reply")
        return True

    def get_replies(self, section, tid):
        if section not in self.sections:
            return False
        elif len(self.sections[section]['threads']) < tid:
            return False
        replies = []
        for reply in os.listdir(f"{self.root_dir}/{section}/{tid}"):
            if reply.endswith(".reply"):
                with open(f"{self.root_dir}/{section}/{tid}/{reply}") as reply:
                    replies.append(json.load(reply))
        return replies
