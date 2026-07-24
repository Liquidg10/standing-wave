#!/usr/bin/env python3
"""Fail closed when a Standing Wave build is incomplete or loses subscriptions."""

from __future__ import annotations

import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SITE = ROOT / "site"
MINIMUM_EXPECTED_ISSUES = 41
SUBSCRIBE_MARKER = 'id="standingwave-subscribe"'
LEAD_ENDPOINT = "https://gdcfvscjmnfkfwsjpaxn.supabase.co/functions/v1/musenexus-lead"
CONSENT_VERSION = 'consent_version:"2026-07-18.2"'
TOPIC_MARKER = 'topics:["standingwave.new-issue"]'
EXPLICIT_CONSENT = "Email me new issues of The Standing Wave. I can unsubscribe at any time."
LAB_HUB_LINK = 'href="https://musenexus.studio/labs"'


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def read(path: Path) -> str:
    if not path.is_file():
        fail(f"missing {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


source_paths = sorted((ROOT / "issues").glob("no-*.md"))
source_numbers = []
source_slugs = {}
for path in source_paths:
    source = read(path)
    match = re.search(r"^number:\s*(\d+)\s*$", source, re.MULTILINE)
    slug_match = re.search(r"^slug:\s*([^\s]+)\s*$", source, re.MULTILINE)
    if not match or not slug_match:
        fail(f"missing issue number in {path.relative_to(ROOT)}")
    number = int(match.group(1))
    source_numbers.append(number)
    source_slugs[number] = slug_match.group(1)

if len(source_numbers) < MINIMUM_EXPECTED_ISSUES:
    fail(
        f"only {len(source_numbers)} source issues; refusing to deploy below "
        f"the known production floor of {MINIMUM_EXPECTED_ISSUES}"
    )
if len(set(source_numbers)) != len(source_numbers):
    fail("duplicate source issue numbers")
if sorted(source_numbers) != list(range(1, max(source_numbers) + 1)):
    fail("source issue numbers are not contiguous from 1")

issue_pages = sorted((SITE / "issues").glob("*.html"))
if len(issue_pages) != len(source_numbers):
    fail(f"{len(issue_pages)} generated issue pages != {len(source_numbers)} sources")

rss_root = ET.fromstring(read(SITE / "feed.xml"))
rss_items = rss_root.findall("./channel/item")
if len(rss_items) != len(source_numbers):
    fail(f"RSS has {len(rss_items)} items != {len(source_numbers)} sources")

json_feed = json.loads(read(SITE / "feed.json"))
json_items = json_feed.get("items", [])
if len(json_items) != len(source_numbers):
    fail(f"JSON Feed has {len(json_items)} items != {len(source_numbers)} sources")

sitemap_root = ET.fromstring(read(SITE / "sitemap.xml"))
sitemap_urls = {
    node.text
    for node in sitemap_root.findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}loc")
    if node.text
}
for number, slug in source_slugs.items():
    expected = f"https://standingwave.ink/issues/{slug}"
    if expected not in sitemap_urls:
        fail(f"sitemap is missing {expected}")

reader_pages = [
    SITE / "index.html",
    SITE / "start.html",
    SITE / "about.html",
    SITE / "topics.html",
    SITE / "404.html",
    *issue_pages,
]
for path in reader_pages:
    page = read(path)
    if page.count(SUBSCRIBE_MARKER) != 1:
        fail(f"{path.relative_to(ROOT)} must contain exactly one subscription form")
    for marker in (
        LEAD_ENDPOINT,
        'site:"standingwave"',
        'interest:"updates"',
        TOPIC_MARKER,
        CONSENT_VERSION,
        EXPLICIT_CONSENT,
        "page:window.location.pathname",
        'href="/feed.xml"',
        'href="/feed.json"',
        LAB_HUB_LINK,
    ):
        if marker not in page:
            fail(f"{path.relative_to(ROOT)} is missing subscription marker {marker}")

homepage = read(SITE / "index.html")
newest = max(source_numbers)
if f'href="/issues/{source_slugs[newest]}"' not in homepage:
    fail(f"homepage does not link to newest issue No. {newest}")
if 'href="https://thoughttoys.com/#subscribe"' not in homepage:
    fail("homepage lost the Thought Toys cross-publication link")

print(
    "PASS: Standing Wave release is complete — "
    f"{len(source_numbers)} issues, matching RSS/JSON feeds, sitemap, and "
    f"subscription contracts across {len(reader_pages)} reader pages."
)
