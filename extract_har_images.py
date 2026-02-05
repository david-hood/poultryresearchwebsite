#!/usr/bin/env python3
"""
Extract image responses from a Chrome DevTools HAR file.

Usage examples:
  python3 extract_har_images.py path/to/session.har -o assets/images
  python3 extract_har_images.py session.har --output ./downloaded_images
"""

import argparse
import base64
import binascii
import json
from pathlib import Path
from urllib.parse import urlparse, unquote


def _dedupe_name(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    counter = 2
    while True:
        candidate = path.with_name(f"{stem}__{counter}{suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def _filename_from_url(url: str) -> str:
    parsed = urlparse(url)
    name = Path(unquote(parsed.path)).name
    return name or "image"


def extract_images(har_path: Path, output_dir: Path) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)
    data = json.loads(har_path.read_text(encoding="utf-8"))
    entries = data.get("log", {}).get("entries", [])
    saved = 0

    for entry in entries:
        response = entry.get("response", {})
        content = response.get("content", {})
        mime_type = content.get("mimeType", "")
        if not mime_type.startswith("image/"):
            continue

        text = content.get("text")
        if not text:
            continue

        encoding = content.get("encoding", "")
        if encoding == "base64":
            try:
                payload = base64.b64decode(text)
            except (ValueError, binascii.Error):
                continue
        else:
            payload = text.encode("utf-8")

        url = entry.get("request", {}).get("url", "")
        filename = _filename_from_url(url)
        target = _dedupe_name(output_dir / filename)
        target.write_bytes(payload)
        saved += 1

    return saved


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract images from a Chrome DevTools HAR (Save all as HAR with content)."
    )
    parser.add_argument("har", type=Path, help="Path to the HAR file.")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("har_images"),
        help="Output folder for extracted images (default: har_images).",
    )
    args = parser.parse_args()

    if not args.har.exists():
        raise SystemExit(f"HAR file not found: {args.har}")

    saved = extract_images(args.har, args.output)
    print(f"Saved {saved} image(s) to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
