import hashlib
import os
import sys

import boto3

MODEL_DIR = sys.argv[1]
DEST_PREFIX = sys.argv[2]

s3 = boto3.client(
    "s3",
    endpoint_url=os.environ["S3_ENDPOINT"],
    aws_access_key_id=os.environ["S3_ACCESS_KEY"],
    aws_secret_access_key=os.environ["S3_SECRET_KEY"],
)

digest = hashlib.sha256()
for name in sorted(os.listdir(MODEL_DIR)):
    path = os.path.join(MODEL_DIR, name)
    if not os.path.isfile(path):
        continue
    with open(path, "rb") as f:
        data = f.read()
    digest.update(data)
    s3.put_object(Bucket="models", Key=f"{DEST_PREFIX}/{name}", Body=data)
    print(f"uploaded {DEST_PREFIX}/{name}")

checksum_key = f"{DEST_PREFIX}/model.sha256"
s3.put_object(Bucket="models", Key=checksum_key, Body=digest.hexdigest().encode("utf-8"))
print(f"checksum {digest.hexdigest()} written to {checksum_key}")
