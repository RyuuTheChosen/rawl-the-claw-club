#!/usr/bin/env python3
"""Upload the SF2 ROM to S3 for Railway worker auto-provisioning.

Usage (local MinIO):
    python scripts/upload_rom.py /path/to/rom.md

Usage (production — via Railway env):
    railway run python scripts/upload_rom.py /path/to/rom.md
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

S3_KEY = "roms/sf2ce-genesis/rom.md"


def main() -> None:
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <path-to-rom.md>")
        sys.exit(1)

    rom_path = sys.argv[1]
    if not os.path.exists(rom_path):
        print(f"File not found: {rom_path}")
        sys.exit(1)

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

    size = os.path.getsize(rom_path)
    print(f"Uploading {rom_path} ({size:,} bytes) -> s3://{S3_BUCKET}/{S3_KEY}")
    client.upload_file(rom_path, S3_BUCKET, S3_KEY)
    print("Done.")


if __name__ == "__main__":
    main()
