from __future__ import annotations

import html
import json
import re
import statistics
from collections import Counter
from pathlib import Path

from individualize_math_geo_site4 import (
    MATH_ROOT,
    grade_context,
    load_center_info,
    normalize_text,
    page_identity,
    page_title,
    school_context,
)


def clean(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def extract_block(source: str, start: str, end: str) -> str:
    left = source.find(start)
    right = source.find(end, left + 1)
    return source[left:right] if left >= 0 and right >= 0 else ""


def grams(value: str, size: int = 5) -> set[str]:
    value = re.sub(r"\s+", "", value)
    return {value[i : i + size] for i in range(max(0, len(value) - size + 1))}


def main() -> None:
    center_info = load_center_info()
    files = sorted(MATH_ROOT.glob("*/index.html"))
    paragraph_counters = {
        "summary": Counter(),
        "answer": Counter(),
        "checklist": Counter(),
    }
    substantive_counters = {key: Counter() for key in paragraph_counters}
    section_texts = {key: [] for key in paragraph_counters}
    errors = Counter()

    for path in files:
        source = path.read_text(encoding="utf-8", errors="ignore")
        dong, level = page_identity(path.parent)
        branch = center_info[dong.replace(" ", "")]
        title = page_title(source)
        blocks = {
            "summary": extract_block(source, '<article id="geo-summary"', '<article id="geo-answer"'),
            "answer": extract_block(source, '<article id="geo-answer"', '<article id="geo-checklist"'),
            "checklist": extract_block(source, '<article id="geo-checklist"', '<!-- seo-geo-enhancement:end -->'),
        }
        if not all(blocks.values()):
            errors["missing_section"] += 1
            continue
        if source.count('id="geo-summary"') != 1 or source.count('id="geo-answer"') != 1 or source.count('id="geo-checklist"') != 1:
            errors["duplicate_section_id"] += 1

        grades_label, grades_text = grade_context(branch, level, title)
        _, schools_text = school_context(branch, level, title)
        section = " ".join(clean(block) for block in blocks.values())
        for expected in (
            normalize_text(branch["센터명"]),
            normalize_text(branch["센터 주소"]),
            grades_label,
            grades_text,
            schools_text,
        ):
            if expected not in section:
                errors["missing_expected_center_fact"] += 1
                break

        json_match = re.search(r'<script type="application/ld\+json">(.*?)</script>', source, re.S)
        try:
            json.loads(json_match.group(1))
        except Exception:
            errors["jsonld_parse_error"] += 1
        if len(re.findall(r"<h1\b", source, re.I)) != 1:
            errors["h1_not_one"] += 1
        canonical = re.search(r'<link rel="canonical" href="([^"]+)"', source)
        og_url = re.search(r'<meta property="og:url" content="([^"]+)"', source)
        if not canonical or not og_url or canonical.group(1) != og_url.group(1):
            errors["canonical_og_mismatch"] += 1

        for key, block in blocks.items():
            text = clean(block)
            section_texts[key].append(text)
            for attrs, paragraph in re.findall(r"<p\b([^>]*)>(.*?)</p>", block, re.I | re.S):
                paragraph = clean(paragraph)
                if paragraph:
                    paragraph_counters[key][paragraph] += 1
                    if "eyebrow" not in attrs:
                        substantive_counters[key][paragraph] += 1

    report = {
        "files": len(files),
        "errors": dict(errors),
        "sections": {},
    }
    for key, counter in paragraph_counters.items():
        similarities = []
        for left, right in zip(section_texts[key], section_texts[key][1:]):
            left_grams = grams(left)
            right_grams = grams(right)
            similarities.append(len(left_grams & right_grams) / len(left_grams | right_grams))
        total = sum(counter.values())
        repeated = sum(count for count in counter.values() if count >= 100)
        substantive = substantive_counters[key]
        substantive_total = sum(substantive.values())
        substantive_repeated = sum(count for count in substantive.values() if count >= 100)
        report["sections"][key] = {
            "exact_unique_sections": len(set(section_texts[key])),
            "paragraph_instances": total,
            "unique_paragraphs": len(counter),
            "repeat_ge_100_instances": repeated,
            "repeat_ge_100_share": round(repeated / total, 4) if total else 0,
            "max_repeat": max(counter.values(), default=0),
            "substantive_paragraph_instances": substantive_total,
            "substantive_unique_paragraphs": len(substantive),
            "substantive_repeat_ge_100_share": round(substantive_repeated / substantive_total, 4)
            if substantive_total
            else 0,
            "substantive_max_repeat": max(substantive.values(), default=0),
            "adjacent_5gram_mean": round(statistics.mean(similarities), 4) if similarities else 0,
            "adjacent_5gram_median": round(statistics.median(similarities), 4) if similarities else 0,
        }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
