#!/usr/bin/env python3
"""Add page-specific anchor navigation to subject academy detail pages.

The site stores subject pages below ``전국센터`` rather than ``과목별학원``.
Only math, English, and combined English-math detail pages are targeted; grade-
intent pages and every hub remain untouched.  Existing section IDs and
``WebPage.hasPart`` fragments are reused, so the visible manuscript, metadata,
images, and JSON-LD do not need to be rewritten.

Run this idempotent postprocessor again after a full detail-page regeneration.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
CENTER_ROOT = ROOT / "전국센터"
SUBJECT_CATEGORIES = ("수학학원", "영어학원", "영수학원")
TARGET_IDS = (
    "geo-summary",
    "geo-answer",
    "geo-checklist",
    "consultation-cases",
    "faq-section",
    "internal-links",
)

STYLE_MARKER = "<!-- subject-page-anchor-toc:style -->"
STYLE_HREF = "../../../assets/subject-anchor-toc.css"
STYLE_LINK = f'<link rel="stylesheet" href="{STYLE_HREF}">'
TOC_START = "<!-- subject-page-anchor-toc:start -->"
TOC_END = "<!-- subject-page-anchor-toc:end -->"
SEO_START = "<!-- seo-geo-enhancement:start -->"

TOC_BLOCK_RE = re.compile(
    rf"^[ \t]*{re.escape(TOC_START)}\r?\n.*?"
    rf"^[ \t]*{re.escape(TOC_END)}\r?\n",
    re.IGNORECASE | re.DOTALL | re.MULTILINE,
)
TOC_CAPTURE_RE = re.compile(
    rf"{re.escape(TOC_START)}.*?{re.escape(TOC_END)}",
    re.IGNORECASE | re.DOTALL,
)
SITE_CSS_RE = re.compile(
    r'(?P<indent>^[ \t]*)<link\s+rel=["\']stylesheet["\']\s+'
    r'href=["\']\.\./\.\./\.\./assets/site\.css["\']\s*>' ,
    re.IGNORECASE | re.MULTILINE,
)
STYLE_BLOCK_RE = re.compile(
    rf"^[ \t]*{re.escape(STYLE_MARKER)}\r?\n"
    rf'[ \t]*<link\s+rel=["\']stylesheet["\']\s+'
    rf'href=["\']{re.escape(STYLE_HREF)}["\']\s*>\r?\n?',
    re.IGNORECASE | re.MULTILINE,
)
OPEN_TAG_RE = re.compile(
    r"<(?P<tag>section|article)\b(?P<attrs>[^>]*)>", re.IGNORECASE
)
H2_RE = re.compile(r"<h2\b[^>]*>(?P<body>.*?)</h2>", re.IGNORECASE | re.DOTALL)
CLASS_RE = re.compile(
    r'\bclass\s*=\s*(["\'])(?P<class_names>[^"\']+)\1', re.IGNORECASE
)
ID_RE = re.compile(r'\bid\s*=\s*(["\'])(?P<id>[^"\']+)\1', re.IGNORECASE)
ANY_ID_RE = re.compile(
    r'\bid\s*=\s*(["\'])(?P<id>[^"\']+)\1', re.IGNORECASE
)
JSON_LD_RE = re.compile(
    r'<script\b[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)
TOC_LINK_RE = re.compile(
    r'<a href="#(?P<id>[^"]+)">.*?'
    r'<span class="subject-page-toc-text">(?P<label>.*?)</span>\s*</a>',
    re.IGNORECASE | re.DOTALL,
)


@dataclass(frozen=True)
class TocTarget:
    target_id: str
    text: str
    start: int
    closing_end: int


def visible_text(fragment: str) -> str:
    text = re.sub(r"<[^>]+>", " ", fragment)
    return " ".join(html.unescape(text).split())


def class_names(attrs: str) -> set[str]:
    match = CLASS_RE.search(attrs)
    return set(match.group("class_names").split()) if match else set()


def element_id(attrs: str) -> str | None:
    match = ID_RE.search(attrs)
    return match.group("id") if match else None


def detect_newline(source: str) -> str:
    if "\r\n" in source:
        if source.replace("\r\n", "").find("\n") != -1:
            raise ValueError("Mixed newline styles")
        return "\r\n"
    return "\n"


def detail_pages() -> list[Path]:
    result: list[Path] = []
    for category in SUBJECT_CATEGORIES:
        category_root = CENTER_ROOT / category
        if not category_root.exists():
            continue
        for path in category_root.glob("*/index.html"):
            source = path.read_text(encoding="utf-8")
            if (
                'data-intent-role="' in source
                and all(f'id="{target_id}"' in source for target_id in TARGET_IDS)
            ):
                result.append(path)
    return sorted(result, key=lambda path: path.as_posix())


def matching_tag_end(source: str, opening: re.Match[str]) -> int | None:
    tag = opening.group("tag")
    token_re = re.compile(rf"</?{tag}\b[^>]*>", re.IGNORECASE)
    depth = 0
    for match in token_re.finditer(source, opening.start()):
        if match.group(0).lower().startswith(f"</{tag}"):
            depth -= 1
            if depth == 0:
                return match.end()
        else:
            depth += 1
    return None


def select_targets(source: str) -> list[TocTarget]:
    found: dict[str, TocTarget] = {}
    for opening in OPEN_TAG_RE.finditer(source):
        target_id = element_id(opening.group("attrs"))
        if target_id not in TARGET_IDS:
            continue
        closing_end = matching_tag_end(source, opening)
        if closing_end is None:
            raise ValueError(f"Closing tag not found for {target_id}")
        heading = H2_RE.search(source, opening.end(), closing_end)
        if not heading:
            raise ValueError(f"H2 not found inside {target_id}")
        label = visible_text(heading.group("body"))
        if not label:
            raise ValueError(f"Empty H2 inside {target_id}")
        if target_id in found:
            raise ValueError(f"Duplicate target {target_id}")
        found[target_id] = TocTarget(target_id, label, opening.start(), closing_end)

    missing = [target_id for target_id in TARGET_IDS if target_id not in found]
    if missing:
        raise ValueError(f"Missing targets: {missing}")
    targets = [found[target_id] for target_id in TARGET_IDS]
    if [target.start for target in targets] != sorted(target.start for target in targets):
        raise ValueError("Target order does not match the expected reading order")
    return targets


def webpage_parts(source: str) -> list[str]:
    webpages: list[dict] = []
    for script in JSON_LD_RE.findall(source):
        data = json.loads(script)
        roots = data if isinstance(data, list) else [data]
        nodes: list[object] = []
        for root in roots:
            if isinstance(root, dict) and isinstance(root.get("@graph"), list):
                nodes.extend(root["@graph"])
            else:
                nodes.append(root)
        for node in nodes:
            if not isinstance(node, dict):
                continue
            kinds = node.get("@type", [])
            kinds = [kinds] if isinstance(kinds, str) else kinds
            if "WebPage" in kinds and isinstance(node.get("hasPart"), list):
                webpages.append(node)
    if len(webpages) != 1:
        raise ValueError(f"WebPage with hasPart count is {len(webpages)}")
    return [
        urlsplit(str(part.get("url", ""))).fragment
        for part in webpages[0]["hasPart"]
        if isinstance(part, dict)
    ]


def seo_section_start(source: str) -> int | None:
    for opening in OPEN_TAG_RE.finditer(source):
        if opening.group("tag").lower() != "section":
            continue
        classes = class_names(opening.group("attrs"))
        if {"seo-geo-section", "intent-role-section"}.issubset(classes):
            return opening.start()
    return None


def seo_marker_start(source: str) -> int | None:
    if source.count(SEO_START) != 1:
        return None
    return source.index(SEO_START)


def ensure_style_link(source: str, newline: str) -> str:
    if STYLE_MARKER in source:
        if len(STYLE_BLOCK_RE.findall(source)) != 1:
            raise ValueError("Existing TOC stylesheet marker is malformed")
        return source
    matches = list(SITE_CSS_RE.finditer(source))
    if len(matches) != 1:
        raise ValueError(f"Main stylesheet link count is {len(matches)}")
    match = matches[0]
    addition = (
        newline
        + match.group("indent")
        + STYLE_MARKER
        + newline
        + match.group("indent")
        + STYLE_LINK
    )
    return source[: match.end()] + addition + source[match.end() :]


def toc_markup(targets: list[TocTarget], indent: str, newline: str) -> str:
    child = indent + "  "
    grandchild = child + "  "
    item_indent = grandchild + "  "
    lines = [
        indent + TOC_START,
        indent
        + '<nav class="subject-page-toc" aria-labelledby="subject-page-toc-title">',
        child + '<div class="wrap subject-page-toc-shell">',
        grandchild + '<div class="subject-page-toc-heading">',
        item_indent + '<p class="eyebrow">PAGE CONTENTS</p>',
        item_indent + '<strong id="subject-page-toc-title">상담 안내 목차</strong>',
        grandchild + "</div>",
        grandchild + '<ol class="subject-page-toc-list">',
    ]
    for index, target in enumerate(targets, start=1):
        lines.append(
            item_indent
            + "<li>"
            + f'<a href="#{html.escape(target.target_id, quote=True)}">'
            + f'<span class="subject-page-toc-number" aria-hidden="true">{index:02d}</span>'
            + f'<span class="subject-page-toc-text">{html.escape(target.text)}</span>'
            + "</a></li>"
        )
    lines.extend(
        [
            grandchild + "</ol>",
            child + "</div>",
            indent + "</nav>",
            indent + TOC_END,
        ]
    )
    return newline.join(lines) + newline


def render_page(original: str) -> tuple[str, int]:
    source = TOC_BLOCK_RE.sub("", original, count=1)
    newline = detect_newline(source)
    source = ensure_style_link(source, newline)
    targets = select_targets(source)
    if webpage_parts(source) != list(TARGET_IDS):
        raise ValueError("Visible anchor targets and WebPage.hasPart do not match")

    insertion_point = seo_marker_start(source)
    if insertion_point is None:
        raise ValueError("SEO enhancement start marker not found")
    line_start = source.rfind(newline, 0, insertion_point) + len(newline)
    indent = source[line_start:insertion_point]
    if indent.strip():
        raise ValueError("SEO content section does not begin on its own line")
    rendered = (
        source[:line_start]
        + toc_markup(targets, indent, newline)
        + source[line_start:]
    )
    return rendered, len(targets)


def validate_page(source: str) -> list[str]:
    errors: list[str] = []
    if source.count(STYLE_MARKER) != 1 or source.count(STYLE_HREF) != 1:
        errors.append("TOC stylesheet marker or link count is not exactly one")
    if source.count(TOC_START) != 1 or source.count(TOC_END) != 1:
        errors.append("TOC marker count is not exactly one")
    toc = TOC_CAPTURE_RE.search(source)
    if not toc:
        errors.append("TOC block missing")
        return errors

    try:
        targets = select_targets(source)
    except Exception as exc:  # noqa: BLE001
        errors.append(str(exc))
        return errors
    expected = [(target.target_id, target.text) for target in targets]
    links = [
        (match.group("id"), visible_text(match.group("label")))
        for match in TOC_LINK_RE.finditer(toc.group(0))
    ]
    if links != expected:
        errors.append("TOC links or labels do not match visible H2 headings")
    try:
        if webpage_parts(source) != [target.target_id for target in targets]:
            errors.append("TOC targets do not match WebPage.hasPart")
    except Exception as exc:  # noqa: BLE001
        errors.append(str(exc))

    all_ids = [match.group("id") for match in ANY_ID_RE.finditer(source)]
    if all_ids.count("subject-page-toc-title") != 1:
        errors.append("TOC title ID count is not exactly one")
    for target_id, _ in links:
        if all_ids.count(target_id) != 1:
            errors.append(
                f"Anchor target count for {target_id!r} is {all_ids.count(target_id)}"
            )

    marker_start = seo_marker_start(source)
    section_start = seo_section_start(source)
    if marker_start is None or toc.end() > marker_start:
        errors.append("TOC is not before the SEO enhancement marker")
    elif source[toc.end() : marker_start].strip():
        errors.append("Unexpected content appears between TOC and SEO marker")
    if section_start is None or marker_start is None or marker_start > section_start:
        errors.append("SEO enhancement marker or content section order is invalid")
    return errors


def process(write: bool) -> int:
    pages = detail_pages()
    if len(pages) != 4452:
        print(f"ERROR expected 4452 subject detail pages, found {len(pages)}")
        return 1

    changed = 0
    validated = 0
    distribution: Counter[int] = Counter()
    categories: Counter[str] = Counter()
    failures: list[str] = []

    for path in pages:
        try:
            raw = path.read_bytes()
            if raw.startswith(b"\xef\xbb\xbf"):
                raise ValueError("UTF-8 BOM is not supported")
            original = raw.decode("utf-8")
            rendered, target_count = render_page(original)
            page_errors = validate_page(rendered)
            if page_errors:
                raise ValueError("; ".join(page_errors))
            if rendered != original:
                changed += 1
                if write:
                    path.write_bytes(rendered.encode("utf-8"))
            distribution[target_count] += 1
            categories[path.relative_to(CENTER_ROOT).parts[0]] += 1
            validated += 1
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{path.relative_to(ROOT).as_posix()}: {exc}")

    print(f"pages={len(pages)} validated={validated}")
    print(
        "toc_link_distribution="
        + ",".join(f"{count}:{pages_count}" for count, pages_count in sorted(distribution.items()))
    )
    print(f"toc_links_total={sum(count * pages_count for count, pages_count in distribution.items())}")
    print(
        "categories="
        + ",".join(f"{name}:{count}" for name, count in sorted(categories.items()))
    )
    print(f"changed={changed} mode={'write' if write else 'dry-run'}")
    for failure in failures[:50]:
        print("ERROR", failure)
    if len(failures) > 50:
        print(f"ERROR ... and {len(failures) - 50} more")
    return 1 if failures else 0


def main() -> None:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true", help="Apply/update TOCs")
    mode.add_argument("--check", action="store_true", help="Validate idempotence")
    args = parser.parse_args()
    raise SystemExit(process(write=args.write))


if __name__ == "__main__":
    main()
