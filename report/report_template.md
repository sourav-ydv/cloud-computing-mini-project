# Cloud Computing Mini Project — Report

Name: Sourav Yadav
Roll number: 230101043
GitHub repo: https://github.com/sourav-ydv/cloud-computing-mini-project

## 1. Object Storage and Parallel Teacher Labelling
Architecture, sharding explanation (half page max), counts table (input, rejected a-d, duplicates, kept).

## 2. Training the Student

config.yaml summary: seed 42, learning rate 5.0e-5, batch size 8, 3 epochs, max sequence length 128, EleutherAI/pythia-70m, trained with PyTorch 2.3.1+cpu and Transformers 4.42.4.

Loss curve (v1, seed 42, 1500 examples): epoch 1 — 1.0132, epoch 2 — 0.6729, epoch 3 — 0.5260. A second version (v2, seed 123) was trained the same way: epoch 1 — 1.0315, epoch 2 — 0.6875, epoch 3 — 0.5471.

Model artefact locations: `models/v1/`, `models/v2/`, uploaded to the `models` bucket under `v1/` and `v2/`, each with a SHA-256 checksum written to `model.sha256` alongside the weights.

### Sequence-level vs logit-based distillation

Sequence-level distillation trains the student on the teacher's final output text, treated as if it were a ground-truth label. For this project, the teacher (phi3.5, run through Ollama with temperature 0 and seed 42) generated a JSON object for each of the 3,000 commands in the pool. After cleaning, 2,856 of these teacher outputs became training examples: the student (Pythia-70M) was fine-tuned to predict the exact JSON string the teacher produced, given the command as input. The student never sees the teacher's internal computation — only its output text.

Logit-based distillation instead trains the student to match the teacher's full probability distribution over the vocabulary at each generation step (the "soft targets"), not just the single token the teacher happened to pick. This usually transfers more information per example, since the distribution encodes the teacher's relative confidence across all plausible next tokens, not only its top choice.

Logit-based distillation was not possible in this project because Ollama's `/api/generate` endpoint only returns the generated text, not the per-token logits or probability distribution the teacher model computed internally. Without access to those distributions, there is nothing to match the student's distribution against beyond the teacher's chosen output tokens, which is exactly what sequence-level distillation uses.

### Results

| Model | JSON validity | Intent accuracy | Date | Time | Place | Full-frame |
|---|---|---|---|---|---|---|
| Teacher (phi3.5, 3.8B) | 99% | 82% | 84% | 82% | 79% | 46% |
| Untrained Pythia-70M | 0% | 0% | 0% | 0% | 0% | 0% |
| Trained student (Pythia-70M) | 99% | 81% | 71% | 82% | 79% | 40% |

The untrained model produced no valid JSON at all on the validation set — it has no notion of the task's output format. After fine-tuning on 1,500 teacher-labelled examples, the student reaches 40% full-frame accuracy, 87% of the teacher's 46%, despite being roughly 54x smaller in parameter count (70M vs 3.8B). JSON validity and intent accuracy are nearly identical between teacher and student; the main gap is in slot accuracy, particularly `date`, where the student is less consistent than the teacher.

### Limitation

A specific limitation observed during generation: in a noticeable fraction of early-epoch outputs (and occasionally even in the final model), the student echoed its own prompt label — producing `"JSON: {...}"` or repeating `"JSON:"` a second time before the actual object — rather than going straight to the JSON object the teacher always produced. This is a training-data formatting artifact: with only 1,500 examples and 3 epochs on a 70M-parameter model, the student partially learned the surface pattern of the prompt template itself rather than cleanly separating "prompt" from "completion." The teacher never exhibits this behaviour. In practice this was handled by stripping a leading repeated `"JSON:"` label during post-processing before JSON parsing, which is why the reported `json_validity` (99%) is high despite this artifact — but it is a real limitation of the fine-tuned model's output discipline, not something hidden by the scoring method.

## 3. The Inference Service in a Container

All three endpoints behave as specified: /healthz returns 200 once the process is alive;
/readyz returns 503 until the model finishes downloading from object storage, then 200;
/parse returns the four-key JSON with X-Model-Version and X-Served-By headers set correctly.

FAULT_INJECT=1 test: /parse returned HTTP 500 with body exactly {"error": "invalid_model_output"},
as required.

Image size: see results/task3/image_size.txt — well under the 2GB limit (content size ~364MB).

Under --cpus 1 --memory 1g, 50 sequential /parse requests all completed with HTTP 200
(see results/task3/50_requests_status.txt). Peak memory observed was ~565MiB / 1GiB (55%),
no out-of-memory kill (results/task3/peak_memory.txt).

## 4. Kubernetes Deployment, Scaling, and Reliability

Namespace `app`, Deployment, Service and Ingress applied and verified: `/parse` answers
correctly through the Ingress at the mapped port, with the correct `X-Model-Version` and
`X-Served-By` headers (see Task 3 for header format).

Resource requests/limits: cpu 250m/1, memory 512Mi/1Gi per pod. Readiness probe on
`/readyz` gates traffic — confirmed the Service has no ready endpoints while the model
is still downloading.

HPA: min 1, max 2 replicas, target 70% CPU. Observed scaling from 1 to 2 replicas under
Locust load, and back down to 1 when idle (see `kubectl get hpa` output during testing).

**A real bug found and fixed during testing:** the first rolling-update test showed a
99% failure rate under concurrent load, with repeated pod restarts. Investigation showed
the `/parse` handler was `async def` but called `model.generate()` synchronously inside
it — this blocked FastAPI's single event loop during each ~2-3 second generation, so
concurrent requests (including the liveness/readiness probes themselves) queued up and
timed out. Kubernetes then killed pods it believed were unresponsive, triggering a
crash-restart loop that made things worse. Fix: moved the blocking generation call into
a background thread via `asyncio.to_thread`, so health checks keep responding while
`/parse` requests generate. After the fix, pod restarts during load testing dropped to
zero across every subsequent test run.

Rolling update: `MODEL_VERSION`/`MODEL_URI` changed from v1 to v2 while a 2-minute Locust
load test ran (`--users 4 --spawn-rate 4`). Best observed run: 169 requests, 1 failure
(0.59%), 0 pod restarts (`results/task4/real_test_v4_stats.csv`). A later run under
colder conditions (immediately after a cold-start/pod-recovery test) showed a higher
3.70% failure rate (`results/task4/loadbalance_test_stats.csv`) — all failures were clean
HTTP 500s from the service's own output-validation path, not crashes or timeouts,
suggesting the single-CPU-per-pod generation occasionally produces malformed JSON under
concurrent load rather than an infrastructure fault. Rollback via
`kubectl rollout undo` confirmed working: `X-Model-Version` header correctly reverted
to `v1`.

Pod recovery: deleting one pod under the Deployment showed Kubernetes automatically
recreate it, restoring 2/2 Ready within seconds (`results/task4/pod_recovery.txt`).

Cold start: three runs of deleting all pods and timing until Ready gave 6s, 5s, 5s
(median 5s) (`results/task4/cold_start_times.txt`).

Load balancing: with 2 Ready replicas, a 2-minute Locust run through the Ingress split
successful requests 80/76 between the two pods (~51%/49%), both well above the required
30% minimum (`results/task4/loadbalance_test_stats.csv`).

**Limitation:** this cluster runs as a single node on one laptop. It does not demonstrate
fault tolerance across multiple physical machines — a node failure would take down every
pod regardless of replica count, since there is only one underlying host.

## 5. Subnetting and Network Access Control
Subnet table, NACL design, nacl_sim.py score, explanation of statelessness and rule ordering.

## 6. Reproducibility, Testing, and CI/CD
CI stages, link to a run that failed the quality gate, AI_USE.md summary, secret scan result.

## 7. Performance, Cost, and Review
Latency/throughput/error rate/resource/cold-start table, cost calculation worked out step by step, SLO and error budget, review table (evidence / limitation / improvement per row).

## Limitations and improvements