# Cloud Computing Mini Project — Command Parser

GitHub repo: https://github.com/sourav-ydv/cloud-computing-mini-project

## Build and deploy

    make up

This creates the k3d cluster, builds and imports the service image, deploys SeaweedFS, and applies the Kubernetes manifests.

## Train

    make train
    make train SUBSET=50

## Test

    make test

## Tear down

    make down

## Layout

    cluster/        k3d cluster config
    prompts/        teacher prompt
    worker/         labelling and cleaning scripts (Task 1)
    training/       config, training script, model upload (Task 2)
    service/        FastAPI inference service and Dockerfile (Task 3)
    k8s/            Kubernetes manifests (Task 4)
    network/        subnetting and NACL (Task 5)
    tools/          score.py, locustfile.py, nacl_sim.py, eval helpers (provided + mine)
    tests/          unit tests
    results/        logs, score reports, load test output (Task 6, 7)
    report/         report.pdf
