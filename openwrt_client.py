import requests


class OpenWrtClient:
    def __init__(self, host: str, username: str, password: str, verify_ssl: bool = False, ssh_client=None):
        self.host = host
        self.username = username
        self.password = password
        self.verify_ssl = verify_ssl
        self.url = f"http://{host}/ubus"
        self.session = requests.Session()
        self.token = None
        self.ssh_client = ssh_client

    def login(self):
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "call",
            "params": [
                "00000000000000000000000000000000",
                "session",
                "login",
                {"username": self.username, "password": self.password}
            ]
        }
        r = self.session.post(self.url, json=payload, verify=self.verify_ssl, timeout=20)
        r.raise_for_status()
        data = r.json()
        result = data.get("result")
        if not isinstance(result, list) or len(result) < 2 or "ubus_rpc_session" not in result[1]:
            raise RuntimeError(f"Login failed. Raw response: {data}")
        self.token = result[1]["ubus_rpc_session"]
        return self.token

    def call(self, namespace: str, method: str, params: dict | None = None, raw: bool = False):
        if self.token is None:
            self.login()

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "call",
            "params": [self.token, namespace, method, params or {}]
        }

        r = self.session.post(self.url, json=payload, verify=self.verify_ssl, timeout=20)
        r.raise_for_status()
        data = r.json()

        if raw:
            return data

        if "error" in data and data["error"]:
            raise RuntimeError(data["error"])

        result = data.get("result")
        if not isinstance(result, list) or len(result) == 0:
            return None

        code = result[0]
        if code != 0:
            raise RuntimeError(f"RPC call failed with code {code}: {data}")

        return result[1] if len(result) > 1 else None

    def exec(self, command: str):
        return self.call("file", "exec", {
            "command": "/bin/sh",
            "params": ["-lc", command]
        })

    def run(self, command: str, check: bool = False, prefer_ssh: bool = False) -> dict:
        if prefer_ssh and self.ssh_client is not None:
            return self.ssh_client.run(command, check=check)

        try:
            res = self.exec(command)
            if not isinstance(res, dict):
                result = {
                    "command": command,
                    "ok": True,
                    "exit_status": 0,
                    "stdout": str(res or ""),
                    "stderr": "",
                }
            else:
                exit_status = (
                    res.get("code")
                    if res.get("code") is not None
                    else res.get("exitcode")
                    if res.get("exitcode") is not None
                    else res.get("exit_status")
                    if res.get("exit_status") is not None
                    else 0
                )
                result = {
                    "command": command,
                    "ok": exit_status == 0,
                    "exit_status": exit_status,
                    "stdout": res.get("stdout", "") or "",
                    "stderr": res.get("stderr", "") or "",
                }

            if check and not result["ok"]:
                raise RuntimeError(result["stderr"] or f"Command failed: {command}")
            return result

        except Exception as e:
            if self.ssh_client is not None:
                return self.ssh_client.run(command, check=check)
            if check:
                raise
            return {
                "command": command,
                "ok": False,
                "exit_status": 1,
                "stdout": "",
                "stderr": str(e),
            }

    def _run_cmd(self, command: str) -> str:
        res = self.run(command, check=True)
        stdout = res.get("stdout", "") or ""
        stderr = res.get("stderr", "") or ""
        return stdout + (("\n" + stderr) if stderr else "")

    def run_shell(self, command: str) -> str:
        return self._run_cmd(command)

    def get_board_info(self):
        return self.call("system", "board", {})

    def read_file(self, path: str):
        res = self.call("file", "read", {"path": path})
        return res.get("data", "") if isinstance(res, dict) else ""

    def read_optional_file(self, path: str):
        try:
            return self.read_file(path)
        except Exception:
            return ""

    def get_odhcpd_leases(self):
        candidates = [
            "/tmp/odhcpd.leases",
            "/tmp/dhcp.leases",
            "/tmp/dhcpd.leases",
        ]
        for path in candidates:
            content = self.read_optional_file(path)
            if content and content.strip():
                return content
        return ""

    def get_odhcpd_hosts(self):
        return self.read_optional_file("/tmp/hosts/odhcpd.hosts.lan")

    def get_dns_hosts(self):
        return self.read_optional_file("/tmp/hosts/dhcp.cfg01411c")

    def get_dhcp_ipv4_leases(self):
        try:
            return self.call("dhcp", "ipv4leases", {})
        except Exception:
            return None

    def get_dhcp_ipv6_leases(self):
        try:
            return self.call("dhcp", "ipv6leases", {})
        except Exception:
            return None

    def uci_get(self, config: str, section: str | None = None, option: str | None = None, type_: str | None = None, match: dict | None = None):
        params = {"config": config}
        if section is not None:
            params["section"] = section
        if option is not None:
            params["option"] = option
        if type_ is not None:
            params["type"] = type_
        if match is not None:
            params["match"] = match
        return self.call("uci", "get", params)

    def uci_changes(self, config: str):
        return self.call("uci", "changes", {"config": config})

    def uci_set(self, config: str, section: str, values: dict):
        return self.call("uci", "set", {
            "config": config,
            "section": section,
            "values": values
        })

    def uci_add(self, config: str, type_: str, name: str | None = None, values: dict | None = None):
        params = {
            "config": config,
            "type": type_,
            "values": values or {}
        }
        if name is not None:
            params["name"] = name
        return self.call("uci", "add", params)

    def uci_delete(self, config: str, section: str, option: str | None = None, options: list[str] | None = None):
        params = {
            "config": config,
            "section": section
        }
        if option is not None:
            params["option"] = option
        if options is not None:
            params["options"] = options
        return self.call("uci", "delete", params)

    def uci_commit(self, config: str):
        return self.call("uci", "commit", {"config": config})

    def uci_apply(self, rollback: bool = True, timeout: int = 30):
        return self.call("uci", "apply", {
            "rollback": rollback,
            "timeout": timeout
        })

    def get_luci_dhcp_leases(self):
        try:
            return self.call("luci-rpc", "getDHCPLeases", {})
        except Exception:
            return None

    def get_host_hints(self):
        try:
            return self.call("luci-rpc", "getHostHints", {})
        except Exception:
            return None

    def get_dnsmasq_help(self):
        result = self.run("dnsmasq --help 2>/dev/null || true", check=False)
        return result.get("stdout", "") or ""

    def dnsmasq_supports_nftset(self):
        out = self.get_dnsmasq_help()
        return "--nftset" in out