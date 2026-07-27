from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from audit_faq_consistency_site4 import (
    JSON_LD_RE,
    ROOT,
    is_detail_page,
    node_has_type,
    visible_faq_pairs,
)


def faq_entity(question: str, answer: str) -> dict[str, Any]:
    return {
        "@type": "Question",
        "name": question,
        "acceptedAnswer": {"@type": "Answer", "text": answer},
    }


def remove_faq_references(value: Any) -> None:
    if isinstance(value, dict):
        has_part = value.get("hasPart")
        if isinstance(has_part, list):
            value["hasPart"] = [
                item
                for item in has_part
                if not (
                    isinstance(item, dict)
                    and (
                        str(item.get("url", "")).rstrip("/").endswith("#faq")
                        or item.get("name") == "자주 묻는 질문"
                    )
                )
            ]
        for child in value.values():
            remove_faq_references(child)
    elif isinstance(value, list):
        for child in value:
            remove_faq_references(child)


def sync_jsonld(data: Any, visible: list[tuple[str, str]]) -> tuple[Any, bool]:
    if not isinstance(data, dict):
        return data, False

    changed = False
    graph = data.get("@graph")
    if isinstance(graph, list):
        faq_nodes = [node for node in graph if isinstance(node, dict) and node_has_type(node, "FAQPage")]
        if visible:
            if faq_nodes:
                faq_node = faq_nodes[0]
            else:
                faq_node = {"@type": "FAQPage"}
            expected = [faq_entity(question, answer) for question, answer in visible]
            if faq_node.get("mainEntity") != expected:
                faq_node["mainEntity"] = expected
                changed = True
            new_graph = []
            inserted = False
            for node in graph:
                if isinstance(node, dict) and node_has_type(node, "FAQPage"):
                    if not inserted:
                        new_graph.append(faq_node)
                        inserted = True
                    continue
                new_graph.append(node)
            if not inserted:
                new_graph.append(faq_node)
            # Keep the established graph order: visible FAQ before the page article.
            if faq_node in new_graph:
                article_index = next(
                    (
                        index
                        for index, node in enumerate(new_graph)
                        if isinstance(node, dict) and node_has_type(node, "Article")
                    ),
                    None,
                )
                faq_index = new_graph.index(faq_node)
                if article_index is not None and faq_index > article_index:
                    new_graph.pop(faq_index)
                    new_graph.insert(article_index, faq_node)
            if graph != new_graph:
                data["@graph"] = new_graph
                changed = True
        else:
            non_faq_nodes = [
                node for node in graph if not (isinstance(node, dict) and node_has_type(node, "FAQPage"))
            ]
            if faq_nodes:
                data["@graph"] = non_faq_nodes
                changed = True
            before = json.dumps(data, ensure_ascii=False, sort_keys=True)
            remove_faq_references(data)
            if json.dumps(data, ensure_ascii=False, sort_keys=True) != before:
                changed = True
    elif node_has_type(data, "FAQPage"):
        if visible:
            expected = [faq_entity(question, answer) for question, answer in visible]
            if data.get("mainEntity") != expected:
                data["mainEntity"] = expected
                changed = True
        else:
            raise ValueError("A standalone structured-only FAQPage cannot be removed without removing its script")
    return data, changed


def sync_page(path: Path) -> bool:
    source = path.read_text(encoding="utf-8")
    visible = visible_faq_pairs(source)
    changed = False

    def replace(match):
        nonlocal changed
        data = json.loads(match.group(1))
        updated, json_changed = sync_jsonld(data, visible)
        if not json_changed:
            return match.group(0)
        changed = True
        encoded = json.dumps(updated, ensure_ascii=False, separators=(",", ":"))
        return match.group(0).replace(match.group(1), encoded, 1)

    updated = JSON_LD_RE.sub(replace, source)
    if changed:
        path.write_text(updated, encoding="utf-8")
    return changed


def main() -> None:
    pages = [path for path in sorted(ROOT.rglob("index.html")) if not is_detail_page(path)]
    changed = []
    for path in pages:
        if sync_page(path):
            changed.append(path.relative_to(ROOT).as_posix())
    print(f"general_pages={len(pages)} changed={len(changed)}")
    for relative in changed:
        print(f"synced {relative}")


if __name__ == "__main__":
    main()
