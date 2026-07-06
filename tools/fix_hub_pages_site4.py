from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOMAIN = "https://xn--ol5ba64b839b.com"
ALTERNATE_NAMES = ["와와학습코칭학원", "와와학습코칭센터", "와와학원", "와와학원.com"]

HUB_FILES = [
    ROOT / "index.html",
    ROOT / "학습코칭" / "index.html",
    ROOT / "상담문의" / "index.html",
    ROOT / "전국센터" / "index.html",
    ROOT / "전국센터" / "수학학원" / "index.html",
    ROOT / "전국센터" / "영어학원" / "index.html",
    ROOT / "전국센터" / "영수학원" / "index.html",
    ROOT / "전국센터" / "초등학생학원" / "index.html",
    ROOT / "전국센터" / "중학생학원" / "index.html",
    ROOT / "전국센터" / "고등학생학원" / "index.html",
]

URL_KEY_PATTERN = re.compile(r'"(@id|url|item|image|og:image)":"(/[^"]*)"')


def absolutize_jsonld_urls(jsonld_text: str) -> str:
    def repl(m: re.Match) -> str:
        key, value = m.group(1), m.group(2)
        return f'"{key}":"{DOMAIN}{value}"'

    return URL_KEY_PATTERN.sub(repl, jsonld_text)


def fix_page(path: Path) -> bool:
    source = path.read_text(encoding="utf-8", errors="ignore")
    updated = source

    # canonical: relative -> absolute
    canon_m = re.search(r'<link rel="canonical" href="([^"]*)">', updated)
    rel_path = canon_m.group(1)
    abs_canon = DOMAIN + rel_path
    updated = updated.replace(f'<link rel="canonical" href="{rel_path}">', f'<link rel="canonical" href="{abs_canon}">')

    # og:image: relative -> absolute
    updated = re.sub(
        r'(<meta property="og:image" content=")(/[^"]*)(")',
        lambda m: m.group(1) + DOMAIN + m.group(2) + m.group(3),
        updated,
    )

    # og:url: add if missing, right after og:title (or og:type as fallback)
    if 'property="og:url"' not in updated:
        anchor_m = re.search(r'<meta property="og:title"[^>]*>', updated)
        if anchor_m:
            og_url_tag = f'\n  <meta property="og:url" content="{abs_canon}">'
            updated = updated[: anchor_m.end()] + og_url_tag + updated[anchor_m.end():]

    # JSON-LD: absolutize @id/url/item/image string values, add alternateName to root org
    m = re.search(r'(<script type="application/ld\+json">)(.*?)(</script>)', updated, re.S)
    jsonld_text = m.group(2)
    jsonld_text = absolutize_jsonld_urls(jsonld_text)

    data = json.loads(jsonld_text)
    for node in data.get("@graph", []):
        if not isinstance(node, dict):
            continue
        t = node.get("@type")
        types = t if isinstance(t, list) else [t]
        if "EducationalOrganization" in types and "alternateName" not in node:
            node["alternateName"] = list(ALTERNATE_NAMES)
    jsonld_text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))

    updated = updated[: m.start()] + m.group(1) + jsonld_text + m.group(3) + updated[m.end():]

    if updated != source:
        path.write_text(updated, encoding="utf-8")
        return True
    return False


def main() -> None:
    changed = 0
    for f in HUB_FILES:
        if fix_page(f):
            changed += 1
            print(f"fixed: {f.relative_to(ROOT)}")
    print(f"total={len(HUB_FILES)} changed={changed}")


if __name__ == "__main__":
    main()
