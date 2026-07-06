from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CENTER_ROOT = ROOT / "전국센터"

REQUIRED_TYPES = [
    "EducationalOrganization",
    "LocalBusiness",
    "WebPage",
    "BreadcrumbList",
    "Article",
    "Service",
    "FAQPage",
    "ItemList",
]


def type_names(node) -> list[str]:
    t = node.get("@type")
    if isinstance(t, list):
        return t
    return [t] if t else []


def target_files() -> list[Path]:
    result = []
    for index in CENTER_ROOT.rglob("index.html"):
        rel = index.parent.relative_to(CENTER_ROOT)
        if str(rel) == ".":
            continue
        result.append(index)
    return sorted(result)


def main() -> None:
    files = target_files()
    print(f"total_detail_pages={len(files)}")

    issues = Counter()
    faq_counter: Counter[str] = Counter()
    review_counter: Counter[str] = Counter()
    review_sets: Counter[frozenset] = Counter()
    relative_id_bug = 0

    for f in files:
        text = f.read_text(encoding="utf-8", errors="ignore")

        if 'canonical" href="/"' in text or "canonical\" href=\"/\"" in text:
            issues["placeholder_canonical"] += 1
        if not re.search(r'<link rel="canonical"', text):
            issues["no_canonical"] += 1
        if not re.search(r'<meta property="og:url"', text):
            issues["no_og_url"] += 1

        h1s = re.findall(r"<h1\b[^>]*>.*?</h1>", text, re.S)
        if len(h1s) != 1:
            issues["h1_not_exactly_one"] += 1

        title_m = re.search(r"<title>(.*?)</title>", text, re.S)
        if not title_m or " | " not in title_m.group(1):
            issues["bad_title_format"] += 1

        if '"@id":"/전국센터' in text:
            relative_id_bug += 1

        m = re.search(r'<script type="application/ld\+json">(.*?)</script>', text, re.S)
        if not m:
            issues["no_jsonld"] += 1
            continue
        try:
            data = json.loads(m.group(1))
        except Exception:
            issues["jsonld_parse_error"] += 1
            continue

        graph = data.get("@graph", [])
        present_types = set()
        for node in graph:
            if isinstance(node, dict):
                present_types.update(type_names(node))
        missing = [t for t in REQUIRED_TYPES if t not in present_types]
        if missing:
            issues[f"missing:{','.join(missing)}"] += 1

        def find(type_name):
            for node in graph:
                if isinstance(node, dict) and type_name in type_names(node):
                    return node
            return None

        webpage = find("WebPage")
        article = find("Article")
        org = find("EducationalOrganization")
        if webpage and not webpage.get("about"):
            issues["webpage_no_about"] += 1
        if webpage and not webpage.get("mentions"):
            issues["webpage_no_mentions"] += 1
        if webpage and not webpage.get("hasPart"):
            issues["webpage_no_haspart"] += 1
        if article and not article.get("articleSection"):
            issues["article_no_articlesection"] += 1
        if org and not org.get("makesOffer"):
            issues["org_no_makesoffer"] += 1
        if org and not org.get("alternateName"):
            issues["org_no_alternatename"] += 1
        if org and not org.get("branchOf"):
            issues["org_no_branchof"] += 1

        faq_section_m = re.search(r'<section id="faq-section".*?</section>', text, re.S)
        faqs = re.findall(r"<summary>([^<]*)</summary>", faq_section_m.group(0)) if faq_section_m else []
        for q in faqs:
            faq_counter[q] += 1
        reviews = re.findall(r'review-card">\s*<div class="stars"[^>]*>[^<]*</div>\s*<p>(.*?)</p>', text, re.S)
        for r in reviews:
            review_counter[r] += 1
        if reviews:
            review_sets[frozenset(reviews)] += 1

    print("--- structural issues ---")
    for key, cnt in issues.most_common(40):
        print(f"{key}: {cnt}")

    print(f"\nrelative_id_bug_pages={relative_id_bug}")

    print(f"\ndistinct_faq_questions={len(faq_counter)} total_faq_instances={sum(faq_counter.values())}")
    for text, cnt in faq_counter.most_common(5):
        print(f"  {cnt}x  {text[:50]}")

    print(f"\ndistinct_review_bodies={len(review_counter)} total_review_instances={sum(review_counter.values())}")
    for text, cnt in review_counter.most_common(5):
        print(f"  {cnt}x  {text[:50]}")

    dup_sets = sum(1 for c in review_sets.values() if c > 1)
    print(f"\ndistinct_review_sets={len(review_sets)} pages_with_reviews={sum(review_sets.values())} dup_sets={dup_sets}")


if __name__ == "__main__":
    main()
