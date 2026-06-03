import json
import re
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftConfig, PeftModel

ADAPTER_PATH = r"C:\router\models\checkpoint-300"

_tokenizer = None
_model = None

SCHEMA_EXAMPLE = {
    "intent": "schedule_block",
    "action": "block",
    "target_device": "WecimsPC",
    "target_profile": None,
    "service": None,
    "domains": ["youtube.com"],
    "category": None,
    "days": ["weekdays"],
    "start_time": "19:00",
    "end_time": "21:00",
    "duration_minutes": None,
    "priority": None,
    "bandwidth_mbps": None,
    "requires_confirmation": True,
    "needs_clarification": False,
    "clarification_question": None,
    "status": "ok"
}

def _load_model():
    global _tokenizer, _model

    if _tokenizer is not None and _model is not None:
        return _tokenizer, _model

    peft_config = PeftConfig.from_pretrained(ADAPTER_PATH)
    base_model_name = peft_config.base_model_name_or_path

    _tokenizer = AutoTokenizer.from_pretrained(ADAPTER_PATH, trust_remote_code=True)
    if _tokenizer.pad_token is None:
        _tokenizer.pad_token = _tokenizer.eos_token

    base_model = AutoModelForCausalLM.from_pretrained(
        base_model_name,
        dtype="auto",
        device_map="auto",
        low_cpu_mem_usage=True,
        trust_remote_code=True,
    )

    _model = PeftModel.from_pretrained(base_model, ADAPTER_PATH)
    _model.eval()

    return _tokenizer, _model

def warmup_model():
    _load_model()

def _build_messages(user_prompt: str):
    schema_text = json.dumps(SCHEMA_EXAMPLE, ensure_ascii=False)

    return [
        {
            "role": "system",
            "content": (
                "You are a router control parser. "
                "Return exactly one valid JSON object and nothing else."
            ),
        },
        {
            "role": "user",
            "content": (
                "Convert the following request into one JSON object.\n\n"
                "Allowed keys:\n"
                "intent, action, target_device, target_profile, service, domains, "
                "category, days, start_time, end_time, duration_minutes, priority, "
                "bandwidth_mbps, requires_confirmation, needs_clarification, "
                "clarification_question, status\n\n"
                f"Example format:\n{schema_text}\n\n"
                f"User request: {user_prompt}"
            ),
        },
    ]

def _extract_json(text: str) -> dict:
    text = text.strip()

    try:
        return json.loads(text)
    except Exception:
        pass

    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        candidate = match.group(0)
        try:
            return json.loads(candidate)
        except Exception:
            pass

    raise ValueError(f"No valid JSON object found in model output: {text}")

def parse_prompt_to_router_json(user_prompt: str) -> dict:
    tokenizer, model = _load_model()
    messages = _build_messages(user_prompt)

    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True
    )

    inputs = tokenizer([text], return_tensors="pt", truncation=True)
    inputs = {k: v.to(model.device) for k, v in inputs.items()}

    with torch.no_grad():
        output_ids = model.generate(
            **inputs,
            max_new_tokens=120,
            do_sample=False,
            use_cache=True,
            pad_token_id=tokenizer.eos_token_id,
        )

    generated_ids = [
        out[len(inp):] for inp, out in zip(inputs["input_ids"], output_ids)
    ]
    generated_text = tokenizer.batch_decode(
        generated_ids,
        skip_special_tokens=True
    )[0].strip()

    return _extract_json(generated_text)