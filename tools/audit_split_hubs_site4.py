from __future__ import annotations

import argparse
import html
import json
import posixpath
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote, unquote, urljoin, urlsplit


ROOT = Path(__file__).resolve().parents[1]
CENTER_ROOT = ROOT / "전국센터"
INFO_PATH = ROOT / "tools" / "center_info.json"
DOMAIN = "https://xn--ol5ba64b839b.com"
DOMAIN_HOST = urlsplit(DOMAIN).netloc.lower()
SITE_NAME = "와와학습코칭학원"

REGIONS = ("서울", "경기", "인천", "충청", "대전", "대구", "울산", "부산", "경상", "광주", "전라", "강원", "제주")
DISTRICT_HUB_REGION = "경기"
EXPECTED_CATEGORIES = 6
EXPECTED_REGION_HUBS = 78
EXPECTED_DISTRICT_HUBS = 132
EXPECTED_DETAILS = 8_904
DEFAULT_MAX_INTERNAL_LINKS = 200

# The role-to-suffix mapping is intentionally explicit. Besides checking the
# count, it protects every pre-existing detail URL from accidental relocation.
CATEGORY_ROLE_SUFFIXES: dict[str, tuple[tuple[str, str], ...]] = {
    "수학학원": (
        ("subject-all-math", "수학학원"),
        ("subject-elementary-math", "초등수학학원"),
        ("subject-middle-math", "중등수학학원"),
        ("subject-high-math", "고등수학학원"),
    ),
    "영어학원": (
        ("subject-all-english", "영어학원"),
        ("subject-elementary-english", "초등영어학원"),
        ("subject-middle-english", "중등영어학원"),
        ("subject-high-english", "고등영어학원"),
    ),
    "영수학원": (
        ("subject-all-combined", "영수학원"),
        ("subject-elementary-combined", "초등영수학원"),
        ("subject-middle-combined", "중등영수학원"),
        ("subject-high-combined", "고등영수학원"),
    ),
    "초등학생학원": (
        ("grade-elementary-general", "초등학생학원"),
        ("grade-elementary-math", "초등학생수학학원"),
        ("grade-elementary-english", "초등학생영어학원"),
        ("grade-elementary-combined", "초등학생영수학원"),
    ),
    "중학생학원": (
        ("grade-middle-general", "중학생학원"),
        ("grade-middle-math", "중학생수학학원"),
        ("grade-middle-english", "중학생영어학원"),
        ("grade-middle-combined", "중학생영수학원"),
    ),
    "고등학생학원": (
        ("grade-high-general", "고등학생학원"),
        ("grade-high-math", "고등학생수학학원"),
        ("grade-high-english", "고등학생영어학원"),
        ("grade-high-combined", "고등학생영수학원"),
    ),
}
CATEGORIES = tuple(CATEGORY_ROLE_SUFFIXES)


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def class_tokens(attrs: dict[str, str]) -> set[str]:
    return set(attrs.get("class", "").split())


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.anchors: list[str] = []
        self.canonicals: list[str] = []
        self.og_urls: list[str] = []
        self.jsonld: list[str] = []
        self.intent_roles: list[str] = []
        self.h1s: list[str] = []
        self.titles: list[str] = []
        self.breadcrumb: list[tuple[str, str | None]] = []

        self._h1_depth = 0
        self._h1_parts: list[str] = []
        self._title_depth = 0
        self._title_parts: list[str] = []
        self._json_depth = 0
        self._json_parts: list[str] = []
        self._breadcrumb_depth = 0
        self._breadcrumb_li_depth = 0
        self._breadcrumb_parts: list[str] = []
        self._breadcrumb_href: str | None = None

    def handle_starttag(self, tag: str, attrs_list: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attrs = {key.lower(): value or "" for key, value in attrs_list}

        if self._breadcrumb_depth:
            self._breadcrumb_depth += 1
            if self._breadcrumb_li_depth:
                self._breadcrumb_li_depth += 1
        elif tag == "nav" and "seo-breadcrumb" in class_tokens(attrs):
            self._breadcrumb_depth = 1

        if self._breadcrumb_depth and tag == "li" and not self._breadcrumb_li_depth:
            self._breadcrumb_li_depth = 1
            self._breadcrumb_parts = []
            self._breadcrumb_href = None

        if tag == "a":
            href = attrs.get("href")
            if href is not None:
                self.anchors.append(href)
                if self._breadcrumb_li_depth and self._breadcrumb_href is None:
                    self._breadcrumb_href = href

        if tag == "link" and "canonical" in attrs.get("rel", "").lower().split():
            self.canonicals.append(attrs.get("href", ""))
        if tag == "meta" and attrs.get("property", "").lower() == "og:url":
            self.og_urls.append(attrs.get("content", ""))

        role = attrs.get("data-intent-role")
        if role:
            self.intent_roles.append(role)

        if tag == "h1":
            self._h1_depth = 1
            self._h1_parts = []
        elif self._h1_depth:
            self._h1_depth += 1

        if tag == "title":
            self._title_depth = 1
            self._title_parts = []
        elif self._title_depth:
            self._title_depth += 1

        if tag == "script" and attrs.get("type", "").lower() == "application/ld+json":
            self._json_depth = 1
            self._json_parts = []
        elif self._json_depth:
            self._json_depth += 1

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        # The fields read from void elements are handled by handle_starttag.
        self.handle_starttag(tag, attrs)
        if tag.lower() not in {"meta", "link", "img", "input", "br", "hr", "source"}:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()

        if self._h1_depth:
            self._h1_depth -= 1
            if self._h1_depth == 0:
                self.h1s.append(clean_text("".join(self._h1_parts)))
        if self._title_depth:
            self._title_depth -= 1
            if self._title_depth == 0:
                self.titles.append(clean_text("".join(self._title_parts)))
        if self._json_depth:
            self._json_depth -= 1
            if self._json_depth == 0:
                self.jsonld.append("".join(self._json_parts).strip())

        if self._breadcrumb_li_depth:
            self._breadcrumb_li_depth -= 1
            if self._breadcrumb_li_depth == 0:
                self.breadcrumb.append((clean_text("".join(self._breadcrumb_parts)), self._breadcrumb_href))
        if self._breadcrumb_depth:
            self._breadcrumb_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._h1_depth:
            self._h1_parts.append(data)
        if self._title_depth:
            self._title_parts.append(data)
        if self._json_depth:
            self._json_parts.append(data)
        if self._breadcrumb_li_depth:
            self._breadcrumb_parts.append(data)


@dataclass
class PageInfo:
    path: Path
    route: str
    anchors: list[str]
    canonicals: list[str]
    og_urls: list[str]
    jsonld_raw: list[str]
    intent_roles: list[str]
    h1s: list[str]
    titles: list[str]
    breadcrumb: list[tuple[str, str | None]]
    json_nodes: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class DetailRecord:
    category: str
    dong: str
    region: str
    district: str
    role: str
    path: Path


class Audit:
    def __init__(self, example_limit: int = 5) -> None:
        self.counts: Counter[str] = Counter()
        self.examples: dict[str, list[str]] = defaultdict(list)
        self.example_limit = example_limit

    def fail(self, code: str, message: str) -> None:
        self.counts[code] += 1
        if len(self.examples[code]) < self.example_limit:
            self.examples[code].append(message)

    def check(self, condition: bool, code: str, message: str) -> None:
        if not condition:
            self.fail(code, message)

    @property
    def total(self) -> int:
        return sum(self.counts.values())

    def print_failures(self) -> None:
        for code in sorted(self.counts):
            print(f"FAIL {code}: {self.counts[code]}")
            for example in self.examples[code]:
                print(f"  - {example}")


def canonical_url(*parts: str) -> str:
    encoded = "/".join(quote(part, safe="") for part in parts)
    return f"{DOMAIN}/{encoded}/" if encoded else f"{DOMAIN}/"


def root_href(*parts: str) -> str:
    encoded = "/".join(quote(part, safe="") for part in parts)
    return f"/{encoded}/" if encoded else "/"


def route_for_page(path: Path) -> str:
    relative = path.relative_to(ROOT)
    if relative == Path("index.html"):
        return "/"
    parts = relative.parent.parts
    return "/" + "/".join(quote(part, safe="") for part in parts) + "/"


def canonical_for_page(path: Path) -> str:
    relative = path.relative_to(ROOT)
    return canonical_url(*relative.parent.parts) if relative.parent.parts else canonical_url()


def normalized_route(value: str) -> str:
    value = unicodedata.normalize("NFC", unquote(value or "/")).replace("\\", "/")
    normalized = posixpath.normpath("/" + value.lstrip("/"))
    return normalized.rstrip("/") or "/"


def parse_page(path: Path, audit: Audit) -> PageInfo:
    parser = PageParser()
    try:
        parser.feed(path.read_text(encoding="utf-8", errors="strict"))
        parser.close()
    except Exception as exc:  # noqa: BLE001
        audit.fail("html_parse", f"{path.relative_to(ROOT).as_posix()}: {exc}")
    info = PageInfo(
        path=path,
        route=route_for_page(path),
        anchors=parser.anchors,
        canonicals=parser.canonicals,
        og_urls=parser.og_urls,
        jsonld_raw=parser.jsonld,
        intent_roles=parser.intent_roles,
        h1s=parser.h1s,
        titles=parser.titles,
        breadcrumb=parser.breadcrumb,
    )
    for index, raw in enumerate(info.jsonld_raw, 1):
        try:
            data = json.loads(raw)
        except Exception as exc:  # noqa: BLE001
            audit.fail("jsonld_parse", f"{path.relative_to(ROOT).as_posix()} script#{index}: {exc}")
            continue
        if isinstance(data, dict):
            graph = data.get("@graph")
            if isinstance(graph, list):
                info.json_nodes.extend(node for node in graph if isinstance(node, dict))
            else:
                info.json_nodes.append(data)
        elif isinstance(data, list):
            info.json_nodes.extend(node for node in data if isinstance(node, dict))
    return info


def has_type(node: dict[str, Any], expected: str) -> bool:
    value = node.get("@type")
    return expected in value if isinstance(value, list) else value == expected


def nodes_of_type(info: PageInfo, expected: str) -> list[dict[str, Any]]:
    return [node for node in info.json_nodes if has_type(node, expected)]


def relative(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def load_centers(audit: Audit) -> dict[str, dict[str, str]]:
    try:
        raw = json.loads(INFO_PATH.read_text(encoding="utf-8", errors="strict"))
    except Exception as exc:  # noqa: BLE001
        audit.fail("center_info", f"center_info.json 읽기 실패: {exc}")
        return {}
    if not isinstance(raw, dict):
        audit.fail("center_info", "center_info.json 최상위 값이 객체가 아닙니다")
        return {}
    centers: dict[str, dict[str, str]] = {}
    required = ("지역", "지역 영어", "시or구", "시or구 영어")
    for key, branch in raw.items():
        normalized = re.sub(r"\s+", "", key)
        if not isinstance(branch, dict):
            audit.fail("center_info", f"{key}: 센터 값이 객체가 아닙니다")
            continue
        missing = [field for field in required if not clean_text(str(branch.get(field, "")))]
        if missing:
            audit.fail("center_info", f"{key}: 필수 필드 누락 {missing}")
            continue
        if normalized in centers:
            audit.fail("center_info", f"공백 정규화 후 동네 키 중복: {key} -> {normalized}")
            continue
        centers[normalized] = {field: clean_text(str(branch[field])) for field in required}
    audit.check(len(centers) == 371, "center_count", f"동네 {len(centers)}개 (예상 371개)")
    audit.check(set(branch["지역"] for branch in centers.values()) == set(REGIONS), "region_data", "center_info 광역지역 집합이 확정 13개와 다릅니다")
    gyeonggi_districts = {branch["시or구"] for branch in centers.values() if branch["지역"] == DISTRICT_HUB_REGION}
    audit.check(len(gyeonggi_districts) == 22, "district_data", f"경기 시/군/구 {len(gyeonggi_districts)}개 (예상 22개)")
    return centers


def expected_details(centers: dict[str, dict[str, str]]) -> list[DetailRecord]:
    result: list[DetailRecord] = []
    for category, roles in CATEGORY_ROLE_SUFFIXES.items():
        for dong, branch in centers.items():
            for role, suffix in roles:
                result.append(
                    DetailRecord(
                        category=category,
                        dong=dong,
                        region=branch["지역"],
                        district=branch["시or구"],
                        role=role,
                        path=CENTER_ROOT / category / f"{dong}{suffix}" / "index.html",
                    )
                )
    return result


def expected_breadcrumbs(record: DetailRecord, h1: str) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    visible = [
        ("홈", root_href()),
        ("전국센터", root_href("전국센터")),
        (record.category, root_href("전국센터", record.category)),
        (record.region, root_href("전국센터", record.category, record.region)),
    ]
    structured = [
        (SITE_NAME, canonical_url()),
        ("전국센터", canonical_url("전국센터")),
        (record.category, canonical_url("전국센터", record.category)),
        (record.region, canonical_url("전국센터", record.category, record.region)),
    ]
    if record.region == DISTRICT_HUB_REGION:
        visible.append((record.district, root_href("전국센터", record.category, record.region, record.district)))
        structured.append((record.district, canonical_url("전국센터", record.category, record.region, record.district)))
    visible.append((h1, ""))
    structured.append((h1, canonical_for_page(record.path)))
    return visible, structured


def expected_hub_paths(centers: dict[str, dict[str, str]]) -> tuple[set[Path], set[Path], set[Path]]:
    category_paths = {CENTER_ROOT / category / "index.html" for category in CATEGORIES}
    region_paths = {CENTER_ROOT / category / region / "index.html" for category in CATEGORIES for region in REGIONS}
    districts = sorted({branch["시or구"] for branch in centers.values() if branch["지역"] == DISTRICT_HUB_REGION})
    district_paths = {
        CENTER_ROOT / category / DISTRICT_HUB_REGION / district / "index.html"
        for category in CATEGORIES
        for district in districts
    }
    return category_paths, region_paths, district_paths


def route_map_for_pages(pages: Iterable[Path]) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for path in pages:
        route = normalized_route(route_for_page(path))
        result[route] = path
        if route == "/":
            result["/index.html"] = path
        else:
            result[f"{route}/index.html"] = path
    return result


@dataclass(frozen=True)
class ResolvedLink:
    internal: bool
    exists: bool
    page: Path | None
    route: str | None


def resolve_link(source: PageInfo, href: str, route_map: dict[str, Path]) -> ResolvedLink:
    href = href.strip()
    if not href or href.startswith("#"):
        return ResolvedLink(True, True, source.path, normalized_route(source.route))
    parsed_initial = urlsplit(href)
    if parsed_initial.scheme and parsed_initial.scheme.lower() not in {"http", "https"}:
        return ResolvedLink(False, True, None, None)
    absolute = urljoin(f"{DOMAIN}{source.route}", href)
    parsed = urlsplit(absolute)
    if parsed.scheme.lower() not in {"http", "https"} or parsed.netloc.lower() != DOMAIN_HOST:
        return ResolvedLink(False, True, None, None)
    route = normalized_route(parsed.path)
    page = route_map.get(route)
    if page is not None:
        return ResolvedLink(True, True, page, route)

    decoded = unicodedata.normalize("NFC", unquote(parsed.path)).lstrip("/")
    candidate = ROOT.joinpath(*[part for part in decoded.split("/") if part])
    if candidate.is_file():
        return ResolvedLink(True, True, None, route)
    if candidate.is_dir() and (candidate / "index.html").is_file():
        return ResolvedLink(True, True, candidate / "index.html", route)
    if not candidate.suffix and (candidate / "index.html").is_file():
        return ResolvedLink(True, True, candidate / "index.html", route)
    return ResolvedLink(True, False, None, route)


def validate_meta(info: PageInfo, expected_canonical: str, expected_h1: str | None, audit: Audit) -> None:
    label = relative(info.path)
    audit.check(len(info.canonicals) == 1, "canonical_count", f"{label}: canonical {len(info.canonicals)}개")
    if len(info.canonicals) == 1:
        audit.check(info.canonicals[0] == expected_canonical, "canonical_value", f"{label}: {info.canonicals[0]} != {expected_canonical}")
    audit.check(len(info.og_urls) == 1, "og_url_count", f"{label}: og:url {len(info.og_urls)}개")
    if len(info.og_urls) == 1:
        audit.check(info.og_urls[0] == expected_canonical, "og_url_value", f"{label}: {info.og_urls[0]} != {expected_canonical}")
    audit.check(len(info.h1s) == 1 and bool(info.h1s[0]), "h1_count", f"{label}: H1={info.h1s}")
    if expected_h1 is not None and len(info.h1s) == 1:
        audit.check(info.h1s[0] == expected_h1, "h1_value", f"{label}: {info.h1s[0]} != {expected_h1}")
    audit.check(len(info.titles) == 1 and bool(info.titles[0]), "title_count", f"{label}: title={info.titles}")


def validate_structured_breadcrumb(
    info: PageInfo,
    expected_canonical: str,
    expected: list[tuple[str, str]],
    audit: Audit,
) -> None:
    label = relative(info.path)
    breadcrumbs = nodes_of_type(info, "BreadcrumbList")
    audit.check(len(breadcrumbs) == 1, "breadcrumb_json_count", f"{label}: BreadcrumbList {len(breadcrumbs)}개")
    if len(breadcrumbs) != 1:
        return
    node = breadcrumbs[0]
    audit.check(node.get("@id") == f"{expected_canonical}#breadcrumb", "breadcrumb_json_id", f"{label}: BreadcrumbList @id 불일치")
    items = node.get("itemListElement")
    if not isinstance(items, list):
        audit.fail("breadcrumb_json_items", f"{label}: itemListElement가 배열이 아닙니다")
        return
    actual: list[tuple[str, str]] = []
    positions: list[Any] = []
    for item in items:
        if not isinstance(item, dict):
            actual.append(("", ""))
            positions.append(None)
            continue
        actual.append((str(item.get("name", "")), str(item.get("item", ""))))
        positions.append(item.get("position"))
        audit.check(item.get("@type") == "ListItem", "breadcrumb_json_type", f"{label}: ListItem @type 누락")
    audit.check(positions == list(range(1, len(items) + 1)), "breadcrumb_json_positions", f"{label}: positions={positions}")
    audit.check(actual == expected, "breadcrumb_json_hierarchy", f"{label}: {actual} != {expected}")


def validate_visible_breadcrumb(
    info: PageInfo,
    expected: list[tuple[str, str]],
    route_map: dict[str, Path],
    audit: Audit,
) -> None:
    label = relative(info.path)
    actual_names = [name for name, _ in info.breadcrumb]
    expected_names = [name for name, _ in expected]
    audit.check(actual_names == expected_names, "breadcrumb_visible_names", f"{label}: {actual_names} != {expected_names}")
    if len(info.breadcrumb) != len(expected):
        return
    for index, ((_, href), (_, expected_href)) in enumerate(zip(info.breadcrumb, expected, strict=True), 1):
        if not expected_href:
            audit.check(href is None, "breadcrumb_visible_current", f"{label}: 현재 항목 #{index}에 href={href}")
            continue
        if href is None:
            audit.fail("breadcrumb_visible_href", f"{label}: 항목 #{index} 링크 누락")
            continue
        actual_link = resolve_link(info, href, route_map)
        expected_link = resolve_link(info, expected_href, route_map)
        audit.check(
            actual_link.page == expected_link.page and actual_link.exists,
            "breadcrumb_visible_href",
            f"{label}: 항목 #{index} {href} -> {actual_link.route}, expected {expected_link.route}",
        )


def validate_jsonld_core(info: PageInfo, expected_canonical: str, require_collection: bool, audit: Audit) -> None:
    label = relative(info.path)
    audit.check(bool(info.jsonld_raw), "jsonld_missing", f"{label}: JSON-LD 없음")
    web_pages = nodes_of_type(info, "WebPage")
    audit.check(len(web_pages) == 1, "webpage_json_count", f"{label}: WebPage {len(web_pages)}개")
    if len(web_pages) == 1:
        node = web_pages[0]
        audit.check(node.get("url") == expected_canonical, "webpage_json_url", f"{label}: WebPage url 불일치")
        audit.check(node.get("@id") == f"{expected_canonical}#webpage", "webpage_json_id", f"{label}: WebPage @id 불일치")
        audit.check(
            isinstance(node.get("breadcrumb"), dict) and node["breadcrumb"].get("@id") == f"{expected_canonical}#breadcrumb",
            "webpage_json_breadcrumb",
            f"{label}: WebPage breadcrumb 참조 불일치",
        )
        if len(info.titles) == 1:
            audit.check(node.get("name") == info.titles[0], "webpage_json_name", f"{label}: WebPage name과 title 불일치")
        if require_collection:
            audit.check(has_type(node, "CollectionPage"), "collection_json_type", f"{label}: CollectionPage 타입 누락")


def validate_item_list(
    info: PageInfo,
    expected_children: list[tuple[str, str]],
    audit: Audit,
) -> None:
    label = relative(info.path)
    item_lists = nodes_of_type(info, "ItemList")
    audit.check(len(item_lists) == 1, "itemlist_count", f"{label}: ItemList {len(item_lists)}개")
    if len(item_lists) != 1:
        return
    node = item_lists[0]
    items = node.get("itemListElement")
    if not isinstance(items, list):
        audit.fail("itemlist_items", f"{label}: itemListElement가 배열이 아닙니다")
        return
    audit.check(node.get("numberOfItems") == len(expected_children), "itemlist_number", f"{label}: numberOfItems={node.get('numberOfItems')} expected={len(expected_children)}")
    actual: list[tuple[str, str]] = []
    positions: list[Any] = []
    for item in items:
        if not isinstance(item, dict):
            actual.append(("", ""))
            positions.append(None)
            continue
        actual.append((str(item.get("name", "")), str(item.get("url") or item.get("item") or "")))
        positions.append(item.get("position"))
    audit.check(positions == list(range(1, len(items) + 1)), "itemlist_positions", f"{label}: positions 불연속")
    audit.check(actual == expected_children, "itemlist_children", f"{label}: 하위 페이지 목록/순서 불일치")


def main() -> int:
    parser = argparse.ArgumentParser(description="새 홈페이지4 분할 지역 허브 구조를 전수 검증합니다.")
    parser.add_argument("--max-links", type=int, default=DEFAULT_MAX_INTERNAL_LINKS, help="페이지당 허용할 최대 내부 HTML 링크 수")
    parser.add_argument("--examples", type=int, default=5, help="실패 유형별 출력할 예시 수")
    args = parser.parse_args()

    audit = Audit(example_limit=max(1, args.examples))
    centers = load_centers(audit)
    details = expected_details(centers)
    category_paths, region_paths, district_paths = expected_hub_paths(centers)
    detail_paths = {record.path for record in details}
    expected_scoped_paths = category_paths | region_paths | district_paths | detail_paths

    all_pages = sorted(path for path in ROOT.rglob("index.html") if ".git" not in path.parts)
    infos: dict[Path, PageInfo] = {path: parse_page(path, audit) for path in all_pages}
    route_map = route_map_for_pages(all_pages)

    actual_category_count = sum(path in infos for path in category_paths)
    actual_region_count = sum(path in infos for path in region_paths)
    actual_district_count = sum(path in infos for path in district_paths)
    actual_detail_count = sum(path in infos for path in detail_paths)
    audit.check(actual_category_count == EXPECTED_CATEGORIES, "count_categories", f"카테고리 {actual_category_count}개 (예상 {EXPECTED_CATEGORIES})")
    audit.check(actual_region_count == EXPECTED_REGION_HUBS, "count_regions", f"광역 허브 {actual_region_count}개 (예상 {EXPECTED_REGION_HUBS})")
    audit.check(actual_district_count == EXPECTED_DISTRICT_HUBS, "count_districts", f"경기 시 허브 {actual_district_count}개 (예상 {EXPECTED_DISTRICT_HUBS})")
    audit.check(actual_detail_count == EXPECTED_DETAILS, "count_details", f"기존 상세 {actual_detail_count}개 (예상 {EXPECTED_DETAILS})")
    audit.check(len(details) == EXPECTED_DETAILS, "expected_detail_model", f"데이터에서 계산한 상세 {len(details)}개")

    # Any extra center index at these depths is a stale, duplicated, or
    # accidentally generated page and must not silently pass the count check.
    allowed_center_pages = expected_scoped_paths | {CENTER_ROOT / "index.html"}
    for path in CENTER_ROOT.rglob("index.html"):
        if path not in allowed_center_pages:
            audit.fail("unexpected_center_page", relative(path))

    for record in details:
        info = infos.get(record.path)
        if info is None:
            audit.fail("detail_missing", relative(record.path))
            continue
        audit.check(info.intent_roles == [record.role], "detail_role", f"{relative(record.path)}: {info.intent_roles} != {[record.role]}")

    # Build the visible link graph once. It powers broken-link, orphan,
    # hierarchy, and maximum-link checks.
    adjacency: dict[Path, set[Path]] = defaultdict(set)
    inbound: dict[Path, set[Path]] = defaultdict(set)
    internal_link_occurrences: dict[Path, int] = {}
    for path, info in infos.items():
        count = 0
        for href in info.anchors:
            resolved = resolve_link(info, href, route_map)
            if not resolved.internal:
                continue
            if not resolved.exists:
                audit.fail("broken_internal_link", f"{relative(path)} -> {href}")
                continue
            if resolved.page is not None:
                count += 1
                adjacency[path].add(resolved.page)
                if resolved.page != path:
                    inbound[resolved.page].add(path)
        internal_link_occurrences[path] = count

    max_path, max_links = max(internal_link_occurrences.items(), key=lambda item: item[1], default=(ROOT / "index.html", 0))
    audit.check(max_links <= args.max_links, "max_internal_links", f"{relative(max_path)}: {max_links}개 (허용 {args.max_links})")

    by_category_region: dict[tuple[str, str], list[DetailRecord]] = defaultdict(list)
    by_category_region_district: dict[tuple[str, str, str], list[DetailRecord]] = defaultdict(list)
    record_by_path = {record.path: record for record in details}
    for record in details:
        by_category_region[(record.category, record.region)].append(record)
        by_category_region_district[(record.category, record.region, record.district)].append(record)

    canonical_owners: dict[str, list[Path]] = defaultdict(list)

    def validate_page(
        path: Path,
        *,
        expected_h1: str | None,
        visible_crumbs: list[tuple[str, str]],
        structured_crumbs: list[tuple[str, str]],
        children: list[tuple[str, str]] | None,
        require_collection: bool,
    ) -> None:
        info = infos.get(path)
        if info is None:
            return
        canonical = canonical_for_page(path)
        validate_meta(info, canonical, expected_h1, audit)
        validate_jsonld_core(info, canonical, require_collection, audit)
        validate_visible_breadcrumb(info, visible_crumbs, route_map, audit)
        validate_structured_breadcrumb(info, canonical, structured_crumbs, audit)
        if children is not None:
            validate_item_list(info, children, audit)
        if len(info.canonicals) == 1:
            canonical_owners[info.canonicals[0]].append(path)

    # 전국센터 -> six category roots.
    national = CENTER_ROOT / "index.html"
    if national in infos:
        for child in sorted(category_paths):
            audit.check(child in adjacency[national], "national_to_category", f"전국센터에서 {relative(child)} 링크 누락")

    for category in CATEGORIES:
        path = CENTER_ROOT / category / "index.html"
        child_pairs = [
            (f"{region} {category}", canonical_url("전국센터", category, region))
            for region in REGIONS
        ]
        validate_page(
            path,
            expected_h1=f"{category} 지역별 안내",
            visible_crumbs=[("홈", root_href()), ("전국센터", root_href("전국센터")), (category, "")],
            structured_crumbs=[
                (SITE_NAME, canonical_url()),
                ("전국센터", canonical_url("전국센터")),
                (category, canonical_url("전국센터", category)),
            ],
            children=child_pairs,
            require_collection=True,
        )
        for region in REGIONS:
            child = CENTER_ROOT / category / region / "index.html"
            audit.check(child in adjacency[path], "category_to_region", f"{relative(path)} -> {relative(child)} 누락")
        bypasses = adjacency[path] & detail_paths
        audit.check(not bypasses, "category_bypasses_region", f"{relative(path)}: 상세 직링크 {len(bypasses)}개")

    for category in CATEGORIES:
        for region in REGIONS:
            path = CENTER_ROOT / category / region / "index.html"
            grouped = sorted(
                by_category_region[(category, region)],
                key=lambda item: (item.district, item.dong, [role for role, _ in CATEGORY_ROLE_SUFFIXES[category]].index(item.role)),
            )
            if region == DISTRICT_HUB_REGION:
                districts = sorted({record.district for record in grouped})
                child_pairs = [
                    (f"{region} {district} {category}", canonical_url("전국센터", category, region, district))
                    for district in districts
                ]
                child_paths = [CENTER_ROOT / category / region / district / "index.html" for district in districts]
            else:
                child_pairs = [
                    ((infos[record.path].h1s[0] if record.path in infos and len(infos[record.path].h1s) == 1 else record.path.parent.name), canonical_for_page(record.path))
                    for record in grouped
                ]
                child_paths = [record.path for record in grouped]
            validate_page(
                path,
                expected_h1=f"{region} {category} 지역 찾기",
                visible_crumbs=[
                    ("홈", root_href()),
                    ("전국센터", root_href("전국센터")),
                    (category, root_href("전국센터", category)),
                    (region, ""),
                ],
                structured_crumbs=[
                    (SITE_NAME, canonical_url()),
                    ("전국센터", canonical_url("전국센터")),
                    (category, canonical_url("전국센터", category)),
                    (region, canonical_url("전국센터", category, region)),
                ],
                children=child_pairs,
                require_collection=True,
            )
            for child in child_paths:
                audit.check(child in adjacency[path], "region_to_child", f"{relative(path)} -> {relative(child)} 누락")
            if region == DISTRICT_HUB_REGION:
                bypasses = adjacency[path] & {record.path for record in grouped}
                audit.check(not bypasses, "region_bypasses_district", f"{relative(path)}: 경기 상세 직링크 {len(bypasses)}개")

    gyeonggi_districts = sorted({branch["시or구"] for branch in centers.values() if branch["지역"] == DISTRICT_HUB_REGION})
    for category in CATEGORIES:
        role_order = [role for role, _ in CATEGORY_ROLE_SUFFIXES[category]]
        for district in gyeonggi_districts:
            path = CENTER_ROOT / category / DISTRICT_HUB_REGION / district / "index.html"
            grouped = sorted(
                by_category_region_district[(category, DISTRICT_HUB_REGION, district)],
                key=lambda item: (item.dong, role_order.index(item.role)),
            )
            child_pairs = [
                ((infos[record.path].h1s[0] if record.path in infos and len(infos[record.path].h1s) == 1 else record.path.parent.name), canonical_for_page(record.path))
                for record in grouped
            ]
            validate_page(
                path,
                expected_h1=f"{DISTRICT_HUB_REGION} {district} {category} 찾기",
                visible_crumbs=[
                    ("홈", root_href()),
                    ("전국센터", root_href("전국센터")),
                    (category, root_href("전국센터", category)),
                    (DISTRICT_HUB_REGION, root_href("전국센터", category, DISTRICT_HUB_REGION)),
                    (district, ""),
                ],
                structured_crumbs=[
                    (SITE_NAME, canonical_url()),
                    ("전국센터", canonical_url("전국센터")),
                    (category, canonical_url("전국센터", category)),
                    (DISTRICT_HUB_REGION, canonical_url("전국센터", category, DISTRICT_HUB_REGION)),
                    (district, canonical_url("전국센터", category, DISTRICT_HUB_REGION, district)),
                ],
                children=child_pairs,
                require_collection=True,
            )
            for record in grouped:
                audit.check(record.path in adjacency[path], "district_to_detail", f"{relative(path)} -> {relative(record.path)} 누락")

    for record in details:
        info = infos.get(record.path)
        if info is None:
            continue
        h1 = info.h1s[0] if len(info.h1s) == 1 else record.path.parent.name
        visible, structured = expected_breadcrumbs(record, h1)
        validate_page(
            record.path,
            expected_h1=None,
            visible_crumbs=visible,
            structured_crumbs=structured,
            children=None,
            require_collection=False,
        )
        immediate_parent = (
            CENTER_ROOT / record.category / record.region / record.district / "index.html"
            if record.region == DISTRICT_HUB_REGION
            else CENTER_ROOT / record.category / record.region / "index.html"
        )
        audit.check(immediate_parent in adjacency[record.path], "detail_to_parent", f"{relative(record.path)} -> {relative(immediate_parent)} 누락")
        region_parent = CENTER_ROOT / record.category / record.region / "index.html"
        audit.check(region_parent in adjacency[record.path], "detail_to_region", f"{relative(record.path)} -> {relative(region_parent)} 누락")

    for canonical, owners in canonical_owners.items():
        if len(owners) > 1:
            audit.fail("canonical_duplicate", f"{canonical}: {[relative(path) for path in owners]}")

    for path in sorted(expected_scoped_paths):
        if path in infos and not inbound[path]:
            audit.fail("orphan_page", relative(path))

    max_unique_path, max_unique_links = max(adjacency.items(), key=lambda item: len(item[1]), default=(ROOT / "index.html", set()))
    summary = {
        "categories": actual_category_count,
        "region_hubs": actual_region_count,
        "district_hubs": actual_district_count,
        "detail_pages": actual_detail_count,
        "scoped_pages": actual_category_count + actual_region_count + actual_district_count + actual_detail_count,
        "all_html_pages": len(all_pages),
        "broken_internal_links": audit.counts.get("broken_internal_link", 0),
        "orphan_pages": audit.counts.get("orphan_page", 0),
        "max_internal_links": max_links,
        "max_internal_links_page": relative(max_path),
        "max_unique_internal_targets": len(max_unique_links),
        "max_unique_internal_targets_page": relative(max_unique_path),
        "link_limit": args.max_links,
        "failures": audit.total,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if audit.total:
        audit.print_failures()
        return 1
    print("PASS split hub architecture audit")
    return 0


if __name__ == "__main__":
    sys.exit(main())
