import json
import sys

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL_DIR = sys.argv[1]
VAL_PATH = sys.argv[2]
OUT_PATH = sys.argv[3]
MAX_NEW_TOKENS = int(sys.argv[4]) if len(sys.argv) > 4 else 64

tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR)
model = AutoModelForCausalLM.from_pretrained(MODEL_DIR)
model.eval()

with open(VAL_PATH, encoding="utf-8") as f, open(OUT_PATH, "w", encoding="utf-8") as out:
    for line in f:
        if not line.strip():
            continue
        rec = json.loads(line)
        prompt = f"Command: {rec['text']}\nJSON: "
        inputs = tokenizer(prompt, return_tensors="pt")
        with torch.no_grad():
            generated = model.generate(
                **inputs,
                max_new_tokens=MAX_NEW_TOKENS,
                do_sample=False,
                pad_token_id=tokenizer.eos_token_id,
            )
        full = tokenizer.decode(generated[0], skip_special_tokens=True)
        prediction = full[len(prompt):].strip()
        out.write(json.dumps({"id": rec["id"], "prediction": prediction}) + "\n")
