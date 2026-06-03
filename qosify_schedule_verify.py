def verify_qosify_schedule_plan(ssh_client, writer_plan: dict) -> dict:
    if not writer_plan:
        return {
            "verified": False,
            "reason": "Missing writer plan for scheduled QoS verification.",
        }

    enable_script = writer_plan.get("enable_script_path")
    disable_script = writer_plan.get("disable_script_path")
    start_cron = writer_plan.get("start_cron_line")
    end_cron = writer_plan.get("end_cron_line")
    remote_rule_path = writer_plan.get("remote_rule_path")

    checks = []

    for label, cmd in [
        ("enable_script_exists", f"test -s {enable_script} && echo OK || echo FAIL"),
        ("disable_script_exists", f"test -s {disable_script} && echo OK || echo FAIL"),
        ("start_cron_present", f"grep -F {start_cron!r} /etc/crontabs/root >/dev/null && echo OK || echo FAIL"),
        ("end_cron_present", f"grep -F {end_cron!r} /etc/crontabs/root >/dev/null && echo OK || echo FAIL"),
        ("rule_file_currently_present", f"test -s {remote_rule_path} && echo OK || echo ABSENT"),
    ]:
        res = ssh_client.run(cmd, check=False)
        checks.append({
            "check": label,
            "stdout": (res.get("stdout") or "").strip(),
            "stderr": (res.get("stderr") or "").strip(),
            "exit_code": res.get("exit_code"),
        })

    ok_map = {c["check"]: c["stdout"].endswith("OK") for c in checks}

    verified = (
        ok_map.get("enable_script_exists", False)
        and ok_map.get("disable_script_exists", False)
        and ok_map.get("start_cron_present", False)
        and ok_map.get("end_cron_present", False)
    )

    return {
        "verified": verified,
        "dry_run": False,
        "checks": checks,
        "reason": None if verified else "Scheduled QoS artifacts or cron entries are missing.",
    }