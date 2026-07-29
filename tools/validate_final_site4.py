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
    return sorted(CENTER_ROOT.glob("*/*/index.html"))


def main() -> None:
    files = target_files()
    parse_errors = 0
    faq_mismatch = 0
    faq_pair_invalid = 0
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
        visible_faqs = re.findall(
            r"<details>\s*<summary>([^<]*)</summary><p>(.*?)</p></details>",
            faq_section_m.group(0),
            re.S,
        )
        jsonld_faqs = [
            (q["name"], q["acceptedAnswer"]["text"])
            for q in faq_node["mainEntity"]
        ]
        if visible_faqs != jsonld_faqs:
            faq_mismatch += 1
            print("FAQ MISMATCH", f)

        # FAQ는 고정 문구 은행의 특정 두 쌍을 강제하지 않는다. 페이지별로
        # 개별화된 질문·답변이더라도 여섯 가지 상담 의도와 의미가 맞는지를
        # 검증한다. 화면/JSON-LD의 완전 일치는 위에서 별도로 검사한다.
        faq_intent_terms = (
            (("먼저", "확인"), ("먼저", "정")),
            (("준비", "자료"), ("준비", "확인")),
            (("다른", "어떻게"), ("학생", "도움")),
            (("수업", "학년"), ("가능", "학년")),
            (("학교", "정보"), ("시험", "참고")),
            (("위치", "확인"), ("주소", "방문")),
        )

        def has_pair(value: str, alternatives) -> bool:
            return any(all(term in value for term in pair) for pair in alternatives)

        pair_ok = len(visible_faqs) == 6
        if pair_ok:
            for (question, answer), alternatives in zip(visible_faqs, faq_intent_terms):
                combined = question + " " + answer
                if not question.strip() or not answer.strip() or not has_pair(combined, alternatives):
                    pair_ok = False
                    break
        if not pair_ok:
            faq_pair_invalid += 1
            print("FAQ PAIR INVALID", f)

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

    print(
        f"total={len(files)} parse_errors={parse_errors} "
        f"faq_mismatch={faq_mismatch} faq_pair_invalid={faq_pair_invalid} "
        f"review_mismatch={review_mismatch} rating_bad={rating_bad}"
    )


if __name__ == "__main__":
    main()
