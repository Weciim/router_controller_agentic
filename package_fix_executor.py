from datetime import datetime


def execute_package_fix_plan(ssh_client, fix_plan: dict, dry_run: bool = True) -> dict:
    commands = fix_plan.get("commands", [])

    if dry_run:
        return {
            "applied": False,
            "dry_run": True,
            "applied_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "commands": commands,
            "notes": fix_plan.get("notes", []),
        }

    results = []
    for cmd in commands:
        if cmd.strip().startswith("#") or not cmd.strip():
            continue
        res = ssh_client.run(cmd, check=False)
        results.append(res)

    return {
        "applied": True,
        "dry_run": False,
        "applied_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "results": results,
        "notes": fix_plan.get("notes", []),
    }