from qosify_catalog import APPLICATION_SIGNATURES


def list_supported_apps() -> list[str]:
    return sorted(APPLICATION_SIGNATURES.keys())


def list_supported_aliases() -> list[str]:
    values = set()
    for canonical_name, signature in APPLICATION_SIGNATURES.items():
        values.add(canonical_name)
        for alias in signature.get("aliases", []):
            values.add(alias)
    return sorted(values)