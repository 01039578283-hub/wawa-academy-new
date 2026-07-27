from __future__ import annotations

import html
import json
import re
import zlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MATH_ROOT = ROOT / "전국센터" / "수학학원"
INFO_PATH = ROOT / "tools" / "center_info.json"

SUFFIX_LEVELS = [
    ("초등수학학원", "elementary"),
    ("중등수학학원", "middle"),
    ("고등수학학원", "high"),
    ("수학학원", "all"),
]

LEVEL_INFO = {
    "all": {
        "label": "초등·중등·고등",
        "grade_prefix": "",
        "school_key": "",
        "plans": [
            "학년별 개념 누락과 오답 원인을 구분한 뒤 복습 순서를 정하는 것",
            "현재 교재의 진도와 실제 이해 수준을 대조해 주간 분량을 조절하는 것",
            "계산 정확도·문제 해석·풀이 과정을 나누어 필요한 연습부터 배치하는 것",
            "최근 시험 결과와 평소 학습 기록을 함께 보고 우선 보완 단원을 정하는 것",
        ],
    },
    "elementary": {
        "label": "초등",
        "grade_prefix": "초",
        "school_key": "타깃학교\n(초)",
        "plans": [
            "연산 속도보다 수 개념과 문제 문장을 이해하는 과정을 함께 확인하는 것",
            "풀이 이유를 말로 설명하고 스스로 검산하는 기초 습관을 만드는 것",
            "학교 진도에 맞춰 연산·개념·문장제를 무리 없이 연결하는 것",
            "짧게라도 매일 풀고 틀린 문제를 다시 보는 반복 기준을 세우는 것",
        ],
    },
    "middle": {
        "label": "중등",
        "grade_prefix": "중",
        "school_key": "타깃학교\n(중)",
        "plans": [
            "학교 시험 범위와 누적된 개념 공백을 함께 보고 복습 우선순위를 정하는 것",
            "개념 확인·유형 적용·서술형 풀이·오답 재확인을 한 흐름으로 연결하는 것",
            "단원별 이해도와 계산 실수를 분리해 내신 준비 시간을 배분하는 것",
            "시험 직전 몰아서 풀기보다 학교 진도에 맞춘 주간 복습 주기를 만드는 것",
        ],
    },
    "high": {
        "label": "고등",
        "grade_prefix": "고",
        "school_key": "타깃학교\n(고)",
        "plans": [
            "내신 범위와 모의고사 약점 단원을 분리해 제한된 공부 시간을 배분하는 것",
            "개념 간 연결을 확인한 뒤 유형별 풀이 근거와 시간 사용을 함께 점검하는 것",
            "어려운 문제 수보다 반복해서 놓치는 조건과 풀이 단계를 먼저 교정하는 것",
            "현재 진도와 선행 여부보다 시험에서 실제로 해결할 수 있는 범위를 확인하는 것",
        ],
    },
}

SCENARIOS = {
    "all": [
        ("개념은 기억하지만 문제 조건에 맞게 적용하는 과정에서 멈추는 학생", "최근 풀이에서 개념 선택이 어려웠던 문제와 그때 적은 식을 비교합니다.", "개념을 어떤 조건에서 사용해야 하는지 설명하고 유사 문제로 다시 확인합니다."),
        ("계산 실수와 문제 해석 오류가 섞여 오답 원인이 분명하지 않은 학생", "오답을 계산·조건 해석·개념 선택으로 나누고 가장 자주 반복된 원인을 찾습니다.", "반복 비중이 높은 오류부터 짧은 확인 문제와 재풀이 순서로 정리합니다."),
        ("숙제는 완료하지만 틀린 문제를 다시 풀지 않아 같은 실수가 이어지는 학생", "숙제 표시보다 오답을 다시 풀었을 때 스스로 해결되는지 확인합니다.", "오답 재풀이 날짜와 확인 기준을 주간 계획에 넣어 복습이 끝까지 이어지게 합니다."),
        ("학년이 올라가면서 이전 단원의 공백이 현재 진도를 막는 학생", "현재 단원에 필요한 이전 개념을 찾아 최근 시험지와 교재에서 함께 확인합니다.", "필수 선행 개념만 우선 복습하고 현재 학교 진도와 연결되는 문제로 넘어갑니다."),
        ("문제를 오래 풀지만 풀이 순서와 시간 배분이 일정하지 않은 학생", "문제별 풀이 시간과 중간에 막힌 단계를 기록해 시간 지연의 원인을 찾습니다.", "풀이 순서를 단순화하고 제한 시간 안에서 다시 해결하는 연습을 배치합니다."),
        ("정답은 맞히지만 풀이 근거를 설명하기 어려워 응용에서 흔들리는 학생", "맞힌 문제도 풀이 이유와 다른 해결 방법을 설명할 수 있는지 살펴봅니다.", "개념 언어와 식을 연결해 설명한 뒤 조건이 바뀐 문제에 적용해 봅니다."),
    ],
    "elementary": [
        ("연산은 가능하지만 문장제에서 필요한 식을 세우기 어려운 학생", "문장제에서 구해야 하는 값과 주어진 조건을 구분해 표시할 수 있는지 봅니다.", "짧은 문장을 식으로 바꾸고 풀이 과정을 말로 설명하는 연습을 연결합니다."),
        ("계산 속도는 빠르지만 받아올림·부호·단위 실수가 반복되는 학생", "최근 연산에서 실수가 생긴 위치와 검산 습관을 함께 확인합니다.", "속도보다 정확도를 기준으로 짧게 풀고 바로 검산하는 루틴을 만듭니다."),
        ("도형과 측정 단원에서 그림의 조건을 읽는 데 시간이 오래 걸리는 학생", "그림에 표시된 길이·각·단위를 풀이 전에 정리할 수 있는지 확인합니다.", "도형 정보를 직접 표시하고 사용할 개념을 고른 뒤 식을 세우게 합니다."),
        ("수학에 대한 자신감이 낮아 새로운 문제를 시작하기 어려운 학생", "맞힐 수 있는 기본 문제와 멈추는 문제의 난이도 차이를 먼저 살펴봅니다.", "해결 가능한 작은 단계부터 성공 경험을 쌓고 문제 난도를 천천히 조정합니다."),
        ("풀이를 머릿속으로만 처리해 과정 기록과 검산이 부족한 학생", "식과 풀이 과정을 어느 단계까지 기록하는지 현재 교재에서 확인합니다.", "필요한 식을 줄 단위로 적고 마지막에 답의 단위와 조건을 검토하게 합니다."),
        ("학습량은 충분하지만 개념을 자기 말로 설명하기 어려운 학생", "공식이나 계산 방법을 왜 사용하는지 예시와 함께 설명하도록 확인합니다.", "개념을 말과 그림으로 표현한 뒤 기본 문제와 문장제에 차례로 적용합니다."),
    ],
    "middle": [
        ("방정식과 함수처럼 단원이 연결될 때 이전 개념 때문에 막히는 학생", "현재 단원 풀이에 필요한 이전 개념을 시험지와 교재에서 찾아봅니다.", "연결되는 핵심 개념을 먼저 복습하고 학교 진도 문제로 다시 확인합니다."),
        ("시험 준비를 늦게 시작해 여러 단원의 오답을 한꺼번에 처리하는 학생", "시험 범위와 남은 기간을 기준으로 단원별 이해도와 오답량을 나눕니다.", "기본 개념·빈출 유형·서술형·재풀이 순서로 주간 계획을 앞당겨 세웁니다."),
        ("부호와 계산 과정의 실수로 아는 문제에서도 점수를 잃는 학생", "오답에서 부호·이항·분수 계산 중 어느 단계가 반복되는지 확인합니다.", "실수 유형별 확인 규칙을 만들고 같은 유형을 간격을 두고 다시 풉니다."),
        ("객관식은 풀지만 서술형에서 풀이 근거를 빠뜨리는 학생", "답까지 이어지는 식과 설명 중 누락되는 단계를 실제 답안에서 확인합니다.", "채점 기준에 필요한 식과 근거를 나누어 쓰고 완성된 답안을 다시 검토합니다."),
        ("문제집 진도는 빠르지만 단원별 이해 편차가 큰 학생", "진도량보다 단원별 정답률과 설명 가능한 문제의 범위를 비교합니다.", "취약 단원은 기본 유형으로 돌아가고 안정된 단원은 응용 문제로 확장합니다."),
        ("내신 문제와 평소 교재의 난이도 차이에 적응하기 어려운 학생", "학교 시험에서 막힌 유형과 평소 교재의 유사 문제를 함께 대조합니다.", "학교 범위에 맞는 문제를 단계별로 배치하고 시간 안에 푸는 연습을 더합니다."),
    ],
    "high": [
        ("개념을 배웠지만 여러 단원을 연결하는 문제에서 출발점을 잡기 어려운 학생", "문제 조건에서 어떤 개념을 떠올렸고 어디에서 선택이 막혔는지 확인합니다.", "조건과 개념의 연결 근거를 적고 유사한 복합 문제로 다시 적용합니다."),
        ("내신과 모의고사 준비를 함께 하면서 학습 우선순위가 자주 바뀌는 학생", "시험 일정·학교 진도·모의고사 약점을 나누어 실제 공부 시간을 점검합니다.", "가까운 평가를 우선하되 누적 약점 복습 시간을 주간 계획에 고정합니다."),
        ("시간을 많이 쓰는 고난도 문제 때문에 기본·중간 난도 검토가 부족한 학생", "난도별 정답률과 사용 시간을 비교해 점수 손실이 큰 구간을 찾습니다.", "확보해야 할 문제를 먼저 안정시키고 고난도 문제는 풀이 단계별로 나눕니다."),
        ("풀이를 외워 적용하다 조건이 바뀌면 해결 과정이 흔들리는 학생", "외운 풀이와 개념에 근거해 다시 구성할 수 있는 풀이를 구분합니다.", "공식 선택 이유를 설명하고 조건이 달라진 문제에서 풀이를 다시 설계합니다."),
        ("오답노트는 작성하지만 일정 시간이 지난 뒤 재풀이가 이어지지 않는 학생", "기록된 오답 중 다시 풀어 정답까지 도달한 문제의 비율을 확인합니다.", "오답 원인과 재풀이 날짜를 함께 기록하고 간격을 둔 확인 문제를 배치합니다."),
        ("계산 과정이 길어질수록 검산과 시간 관리가 무너지는 학생", "긴 풀이에서 시간이 집중되는 단계와 자주 생기는 계산 오류를 표시합니다.", "중간 결과 확인 지점을 정하고 제한 시간 안에서 풀이를 다시 점검합니다."),
    ],
}

PARENT_CHECKS = [
    "수업 횟수보다 진단 결과가 다음 주 계획과 오답 재풀이에 어떻게 반영되는지 확인합니다.",
    "숙제 양보다 학생이 스스로 해결한 범위와 도움을 받은 범위를 구분해 봅니다.",
    "점수 변화만 보지 않고 계산 실수·개념 공백·문제 해석 중 어떤 원인이 줄고 있는지 살펴봅니다.",
    "시험 직전 계획뿐 아니라 평소 복습 주기와 누적 오답 확인 방식이 이어지는지 확인합니다.",
    "현재 진도보다 학생이 풀이 이유를 설명하고 비슷한 문제를 다시 해결할 수 있는지 봅니다.",
    "피드백을 받을 때 완료한 분량과 함께 막힌 단원, 다음 보완 순서가 구체적인지 확인합니다.",
]

EVIDENCE_PROMPTS = [
    "최근 시험지에서 정답과 오답을 각각 한 문제씩 골라 풀이 과정을 남겨 둡니다.",
    "현재 교재에서 혼자 푼 문제와 도움을 받아 푼 문제를 구분해 표시합니다.",
    "자주 멈추는 단원과 계산 실수가 반복되는 유형을 한 가지씩 적어 둡니다.",
    "평일·주말의 실제 수학 공부 시간과 숙제 완료 시간을 간단히 기록합니다.",
    "최근 오답 중 다시 풀어 맞힌 문제와 여전히 어려운 문제를 나누어 둡니다.",
    "학교 진도, 사용 교재, 다음 시험 일정을 확인할 수 있는 자료를 준비합니다.",
]


def choose(items: list, *seed_parts: str):
    seed = zlib.crc32("|".join(seed_parts).encode("utf-8"))
    return items[seed % len(items)]


def load_center_info() -> dict[str, dict]:
    raw = json.loads(INFO_PATH.read_text(encoding="utf-8"))
    return {key.replace(" ", ""): value for key, value in raw.items()}


def parse_list(value: str) -> list[str]:
    seen = set()
    result = []
    for item in (value or "").split(","):
        item = item.strip()
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def page_identity(page_dir: Path) -> tuple[str, str]:
    leaf = page_dir.name
    for suffix, level in SUFFIX_LEVELS:
        if leaf.endswith(suffix):
            return leaf[: -len(suffix)], level
    raise ValueError(f"unknown math page suffix: {leaf}")


def page_title(source: str) -> str:
    match = re.search(r"<h1\b[^>]*>(.*?)</h1>", source, re.S)
    if not match:
        raise ValueError("H1 not found")
    return html.unescape(re.sub(r"<[^>]+>", "", match.group(1))).strip()


def school_context(branch: dict, level: str, title: str) -> tuple[str, str]:
    info = LEVEL_INFO[level]
    if level == "all":
        schools = []
        for key in ("타깃학교\n(초)", "타깃학교\n(중)", "타깃학교\n(고)"):
            schools.extend(parse_list(branch.get(key, "")))
        schools = list(dict.fromkeys(schools))
        label = "제공된 학교정보"
    else:
        schools = parse_list(branch.get(info["school_key"], ""))
        label = f'{info["label"]} 학교정보'

    if schools:
        names = "·".join(schools[:4])
        return (
            names,
            f"센터정보의 {label}에는 {names} 등이 기재되어 있습니다. {title} 상담에서는 재학 학교와 실제 시험 범위를 확인한 뒤 준비 순서를 정합니다.",
        )
    return (
        "상담 시 재학 학교 확인",
        f"센터정보에는 {info['label']} 타깃학교가 별도로 기재되어 있지 않습니다. {title} 상담에서 재학 학교와 현재 시험 범위를 먼저 확인합니다.",
    )


def grade_context(branch: dict, level: str, title: str) -> tuple[str, str]:
    info = LEVEL_INFO[level]
    all_grades = parse_list(branch.get("가능학년\n(수학)", ""))
    grades = all_grades if level == "all" else [g for g in all_grades if g.startswith(info["grade_prefix"])]
    center = branch["센터명"]
    if grades:
        names = "·".join(grades)
        return (
            names,
            f"{center} 센터정보에 확인된 수학 가능 학년은 {names}입니다. {title} 상담에서는 해당 학년과 현재 진도를 함께 대조합니다.",
        )
    return (
        "센터 상담 확인 필요",
        f"{center} 센터정보에는 {info['label']} 수학 가능 학년이 명시되어 있지 않습니다. {title} 수업 가능 여부는 상담에서 먼저 확인해야 합니다.",
    )


def location_context(branch: dict, dong: str) -> str:
    address = normalize_text(branch["센터 주소"])
    guide = normalize_text(branch.get("위치안내", ""))
    if guide:
        return f"등록 주소는 {address}이며, 센터정보의 위치안내에는 ‘{guide}’로 기재되어 있습니다. 방문 전 상담 시간과 실제 동선을 다시 확인하는 것이 좋습니다."
    return f"등록된 센터 주소는 {address}입니다. {dong}에서 방문할 경우 상담 시간과 실제 이동 경로를 먼저 확인하는 것이 좋습니다."


def render_section(page_dir: Path, source: str, branch: dict, dong: str, level: str) -> str:
    title = page_title(source)
    info = LEVEL_INFO[level]
    key = page_dir.name
    scenario, diagnosis, action = choose(SCENARIOS[level], key, "scenario")
    plan = choose(info["plans"], key, "plan")
    parent_check = choose(PARENT_CHECKS, key, "parent")
    evidence = choose(EVIDENCE_PROMPTS, key, "evidence")
    grades_label, grades_text = grade_context(branch, level, title)
    schools_label, schools_text = school_context(branch, level, title)
    location_text = location_context(branch, dong)
    center = normalize_text(branch["센터명"])
    region = " ".join(
        x for x in (normalize_text(branch["지역"]), normalize_text(branch["시or구"]), dong) if x
    )

    esc = html.escape
    return f'''<!-- seo-geo-enhancement:start -->
    <section class="section seo-geo-section" aria-label="{esc(title)} 지역별 수학 학습 안내">
      <div class="wrap seo-geo-enhancement">
        <article id="geo-summary" class="geo-summary-panel">
          <p class="eyebrow">KEY SUMMARY</p>
          <h2>{esc(title)} 핵심 요약</h2>
          <p>{esc(title)} 상담에서는 {esc(region)}의 {esc(center)} 등록정보와 실제 수학 가능 학년을 기준으로, {esc(scenario)} 상황을 먼저 살펴봅니다. {esc(info['label'])} 수학에서는 {esc(plan)}이 중요합니다.</p>
          <div class="geo-fact-grid">
            <article class="geo-fact-card">
              <span>센터·지역 기준</span>
              <strong>{esc(center)}</strong>
              <p>{esc(location_text)}</p>
            </article>
            <article class="geo-fact-card">
              <span>수학 가능 학년</span>
              <strong>{esc(grades_label)}</strong>
              <p>{esc(grades_text)}</p>
            </article>
            <article class="geo-fact-card">
              <span>우선 확인할 학생 상황</span>
              <strong>{esc(scenario)}</strong>
              <p>{esc(schools_text)}</p>
            </article>
          </div>
        </article>

        <article id="geo-answer" class="geo-answer-panel">
          <p class="eyebrow">ANSWER READY</p>
          <h2>{esc(title)} 상담에서 확인할 내용</h2>
          <p>{esc(title)}을 알아볼 때는 광고 문구보다 최근 풀이 기록, 수학 가능 학년, 재학 학교의 시험 범위, 센터 등록정보를 함께 확인해야 합니다. 이 페이지는 제공된 센터정보와 {esc(scenario)} 상황을 기준으로 상담 준비 내용을 정리했습니다.</p>
          <div class="geo-answer-grid">
            <article class="geo-answer-card">
              <strong>{esc(info['label'])} 수학에서 무엇을 먼저 확인하나요?</strong>
              <p>{esc(diagnosis)} {esc(title)} 상담에서는 이 기록을 현재 교재와 함께 비교합니다.</p>
            </article>
            <article class="geo-answer-card">
              <strong>확인한 약점은 어떻게 관리하나요?</strong>
              <p>{esc(action)} 이어서 {esc(plan)}을 주간 계획에 반영합니다.</p>
            </article>
            <article class="geo-answer-card">
              <strong>학교 시험 준비는 어떻게 연결하나요?</strong>
              <p>{esc(schools_text)}</p>
            </article>
            <article class="geo-answer-card">
              <strong>학부모는 어떤 변화를 확인하면 좋나요?</strong>
              <p>{esc(parent_check)} {esc(center)}의 구체적인 피드백 방식은 상담에서 확인합니다.</p>
            </article>
          </div>
          <div class="geo-mini-faq">
            <details open>
              <summary>{esc(title)} 상담 전에 무엇을 준비하면 좋나요?</summary>
              <p>{esc(evidence)} 또한 {esc(grades_text)}</p>
            </details>
          </div>
        </article>

        <article id="geo-checklist" class="geo-checklist-panel">
          <p class="eyebrow">CONSULTING CHECKLIST</p>
          <h2>{esc(title)} 상담 전 체크리스트</h2>
          <div class="geo-checklist-grid">
            <article class="geo-check-card"><b>01</b><strong>풀이 기록</strong><p>{esc(evidence)} {esc(diagnosis)}</p></article>
            <article class="geo-check-card"><b>02</b><strong>가능 학년</strong><p>{esc(grades_text)}</p></article>
            <article class="geo-check-card"><b>03</b><strong>학교·시험 범위</strong><p>{esc(schools_text)}</p></article>
            <article class="geo-check-card"><b>04</b><strong>우선 개선 목표</strong><p>{esc(scenario)}이라면 {esc(action)} 상담에서는 {esc(plan)}을 우선 목표로 정합니다.</p></article>
          </div>
        </article>
      </div>
    </section>
    <!-- seo-geo-enhancement:end -->'''


def process_page(page_dir: Path, center_info: dict[str, dict]) -> bool:
    dong, level = page_identity(page_dir)
    branch = center_info[dong.replace(" ", "")]
    path = page_dir / "index.html"
    source = path.read_text(encoding="utf-8", errors="ignore")
    replacement = render_section(page_dir, source, branch, dong, level)
    updated, count = re.subn(
        r"<!-- seo-geo-enhancement:start -->.*?<!-- seo-geo-enhancement:end -->",
        replacement,
        source,
        count=1,
        flags=re.S,
    )
    if count != 1:
        raise RuntimeError(f"SEO/GEO section not found exactly once: {path}")
    if updated != source:
        path.write_text(updated, encoding="utf-8")
        return True
    return False


def main() -> None:
    center_info = load_center_info()
    targets = sorted(path.parent for path in MATH_ROOT.glob("*/index.html"))
    changed = 0
    errors = 0
    for page_dir in targets:
        try:
            if process_page(page_dir, center_info):
                changed += 1
        except Exception as exc:  # noqa: BLE001
            errors += 1
            print(f"ERROR {page_dir}: {exc}")
    print(json.dumps({"targets": len(targets), "changed": changed, "errors": errors}, ensure_ascii=False))


if __name__ == "__main__":
    main()
