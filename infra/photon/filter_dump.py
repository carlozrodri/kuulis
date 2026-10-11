"""Merges Photon dump files into one stream for `photon import`, keeping only the places we serve.

Usage: filter_dump.py FILE=FILTER [FILE=FILTER ...] > merged.jsonl
FILTER is a comma-separated list of country codes ("ve") or "bbox:minLng,minLat,maxLng,maxLat".

The header and country names come from the first file; places keep the files' order (each dump is
sorted by country, so the merged stream stays grouped by country).
"""

import io
import re
import sys

import zstandard

COUNTRY = re.compile(r'"country_code":"([a-z]{2})"')
CENTROID = re.compile(r'"centroid":\[(-?[\d.]+(?:e-?\d+)?),(-?[\d.]+(?:e-?\d+)?)\]')


def matcher(spec: str):
    if spec.startswith("bbox:"):
        min_lng, min_lat, max_lng, max_lat = (float(v) for v in spec[5:].split(","))

        def in_box(line: str) -> bool:
            found = CENTROID.search(line)
            if not found:
                return False
            lng, lat = float(found.group(1)), float(found.group(2))
            return min_lng <= lng <= max_lng and min_lat <= lat <= max_lat

        return in_box
    codes = {c.strip().lower() for c in spec.split(",") if c.strip()}

    def in_countries(line: str) -> bool:
        found = COUNTRY.search(line)
        return bool(found and found.group(1) in codes)

    return in_countries


def main(args: list[str]) -> int:
    out = sys.stdout
    for index, arg in enumerate(args):
        path, spec = arg.split("=", 1)
        keep = matcher(spec)
        kept = 0
        with open(path, "rb") as raw:
            reader = io.TextIOWrapper(zstandard.ZstdDecompressor().stream_reader(raw), "utf-8")
            for line in reader:
                if not line.strip():
                    continue
                if '"type":"Place"' not in line[:40]:
                    if index == 0:  # header and country names, once
                        out.write(line)
                    continue
                if keep(line):
                    out.write(line)
                    kept += 1
        print(f"{path}: kept {kept} places ({spec})", file=sys.stderr)
    out.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
