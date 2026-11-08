import json
import os
import socket
import threading

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import asyncio

import boto3
import torch
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from transformers import AutoModelForCausalLM, AutoTokenizer

torch.set_num_threads(1)

MODEL_URI = os.environ["MODEL_URI"]
MODEL_VERSION = os.environ["MODEL_VERSION"]
S3_ENDPOINT = os.environ["S3_ENDPOINT"]
MAX_NEW_TOKENS = int(os.environ.get("MAX_NEW_TOKENS", "64"))
FAULT_INJECT = os.environ.get("FAULT_INJECT", "0")
POD_NAME = os.environ.get("POD_NAME", socket.gethostname())

VALID_INTENTS = {
    "alarm_set",
    "alarm_query",
    "calendar_set",
    "calendar_query",
    "calendar_remove",
    "weather_query",
    "datetime_query",
    "recommendation_events",
}
VALID_KEYS = {"intent", "date", "time", "place"}

app = FastAPI()
state = {"ready": False, "model": None, "tokenizer": None}


def load_model():
    bucket, prefix = MODEL_URI.replace("s3://", "").split("/", 1)
    local_dir = "/tmp/model"
    os.makedirs(local_dir, exist_ok=True)
    s3 = boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
    )
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key.endswith("model.sha256"):
                continue
            name = key[len(prefix):].lstrip("/")
            if not name:
                continue
            dest = os.path.join(local_dir, name)
            s3.download_file(bucket, key, dest)
    tokenizer = AutoTokenizer.from_pretrained(local_dir)
    model = AutoModelForCausalLM.from_pretrained(local_dir)
    model.eval()
    state["tokenizer"] = tokenizer
    state["model"] = model
    state["ready"] = True


threading.Thread(target=load_model, daemon=True).start()


def validate(obj):
    if not isinstance(obj, dict) or set(obj.keys()) != VALID_KEYS:
        return False
    if obj["intent"] not in VALID_INTENTS:
        return False
    for key in ("date", "time", "place"):
        if obj[key] is not None and not isinstance(obj[key], str):
            return False
    return True


@app.get("/healthz")
def healthz():
    return {"status": "alive"}


@app.get("/readyz")
def readyz():
    if state["ready"]:
        return {"status": "ready"}
    return JSONResponse(status_code=503, content={"status": "loading"})

def run_parse(text):
    if FAULT_INJECT == "1":
        raw = "not json"
    else:
        prompt = f"Command: {text}\nJSON: "
        inputs = state["tokenizer"](prompt, return_tensors="pt")
        input_len = inputs["input_ids"].shape[1]
        with torch.no_grad():
            out = state["model"].generate(
                **inputs,
                max_new_tokens=MAX_NEW_TOKENS,
                do_sample=False,
                pad_token_id=state["tokenizer"].eos_token_id,
            )
        new_tokens = out[0][input_len:]
        raw = state["tokenizer"].decode(new_tokens, skip_special_tokens=True).strip()
        while raw.lower().startswith("json:"):
            raw = raw.split(":", 1)[1].strip()
        if "{" in raw:
            raw = raw[raw.index("{"):]

    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError, ValueError):
        parsed = None

    if parsed is None or not validate(parsed):
        return JSONResponse(
            status_code=500,
            content={"error": "invalid_model_output"},
            headers={"X-Model-Version": MODEL_VERSION, "X-Served-By": POD_NAME},
        )

    return JSONResponse(
        status_code=200,
        content=parsed,
        headers={"X-Model-Version": MODEL_VERSION, "X-Served-By": POD_NAME},
    )

@app.post("/parse")
async def parse(request: Request):
    body = await request.json()
    text = body["text"]
    return await asyncio.to_thread(run_parse, text)
    text = body["text"]

    if FAULT_INJECT == "1":
        raw = "not json"
    else:
        prompt = f"Command: {text}\nJSON: "
        inputs = state["tokenizer"](prompt, return_tensors="pt")
        input_len = inputs["input_ids"].shape[1]
        with torch.no_grad():
            out = state["model"].generate(
                **inputs,
                max_new_tokens=MAX_NEW_TOKENS,
                do_sample=False,
                pad_token_id=state["tokenizer"].eos_token_id,
            )
        new_tokens = out[0][input_len:]
        raw = state["tokenizer"].decode(new_tokens, skip_special_tokens=True).strip()
        while raw.lower().startswith("json:"):
            raw = raw.split(":", 1)[1].strip()
        if "{" in raw:
            raw = raw[raw.index("{"):]

    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError, ValueError):
        parsed = None

    if parsed is None or not validate(parsed):
        return JSONResponse(
            status_code=500,
            content={"error": "invalid_model_output"},
            headers={"X-Model-Version": MODEL_VERSION, "X-Served-By": POD_NAME},
        )

    return JSONResponse(
        status_code=200,
        content=parsed,
        headers={"X-Model-Version": MODEL_VERSION, "X-Served-By": POD_NAME},
    )
