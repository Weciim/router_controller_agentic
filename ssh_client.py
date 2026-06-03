import paramiko
import time


class SSHCommandError(RuntimeError):
    pass

class SSHClient:
    def __init__(self, client):
        self.client = client

    def run(self, command: str, check: bool = False) -> dict:
        stdin, stdout, stderr = self.client.exec_command(command)
        exit_status = stdout.channel.recv_exit_status()
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")

        ok = (exit_status == 0)

        result = {
            "command": command,
            "ok": ok,
            "exit_status": exit_status,
            "stdout": out,
            "stderr": err,
        }

        if check and not ok:
            raise RuntimeError(f"Command failed ({exit_status}): {command}\n{err}")

        return result

class OpenWrtSSHClient:
    def __init__(self, host: str, username: str, password: str, port: int = 22, timeout: int = 10):
        self.host = host
        self.username = username
        self.password = password
        self.port = port
        self.timeout = timeout
        self.client = None

    def connect(self):
        if self.client is not None:
            return

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            hostname=self.host,
            port=self.port,
            username=self.username,
            password=self.password,
            timeout=self.timeout,
            look_for_keys=False,
            allow_agent=False,
        )
        self.client = client

    def close(self):
        if self.client is not None:
            self.client.close()
            self.client = None

    def run(self, command: str, check: bool = True, get_pty: bool = False) -> dict:
        self.connect()

        stdin, stdout, stderr = self.client.exec_command(
            f"/bin/sh -lc '{command.replace("'", "'\"'\"'")}'",
            get_pty=get_pty,
        )

        exit_status = stdout.channel.recv_exit_status()
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")

        result = {
            "command": command,
            "exit_status": exit_status,
            "stdout": out,
            "stderr": err,
        }

        if check and exit_status != 0:
            raise SSHCommandError(result)

        return result
