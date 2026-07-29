from __future__ import annotations

import html
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
CENTER_ROOT = ROOT / "전국센터"
INFO_PATH = ROOT / "tools" / "center_info.json"
DOMAIN = "https://xn--ol5ba64b839b.com"
SITE_NAME = "와와학습코칭학원"
TODAY = date.today().isoformat()
REGIONS = ["서울", "경기", "인천", "충청", "대전", "대구", "울산", "부산", "경상", "광주", "전라", "강원", "제주"]
SPLIT_DISTRICT_REGIONS = {"경기"}


@dataclass(frozen=True)
class Category:
    name: str
    eyebrow: str
    focus: str
    audience: str
    role_order: tuple[str, ...]
    role_labels: dict[str, str]


CATEGORIES = (
    Category(
        "수학학원",
        "MATH ACADEMY DIRECTORY",
        "개념 이해·계산 정확도·유형 적용·오답 재학습을 학년 단계에 맞춰 확인하는 수학 학습 안내",
        "초등·중등·고등 수학 학습을 점검하려는 학생과 학부모",
        ("subject-all-math", "subject-elementary-math", "subject-middle-math", "subject-high-math"),
        {
            "subject-all-math": "수학 전체",
            "subject-elementary-math": "초등 수학",
            "subject-middle-math": "중등 수학",
            "subject-high-math": "고등 수학",
        },
    ),
    Category(
        "영어학원",
        "ENGLISH ACADEMY DIRECTORY",
        "어휘·문법·독해·학교 본문과 서술형 대비를 학년별로 연결하는 영어 학습 안내",
        "초등·중등·고등 영어 학습을 점검하려는 학생과 학부모",
        ("subject-all-english", "subject-elementary-english", "subject-middle-english", "subject-high-english"),
        {
            "subject-all-english": "영어 전체",
            "subject-elementary-english": "초등 영어",
            "subject-middle-english": "중등 영어",
            "subject-high-english": "고등 영어",
        },
    ),
    Category(
        "영수학원",
        "ENGLISH & MATH DIRECTORY",
        "영어와 수학의 주간 분량·복습 순서·시험 대비 균형을 함께 점검하는 영수 학습 안내",
        "영어와 수학을 함께 관리하려는 초등·중등·고등 학생과 학부모",
        ("subject-all-combined", "subject-elementary-combined", "subject-middle-combined", "subject-high-combined"),
        {
            "subject-all-combined": "영수 전체",
            "subject-elementary-combined": "초등 영수",
            "subject-middle-combined": "중등 영수",
            "subject-high-combined": "고등 영수",
        },
    ),
    Category(
        "초등학생학원",
        "ELEMENTARY ACADEMY DIRECTORY",
        "기초 개념과 숙제 습관부터 영어·수학의 주간 학습 흐름까지 확인하는 초등 학습 안내",
        "초등 학습 습관과 과목별 기초를 점검하려는 학생과 학부모",
        ("grade-elementary-general", "grade-elementary-math", "grade-elementary-english", "grade-elementary-combined"),
        {
            "grade-elementary-general": "초등 종합",
            "grade-elementary-math": "초등 수학",
            "grade-elementary-english": "초등 영어",
            "grade-elementary-combined": "초등 영수",
        },
    ),
    Category(
        "중학생학원",
        "MIDDLE SCHOOL DIRECTORY",
        "학교 진도·내신 범위·수행평가·오답 복습을 함께 관리하는 중등 학습 안내",
        "중등 내신과 과목별 학습 루틴을 점검하려는 학생과 학부모",
        ("grade-middle-general", "grade-middle-math", "grade-middle-english", "grade-middle-combined"),
        {
            "grade-middle-general": "중등 종합",
            "grade-middle-math": "중등 수학",
            "grade-middle-english": "중등 영어",
            "grade-middle-combined": "중등 영수",
        },
    ),
    Category(
        "고등학생학원",
        "HIGH SCHOOL DIRECTORY",
        "학년별 내신·모의고사 일정과 영어·수학 공부 시간을 함께 설계하는 고등 학습 안내",
        "고등 내신·모의고사와 과목별 시간 관리를 점검하려는 학생과 학부모",
        ("grade-high-general", "grade-high-math", "grade-high-english", "grade-high-combined"),
        {
            "grade-high-general": "고등 종합",
            "grade-high-math": "고등 수학",
            "grade-high-english": "고등 영어",
            "grade-high-combined": "고등 영수",
        },
    ),
)
CATEGORY_BY_NAME = {category.name: category for category in CATEGORIES}


@dataclass
class DetailPage:
    category: Category
    dong: str
    region: str
    district: str
    role: str
    title: str
    canonical: str
    path: Path


def escape(value: str) -> str:
    return html.escape(value, quote=True)


def canonical_url(*parts: str) -> str:
    encoded = "/".join(quote(part, safe="") for part in parts)
    return f"{DOMAIN}/{encoded}/" if encoded else f"{DOMAIN}/"


def root_href(*parts: str) -> str:
    encoded = "/".join(quote(part, safe="") for part in parts)
    return f"/{encoded}/" if encoded else "/"


def normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def load_centers() -> tuple[dict[str, dict], list[str]]:
    raw = json.loads(INFO_PATH.read_text(encoding="utf-8"))
    # 원본 센터표의 새롬동·다정동은 시군구 열에 도로명(새롬중앙로)이
    # 들어가 있다. 허브 탐색에서는 행정 생활권인 세종시로 정규화하되,
    # 원본 파일과 상세페이지의 사실 정보는 변경하지 않는다.
    for branch in raw.values():
        address = normalize(branch.get("센터 주소", ""))
        if address.startswith("세종특별자치시") and normalize(branch.get("시or구", "")).endswith("로"):
            branch["시or구"] = "세종시"
    centers = {normalize(key).replace(" ", ""): value for key, value in raw.items()}
    return centers, sorted(centers, key=len, reverse=True)


def find_dong(leaf: str, dong_names: list[str]) -> str:
    for dong in dong_names:
        if leaf.startswith(dong):
            return dong
    raise ValueError(f"센터정보에서 동네를 찾을 수 없습니다: {leaf}")


def collect_details(centers: dict[str, dict], dong_names: list[str]) -> list[DetailPage]:
    pages: list[DetailPage] = []
    for category in CATEGORIES:
        category_root = CENTER_ROOT / category.name
        for path in sorted(category_root.glob("*/index.html")):
            source = path.read_text(encoding="utf-8", errors="strict")
            role_match = re.search(r'data-intent-role="([^"]+)"', source)
            if not role_match:
                continue
            role = role_match.group(1)
            if role not in category.role_order:
                raise RuntimeError(f"예상하지 못한 역할: {path} -> {role}")
            dong = find_dong(path.parent.name, dong_names)
            branch = centers[dong]
            title_match = re.search(r"<h1\b[^>]*>(.*?)</h1>", source, re.S | re.I)
            canonical_match = re.search(r'<link rel="canonical" href="([^"]+)"', source, re.I)
            if not title_match or not canonical_match:
                raise RuntimeError(f"필수 메타데이터 누락: {path}")
            title = normalize(re.sub(r"<[^>]+>", " ", title_match.group(1)))
            pages.append(
                DetailPage(
                    category=category,
                    dong=dong,
                    region=normalize(branch["지역"]),
                    district=normalize(branch["시or구"]),
                    role=role,
                    title=title,
                    canonical=canonical_match.group(1),
                    path=path,
                )
            )
    expected = len(CATEGORIES) * len(centers) * 4
    if len(pages) != expected:
        raise RuntimeError(f"상세페이지 {len(pages)}개 (예상 {expected}개)")
    return pages


def jsonld_script(
    *,
    title: str,
    description: str,
    canonical: str,
    breadcrumbs: list[tuple[str, str]],
    children: list[tuple[str, str]],
    about: list[str],
) -> str:
    breadcrumb_id = f"{canonical}#breadcrumb"
    list_id = f"{canonical}#directory"
    graph = [
        {
            "@type": "WebSite",
            "@id": f"{DOMAIN}/#website",
            "url": f"{DOMAIN}/",
            "name": SITE_NAME,
            "inLanguage": "ko-KR",
        },
        {
            "@type": "EducationalOrganization",
            "@id": f"{DOMAIN}/#organization",
            "name": SITE_NAME,
            "url": f"{DOMAIN}/",
            "logo": f"{DOMAIN}/assets/favicon.svg",
            "telephone": "010-3957-8283",
            "areaServed": {"@type": "Country", "name": "대한민국"},
            "alternateName": ["와와학습코칭학원", "와와학습코칭센터", "와와학원", "와와학원.com"],
        },
        {
            "@type": ["WebPage", "CollectionPage"],
            "@id": f"{canonical}#webpage",
            "url": canonical,
            "name": title,
            "description": description,
            "inLanguage": "ko-KR",
            "isPartOf": {"@id": f"{DOMAIN}/#website"},
            "publisher": {"@id": f"{DOMAIN}/#organization"},
            "breadcrumb": {"@id": breadcrumb_id},
            "mainEntity": {"@id": list_id},
            "about": [{"@type": "Thing", "name": value} for value in about],
            "dateModified": TODAY,
        },
        {
            "@type": "BreadcrumbList",
            "@id": breadcrumb_id,
            "itemListElement": [
                {"@type": "ListItem", "position": index, "name": name, "item": url}
                for index, (name, url) in enumerate(breadcrumbs, 1)
            ],
        },
        {
            "@type": "ItemList",
            "@id": list_id,
            "name": f"{title} 하위 페이지",
            "numberOfItems": len(children),
            "itemListElement": [
                {"@type": "ListItem", "position": index, "name": name, "url": url}
                for index, (name, url) in enumerate(children, 1)
            ],
        },
    ]
    return json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False, separators=(",", ":"))


def header() -> str:
    return '''<body class="split-hub-page">
  <a class="skip-link" href="#main">본문 바로가기</a>
  <header class="site-header">
    <div class="wrap header-inner">
      <a class="brand" href="/">
        <span class="brand-mark" aria-hidden="true">W</span>
        <span class="brand-text">와와학습코칭학원</span>
      </a>
      <nav class="main-nav" aria-label="주요 메뉴">
        <a href="/" class="nav-link">홈</a>
        <a href="/%ED%95%99%EC%8A%B5%EC%BD%94%EC%B9%AD/" class="nav-link">학습코칭</a>
        <a href="/%EC%A0%84%EA%B5%AD%EC%84%BC%ED%84%B0/" class="nav-link is-active">전국센터</a>
        <a href="/%EC%83%81%EB%8B%B4%EB%AC%B8%EC%9D%98/" class="nav-link">상담문의</a>
      </nav>
      <a class="header-cta" href="https://docs.google.com/forms/d/e/1FAIpQLSdb2oE5Qk5YS0TfYDxyV1w-IOTkhkjOCmmpAKTI9FmqpVj6Yg/viewform" target="_blank" rel="noopener">상담 신청</a>
    </div>
  </header>'''


def footer(category_name: str) -> str:
    return f'''  <section class="final-cta">
    <div class="wrap final-cta-inner">
      <p class="eyebrow">CONSULTING READY</p>
      <h2>지역을 선택한 뒤 학생에게 필요한 {escape(category_name)} 상담 기준을 확인하세요.</h2>
      <p>현재 학년과 교재, 최근 평가 자료, 오답 기록을 함께 살펴보면 상담의 우선순위를 더 구체적으로 정할 수 있습니다.</p>
      <div class="button-row">
        <a class="btn btn-primary" href="https://docs.google.com/forms/d/e/1FAIpQLSdb2oE5Qk5YS0TfYDxyV1w-IOTkhkjOCmmpAKTI9FmqpVj6Yg/viewform" target="_blank" rel="noopener">상담 신청하기</a>
        <a class="btn btn-soft" href="tel:01039578283">전화 문의</a>
      </div>
    </div>
  </section>
  <footer class="site-footer">
    <div class="wrap footer-inner">
      <div><strong>와와학습코칭학원</strong><p>초등·중등·고등 영어·수학·국어 학습코칭 전문 안내</p></div>
      <div class="footer-links">
        <a href="/%ED%95%99%EC%8A%B5%EC%BD%94%EC%B9%AD/">학습코칭</a>
        <a href="/%EC%A0%84%EA%B5%AD%EC%84%BC%ED%84%B0/">전국센터</a>
        <a href="/%ED%95%99%EC%8A%B5%EA%B0%80%EC%9D%B4%EB%93%9C/">학습가이드</a>
        <a href="/%EC%83%81%EB%8B%B4%EB%AC%B8%EC%9D%98/">상담문의</a>
      </div>
      <div class="footer-contact"><span>상담 전화</span><a href="tel:01039578283">010-3957-8283</a></div>
    </div>
  </footer>
  <div class="floating-actions" aria-label="빠른 상담 버튼">
    <a class="fab fab-call" href="tel:01039578283">전화문의</a>
    <a class="fab fab-sms" href="https://blogsms.net/01039578283" target="_blank" rel="noopener">문자문의</a>
    <a class="fab fab-form" href="https://docs.google.com/forms/d/e/1FAIpQLSdb2oE5Qk5YS0TfYDxyV1w-IOTkhkjOCmmpAKTI9FmqpVj6Yg/viewform" target="_blank" rel="noopener">상담신청</a>
  </div>
  <script src="/assets/site.js" defer></script>
</body>
</html>
'''


def breadcrumb_html(items: list[tuple[str, str]], current: str) -> str:
    links = "\n".join(f'          <li><a href="{escape(url)}">{escape(name)}</a></li>' for name, url in items)
    return f'''    <nav class="seo-breadcrumb" aria-label="현재 위치">
      <div class="wrap"><ol>
{links}
          <li><span aria-current="page">{escape(current)}</span></li>
      </ol></div>
    </nav>'''


def page_shell(
    *,
    title: str,
    description: str,
    canonical: str,
    jsonld: str,
    body: str,
    category_name: str,
) -> str:
    return f'''<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <meta name="description" content="{escape(description)}">
  <meta name="robots" content="index, follow">
  <link rel="canonical" href="{escape(canonical)}">
  <link rel="alternate" type="application/rss+xml" title="와와학습코칭학원 학습정보 RSS" href="{DOMAIN}/rss.xml">
  <link rel="icon" href="/assets/favicon.svg" type="image/svg+xml">
  <link rel="stylesheet" href="/assets/site.css">
  <meta property="og:locale" content="ko_KR">
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="와와학습코칭학원">
  <meta property="og:title" content="{escape(title)}">
  <meta property="og:description" content="{escape(description)}">
  <meta property="og:url" content="{escape(canonical)}">
  <meta property="og:image" content="{DOMAIN}/assets/generated/jeonguk-coaching-hero.png">
  <script type="application/ld+json">{jsonld}</script>
</head>
{header()}
  <main id="main">
{body}
  </main>
{footer(category_name)}'''


def category_cards(category: Category, grouped: dict[str, list[DetailPage]]) -> str:
    cards = []
    for index, region in enumerate(REGIONS, 1):
        detail_count = len(grouped[region])
        dong_count = len({page.dong for page in grouped[region]})
        href = root_href("전국센터", category.name, region)
        cards.append(
            f'''        <a class="split-region-card" href="{href}">
          <span>REGION {index:02d}</span>
          <strong>{escape(region)} {escape(category.name)}</strong>
          <p>{dong_count:,}개 동네 · {detail_count:,}개 상세 안내</p>
          <em>{escape(region)} 지역 보기 <b aria-hidden="true">→</b></em>
        </a>'''
        )
    return "\n".join(cards)


def sibling_category_links(current: str) -> str:
    links = []
    for category in CATEGORIES:
        active = " is-current" if category.name == current else ""
        links.append(
            f'<a class="split-category-link{active}" href="{root_href("전국센터", category.name)}">{escape(category.name)}</a>'
        )
    return "\n".join(links)


def write_category_page(category: Category, grouped: dict[str, list[DetailPage]]) -> None:
    canonical = canonical_url("전국센터", category.name)
    title = f"{category.name} 지역별 찾기 | {SITE_NAME}"
    description = f"전국 {len(REGIONS)}개 광역지역에서 {category.focus}를 지역별로 확인할 수 있도록 정리했습니다."
    breadcrumbs = [
        (SITE_NAME, f"{DOMAIN}/"),
        ("전국센터", canonical_url("전국센터")),
        (category.name, canonical),
    ]
    children = [(f"{region} {category.name}", canonical_url("전국센터", category.name, region)) for region in REGIONS]
    structured = jsonld_script(
        title=title,
        description=description,
        canonical=canonical,
        breadcrumbs=breadcrumbs,
        children=children,
        about=[category.name, category.focus, category.audience, "지역별 학습코칭"],
    )
    body = f'''{breadcrumb_html([("홈", "/"), ("전국센터", root_href("전국센터"))], category.name)}
    <section class="sub-hero split-hub-hero">
      <div class="wrap narrow">
        <p class="eyebrow">{category.eyebrow}</p>
        <h1>{escape(category.name)} 지역별 안내</h1>
        <p>{escape(category.focus)}입니다. 371개 동네를 13개 광역지역으로 나눠 필요한 지역부터 차분하게 찾을 수 있도록 정리했습니다.</p>
      </div>
    </section>
    <section class="section split-region-section" aria-labelledby="region-directory-title">
      <div class="wrap">
        <div class="section-heading split-section-heading">
          <div><p class="eyebrow">REGIONAL DIRECTORY</p><h2 id="region-directory-title">광역지역부터 선택하세요</h2></div>
          <p>각 광역 허브에서 시·군·구와 동네를 확인한 뒤, 필요한 과목·학년 페이지로 이동할 수 있습니다.</p>
        </div>
        <div class="split-region-grid">
{category_cards(category, grouped)}
        </div>
      </div>
    </section>
    <section class="section muted split-guide-section">
      <div class="wrap">
        <div class="split-guide-grid">
          <article><b>01</b><strong>광역지역 선택</strong><p>서울·경기·인천 등 현재 생활권에 해당하는 지역을 먼저 선택합니다.</p></article>
          <article><b>02</b><strong>시·군·구 확인</strong><p>지역 허브에서 시·군·구별 동네와 제공되는 상세 안내를 확인합니다.</p></article>
          <article><b>03</b><strong>학습 기준 비교</strong><p>학생의 학년, 최근 평가와 오답 기록을 기준으로 상담에 필요한 페이지를 비교합니다.</p></article>
        </div>
      </div>
    </section>
    <section class="section split-category-section">
      <div class="wrap">
        <div class="section-heading"><div><p class="eyebrow">OTHER DIRECTORIES</p><h2>다른 과목·학년 허브</h2></div></div>
        <div class="split-category-links">{sibling_category_links(category.name)}</div>
      </div>
    </section>'''
    path = CENTER_ROOT / category.name / "index.html"
    path.write_text(
        page_shell(title=title, description=description, canonical=canonical, jsonld=structured, body=body, category_name=category.name),
        encoding="utf-8",
    )


def district_cards(category: Category, region: str, grouped: dict[str, list[DetailPage]]) -> str:
    cards = []
    for district in sorted(grouped):
        pages = grouped[district]
        dong_count = len({page.dong for page in pages})
        cards.append(
            f'''        <a class="split-region-card split-district-card" href="{root_href("전국센터", category.name, region, district)}">
          <span>CITY DIRECTORY</span>
          <strong>{escape(district)} {escape(category.name)}</strong>
          <p>{dong_count:,}개 동네 · {len(pages):,}개 상세 안내</p>
          <em>{escape(district)} 지역 보기 <b aria-hidden="true">→</b></em>
        </a>'''
        )
    return "\n".join(cards)


def dong_directory(category: Category, grouped: dict[str, list[DetailPage]], *, open_first: bool = False) -> str:
    panels = []
    for group_index, district in enumerate(sorted(grouped)):
        by_dong: dict[str, list[DetailPage]] = defaultdict(list)
        for page in grouped[district]:
            by_dong[page.dong].append(page)
        dong_cards = []
        for dong in sorted(by_dong):
            pages = {page.role: page for page in by_dong[dong]}
            links = []
            for role in category.role_order:
                page = pages.get(role)
                if not page:
                    raise RuntimeError(f"{category.name}/{dong}: 역할 누락 {role}")
                links.append(
                    f'<a href="{escape(page.canonical)}"><span>{escape(category.role_labels[role])}</span><strong>{escape(page.title)}</strong></a>'
                )
            search = normalize(f"{dong} {district} {category.name} {' '.join(category.role_labels.values())}")
            dong_cards.append(
                f'''              <article class="split-dong-card" data-split-item="true" data-search="{escape(search)}">
                <div class="split-dong-heading"><span>LOCAL</span><h3>{escape(dong)}</h3></div>
                <div class="split-intent-grid">{"".join(links)}</div>
              </article>'''
            )
        open_attr = " open" if open_first and group_index == 0 else ""
        panels.append(
            f'''          <details class="split-district-group" data-split-group="true"{open_attr}>
            <summary><span>{escape(district)}</span><small>{len(by_dong):,}개 동네 · {len(grouped[district]):,}개 안내</small></summary>
            <div class="split-dong-grid">
{"\n".join(dong_cards)}
            </div>
          </details>'''
        )
    return "\n".join(panels)


def directory_tools(total_dongs: int, total_pages: int) -> str:
    return f'''        <div class="split-directory-tools" role="search">
          <div><label for="split-local-search">동네 또는 시·군·구 검색</label><p>지역 안에서 원하는 동네 이름을 입력하세요.</p></div>
          <div class="split-search-control">
            <input id="split-local-search" type="search" autocomplete="off" placeholder="예: 명일동, 강동구" data-split-search="true">
            <button type="button" data-split-clear="true">검색 초기화</button>
          </div>
          <div class="split-directory-status">
            <p data-split-status="true" aria-live="polite">{total_dongs:,}개 동네 · {total_pages:,}개 안내페이지</p>
            <div><button type="button" data-split-expand="true">모두 펼치기</button><button type="button" data-split-collapse="true">모두 접기</button></div>
          </div>
        </div>'''


def write_region_page(category: Category, region: str, pages: list[DetailPage]) -> None:
    canonical = canonical_url("전국센터", category.name, region)
    title = f"{region} {category.name} 지역 찾기 | {SITE_NAME}"
    dong_count = len({page.dong for page in pages})
    district_count = len({page.district for page in pages})
    description = f"{region} {district_count}개 시·군·구, {dong_count}개 동네의 {category.name} 안내를 지역별로 정리했습니다. {category.focus}를 확인하세요."
    breadcrumbs = [
        (SITE_NAME, f"{DOMAIN}/"),
        ("전국센터", canonical_url("전국센터")),
        (category.name, canonical_url("전국센터", category.name)),
        (region, canonical),
    ]
    by_district: dict[str, list[DetailPage]] = defaultdict(list)
    for page in pages:
        by_district[page.district].append(page)
    if region in SPLIT_DISTRICT_REGIONS:
        children = [
            (f"{region} {district} {category.name}", canonical_url("전국센터", category.name, region, district))
            for district in sorted(by_district)
        ]
    else:
        children = [(page.title, page.canonical) for page in sorted(pages, key=lambda item: (item.district, item.dong, category.role_order.index(item.role)))]
    structured = jsonld_script(
        title=title,
        description=description,
        canonical=canonical,
        breadcrumbs=breadcrumbs,
        children=children,
        about=[region, category.name, category.focus, category.audience],
    )
    crumb = breadcrumb_html(
        [("홈", "/"), ("전국센터", root_href("전국센터")), (category.name, root_href("전국센터", category.name))],
        region,
    )
    hero = f'''{crumb}
    <section class="sub-hero split-hub-hero">
      <div class="wrap narrow">
        <p class="eyebrow">{category.eyebrow}</p>
        <h1>{escape(region)} {escape(category.name)} 지역 찾기</h1>
        <p>{escape(region)}의 {district_count}개 시·군·구와 {dong_count}개 동네를 기준으로 {escape(category.focus)}를 찾을 수 있습니다.</p>
        <div class="split-hero-stats"><span><b>{dong_count}</b>개 동네</span><span><b>{len(pages)}</b>개 상세 안내</span></div>
      </div>
    </section>'''
    if region in SPLIT_DISTRICT_REGIONS:
        directory = f'''    <section class="section split-region-section" aria-labelledby="district-directory-title">
      <div class="wrap">
        <div class="section-heading split-section-heading"><div><p class="eyebrow">CITY DIRECTORY</p><h2 id="district-directory-title">{escape(region)} 시 지역부터 선택하세요</h2></div><p>링크 수가 많은 경기 지역은 22개 시 허브로 한 번 더 나눠 필요한 동네를 빠르게 찾을 수 있습니다.</p></div>
        <div class="split-region-grid split-district-grid">
{district_cards(category, region, by_district)}
        </div>
      </div>
    </section>'''
    else:
        directory = f'''    <section class="section split-local-directory" data-split-directory="true" aria-labelledby="local-directory-title">
      <div class="wrap">
        <div class="section-heading split-section-heading"><div><p class="eyebrow">LOCAL DIRECTORY</p><h2 id="local-directory-title">{escape(region)} 동네별 {escape(category.name)}</h2></div><p>시·군·구 목록을 펼치거나 동네를 검색해 네 가지 학습 목적별 상세페이지를 확인하세요.</p></div>
{directory_tools(dong_count, len(pages))}
        <div class="split-directory-groups">
{dong_directory(category, by_district, open_first=True)}
        </div>
      </div>
    </section>'''
    tail = f'''    <section class="section muted split-category-section"><div class="wrap"><div class="split-back-links">
      <a href="{root_href("전국센터", category.name)}"><span>전체 카테고리</span><strong>{escape(category.name)} 광역지역 보기</strong></a>
      <a href="{root_href("전국센터")}"><span>전국센터</span><strong>다른 과목·학년 허브 보기</strong></a>
    </div></div></section>'''
    path = CENTER_ROOT / category.name / region / "index.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        page_shell(title=title, description=description, canonical=canonical, jsonld=structured, body=hero + "\n" + directory + "\n" + tail, category_name=category.name),
        encoding="utf-8",
    )


def write_district_page(category: Category, region: str, district: str, pages: list[DetailPage]) -> None:
    canonical = canonical_url("전국센터", category.name, region, district)
    title = f"{region} {district} {category.name} 지역 찾기 | {SITE_NAME}"
    dong_count = len({page.dong for page in pages})
    description = f"{region} {district} {dong_count}개 동네의 {category.name} 안내를 한곳에 정리했습니다. {category.focus}를 동네별로 확인하세요."
    breadcrumbs = [
        (SITE_NAME, f"{DOMAIN}/"),
        ("전국센터", canonical_url("전국센터")),
        (category.name, canonical_url("전국센터", category.name)),
        (region, canonical_url("전국센터", category.name, region)),
        (district, canonical),
    ]
    children = [(page.title, page.canonical) for page in sorted(pages, key=lambda item: (item.dong, category.role_order.index(item.role)))]
    structured = jsonld_script(
        title=title,
        description=description,
        canonical=canonical,
        breadcrumbs=breadcrumbs,
        children=children,
        about=[region, district, category.name, category.focus, category.audience],
    )
    crumb = breadcrumb_html(
        [
            ("홈", "/"),
            ("전국센터", root_href("전국센터")),
            (category.name, root_href("전국센터", category.name)),
            (region, root_href("전국센터", category.name, region)),
        ],
        district,
    )
    by_district = {district: pages}
    body = f'''{crumb}
    <section class="sub-hero split-hub-hero">
      <div class="wrap narrow">
        <p class="eyebrow">{category.eyebrow}</p>
        <h1>{escape(region)} {escape(district)} {escape(category.name)} 찾기</h1>
        <p>{escape(district)}의 {dong_count}개 동네를 기준으로 {escape(category.focus)}를 확인할 수 있습니다.</p>
        <div class="split-hero-stats"><span><b>{dong_count}</b>개 동네</span><span><b>{len(pages)}</b>개 상세 안내</span></div>
      </div>
    </section>
    <section class="section split-local-directory" data-split-directory="true" aria-labelledby="district-local-title">
      <div class="wrap">
        <div class="section-heading split-section-heading"><div><p class="eyebrow">LOCAL DIRECTORY</p><h2 id="district-local-title">{escape(district)} 동네별 {escape(category.name)}</h2></div><p>동네 이름을 검색하거나 목록에서 학생에게 필요한 상세 안내를 선택하세요.</p></div>
{directory_tools(dong_count, len(pages))}
        <div class="split-directory-groups split-single-district">
{dong_directory(category, by_district, open_first=True)}
        </div>
      </div>
    </section>
    <section class="section muted split-category-section"><div class="wrap"><div class="split-back-links">
      <a href="{root_href("전국센터", category.name, region)}"><span>{escape(region)} 지역</span><strong>{escape(region)} {escape(category.name)} 시 허브 보기</strong></a>
      <a href="{root_href("전국센터", category.name)}"><span>전체 카테고리</span><strong>{escape(category.name)} 광역지역 보기</strong></a>
    </div></div></section>'''
    path = CENTER_ROOT / category.name / region / district / "index.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        page_shell(title=title, description=description, canonical=canonical, jsonld=structured, body=body, category_name=category.name),
        encoding="utf-8",
    )


def detail_breadcrumbs(page: DetailPage) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    visible = [
        ("홈", "/"),
        ("전국센터", root_href("전국센터")),
        (page.category.name, root_href("전국센터", page.category.name)),
        (page.region, root_href("전국센터", page.category.name, page.region)),
    ]
    structured = [
        (SITE_NAME, f"{DOMAIN}/"),
        ("전국센터", canonical_url("전국센터")),
        (page.category.name, canonical_url("전국센터", page.category.name)),
        (page.region, canonical_url("전국센터", page.category.name, page.region)),
    ]
    if page.region in SPLIT_DISTRICT_REGIONS:
        visible.append((page.district, root_href("전국센터", page.category.name, page.region, page.district)))
        structured.append((page.district, canonical_url("전국센터", page.category.name, page.region, page.district)))
    structured.append((page.title, page.canonical))
    return visible, structured


def update_detail_page(page: DetailPage, district_peers: list[DetailPage]) -> bool:
    source = page.path.read_text(encoding="utf-8", errors="strict")
    visible, structured = detail_breadcrumbs(page)
    peer_candidates = [peer for peer in district_peers if peer.role == page.role and peer.dong != page.dong]
    peer_candidates.sort(key=lambda item: item.dong)
    updated = re.sub(
        r'<nav class="seo-breadcrumb" aria-label="현재 위치">.*?</nav>',
        breadcrumb_html(visible, page.title),
        source,
        count=1,
        flags=re.S,
    )
    if updated == source:
        raise RuntimeError(f"브레드크럼 교체 실패: {page.path}")

    json_match = re.search(r'(<script type="application/ld\+json">)(.*?)(</script>)', updated, re.S)
    if not json_match:
        raise RuntimeError(f"JSON-LD 누락: {page.path}")
    data = json.loads(json_match.group(2))
    graph = data.get("@graph", [])
    breadcrumb_node = next((node for node in graph if isinstance(node, dict) and node.get("@type") == "BreadcrumbList"), None)
    if not breadcrumb_node:
        raise RuntimeError(f"BreadcrumbList 누락: {page.path}")
    breadcrumb_node["itemListElement"] = [
        {"@type": "ListItem", "position": index, "name": name, "item": url}
        for index, (name, url) in enumerate(structured, 1)
    ]
    for node in graph:
        if not isinstance(node, dict):
            continue
        types = node.get("@type")
        types = types if isinstance(types, list) else [types]
        if "WebPage" in types or "Article" in types:
            node["dateModified"] = TODAY
    item_node = next((node for node in graph if isinstance(node, dict) and node.get("@type") == "ItemList"), None)
    if item_node:
        parent_items = [
            (f"{page.region} {page.category.name}", canonical_url("전국센터", page.category.name, page.region)),
        ]
        if page.region in SPLIT_DISTRICT_REGIONS:
            parent_items.append(
                (f"{page.region} {page.district} {page.category.name}", canonical_url("전국센터", page.category.name, page.region, page.district))
            )
        parent_items.append(
            (f"전체 {page.category.name}", canonical_url("전국센터", page.category.name))
        )
        # 화면의 내부링크와 구조화 데이터가 같은 역할을 갖도록 기존의
        # 광범위한 24개 목록을 지역 허브 + 같은 학습 목적 인접 동네로 정리한다.
        merged = parent_items + [(peer.title, peer.canonical) for peer in peer_candidates[:8]]
        item_node["name"] = f"{page.title} 지역 허브와 관련 페이지"
        item_node["itemListElement"] = [
            {"@type": "ListItem", "position": index, "name": name, "url": url}
            for index, (name, url) in enumerate(merged, 1)
        ]
        item_node["numberOfItems"] = len(merged)
    encoded_json = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    updated = updated[: json_match.start()] + json_match.group(1) + encoded_json + json_match.group(3) + updated[json_match.end() :]

    parent_links = [
        (f"{page.region} {page.category.name}", root_href("전국센터", page.category.name, page.region)),
    ]
    if page.region in SPLIT_DISTRICT_REGIONS:
        parent_links.append(
            (f"{page.district} {page.category.name}", root_href("전국센터", page.category.name, page.region, page.district))
        )
    parent_links.extend(
        [
            (f"전체 {page.category.name}", root_href("전국센터", page.category.name)),
            ("상담문의", root_href("상담문의")),
        ]
    )
    parent_anchor_html = "\n".join(
        f'            <a class="mini-link" href="{href}">{escape(label)}</a>' for label, href in parent_links
    )
    peer_anchor_html = "\n".join(
        f'            <a class="mini-link" href="{escape(peer.canonical)}">{escape(peer.title)}</a>' for peer in peer_candidates[:8]
    )
    if not peer_anchor_html:
        peer_anchor_html = f'            <a class="mini-link" href="{root_href("전국센터", page.category.name, page.region)}">{escape(page.region)} 전체 지역 보기</a>'
    replacement = f'''<section id="parent-links" class="section muted">
      <div class="wrap center-next-grid">
        <article class="info-card">
          <span class="card-tag">REGIONAL DIRECTORY</span>
          <h3>지역 허브로 이동</h3>
          <div class="mini-link-grid">
{parent_anchor_html}
          </div>
        </article>
        <article class="info-card">
          <span class="card-tag">SAME DISTRICT</span>
          <h3>{escape(page.district)}의 같은 학습 목적 페이지</h3>
          <div class="mini-link-grid">
{peer_anchor_html}
          </div>
        </article>
      </div>
    </section>'''
    updated, count = re.subn(
        r'<section id="parent-links" class="section muted">.*?</section>',
        replacement,
        updated,
        count=1,
        flags=re.S,
    )
    if count != 1:
        raise RuntimeError(f"상위 링크 교체 실패: {page.path}")
    if updated != source:
        page.path.write_text(updated, encoding="utf-8")
        return True
    return False


def main() -> None:
    centers, dong_names = load_centers()
    pages = collect_details(centers, dong_names)
    by_category_region: dict[tuple[str, str], list[DetailPage]] = defaultdict(list)
    by_category_region_district: dict[tuple[str, str, str], list[DetailPage]] = defaultdict(list)
    for page in pages:
        by_category_region[(page.category.name, page.region)].append(page)
        by_category_region_district[(page.category.name, page.region, page.district)].append(page)

    generated_regions = 0
    generated_districts = 0
    for category in CATEGORIES:
        grouped = {region: by_category_region[(category.name, region)] for region in REGIONS}
        if any(not grouped[region] for region in REGIONS):
            raise RuntimeError(f"{category.name}: 광역지역 상세페이지 누락")
        write_category_page(category, grouped)
        for region in REGIONS:
            write_region_page(category, region, grouped[region])
            generated_regions += 1
            if region in SPLIT_DISTRICT_REGIONS:
                districts = sorted({page.district for page in grouped[region]})
                for district in districts:
                    write_district_page(category, region, district, by_category_region_district[(category.name, region, district)])
                    generated_districts += 1

    changed_details = 0
    for page in pages:
        peers = by_category_region_district[(page.category.name, page.region, page.district)]
        changed_details += int(update_detail_page(page, peers))

    print(
        json.dumps(
            {
                "categories": len(CATEGORIES),
                "region_hubs": generated_regions,
                "district_hubs": generated_districts,
                "detail_pages": len(pages),
                "detail_pages_changed": changed_details,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
