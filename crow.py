#!/usr/bin/python3

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Literal

import yaml

DEBUG = False
CROW_CMD = "crow"

if os.getuid():
    print("crow: make sure you're running as super user, things may not work otherwise")

ROOT = [Path("./conf/"), Path("./data/")] if DEBUG else [Path("/etc/crow.d"), Path("/var/crow/")]

DEFAULTS = {
    "nginx_file": ROOT[1] / "nginx.conf" if DEBUG else "/etc/nginx/sites-enabled/crow.conf",
    "update_script": ROOT[1] / "update.sh",
    "compose_file": ROOT[1] / "compose.yaml",
    "container_folder": ROOT[0] / "containers",
    "nginx_use_cloudflare_ips": "false"
}

class DCConf:
    DEFAULT_CONFIG_STR = (
        f"nginx_file = {DEFAULTS['nginx_file']}\n"
        f"update_script = {DEFAULTS['update_script']}\n"
        f"compose_file = {DEFAULTS['compose_file']}\n"
        f"container_folder = {DEFAULTS['container_folder']}\n"
        f"nginx_use_cloudflare_ips = {DEFAULTS['nginx_use_cloudflare_ips']}\n"
    )

    def __init__(self, conf_file: Path):
        self.conf_path = conf_file
        self.reload_conf_from_file()

    def reload_conf_from_file(self, conf_file: Path | None=None):
        self.conf_path = conf_file or self.conf_path

        try:
            self.fp = open(self.conf_path, "r")
        except FileNotFoundError:
            os.makedirs(self.conf_path.parent, exist_ok=True)
            f = open(self.conf_path, "w")
            f.write(self.DEFAULT_CONFIG_STR)
            f.close()

            self.fp = open(self.conf_path, "r")

        self.nginx_file: Path = Path(DEFAULTS["nginx_file"])
        self.update_script: Path = Path(DEFAULTS["update_script"])
        self.compose_file: Path = Path(DEFAULTS["compose_file"])
        self.container_folder: Path = Path(DEFAULTS["container_folder"])
        self.use_cloudflare_ips: bool = DEFAULTS["nginx_use_cloudflare_ips"]

        self._parse_fp()

        os.makedirs(self.container_folder, exist_ok=True)
        self.containers: list[DCContainer] = []
        self._load_containers()

    def _parse_fp(self):
        while (line := self.fp.readline()):
            if line.startswith("#"):
                continue

            setting_name = line.split("=")[0].strip()
            setting_value = line.split("=", 1)[1].strip().strip("\"'") if "=" in line else None

            if setting_name == "nginx_file" and setting_value:
                self.nginx_file = Path(setting_value)
            elif setting_name == "update_script" and setting_value:
                self.update_script = Path(setting_value)
            elif setting_name == "compose_file" and setting_value:
                self.compose_file = Path(setting_value)
            elif setting_name == "container_folder" and setting_value:
                self.container_folder = Path(setting_value)
            elif setting_name == "nginx_use_cloudflare_ips" and setting_value:
                self.use_cloudflare_ips = setting_value[0].lower() == "t"
            else:
                print(f"crow: unknown setting '{setting_name}' in crow.conf")

    def _load_containers(self):
        container_fnames = os.listdir(self.container_folder)
        for container in container_fnames:
            f = yaml.safe_load(open(self.container_folder / container, "r"))
            for id, data in f.items():
                self.containers.append(DCContainer(data, id))

    def generate(self):
        compose: dict = { "services": {}}
        update_script = ""
        nginx = ""
        for i in self.containers:
            compose["services"] |= i.generate_compose()["services"]
            update_script += i.generate_update_script() or ""
            nginx += i.generate_nginx() or ""

        os.makedirs(self.nginx_file.parent, exist_ok=True)
        os.makedirs(self.update_script.parent, exist_ok=True)
        os.makedirs(self.compose_file.parent, exist_ok=True)

        with open(self.compose_file, "w") as f:
            json.dump(compose, f)
            print(f"crow: wrote docker-compose to {self.compose_file}")

        with open(self.nginx_file, "w") as f:
            f.write(nginx)
            print(f"crow: wrote nginx conf to {self.nginx_file}")

        with open(self.update_script, "w") as f:
            f.write(update_script + f"cd {self.compose_file.parent} && {CROW_CMD} pull -b && cd -\n")
            os.chmod(self.update_script, 0o755)
            print(f"crow: wrote update script to {self.update_script}")

class DCContainer:
    def __init__(self, data: dict, id: str):
        self.id = id

        self.build: Literal[False] | str = "build" in data and data["build"]
        self.image: Literal[False] | str = "image" in data and data["image"]
        self.dns_override: bool = "dns_override" in data and bool(data["dns_override"])
        self.git_pull: bool = "git_pull" in data and bool(data["git_pull"])
        self.pre_script: str | None = data["pre_script"] if "pre_script" in data and data["pre_script"] else None
        self.port: list[str] | Literal["host"] = ("host" if data["port"] == "host" else (data["port"] if isinstance(data["port"], list) else [data["port"] if isinstance(data["port"], str) else f"{data['port']}:{data['port']}"])) if "port" in data and data["port"] else []
        self.dirs: dict[str, str] = data["dirs"] if "dirs" in data and data["dirs"] else {}
        self.env: dict = data["env"] if "env" in data and data["env"] else {}

        self.nginx: dict | None = {
            "host": data["nginx"]["host"],
            "http": "http" in data["nginx"] and data["nginx"]["http"],
            "https": "https" in data["nginx"] and data["nginx"]["https"],
            "ssl_conf": data["nginx"]["ssl_conf"] if "ssl_conf" in data["nginx"] else None,
            "port": data["nginx"]["port"] if "port" in data["nginx"] else None,
            "static": data["nginx"]["static"] if "static" in data["nginx"] else {}
        } if "nginx" in data and data["nginx"] else None

    def generate_compose(self) -> dict:
        compose_data: dict = {
            "restart": "always"
        }

        if self.build:
            if self.git_pull == "only":
                return {}
            compose_data["build"] = self.build
        elif self.image:
            compose_data["image"] = self.image
        else:
            print(f"cro w: container '{self.id}' must have property `build` or `image` set")
            exit(1)

        if self.dns_override:
            compose_data["dns"] = ["1.1.1.1", "1.0.0.1"]

        if self.port == "host":
            compose_data["network_mode"] = "host"
        elif self.port:
            compose_data["ports"] = self.port

        if self.dirs:
            compose_data["volumes"] = []
            for src, dst in self.dirs.items():
                compose_data["volumes"].append(f"{src}:{dst}")

        if self.env:
            compose_data["environment"] = self.env

        return { "services": { self.id: compose_data }}

    def _generate_nginx_body(self) -> str:
        if not self.nginx:
            return ""

        return (
            "location / {"
                f"proxy_pass http://127.0.0.1:{self.nginx['port'] or str(self.port[0]).split(':')[0]};"
                "proxy_set_header Host $host;"
                "proxy_set_header Origin $http_origin;"
                f"proxy_set_header X-Real-IP ${'http_cf_connecting_ip' if conf.use_cloudflare_ips else 'remote_addr'};"
            "}"
        ) + ''.join([(
            f"location {http_path} {{"
                f"alias {file_dir};"
            "}"
        ) for http_path, file_dir in self.nginx["static"].items()])

    def _generate_nginx_http(self) -> str:
        if not self.nginx:
            return ""

        return (
            "server {"
                f"server_name {self.nginx['host']};"
                "listen 80;"
                f"{self._generate_nginx_body()}"
            "}"
        )

    def _generate_nginx_https(self) -> str:
        if not self.nginx:
            return ""

        return (
            "server {"
                f"server_name {self.nginx['host']};"
                "listen 443 ssl http2;"
                f"include {self.nginx['ssl_conf']};"
                "ssl_protocols TLSv1.2 TLSv1.3;"
                "ssl_ciphers HIGH:!aNULL:!MD5;"
                "ssl_prefer_server_ciphers on;"
                f"{self._generate_nginx_body()}"
            "}"
        )

    def generate_nginx(self) -> str | None:
        if not self.nginx or not (self.nginx["http"] or self.nginx["https"]):
            return
        return (self._generate_nginx_http() if self.nginx["http"] else "") + (self._generate_nginx_https() if self.nginx["https"] else "")

    def generate_update_script(self) -> str | None:
        output = ""

        if self.pre_script:
            output += f"sh {self.pre_script}\n"

        if self.git_pull and self.build:
            output += f"cd {self.build}\ngit stash && git submodule init && git pull --recurse-submodules git stash pop\ncd -\n"

        return output or None

conf = DCConf(ROOT[0] / "crow.conf")
action = len(sys.argv) > 1 and sys.argv[1].lower() or None
commands = ["generate", "update", "pull", "up", "down", "logs", "exec", "ps"]

def fuzzy_match(needle: str | None, haystack: str, _check_conflicting: list[str] | None=commands) -> bool:
    if not needle or not haystack or needle[0] != haystack[0]:
        return False

    if needle == haystack:
        return True

    haystack_copy = haystack[1:]
    for char in needle[1:]:
        if char not in haystack_copy:
            return False
        haystack_copy = haystack_copy.split(char, 1)[1]

    if not _check_conflicting:
        return True

    for confl in _check_conflicting:
        if confl != haystack and fuzzy_match(needle, confl, []):
            return False

    return True

if fuzzy_match(action, "generate"):
    conf.generate()
elif fuzzy_match(action, "update"):
    subprocess.run(["sh", conf.update_script])
elif fuzzy_match(action, "pull"):
    subprocess.run(["sudo", "docker", "compose", "pull"], cwd=conf.compose_file.parent)
    subprocess.run(list(filter(bool, ["sudo", "docker", "compose", "up", "-d", "--build" if len(sys.argv) > 2 and (sys.argv[2] == "-b" or sys.argv[2] == "--build") else ""])), cwd=conf.compose_file.parent)
elif fuzzy_match(action, "up"):
    subprocess.run(list(filter(bool, ["sudo", "docker", "compose", "up", "-d", "--build" if len(sys.argv) > 2 and (sys.argv[2] == "-b" or sys.argv[2] == "--build") else ""])), cwd=conf.compose_file.parent)
elif fuzzy_match(action, "down"):
    subprocess.run(["sudo", "docker", "compose", "down"], cwd=conf.compose_file.parent)
elif fuzzy_match(action, "logs"):
    subprocess.run(["sudo", "docker", "compose", "logs", "-fn", str(int(sys.argv[2]) if len(sys.argv) > 2 else 100)], cwd=conf.compose_file.parent)
elif fuzzy_match(action, "exec") and len(sys.argv) > 2:
    subprocess.run(["sudo", "docker", "exec", "-it", sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "bash"])
elif fuzzy_match(action, "ps"):
    subprocess.run(["sudo", "docker", "ps"])
else:
  print(f"Usage: {sys.argv[0]} generate\n"
        f"       {sys.argv[0]} update\n"
        f"       {sys.argv[0]} pull [-b | --build]\n"
        f"       {sys.argv[0]} up [-b | --build]\n"
        f"       {sys.argv[0]} down\n"
        f"       {sys.argv[0]} logs [num]\n"
        f"       {sys.argv[0]} exec <id> [cmd]\n"
        f"       {sys.argv[0]} ps")
