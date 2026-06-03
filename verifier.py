from rules_store import get_rule


def verify_apply_result(apply_result: dict) -> dict:
    rule = apply_result.get("rule")
    if not rule:
        return {
            "verified": False,
            "reason": "No rule payload returned from apply_execution_spec()."
        }

    rule_id = rule.get("rule_id")
    if not rule_id:
        return {
            "verified": False,
            "reason": "Returned rule has no rule_id."
        }

    stored = get_rule(rule_id)
    if not stored:
        return {
            "verified": False,
            "reason": f"Rule {rule_id} not found in store after apply."
        }

    return {
        "verified": True,
        "dry_run": apply_result.get("dry_run", False),
        "rule_id": rule_id,
        "stored_rule": stored,
        "reason": "Dry run preview stored successfully."
    }