from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CENTER_ROOT = ROOT / "전국센터"


def target_files() -> list[Path]:
    return sorted(CENTER_ROOT.glob("*/*/index.html"))


def main() -> None:
    files = target_files()
    parse_errors = 0
    faq_mismatch = 0
    review_mismatch = 0
    rating_bad = 0

    for f in files:
        text = f.read_text(encoding="utf-8", errors="ignore")
        m = re.search(r'<script type="application/ld\+json">(.*?)</script>', text, re.S)
        try:
            data = json.loads(m.group(1))
        except Exception as exc:  # noqa: BLE001
            parse_errors += 1
            print("PARSE ERROR", f, exc)
            continue

        graph = data["@graph"]

        def find(type_name):
            for node in graph:
                t = node.get("@type")
                types = t if isinstance(t, list) else [t]
                if type_name in types:
                    return node
            return None

        faq_node = find("FAQPage")
        faq_section_m = re.search(r'<section id="faq-section".*?</section>', text, re.S)
        visible_q = re.findall(r"<summary>([^<]*)</summary>", faq_section_m.group(0))
        jsonld_q = [q["name"] for q in faq_node["mainEntity"]]
        if visible_q != jsonld_q:
            faq_mismatch += 1
            print("FAQ MISMATCH", f)

        org = find("EducationalOrganization")
        visible_reviews = re.findall(r'<p>(.*?)</p>\s*<span>학부모</span>', text)
        jsonld_reviews = [r["reviewBody"] for r in org["review"]]
        if visible_reviews != jsonld_reviews:
            review_mismatch += 1
            print("REVIEW MISMATCH", f)

        visible_ratings = re.findall(r'aria-label="(\d)점"', text)
        if not (visible_ratings.count("5") == 5 and visible_ratings.count("4") == 1 and len(visible_ratings) == 6):
            rating_bad += 1
            print("RATING BAD", f, visible_ratings)

    print(f"total={len(files)} parse_errors={parse_errors} faq_mismatch={faq_mismatch} review_mismatch={review_mismatch} rating_bad={rating_bad}")


if __name__ == "__main__":
    main()
