#!/usr/bin/env python3
import sys
import pysrt
from transformers import AutoModelForCausalLM, AutoTokenizer

# ─── CONFIG ───────────────────────────────────────────────
MODEL_NAME   = "ByteDance-Seed/Seed-X-Instruct-7B"
INPUT_SRT    = sys.argv[1]  # e.g. input_en.srt
OUTPUT_SRT   = sys.argv[2]  # e.g. output_tr.srt
MAX_TOKENS   = 300000  # max_new_tokens per subtitle block
# ─────────────────────────────────────────────────────────

# load model & tokenizer (4‑bit quant to save VRAM)
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModelForCausalLM.from_pretrained(
    MODEL_NAME,
    device_map="auto",
    load_in_4bit=True,
    torch_dtype="auto",
    low_cpu_mem_usage=True,
)

# read original SRT
subs = pysrt.open(INPUT_SRT, encoding="utf-8")

# translate each subtitle block in place
for sub in subs:
    prompt = (
        "Translate the following subtitle text to Turkish, preserving meaning but not timing as this will be a complete subtitle translation:\n\n"
        f"{sub.text}\n\n###\n"
    )
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    out = model.generate(
        **inputs,
        max_new_tokens=MAX_TOKENS,
        do_sample=False,
        temperature=0.2,
    )
    # decode & strip the prompt echo if present
    translated = tokenizer.decode(out[0], skip_special_tokens=True)
    translated = translated.replace(prompt, "").strip()
    sub.text = translated

# write out new SRT with identical timings
subs.save(OUTPUT_SRT, encoding="utf-8")
print(f"✅ Saved translated subtitles to {OUTPUT_SRT}")
