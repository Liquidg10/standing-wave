#!/usr/bin/env python3
"""Assert the committed Standing Wave production artifact is safe to deploy."""

from hashlib import sha256
from pathlib import Path
from struct import unpack


ROOT = Path(__file__).resolve().parent
INDEX = ROOT / "site" / "index.html"
BUILDER = ROOT / "build.py"
OG_IMAGE = ROOT / "site" / "og" / "standingwave.png"
EXPECTED_OG_SHA256 = "5f739c22afe7e42efedcbfb3f26c82ec7775b7d75e806a963e70923a9478533c"


html = INDEX.read_text(encoding="utf-8")
builder = BUILDER.read_text(encoding="utf-8")

for tag in (
    '<meta property="og:image:type" content="image/png">',
    '<meta property="og:image:width" content="1200">',
    '<meta property="og:image:height" content="630">',
    '<meta property="og:image:alt" content="The Standing Wave">',
    '<meta name="twitter:image:alt" content="The Standing Wave">',
):
    assert html.count(tag) == 1, f"expected exactly one homepage tag: {tag}"

assert "twitter:image:alt" in builder, "generator would drop twitter:image:alt"

assert html.count('id="standingwave-subscribe"') == 1, "homepage email form missing or duplicated"
for contract in (
    'intent:"newsletter"',
    'site:"standingwave"',
    'interest:"updates"',
    'consent_version:',
    'name="consent"',
    'name="website"',
):
    assert contract in html, f"homepage email contract missing: {contract}"

png = OG_IMAGE.read_bytes()
assert png[:8] == b"\x89PNG\r\n\x1a\n", "standingwave.png is not a PNG"
width, height = unpack(">II", png[16:24])
assert (width, height) == (1200, 630), (width, height)
assert sha256(png).hexdigest() == EXPECTED_OG_SHA256, "OG art bytes changed"

issue_sources = tuple((ROOT / "issues").glob("no-*.md"))
issue_pages = tuple((ROOT / "site" / "issues").glob("*.html"))
assert len(issue_sources) == len(issue_pages) == 27, (
    len(issue_sources),
    len(issue_pages),
)

for page in issue_pages:
    issue_html = page.read_text(encoding="utf-8")
    assert issue_html.count('id="standingwave-subscribe"') == 1, (
        f"issue email form missing or duplicated: {page.name}"
    )

print("Standing Wave production artifact: PASS (27 issues, email capture, exact OG art, complete metadata)")
