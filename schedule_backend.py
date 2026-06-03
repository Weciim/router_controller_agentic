import shlex


DAY_TO_CRON = {
    "Sun": "0",
    "Mon": "1",
    "Tue": "2",
    "Wed": "3",
    "Thu": "4",
    "Fri": "5",
    "Sat": "6",
}


def to_cron_days(days):
    values = []
    for day in days or []:
        mapped = DAY_TO_CRON.get(day)
        if mapped is not None:
            values.append(mapped)
    if not values:
        return "*"
    deduped = []
    for value in values:
        if value not in deduped:
            deduped.append(value)
    return ",".join(deduped)


def detect_cron_backend(ssh_client):
    cron_d = ssh_client.run("test -d /etc/cron.d && echo yes || echo no", check=False)
    crontabs = ssh_client.run("test -d /etc/crontabs && echo yes || echo no", check=False)

    cron_d_ok = "yes" in (getattr(cron_d, "stdout", "") or "").lower()
    crontabs_ok = "yes" in (getattr(crontabs, "stdout", "") or "").lower()

    if cron_d_ok:
        return {
            "ok": True,
            "mode": "cron.d",
            "cron_owner_style": "with_user_field",
            "cron_target": None,
        }

    if crontabs_ok:
        return {
            "ok": True,
            "mode": "crontabs",
            "cron_owner_style": "no_user_field",
            "cron_target": "/etc/crontabs/root",
        }

    return {
        "ok": False,
        "mode": "unknown",
        "cron_owner_style": None,
        "cron_target": None,
        "reason": "Neither /etc/cron.d nor /etc/crontabs exists on target router.",
    }


def build_qosify_schedule_plan(writer_plan, cron_backend, activate_now):
    if not writer_plan:
        return {"ok": False, "reason": "writer_plan is required"}

    if not cron_backend.get("ok"):
        return {"ok": False, "reason": cron_backend.get("reason", "No supported cron backend detected.")}

    remote_path = writer_plan["remote_path"]
    basename = remote_path.split("/")[-1]
    staged_rule_path = f"/etc/qosify/staged/{basename}"

    hostname_slug = writer_plan["hostname"].strip().lower()
    app_slug = writer_plan["application"].strip().lower()

    enable_script = f"/usr/bin/llm-qosify-enable-{hostname_slug}-{app_slug}.sh"
    disable_script = f"/usr/bin/llm-qosify-disable-{hostname_slug}-{app_slug}.sh"

    schedule = writer_plan["schedule"]
    cron_days = to_cron_days(schedule["days"])
    start_hour, start_minute = schedule["start_time"].split(":")
    end_hour, end_minute = schedule["end_time"].split(":")

    enable_body = f"""#!/bin/sh
set -eu
STAGED_RULE="{staged_rule_path}"
TARGET_FILE="{remote_path}"

mkdir -p /etc/qosify
if [ -s "$STAGED_RULE" ]; then
  cp "$STAGED_RULE" "$TARGET_FILE"
fi

/etc/init.d/qosify restart
"""

    disable_body = f"""#!/bin/sh
set -eu
TARGET_FILE="{remote_path}"

rm -f "$TARGET_FILE"
/etc/init.d/qosify restart
"""

    commands = [
        "mkdir -p /etc/qosify/staged",
    ]

    if activate_now:
        commands.append(f"cp {shlex.quote(remote_path)} {shlex.quote(staged_rule_path)}")
    else:
        commands.append(
            f"cat > {shlex.quote(staged_rule_path)} <<'__QOSIFY_RULE_EOF__'\n"
            f"{writer_plan['file_body']}"
            "__QOSIFY_RULE_EOF__\n"
        )

    commands.extend([
        f"cat > {shlex.quote(enable_script)} <<'__LLM_QOSIFY_ENABLE__'\n{enable_body}__LLM_QOSIFY_ENABLE__\n",
        f"chmod +x {shlex.quote(enable_script)}",
        f"cat > {shlex.quote(disable_script)} <<'__LLM_QOSIFY_DISABLE__'\n{disable_body}__LLM_QOSIFY_DISABLE__\n",
        f"chmod +x {shlex.quote(disable_script)}",
    ])

    if cron_backend["mode"] == "cron.d":
        cron_file = f"/etc/cron.d/llm-qosify-{hostname_slug}-{app_slug}"
        cron_body = (
            f"{start_minute} {start_hour} * * {cron_days} root {enable_script}\n"
            f"{end_minute} {end_hour} * * {cron_days} root {disable_script}\n"
        )
        commands.append(
            f"cat > {shlex.quote(cron_file)} <<'__LLM_QOSIFY_CRON__'\n"
            f"{cron_body}"
            "__LLM_QOSIFY_CRON__\n"
        )
        cron_target = cron_file
    else:
        cron_target = cron_backend["cron_target"]
        start_line = f"{start_minute} {start_hour} * * {cron_days} {enable_script}"
        end_line = f"{end_minute} {end_hour} * * {cron_days} {disable_script}"
        commands.append(
            f"(grep -Fv {shlex.quote(enable_script)} {shlex.quote(cron_target)} 2>/dev/null || true) | "
            f"(grep -Fv {shlex.quote(disable_script)} || true) > /tmp/llm-qosify-cron.$$"
        )
        commands.append(
            f"printf '%s\\n%s\\n' {shlex.quote(start_line)} {shlex.quote(end_line)} >> /tmp/llm-qosify-cron.$$"
        )
        commands.append(f"cat /tmp/llm-qosify-cron.$$ > {shlex.quote(cron_target)}")
        commands.append("rm -f /tmp/llm-qosify-cron.$$")

    commands.extend([
        "/etc/init.d/cron enable || true",
        "/etc/init.d/cron restart",
        f"sed -n '1,120p' {shlex.quote(enable_script)}",
        f"sed -n '1,120p' {shlex.quote(disable_script)}",
        f"sed -n '1,120p' {shlex.quote(cron_target)}",
    ])

    return {
        "ok": True,
        "mode": "qosify_schedule_apply",
        "activate_now": activate_now,
        "cron_mode": cron_backend["mode"],
        "schedule": schedule,
        "paths": {
            "active_rule_path": remote_path,
            "staged_rule_path": staged_rule_path,
            "enable_script": enable_script,
            "disable_script": disable_script,
            "cron_target": cron_target,
        },
        "commands": commands,
    }