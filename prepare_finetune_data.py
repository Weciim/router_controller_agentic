import json
from pathlib import Path

# =========================================================
# CONFIG
# =========================================================
DATASET_DIR = Path("router_dataset_programmatic_v2")

TRAIN_FILE = DATASET_DIR / "train.jsonl"
VALID_FILE = DATASET_DIR / "valid.jsonl"

TRAIN_CHAT_FILE = DATASET_DIR / "train_chat.jsonl"
VALID_CHAT_FILE = DATASET_DIR / "valid_chat.jsonl"

TRAIN_ALPACA_FILE = DATASET_DIR / "train_alpaca.jsonl"
VALID_ALPACA_FILE = DATASET_DIR / "valid_alpaca.jsonl"

SYSTEM_PROMPT = """You are a router control parser.
Convert the user's request into exactly one valid JSON object.
Return JSON only.
Do not add explanations.
Use this schema exactly:
{
  "intent": string|null,
  "action": string|null,
  "target_device": string|null,
  "target_profile": string|null,
  "service": string|null,
  "domains": [string]|null,
  "category": string|null,
  "days": [string]|null,
  "start_time": string|null,
  "end_time": string|null,
  "duration_minutes": integer|null,
  "priority": string|null,
  "bandwidth_mbps": integer|null,
  "requires_confirmation": boolean,
  "needs_clarification": boolean,
  "clarification_question": string|null,
  "status": string|null
}"""

# =========================================================
# HELPERS
# =========================================================
def read_jsonl(path):
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows

def to_chat_record(row):
    assistant_json = json.dumps(row["output"], ensure_ascii=False, separators=(",", ":"))
    return {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": row["input"]},
            {"role": "assistant", "content": assistant_json}
        ]
    }

def to_alpaca_record(row):
    assistant_json = json.dumps(row["output"], ensure_ascii=False, separators=(",", ":"))
    return {
        "instruction": SYSTEM_PROMPT,
        "input": row["input"],
        "output": assistant_json
    }

def write_jsonl(path, rows):
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

# =========================================================
# MAIN
# =========================================================
train_rows = read_jsonl(TRAIN_FILE)
valid_rows = read_jsonl(VALID_FILE)

train_chat = [to_chat_record(r) for r in train_rows]
valid_chat = [to_chat_record(r) for r in valid_rows]

train_alpaca = [to_alpaca_record(r) for r in train_rows]
valid_alpaca = [to_alpaca_record(r) for r in valid_rows]

write_jsonl(TRAIN_CHAT_FILE, train_chat)
write_jsonl(VALID_CHAT_FILE, valid_chat)
write_jsonl(TRAIN_ALPACA_FILE, train_alpaca)
write_jsonl(VALID_ALPACA_FILE, valid_alpaca)

print("Saved:")
print(" -", TRAIN_CHAT_FILE.resolve())
print(" -", VALID_CHAT_FILE.resolve())
print(" -", TRAIN_ALPACA_FILE.resolve())
print(" -", VALID_ALPACA_FILE.resolve())

print("\nCounts:")
print("train rows:", len(train_rows))
print("valid rows:", len(valid_rows))

print("\nExample chat sample:")
print(json.dumps(train_chat[0], ensure_ascii=False, indent=2)[:1500])

print("\nExample alpaca sample:")
print(json.dumps(train_alpaca[0], ensure_ascii=False, indent=2)[:1500])