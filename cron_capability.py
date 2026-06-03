from ssh_result_utils import run_ssh_normalized


def detect_scheduler_backend(ssh_client):
    probes = {
        "cron_d": run_ssh_normalized(ssh_client, "test -d /etc/cron.d", check=False),
        "crontabs": run_ssh_normalized(ssh_client, "test -d /etc/crontabs", check=False),
        "crond_bin": run_ssh_normalized(ssh_client, "command -v crond", check=False),
        "crontab_bin": run_ssh_normalized(ssh_client, "command -v crontab", check=False),
        "init_crond": run_ssh_normalized(ssh_client, "test -x /etc/init.d/cron || test -x /etc/init.d/crond", check=False),
        "spool_var": run_ssh_normalized(ssh_client, "test -d /var/spool/cron || test -d /var/spool/cron/crontabs", check=False),
        "spool_tmp": run_ssh_normalized(ssh_client, "test -d /tmp/crontabs", check=False),
    }

    has_etc_cron_d = probes["cron_d"]["exit_status"] == 0
    has_etc_crontabs = probes["crontabs"]["exit_status"] == 0
    has_crond_bin = probes["crond_bin"]["exit_status"] == 0
    has_crontab_bin = probes["crontab_bin"]["exit_status"] == 0
    has_init = probes["init_crond"]["exit_status"] == 0
    has_spool_var = probes["spool_var"]["exit_status"] == 0
    has_spool_tmp = probes["spool_tmp"]["exit_status"] == 0

    if has_etc_cron_d:
        return {
            "ok": True,
            "mode": "cron.d",
            "cron_owner_style": "root_file",
            "cron_target": "/etc/cron.d/llm-qosify",
            "reason": None,
            "probes": probes,
        }

    if has_etc_crontabs:
        return {
            "ok": True,
            "mode": "crontabs",
            "cron_owner_style": "root_spool_file",
            "cron_target": "/etc/crontabs/root",
            "reason": None,
            "probes": probes,
        }

    if has_crontab_bin:
        return {
            "ok": True,
            "mode": "crontab_cmd",
            "cron_owner_style": "crontab_install",
            "cron_target": "root",
            "reason": None,
            "probes": probes,
        }

    if has_crond_bin and (has_spool_var or has_spool_tmp or has_init):
        return {
            "ok": True,
            "mode": "crond_runtime_only",
            "cron_owner_style": "runtime_spool",
            "cron_target": "/tmp/crontabs/root" if has_spool_tmp else "/var/spool/cron/crontabs/root",
            "reason": None,
            "probes": probes,
        }

    return {
        "ok": False,
        "mode": "unknown",
        "cron_owner_style": None,
        "cron_target": None,
        "reason": "No usable cron backend detected: no /etc/cron.d, /etc/crontabs, crontab command, or writable runtime spool.",
        "probes": probes,
    }