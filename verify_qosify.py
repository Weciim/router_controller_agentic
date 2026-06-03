from ssh_result_utils import run_ssh_normalized

def _is_success(result: dict) -> bool:
    return result.get("exit_status") == 0
def _normalize_text(value):
    return value if isinstance(value, str) else ("" if value is None else str(value))


def _command_result(ssh_client, command: str) -> dict:
    return run_ssh_normalized(ssh_client, command, check=False)

def _is_success_exit(result):
    code = result.get("exit_code")
    return code == 0


def _check_exists(ssh_client, path: str) -> dict:
    result = _command_result(ssh_client, f"test -s '{path}'")
    return {
        "path": path,
        "stdout": result["stdout"],
        "stderr": result["stderr"],
        "exit_status": result["exit_status"],
        "ok": _is_success(result),
    }


def _check_contains(ssh_client, path: str, needle: str) -> dict:
    escaped = needle.replace("'", "'\"'\"'")
    result = _command_result(ssh_client, f"grep -F '{escaped}' '{path}' >/dev/null")
    return {
        "path": path,
        "needle": needle,
        "stdout": result["stdout"],
        "stderr": result["stderr"],
        "exit_status": result["exit_status"],
        "ok": _is_success(result),
    }


def _check_readable(ssh_client, path: str) -> dict:
    result = _command_result(ssh_client, f"sed -n '1,5p' '{path}' >/dev/null")
    return {
        "path": path,
        "stdout": result["stdout"],
        "stderr": result["stderr"],
        "exit_status": result["exit_status"],
        "ok": _is_success(result),
    }


def verify_qosify_result(ssh_client, apply_result, schedule_apply_result=None):
    writer_plan = (apply_result or {}).get("writer_plan") or {}
    active_path = writer_plan.get("remote_path")
    expected_lines = writer_plan.get("expected_lines", [])

    checks = []
    live_verified = True
    schedule_verified = None
    mode = "live_only"
    reason = None

    if apply_result and apply_result.get("applied") and active_path:
        exists_check = _check_exists(ssh_client, active_path)
        checks.append({"check": "active_rule_exists", **exists_check})

        if not exists_check["ok"]:
            readable_check = _check_readable(ssh_client, active_path)
            checks.append({"check": "active_rule_readable_fallback", **readable_check})
            if readable_check["ok"]:
                exists_check["ok"] = True
            else:
                live_verified = False

        if exists_check["ok"]:
            for line in expected_lines:
                line_check = _check_contains(ssh_client, active_path, line)
                checks.append({"check": f"active_contains:{line}", **line_check})
                if not line_check["ok"]:
                    live_verified = False

    schedule_plan = (schedule_apply_result or {}).get("plan") or {}
    if schedule_apply_result is not None:
        if schedule_apply_result.get("applied"):
            schedule_verified = True
            mode = "live_plus_schedule" if apply_result and apply_result.get("applied") else "schedule_only"
        else:
            schedule_verified = False
            mode = "live_applied_schedule_failed" if apply_result and apply_result.get("applied") else "schedule_failed"

    verified = live_verified and (schedule_verified in (None, True))

    if apply_result and apply_result.get("applied") and live_verified and schedule_verified is False:
        reason = "Live QoS rule applied and verified, but scheduled automation was not installed."
    elif apply_result and apply_result.get("applied") and not live_verified:
        reason = "Live QoS rule applied, but verification did not pass."
    elif schedule_verified is False:
        reason = "Scheduled automation was not installed."

    return {
        "verified": verified,
        "live_verified": live_verified,
        "schedule_verified": schedule_verified,
        "mode": mode,
        "reason": reason,
        "checks": checks,
    }