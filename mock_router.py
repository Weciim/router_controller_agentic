from schemas import RouterAction

def dry_run(action: RouterAction) -> dict:
    return {
        "status": "dry_run",
        "intent": action.intent,
        "summary": f"Would execute {action.intent} for device={action.target_device} profile={action.target_profile}"
    }