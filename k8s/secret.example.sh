kubectl create namespace app --dry-run=client -o yaml | kubectl apply -f -

kubectl create secret generic s3-credentials \
  --namespace app \
  --from-literal=access-key="$S3_ACCESS_KEY" \
  --from-literal=secret-key="$S3_SECRET_KEY" \
  --dry-run=client -o yaml | kubectl apply -f -
