from __future__ import annotations

import argparse
import html
import json
import re
import statistics
from collections import Counter
from pathlib import Path

from separate_page_intents_site4 import CATEGORY_RULES, CENTER_ROOT, canonical, classify, role_key


PAIR_CATEGORIES = {
    "math": "수학학원",
    "english": "영어학원",
    "combined": "영수학원",
}
GRADE_CATEGORIES = {
    "elementary": "초등학생학원",
    "middle": "중학생학원",
    "high": "고등학생학원",
}
COURSE_TERMS = {"elementary": "초등", "middle": "중등", "high": "고등"}
STUDENT_TERMS = {"elementary": "초등학생", "middle": "중학생", "high": "고등학생"}
SUBJECT_TERMS = {"math": "수학", "english": "영어", "combined": "영수"}


def visible_text(fragment: str) -> str:
    fragment = re.sub(r"<script\b.*?</script>", " ", fragment, flags=re.S | re.I)
    fragment = re.sub(r"<style\b.*?</style>", " ", fragment, flags=re.S | re.I)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def role_fragment(source: str) -> str:
    match = re.search(r"<!-- seo-geo-enhancement:start -->(.*?)<!-- seo-geo-enhancement:end -->", source, re.S)
    if not match:
        raise ValueError("role section missing")
    # 과목형/학년형 역할 분리는 공통으로 확인해야 하는 센터 주소·학년·학교
    # 카드가 아니라 페이지 상단의 직접 답변과 역할 경계 문단으로 측정한다.
    summary = re.search(r'<article id="geo-summary".*?</article>', match.group(1), re.S)
    if not summary:
        raise ValueError("role summary missing")
    return visible_text(summary.group(0))


def shingles(text: str, n: int = 4) -> set[tuple[str, ...]]:
    words = re.findall(r"[가-힣A-Za-z0-9]+", text)
    return {tuple(words[i : i + n]) for i in range(max(0, len(words) - n + 1))}


def jaccard(a: str, b: str) -> float:
    sa, sb = shingles(a), shingles(b)
    return len(sa & sb) / len(sa | sb) if sa or sb else 1.0


def normalize_pair_text(text: str, dong: str) -> str:
    return re.sub(
        r"수학|영어|영수|영어·수학|초등학생|중학생|고등학생|초등|중등|고등|학원|" + re.escape(dong),
        " ",
        text,
    )


def page_path(category: str, leaf: str) -> Path:
    return CENTER_ROOT / category / leaf / "index.html"


def pair_paths(dong: str, stage: str, subject: str) -> tuple[Path, Path]:
    course_leaf = f"{dong}{COURSE_TERMS[stage]}{SUBJECT_TERMS[subject]}학원"
    grade_leaf = f"{dong}{STUDENT_TERMS[stage]}{SUBJECT_TERMS[subject]}학원"
    return page_path(PAIR_CATEGORIES[subject], course_leaf), page_path(GRADE_CATEGORIES[stage], grade_leaf)


def percentile(values: list[float], p: float) -> float:
    values = sorted(values)
    if not values:
        return 0.0
    index = min(len(values) - 1, round((len(values) - 1) * p))
    return values[index]


def extract_json(source: str) -> dict:
    match = re.search(r'<script type="application/ld\+json">(.*?)</script>', source, re.S)
    if not match:
        raise ValueError("JSON-LD missing")
    return json.loads(match.group(1))


def find_node(graph: list[dict], kind: str) -> dict | None:
    for node in graph:
        value = node.get("@type") if isinstance(node, dict) else None
        kinds = value if isinstance(value, list) else [value]
        if kind in kinds:
            return node
    return None


def visible_faqs(source: str) -> list[tuple[str, str]]:
    match = re.search(r'<div class="faq-list">(.*?)</div>\s*</div>\s*</section>', source, re.S)
    if not match:
        return []
    return re.findall(r"<details>\s*<summary>(.*?)</summary><p>(.*?)</p></details>", match.group(1), re.S)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", action="store_true")
    args = parser.parse_args()

    targets = sorted(CENTER_ROOT.glob("*/*/index.html"))
    failures: list[str] = []
    counts: Counter[str] = Counter()
    canonicals: list[str] = []
    role_sections = 0
    faq_matches = 0
    h1_ok = 0
    href_targets_missing = 0
    sources: dict[Path, str] = {}
    identities: dict[Path, dict] = {}

    for path in targets:
        try:
            source = path.read_text(encoding="utf-8")
            identity = classify(path.parent.parent.name, path.parent.name)
            sources[path] = source
            identities[path] = identity
            key = role_key(identity)
            counts[key] += 1
            canonicals.append(canonical(source))
            if len(re.findall(r"<h1\b", source, re.I)) == 1:
                h1_ok += 1
            elif not args.baseline:
                failures.append(f"H1 count: {path}")

            marker = re.search(r'data-intent-role="([^"]+)"', source)
            if marker and marker.group(1) == key:
                role_sections += 1
            elif not args.baseline:
                failures.append(f"role marker: {path}")

            data = extract_json(source)
            graph = data.get("@graph", [])
            webpage = find_node(graph, "WebPage")
            service = find_node(graph, "Service")
            article = find_node(graph, "Article")
            faq = find_node(graph, "FAQPage")
            if not all((webpage, service, article, faq)):
                failures.append(f"JSON node: {path}")
                continue
            visible = visible_faqs(source)
            structured = [
                (item.get("name", ""), item.get("acceptedAnswer", {}).get("text", ""))
                for item in faq.get("mainEntity", [])
            ]
            if visible == structured and len(visible) == 6:
                faq_matches += 1
            elif not args.baseline:
                failures.append(f"FAQ mismatch: {path}")
            if not args.baseline:
                knows_about = (find_node(graph, "EducationalOrganization") or {}).get("knowsAbout", [])
                if service.get("serviceType") not in knows_about:
                    failures.append(f"role JSON mismatch: {path}")
                if not webpage.get("description") or webpage.get("description") != article.get("description") or webpage.get("description") != service.get("description"):
                    failures.append(f"description mismatch: {path}")

            for href in re.findall(r'\bhref="([^"]+)"', source):
                if href.startswith("/") and not href.startswith("//"):
                    candidate = CENTER_ROOT.parent / href.lstrip("/")
                    if href.endswith("/"):
                        candidate = candidate / "index.html"
                    if not candidate.exists():
                        href_targets_missing += 1
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{path}: {exc}")

    pair_scores: list[float] = []
    pair_errors = 0
    for dong in sorted({identity["dong"] for identity in identities.values()}):
        for stage in ("elementary", "middle", "high"):
            for subject in ("math", "english", "combined"):
                left, right = pair_paths(dong, stage, subject)
                try:
                    lt = normalize_pair_text(role_fragment(sources[left]), dong)
                    rt = normalize_pair_text(role_fragment(sources[right]), dong)
                    pair_scores.append(jaccard(lt, rt))
                except Exception:
                    pair_errors += 1

    result = {
        "detail_pages": len(targets),
        "role_types": len(counts),
        "role_counts": dict(sorted(counts.items())),
        "unique_canonicals": len(set(canonicals)),
        "h1_ok": h1_ok,
        "role_sections": role_sections,
        "faq_screen_json_matches": faq_matches,
        "missing_internal_targets": href_targets_missing,
        "paired_pages": len(pair_scores),
        "paired_section_similarity": {
            "mean": round(statistics.mean(pair_scores), 4) if pair_scores else None,
            "p50": round(percentile(pair_scores, 0.5), 4),
            "p95": round(percentile(pair_scores, 0.95), 4),
            "max": round(max(pair_scores), 4) if pair_scores else None,
        },
        "pair_errors": pair_errors,
        "failures": len(failures),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not args.baseline:
        expected = 8904
        checks = [
            len(targets) == expected,
            len(counts) == 24 and all(value == 371 for value in counts.values()),
            len(set(canonicals)) == expected,
            h1_ok == expected,
            role_sections == expected,
            faq_matches == expected,
            href_targets_missing == 0,
            len(pair_scores) == 3339 and pair_errors == 0,
            percentile(pair_scores, 0.95) < 0.30,
            not failures,
        ]
        if not all(checks):
            for failure in failures[:30]:
                print(f"FAIL {failure}")
            raise SystemExit(1)


if __name__ == "__main__":
    main()
