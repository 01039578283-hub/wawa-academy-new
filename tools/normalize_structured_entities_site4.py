from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from add_center_info_site4 import extract_dong, load_center_info


ROOT = Path(__file__).resolve().parents[1]
CENTER_ROOT = ROOT / "전국센터"
DOMAIN = "https://xn--ol5ba64b839b.com"
ROOT_ORG_ID = f"{DOMAIN}/#organization"
SITE_NAME = "와와학습코칭학원"
HOME_LABEL = "홈"
ROOT_ALTERNATE_NAMES = ["와와학습코칭학원", "와와학습코칭센터", "와와학원", "와와학원.com"]

JSONLD_RE = re.compile(
    r'<script\b[^>]*\btype=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.I | re.S,
)
VISIBLE_BREADCRUMB_RE = re.compile(
    r'<nav\b[^>]*\bclass=["\'][^"\']*\bseo-breadcrumb\b[^"\']*["\'][^>]*>(.*?)</nav>',
    re.I | re.S,
)
FIRST_LINK_RE = re.compile(r"<a\b[^>]*>(.*?)</a>", re.I | re.S)
TAG_RE = re.compile(r"<[^>]+>")


def type_names(node: dict) -> list[str]:
    value = node.get("@type")
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)] if value else []


def compact_text(value: object) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(value or "")).strip())


def identity_text(branch: dict) -> str:
    registration = compact_text(branch.get("교육지원청 등록번호")).casefold()
    address = compact_text(branch.get("센터 주소")).casefold()
    if not registration or not address:
        raise ValueError("센터 등록번호 또는 주소가 비어 있습니다.")
    return f"{registration}\n{address}"


def stable_branch_id(branch: dict) -> str:
    digest = hashlib.sha256(identity_text(branch).encode("utf-8")).hexdigest()[:20]
    return f"{DOMAIN}/#branch-{digest}"


def find_branch_node(graph: list[dict]) -> tuple[int, dict]:
    local_business = [
        (index, node)
        for index, node in enumerate(graph)
        if isinstance(node, dict) and "LocalBusiness" in type_names(node)
    ]
    if len(local_business) != 1:
        raise ValueError(f"LocalBusiness branch node가 1개가 아닙니다: {len(local_business)}")
    return local_business[0]


def find_node_by_id(graph: list[dict], node_id: str) -> tuple[int, dict] | None:
    for index, node in enumerate(graph):
        if isinstance(node, dict) and node.get("@id") == node_id:
            return index, node
    return None


def replace_id_references(value: object, old_id: str, new_id: str) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "@id" and item == old_id:
                value[key] = new_id
            else:
                replace_id_references(item, old_id, new_id)
    elif isinstance(value, list):
        for item in value:
            replace_id_references(item, old_id, new_id)


def stable_alternate_names(branch: dict) -> list[str]:
    names = [
        compact_text(branch.get("교육지원청명칭")),
        *ROOT_ALTERNATE_NAMES,
    ]
    return list(dict.fromkeys(name for name in names if name and name != compact_text(branch.get("센터명"))))


def normalize_branch_node(data: dict, branch: dict) -> tuple[str, str]:
    graph = data.get("@graph")
    if not isinstance(graph, list):
        raise ValueError("JSON-LD @graph가 없습니다.")

    branch_index, organization = find_branch_node(graph)
    old_id = str(organization.get("@id") or "")
    new_id = stable_branch_id(branch)
    if old_id and old_id != new_id:
        replace_id_references(data, old_id, new_id)

    organization["@type"] = ["EducationalOrganization", "LocalBusiness"]
    organization["@id"] = new_id
    organization["name"] = compact_text(branch.get("센터명"))
    organization.pop("url", None)

    # 검색어·과목·학년은 페이지와 서비스의 주제입니다. 실제 센터 엔터티에는
    # 등록 자료로 확인되는 안정적인 사실만 남겨 같은 센터가 페이지마다
    # 다른 조직으로 보이지 않게 합니다. Review 계열은 별도 담당 범위이므로 보존합니다.
    for key in ("knowsAbout", "about", "mentions", "makesOffer", "offers"):
        organization.pop(key, None)

    organization["areaServed"] = {
        "@type": "Place",
        "name": " ".join(
            value
            for value in (
                compact_text(branch.get("지역")),
                compact_text(branch.get("시or구")),
            )
            if value
        ),
    }
    organization["alternateName"] = stable_alternate_names(branch)
    organization["branchOf"] = {"@id": ROOT_ORG_ID}
    organization["address"] = {
        "@type": "PostalAddress",
        "streetAddress": compact_text(branch.get("센터 주소")),
        "addressRegion": compact_text(branch.get("지역")),
        "addressLocality": compact_text(branch.get("시or구")),
        "addressCountry": "KR",
    }
    organization["identifier"] = {
        "@type": "PropertyValue",
        "propertyID": "교육지원청 등록번호",
        "value": compact_text(branch.get("교육지원청 등록번호")),
    }

    # The root organization is authoritatively defined once in the homepage
    # graph. Detail graphs reference that stable @id instead of duplicating
    # another root entity on every one of the 8,904 service pages.
    graph[:] = [
        node
        for index, node in enumerate(graph)
        if index == branch_index or not (isinstance(node, dict) and node.get("@id") == ROOT_ORG_ID)
    ]
    return old_id, new_id


def visible_home_label(source: str) -> str:
    match = VISIBLE_BREADCRUMB_RE.search(source)
    if not match:
        raise ValueError("화면 seo-breadcrumb를 찾지 못했습니다.")
    first = FIRST_LINK_RE.search(match.group(1))
    if not first:
        raise ValueError("화면 breadcrumb 첫 링크를 찾지 못했습니다.")
    return compact_text(html.unescape(TAG_RE.sub("", first.group(1))))


def normalize_breadcrumb_node(source: str, data: dict) -> str:
    label = visible_home_label(source)
    if label != HOME_LABEL:
        raise ValueError(f"화면 breadcrumb 첫 라벨이 '{HOME_LABEL}'이 아닙니다: {label!r}")
    graph = data.get("@graph")
    breadcrumbs = [
        node
        for node in graph or []
        if isinstance(node, dict) and "BreadcrumbList" in type_names(node)
    ]
    if len(breadcrumbs) != 1:
        raise ValueError(f"BreadcrumbList가 1개가 아닙니다: {len(breadcrumbs)}")
    items = breadcrumbs[0].get("itemListElement")
    if not isinstance(items, list) or not items:
        raise ValueError("BreadcrumbList itemListElement가 비어 있습니다.")
    items[0]["name"] = label
    return label


def page_branch(path: Path, center_info: dict[str, dict]) -> dict:
    category = path.parent.parent.name
    leaf = path.parent.name
    dong = extract_dong(category, leaf)
    if not dong:
        raise ValueError(f"동네명을 추출하지 못했습니다: {path}")
    key = dong.replace(" ", "")
    if key not in center_info:
        raise KeyError(f"센터 정보가 없습니다: {dong}")
    return center_info[key]


def transform_html(source: str, branch: dict | None) -> tuple[str, dict]:
    match = JSONLD_RE.search(source)
    if not match:
        raise ValueError("JSON-LD script를 찾지 못했습니다.")
    data = json.loads(match.group(1))
    old_id = new_id = None
    if branch is not None:
        old_id, new_id = normalize_branch_node(data, branch)
    label = normalize_breadcrumb_node(source, data)
    rendered = (
        '<script type="application/ld+json">'
        + json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        + "</script>"
    )
    updated = source[: match.start()] + rendered + source[match.end() :]
    return updated, {
        "branch_old_id": old_id,
        "branch_new_id": new_id,
        "breadcrumb_first_name": label,
    }


def validate_transformed(source: str, branch: dict | None) -> None:
    match = JSONLD_RE.search(source)
    if not match:
        raise ValueError("변환 후 JSON-LD script 누락")
    data = json.loads(match.group(1))
    graph = data.get("@graph", [])
    breadcrumb = [
        node
        for node in graph
        if isinstance(node, dict) and "BreadcrumbList" in type_names(node)
    ]
    if len(breadcrumb) != 1 or breadcrumb[0]["itemListElement"][0].get("name") != HOME_LABEL:
        raise ValueError("변환 후 화면/JSON breadcrumb 첫 라벨 불일치")
    if branch is None:
        return

    _, organization = find_branch_node(graph)
    expected_id = stable_branch_id(branch)
    if organization.get("@id") != expected_id:
        raise ValueError("안정적 branch @id 불일치")
    if organization.get("name") != compact_text(branch.get("센터명")):
        raise ValueError("실제 센터명 불일치")
    if organization.get("branchOf", {}).get("@id") != ROOT_ORG_ID:
        raise ValueError("branchOf 불일치")
    if find_node_by_id(graph, ROOT_ORG_ID) is not None:
        raise ValueError("상세 graph에 root organization 중복 정의가 남았습니다.")
    for key in ("knowsAbout", "about", "mentions", "makesOffer", "offers"):
        if key in organization:
            raise ValueError(f"branch org에 페이지 키워드 속성이 남았습니다: {key}")


@dataclass
class Result:
    targets: int = 0
    detail_targets: int = 0
    changed: int = 0
    branch_changed: int = 0
    breadcrumb_changed: int = 0
    errors: int = 0
    non_idempotent: int = 0
    expected_unique_branches: int = 0
    observed_unique_branches: int = 0
    branch_name_conflicts: int = 0


def validate_homepage_root() -> None:
    source = (ROOT / "index.html").read_text(encoding="utf-8", errors="strict")
    match = JSONLD_RE.search(source)
    if not match:
        raise ValueError("홈페이지 JSON-LD script를 찾지 못했습니다.")
    data = json.loads(match.group(1))
    graph = data.get("@graph", [])
    root_match = find_node_by_id(graph, ROOT_ORG_ID)
    if root_match is None:
        raise ValueError("홈페이지 graph에 root organization @id가 없습니다.")
    _, node = root_match
    if "EducationalOrganization" not in type_names(node):
        raise ValueError("홈페이지 root organization의 @type이 EducationalOrganization이 아닙니다.")


def validate_center_identity_map(center_info: dict[str, dict]) -> int:
    by_id: dict[str, tuple[str, str]] = {}
    for dong, branch in center_info.items():
        branch_id = stable_branch_id(branch)
        identity = identity_text(branch)
        name = compact_text(branch.get("센터명"))
        if not name:
            raise ValueError(f"실제 센터명이 비어 있습니다: {dong}")
        previous = by_id.get(branch_id)
        if previous and previous != (identity, name):
            raise ValueError(f"branch hash 충돌 또는 센터명 불일치: {dong}, {branch_id}")
        by_id[branch_id] = (identity, name)
    return len(by_id)


def target_pages(dong: str | None = None) -> list[Path]:
    details: list[Path] = []
    hubs: list[Path] = []
    normalized_dong = compact_text(dong).replace(" ", "") if dong else None
    for path in sorted(CENTER_ROOT.rglob("index.html")):
        source = path.read_text(encoding="utf-8", errors="ignore")
        is_detail = 'data-intent-role="' in source
        if normalized_dong:
            if not is_detail:
                continue
            if normalized_dong not in path.parent.name.replace(" ", ""):
                continue
        (details if is_detail else hubs).append(path)
    return details + hubs


def run(*, apply: bool, limit: int | None = None, dong: str | None = None) -> Result:
    validate_homepage_root()
    center_info = load_center_info()
    paths = target_pages(dong=dong)
    if limit is not None:
        paths = paths[:limit]
    result = Result(
        targets=len(paths),
        expected_unique_branches=validate_center_identity_map(center_info),
    )
    observed: dict[str, str] = {}

    for path in paths:
        try:
            source = path.read_text(encoding="utf-8", errors="strict")
            is_detail = 'data-intent-role="' in source
            branch = page_branch(path, center_info) if is_detail else None
            if is_detail:
                result.detail_targets += 1
            updated, info = transform_html(source, branch)
            validate_transformed(updated, branch)
            second, _ = transform_html(updated, branch)
            if second != updated:
                result.non_idempotent += 1
                raise ValueError("두 번째 실행 결과가 달라 멱등성이 깨졌습니다.")
            if updated != source:
                result.changed += 1
                if info["branch_old_id"] and info["branch_old_id"] != info["branch_new_id"]:
                    result.branch_changed += 1
                if '"name":"와와학습코칭학원","item":' in source:
                    result.breadcrumb_changed += 1
                if apply:
                    path.write_text(updated, encoding="utf-8")
            if branch is not None:
                branch_id = str(info["branch_new_id"])
                branch_name = compact_text(branch.get("센터명"))
                previous_name = observed.get(branch_id)
                if previous_name is not None and previous_name != branch_name:
                    result.branch_name_conflicts += 1
                    raise ValueError(f"같은 branch @id에 센터명이 다릅니다: {branch_id}")
                observed[branch_id] = branch_name
        except Exception as exc:  # noqa: BLE001
            result.errors += 1
            print(f"ERROR {path}: {exc}")
    result.observed_unique_branches = len(observed)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="와와학원.com 전국센터의 실제 센터 엔터티와 BreadcrumbList를 멱등 정규화합니다."
    )
    parser.add_argument("--apply", action="store_true", help="검증을 통과한 변경을 실제 HTML에 기록합니다.")
    parser.add_argument("--limit", type=int, help="앞에서부터 검사할 페이지 수(샘플 dry-run용)")
    parser.add_argument("--dong", help="특정 동네 상세 페이지만 검사(샘플 dry-run용)")
    args = parser.parse_args()
    result = run(apply=args.apply, limit=args.limit, dong=args.dong)
    payload = {
        **result.__dict__,
        "mode": "apply" if args.apply else "dry-run",
        "dong": args.dong,
        "limit": args.limit,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if result.errors or result.non_idempotent:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
