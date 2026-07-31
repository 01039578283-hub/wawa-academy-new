from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CENTER_ROOT = ROOT / "전국센터"

SUBJECT_MAP = {
    "수학학원": "수학",
    "영어학원": "영어",
    "영수학원": "영어·수학",
    "초등학생학원": "주요 과목",
    "중학생학원": "주요 과목",
    "고등학생학원": "주요 과목",
}


def target_files() -> list[Path]:
    return sorted(
        path
        for path in CENTER_ROOT.glob("*/*/index.html")
        if 'data-intent-role="' in path.read_text(encoding="utf-8", errors="ignore")
    )


def hub_files() -> list[Path]:
    result = []
    for path in CENTER_ROOT.rglob("index.html"):
        rel = path.parent.relative_to(CENTER_ROOT)
        if not rel.parts or len(rel.parts) > 3:
            continue
        source = path.read_text(encoding="utf-8", errors="ignore")
        if 'data-intent-role="' not in source:
            result.append(path)
    return sorted(result)


def type_names(node: dict) -> list[str]:
    value = node.get("@type")
    return value if isinstance(value, list) else [value] if value else []


def find_node(graph: list[dict], type_name: str) -> dict | None:
    return next(
        (
            node
            for node in graph
            if isinstance(node, dict) and type_name in type_names(node)
        ),
        None,
    )


def extract_json(text: str) -> dict:
    match = re.search(r'<script type="application/ld\+json">(.*?)</script>', text, re.S)
    if not match:
        raise ValueError("JSON-LD missing")
    return json.loads(match.group(1))


def extract_visible_faqs(text: str, *, hub: bool = False) -> list[tuple[str, str]]:
    if hub:
        match = re.search(
            r'<div class="faq-list" id="hub-faq-list">.*?</div>',
            text,
            re.S,
        )
    else:
        match = re.search(r'<section id="faq-section".*?</section>', text, re.S)
    return re.findall(
        r"<details(?:\s[^>]*)?>\s*<summary>(.*?)</summary>\s*<p>(.*?)</p>\s*</details>",
        match.group(0) if match else "",
        re.S,
    )


def extract_structured_faqs(graph: list[dict]) -> list[tuple[str, str]]:
    faq = find_node(graph, "FAQPage")
    return [
        (str(item.get("name", "")), str(item.get("acceptedAnswer", {}).get("text", "")))
        for item in (faq or {}).get("mainEntity", [])
        if isinstance(item, dict)
    ]


def main() -> None:
    files = target_files()
    hubs = hub_files()
    parse_errors = 0
    faq_mismatch = 0
    faq_pair_invalid = 0
    unsupported_review_schema = 0
    unsupported_review_markup = 0
    consultation_case_bad = 0
    mechanical_label_bad = 0
    hub_content_missing = 0
    hub_faq_mismatch = 0

    for f in files:
        text = f.read_text(encoding="utf-8", errors="ignore")
        try:
            data = extract_json(text)
        except Exception as exc:  # noqa: BLE001
            parse_errors += 1
            print("PARSE ERROR", f, exc)
            continue

        graph = data["@graph"]

        visible_faqs = extract_visible_faqs(text)
        jsonld_faqs = extract_structured_faqs(graph)
        if visible_faqs != jsonld_faqs:
            faq_mismatch += 1
            print("FAQ MISMATCH", f)

        # FAQ는 고정 문구 은행의 특정 두 쌍을 강제하지 않는다. 페이지별로
        # 개별화된 질문·답변이더라도 여섯 가지 상담 의도와 의미가 맞는지를
        # 검증한다. 화면/JSON-LD의 완전 일치는 위에서 별도로 검사한다.
        pair_ok = len(visible_faqs) == 6
        if pair_ok:
            checks = (
                lambda question, answer: "먼저" in question + answer
                and any(term in answer for term in ("확인", "정합니다")),
                lambda question, answer: any(
                    term in question
                    for term in ("자료", "기록", "진도", "단원", "오답", "습관", "시간", "계획")
                )
                and any(
                    term in answer
                    for term in ("자료", "기록", "교재", "시험지", "플래너", "진도")
                ),
                lambda question, answer: any(
                    term in question for term in ("다른", "학생", "도움")
                )
                and any(term in answer for term in ("중심", "기준", "학생")),
                lambda question, answer: "학년" in question
                and any(term in answer for term in ("학년", "과정", "수업 가능")),
                lambda question, answer: "학교" in question
                and any(term in answer for term in ("학교", "시험 범위", "교재")),
                lambda question, answer: any(term in question for term in ("위치", "방문"))
                and any(term in answer for term in ("주소", "방문", "위치")),
            )
            for (question, answer), check in zip(visible_faqs, checks):
                if not question.strip() or not answer.strip() or not check(question, answer):
                    pair_ok = False
                    break
        if not pair_ok:
            faq_pair_invalid += 1
            print("FAQ PAIR INVALID", f)

        org = find_node(graph, "EducationalOrganization")
        review_nodes = [
            node
            for node in graph
            if isinstance(node, dict)
            and any(kind in ("Review", "AggregateRating") for kind in type_names(node))
        ]
        if (
            not org
            or "review" in org
            or "aggregateRating" in org
            or review_nodes
        ):
            unsupported_review_schema += 1
            print("UNSUPPORTED REVIEW SCHEMA", f)
        if (
            "PARENT REVIEW" in text
            or 'class="stars"' in text
            or re.search(r"<span>\s*학부모\s*</span>", text)
        ):
            unsupported_review_markup += 1
            print("UNSUPPORTED REVIEW MARKUP", f)
        case_match = re.search(
            r'<section id="consultation-cases"[^>]*>(.*?)</section>',
            text,
            re.S,
        )
        if (
            not case_match
            or len(re.findall(r'class="review-card consultation-case-card"', case_match.group(0))) != 3
            or "이용 후기가 아니라" not in case_match.group(0)
        ):
            consultation_case_bad += 1
            print("CONSULTATION CASE BAD", f)
        if any(
            phrase in text
            for phrase in (
                "DIRECT STUDY ANSWER",
                "VERIFIED CENTER CONTEXT",
                "PERSONALIZED CHECKLIST",
            )
        ):
            mechanical_label_bad += 1
            print("MECHANICAL LABEL", f)

    for f in hubs:
        text = f.read_text(encoding="utf-8", errors="ignore")
        try:
            graph = extract_json(text).get("@graph", [])
        except Exception as exc:  # noqa: BLE001
            parse_errors += 1
            print("HUB PARSE ERROR", f, exc)
            continue
        if (
            "<!-- content-trust-hub:start -->" not in text
            or 'id="hub-answer"' not in text
            or 'id="hub-faq-list"' not in text
        ):
            hub_content_missing += 1
            print("HUB CONTENT MISSING", f)
            continue
        visible = extract_visible_faqs(text, hub=True)
        structured = extract_structured_faqs(graph)
        if len(visible) != 3 or visible != structured:
            hub_faq_mismatch += 1
            print("HUB FAQ MISMATCH", f)

    print(
        f"details={len(files)} hubs={len(hubs)} parse_errors={parse_errors} "
        f"faq_mismatch={faq_mismatch} faq_pair_invalid={faq_pair_invalid} "
        f"unsupported_review_schema={unsupported_review_schema} "
        f"unsupported_review_markup={unsupported_review_markup} "
        f"consultation_case_bad={consultation_case_bad} "
        f"mechanical_label_bad={mechanical_label_bad} "
        f"hub_content_missing={hub_content_missing} "
        f"hub_faq_mismatch={hub_faq_mismatch}"
    )
    failures = (
        parse_errors
        + faq_mismatch
        + faq_pair_invalid
        + unsupported_review_schema
        + unsupported_review_markup
        + consultation_case_bad
        + mechanical_label_bad
        + hub_content_missing
        + hub_faq_mismatch
    )
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
