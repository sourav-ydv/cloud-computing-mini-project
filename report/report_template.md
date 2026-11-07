# Cloud Computing Mini Project — Report

Name:
Roll number:
GitHub repo:

## 1. Object Storage and Parallel Teacher Labelling
Architecture, sharding explanation (half page max), counts table (input, rejected a-d, duplicates, kept).

## 2. Training the Student
config.yaml summary, loss curve, model artefact locations and checksums, score.py results table for teacher / untrained pythia-70m / trained student, sequence-level vs logit-based distillation explanation (one page max).

## 3. The Inference Service in a Container
Endpoint behaviour, FAULT_INJECT test evidence, image size, peak memory under 1 CPU / 1 GiB for 50 requests.

## 4. Kubernetes Deployment, Scaling, and Reliability
Deployment/Service/Ingress evidence, HPA scale-up/down evidence, rolling update and rollback evidence, Pod recovery evidence, cold-start median of three runs, load-balancing split between replicas, limitation of a single-node cluster.

## 5. Subnetting and Network Access Control
Subnet table, NACL design, nacl_sim.py score, explanation of statelessness and rule ordering.

## 6. Reproducibility, Testing, and CI/CD
CI stages, link to a run that failed the quality gate, AI_USE.md summary, secret scan result.

## 7. Performance, Cost, and Review
Latency/throughput/error rate/resource/cold-start table, cost calculation worked out step by step, SLO and error budget, review table (evidence / limitation / improvement per row).

## Limitations and improvements
