from typing import Any, Dict


def _text(value: Any) -> str:
    if value is None:
        return ""
    return value if isinstance(value, str) else str(value)


def _first_present(mapping: dict, *keys):
    for key in keys:
        value = mapping.get(key)
        if value is not None:
            return value
    return None


def normalize_ssh_result(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, dict):
        stdout = _text(raw.get("stdout"))
        stderr = _text(raw.get("stderr"))
        exit_status = _first_present(raw, "exit_status", "exitstatus", "exit_code", "returncode", "rc", "status")
        failed = raw.get("failed")
        if failed is None:
            failed = (exit_status not in (0, None))
        return {
            "stdout": stdout,
            "stderr": stderr,
            "exit_status": exit_status,
            "failed": bool(failed),
        }

    stdout = _text(getattr(raw, "stdout", ""))
    stderr = _text(getattr(raw, "stderr", ""))
    exit_status = None
    for attr in ("exit_status", "exitstatus", "exit_code", "returncode", "rc", "status"):
        value = getattr(raw, attr, None)
        if value is not None:
            exit_status = value
            break

    failed = getattr(raw, "failed", None)
    if failed is None:
        failed = (exit_status not in (0, None))

    return {
        "stdout": stdout,
        "stderr": stderr,
        "exit_status": exit_status,
        "failed": bool(failed),
    }


def run_ssh_normalized(ssh_client, command: str, check: bool = False) -> Dict[str, Any]:
    raw = ssh_client.run(command, check=check)
    result = normalize_ssh_result(raw)
    result["command"] = command
    return result