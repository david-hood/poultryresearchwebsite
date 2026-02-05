#!/usr/bin/env python3
"""
Download images used by https://poultryresearchtrialservices.ca/.

Requirements:
1) Load the homepage HTML.
2) Extract:
   - all <img> tag src attributes
   - all url(...) references from linked CSS files
   - any images in /build/assets/ or /img/ or /images/ directories on the same domain
3) Follow relative URLs correctly.
4) Download files with extensions: jpg, jpeg, png, webp, svg.
5) Save each file under its basename (last path segment) without renaming/hashing.
6) Output directory: downloaded_images
7) Handle duplicates by appending __2, __3, etc.
8) Print a summary of how many files were saved.
"""

import re
from pathlib import Path
from urllib.parse import urljoin, urlparse, unquote

import requests
from bs4 import BeautifulSoup


BASE_URL = "https://poultryresearchtrialservices.ca/"
OUTPUT_DIR = Path("downloaded_images")
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".svg")


def dedupe_path(path: Path) -> Path:
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


def is_image_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.path.lower().endswith(IMAGE_EXTENSIONS)


def filename_from_url(url: str) -> str:
    parsed = urlparse(url)
    name = Path(unquote(parsed.path)).name
    return name or "image"


def extract_css_urls(css_text: str, base_url: str) -> set[str]:
    urls = set()
    for match in re.findall(r"url\\(([^)]+)\\)", css_text, flags=re.IGNORECASE):
        raw = match.strip().strip("\"'").split()[0]
        if raw.startswith("data:"):
            continue
        full = urljoin(base_url, raw)
        urls.add(full)
    return urls


def extract_image_urls_from_html(html_text: str, base_url: str) -> tuple[set[str], set[str]]:
    soup = BeautifulSoup(html_text, "html.parser")
    image_urls = set()
    css_urls = set()

    for img in soup.find_all("img"):
        src = img.get("src")
        if src:
            image_urls.add(urljoin(base_url, src))

    for link in soup.find_all("link", rel=lambda value: value and "stylesheet" in value):
        href = link.get("href")
        if href:
            css_urls.add(urljoin(base_url, href))

    return image_urls, css_urls


def extract_directory_images(html_text: str, base_url: str) -> set[str]:
    domain = urlparse(base_url).netloc
    directory_pattern = re.compile(
        r"""(?i)\b(?:/build/assets/|/img/|/images/)[^"'\\s)]+"""
    )
    urls = set()
    for match in directory_pattern.findall(html_text):
        full = urljoin(base_url, match)
        if urlparse(full).netloc == domain:
            urls.add(full)
    return urls


def download(url: str, session: requests.Session) -> Path | None:
    if not is_image_url(url):
        return None

    try:
        response = session.get(url, timeout=20)
    except requests.RequestException:
        return None

    if response.status_code != 200:
        return None

    filename = filename_from_url(url)
    target = dedupe_path(OUTPUT_DIR / filename)
    target.write_bytes(response.content)
    return target


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})

    homepage = session.get(BASE_URL, timeout=20)
    homepage.raise_for_status()

    image_urls, css_urls = extract_image_urls_from_html(homepage.text, BASE_URL)
    image_urls.update(extract_directory_images(homepage.text, BASE_URL))

    css_image_urls = set()
    for css_url in css_urls:
        try:
            css_response = session.get(css_url, timeout=20)
            if css_response.status_code == 200:
                css_image_urls.update(extract_css_urls(css_response.text, css_url))
        except requests.RequestException:
            continue

    image_urls.update(css_image_urls)

    saved = 0
    for url in sorted(image_urls):
        result = download(url, session)
        if result is not None:
            saved += 1

    print(f"Saved {saved} file(s) to {OUTPUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
