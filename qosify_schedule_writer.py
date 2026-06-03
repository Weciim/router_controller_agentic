import re


DAY_TO_CRON = {
    "Mon": "1",
    "Tue": "2",
    "Wed": "3",
    "Thu": "4",
    "Fri": "5",
    "Sat": "6",
    "Sun": "0",
}


def _slugify(value: str) -> str:
    return "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in (value or "").strip().lower())


def _parse_hhmm(value: str) -> tuple[int, int]:
    m = re.fullmatch(r"(\d{2}):(\d{2})", (value or "").strip())
    if not m:
        raise ValueError(f"Invalid time format: {value}")
    hh = int(m.group(1))
    mm = int(m.group(2))
    if hh < 0 or hh > 23 or mm < 0 or mm > 59:
        raise ValueError(f"Invalid time value: {value}")
    return hh, mm


def _cron_days(days: list[str]) -> str:
    mapped = []
    for d in days or []:
        if d not in DAY_TO_CRON:
            raise ValueError(f"Unsupported day value: {d}")
        mapped.append(DAY_TO_CRON[d])
    uniq = []
    for x in mapped:
        if x not in uniq:
            uniq.append(x)
    return ",".join(uniq)


def _build_script_body(rule_path: str, target_dir: str, mode: str) -> str:
    if mode == "enable":
        return f"""#!/bin/sh
set -eu
RULE_PATH="{rule_path}"
TARGET_DIR="{target_dir}"
TARGET_FILE="$TARGET_DIR/$(basename "$RULE_PATH")"

mkdir -p "$TARGET_DIR"
if [ -s "$RULE_PATH" ]; then
  cp "$RULE_PATH" "$TARGET_FILE"
fi

/etc/init.d/qosify restart
"""
    if mode == "disable":
        return f"""#!/bin/sh
set -eu
TARGET_DIR="{target_dir}"
TARGET_FILE="$TARGET_DIR/$(basename "{rule_path}")"

rm -f "$TARGET_FILE"
/etc/init.d/qosify restart
"""
    raise ValueError(f"Unsupported mode: {mode}")


def _heredoc_write(remote_path: str, body: str, marker: str) -> str:
    return f"""cat > {remote_path} <<'{marker}'
{body}{marker}
"""


def build_qosify_schedule_plan(writer_plan: dict) -> dict:
    remote_path = writer_plan["remote_path"]
    schedule = writer_plan["schedule"]
    hostname = writer_plan["hostname"]
    application = writer_plan["application"]

    days = schedule["days"]
    start_time = schedule["start_time"]
    end_time = schedule["end_time"]

    start_h, start_m = _parse_hhmm(start_time)
    end_h, end_m = _parse_hhmm(end_time)
    cron_dow = _cron_days(days)

    slug = f"{_slugify(hostname)}-{_slugify(application)}"
    staged_dir = "/etc/qosify/staged"
    active_dir = "/etc/qosify"
    enable_script = f"/usr/bin/llm-qosify-enable-{slug}.sh"
    disable_script = f"/usr/bin/llm-qosify-disable-{slug}.sh"
    cron_file = f"/etc/cron.d/llm-qosify-{slug}"

    enable_body = _build_script_body(remote_path, active_dir, "enable")
    disable_body = _build_script_body(remote_path, active_dir, "disable")

    cron_body = "\n".join([
        f"{start_m} {start_h} * * {cron_dow} root {enable_script}",
        f"{end_m} {end_h} * * {cron_dow} root {disable_script}",
        ""
    ])

    commands = [
        "mkdir -p /etc/qosify/staged",
        f"mv {remote_path} {staged_dir}/$(basename {remote_path})",
        _heredoc_write(enable_script, enable_body, "__LLM_QOSIFY_ENABLE__"),
        f"chmod +x {enable_script}",
        _heredoc_write(disable_script, disable_body, "__LLM_QOSIFY_DISABLE__"),
        f"chmod +x {disable_script}",
        _heredoc_write(cron_file, cron_body, "__LLM_QOSIFY_CRON__"),
        "/etc/init.d/cron enable || true",
        "/etc/init.d/cron restart",
        f"sed -n '1,120p' {enable_script}",
        f"sed -n '1,120p' {disable_script}",
        f"sed -n '1,120p' {cron_file}",
    ]

    return {
        "ok": True,
        "mode": "qosify_schedule_apply",
        "schedule": schedule,
        "paths": {
            "staged_rule_path": f"{staged_dir}/{remote_path.split('/')[-1]}",
            "enable_script": enable_script,
            "disable_script": disable_script,
            "cron_file": cron_file,
        },
        "commands": commands,
    }