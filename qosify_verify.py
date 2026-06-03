from ssh_output_cleaner import normalize_ssh_result

def verify_qosify_live_rule(ssh_client, writer_plan: dict) -> dict:
    if not writer_plan:
        return {
            "verified": False,
            "reason": "Missing writer plan for QoS verification.",
        }

    remote_path = writer_plan.get("remote_path")
    expected_lines = writer_plan.get("expected_lines") or []

    checks = []

    file_exists_cmd = f"test -s {remote_path} && echo OK || echo FAIL"
    res = ssh_client.run(file_exists_cmd, check=False)
    file_exists_out = (res.get("stdout") or "").strip()
    checks.append({
        "check": "rule_file_exists",
        "stdout": file_exists_out,
        "stderr": (res.get("stderr") or "").strip(),
        "exit_code": res.get("exit_code"),
    })

    for line in expected_lines:
        cmd = f"grep -F {line!r} {remote_path} >/dev/null && echo OK || echo FAIL"
        res = ssh_client.run(cmd, check=False)
        checks.append({
            "check": f"contains:{line}",
            "stdout": (res.get("stdout") or "").strip(),
            "stderr": (res.get("stderr") or "").strip(),
            "exit_code": res.get("exit_code"),
        })

    qosify_res = ssh_client.run("qosify-status 2>/dev/null || true", check=False)
    tc_res = ssh_client.run("tc -s qdisc 2>/dev/null || true", check=False)

    verified = all((c.get("stdout") or "").endswith("OK") for c in checks)

    return {
        "verified": verified,
        "dry_run": False,
        "checks": checks,
        "status_excerpt": {
            "qosify_status": (qosify_res.get("stdout") or "").strip()[:1000],
            "tc_qdisc": (tc_res.get("stdout") or "").strip()[:1500],
        },
        "reason": None if verified else "qosify managed file is missing or incomplete.",
    }
def verify_qosify_rule(ssh_client, remote_path: str, expected_lines: list[str]) -> dict:
    checks = []

    exists = normalize_ssh_result(
        ssh_client.run(f"test -s {remote_path} && echo OK", check=False)
    )
    exists_ok = exists["stdout"].strip() == "OK" and not exists["failed"]
    checks.append({
        "check": "rule_file_exists",
        "stdout": exists["stdout"],
        "stderr": exists["stderr"],
        "exit_code": exists.get("exit_code"),
        "passed": exists_ok,
    })

    file_read = normalize_ssh_result(
        ssh_client.run(f"sed -n '1,200p' {remote_path}", check=False)
    )
    file_text = file_read["stdout"]

    checks.append({
        "check": "rule_file_readable",
        "stdout": file_text[:1000],
        "stderr": file_read["stderr"],
        "exit_code": file_read.get("exit_code"),
        "passed": bool(file_text.strip()) and not file_read["failed"],
    })

    for expected in expected_lines:
        passed = expected in file_text
        checks.append({
            "check": f"contains:{expected}",
            "stdout": "OK" if passed else "",
            "stderr": "" if passed else f"Missing expected line: {expected}",
            "exit_code": 0 if passed else 1,
            "passed": passed,
        })

    qosify_status = normalize_ssh_result(
        ssh_client.run("qosify-status 2>/dev/null || true", check=False)
    )
    tc_qdisc = normalize_ssh_result(
        ssh_client.run("tc -s qdisc 2>/dev/null || true", check=False)
    )

    verified = all(item["passed"] for item in checks)

    return {
        "verified": verified,
        "dry_run": False,
        "checks": checks,
        "status_excerpt": {
            "qosify_status": qosify_status["stdout"][:1200],
            "tc_qdisc": tc_qdisc["stdout"][:1200],
        },
        "reason": None if verified else "One or more qosify verification checks failed.",
        "rule_id": None,
    }