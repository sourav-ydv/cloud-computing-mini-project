import argparse
import csv
import json
import os
import random
import time

import numpy as np
import torch
import yaml

torch.set_num_threads(2)
from torch.utils.data import DataLoader, Dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    get_linear_schedule_with_warmup,
)

ap = argparse.ArgumentParser()
ap.add_argument("--data", default="datasets/v1/train.jsonl")
ap.add_argument("--config", default="training/config.yaml")
ap.add_argument("--out", default="models/v1")
ap.add_argument("--subset", type=int, default=1500)
ap.add_argument("--epochs", type=int, default=None)
a = ap.parse_args()

with open(a.config, encoding="utf-8") as f:
    cfg = yaml.safe_load(f)

random.seed(cfg["seed"])
np.random.seed(cfg["seed"])
torch.manual_seed(cfg["seed"])

print("loading tokenizer...", flush=True)
tokenizer = AutoTokenizer.from_pretrained(cfg["model_name"])
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token
print("loading model...", flush=True)
model = AutoModelForCausalLM.from_pretrained(cfg["model_name"])
print("model loaded", flush=True)

examples = []
with open(a.data, encoding="utf-8") as f:
    for line in f:
        if len(examples) >= a.subset:
            break
        rec = json.loads(line)
        prompt = f"Command: {rec['text']}\nJSON: "
        target = json.dumps(rec["teacher_json"])
        examples.append(prompt + target + tokenizer.eos_token)
print(f"built {len(examples)} examples", flush=True)


class JsonlDataset(Dataset):
    def __init__(self, texts, tok, max_len):
        self.enc = tok(
            texts,
            truncation=True,
            max_length=max_len,
            padding="max_length",
            return_tensors="pt",
        )

    def __len__(self):
        return self.enc["input_ids"].shape[0]

    def __getitem__(self, idx):
        input_ids = self.enc["input_ids"][idx]
        attn = self.enc["attention_mask"][idx]
        labels = input_ids.clone()
        labels[attn == 0] = -100
        return {"input_ids": input_ids, "attention_mask": attn, "labels": labels}


print("tokenizing dataset...", flush=True)
dataset = JsonlDataset(examples, tokenizer, cfg["max_seq_length"])
print("dataset tokenized", flush=True)
loader = DataLoader(dataset, batch_size=cfg["batch_size"], shuffle=True)

device = torch.device("cpu")
print("moving model to device...", flush=True)
model.to(device)
print("ready, starting training loop", flush=True)
optimizer = torch.optim.AdamW(model.parameters(), lr=cfg["learning_rate"])
num_epochs = a.epochs or cfg["num_epochs"]
total_steps = len(loader) * num_epochs
scheduler = get_linear_schedule_with_warmup(optimizer, num_warmup_steps=0, num_training_steps=total_steps)

os.makedirs(a.out, exist_ok=True)
os.makedirs("training", exist_ok=True)
loss_rows = []


model.train()
for epoch in range(num_epochs):
    total_loss = 0.0
    for step, batch in enumerate(loader):
        t0 = time.time()
        batch = {k: v.to(device) for k, v in batch.items()}
        optimizer.zero_grad()
        out = model(**batch)
        out.loss.backward()
        optimizer.step()
        scheduler.step()
        total_loss += out.loss.item()
        print(f"epoch {epoch + 1} step {step + 1}/{len(loader)} loss {out.loss.item():.4f} time {time.time() - t0:.1f}s", flush=True)
    avg_loss = total_loss / len(loader)
    print(f"epoch {epoch + 1}/{num_epochs} loss {avg_loss:.4f}", flush=True)
    loss_rows.append({"epoch": epoch + 1, "loss": avg_loss})

with open("training/loss.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["epoch", "loss"])
    writer.writeheader()
    writer.writerows(loss_rows)

model.save_pretrained(a.out)
tokenizer.save_pretrained(a.out)
print(f"saved model to {a.out}")
