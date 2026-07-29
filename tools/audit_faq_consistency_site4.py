from __future__ import annotations

import argparse
import html
import json
import re
import sys
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CENTER_ROOT = ROOT / "전국센터"
JSON_LD_RE = re.compile(
    r'<script\b[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def node_has_type(node: dict[str, Any], type_name: str) -> bool:
    value = node.get("@type")
    if isinstance(value, list):
        return type_name in value
    return value == type_name


def iter_json_nodes(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from iter_json_nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_json_nodes(child)


class VisibleFaqParser(HTMLParser):
    """Read Question/Answer pairs only from an explicitly marked FAQ region."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.faq_roots: list[int] = []
        self.details_depth: int | None = None
        self.capture: str | None = None
        self.buffer: list[str] = []
        self.question = ""
        self.answer_parts: list[str] = []
        self.pairs: list[tuple[str, str]] = []

    @property
    def in_faq(self) -> bool:
        return bool(self.faq_roots)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.depth += 1
        attr = {key.lower(): (value or "") for key, value in attrs}
        classes = set(attr.get("class", "").split())
        region = attr.get("id", "").lower() == "faq" or bool(
            classes.intersection({"faq-list", "faq-section", "faq-wrap", "faq-grid"})
        )
        if region:
            self.faq_roots.append(self.depth)

        if self.in_faq and tag == "details":
            self.details_depth = self.depth
            self.question = ""
            self.answer_parts = []
        elif self.details_depth is not None and tag == "summary":
            self.capture = "question"
            self.buffer = []
        elif self.details_depth is not None and tag in {"p", "div", "span", "li"}:
            if self.capture is None:
                self.capture = "answer"
                self.buffer = []
        elif self.in_faq and tag in {"dt", "h3", "h4"}:
            self.capture = "question"
            self.buffer = []
        elif self.in_faq and tag == "dd":
            self.capture = "answer"
            self.buffer = []

    def handle_data(self, data: str) -> None:
        if self.capture:
            self.buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self.capture == "question" and tag in {"summary", "dt", "h3", "h4"}:
            self.question = clean_text(" ".join(self.buffer))
            self.capture = None
            self.buffer = []
        elif self.capture == "answer" and tag in {"p", "div", "span", "li", "dd"}:
            answer = clean_text(" ".join(self.buffer))
            if answer:
                self.answer_parts.append(answer)
            self.capture = None
            self.buffer = []

        if tag == "details" and self.details_depth is not None:
            answer = clean_text(" ".join(self.answer_parts))
            if self.question and answer:
                self.pairs.append((self.question, answer))
            self.details_depth = None
            self.question = ""
            self.answer_parts = []

        if self.faq_roots and self.depth == self.faq_roots[-1]:
            self.faq_roots.pop()
        self.depth -= 1


def visible_faq_pairs(source: str) -> list[tuple[str, str]]:
    parser = VisibleFaqParser()
    parser.feed(source)
    return parser.pairs


def json_faq_pairs(source: str) -> tuple[list[tuple[str, str]], int, list[str]]:
    pairs: list[tuple[str, str]] = []
    faq_count = 0
    errors: list[str] = []
    for index, raw in enumerate(JSON_LD_RE.findall(source), start=1):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            errors.append(f"json-ld[{index}] parse error: {exc}")
            continue
        for node in iter_json_nodes(data):
            if not node_has_type(node, "FAQPage"):
                continue
            faq_count += 1
            for entity in node.get("mainEntity", []):
                if not isinstance(entity, dict) or not node_has_type(entity, "Question"):
                    continue
                accepted = entity.get("acceptedAnswer", {})
                if not isinstance(accepted, dict):
                    accepted = {}
                pairs.append(
                    (clean_text(str(entity.get("name", ""))), clean_text(str(accepted.get("text", ""))))
                )
    return pairs, faq_count, errors


def is_detail_page(path: Path) -> bool:
    try:
        relative = path.relative_to(CENTER_ROOT)
    except ValueError:
        return False
    return (
        len(relative.parts) == 3
        and relative.name == "index.html"
        and 'data-intent-role="' in path.read_text(encoding="utf-8", errors="ignore")
    )


@dataclass
class Result:
    path: Path
    visible: list[tuple[str, str]]
    structured: list[tuple[str, str]]
    faq_nodes: int
    errors: list[str]

    @property
    def mismatch(self) -> bool:
        return bool(self.errors) or self.visible != self.structured or self.faq_nodes > 1

    @property
    def reason(self) -> str:
        reasons = list(self.errors)
        if self.faq_nodes > 1:
            reasons.append(f"FAQPage nodes={self.faq_nodes}")
        if self.visible and not self.structured:
            reasons.append("visible-only FAQ")
        elif self.structured and not self.visible:
            reasons.append("structured-only FAQ")
        elif self.visible != self.structured:
            reasons.append("question/answer mismatch")
        return "; ".join(reasons) or "ok"


def audit(scope: str) -> list[Result]:
    results: list[Result] = []
    for path in sorted(ROOT.rglob("index.html")):
        detail = is_detail_page(path)
        if scope == "detail" and not detail:
            continue
        if scope == "general" and detail:
            continue
        source = path.read_text(encoding="utf-8")
        structured, nodes, errors = json_faq_pairs(source)
        results.append(Result(path, visible_faq_pairs(source), structured, nodes, errors))
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope", choices=("all", "general", "detail"), default="all")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    results = audit(args.scope)
    mismatches = [result for result in results if result.mismatch]
    structured_only = [result for result in results if result.structured and not result.visible]
    visible_only = [result for result in results if result.visible and not result.structured]

    print(
        f"scope={args.scope} pages={len(results)} mismatches={len(mismatches)} "
        f"structured_only={len(structured_only)} visible_only={len(visible_only)}"
    )
    if not args.quiet:
        for result in mismatches:
            relative = result.path.relative_to(ROOT)
            print(
                f"MISMATCH {relative.as_posix()} visible={len(result.visible)} "
                f"structured={len(result.structured)} nodes={result.faq_nodes} reason={result.reason}"
            )
    return 1 if mismatches else 0


if __name__ == "__main__":
    sys.exit(main())
