import json
import re
from pathlib import Path
from collections import Counter, defaultdict

import torch
print("Torch path:", torch.__file__)
print("Torch version:", torch.__version__)
from transformers import AutoTokenizer, AutoModelForCausalLM

# =========================================================
# CONFIG
# =========================================================
DATASET_DIR = Path("router_dataset_programmatic_v2")
VALID_FILE = DATASET_DIR / "valid_chat.jsonl"
REPORT_FILE = DATASET_DIR / "baseline_eval_report.json"

MODEL_NAME = "Qwen/Qwen2.5-1.5B-Instruct"   
MAX_SAMPLES = 100                           
MAX_NEW_TOKENS = 220
TEMPERATURE = 0.0
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

FIELDS = [
    "intent",
    "action",
    "target_device",
    "target_profile",
    "service",
    "domains",
    "category",
    "days",
    "start_time",
    "end_time",
    "duration_minutes",
    "priority",
    "bandwidth_mbps",
    "requires_confirmation",
    "needs_clarification",
    "clarification_question",
    "status"
]

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

def try_extract_json(text):
    text = text.strip()

    # Direct parse
    try:
        return json.loads(text), "direct"
    except Exception:
        pass

    # Extract largest {...} block
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        candidate = match.group(0)
        try:
            return json.loads(candidate), "regex_block"
        except Exception:
            pass

    return None, "failed"

def normalize_value(v):
    if isinstance(v, str):
        return v.strip()
    if isinstance(v, list):
        return [normalize_value(x) for x in v]
    return v

def exact_object_match(pred, gold):
    for f in FIELDS:
        if normalize_value(pred.get(f)) != normalize_value(gold.get(f)):
            return False
    return True

def build_prompt(messages, tokenizer):
    if hasattr(tokenizer, "apply_chat_template"):
        return tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )
    # fallback
    chunks = []
    for m in messages:
        chunks.append(f"{m['role'].upper()}: {m['content']}")
    chunks.append("ASSISTANT:")
    return "\n".join(chunks)

# =========================================================
# LOAD DATA
# =========================================================
rows = read_jsonl(VALID_FILE)[:MAX_SAMPLES]

# Each row:
# {
#   "messages": [
#       {"role":"system","content":"..."},
#       {"role":"user","content":"..."},
#       {"role":"assistant","content":"{...json...}"}
#   ]
# }

# =========================================================
# LOAD MODEL
# =========================================================
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, trust_remote_code=True)
model = AutoModelForCausalLM.from_pretrained(
    MODEL_NAME,
    torch_dtype=torch.float16 if DEVICE == "cuda" else torch.float32,
    device_map="auto" if DEVICE == "cuda" else None,
    trust_remote_code=True
)

if DEVICE != "cuda":
    model.to(DEVICE)

# =========================================================
# EVALUATION
# =========================================================
results = []
field_correct = Counter()
field_total = Counter()

valid_json_count = 0
exact_match_count = 0
parse_method_counts = Counter()

for idx, row in enumerate(rows):
    messages = row["messages"]
    gold = json.loads(messages[-1]["content"])

    prompt_messages = messages[:-1]  # system + user only
    prompt_text = build_prompt(prompt_messages, tokenizer)

    inputs = tokenizer(prompt_text, return_tensors="pt").to(model.device)

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=MAX_NEW_TOKENS,
            do_sample=False if TEMPERATURE == 0.0 else True,
            temperature=TEMPERATURE,
            pad_token_id=tokenizer.eos_token_id
        )

    generated = tokenizer.decode(outputs[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True).strip()
    pred_json, parse_method = try_extract_json(generated)
    parse_method_counts[parse_method] += 1

    sample_result = {
        "index": idx,
        "user_input": messages[1]["content"],
        "raw_output": generated,
        "json_valid": pred_json is not None,
        "parse_method": parse_method,
        "exact_match": False,
        "field_matches": {},
        "gold": gold,
        "pred": pred_json
    }

    if pred_json is not None:
        valid_json_count += 1

        is_exact = exact_object_match(pred_json, gold)
        sample_result["exact_match"] = is_exact
        if is_exact:
            exact_match_count += 1

        for f in FIELDS:
            pred_val = normalize_value(pred_json.get(f))
            gold_val = normalize_value(gold.get(f))
            ok = pred_val == gold_val
            sample_result["field_matches"][f] = ok
            field_total[f] += 1
            if ok:
                field_correct[f] += 1
    else:
        for f in FIELDS:
            sample_result["field_matches"][f] = False
            field_total[f] += 1

    results.append(sample_result)

# =========================================================
# SUMMARY
# =========================================================
num_samples = len(results)
field_accuracy = {
    f: (field_correct[f] / field_total[f] if field_total[f] else 0.0)
    for f in FIELDS
}

summary = {
    "model_name": MODEL_NAME,
    "num_samples": num_samples,
    "valid_json_rate": valid_json_count / num_samples if num_samples else 0.0,
    "exact_match_rate": exact_match_count / num_samples if num_samples else 0.0,
    "parse_method_counts": dict(parse_method_counts),
    "field_accuracy": field_accuracy
}

report = {
    "summary": summary,
    "samples": results
}

with open(REPORT_FILE, "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

# =========================================================
# PRINT SUMMARY
# =========================================================
print("=" * 80)
print("BASELINE ROUTER JSON EVALUATION")
print("=" * 80)
print("Model:", MODEL_NAME)
print("Samples:", num_samples)
print("Valid JSON rate:", round(summary["valid_json_rate"] * 100, 2), "%")
print("Exact match rate:", round(summary["exact_match_rate"] * 100, 2), "%")
print("Parse methods:", summary["parse_method_counts"])
print("\nField accuracy:")
for f in FIELDS:
    print(f"{f:24s} {summary['field_accuracy'][f]*100:6.2f}%")
print("\nSaved report:", REPORT_FILE.resolve())