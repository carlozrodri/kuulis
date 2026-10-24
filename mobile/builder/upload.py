"""Uploads the APK to S3 (also as the "latest" key) with a metadata file the API reads (doc 09), and
prints a 7-day download link for each.

Usage: upload.py <apk> <key> <latest key> <profile> [runtime version]
       upload.py --bundle <aab> <key>   (Google Play bundle: uploaded as is, with no metadata)
The metadata (<key without .apk>.json) has the version, build number (versionCode), size, SHA-256,
MD5 and runtime version; the admin publishes a build to a channel from it, the app checks the MD5
before installing, and the compiler sends JS updates instead of a new APK while the runtime version
(native code fingerprint) stays the same.
"""

import hashlib
import json
import os
import re
import subprocess
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import boto3
from botocore.config import Config

bucket = os.environ["AWS_S3_BUCKET"]
s3 = boto3.client(
    "s3",
    endpoint_url=os.environ["AWS_S3_ENDPOINT"],
    aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
    aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
    region_name=os.environ.get("AWS_S3_REGION", "us-east-1"),
    config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
)


def upload(path: str, target: str, content_type: str) -> None:
    s3.upload_file(
        path,
        bucket,
        target,
        ExtraArgs={
            "ContentType": content_type,
            "ContentDisposition": f'attachment; filename="{target.rsplit("/", 1)[-1]}"',
        },
    )
    url = s3.generate_presigned_url(
        "get_object", Params={"Bucket": bucket, "Key": target}, ExpiresIn=7 * 24 * 3600
    )
    print(f"Uploaded s3://{bucket}/{target}\n{url}")


if sys.argv[1] == "--bundle":
    upload(sys.argv[2], sys.argv[3], "application/octet-stream")
    sys.exit(0)

path, key, latest, profile = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
expected_runtime = sys.argv[5] if len(sys.argv) > 5 else None


def aapt2(*args: str) -> str:
    """Runs aapt2 (it ships with the build tools)."""
    tools = Path(os.environ["ANDROID_HOME"], "build-tools")
    binary = sorted(tools.glob("*/aapt2"))[-1]
    return subprocess.run([str(binary), *args], capture_output=True, text=True, check=True).stdout


def apk_runtime(apk: str) -> str | None:
    """The expo-updates runtime version compiled into the APK (string resource), if found."""
    try:
        resources = aapt2("dump", "resources", apk)
    except subprocess.CalledProcessError:
        return None
    match = re.search(r'string/expo_runtime_version[^\n]*\n\s*\([^)]*\)\s*"([^"]+)"', resources)
    if not match:
        return None
    value = match.group(1)
    if value.startswith("file:"):  # the fingerprint policy stores it in an asset: "file:fingerprint"
        with zipfile.ZipFile(apk) as archive:
            value = archive.read(f"assets/{value.removeprefix('file:')}").decode().strip()
    return value


def apk_version(apk: str) -> tuple[str, int]:
    """versionName and versionCode from the APK manifest."""
    badging = aapt2("dump", "badging", apk)
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
runtime = apk_runtime(path)
if runtime and expected_runtime and runtime != expected_runtime:
    print(f"Warning: the APK has runtime {runtime}, the source resolved {expected_runtime}")
runtime = runtime or expected_runtime
meta = {
    "file_name": key.rsplit("/", 1)[-1],
    "version": version,
    "build": build,
    "size": os.path.getsize(path),
    "sha256": sha256,
    "md5": md5,
    "profile": profile,
    # What the APK accepts, and what the source resolved to (the compiler matches on the latter).
    "runtime_version": runtime,
    "source_runtime": expected_runtime,
    "commit": os.environ.get("SOURCE_COMMIT") or None,
    "built_at": datetime.now(UTC).isoformat(),
}

for target in (key, latest):
    upload(path, target, "application/vnd.android.package-archive")

# Written last: the admin only lists builds whose APK is already in place.
s3.put_object(
    Bucket=bucket,
    Key=key.removesuffix(".apk") + ".json",
    Body=json.dumps(meta).encode(),
    ContentType="application/json",
)
print(f"Version {version} (build {build}), runtime {runtime}, SHA-256 {sha256}")
