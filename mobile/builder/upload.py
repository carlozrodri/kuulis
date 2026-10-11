"""Uploads the APK to S3 (also as the "latest" key) with a metadata file the API reads (doc 09), and
prints a 7-day download link for each.

Usage: upload.py <apk> <key> <latest key> <profile>
The metadata (<key without .apk>.json) has the version, build number (versionCode), size, SHA-256 and
MD5; the admin publishes a build to a channel from it, and the app checks the MD5 before installing.
"""

import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import boto3
from botocore.config import Config

path, key, latest, profile = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
bucket = os.environ["AWS_S3_BUCKET"]
s3 = boto3.client(
    "s3",
    endpoint_url=os.environ["AWS_S3_ENDPOINT"],
    aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
    aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
    region_name=os.environ.get("AWS_S3_REGION", "us-east-1"),
    config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
)


def apk_version(apk: str) -> tuple[str, int]:
    """versionName and versionCode from the APK manifest (aapt2 ships with the build tools)."""
    tools = Path(os.environ["ANDROID_HOME"], "build-tools")
    aapt2 = sorted(tools.glob("*/aapt2"))[-1]
    badging = subprocess.run(
        [str(aapt2), "dump", "badging", apk], capture_output=True, text=True, check=True
    ).stdout
    match = re.search(r"versionCode='(\d+)' versionName='([^']*)'", badging)
    if not match:
        raise SystemExit("Could not read the APK version")
    return match.group(2), int(match.group(1))


def hashes(apk: str) -> tuple[str, str]:
    sha256, md5 = hashlib.sha256(), hashlib.md5()  # noqa: S324 (md5 is a download check, not security)
    with open(apk, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            sha256.update(chunk)
            md5.update(chunk)
    return sha256.hexdigest(), md5.hexdigest()


version, build = apk_version(path)
sha256, md5 = hashes(path)
meta = {
    "file_name": key.rsplit("/", 1)[-1],
    "version": version,
    "build": build,
    "size": os.path.getsize(path),
    "sha256": sha256,
    "md5": md5,
    "profile": profile,
    "commit": os.environ.get("SOURCE_COMMIT") or None,
    "built_at": datetime.now(UTC).isoformat(),
}

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

# Written last: the admin only lists builds whose APK is already in place.
s3.put_object(
    Bucket=bucket,
    Key=key.removesuffix(".apk") + ".json",
    Body=json.dumps(meta).encode(),
    ContentType="application/json",
)
print(f"Version {version} (build {build}), SHA-256 {sha256}")
