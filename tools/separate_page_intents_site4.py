from __future__ import annotations

import html
import json
import re
import zlib
from collections import Counter
from pathlib import Path
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
CENTER_ROOT = ROOT / "전국센터"
INFO_PATH = ROOT / "tools" / "center_info.json"
DOMAIN = "https://xn--ol5ba64b839b.com"

STAGES = {
    "all": {
        "course": "전 학년",
        "student": "초등·중등·고등 학생",
        "prefix": "",
        "school": None,
        "assessment": "현재 교재와 최근 평가 기록",
        "calendar": "학교 진도와 다음 평가 일정",
        "habit": "학년이 바뀌어도 이어갈 수 있는 주간 공부 흐름",
    },
    "elementary": {
        "course": "초등",
        "student": "초등학생",
        "prefix": "초",
        "school": "타깃학교\n(초)",
        "assessment": "학교 진도와 단원별 기초 이해",
        "calendar": "학기 진도와 숙제 일정",
        "habit": "짧게라도 매일 시작하고 끝낸 내용을 확인하는 습관",
    },
    "middle": {
        "course": "중등",
        "student": "중학생",
        "prefix": "중",
        "school": "타깃학교\n(중)",
        "assessment": "학교별 시험 범위와 최근 내신 결과",
        "calendar": "중간·기말고사와 수행평가 일정",
        "habit": "시험 범위를 미리 나누고 평소 복습을 누적하는 습관",
    },
    "high": {
        "course": "고등",
        "student": "고등학생",
        "prefix": "고",
        "school": "타깃학교\n(고)",
        "assessment": "내신 범위와 모의고사 문항별 결과",
        "calendar": "내신·수행평가·모의고사 일정",
        "habit": "학년 일정에 맞춰 제한된 자습 시간을 배분하는 습관",
    },
}

SUBJECTS = {
    "math": {
        "label": "수학",
        "grade_field": "가능학년\n(수학)",
        "skills": "개념 이해·계산 정확도·유형 적용·오답 원인",
        "record": "최근 수학 시험지와 풀이 과정이 남은 오답",
        "result": "같은 유형을 다시 풀 때 풀이 근거와 정확도가 달라지는지",
        "subject_problem": [
            "개념은 기억하지만 문제 조건에 맞는 식을 고르기 어려운 경우",
            "계산 실수와 개념 공백이 섞여 오답 원인이 분명하지 않은 경우",
            "문제집 진도는 나가지만 틀린 문제의 재풀이가 이어지지 않는 경우",
            "풀이 시간을 많이 쓰고도 검산할 여유를 확보하지 못하는 경우",
        ],
        "habit_task": "수학 문제 풀이와 오답 재풀이",
    },
    "english": {
        "label": "영어",
        "grade_field": "가능학년\n(영어)",
        "skills": "어휘 회상·문법 적용·구문 해석·독해 근거",
        "record": "최근 영어 시험지와 어휘·문법·독해에서 막힌 기록",
        "result": "새 지문에서도 문장 구조와 정답 근거를 스스로 찾는지",
        "subject_problem": [
            "어휘는 외웠지만 문장 안에서 의미를 바로 떠올리기 어려운 경우",
            "문법 규칙은 알지만 실제 문장과 서술형에 적용하기 어려운 경우",
            "지문은 읽지만 정답 근거가 되는 문장을 구분하지 못하는 경우",
            "영어 과제를 끝내도 어휘와 오답 복습이 다음 날로 이어지지 않는 경우",
        ],
        "habit_task": "영어 어휘·구문 복습과 독해 연습",
    },
    "combined": {
        "label": "영어·수학",
        "grade_field": None,
        "skills": "영어와 수학의 과목별 약점·주간 분량·시험 우선순위",
        "record": "최근 영어·수학 시험지와 두 과목의 실제 공부 시간",
        "result": "취약 과목을 보완하면서 두 과목의 복습 주기가 함께 유지되는지",
        "subject_problem": [
            "영어와 수학 중 한 과목에 시간이 치우쳐 다른 과목 복습이 밀리는 경우",
            "두 과목의 시험 범위를 같은 방식으로 준비해 효율이 떨어지는 경우",
            "과제량은 많지만 과목별 오답 재학습 시간이 따로 확보되지 않는 경우",
            "취약 과목이 달라질 때마다 주간 우선순위가 자주 흔들리는 경우",
        ],
        "habit_task": "영어·수학 과목별 과제와 복습 시간 배분",
    },
    "general": {
        "label": "주요 과목",
        "grade_field": None,
        "skills": "과목별 우선순위·과제 수행·복습 간격·자기점검",
        "record": "최근 시험지와 과목별 과제·공부 시간 기록",
        "result": "계획한 과목을 정해진 시간 안에 마치고 부족한 부분을 다시 확인하는지",
        "subject_problem": [
            "해야 할 과목이 많아 무엇부터 시작할지 정하지 못하는 경우",
            "숙제는 하지만 시험 범위 복습과 오답 확인이 뒤로 밀리는 경우",
            "계획표는 작성해도 완료 기준이 없어 실행 여부를 판단하기 어려운 경우",
            "학년이 올라간 뒤 과목별 공부량 변화에 적응하지 못하는 경우",
        ],
        "habit_task": "주요 과목의 과제·복습·오답 확인",
    },
}

CATEGORY_RULES = {
    "수학학원": {
        "family": "subject",
        "subject": "math",
        "suffixes": [("초등수학학원", "elementary"), ("중등수학학원", "middle"), ("고등수학학원", "high"), ("수학학원", "all")],
    },
    "영어학원": {
        "family": "subject",
        "subject": "english",
        "suffixes": [("초등영어학원", "elementary"), ("중등영어학원", "middle"), ("고등영어학원", "high"), ("영어학원", "all")],
    },
    "영수학원": {
        "family": "subject",
        "subject": "combined",
        "suffixes": [("초등영수학원", "elementary"), ("중등영수학원", "middle"), ("고등영수학원", "high"), ("영수학원", "all")],
    },
    "초등학생학원": {
        "family": "grade",
        "stage": "elementary",
        "suffixes": [("초등학생수학학원", "math"), ("초등학생영어학원", "english"), ("초등학생영수학원", "combined"), ("초등학생학원", "general")],
    },
    "중학생학원": {
        "family": "grade",
        "stage": "middle",
        "suffixes": [("중학생수학학원", "math"), ("중학생영어학원", "english"), ("중학생영수학원", "combined"), ("중학생학원", "general")],
    },
    "고등학생학원": {
        "family": "grade",
        "stage": "high",
        "suffixes": [("고등학생수학학원", "math"), ("고등학생영어학원", "english"), ("고등학생영수학원", "combined"), ("고등학생학원", "general")],
    },
}

GRADE_SCENARIOS = {
    "elementary": [
        "공부를 시작하는 시간이 매일 달라 짧은 과제도 미루는 학생",
        "문제를 푼 뒤 확인하지 않고 바로 다음 활동으로 넘어가는 학생",
        "도움을 받으면 풀지만 혼자 시작하는 순서를 정하기 어려운 학생",
        "학습량이 길어질수록 집중력이 떨어져 완료 기준이 흐려지는 학생",
    ],
    "middle": [
        "시험 기간에만 공부량을 늘려 평소 복습 기록이 남지 않는 학생",
        "과목별 과제와 수행평가가 겹치면 우선순위를 정하기 어려운 학생",
        "계획한 분량을 끝내지 못해 다음 날 일정까지 연쇄적으로 밀리는 학생",
        "오답을 정리해도 며칠 뒤 다시 푸는 일정이 이어지지 않는 학생",
    ],
    "high": [
        "내신과 모의고사 준비를 함께 하며 자습 시간 배분이 자주 흔들리는 학생",
        "학년이 올라간 뒤 과목별 공부량이 늘어 복습 시간을 확보하지 못하는 학생",
        "긴 계획은 세우지만 하루 단위 완료 기준이 없어 실행을 점검하기 어려운 학생",
        "취약 단원에만 오래 머물러 다른 과목과 누적 복습이 밀리는 학생",
    ],
}


def choose(items: list[str], *parts: str) -> str:
    return items[zlib.crc32("|".join(parts).encode("utf-8")) % len(items)]


def normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def parse_list(value: str) -> list[str]:
    return list(dict.fromkeys(x.strip() for x in (value or "").split(",") if x.strip()))


def load_centers() -> dict[str, dict]:
    raw = json.loads(INFO_PATH.read_text(encoding="utf-8"))
    return {key.replace(" ", ""): value for key, value in raw.items()}


def page_title(source: str) -> str:
    match = re.search(r"<h1\b[^>]*>(.*?)</h1>", source, re.S)
    if not match:
        raise ValueError("H1 not found")
    return html.unescape(re.sub(r"<[^>]+>", "", match.group(1))).strip()


def classify(category: str, leaf: str) -> dict:
    rule = CATEGORY_RULES[category]
    for suffix, dimension in rule["suffixes"]:
        if leaf.endswith(suffix):
            dong = leaf[: -len(suffix)]
            if rule["family"] == "subject":
                return {"family": "subject", "subject": rule["subject"], "stage": dimension, "dong": dong}
            return {"family": "grade", "subject": dimension, "stage": rule["stage"], "dong": dong}
    raise ValueError(f"unknown page type: {category}/{leaf}")


def role_key(identity: dict) -> str:
    return f"{identity['family']}-{identity['stage']}-{identity['subject']}"


def stage_label(identity: dict) -> str:
    return STAGES[identity["stage"]]["course"]


def role_content(identity: dict) -> dict:
    stage = STAGES[identity["stage"]]
    subject = SUBJECTS[identity["subject"]]
    if identity["family"] == "subject":
        scope = f"{stage['course']} {subject['label']} 교과 성취"
        lead = (
            f"이 페이지는 {stage['course']} {subject['label']}의 {subject['skills']}을 중심으로, "
            f"{stage['assessment']}에서 확인된 약점을 어떻게 보완할지 안내합니다."
        )
        boundary = (
            f"과목 내용과 평가 대비가 중심입니다. {stage['student']}의 하루 시간표나 공부 습관 자체보다 "
            f"{subject['label']}에서 무엇을 이해하지 못했고 어떤 문제를 다시 풀어야 하는지에 초점을 둡니다."
        )
        scenario_bank = subject["subject_problem"]
        action = (
            f"{stage['assessment']}을 기준으로 {subject['skills']}을 나누어 보고, "
            f"{stage['calendar']}에 맞춰 개념 확인과 재풀이 순서를 정합니다."
        )
        metric = subject["result"]
    else:
        scope = f"{stage['student']} {subject['label']} 학습 운영"
        lead = (
            f"이 페이지는 {stage['student']}이 {subject['habit_task']}을 꾸준히 실행하도록 "
            f"시간 배분·과제 완료·복습 간격을 설계하는 방법을 안내합니다."
        )
        boundary = (
            f"학년 단계와 생활 리듬이 중심입니다. {subject['label']}의 특정 단원이나 시험 문항 분석보다 "
            f"{stage['habit']}을 실제 주간 계획으로 만드는 데 초점을 둡니다."
        )
        scenario_bank = GRADE_SCENARIOS[identity["stage"]]
        action = (
            f"{stage['calendar']}을 먼저 펼쳐 놓고 {subject['habit_task']}에 필요한 시간을 나눈 뒤, "
            f"완료 여부와 다음 복습 날짜를 주간 단위로 확인합니다."
        )
        metric = f"{stage['habit']}이 실제 기록으로 이어지는지"
    return {"scope": scope, "lead": lead, "boundary": boundary, "scenarios": scenario_bank, "action": action, "metric": metric}


def grades_for(branch: dict, identity: dict) -> list[str]:
    subject_key = identity["subject"]
    fields = []
    if subject_key in ("math", "english"):
        fields = [SUBJECTS[subject_key]["grade_field"]]
    elif subject_key == "combined":
        english = parse_list(branch.get(SUBJECTS["english"]["grade_field"], ""))
        math = set(parse_list(branch.get(SUBJECTS["math"]["grade_field"], "")))
        values = [grade for grade in english if grade in math]
        prefix = STAGES[identity["stage"]]["prefix"]
        return values if not prefix else [value for value in values if value.startswith(prefix)]
    else:
        fields = ["가능학년\n(국어)", "가능학년\n(영어)", "가능학년\n(수학)"]
    values: list[str] = []
    for field in fields:
        values.extend(parse_list(branch.get(field, "")))
    values = list(dict.fromkeys(values))
    prefix = STAGES[identity["stage"]]["prefix"]
    return values if not prefix else [value for value in values if value.startswith(prefix)]


def schools_for(branch: dict, identity: dict) -> list[str]:
    school_key = STAGES[identity["stage"]]["school"]
    if school_key:
        return parse_list(branch.get(school_key, ""))
    result: list[str] = []
    for key in ("타깃학교\n(초)", "타깃학교\n(중)", "타깃학교\n(고)"):
        result.extend(parse_list(branch.get(key, "")))
    return list(dict.fromkeys(result))


def counterpart(identity: dict) -> tuple[str, str] | None:
    if identity["stage"] == "all" or identity["subject"] == "general":
        return None
    stage_terms = {
        "elementary": ("초등", "초등학생", "초등학생학원"),
        "middle": ("중등", "중학생", "중학생학원"),
        "high": ("고등", "고등학생", "고등학생학원"),
    }
    course, student, grade_category = stage_terms[identity["stage"]]
    subject_label = SUBJECTS[identity["subject"]]["label"].replace("영어·수학", "영수")
    dong = identity["dong"]
    if identity["family"] == "subject":
        leaf = f"{dong}{student}{subject_label}학원"
        label = f"{dong} {student} {SUBJECTS[identity['subject']]['label']}학원"
        url = f"{DOMAIN}/{quote('전국센터')}/{quote(grade_category)}/{quote(leaf)}/"
    else:
        subject_category = {"math": "수학학원", "english": "영어학원", "combined": "영수학원"}[identity["subject"]]
        leaf = f"{dong}{course}{subject_label}학원"
        label = f"{dong} {course} {SUBJECTS[identity['subject']]['label']}학원"
        url = f"{DOMAIN}/{quote('전국센터')}/{quote(subject_category)}/{quote(leaf)}/"
    return label, url


def facts(branch: dict, identity: dict) -> dict:
    grades = grades_for(branch, identity)
    schools = schools_for(branch, identity)
    center = normalize(branch.get("센터명", ""))
    address = normalize(branch.get("센터 주소", ""))
    region = " ".join(filter(None, [normalize(branch.get("지역", "")), normalize(branch.get("시or구", "")), identity["dong"]]))
    return {
        "center": center,
        "address": address,
        "region": region,
        "grades": "·".join(grades) if grades else "상담 시 가능 학년 확인",
        "schools": "·".join(schools[:5]) if schools else "상담 시 재학 학교와 시험 범위 확인",
        "has_grades": bool(grades),
        "has_schools": bool(schools),
    }


def description_for(title: str, role: dict, fact: dict, identity: dict) -> str:
    subject = SUBJECTS[identity["subject"]]["label"]
    if identity["family"] == "subject":
        tail = f"{subject} 과목의 진단·평가 대비·오답 보완 기준을 확인하세요."
    else:
        tail = f"{STAGES[identity['stage']]['student']}의 시간 관리·과제·복습 습관 기준을 확인하세요."
    return f"{title} 안내입니다. {role['scope']} 중심으로 {tail}"


def render_section(title: str, identity: dict, branch: dict) -> str:
    role = role_content(identity)
    fact = facts(branch, identity)
    scenario = choose(role["scenarios"], title, role_key(identity), "scenario")
    counterpart_info = counterpart(identity)
    grade_text = (
        f"센터정보에 확인된 관련 가능 학년은 {fact['grades']}입니다."
        if fact["has_grades"]
        else "센터정보에 관련 가능 학년이 명시되지 않아 상담에서 수업 가능 여부를 먼저 확인해야 합니다."
    )
    school_text = (
        f"센터정보에 기재된 참고 학교는 {fact['schools']}입니다. 실제 재학 학교와 시험 범위는 상담에서 다시 확인합니다."
        if fact["has_schools"]
        else "센터정보에 참고 학교가 별도로 기재되지 않아 상담에서 재학 학교와 실제 시험 범위를 확인합니다."
    )
    if counterpart_info:
        other_label, other_url = counterpart_info
        distinction = (
            f'<div class="intent-counterpart"><strong>비슷한 이름의 페이지와 어떻게 다른가요?</strong>'
            f'<p>{html.escape(role["boundary"])} 학년 운영 관점 또는 과목 성취 관점을 함께 비교하려면 '
            f'<a href="{html.escape(other_url)}">{html.escape(other_label)}</a> 안내를 확인하세요.</p></div>'
        )
    else:
        distinction = f'<div class="intent-counterpart"><strong>이 페이지의 범위</strong><p>{html.escape(role["boundary"])}</p></div>'

    if identity["family"] == "subject":
        summary_eyebrow = "SUBJECT ACHIEVEMENT"
        summary_heading = f"{title}에서 확인할 교과 학습 범위"
        summary_intro = (
            f"{role['lead']} {fact['region']}의 {fact['center']} 센터정보와 실제 평가 자료를 함께 보고, "
            "점수보다 먼저 교과 내용에서 막힌 지점을 찾습니다."
        )
        answer_eyebrow = "ASSESSMENT PLAN"
        answer_heading = f"{title} 내신·평가 준비 기준"
        answer_intro = (
            f"{scenario}라면 진도량을 늘리기 전에 틀린 문항의 원인을 구분해야 합니다. {role['action']}"
        )
        cards = [
            ("교과 역할", f"{role['scope']}에 집중합니다. {role['boundary']}"),
            ("수업 가능 범위", f"{grade_text} 등록 주소는 {fact['address']}입니다."),
            ("평가 자료", school_text),
            ("성취 확인", f"{role['metric']} 살펴봅니다. 센터별 문항 피드백 방식은 상담에서 확인하세요."),
        ]
        mini_question = f"{title} 과목 상담에 가져갈 자료는 무엇인가요?"
        mini_answer = f"{SUBJECTS[identity['subject']]['record']}을 준비하고, 틀린 문항에서 멈춘 풀이 단계와 다음 평가 범위를 표시해 주세요."
        checklist_eyebrow = "SUBJECT CHECKLIST"
        checklist_heading = f"{title} 교과 진단 체크리스트"
        checks = [
            ("01", "평가 기록", f"{SUBJECTS[identity['subject']]['record']}에서 정답과 오답의 풀이 근거를 대조합니다."),
            ("02", "약점 범위", f"{stage_label(identity)} 과정에서 반복해서 막힌 단원과 문제 유형을 구분합니다."),
            ("03", "오답 원인", f"{scenario}인지 실제 답안과 교재 표시를 통해 확인합니다."),
            ("04", "재풀이 기준", f"{role['metric']} 다음 교과 점검에서 확인할 기준으로 정합니다."),
        ]
    else:
        summary_eyebrow = "STUDY ROUTINE"
        summary_heading = f"{title} 학년 단계에 맞춘 공부 운영"
        summary_intro = (
            f"{role['lead']} {fact['region']}의 {fact['center']} 센터정보를 바탕으로, "
            "학생이 학교생활과 함께 지속할 수 있는 실행 단위를 정리했습니다."
        )
        answer_eyebrow = "WEEKLY PRACTICE"
        answer_heading = f"{title} 주간 시간표와 실행 점검"
        answer_intro = (
            f"{scenario}이라면 공부 내용을 더 추가하기 전에 실제로 사용할 수 있는 시간부터 계산해야 합니다. {role['action']}"
        )
        cards = [
            ("학년 운영 역할", f"{role['scope']}에 집중합니다. {role['boundary']}"),
            ("생활 시간", f"{grade_text} 학교·이동·휴식 시간을 제외한 실제 학습 가능 시간을 먼저 찾습니다."),
            ("학사 일정", school_text),
            ("실행 확인", f"{role['metric']} 기록으로 확인합니다. 센터별 플래너 점검 방식은 상담에서 확인하세요."),
        ]
        mini_question = f"{title} 학습 습관 상담에는 어떤 기록이 필요한가요?"
        mini_answer = f"최근 일주일의 시작 시간·완료 과제·미룬 복습을 간단히 적고, {SUBJECTS[identity['subject']]['record']}도 함께 알려주세요."
        checklist_eyebrow = "ROUTINE CHECKLIST"
        checklist_heading = f"{title} 학습 실행 체크리스트"
        checks = [
            ("01", "생활 시간", "평일과 주말에 실제로 공부를 시작할 수 있는 시간과 종료 시간을 적습니다."),
            ("02", "과제 일정", f"{STAGES[identity['stage']]['calendar']}을 날짜순으로 펼쳐 놓고 마감이 가까운 과제를 표시합니다."),
            ("03", "복습 간격", f"{scenario}인지 최근 일주일의 계획과 완료 기록을 비교합니다."),
            ("04", "완료 기준", f"{role['metric']} 다음 주 플래너에서 확인할 기준으로 정합니다."),
        ]

    card_html = "".join(
        f'<article class="geo-answer-card"><strong>{html.escape(heading)}</strong><p>{html.escape(body)}</p></article>'
        for heading, body in cards
    )
    check_html = "".join(
        f'<article class="geo-check-card"><b>{number}</b><strong>{html.escape(heading)}</strong><p>{html.escape(body)}</p></article>'
        for number, heading, body in checks
    )

    esc = html.escape
    return f'''<!-- seo-geo-enhancement:start -->
    <section class="section seo-geo-section intent-role-section" data-intent-role="{esc(role_key(identity))}" aria-label="{esc(title)} 학습 안내">
      <div class="wrap seo-geo-enhancement">
        <article id="geo-summary" class="geo-summary-panel">
          <p class="eyebrow">{esc(summary_eyebrow)}</p>
          <h2 id="intent-role-title">{esc(summary_heading)}</h2>
          <p>{esc(summary_intro)}</p>
          <div class="intent-role-badges" aria-label="페이지 핵심 역할">
            <span>{esc(role['scope'])}</span><span>{esc(SUBJECTS[identity['subject']]['label'])}</span><span>{esc(STAGES[identity['stage']]['student'])}</span>
          </div>
          {distinction}
        </article>

        <article id="geo-answer" class="geo-answer-panel">
          <p class="eyebrow">{esc(answer_eyebrow)}</p>
          <h2>{esc(answer_heading)}</h2>
          <p>{esc(answer_intro)}</p>
          <div class="geo-answer-grid">
            {card_html}
          </div>
          <div class="geo-mini-faq">
            <details open><summary>{esc(mini_question)}</summary><p>{esc(mini_answer)}</p></details>
          </div>
        </article>

        <article id="geo-checklist" class="geo-checklist-panel">
          <p class="eyebrow">{esc(checklist_eyebrow)}</p>
          <h2>{esc(checklist_heading)}</h2>
          <div class="geo-checklist-grid">
            {check_html}
          </div>
        </article>
      </div>
    </section>
    <!-- seo-geo-enhancement:end -->'''


def extract_faqs(source: str) -> list[tuple[str, str]]:
    match = re.search(r'<div class="faq-list">(.*?)</div>\s*</div>\s*</section>', source, re.S)
    if not match:
        raise ValueError("FAQ list not found")
    return re.findall(r"<details>\s*<summary>(.*?)</summary><p>(.*?)</p></details>", match.group(1), re.S)


def render_faqs(faqs: list[tuple[str, str]]) -> str:
    return "\n".join(f"          <details><summary>{q}</summary><p>{a}</p></details>" for q, a in faqs)


def role_faqs(title: str, identity: dict, branch: dict, existing: list[tuple[str, str]]) -> list[tuple[str, str]]:
    role = role_content(identity)
    fact = facts(branch, identity)
    scenario = choose(role["scenarios"], title, role_key(identity), "faq-scenario")
    result = list(existing)
    result[0] = (
        f"{title} 페이지는 어떤 학습 문제를 중점적으로 다루나요?",
        f"{title} 페이지는 {role['scope']}을 중심으로 안내합니다. {role['lead']} 특히 {scenario}인지 먼저 확인합니다.",
    )
    result[1] = (
        f"{title} 상담에서는 무엇을 먼저 확인하나요?",
        f"{SUBJECTS[identity['subject']]['record']}과 실제 공부 시간을 먼저 확인합니다. 이후 {role['action']}",
    )
    counterpart_info = counterpart(identity)
    if counterpart_info:
        other_label, _ = counterpart_info
        result[2] = (
            f"{title}과 {other_label} 안내는 무엇이 다른가요?",
            f"{title}은 {role['scope']}을 담당합니다. {role['boundary']} 두 페이지는 같은 학생을 다루더라도 상담에서 먼저 확인하는 기준이 다릅니다.",
        )
    else:
        result[2] = (
            f"{title} 상담에 학교와 학년 정보를 준비해야 하나요?",
            f"네. 확인된 가능 학년은 {fact['grades']}이며, 참고 학교 정보는 {fact['schools']}입니다. 실제 재학 학교와 시험 범위는 상담에서 다시 확인합니다.",
        )
    return result


def replace_meta(source: str, description: str) -> str:
    escaped = html.escape(description, quote=True)
    patterns = [
        (r'(<meta name="description" content=")[^"]*(">)', escaped),
        (r'(<meta property="og:description" content=")[^"]*(">)', escaped),
        (r'(<meta name="twitter:description" content=")[^"]*(">)', escaped),
    ]
    result = source
    for pattern, value in patterns:
        result = re.sub(pattern, lambda m: m.group(1) + value + m.group(2), result, count=1)
    return result


def type_names(node: dict) -> list[str]:
    value = node.get("@type")
    return value if isinstance(value, list) else [value] if value else []


def find_node(graph: list[dict], type_name: str) -> dict | None:
    return next((node for node in graph if isinstance(node, dict) and type_name in type_names(node)), None)


def role_topics(title: str, identity: dict, role: dict, fact: dict) -> tuple[list[dict], list[dict]]:
    about = [
        {"@type": "Place", "name": fact["region"]},
        {"@type": "Thing", "name": title},
        {"@type": "Thing", "name": role["scope"]},
    ]
    mentions = [
        {"@type": "Thing", "name": x}
        for x in [
            SUBJECTS[identity["subject"]]["skills"],
            STAGES[identity["stage"]]["assessment"],
            STAGES[identity["stage"]]["calendar"],
            role["metric"],
        ]
    ]
    return about, mentions


def update_jsonld(source: str, title: str, description: str, identity: dict, branch: dict, faqs: list[tuple[str, str]]) -> str:
    match = re.search(r'<script type="application/ld\+json">(.*?)</script>', source, re.S)
    if not match:
        raise ValueError("JSON-LD not found")
    data = json.loads(match.group(1))
    graph = data.get("@graph", [])
    role = role_content(identity)
    fact = facts(branch, identity)
    about, mentions = role_topics(title, identity, role, fact)
    org = find_node(graph, "EducationalOrganization")
    webpage = find_node(graph, "WebPage")
    service = find_node(graph, "Service")
    article = find_node(graph, "Article")
    faq = find_node(graph, "FAQPage")
    if not all((org, webpage, service, article, faq)):
        raise ValueError("required JSON-LD node missing")

    # Generated testimonial banks are not evidence-backed reviews. Keep the
    # verified organization facts, but never recreate Review/AggregateRating.
    org.pop("review", None)
    org.pop("aggregateRating", None)
    graph[:] = [
        node
        for node in graph
        if not (
            isinstance(node, dict)
            and any(kind in ("Review", "AggregateRating") for kind in type_names(node))
        )
    ]

    webpage["description"] = description
    webpage["about"] = about
    webpage["mentions"] = mentions
    webpage["keywords"] = ", ".join([title, role["scope"], SUBJECTS[identity["subject"]]["label"], STAGES[identity["stage"]]["student"], identity["dong"]])
    service["description"] = description
    service["serviceType"] = role["scope"]
    service["about"] = about
    service["mentions"] = mentions
    article["description"] = description
    article["articleSection"] = [
        role["scope"],
        "학습 기준",
        "학생 상황",
        "상담 전 체크리스트",
        "학습 상담 참고 사례",
        "FAQ",
        "내부링크",
    ]
    article["about"] = about
    article["mentions"] = mentions
    article["keywords"] = webpage["keywords"]
    faq["mainEntity"] = [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}}
        for q, a in faqs
    ]
    faq["about"] = about
    faq["mentions"] = mentions
    rendered = '<script type="application/ld+json">' + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "</script>"
    return source[: match.start()] + rendered + source[match.end() :]


def href_counter(source: str) -> Counter:
    return Counter(html.unescape(x) for x in re.findall(r'\bhref="([^"]+)"', source))


def canonical(source: str) -> str:
    match = re.search(r'<link rel="canonical" href="([^"]+)">', source)
    if not match:
        raise ValueError("canonical missing")
    return match.group(1)


def process_page(path: Path, centers: dict[str, dict]) -> tuple[bool, str]:
    source = path.read_text(encoding="utf-8", errors="strict")
    before_canonical = canonical(source)
    before_hrefs = href_counter(source)
    category = path.parent.parent.name
    identity = classify(category, path.parent.name)
    branch = centers[identity["dong"].replace(" ", "")]
    title = page_title(source)
    role = role_content(identity)
    fact = facts(branch, identity)
    description = description_for(title, role, fact, identity)
    existing_faqs = extract_faqs(source)
    if len(existing_faqs) != 6:
        raise ValueError(f"expected 6 FAQs, found {len(existing_faqs)}")
    faqs = role_faqs(title, identity, branch, existing_faqs)

    updated = replace_meta(source, description)
    replacement = render_section(title, identity, branch)
    updated, count = re.subn(
        r"<!-- seo-geo-enhancement:start -->.*?<!-- seo-geo-enhancement:end -->",
        replacement,
        updated,
        count=1,
        flags=re.S,
    )
    if count != 1:
        raise ValueError("SEO/GEO section marker missing or duplicated")
    faq_html = render_faqs(faqs)
    updated, count = re.subn(
        r'(<div class="faq-list">\n)(.*?)(\n\s*</div>\s*\n\s*</div>\s*\n\s*</section>)',
        lambda m: m.group(1) + faq_html + m.group(3),
        updated,
        count=1,
        flags=re.S,
    )
    if count != 1:
        raise ValueError("FAQ HTML replacement failed")
    updated = update_jsonld(updated, title, description, identity, branch, faqs)

    if canonical(updated) != before_canonical:
        raise ValueError("canonical changed")
    after_hrefs = href_counter(updated)
    lost = before_hrefs - after_hrefs
    if lost:
        raise ValueError(f"existing href removed: {lost.most_common(3)}")
    if updated != source:
        path.write_text(updated, encoding="utf-8", newline="\n")
        return True, role_key(identity)
    return False, role_key(identity)


def main() -> None:
    centers = load_centers()
    targets = sorted(
        path
        for path in CENTER_ROOT.glob("*/*/index.html")
        if 'data-intent-role="' in path.read_text(encoding="utf-8", errors="ignore")
    )
    counts: Counter[str] = Counter()
    changed = 0
    errors: list[str] = []
    for path in targets:
        try:
            did_change, key = process_page(path, centers)
            counts[key] += 1
            changed += int(did_change)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{path}: {exc}")
            if len(errors) <= 20:
                print(f"ERROR {errors[-1]}")
    result = {"targets": len(targets), "changed": changed, "roles": dict(sorted(counts.items())), "errors": len(errors)}
    print(json.dumps(result, ensure_ascii=False))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
