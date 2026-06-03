BANNER_PREFIXES = (
    "_______",
    "|       |.-----",
    "|   -   ||",
    "|_______||",
    "|__| W I R E L E S S",
    "-----------------------------------------------------",
    "OpenWrt recently switched to the",
    "OPKG Command",
    "opkg install <pkg>",
    "opkg remove <pkg>",
    "opkg upgrade",
    "opkg files <pkg>",
    "opkg list-installed",
    "opkg update",
    "opkg search <pkg>",
    "For more information visit:",
    "https://openwrt.org/docs/guide-user/additional-software/opkg-to-apk-cheatsheet",
)
BANNER_SNIPPETS = [
    "W I R E L E S S   F R E E D O M",
    "OpenWrt recently switched to the \"apk\" package manager!",
    "OPKG Command",
    "APK Equivalent",
    "For more information visit:",
    "opkg install <pkg>",
    "apk add <pkg>",
]

def strip_openwrt_banner(text: str) -> str:
    if not text:
        return ""

    lines = text.splitlines()

    start = None
    for i, line in enumerate(lines):
        if any(snippet in line for snippet in BANNER_SNIPPETS):
            start = i
            break

    if start is None:
        return text.strip()

    end = start
    while end < len(lines):
        line = lines[end]
        if "https://openwrt.org/docs/guide-user/additional-software/opkg-to-apk-cheatsheet" in line:
            end += 1
            break
        end += 1

    cleaned = lines[end:]
    while cleaned and not cleaned[0].strip():
        cleaned.pop(0)

    return "\n".join(cleaned).strip()


def cleaned_lines(text: str) -> list[str]:
    cleaned = strip_openwrt_banner(text)
    return [line.strip() for line in cleaned.splitlines() if line.strip()]
OPENWRT_BANNER_MARKERS = [
    "OpenWrt recently switched to the \"apk\" package manager!",
    "OPKG Command           APK Equivalent",
    "For more information visit:",
    "https://openwrt.org/docs/guide-user/additional-software/opkg-to-apk-cheatsheet",
]

def strip_openwrt_banner(text: str) -> str:
    if not text:
        return ""
    lines = text.splitlines()

    cut_index = None
    for i, line in enumerate(lines):
        if any(marker in line for marker in OPENWRT_BANNER_MARKERS):
            cut_index = i
            break

    if cut_index is None:
        return text.strip()

    j = cut_index
    while j < len(lines) and lines[j].strip() != "":
        j += 1
    while j < len(lines) and lines[j].strip() == "":
        j += 1

    cleaned = "\n".join(lines[j:]).strip()
    return cleaned


def normalize_ssh_result(result: dict) -> dict:
    stdout = strip_openwrt_banner(result.get("stdout") or "")
    stderr = strip_openwrt_banner(result.get("stderr") or "")
    exit_code = result.get("exit_code")

    failed = bool(stderr.strip())
    if exit_code not in (None, 0):
        failed = True

    out = dict(result)
    out["stdout"] = stdout
    out["stderr"] = stderr
    out["failed"] = failed
    return out