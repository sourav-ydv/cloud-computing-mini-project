# Cloud Computing Mini Project — Report

Name: Sourav Yadav
Roll number: 230101043
GitHub repo: https://github.com/sourav-ydv/cloud-computing-mini-project

## 1. Object Storage and Parallel Teacher Labelling

Cluster created from `cluster/k3d.yaml`, SeaweedFS deployed in namespace `data`, with
`datasets` and `models` buckets. `commands_pool.jsonl` uploaded to `datasets`. Teacher
prompt in `prompts/teacher_prompt.txt`.

Sharding: `worker/labeler.py` reads `SHARD_INDEX` and `SHARD_COUNT` from the environment
and takes every command whose line number (0-indexed) satisfies
`line_number % SHARD_COUNT == SHARD_INDEX`, so two workers with `SHARD_COUNT=2` and
`SHARD_INDEX=0`/`1` between them cover every command exactly once with no gaps or
repeats (verified: 3000 unique ids across both shard outputs, 0 duplicates). Each worker
writes its own object (`datasets/teacher/shard-0.jsonl`, `shard-1.jsonl`) and checkpoints
every 25 records so progress survives an interruption. Both workers were run with
different `SHARD_INDEX` values at the same time to demonstrate parallelism, then run to
completion afterward (CPU-bound local inference made true full-length parallel execution
impractical on available hardware — see Limitations).

Counts from `worker/clean.py` on the combined shard outputs:

| Reason | Count |
|---|---|
| Input records | 3000 |
| Rejected: not valid JSON (a) | 5 |
| Rejected: wrong keys (b) | 15 |
| Rejected: bad intent (c) | 11 |
| Rejected: bad slot value (d) | 65 |
| Duplicates | 48 |
| Kept | 2856 |

Check: 5 + 15 + 11 + 65 + 48 + 2856 = 3000. Output written to `datasets/v1/train.jsonl`
with checksum in `datasets/v1/train.sha256`.

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

Subnet allocation (see `network/subnets.md` for full working):

| Subnet | Hosts needed | Prefix | Network | Broadcast | Usable range | Usable hosts |
|---|---|---|---|---|---|---|
| app | 1000 | /22 | 10.20.0.0 | 10.20.3.255 | 10.20.0.1–10.20.3.254 | 1022 |
| public | 250 | /24 | 10.20.4.0 | 10.20.4.255 | 10.20.4.1–10.20.4.254 | 254 |
| data | 100 | /25 | 10.20.5.0 | 10.20.5.127 | 10.20.5.1–10.20.5.126 | 126 |
| management | 20 | /27 | 10.20.5.128 | 10.20.5.159 | 10.20.5.129–10.20.5.158 | 30 |

NACL (`network/nacl.json`) checked against `network/packets_sample.jsonl` with
`tools/nacl_sim.py`: 6/6 packets decided correctly (100%).

A stateless NACL has no memory of connections, so inbound and outbound rules must be
written separately for both directions of traffic — a reply to an outbound request is
itself a new inbound packet as far as the device is concerned, and needs its own allow
rule, or it is dropped. Rule order matters for the `198.51.100.0/24` block because NACL
rules are evaluated lowest-number-first with first-match-wins: the deny rule for that
range is given a lower rule number than the allow rules for ports 80/443, so a packet
from that range is denied immediately regardless of which port it targets, before it can
ever reach a later allow rule that would otherwise let it through.

## 6. Reproducibility, Testing, and CI/CD

`make up` builds and deploys the whole system from a fresh clone; `make down` tears it down.

GitHub Actions workflow (`.github/workflows/ci.yml`) runs, in order: lint (ruff) → secret
scan (gitleaks) → unit tests (6 tests, `tests/`) → model evaluation (downloads the
GitHub Release model, runs `score.py`) → quality gate (`score.py --min-validity 95`).

Quality gate demonstrated failing with a deliberately bad model (untrained Pythia-70M):
https://github.com/sourav-ydv/cloud-computing-mini-project/actions/runs/42514219577
— `evaluate` succeeded (it runs regardless of model quality) but `gate` failed, since the
untrained model's JSON validity was far below the 95% threshold.

`AI_USE.md` documents AI tool usage. Gitleaks reports no secrets in the repository.

## 7. Performance, Cost, and Review

Load test: `locust -f tools/locustfile.py --headless --users 4 --spawn-rate 4 --run-time 2m --host http://localhost:8081` (`results/task7/final_loadtest_stats.csv`).

The latest run generated 111 requests. There were 107 successful responses and 4 HTTP 500 failures. Both replicas received successful requests, and both remained available during the test.

| Metric | Value |
|---|---:|
| Total requests | 111 |
| Successful requests | 107 |
| Failed requests | 4 |
| Error rate | 3.60% |
| p50 latency | 5200 ms |
| p95 latency | 7800 ms |
| Throughput | 0.94 requests/s |
| Replica 1 successful requests (`parser-c5588b4cb-vz662`) | 67 (62.6%) |
| Replica 2 successful requests (`parser-c5588b4cb-44pwb`) | 40 (37.4%) |
| Replica 1 peak sampled CPU / memory | 1000m / 593Mi |
| Replica 2 peak sampled CPU / memory | 1007m / 687Mi |
| Cold-start (median of 3) | 5s |

The per-pod measurements were sampled approximately every five seconds during the load test and are recorded in `results/task7/pod_metrics_during_load.txt`. The Locust statistics, failures and request history are retained in `results/task7/final_loadtest_*.csv`.

Both replicas handled more than the required 30% of successful requests. However, the measured p95 latency of 7800 ms exceeded the 5000 ms performance target, and the 3.60% error rate exceeded the 1% error-rate target. The four failures were HTTP 500 responses from the service's output-validation path. The sampled memory usage remained below the 1Gi pod limit; CPU usage reached approximately one core on both replicas, indicating that CPU capacity was a significant constraint during this run.

### Cost

The rate card is hypothetical and is used only for this assignment's cost-estimation exercise.

Each replica is billed for its CPU and memory limits for every hour it runs:

    hourly cost per replica = (1 vCPU x Rs 3.50/vCPU-hr) + (1 GiB x Rs 0.45/GiB-hr)
                             = Rs 3.50 + Rs 0.45 = Rs 3.95/hour

    hourly cost, 2 replicas = 2 x Rs 3.95 = Rs 7.90/hour

Using 107 successful requests over the 120-second test window:

    successful requests per hour = (107 / 120) x 3600
                                  = 3210 requests/hour

    cost per 1000 successful requests = (Rs 7.90 / 3210) x 1000
                                      = approximately Rs 2.46

This is an extrapolated estimate based on the two-replica hourly rate and the observed successful-request throughput, not an actual cloud bill.

### SLO and error budget

The project's stated SLO is 95% successful requests, equivalent to a maximum 5% error rate. For this run of 111 requests, the theoretical error budget was 5.55 failures (approximately 5 whole requests when expressed as an integer allowance).

Observed failures: 4. This represents approximately 72.1% of the theoretical error budget, or 80% of the five-failure whole-request allowance. The run therefore remained within the stated 95% success SLO.

The separate performance target of at most 1% errors was not met: the observed error rate was 3.60%. The p95 latency target of 5000 ms was also not met.

### Review

| Component | Evidence (measured) | Limitation found | Improvement proposed |
|---|---|---|---|
| Data and storage | 2856/3000 records kept after cleaning (95.2% yield) | NodePort used instead of port-forward after repeated connection drops during large transfers | Use persistent-volume-backed SeaweedFS with retry-aware clients |
| Model quality | Student full-frame 40% vs teacher 46% (87% of teacher) | Student occasionally echoes its own prompt label (`JSON:`) before output | More training data or epochs; improve prompt/completion boundary formatting |
| Latency and throughput | p50 5200ms, p95 7800ms, 0.94 requests/s | p95 exceeded 5000ms; CPU approached one core per pod | Increase CPU capacity, optimize generation, or batch requests |
| Resource utilisation | Sampled peak CPU 1000m and 1007m; memory 593Mi and 687Mi | CPU approached the per-pod limit under concurrent load | Profile inference and increase CPU allocation if available |
| Reliability and recovery | Both replicas served traffic; 4 HTTP 500 responses in 111 requests | Error rate 3.60% exceeded the 1% performance target | Improve output validation and generation robustness under concurrency |
| Security and cost | Approximately Rs 2.46 per 1000 successful requests using the hypothetical rate card; gitleaks reports no secrets in repo | Local object-storage credentials are not representative of production access control | Use scoped credentials and TLS in a production deployment |

## Limitations and improvements

- **Single-node cluster**: the entire deployment runs on one laptop as one node. This
  does not demonstrate fault tolerance across multiple physical machines — a hardware
  failure takes down every pod regardless of replica count.
- **CPU-only inference**: both the teacher labelling (Ollama/phi3.5) and the student
  training/serving ran on CPU (teacher was GPU-accelerated via Ollama automatically on
  an RTX 3050; student training and the deployed service ran CPU-only per the
  assignment's spec). This capped throughput and made concurrent request handling the
  main scaling bottleneck (Task 7).
- **Network reliability**: `kubectl port-forward` proved unreliable for the ~281MB model
  transfer after a WiFi network change; SeaweedFS was switched to a NodePort Service for
  a stable connection, documented in the Task 1/3 commits.
- **A real concurrency bug was found and fixed during testing**: the inference service's
  `/parse` handler initially blocked FastAPI's event loop during generation, causing
  health-check failures and pod crash-loops under load. Fixed by moving generation into
  a background thread (`asyncio.to_thread`). Full detail in Task 4.
- **Improvement for future work**: logit-based distillation (matching the teacher's full
  probability distribution rather than just its chosen text) would likely close more of
  the gap between the teacher's 46% and the student's 40% full-frame accuracy, but needs
  a teacher that exposes logits — Ollama's API does not.