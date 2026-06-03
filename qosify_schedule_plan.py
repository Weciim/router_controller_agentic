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


def _hhmm_to_parts(value: str) -> tuple[str, str]:
    if not re.fullmatch(r"\d{2}:\d{2}", value or ""):
        raise ValueError(f"Invalid HH:MM time: {value}")
    hh, mm = value.split(":")
    return hh, mm


def _days_to_cron(days: list[str]) -> str:
    cron_days = []
    for day in days or []:
        mapped = DAY_TO_CRON.get(day)
        if mapped is None:
            raise ValueError(f"Unsupported day value: {day}")
        cron_days.append(mapped)
    uniq = []
    for d in cron_days:
        if d not in uniq:
            uniq.append(d)
    return ",".join(uniq)


def _build_mapping_lines(src_ip: str, signature: dict) -> list[str]:
    lines = []
    dscp = signature.get("priority_class", "video")

    for proto in signature.get("protocols", []):
        for port in signature.get("ports", []):
            lines.append(f"{proto}:{port} {dscp}")

    if src_ip:
        lines.append(f"{src_ip} {dscp}")

    for pattern in signature.get("dns_patterns", []):
        if pattern.startswith("dns:"):
            lines.append(f"{pattern} {dscp}")
        else:
            lines.append(f"dns:{pattern} {dscp}")

    deduped = []
    for line in lines:
        if line not in deduped:
            deduped.append(line)
    return deduped


def _heredoc_write_command(path: str, body: str, marker: str) -> str:
    return f"cat > {path} <<'{marker}'\n{body}{marker}\n"


def build_qosify_schedule_plan(live_plan: dict, cron_backend: dict):
    if not cron_backend.get("ok"):
        return {
            "ok": False,
            "reason": cron_backend.get("reason"),
        }

    remote_path = live_plan["remote_path"]
    staged_path = f"/etc/qosify/staged/{remote_path.split('/')[-1]}"
    enable_script = "/usr/libexec/llm-qosify-enable.sh"
    disable_script = "/usr/libexec/llm-qosify-disable.sh"

    days = live_plan["schedule"]["days"]
    start_time = live_plan["schedule"]["start_time"]
    end_time = live_plan["schedule"]["end_time"]

    cron_days = ",".join(_to_cron_day(d) for d in days)
    start_min, start_hour = start_time.split(":")[1], start_time.split(":")[0]
    end_min, end_hour = end_time.split(":")[1], end_time.split(":")[0]

    start_line = f"{start_min} {start_hour} * * {cron_days} {enable_script} '{staged_path}' '{remote_path}'"
    end_line = f"{end_min} {end_hour} * * {cron_days} {disable_script} '{remote_path}'"

    mode = cron_backend["mode"]
    cron_target = cron_backend["cron_target"]

    return {
        "ok": True,
        "mode": mode,
        "paths": {
            "staged_rule_path": staged_path,
            "enable_script": enable_script,
            "disable_script": disable_script,
            "cron_target": cron_target,
        },
        "artifacts": {
            "staged_file_body": live_plan["file_body"],
            "enable_script_body": _enable_script_body(),
            "disable_script_body": _disable_script_body(),
            "cron_lines": [start_line, end_line],
        },
    }


def _to_cron_day(day: str) -> str:
    mapping = {
        "Mon": "1",
        "Tue": "2",
        "Wed": "3",
        "Thu": "4",
        "Fri": "5",
        "Sat": "6",
        "Sun": "0",
    }
    return mapping[day]


def _enable_script_body():
    return """#!/bin/sh
set -eu
src="$1"
dst="$2"
mkdir -p "$(dirname "$dst")"
cp "$src" "$dst"
/etc/init.d/qosify restart >/dev/null 2>&1 || true
"""


def _disable_script_body():
    return """#!/bin/sh
set -eu
dst="$1"
rm -f "$dst"
/etc/init.d/qosify restart >/dev/null 2>&1 || true
"""