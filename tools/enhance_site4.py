from __future__ import annotations

import json
import random
import re
from pathlib import Path
from urllib.parse import quote

from content_banks_site4 import (
    FAQ_SLOT4_BANK,
    FAQ_SLOT6_BANK,
    REVIEW_BANK_4,
    REVIEW_BANK_5,
    pick,
    pick_unique,
    seed_for,
)

ROOT = Path(__file__).resolve().parents[1]
CENTER_ROOT = ROOT / "전국센터"
DOMAIN = "https://xn--ol5ba64b839b.com"
ROOT_ORG_ID = f"{DOMAIN}/#organization"

SUBJECT_MAP = {
    "수학학원": "수학",
    "영어학원": "영어",
    "영수학원": "영어·수학",
    "초등학생학원": "주요 과목",
    "중학생학원": "주요 과목",
    "고등학생학원": "주요 과목",
}

ALTERNATE_NAMES = ["와와학습코칭학원", "와와학습코칭센터", "와와학원", "와와학원.com"]


def target_files() -> list[Path]:
    result = []
    for index in CENTER_ROOT.glob("*/*/index.html"):
        result.append(index.parent)
    return sorted(result)


def type_names(node) -> list[str]:
    t = node.get("@type")
    if isinstance(t, list):
        return t
    return [t] if t else []


def find_node(graph: list[dict], type_name: str) -> dict | None:
    for node in graph:
        if isinstance(node, dict) and type_name in type_names(node):
            return node
    return None


def fix_relative_ids(obj, real_org_id: str) -> None:
    if isinstance(obj, dict):
        if isinstance(obj.get("@id"), str) and obj["@id"].startswith("/전국센터"):
            obj["@id"] = real_org_id
        for v in obj.values():
            fix_relative_ids(v, real_org_id)
    elif isinstance(obj, list):
        for v in obj:
            fix_relative_ids(v, real_org_id)


def extract_reviews(text: str) -> list[tuple[str, str]]:
    pattern = re.compile(
        r'<div class="stars" aria-label="(\d)점">[^<]*</div>\s*<p>(.*?)</p>',
        re.S,
    )
    return [(m.group(1), m.group(2)) for m in pattern.finditer(text)]


def extract_faqs(text: str) -> list[tuple[str, str]]:
    faq_section_m = re.search(r'<div class="faq-list">.*?</div>\s*</div>\s*</section>', text, re.S)
    block = faq_section_m.group(0) if faq_section_m else text
    pattern = re.compile(r"<details>\s*<summary>(.*?)</summary><p>(.*?)</p></details>", re.S)
    return [(m.group(1), m.group(2)) for m in pattern.finditer(block)]


def render_review_grid(reviews: list[tuple[str, str]]) -> str:
    cards = []
    for rating, body in reviews:
        stars = "★" * int(rating) + "☆" * (5 - int(rating))
        cards.append(
            f'          <article class="review-card">\n'
            f'          <div class="stars" aria-label="{rating}점">{stars}</div>\n'
            f'          <p>{body}</p>\n'
            f'          <span>학부모</span>\n'
            f'        </article>'
        )
    return "\n".join(cards)


def render_faq_list(faqs: list[tuple[str, str]]) -> str:
    items = []
    for q, a in faqs:
        items.append(f"          <details><summary>{q}</summary><p>{a}</p></details>")
    return "\n".join(items)


def process_page(page_dir: Path, seen_reviews: set) -> bool:
    path = page_dir / "index.html"
    source = path.read_text(encoding="utf-8", errors="ignore")
    rel = page_dir.relative_to(CENTER_ROOT)
    category = rel.parts[0]
    subject = SUBJECT_MAP.get(category, "주요 과목")
    page_url = DOMAIN + "/" + quote("전국센터/" + "/".join(rel.parts), safe="/") + "/"

    updated = source

    # 1) JSON-LD: fix relative @id bug + add alternateName/branchOf + rebuild review/FAQ nodes
    m = re.search(r'<script type="application/ld\+json">(.*?)</script>', updated, re.S)
    data = json.loads(m.group(1))
    graph = data["@graph"]

    org = find_node(graph, "EducationalOrganization")
    real_org_id = org["@id"]
    fix_relative_ids(data, real_org_id)

    if "alternateName" not in org:
        org["alternateName"] = list(ALTERNATE_NAMES)
    if "branchOf" not in org:
        org["branchOf"] = {"@id": ROOT_ORG_ID}

    # Reviews: keep slot 0 (dong-specific opener), regenerate slots 1-5 from bank
    visible_reviews = extract_reviews(updated)
    opener_rating, opener_body = visible_reviews[0]
    five_star = pick_unique(REVIEW_BANK_5, 4, seen_reviews, page_url, "review5")
    four_star = pick(REVIEW_BANK_4, 1, page_url, "review4")[0]
    rng = random.Random(seed_for(page_url, "review-pos"))
    position = 1 + rng.randrange(5)
    new_reviews = [(opener_rating, opener_body)] + [("5", b) for b in five_star]
    new_reviews.insert(position, ("4", four_star))

    org["review"] = [
        {
            "@type": "Review",
            "author": {"@type": "Person", "name": "학부모"},
            "reviewBody": body,
            "reviewRating": {"@type": "Rating", "ratingValue": rating, "bestRating": "5"},
        }
        for rating, body in new_reviews
    ]

    # FAQ: keep slots 0,1,2,4 (dong/subject-specific), regenerate slots 3 and 5.
    # Questions and answers are selected as an inseparable pair so that a
    # newly selected question can never retain an unrelated previous answer.
    visible_faqs = extract_faqs(updated)
    faq_q4_template, faq_a4_template = pick(FAQ_SLOT4_BANK, 1, page_url, "faq4")[0]
    faq_q6_template, faq_a6_template = pick(FAQ_SLOT6_BANK, 1, page_url, "faq6")[0]
    faq_q4 = faq_q4_template.format(subject=subject)
    faq_a4 = faq_a4_template.format(subject=subject)
    faq_q6 = faq_q6_template.format(subject=subject)
    faq_a6 = faq_a6_template.format(subject=subject)
    new_faqs = list(visible_faqs)
    new_faqs[3] = (faq_q4, faq_a4)
    new_faqs[5] = (faq_q6, faq_a6)

    faq_node = find_node(graph, "FAQPage")
    faq_node["mainEntity"] = [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}}
        for q, a in new_faqs
    ]

    rendered = '<script type="application/ld+json">' + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "</script>"
    updated = updated[: m.start()] + rendered + updated[m.end():]

    # 2) Visible HTML: rebuild review-grid and faq-list to match JSON-LD exactly
    new_review_html = render_review_grid(new_reviews)
    updated = re.sub(
        r'(<div class="review-grid">\n)(.*?)(\n\s*</div>\s*\n\s*</div>\s*\n\s*</section>)',
        lambda mm: mm.group(1) + new_review_html + mm.group(3),
        updated,
        count=1,
        flags=re.S,
    )

    new_faq_html = render_faq_list(new_faqs)
    updated = re.sub(
        r'(<div class="faq-list">\n)(.*?)(\n\s*</div>\s*\n\s*</div>\s*\n\s*</section>)',
        lambda mm: mm.group(1) + new_faq_html + mm.group(3),
        updated,
        count=1,
        flags=re.S,
    )

    if updated != source:
        path.write_text(updated, encoding="utf-8")
        return True
    return False


def main() -> None:
    targets = target_files()
    seen_reviews: set = set()
    changed = 0
    errors = 0
    for page_dir in targets:
        try:
            if process_page(page_dir, seen_reviews):
                changed += 1
        except Exception as exc:  # noqa: BLE001
            errors += 1
            print(f"ERROR {page_dir}: {exc}")
    print(json.dumps({"targets": len(targets), "changed": changed, "errors": errors}, ensure_ascii=False))


if __name__ == "__main__":
    main()
