"""JS updates (OTA, doc 09) for the compiler.

Usage:
  ota.py has-apk <runtime>                      when an APK built from this native code is in S3, prints
                                                the runtime version it accepts (exit 0); else exit 1
  ota.py upload <export dir> <runtime> <source>  uploads an `expo export` as an update candidate

Each file goes to updates/<APP_ENV>/assets/<sha256> once (updates share most files); the candidate
JSON (updates/<APP_ENV>/candidates/<date>-<source>.json) lists them with the hashes the app checks and
is written last, so the admin never lists a candidate whose files are missing. The API signs and serves
the manifest when a candidate is published from the admin.
"""

import base64
import hashlib
import json
import mimetypes
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

APP_ENV = os.environ.get("APP_ENV", "qa")
BUCKET = os.environ["AWS_S3_BUCKET"]
s3 = boto3.client(
    "s3",
    endpoint_url=os.environ["AWS_S3_ENDPOINT"],
    aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
    aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
    region_name=os.environ.get("AWS_S3_REGION", "us-east-1"),
    config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
)


def apk_runtime(runtime: str) -> str | None:
    """The runtime version of an APK the compiler built from this native code, if any.

    Matched on the runtime the source resolved to before the build; the APK's own value is what
    its updates must carry (they are the same unless the fingerprint differs inside the build)."""
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=BUCKET, Prefix=f"builds/{APP_ENV}/"):
        for obj in page.get("Contents", []):
            if not obj["Key"].endswith(".json"):
                continue
            meta = json.loads(s3.get_object(Bucket=BUCKET, Key=obj["Key"])["Body"].read())
            if runtime in (meta.get("source_runtime"), meta.get("runtime_version")):
                print(f"APK {meta.get('file_name')} was built from runtime {runtime}", file=sys.stderr)
                return meta.get("runtime_version") or runtime
    return None


def _exists(key: str) -> bool:
    try:
        s3.head_object(Bucket=BUCKET, Key=key)
        return True
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") in ("404", "NoSuchKey", "NotFound"):
            return False
        raise


def _upload_asset(path: Path, content_type: str, ext: str | None) -> dict:
    data = path.read_bytes()
    sha256 = hashlib.sha256(data)
    key = f"updates/{APP_ENV}/assets/{sha256.hexdigest()}"
    if not _exists(key):
        s3.put_object(
            Bucket=BUCKET,
            Key=key,
            Body=data,
            ContentType=content_type,
            CacheControl="public, max-age=31536000, immutable",
        )
    return {
        "s3_key": key,
        "hash": base64.urlsafe_b64encode(sha256.digest()).decode().rstrip("="),
        "key": hashlib.md5(data).hexdigest(),  # noqa: S324 (the asset name the bundle uses)
        "contentType": content_type,
        "fileExtension": f".{ext}" if ext else None,
    }


def upload(export_dir: str, runtime: str, source: str) -> None:
    root = Path(export_dir)
    metadata = json.loads((root / "metadata.json").read_text())["fileMetadata"]["android"]
    expo_config = json.loads((root / "expoConfig.json").read_text())
    bundle = root / metadata["bundle"]
    launch = _upload_asset(bundle, "application/javascript", None)
    launch.pop("fileExtension")
    assets = []
    for item in metadata["assets"]:
        ext = item.get("ext")
        content_type = mimetypes.guess_type(f"x.{ext}")[0] if ext else None
        assets.append(_upload_asset(root / item["path"], content_type or "application/octet-stream", ext))
    now = datetime.now(UTC)
    candidate = {
        "platform": "android",
        "runtime_version": runtime,
        "commit": os.environ.get("SOURCE_COMMIT") or None,
        "message": os.environ.get("UPDATE_MESSAGE") or None,
        "built_at": now.isoformat(),
        "bundle_size": bundle.stat().st_size,
        "launch_asset": launch,
        "assets": assets,
        # Constants.expoConfig in the app comes from here after an update (API URL, EAS project id...).
        "extra": {"expoClient": expo_config},
    }
    key = f"updates/{APP_ENV}/candidates/{now:%Y%m%d-%H%M%S}-{source}.json"
    s3.put_object(
        Bucket=BUCKET, Key=key, Body=json.dumps(candidate).encode(), ContentType="application/json"
    )
    print(f"Update candidate {key}: runtime {runtime}, {len(assets) + 1} files")


if __name__ == "__main__":
    command = sys.argv[1]
    if command == "has-apk":
        found = apk_runtime(sys.argv[2])
        if found is None:
            sys.exit(1)
        print(found)
    elif command == "upload":
        upload(sys.argv[2], sys.argv[3], sys.argv[4])
    else:
        raise SystemExit(__doc__)
