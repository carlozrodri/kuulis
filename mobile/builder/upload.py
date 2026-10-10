"""Uploads the APK to S3 (also as the "latest" key) and prints a 7-day download link for each."""

import os
import sys

import boto3
from botocore.config import Config

path, key, latest = sys.argv[1], sys.argv[2], sys.argv[3]
bucket = os.environ["AWS_S3_BUCKET"]
s3 = boto3.client(
    "s3",
    endpoint_url=os.environ["AWS_S3_ENDPOINT"],
    aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
    aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
    region_name=os.environ.get("AWS_S3_REGION", "us-east-1"),
    config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
)
for target in (key, latest):
    s3.upload_file(
        path,
        bucket,
        target,
        ExtraArgs={
            "ContentType": "application/vnd.android.package-archive",
            "ContentDisposition": f'attachment; filename="{target.rsplit("/", 1)[-1]}"',
        },
    )
    url = s3.generate_presigned_url(
        "get_object", Params={"Bucket": bucket, "Key": target}, ExpiresIn=7 * 24 * 3600
    )
    print(f"Uploaded s3://{bucket}/{target}\n{url}")
