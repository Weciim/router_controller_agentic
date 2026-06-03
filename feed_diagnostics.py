from ssh_output_cleaner import strip_openwrt_banner, cleaned_lines


def _text(result: dict) -> str:
    return ((result.get("stdout") or "") + "\n" + (result.get("stderr") or "")).strip()


def diagnose_apk_feeds(ssh_client) -> dict:
    repo_res = ssh_client.run("cat /etc/apk/repositories 2>/dev/null || true", check=False)
    repo_dir_res = ssh_client.run("ls -la /etc/apk /etc/apk/repositories.d 2>/dev/null || true", check=False)
    update_res = ssh_client.run("apk update 2>&1 || true", check=False)
    search_dnsmasq_res = ssh_client.run("apk search dnsmasq 2>&1 || true", check=False)
    search_full_res = ssh_client.run("apk search dnsmasq-full 2>&1 || true", check=False)
    providers_res = ssh_client.run("apk list --providers dnsmasq 2>&1 || true", check=False)
    policy_res = ssh_client.run("apk policy dnsmasq 2>&1 || true", check=False)
    arch_res = ssh_client.run("uname -m 2>/dev/null || true", check=False)

    repo_text = strip_openwrt_banner(_text(repo_res))
    repo_dir_text = strip_openwrt_banner(_text(repo_dir_res))
    update_text = strip_openwrt_banner(_text(update_res))
    search_dnsmasq_text = strip_openwrt_banner(_text(search_dnsmasq_res))
    search_full_text = strip_openwrt_banner(_text(search_full_res))
    providers_text = strip_openwrt_banner(_text(providers_res))
    policy_text = strip_openwrt_banner(_text(policy_res))
    arch_text = strip_openwrt_banner(_text(arch_res))

    dnsmasq_hits = cleaned_lines(search_dnsmasq_text)
    full_hits = cleaned_lines(search_full_text)
    provider_hits = cleaned_lines(providers_text)

    recommendations = []

    if not repo_text.strip():
        recommendations.append("No entries found in /etc/apk/repositories; inspect repositories.d and image defaults.")
    if "error" in update_text.lower() or "warning" in update_text.lower():
        recommendations.append("Inspect apk update output for feed, signature, or connectivity problems.")
    if not dnsmasq_hits and not provider_hits:
        recommendations.append("No dnsmasq-related package metadata was returned; verify package indexes and repository configuration.")
    if dnsmasq_hits and not full_hits:
        recommendations.append("dnsmasq is visible but dnsmasq-full is not; this image/feed set may not publish the full variant.")
    if full_hits:
        recommendations.append("dnsmasq-full appears available; you can add a guided install/remediation path.")
    if provider_hits:
        recommendations.append("Use provider data to distinguish variant names published by this release.")

    return {
        "ok": True,
        "checks": {
            "repositories_present": bool(repo_text.strip() or repo_dir_text.strip()),
            "apk_update_ran": True,
            "dnsmasq_search_has_hits": bool(dnsmasq_hits),
            "dnsmasq_full_search_has_hits": bool(full_hits),
            "dnsmasq_provider_info_present": bool(provider_hits),
        },
        "system": {
            "arch": arch_text.strip(),
        },
        "repositories": {
            "main_file": repo_text,
            "directory_listing": repo_dir_text,
        },
        "search_results": {
            "dnsmasq": dnsmasq_hits,
            "dnsmasq_full": full_hits,
            "providers_dnsmasq": provider_hits,
        },
        "evidence": {
            "apk_update": update_text[:4000],
            "apk_policy_dnsmasq": policy_text[:4000],
        },
        "recommendations": recommendations,
    }