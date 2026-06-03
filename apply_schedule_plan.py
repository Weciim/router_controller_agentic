import shlex

from ssh_result_utils import run_ssh_normalized


def apply_qosify_schedule_plan(ssh_client, plan: dict):
    if not plan.get("ok"):
        return {
            "applied": False,
            "plan": plan,
            "results": [],
            "failures": [plan.get("reason")],
        }

    p = plan["paths"]
    a = plan["artifacts"]
    results = []
    failures = []

    commands = [
        "mkdir -p /etc/qosify/staged",
        "mkdir -p /usr/libexec",
        f"cat > '{p['staged_rule_path']}' <<'__EOF__'\n{a['staged_file_body']}__EOF__",
        f"cat > '{p['enable_script']}' <<'__EOF__'\n{a['enable_script_body']}__EOF__",
        f"cat > '{p['disable_script']}' <<'__EOF__'\n{a['disable_script_body']}__EOF__",
        f"chmod 755 '{p['enable_script']}' '{p['disable_script']}'",
    ]

    for cmd in commands:
        res = run_ssh_normalized(ssh_client, cmd, check=False)
        results.append(res)
        if res["exit_status"] not in (0, None):
            failures.append(f"Command failed: {cmd}")

    mode = plan["mode"]

    if mode == "cron.d":
        cron_body = "\n".join(a["cron_lines"]) + "\n"
        cron_cmds = [
            "mkdir -p /etc/cron.d",
            f"cat > '{p['cron_target']}' <<'__EOF__'\n{cron_body}__EOF__",
        ]
    elif mode in ("crontabs", "crond_runtime_only"):
        line1 = shlex.quote(a["cron_lines"][0])
        line2 = shlex.quote(a["cron_lines"][1])
        target = shlex.quote(p["cron_target"])
        cron_cmds = [
            f"touch {target}",
            f"grep -F -- {line1} {target} >/dev/null || printf '%s\\n' {line1} >> {target}",
            f"grep -F -- {line2} {target} >/dev/null || printf '%s\\n' {line2} >> {target}",
        ]
    elif mode == "crontab_cmd":
        start = a["cron_lines"][0].replace('"', '\\"')
        end = a["cron_lines"][1].replace('"', '\\"')
        cron_cmds = [
            f"""(crontab -l 2>/dev/null; printf '%s\n' "{start}" "{end}") | awk '!seen[$0]++' | crontab -"""
        ]
    else:
        cron_cmds = []

    for cmd in cron_cmds:
        res = run_ssh_normalized(ssh_client, cmd, check=False)
        results.append(res)
        if res["exit_status"] not in (0, None):
            failures.append(f"Command failed: {cmd}")

    restart_cmd = "(/etc/init.d/cron restart || /etc/init.d/crond restart || killall -HUP crond) >/dev/null 2>&1 || true"
    restart_res = run_ssh_normalized(ssh_client, restart_cmd, check=False)
    results.append(restart_res)

    return {
        "applied": len(failures) == 0,
        "plan": plan,
        "results": results,
        "failures": failures,
    }