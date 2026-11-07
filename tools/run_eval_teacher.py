import json
import sys

import requests

PROMPT_PATH = sys.argv[1]
VAL_PATH = sys.argv[2]
OUT_PATH = sys.argv[3]
OLLAMA_HOST = sys.argv[4] if len(sys.argv) > 4 else "http://localhost:11434"

with open(PROMPT_PATH, encoding="utf-8") as f:
    prompt_template = f.read()

with open(VAL_PATH, encoding="utf-8") as f, open(OUT_PATH, "w", encoding="utf-8") as out:
    for line in f:
        if not line.strip():
            continue
        rec = json.loads(line)
        prompt = prompt_template.replace("{command}", rec["text"])
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
        out.write(json.dumps({"id": rec["id"], "prediction": reply}) + "\n")
