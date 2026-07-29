from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "전국센터" / "index.html"
DOMAIN = "https://xn--ol5ba64b839b.com"
SITE_NAME = "와와학습코칭학원"
TODAY = date.today().isoformat()
TITLE = f"전국센터 과목·학년별 학원 안내 | {SITE_NAME}"
DESCRIPTION = (
    "전국센터에서 수학·영어·영수의 일반, 초등, 중등, 고등 학원 안내와 "
    "초등학생·중학생·고등학생 학습관리 페이지를 지역별로 확인하세요."
)


@dataclass(frozen=True)
class Hub:
    name: str
    eyebrow: str
    summary: str


SUBJECT_HUBS = (
    Hub("수학학원", "MATH", "학년을 한정하지 않고 개념·유형·오답 흐름을 점검하는 수학 안내"),
    Hub("영어학원", "ENGLISH", "학년을 한정하지 않고 어휘·문법·독해 흐름을 점검하는 영어 안내"),
    Hub("영수학원", "ENGLISH & MATH", "영어와 수학의 주간 분량과 복습 균형을 함께 살피는 통합 안내"),
)

LEVEL_SUBJECT_HUBS = (
    Hub("초등수학학원", "ELEMENTARY MATH", "연산 정확도와 기초 개념, 문제 읽기 습관을 중심으로 확인"),
    Hub("중등수학학원", "MIDDLE MATH", "학교 진도와 내신 범위, 서술형·오답 관리를 중심으로 확인"),
    Hub("고등수학학원", "HIGH MATH", "내신·모의고사 범위와 풀이 시간, 취약 단원을 중심으로 확인"),
    Hub("초등영어학원", "ELEMENTARY ENGLISH", "어휘 기초와 문장 읽기, 규칙적인 복습 습관을 중심으로 확인"),
    Hub("중등영어학원", "MIDDLE ENGLISH", "교과서 본문과 문법·서술형 내신 준비를 중심으로 확인"),
    Hub("고등영어학원", "HIGH ENGLISH", "내신 지문과 모의고사 독해, 어휘·시간 관리를 중심으로 확인"),
    Hub("초등영수학원", "ELEMENTARY ENGLISH & MATH", "영어·수학 기초와 주간 공부 습관을 함께 확인"),
    Hub("중등영수학원", "MIDDLE ENGLISH & MATH", "두 과목의 내신 범위와 시험기간 분량 배분을 함께 확인"),
    Hub("고등영수학원", "HIGH ENGLISH & MATH", "내신·모의고사 일정에 맞춘 영어·수학 시간 배분을 함께 확인"),
)

GRADE_HUBS = (
    Hub("초등학생학원", "ELEMENTARY", "공부 습관과 기초 개념, 과목별 학습 시작점을 종합적으로 확인"),
    Hub("중학생학원", "MIDDLE SCHOOL", "학교 진도·수행평가·내신 준비와 주간 루틴을 종합적으로 확인"),
    Hub("고등학생학원", "HIGH SCHOOL", "학년 단계와 내신·모의고사 일정, 자기관리 흐름을 종합적으로 확인"),
)

ALL_HUBS = SUBJECT_HUBS + LEVEL_SUBJECT_HUBS + GRADE_HUBS


def esc(value: str) -> str:
    return html.escape(value, quote=True)


def href(*parts: str) -> str:
    return "/" + "/".join(quote(part, safe="") for part in parts) + "/"


def canonical(*parts: str) -> str:
    return DOMAIN + href(*parts)


def cards(hubs: tuple[Hub, ...]) -> str:
    return "\n".join(
        f'''          <a class="center-card" href="{href("전국센터", hub.name)}">
            <span>{esc(hub.eyebrow)}</span>
            <h3>{esc(hub.name)}</h3>
            <p>{esc(hub.summary)}</p>
          </a>'''
        for hub in hubs
    )


def main_html() -> str:
    return f'''  <main id="main">
    <nav class="seo-breadcrumb" aria-label="현재 위치">
      <div class="wrap"><ol>
        <li><a href="/">홈</a></li>
        <li><span aria-current="page">전국센터</span></li>
      </ol></div>
    </nav>
    <section class="sub-hero center-hero">
      <div class="wrap narrow">
        <p class="eyebrow">NATIONAL ACADEMY DIRECTORY</p>
        <h1>과목과 학년을 나눠 찾는 전국센터</h1>
        <p>같은 과목도 초등·중등·고등의 학습 목표는 다릅니다. 먼저 과목과 학년 단계를 선택한 뒤 광역지역과 동네 순서로 필요한 안내를 확인하세요.</p>
      </div>
    </section>

    <section class="section">
      <div class="wrap">
        <div class="section-heading">
          <p class="eyebrow">SUBJECT OVERVIEW</p>
          <h2>학년을 정하기 전 과목부터 살펴보기</h2>
          <p>현재 학년보다 과목의 전반적인 학습 상태를 먼저 확인하고 싶을 때 선택하는 일반 과목 허브입니다.</p>
        </div>
        <div class="center-card-grid">
{cards(SUBJECT_HUBS)}
        </div>
      </div>
    </section>

    <section class="section muted">
      <div class="wrap">
        <div class="section-heading">
          <p class="eyebrow">GRADE × SUBJECT</p>
          <h2>학년과 과목이 정해져 있다면 바로 선택하세요</h2>
          <p>초등·중등·고등별 수학, 영어, 영수 학습 목적을 분리했습니다. 각 허브에는 해당 목적의 371개 지역 안내만 연결됩니다.</p>
        </div>
        <div class="center-card-grid">
{cards(LEVEL_SUBJECT_HUBS)}
        </div>
      </div>
    </section>

    <section class="section">
      <div class="wrap">
        <div class="section-heading">
          <p class="eyebrow">GRADE OVERVIEW</p>
          <h2>과목보다 학년 단계의 공부 흐름을 먼저 보기</h2>
          <p>과목 하나보다 공부 습관, 시간 관리, 내신 준비처럼 학년 전체의 학습 흐름을 점검할 때 선택하세요.</p>
        </div>
        <div class="center-card-grid">
{cards(GRADE_HUBS)}
        </div>
      </div>
    </section>

    <section class="section muted site-summary-section">
      <div class="wrap">
        <div class="section-heading">
          <p class="eyebrow">HOW TO USE</p>
          <h2>학생의 현재 고민에 맞춰 세 단계로 찾습니다</h2>
          <p>검색어가 비슷해도 페이지가 맡는 역할은 겹치지 않도록 구분했습니다.</p>
        </div>
        <div class="site-summary-grid">
          <article class="site-summary-card"><span>01</span><h3>과목·학년 선택</h3><p>수학·영어·영수와 초등·중등·고등 중 현재 상담 목적에 가까운 허브를 고릅니다.</p></article>
          <article class="site-summary-card"><span>02</span><h3>광역지역 선택</h3><p>13개 광역지역에서 생활권에 해당하는 지역을 선택합니다.</p></article>
          <article class="site-summary-card"><span>03</span><h3>동네 안내 확인</h3><p>지역별 학습 상황, 추천 학생, FAQ와 상담 전 확인 항목을 살펴봅니다.</p></article>
          <article class="site-summary-card"><span>04</span><h3>상담 방향 정리</h3><p>최근 어려웠던 단원과 오답, 공부 시간, 시험 일정을 정리해 상담에 활용합니다.</p></article>
        </div>
        <div class="site-summary-links">
          <a class="mini-link" href="{href("학습코칭")}">학습코칭 방식 보기</a>
          <a class="mini-link" href="{href("상담문의")}">상담문의</a>
        </div>
      </div>
    </section>
  </main>'''


def update_jsonld(source: str) -> str:
    match = re.search(r'(<script type="application/ld\+json">)(.*?)(</script>)', source, re.S)
    if not match:
        raise RuntimeError("전국센터 JSON-LD를 찾지 못했습니다.")
    data = json.loads(match.group(2))
    graph = data.get("@graph", [])
    item_list = None
    for node in graph:
        if not isinstance(node, dict):
            continue
        types = node.get("@type")
        types = types if isinstance(types, list) else [types]
        if "EducationalOrganization" in types:
            node["knowsAbout"] = [hub.name for hub in ALL_HUBS] + ["학습코칭"]
        if "WebPage" in types:
            node["name"] = TITLE
            node["description"] = DESCRIPTION
            node["dateModified"] = TODAY
        if "Article" in types:
            node["headline"] = TITLE
            node["description"] = DESCRIPTION
            node["dateModified"] = TODAY
            node["about"] = [{"@type": "Thing", "name": hub.name} for hub in ALL_HUBS]
        if "Service" in types:
            node["name"] = "전국센터 과목·학년별 학습코칭 안내"
            node["description"] = DESCRIPTION
        if "ItemList" in types and str(node.get("@id", "")).endswith("#category-list"):
            item_list = node
    if item_list is None:
        raise RuntimeError("전국센터 ItemList를 찾지 못했습니다.")
    item_list["name"] = "전국센터 직속 학원 허브"
    item_list["numberOfItems"] = len(ALL_HUBS)
    item_list["itemListElement"] = [
        {
            "@type": "ListItem",
            "position": index,
            "name": hub.name,
            "url": canonical("전국센터", hub.name),
        }
        for index, hub in enumerate(ALL_HUBS, 1)
    ]
    encoded = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return source[: match.start()] + match.group(1) + encoded + match.group(3) + source[match.end() :]


def replace_metadata(source: str) -> str:
    replacements = (
        (r"<title>.*?</title>", f"<title>{esc(TITLE)}</title>"),
        (r'<meta name="description" content="[^"]*">', f'<meta name="description" content="{esc(DESCRIPTION)}">'),
        (r'<meta property="og:title" content="[^"]*">', f'<meta property="og:title" content="{esc(TITLE)}">'),
        (r'<meta property="og:description" content="[^"]*">', f'<meta property="og:description" content="{esc(DESCRIPTION)}">'),
    )
    for pattern, replacement in replacements:
        source, count = re.subn(pattern, replacement, source, count=1, flags=re.S)
        if count != 1:
            raise RuntimeError(f"메타데이터 교체 실패: {pattern}")
    return source


def main() -> None:
    source = PAGE.read_text(encoding="utf-8", errors="strict")
    source = replace_metadata(source)
    source = update_jsonld(source)
    source, count = re.subn(r'<main id="main">.*?</main>', main_html(), source, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError("전국센터 main 교체 실패")
    PAGE.write_text(source, encoding="utf-8")
    print(json.dumps({"direct_hubs": len(ALL_HUBS), "page": str(PAGE)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
