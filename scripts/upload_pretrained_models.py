#!/usr/bin/env python3
"""Upload pretrained baseline models to S3/MinIO.

Reads local model files and uploads them to the pretrained/ prefix in S3,
separate from the reference/ prefix used for calibration bots.

Usage:
    python scripts/upload_pretrained_models.py
"""
from __future__ import annotations

import os
import sys

import boto3

S3_ENDPOINT = os.getenv("S3_ENDPOINT", "http://localhost:9000")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY", "minioadmin")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY", "minioadmin")
S3_BUCKET = os.getenv("S3_BUCKET", "rawl-replays")
S3_REGION = os.getenv("S3_REGION", "us-east-1")

# Map of local file paths to S3 destination keys
MODELS = {
    "models/pretrained/linyiLYi_2500k.zip": "pretrained/sf2ce/linyiLYi_2500k.zip",
    "models/pretrained/thuongmhh_discrete15.zip": "pretrained/sf2ce/thuongmhh_discrete15.zip",
}


def main() -> None:
    client = boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=S3_ACCESS_KEY,
        aws_secret_access_key=S3_SECRET_KEY,
        region_name=S3_REGION,
    )

    # Ensure bucket exists
    try:
        client.head_bucket(Bucket=S3_BUCKET)
    except Exception:
        client.create_bucket(Bucket=S3_BUCKET)
        print(f"Created bucket: {S3_BUCKET}")

    for local_path, s3_key in MODELS.items():
        if not os.path.exists(local_path):
            print(f"SKIP  {local_path} — file not found")
            continue

        size = os.path.getsize(local_path)
        print(f"Uploading {local_path} ({size:,} bytes) -> s3://{S3_BUCKET}/{s3_key}")
        client.upload_file(local_path, S3_BUCKET, s3_key)
        print(f"  OK")

    print("Done.")


if __name__ == "__main__":
    main()
