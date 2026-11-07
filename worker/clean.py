import glob
import hashlib
import json
import os
import sys

INTENTS = {
    "alarm_set",
    "alarm_query",
    "calendar_set",
    "calendar_query",
    "calendar_remove",
    "weather_query",
    "datetime_query",
    "recommendation_events",
}
KEYS = {"intent", "date", "time", "place"}

SHARD_DIR = sys.argv[1] if len(sys.argv) > 1 else "shards"
OUT_DIR = sys.argv[2] if len(sys.argv) > 2 else "datasets/v1"

os.makedirs(OUT_DIR, exist_ok=True)

records = {}
for path in sorted(glob.glob(os.path.join(SHARD_DIR, "shard-*.jsonl"))):
    with open(path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            rec = json.loads(line)
            records[rec["id"]] = rec

input_count = len(records)
reject_a = reject_b = reject_c = reject_d = 0
seen_text = {}
kept = []

for rid in sorted(records.keys()):
    rec = records[rid]
    text = rec["text"]
    raw = rec["teacher_raw"]
    try:
        parsed = json.loads(raw)
    except Exception:
        reject_a += 1
        continue
    if not isinstance(parsed, dict) or set(parsed.keys()) != KEYS:
        reject_b += 1
        continue
    if parsed["intent"] not in INTENTS:
        reject_c += 1
        continue
    bad_slot = False
    for slot in ("date", "time", "place"):
        val = parsed[slot]
        if val is not None:
            if not isinstance(val, str) or val.lower() not in text.lower():
                bad_slot = True
                break
    if bad_slot:
        reject_d += 1
        continue
    kept.append({"id": rid, "text": text, "teacher_json": parsed})
    seen_text.setdefault(text, []).append(rid)

duplicates = 0
final = []
for item in kept:
    ids_for_text = seen_text[item["text"]]
    if item["id"] != min(ids_for_text):
        duplicates += 1
        continue
    final.append(item)

final.sort(key=lambda r: r["id"])

out_path = os.path.join(OUT_DIR, "train.jsonl")
with open(out_path, "w", encoding="utf-8") as f:
    for item in final:
        f.write(json.dumps(item) + "\n")

digest = hashlib.sha256()
with open(out_path, "rb") as f:
    digest.update(f.read())

with open(os.path.join(OUT_DIR, "train.sha256"), "w", encoding="utf-8") as f:
    f.write(digest.hexdigest() + "  train.jsonl\n")

print(f"input: {input_count}")
print(f"rejected not valid json (a): {reject_a}")
print(f"rejected wrong keys (b): {reject_b}")
print(f"rejected bad intent (c): {reject_c}")
print(f"rejected bad slot value (d): {reject_d}")
print(f"duplicates: {duplicates}")
print(f"kept: {len(final)}")
check = reject_a + reject_b + reject_c + reject_d + duplicates + len(final)
print(f"sum check: {check} (should equal input {input_count})")
