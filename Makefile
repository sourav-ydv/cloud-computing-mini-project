.PHONY: up down train deploy test

up:
	k3d cluster create --config cluster/k3d.yaml
	docker build -t parser:v1 service
	k3d image import parser:v1 -c cloudmp
	kubectl apply -f k8s/seaweedfs.yaml
	bash k8s/secret.example.sh
	kubectl apply -f k8s/namespace.yaml -f k8s/deployment.yaml -f k8s/service.yaml -f k8s/ingress.yaml -f k8s/hpa.yaml

down:
	k3d cluster delete cloudmp

train:
	python training/train.py --data datasets/v1/train.jsonl --config training/config.yaml --out models/v1 --subset $(if $(SUBSET),$(SUBSET),1500)

test:
	python -m pytest tests -q
