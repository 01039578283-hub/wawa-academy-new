"""Trust, FAQ, and hub-answer improvements for 와와학습코칭학원.

The default mode is a read-only dry run. Use ``--apply`` only after reviewing
the summary. The tool is idempotent and can be run after detail or split-hub
generators, which prevents old testimonial/rating markup from returning.

Scope:
* detail pages: replace unsupported review/rating content with consultation
  examples, diversify two generic FAQ slots, remove Review/AggregateRating,
  and replace production-facing English labels with plain Korean.
* split hubs: add a concise answer section and three visible/schema-matched
  FAQs based on the actual category, region/district, and child-page count.

No school, neighborhood, address, or result claim is invented here. Detail
facts come from ``center_info.json`` through the existing verified formatter;
hub counts come from the actual detail-page inventory.
"""

from __future__ import annotations

import argparse
import html
import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from individualize_aeo_geo_site4 import (
    CENTER_ROOT,
    build_faqs,
    canonical,
    classify,
    format_values,
    href_counter,
    load_centers,
    page_title,
    render_consultation_cases,
    render_section,
    replace_consultation_cases,
    update_jsonld,
)
from separate_page_intents_site4 import find_node, render_faqs, role_key, type_names
from split_category_hubs_site4 import CATEGORY_BY_NAME, collect_details
from split_category_hubs_site4 import load_centers as load_hub_centers


TODAY = date.today().isoformat()
HUB_MARKER_START = "<!-- content-trust-hub:start -->"
HUB_MARKER_END = "<!-- content-trust-hub:end -->"


@dataclass(frozen=True)
class HubFacts:
    category: str
    region: str
    district: str
    detail_count: int
    district_count: int


def text_only(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value))).strip()


def json_data(source: str) -> tuple[dict, re.Match[str]]:
    match = re.search(r'<script type="application/ld\+json">(.*?)</script>', source, re.S)
    if not match:
        raise ValueError("JSON-LD missing")
    return json.loads(match.group(1)), match


def replace_json(source: str, data: dict, match: re.Match[str]) -> str:
    rendered = '<script type="application/ld+json">' + json.dumps(
        data, ensure_ascii=False, separators=(",", ":")
    ) + "</script>"
    return source[: match.start()] + rendered + source[match.end() :]


def visible_faqs(source: str) -> list[tuple[str, str]]:
    section = re.search(r'<section id="faq-section".*?</section>', source, re.S)
    if not section:
        section = re.search(
            r'<div class="faq-list" id="hub-faq-list">.*?</div>',
            source,
            re.S,
        )
    if not section:
        return []
    return [
        (text_only(question), text_only(answer))
        for question, answer in re.findall(
            r"<details(?:\s[^>]*)?>\s*<summary>(.*?)</summary>\s*<p>(.*?)</p>\s*</details>",
            section.group(0),
            re.S,
        )
    ]


def structured_faqs(source: str) -> list[tuple[str, str]]:
    data, _ = json_data(source)
    graph = data.get("@graph", [])
    node = find_node(graph, "FAQPage")
    return [
        (
            str(item.get("name", "")),
            str(item.get("acceptedAnswer", {}).get("text", "")),
        )
        for item in (node or {}).get("mainEntity", [])
        if isinstance(item, dict)
    ]


def replace_detail_faqs(source: str, faqs: list[tuple[str, str]]) -> str:
    updated, count = re.subn(
        r'(<div class="faq-list">\n)(.*?)(\n\s*</div>\s*\n\s*</div>\s*\n\s*</section>)',
        lambda match: match.group(1) + render_faqs(faqs) + match.group(3),
        source,
        count=1,
        flags=re.S,
    )
    if count != 1:
        raise ValueError("detail FAQ HTML replacement failed")
    return updated


def transform_detail_source(source: str, path: Path, centers: dict[str, dict]) -> str:
    category = path.parent.parent.name
    identity = classify(category, path.parent.name)
    branch = centers[identity["dong"].replace(" ", "")]
    title = page_title(source)
    faqs = build_faqs(title, identity, branch)

    updated, count = re.subn(
        r"<!-- seo-geo-enhancement:start -->.*?<!-- seo-geo-enhancement:end -->",
        render_section(title, identity, branch),
        source,
        count=1,
        flags=re.S,
    )
    if count != 1:
        raise ValueError("SEO/GEO section marker missing or duplicated")
    updated = replace_consultation_cases(updated, title, identity, branch)
    updated = replace_detail_faqs(updated, faqs)
    updated = update_jsonld(
        updated,
        title,
        # Preserve the page's current description; this tool is not a meta rewrite.
        html.unescape(
            re.search(r'<meta name="description" content="([^"]*)"', updated).group(1)
        ),
        identity,
        branch,
        faqs,
    )
    updated = updated.replace('href="#parent-reviews"', 'href="#consultation-cases"')

    if canonical(updated) != canonical(source):
        raise ValueError("canonical changed")
    before_hrefs = href_counter(source)
    after_hrefs = href_counter(updated)
    # The only permitted href change is the renamed local consultation anchor.
    before_hrefs.subtract({"#parent-reviews": before_hrefs["#parent-reviews"]})
    after_hrefs.subtract({"#consultation-cases": after_hrefs["#consultation-cases"]})
    if +before_hrefs != +after_hrefs:
        raise ValueError("existing href set changed")
    if visible_faqs(updated) != structured_faqs(updated):
        raise ValueError("detail screen FAQ and FAQPage differ")
    data, _ = json_data(updated)
    graph = data.get("@graph", [])
    org = find_node(graph, "EducationalOrganization")
    if not org or "review" in org or "aggregateRating" in org:
        raise ValueError("unsupported review/rating remains on organization")
    if any(
        kind in ("Review", "AggregateRating")
        for node in graph
        if isinstance(node, dict)
        for kind in type_names(node)
    ):
        raise ValueError("unsupported review/rating graph node remains")
    if "PARENT REVIEW" in updated or 'class="stars"' in updated:
        raise ValueError("testimonial/rating markup remains")
    if 'id="consultation-cases"' not in updated:
        raise ValueError("consultation examples missing")
    return updated


def transform_detail(path: Path, centers: dict[str, dict]) -> str:
    source = path.read_text(encoding="utf-8", errors="strict")
    return transform_detail_source(source, path, centers)


def hub_facts_by_path() -> dict[Path, HubFacts]:
    centers, dong_names = load_hub_centers()
    details = collect_details(centers, dong_names)
    result: dict[Path, HubFacts] = {}
    category_groups: dict[str, list] = {}
    for detail in details:
        category_groups.setdefault(detail.category.name, []).append(detail)
    for category_name, category_details in category_groups.items():
        category_root = CENTER_ROOT / category_name
        result[category_root / "index.html"] = HubFacts(
            category=category_name,
            region="",
            district="",
            detail_count=len(category_details),
            district_count=len({(item.region, item.district) for item in category_details}),
        )
        by_region: dict[str, list] = {}
        for detail in category_details:
            by_region.setdefault(detail.region, []).append(detail)
        for region, region_details in by_region.items():
            region_path = category_root / region / "index.html"
            result[region_path] = HubFacts(
                category=category_name,
                region=region,
                district="",
                detail_count=len(region_details),
                district_count=len({item.district for item in region_details}),
            )
            for district in sorted({item.district for item in region_details}):
                district_path = category_root / region / district / "index.html"
                if not district_path.exists():
                    continue
                district_details = [item for item in region_details if item.district == district]
                result[district_path] = HubFacts(
                    category=category_name,
                    region=region,
                    district=district,
                    detail_count=len(district_details),
                    district_count=1,
                )
    return result


def hub_copy(facts: HubFacts) -> tuple[str, str, list[tuple[str, str]]]:
    category = CATEGORY_BY_NAME[facts.category]
    if not facts.region:
        scope = facts.category
        heading = f"{scope} 지역 안내는 어떻게 선택하면 좋을까요?"
        intro = (
            f"{category.focus}입니다. 이 허브에는 실제 생성된 동네 안내 "
            f"{facts.detail_count}개가 연결되어 있으며, 먼저 광역지역을 선택한 뒤 "
            "학생의 최근 학습 기록과 필요한 관리 기준이 맞는 상세페이지를 확인할 수 있습니다."
        )
        faqs = [
            (
                f"{scope} 동네 안내는 어떤 순서로 찾나요?",
                (
                    f"{facts.detail_count}개 동네 안내를 광역지역별로 나누었습니다. "
                    "현재 생활권의 광역지역을 선택한 뒤 시·군·구와 동네 순서로 확인하세요."
                ),
            ),
            (
                f"{scope} 상담에서는 무엇을 먼저 확인하나요?",
                (
                    f"{category.focus}를 기준으로 최근 교재, 평가 자료와 오답 기록을 함께 확인합니다. "
                    "학생마다 우선순위가 다르므로 실제 기록을 바탕으로 시작 범위를 정하는 것이 좋습니다."
                ),
            ),
            (
                f"{scope} 안내는 어떤 학생과 학부모에게 필요한가요?",
                (
                    f"{category.audience}에게 필요한 확인 기준을 정리했습니다. "
                    "상세페이지에서는 과목·학년 역할과 상담 준비 자료를 구분해 볼 수 있습니다."
                ),
            ),
        ]
    elif not facts.district:
        scope = f"{facts.region} {facts.category}"
        heading = f"{scope} 안내에서 무엇을 확인할 수 있나요?"
        intro = (
            f"{facts.region} 안의 {facts.district_count}개 시·군·구와 "
            f"{facts.detail_count}개 동네 안내를 연결한 페이지입니다. "
            f"{category.focus} 가운데 학생에게 필요한 기준을 먼저 정한 뒤 동네 상세 안내를 선택하세요."
        )
        faqs = [
            (
                f"{scope} 페이지는 몇 개 동네를 안내하나요?",
                (
                    f"현재 {facts.region}에서 확인할 수 있는 {facts.category} 동네 안내는 "
                    f"{facts.detail_count}개이며, {facts.district_count}개 시·군·구로 나누어 정리했습니다."
                ),
            ),
            (
                f"{facts.region}에서 동네 상세페이지를 고를 때 무엇을 비교하나요?",
                (
                    f"{category.focus}를 기준으로 학생의 학년, 최근 평가와 실제 오답 기록이 "
                    "어느 안내와 맞는지 비교한 뒤 해당 동네 페이지로 이동하세요."
                ),
            ),
            (
                f"{scope} 상담 전에 어떤 자료를 준비하면 되나요?",
                (
                    "현재 교재와 최근 평가 자료, 풀이 흔적이나 오답 기록을 준비하면 좋습니다. "
                    "학교 진도와 다음 평가 일정은 실제 재학 학교 기준으로 상담에서 다시 확인합니다."
                ),
            ),
        ]
    else:
        scope = f"{facts.region} {facts.district} {facts.category}"
        heading = f"{scope} 동네 안내를 선택하는 기준"
        intro = (
            f"{facts.region} {facts.district}에 연결된 실제 동네 안내 "
            f"{facts.detail_count}개를 모았습니다. {category.focus} 가운데 현재 학생에게 필요한 "
            "과목·학년 기준을 확인한 뒤 상세페이지를 선택할 수 있습니다."
        )
        faqs = [
            (
                f"{scope}에는 몇 개 동네 안내가 있나요?",
                (
                    f"현재 {facts.region} {facts.district}에서 확인할 수 있는 "
                    f"{facts.category} 동네 안내는 {facts.detail_count}개입니다."
                ),
            ),
            (
                f"{facts.district} 동네 페이지는 어떤 기준으로 선택하나요?",
                (
                    f"{category.focus}를 기준으로 학생의 최근 학습 기록과 필요한 관리 항목이 "
                    "맞는 동네 상세페이지를 선택하세요."
                ),
            ),
            (
                f"{scope} 상담에서 학교 정보는 어떻게 확인하나요?",
                (
                    "허브에서는 동네를 찾고, 학교 진도·교재·시험 범위는 상세페이지의 확인된 자료와 "
                    "학생이 준비한 실제 학교 자료를 함께 보며 상담에서 다시 확인합니다."
                ),
            ),
        ]
    return heading, intro, faqs


def render_hub_section(facts: HubFacts) -> tuple[str, list[tuple[str, str]]]:
    heading, intro, faqs = hub_copy(facts)
    faq_html = "".join(
        (
            "<details>"
            f"<summary>{html.escape(question)}</summary>"
            f"<p>{html.escape(answer)}</p>"
            "</details>"
        )
        for question, answer in faqs
    )
    section = f'''{HUB_MARKER_START}
    <section id="hub-answer" class="section muted split-guide-section" aria-labelledby="hub-answer-title">
      <div class="wrap">
        <div class="section-heading split-section-heading">
          <p class="eyebrow">안내 선택 기준</p>
          <h2 id="hub-answer-title">{html.escape(heading)}</h2>
          <p>{html.escape(intro)}</p>
        </div>
        <div class="faq-list" id="hub-faq-list">
          {faq_html}
        </div>
      </div>
    </section>
    {HUB_MARKER_END}'''
    return section, faqs


def update_hub_json(source: str, facts: HubFacts, faqs: list[tuple[str, str]]) -> str:
    data, match = json_data(source)
    graph = data.get("@graph", [])
    webpage = find_node(graph, "WebPage")
    if not webpage:
        raise ValueError("hub WebPage node missing")
    canonical_url = str(webpage.get("url", "")).rstrip("/") + "/"
    graph[:] = [
        node
        for node in graph
        if not (isinstance(node, dict) and "FAQPage" in type_names(node))
    ]
    graph.append(
        {
            "@type": "FAQPage",
            "@id": canonical_url + "#faq",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": question,
                    "acceptedAnswer": {"@type": "Answer", "text": answer},
                }
                for question, answer in faqs
            ],
            "about": [
                {"@type": "Thing", "name": facts.category},
                *(
                    [{"@type": "Place", "name": " ".join(filter(None, [facts.region, facts.district]))}]
                    if facts.region
                    else []
                ),
            ],
        }
    )
    existing_parts = webpage.get("hasPart", [])
    if not isinstance(existing_parts, list):
        existing_parts = []
    existing_parts = [
        part
        for part in existing_parts
        if not (
            isinstance(part, dict)
            and (
                "#hub-answer" in str(part.get("url", ""))
                or "#hub-faq-list" in str(part.get("url", ""))
                or "#faq" in str(part.get("url", ""))
            )
        )
    ]
    existing_parts.extend(
        [
            {
                "@type": "WebPageElement",
                "name": "지역·학년 안내 선택 기준",
                "url": canonical_url + "#hub-answer",
            },
            {
                "@type": "WebPageElement",
                "name": "자주 묻는 질문",
                "url": canonical_url + "#hub-faq-list",
            },
        ]
    )
    webpage["hasPart"] = existing_parts
    webpage["dateModified"] = TODAY
    return replace_json(source, data, match)


def transform_hub_source(source: str, path: Path, facts: HubFacts) -> str:
    canonical_before = re.search(r'<link rel="canonical" href="([^"]+)"', source)
    hrefs_before = Counter(html.unescape(value) for value in re.findall(r'\bhref="([^"]+)"', source))
    section, faqs = render_hub_section(facts)
    if HUB_MARKER_START in source:
        updated, count = re.subn(
            re.escape(HUB_MARKER_START) + r".*?" + re.escape(HUB_MARKER_END),
            section,
            source,
            count=1,
            flags=re.S,
        )
    else:
        updated, count = re.subn(r"\s*</main>", "\n" + section + "\n  </main>", source, count=1)
    if count != 1:
        raise ValueError("hub answer insertion failed")
    updated = update_hub_json(updated, facts, faqs)

    canonical_after = re.search(r'<link rel="canonical" href="([^"]+)"', updated)
    if not canonical_before or not canonical_after or canonical_before.group(1) != canonical_after.group(1):
        raise ValueError("hub canonical changed")
    hrefs_after = Counter(html.unescape(value) for value in re.findall(r'\bhref="([^"]+)"', updated))
    if hrefs_before != hrefs_after:
        raise ValueError("hub href set changed")
    if visible_faqs(updated) != structured_faqs(updated):
        raise ValueError("hub screen FAQ and FAQPage differ")
    if str(facts.detail_count) not in text_only(section):
        raise ValueError("hub child count missing from answer")
    return updated


def transform_hub(path: Path, facts: HubFacts) -> str:
    source = path.read_text(encoding="utf-8", errors="strict")
    return transform_hub_source(source, path, facts)


def detail_targets() -> list[Path]:
    return sorted(
        path
        for path in CENTER_ROOT.glob("*/*/index.html")
        if 'data-intent-role="' in path.read_text(encoding="utf-8", errors="ignore")
    )


def hub_targets() -> dict[Path, HubFacts]:
    return {
        path: facts
        for path, facts in hub_facts_by_path().items()
        if path.exists()
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="write changes; default is dry-run")
    parser.add_argument("--kind", choices=("detail", "hub", "all"), default="all")
    parser.add_argument("--offset", type=int, default=0, help="skip the first N targets")
    parser.add_argument("--limit", type=int, default=0, help="process only the first N targets")
    args = parser.parse_args()

    targets: list[tuple[str, Path, HubFacts | None]] = []
    if args.kind in ("detail", "all"):
        targets.extend(("detail", path, None) for path in detail_targets())
    if args.kind in ("hub", "all"):
        targets.extend(("hub", path, facts) for path, facts in sorted(hub_targets().items()))
    if args.offset:
        targets = targets[args.offset :]
    if args.limit:
        targets = targets[: args.limit]

    centers = load_centers()
    changed = 0
    unchanged = 0
    errors: list[str] = []
    by_kind = Counter()
    samples: list[str] = []
    for kind, path, facts in targets:
        try:
            source = path.read_text(encoding="utf-8", errors="strict")
            updated = (
                transform_detail(path, centers)
                if kind == "detail"
                else transform_hub(path, facts)  # type: ignore[arg-type]
            )
            by_kind[kind] += 1
            if updated == source:
                unchanged += 1
            else:
                changed += 1
                if len(samples) < 8:
                    samples.append(str(path.relative_to(CENTER_ROOT)))
                if args.apply:
                    path.write_text(updated, encoding="utf-8", newline="\n")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{path}: {exc}")
            if len(errors) <= 20:
                print("ERROR", errors[-1])

    print(
        json.dumps(
            {
                "mode": "apply" if args.apply else "dry-run",
                "targets": len(targets),
                "processed_by_kind": dict(by_kind),
                "changed": changed,
                "unchanged": unchanged,
                "errors": len(errors),
                "samples": samples,
                "sample_errors": errors[:10],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
