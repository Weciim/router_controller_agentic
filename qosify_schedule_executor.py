from ssh_output_cleaner import strip_openwrt_banner


def _looks_failed(stderr: str, exit_code) -> bool:
    if exit_code not in (0, None):
        return True
    if stderr and stderr.strip():
        return True
    return False


def execute_qosify_schedule_plan(ssh_client, plan: dict, dry_run: bool = False) -> dict:
    if not plan.get("ok"):
        return {
            "applied": False,
            "mode": "qosify_scheduled_apply",
            "dry_run": dry_run,
            "reason": plan.get("reason") or "Invalid qosify scheduled plan.",
            "results": [],
            "failures": [],
        }

    payload = plan["plan"]
    results = []

    for cmd in payload.get("commands", []):
        if dry_run:
            results.append({
                "command": cmd,
                "ran": False,
                "dry_run": True,
                "stdout": "",
                "stderr": "",
                "exit_code": None,
                "failed": False,
            })
            continue

        res = ssh_client.run(cmd, check=False)
        stdout = strip_openwrt_banner(res.get("stdout", ""))[:4000]
        stderr = strip_openwrt_banner(res.get("stderr", ""))[:4000]
        exit_code = res.get("exit_code")

        results.append({
            "command": cmd,
            "ran": True,
            "dry_run": False,
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": exit_code,
            "failed": _looks_failed(stderr, exit_code),
        })

    failures = [r for r in results if r["ran"] and r["failed"]]

    return {
        "applied": len(failures) == 0 and not dry_run,
        "mode": "qosify_scheduled_apply",
        "dry_run": dry_run,
        "reason": None if not failures else "One or more qosify scheduled commands failed.",
        "writer_plan": payload,
        "results": results,
        "failures": failures,
    }