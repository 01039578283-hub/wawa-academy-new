from __future__ import annotations

import html
import json
import re
import statistics
from collections import Counter, defaultdict

from individualize_aeo_geo_site4 import (
    CENTER_ROOT,
    canonical,
    classify,
    find_node,
    format_values,
    load_centers,
    page_title,
    role_key,
)


def text_only(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value))).strip()


def article(source: str, article_id: str) -> str:
    match = re.search(rf'<article id="{re.escape(article_id)}".*?</article>', source, re.S)
    if not match:
        raise ValueError(f"missing {article_id}")
    return match.group(0)


def first_body(fragment: str) -> str:
    paragraphs = [text_only(item) for item in re.findall(r"<p(?:\s[^>]*)?>(.*?)</p>", fragment, re.S)]
    return paragraphs[1] if len(paragraphs) > 1 else ""


def json_data(source: str) -> dict:
    match = re.search(r'<script type="application/ld\+json">(.*?)</script>', source, re.S)
    if not match:
        raise ValueError("JSON-LD missing")
    return json.loads(match.group(1))


def meta_description(source: str) -> str:
    match = re.search(r'<meta name="description" content="([^"]*)"', source)
    return html.unescape(match.group(1)) if match else ""


def template_signature(value: str, values: dict, title: str) -> str:
    replacements = {
        title,
        values.get("dong", ""),
        values.get("region", ""),
        values.get("center", ""),
        values.get("address", ""),
        values.get("location", ""),
        values.get("schools", ""),
        values.get("grades", ""),
        values.get("scope", ""),
        values.get("stage_label", ""),
        values.get("stage_student", ""),
        values.get("subject_label", ""),
    }
    result = value
    for item in sorted((item for item in replacements if item), key=len, reverse=True):
        result = result.replace(item, "{FACT}")
    return re.sub(r"\s+", " ", result).strip()


def percentile(values: list[float], ratio: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round((len(ordered) - 1) * ratio))]


def main() -> None:
    centers = load_centers()
    targets = sorted(CENTER_ROOT.glob("*/*/index.html"))
    summaries: Counter[str] = Counter()
    summary_templates: Counter[str] = Counter()
    answers: Counter[str] = Counter()
    answer_templates: Counter[str] = Counter()
    checks: Counter[str] = Counter()
    check_templates: Counter[str] = Counter()
    faq_questions: Counter[str] = Counter()
    faq_answers: Counter[str] = Counter()
    descriptions: Counter[str] = Counter()
    description_lengths: list[int] = []
    role_summary_templates: dict[str, Counter[str]] = defaultdict(Counter)
    grammar_patterns = Counter()
    schema_complete = 0
    verified_context_pages = 0
    faq_matches = 0
    errors: list[str] = []

    bad_phrases = (
        "오답 재풀이을",
        "풀이을",
        "실제 기록으로 이어지는지 기록으로 확인합니다",
        "교과 성취을",
        "센터정보",
        "외고이 기재",
        "맞은편라고",
    )

    for path in targets:
        try:
            source = path.read_text(encoding="utf-8")
            identity = classify(path.parent.parent.name, path.parent.name)
            branch = centers[identity["dong"].replace(" ", "")]
            title = page_title(source)
            values = format_values(title, identity, branch)
            summary = first_body(article(source, "geo-summary"))
            answer = first_body(article(source, "geo-answer"))
            summary_signature = template_signature(summary, values, title)
            answer_signature = template_signature(answer, values, title)
            summaries[summary] += 1
            summary_templates[summary_signature] += 1
            answers[answer] += 1
            answer_templates[answer_signature] += 1
            role_summary_templates[role_key(identity)][summary_signature] += 1

            for body in re.findall(r'<article class="geo-check-card">.*?<p>(.*?)</p></article>', source, re.S):
                plain = text_only(body)
                checks[plain] += 1
                check_templates[template_signature(plain, values, title)] += 1

            faq_section = re.search(r'<section id="faq-section".*?</section>', source, re.S)
            visible = re.findall(
                r"<details>\s*<summary>([^<]*)</summary><p>(.*?)</p></details>",
                faq_section.group(0) if faq_section else "",
                re.S,
            )
            for question, response in visible:
                faq_questions[text_only(question)] += 1
                faq_answers[text_only(response)] += 1

            description = meta_description(source)
            descriptions[description] += 1
            description_lengths.append(len(description))

            data = json_data(source)
            graph = data.get("@graph", [])
            org = find_node(graph, "EducationalOrganization")
            webpage = find_node(graph, "WebPage")
            service = find_node(graph, "Service")
            article_node = find_node(graph, "Article")
            faq_node = find_node(graph, "FAQPage")
            required_nodes = (org, webpage, service, article_node, faq_node)
            if all(required_nodes) and all(
                node.get("about") and node.get("mentions")
                for node in (webpage, service, article_node, faq_node)
            ) and service.get("serviceType") and article_node.get("articleSection"):
                schema_complete += 1

            structured = [
                (item.get("name", ""), item.get("acceptedAnswer", {}).get("text", ""))
                for item in (faq_node or {}).get("mainEntity", [])
            ]
            if visible == structured:
                faq_matches += 1

            factual_parts = [values.get("address", ""), values.get("grades", ""), values.get("schools", "")]
            if all(not part or part in source for part in factual_parts):
                verified_context_pages += 1

            for phrase in bad_phrases:
                if phrase in source:
                    grammar_patterns[phrase] += 1
            if not canonical(source):
                errors.append(f"canonical missing: {path}")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{path}: {exc}")

    total_check_occurrences = sum(checks.values()) or 1
    total_faq_answer_occurrences = sum(faq_answers.values()) or 1
    repeated_checks = sum(count for count in checks.values() if count >= 100)
    repeated_faq_answers = sum(count for count in faq_answers.values() if count >= 100)
    result = {
        "pages": len(targets),
        "errors": len(errors),
        "direct_summary_unique": len(summaries),
        "direct_summary_template_signatures": len(summary_templates),
        "direct_answer_unique": len(answers),
        "direct_answer_template_signatures": len(answer_templates),
        "checklist_sentence_unique": len(checks),
        "checklist_template_signatures": len(check_templates),
        "checklist_occurrences_reused_100_plus_pct": round(repeated_checks / total_check_occurrences * 100, 2),
        "faq_question_unique": len(faq_questions),
        "faq_answer_unique": len(faq_answers),
        "faq_answer_occurrences_reused_100_plus_pct": round(
            repeated_faq_answers / total_faq_answer_occurrences * 100, 2
        ),
        "faq_answer_top_repeats": [
            {"count": count, "sample": value[:140]}
            for value, count in faq_answers.most_common(8)
        ],
        "meta_description_unique": len(descriptions),
        "meta_description_length": {
            "min": min(description_lengths) if description_lengths else 0,
            "mean": round(statistics.mean(description_lengths), 1) if description_lengths else 0,
            "p95": percentile(description_lengths, 0.95),
            "max": max(description_lengths) if description_lengths else 0,
        },
        "schema_complete": schema_complete,
        "faq_screen_json_matches": faq_matches,
        "verified_context_pages": verified_context_pages,
        "grammar_pattern_pages": dict(grammar_patterns),
        "per_role_summary_template_range": {
            "min": min((len(counter) for counter in role_summary_templates.values()), default=0),
            "mean": round(
                statistics.mean(len(counter) for counter in role_summary_templates.values()), 1
            ) if role_summary_templates else 0,
            "max": max((len(counter) for counter in role_summary_templates.values()), default=0),
        },
        "sample_errors": errors[:10],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if errors or schema_complete != len(targets) or faq_matches != len(targets) or grammar_patterns:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
