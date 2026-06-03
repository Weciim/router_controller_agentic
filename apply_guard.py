def ensure_real_apply_allowed(exec_spec: dict, dry_run_only: bool) -> None:
    if dry_run_only:
        return

    backend_gate = (exec_spec or {}).get("backend_gate", {})
    if not backend_gate.get("real_apply_ready", False):
        reason = backend_gate.get("warning") or "Real apply is not allowed."
        raise RuntimeError(f"Refusing real apply: {reason}")