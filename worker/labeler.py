import io
import json
import os
import sys
import time

import boto3
import requests

S3_ENDPOINT = os.environ["S3_ENDPOINT"]
S3_ACCESS_KEY = os.environ["S3_ACCESS_KEY"]
S3_SECRET_KEY = os.environ["S3_SECRET_KEY"]
SHARD_INDEX = int(os.environ["SHARD_INDEX"])
SHARD_COUNT = int(os.environ["SHARD_COUNT"])
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
PROMPT_PATH = os.environ.get("PROMPT_PATH", "prompts/teacher_prompt.txt")
SOURCE_BUCKET = os.environ.get("SOURCE_BUCKET", "datasets")
SOURCE_KEY = os.environ.get("SOURCE_KEY", "commands_pool.jsonl")
DEST_KEY = f"teacher/shard-{SHARD_INDEX}.jsonl"
CHECKPOINT_EVERY = 25

s3 = boto3.client(
    "s3",
    endpoint_url=S3_ENDPOINT,
    aws_access_key_id=S3_ACCESS_KEY,
    aws_secret_access_key=S3_SECRET_KEY,
)

with open(PROMPT_PATH, encoding="utf-8") as f:
    prompt_template = f.read()

obj = s3.get_object(Bucket=SOURCE_BUCKET, Key=SOURCE_KEY)
lines = obj["Body"].read().decode("utf-8").splitlines()

records = []
for idx, line in enumerate(lines):
    if idx % SHARD_COUNT != SHARD_INDEX:
        continue
    if not line.strip():
        continue
    records.append(json.loads(line))

print(f"shard {SHARD_INDEX}/{SHARD_COUNT}: {len(records)} commands", file=sys.stderr)

results = []
try:
    obj = s3.get_object(Bucket="datasets", Key=DEST_KEY)
    for line in obj["Body"].read().decode("utf-8").splitlines():
        if line.strip():
            results.append(json.loads(line))
    done_ids = {r["id"] for r in results}
    records = [r for r in records if r["id"] not in done_ids]
    print(f"resuming, {len(results)} already done, {len(records)} left", file=sys.stderr)
except s3.exceptions.NoSuchKey:
    pass


def save():
    out = io.StringIO()
    for r in results:
        out.write(json.dumps(r) + "\n")
    s3.put_object(Bucket="datasets", Key=DEST_KEY, Body=out.getvalue().encode("utf-8"))


for i, rec in enumerate(records):
    prompt = prompt_template.replace("{command}", rec["text"])
    reply = ""
    for attempt in range(3):
        try:
            resp = requests.post(
                f"{OLLAMA_HOST}/api/generate",
                json={
                    "model": "phi3.5",
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                    "options": {"temperature": 0, "seed": 42, "num_predict": 120, "stop": ["\n\n", "Command:"]},
                },
                timeout=300,
            )
            resp.raise_for_status()
            reply = resp.json()["response"].strip()
            break
        except Exception as e:
            print(f"retry {rec['id']}: {e}", file=sys.stderr)
            time.sleep(2)
    results.append({"id": rec["id"], "text": rec["text"], "teacher_raw": reply})
    if (i + 1) % CHECKPOINT_EVERY == 0:
        save()
        print(f"shard {SHARD_INDEX}: {i + 1}/{len(records)} (checkpointed)", file=sys.stderr)

save()
print(f"shard {SHARD_INDEX}: done, {len(results)} total, wrote datasets/{DEST_KEY}", file=sys.stderr)