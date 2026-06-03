import json
from pathlib import Path

from datasets import load_dataset
from unsloth import FastLanguageModel, is_bfloat16_supported
from trl import SFTTrainer, SFTConfig

# =========================================================
# CONFIG
# =========================================================
DATASET_DIR = "router_dataset_programmatic_v2"
TRAIN_FILE = f"{DATASET_DIR}/train_chat.jsonl"
VALID_FILE = f"{DATASET_DIR}/valid_chat.jsonl"

MODEL_NAME = "unsloth/Qwen2.5-1.5B-Instruct"
OUTPUT_DIR = "router_qwen25_15b_lora"

MAX_SEQ_LENGTH = 1024
LOAD_IN_4BIT = True

# LoRA
R = 16
LORA_ALPHA = 16
LORA_DROPOUT = 0.0

# Training
PER_DEVICE_BATCH_SIZE = 2
GRAD_ACCUM = 4
LEARNING_RATE = 2e-4
WARMUP_STEPS = 20
MAX_STEPS = 400
LOGGING_STEPS = 10
EVAL_STEPS = 50
SAVE_STEPS = 50
SEED = 42

# =========================================================
# LOAD MODEL
# =========================================================
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name=MODEL_NAME,
    max_seq_length=MAX_SEQ_LENGTH,
    dtype=None,
    load_in_4bit=LOAD_IN_4BIT,
)

model = FastLanguageModel.get_peft_model(
    model,
    r=R,
    target_modules=[
        "q_proj", "k_proj", "v_proj", "o_proj",
        "gate_proj", "up_proj", "down_proj",
    ],
    lora_alpha=LORA_ALPHA,
    lora_dropout=LORA_DROPOUT,
    bias="none",
    use_gradient_checkpointing="unsloth",
    random_state=SEED,
    use_rslora=False,
    loftq_config=None,
)

# =========================================================
# LOAD DATA
# =========================================================
train_dataset = load_dataset("json", data_files=TRAIN_FILE, split="train")
valid_dataset = load_dataset("json", data_files=VALID_FILE, split="train")

# =========================================================
# FORMAT DATA
# =========================================================
def formatting_func(example):
    texts = []
    for messages in example["messages"]:
        text = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=False,
        )
        texts.append(text)
    return {"text": texts}

train_dataset = train_dataset.map(formatting_func, batched=True)
valid_dataset = valid_dataset.map(formatting_func, batched=True)

# =========================================================
# TRAINER
# =========================================================
trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=train_dataset,
    eval_dataset=valid_dataset,
    args=SFTConfig(
        dataset_text_field="text",
        max_seq_length=MAX_SEQ_LENGTH,
        per_device_train_batch_size=PER_DEVICE_BATCH_SIZE,
        per_device_eval_batch_size=PER_DEVICE_BATCH_SIZE,
        gradient_accumulation_steps=GRAD_ACCUM,
        warmup_steps=WARMUP_STEPS,
        max_steps=MAX_STEPS,
        learning_rate=LEARNING_RATE,
        logging_steps=LOGGING_STEPS,
        eval_steps=EVAL_STEPS,
        save_steps=SAVE_STEPS,
        eval_strategy="steps",
        save_strategy="steps",
        optim="adamw_8bit",
        weight_decay=0.01,
        lr_scheduler_type="linear",
        seed=SEED,
        report_to="none",
        output_dir=OUTPUT_DIR,
        bf16=is_bfloat16_supported(),
        fp16=not is_bfloat16_supported(),
        packing=False,
        dataset_num_proc=1,
    ),
)

trainer_stats = trainer.train()

# =========================================================
# SAVE
# =========================================================
model.save_pretrained(OUTPUT_DIR)
tokenizer.save_pretrained(OUTPUT_DIR)

print("Training finished.")
print("Adapter/model saved to:", OUTPUT_DIR)
print(trainer_stats)