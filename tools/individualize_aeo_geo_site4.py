from __future__ import annotations

import html
import json
import re
import zlib
from collections import Counter
from pathlib import Path

from separate_page_intents_site4 import (
    CENTER_ROOT,
    ROOT,
    canonical,
    classify,
    counterpart,
    extract_faqs,
    facts as base_facts,
    find_node,
    href_counter,
    load_centers,
    normalize,
    page_title,
    replace_meta,
    render_faqs,
    role_key,
)


MODIFIED_DATE = "2026-07-27"

STAGE = {
    "all": {
        "label": "전 학년",
        "student": "초등·중등·고등 학생",
        "assessment": "현재 교재와 최근 평가 기록",
        "schedule": "학교 진도와 다음 평가 일정",
        "habit": "주간 공부 시간과 과제·복습 완료 기록",
    },
    "elementary": {
        "label": "초등",
        "student": "초등학생",
        "assessment": "학교 진도와 기초 이해 상태",
        "schedule": "학교 숙제와 학기 학습 일정",
        "habit": "혼자 시작하는 시간과 과제 마무리 기록",
    },
    "middle": {
        "label": "중등",
        "student": "중학생",
        "assessment": "학교별 시험 범위와 최근 내신 결과",
        "schedule": "중간·기말고사와 수행평가 일정",
        "habit": "평소 복습과 시험 범위 누적 기록",
    },
    "high": {
        "label": "고등",
        "student": "고등학생",
        "assessment": "내신 범위와 모의고사 문항별 결과",
        "schedule": "내신·수행평가·모의고사 일정",
        "habit": "과목별 자습 시간과 주간 복습 기록",
    },
}

SUBJECT = {
    "math": {
        "label": "수학",
        "focus": "개념 이해·계산 정확도·유형 적용·오답 근거",
        "record": "최근 수학 시험지, 풀이 흔적, 오답 노트",
        "measure": "같은 유형을 다시 풀 때 풀이 근거와 정확도가 달라지는지",
        "problems": [
            "개념은 기억하지만 문제 조건에 맞는 식을 고르기 어려운 학생",
            "계산 실수와 개념 공백이 섞여 오답 원인이 분명하지 않은 학생",
            "진도는 나갔지만 응용 문제의 풀이 순서를 설명하기 어려운 학생",
            "문제 풀이 시간이 길어 검산과 재확인 시간이 부족한 학생",
            "맞힌 문제도 풀이 근거가 흔들려 비슷한 유형에서 다시 틀리는 학생",
            "오답을 표시하지만 다시 푸는 날짜와 완료 기준이 없는 학생",
            "시험 범위를 여러 번 봐도 취약 단원이 계속 바뀌는 학생",
            "선행 진도보다 이전 단원의 연결 개념을 먼저 보완해야 하는 학생",
        ],
    },
    "english": {
        "label": "영어",
        "focus": "어휘 회상·문법 적용·구문 해석·독해 근거",
        "record": "최근 영어 시험지, 어휘 테스트, 독해 지문 표시",
        "measure": "새 지문에서도 문장 구조와 정답 근거를 스스로 찾는지",
        "problems": [
            "어휘를 외웠지만 문장 안에서 뜻을 바로 떠올리기 어려운 학생",
            "문법 규칙은 알지만 실제 문장과 서술형에 적용하기 어려운 학생",
            "지문은 읽지만 정답 근거가 되는 문장을 구분하지 못하는 학생",
            "본문 암기는 하지만 변형 문제와 영작에서 다시 막히는 학생",
            "해석 속도가 일정하지 않아 시험 시간 안에 검토를 마치지 못하는 학생",
            "단어와 오답 복습이 다음 주 학습으로 이어지지 않는 학생",
            "문장별 해석은 가능하지만 글의 흐름과 요지를 연결하기 어려운 학생",
            "듣기·어휘·독해 중 무엇을 먼저 보완할지 우선순위가 필요한 학생",
        ],
    },
    "combined": {
        "label": "영어·수학",
        "focus": "과목별 약점·주간 분량·시험 우선순위·오답 재학습",
        "record": "최근 영어·수학 시험지, 과목별 공부 시간, 오답 기록",
        "measure": "취약 과목을 보완하면서 다른 과목의 복습 주기도 유지되는지",
        "problems": [
            "영어와 수학 중 한 과목에 시간이 치우쳐 다른 과목 복습이 밀리는 학생",
            "두 과목 시험 범위를 같은 방식으로 준비해 효율이 떨어지는 학생",
            "과제량은 많지만 과목별 오답과 복습 시간을 따로 확보하지 못하는 학생",
            "취약 과목이 달라질 때마다 주간 공부 우선순위가 흔들리는 학생",
            "영어 암기와 수학 문제 풀이를 하루 계획 안에 배치하기 어려운 학생",
            "시험 직전에만 두 과목을 몰아서 공부해 평소 기록이 부족한 학생",
            "과목별 목표는 있지만 완료 기준이 없어 계획을 평가하기 어려운 학생",
            "한 과목의 성취 변화가 다른 과목의 학습량 감소로 이어지는 학생",
        ],
    },
    "general": {
        "label": "주요 과목",
        "focus": "과목별 우선순위·과제 수행·복습 간격·자기점검",
        "record": "최근 시험지, 과제 수행 기록, 주간 플래너",
        "measure": "계획한 과목을 정해진 시간 안에 마치고 부족한 부분을 다시 확인하는지",
        "problems": [
            "해야 할 과목이 많아 무엇부터 시작할지 정하기 어려운 학생",
            "숙제는 하지만 시험 범위 복습과 오답 확인이 뒤로 밀리는 학생",
            "계획표는 작성해도 완료 기준이 없어 실행 여부를 판단하기 어려운 학생",
            "학년이 바뀐 뒤 과목별 공부량 변화에 적응하지 못한 학생",
            "공부 시간은 길지만 과목별 목표와 결과 기록이 남지 않는 학생",
            "평일과 주말의 공부 흐름이 달라 계획이 자주 끊기는 학생",
            "부족한 과목을 알지만 구체적인 복습 순서를 정하지 못하는 학생",
            "시험이 끝난 뒤 오답과 다음 학습 계획을 연결하지 못하는 학생",
        ],
    },
}

SUMMARY_TEMPLATES = [
    "{title} 페이지는 {situation}에게 필요한 확인 순서를 안내합니다. {assessment_and} {record_obj} 함께 살펴 {focus} 가운데 어디에서 학습이 막히는지 먼저 구분합니다.",
    "{region}에서 {title} 상담을 알아볼 때에는 진도보다 현재 기록을 먼저 확인해야 합니다. {situation}이라면 {record_obj} 기준으로 {focus_obj} 나누어 보는 것이 출발점입니다.",
    "{title}의 핵심은 학습량을 바로 늘리는 것이 아니라 막힌 원인을 구체화하는 데 있습니다. {assessment}, {record_obj} 대조해 {situation}의 우선 보완 항목을 정리합니다.",
    "이 안내는 {situation}을 기준으로 작성했습니다. {center}에서는 상담 시 {assessment_and} 실제 학습 기록을 확인하고, {focus_obj} 순서대로 점검할 수 있습니다.",
    "{region} {stage_student}의 학습 방향은 최근 결과와 공부 과정을 함께 봐야 정할 수 있습니다. {title} 페이지에서는 {record_obj} 바탕으로 {focus_obj} 확인하는 기준을 설명합니다.",
    "{title}을 찾는 학부모님이라면 먼저 학생이 어디에서 시간을 쓰고 무엇을 반복해 틀리는지 확인해 보세요. {situation}의 경우 {assessment_and} {record_subject} 상담의 핵심 자료가 됩니다.",
    "{center}의 {title} 안내는 학생의 현재 상태를 단정하지 않습니다. {assessment_and} {record_obj} 확인한 뒤 {focus} 가운데 우선 관리할 항목을 정하는 방식으로 설명합니다.",
    "같은 {stage_label} 과정이라도 필요한 관리 순서는 다릅니다. {title} 페이지는 {situation}을 예로 들어 {record}에서 확인할 {focus_obj} 구체적으로 정리했습니다.",
]

ANSWER_TEMPLATES = [
    "상담에서는 {record_obj} 먼저 펼쳐 보고, {schedule}에 맞춰 보완 순서를 정합니다. 학생이 현재 수행할 수 있는 분량과 다음 점검 시 확인할 기준을 함께 정하는 것이 중요합니다.",
    "{assessment}만으로 학습 방향을 단정하지 않습니다. 실제 답안·교재 표시·공부 시간 기록을 함께 확인해 {focus_obj} 구분하고, {schedule}에 맞는 실행 순서를 잡습니다.",
    "현재 교재와 최근 평가 결과가 서로 다르게 보인다면 풀이 과정과 복습 기록을 먼저 비교합니다. 이후 {schedule_obj} 기준으로 개념 확인, 과제, 재풀이의 순서를 나눕니다.",
    "학생에게 필요한 것은 많은 과제가 아니라 확인 가능한 완료 기준입니다. {record}에서 시작해 {measure_obj} 다음 점검 기준으로 설정합니다.",
    "상담 전에는 최근 결과뿐 아니라 평소 공부 과정도 준비하는 것이 좋습니다. {habit_obj} {record_and} 함께 보면 과제량, 복습 간격, 재학습 시점을 더 구체적으로 정할 수 있습니다.",
    "{situation}이라면 먼저 한 주 동안 실제로 실행한 기록을 살펴야 합니다. 그 기록과 {schedule_obj} 연결해 당장 보완할 항목과 이후 확인할 항목을 구분합니다.",
    "{title} 상담의 답은 학생마다 달라질 수 있습니다. 다만 {assessment}, {record}, {habit} 세 자료를 함께 확인하면 현재 우선순위와 실행 가능한 분량을 보다 분명하게 정할 수 있습니다.",
    "진단 결과는 계획으로 끝내지 않고 다음 확인 시점과 연결해야 합니다. {focus_obj} 나누어 점검하고 {measure_obj} 실제 기록으로 확인합니다.",
]

CHECK_TEMPLATES = {
    "record": [
        "{record}에서 맞힌 문제와 틀린 문제의 근거가 어떻게 다른지 표시합니다.",
        "최근 자료 중 학생이 직접 풀이하거나 표시한 {record_obj} 준비합니다.",
        "{record_obj} 날짜순으로 놓고 같은 실수가 반복되는 구간을 찾습니다.",
        "점수만 보지 않고 {record}에 남은 풀이 과정과 복습 흔적을 확인합니다.",
        "상담 전에 {record} 중 현재 수준을 가장 잘 보여주는 자료를 골라 둡니다.",
        "{record_obj} 통해 진도와 실제 이해 수준이 일치하는지 비교합니다.",
        "최근 한 달의 {record_obj} 모아 오답이 생긴 시점과 재확인 여부를 살펴봅니다.",
        "학생이 설명할 수 있는 문제와 다시 확인해야 할 문제를 {record}에서 구분합니다.",
    ],
    "schedule": [
        "{schedule_obj} 달력에 표시하고 준비 기간을 주간 단위로 나눕니다.",
        "{schedule_and} 현재 교재 진도를 비교해 먼저 끝내야 할 범위를 정합니다.",
        "{schedule}에 맞춰 새 학습과 누적 복습이 겹치지 않도록 시간을 배분합니다.",
        "마감이 가까운 과제와 평가를 {schedule} 순서대로 배열합니다.",
        "{schedule} 전까지 확보할 수 있는 실제 공부 시간을 계산합니다.",
        "{schedule_obj} 기준으로 평일 학습과 주말 재점검의 역할을 나눕니다.",
        "학교 일정이 바뀌어도 조정할 수 있도록 {schedule}별 최소 완료 기준을 정합니다.",
        "{schedule} 가운데 학생이 부담을 크게 느끼는 시점을 먼저 표시합니다.",
    ],
    "situation": [
        "{situation}인지 최근 답안과 교재 표시를 통해 확인합니다.",
        "학생이 {situation}에 해당하는지 말로 추측하지 않고 실제 기록과 비교합니다.",
        "최근 일주일 기록에서 {situation}의 징후가 반복되는지 살펴봅니다.",
        "{situation}이라면 원인을 학습량·이해·시간 배분으로 다시 나눕니다.",
        "교재 진도와 평가 결과를 비교해 {situation}이 어느 범위에서 나타나는지 확인합니다.",
        "{situation}의 원인이 한 과목에만 있는지 다른 일정과 연결되는지 구분합니다.",
        "학생이 스스로 설명한 어려움과 {situation}의 실제 기록이 일치하는지 봅니다.",
        "{situation}이 반복되는 시점과 그 직전 학습 과정을 함께 확인합니다.",
    ],
    "measure": [
        "다음 점검에서는 {measure_obj} 확인해 계획의 효과를 평가합니다.",
        "학습량보다 {measure_obj} 기준으로 다음 단계로 넘어갈지 판단합니다.",
        "{measure_obj} 학생이 직접 설명할 수 있을 때까지 재확인합니다.",
        "이번 계획의 완료 기준은 {measure}로 정하고 날짜를 함께 기록합니다.",
        "다음 평가 전에는 {measure_obj} 확인해 복습 간격을 조정합니다.",
        "{measure_obj} 교재와 플래너 양쪽에 남겨 변화 과정을 비교합니다.",
        "수업 후에는 {measure_obj} 확인하고 부족하면 같은 범위를 다시 배치합니다.",
        "학부모 상담에서는 {measure_obj} 중심으로 학습 변화와 다음 계획을 공유합니다.",
    ],
}


def pick(items: list[str], *parts: str) -> str:
    return items[zlib.crc32("|".join(parts).encode("utf-8")) % len(items)]


def with_josa(value: str, consonant: str, vowel: str) -> str:
    """Attach a Korean particle according to the last Hangul syllable."""
    for char in reversed(value.strip()):
        code = ord(char)
        if 0xAC00 <= code <= 0xD7A3:
            return value + (consonant if (code - 0xAC00) % 28 else vowel)
        if char.isalnum():
            break
    return value + consonant


def clean_sentence(value: str, limit: int = 190) -> str:
    value = normalize(value)
    if len(value) <= limit:
        return value
    shortened = value[:limit].rsplit(" ", 1)[0].rstrip(" ,·")
    return shortened + "…"


def verified_facts(branch: dict, identity: dict) -> dict:
    fact = base_facts(branch, identity)
    fact.update(
        {
            "location": clean_sentence(branch.get("위치안내", "")),
            "office": normalize(branch.get("교육지원청명칭", "")),
            "registration": normalize(branch.get("교육지원청 등록번호", "")),
            "tuition_url": normalize(branch.get("센터 교습비", "")),
        }
    )
    return fact


def taxonomy(identity: dict) -> dict:
    stage = STAGE[identity["stage"]]
    subject = SUBJECT[identity["subject"]]
    if identity["family"] == "subject":
        scope = f"{stage['label']} {subject['label']} 교과 학습"
        boundary = (
            f"{subject['label']}의 개념·문항·평가 대비가 중심입니다. "
            f"{stage['student']}의 전체 시간표보다 {subject['label']}에서 막힌 지점과 재학습 순서를 먼저 확인합니다."
        )
        intent_core = (
            "교과 진단형 안내이므로 최근 문항의 풀이 근거, 단원 연결, 평가 범위를 세분화해 "
            "보완 순서와 재확인 기준을 제시합니다. 결과는 문항별 오류 유형과 단원별 재학습 완료 여부로 확인합니다."
        )
    else:
        scope = f"{stage['student']} {subject['label']} 학습 운영"
        boundary = (
            f"{stage['student']}의 시간 배분·과제 수행·복습 습관이 중심입니다. "
            f"특정 문항 분석보다 {subject['label']} 학습을 주간 일정 안에서 지속하는 방법을 먼저 확인합니다."
        )
        intent_core = (
            "학년 운영형 안내이므로 주간 시간표, 과제 이행, 복습 지속성을 함께 살펴 "
            "실행 루틴과 다음 점검 시점을 제시합니다. 결과는 계획 대비 실행률과 과제 마감, 복습 간격 유지 여부로 확인합니다."
        )
    return {
        "stage": stage,
        "subject": subject,
        "scope": scope,
        "boundary": boundary,
        "intent_core": intent_core,
    }


def format_values(title: str, identity: dict, branch: dict) -> dict:
    role = taxonomy(identity)
    fact = verified_facts(branch, identity)
    stage = role["stage"]
    subject = role["subject"]
    situation = pick(subject["problems"], title, role_key(identity), "situation")
    values = {
        "title": title,
        "region": fact["region"],
        "center": fact["center"],
        "stage_label": stage["label"],
        "stage_student": stage["student"],
        "assessment": stage["assessment"],
        "schedule": stage["schedule"],
        "habit": stage["habit"],
        "subject_label": subject["label"],
        "focus": subject["focus"],
        "record": subject["record"],
        "measure": subject["measure"],
        "situation": situation,
        "scope": role["scope"],
        "boundary": role["boundary"],
        "intent_core": role["intent_core"],
        **fact,
    }
    for key in ("assessment", "record", "focus", "schedule", "habit", "measure"):
        values[f"{key}_obj"] = with_josa(values[key], "을", "를")
        values[f"{key}_and"] = with_josa(values[key], "과", "와")
        values[f"{key}_subject"] = with_josa(values[key], "이", "가")
    return values


def render_cards(values: dict, identity: dict) -> list[tuple[str, str]]:
    grade_text = (
        f"{values['center']} 자료에서 {values['scope']} 관련 학년은 {values['grades']} 범위로 확인됩니다. 실제 반 편성과 현재 모집 가능 여부는 상담 시점에 다시 확인합니다."
        if values["has_grades"]
        else f"{values['center']} 자료에 {values['scope']} 가능 범위가 명시되지 않아, 상담에서 수업 가능 여부를 먼저 확인해야 합니다."
    )
    school_text = (
        f"{values['center']} 자료의 참고 학교는 {values['schools']}입니다. 학교명은 생활권 참고 정보이며, 실제 재학 학교와 시험 범위는 상담에서 확인합니다."
        if values["has_schools"]
        else f"{values['center']} 자료에 참고 학교가 별도로 기재되지 않았습니다. 실제 재학 학교와 교재, 시험 범위는 상담에서 확인합니다."
    )
    location_text = (
        f"위치 안내 자료에는 다음 내용이 기재되어 있습니다: {values['location']}. 방문 전에는 상담을 통해 운영 여부와 시간을 확인하세요."
        if values["location"]
        else f"등록 주소는 {values['address']}입니다. 방문 전에는 상담을 통해 운영 여부와 시간을 확인하세요."
    )
    role_text = f"{with_josa(values['scope'], '을', '를')} 담당합니다. {values['boundary']}"
    return [
        ("이 페이지의 역할", role_text),
        ("확인된 수업 범위", grade_text),
        ("학교·평가 참고", school_text),
        ("센터 위치 확인", location_text),
    ]


def render_checks(values: dict, title: str) -> list[tuple[str, str, str]]:
    fields = [
        ("01", "학습 기록", "record"),
        ("02", "학교 일정", "schedule"),
        ("03", "학생 상황", "situation"),
        ("04", "다음 확인", "measure"),
    ]
    result = []
    for number, heading, field in fields:
        template = pick(CHECK_TEMPLATES[field], title, field, values["center"], values["schools"])
        body = template.format(**values)
        if field == "record":
            body = f"{values['center']} 상담 자료로 활용할 수 있도록, {body}"
        elif field == "schedule":
            if values["has_schools"]:
                body = f"참고 학교({values['schools']})와 실제 재학 학교의 일정을 구분한 뒤, {body}"
            else:
                body = f"센터 자료에 참고 학교가 없으므로 재학 학교 일정을 직접 확인한 뒤, {body}"
        elif field == "situation":
            if values["has_grades"]:
                body = f"관련 학년({values['grades']}) 안에서도 학생별 차이가 있으므로, {body}"
            else:
                body = f"수업 가능 학년은 상담 확인이 필요하므로 학생의 현재 과정부터 확인하고, {body}"
        else:
            body = f"{values['scope']} 상담의 다음 확인 항목으로, {body}"
        result.append((number, heading, body))
    return result


def render_section(title: str, identity: dict, branch: dict) -> str:
    values = format_values(title, identity, branch)
    summary = pick(SUMMARY_TEMPLATES, title, role_key(identity), "summary").format(**values)
    answer = pick(ANSWER_TEMPLATES, title, role_key(identity), "answer").format(**values)
    answer += (
        f" 이번 상담 기준은 {values['situation']}의 실제 기록을 "
        f"{values['center']}의 확인 자료와 연결해 판단하는 데 둡니다."
    )
    cards = render_cards(values, identity)
    checks = render_checks(values, title)
    counterpart_info = counterpart(identity)
    if counterpart_info:
        other_label, other_url = counterpart_info
        distinction = (
            '<div class="intent-counterpart"><strong>비슷한 이름의 페이지와 무엇이 다른가요?</strong>'
            f'<p>{html.escape(values["boundary"])} 다른 관점의 안내가 필요하면 '
            f'<a href="{html.escape(other_url)}">{html.escape(other_label)}</a>도 함께 확인하세요.</p></div>'
        )
    else:
        distinction = (
            '<div class="intent-counterpart"><strong>이 페이지의 안내 범위</strong>'
            f'<p>{html.escape(values["boundary"])}</p></div>'
        )
    card_html = "".join(
        f'<article class="geo-answer-card"><strong>{html.escape(heading)}</strong><p>{html.escape(body)}</p></article>'
        for heading, body in cards
    )
    check_html = "".join(
        f'<article class="geo-check-card"><b>{number}</b><strong>{html.escape(heading)}</strong><p>{html.escape(body)}</p></article>'
        for number, heading, body in checks
    )
    direct_answer = (
        f"{title} 상담에서는 {values['record_and']} {values['assessment_obj']} 먼저 확인한 뒤 "
        f"{values['focus']}의 우선순위를 정합니다."
    )
    return f'''<!-- seo-geo-enhancement:start -->
    <section class="section seo-geo-section intent-role-section" data-intent-role="{html.escape(role_key(identity))}" aria-label="{html.escape(title)} 학습 안내">
      <div class="wrap seo-geo-enhancement">
        <article id="geo-summary" class="geo-summary-panel">
          <p class="eyebrow">DIRECT STUDY ANSWER</p>
          <h2 id="intent-role-title">{html.escape(title)}에서 먼저 확인할 학습 기준</h2>
          <p>{html.escape(summary)} {html.escape(values['intent_core'])}</p>
          <div class="intent-role-badges" aria-label="페이지 핵심 역할">
            <span>{html.escape(values['scope'])}</span><span>{html.escape(values['subject_label'])}</span><span>{html.escape(values['stage_student'])}</span>
          </div>
          {distinction}
        </article>

        <article id="geo-answer" class="geo-answer-panel">
          <p class="eyebrow">VERIFIED CENTER CONTEXT</p>
          <h2>{html.escape(title)} 상담에서 확인하는 네 가지 근거</h2>
          <p>{html.escape(answer)}</p>
          <div class="geo-answer-grid">{card_html}</div>
          <div class="geo-mini-faq">
            <details open><summary>한 문장으로 정리하면 무엇을 먼저 확인하나요?</summary><p>{html.escape(direct_answer)}</p></details>
          </div>
        </article>

        <article id="geo-checklist" class="geo-checklist-panel">
          <p class="eyebrow">PERSONALIZED CHECKLIST</p>
          <h2>{html.escape(title)} 상담 전 준비 체크리스트</h2>
          <div class="geo-checklist-grid">{check_html}</div>
        </article>
      </div>
    </section>
    <!-- seo-geo-enhancement:end -->'''


def build_faqs(title: str, identity: dict, branch: dict) -> list[tuple[str, str]]:
    values = format_values(title, identity, branch)
    counterpart_info = counterpart(identity)
    grade_answer = (
        (
            f"{values['center']} 자료에서 {values['scope']} 관련 학년은 {values['grades']} 범위로 확인됩니다. "
            f"다만 실제 반 편성과 모집 가능 여부는 상담 시점에 다시 확인해야 합니다. "
            f"{title} 상담에서는 {values['situation']}인지도 함께 살펴봅니다."
        )
        if values["has_grades"]
        else (
            f"{values['center']} 자료에 {values['scope']}의 가능 범위가 명시되지 않았습니다. 따라서 상담에서 "
            f"{values['stage_student']}의 현재 과정과 {values['record_obj']} 기준으로 수업 가능 여부를 먼저 확인해야 합니다. "
            f"이때 {values['situation']}인지도 함께 살펴봅니다."
        )
    )
    school_answer = (
        f"참고 학교로 {with_josa(values['schools'], '이', '가')} 기재되어 있습니다. 이는 생활권 참고 정보이며, 실제 재학 학교의 교재·진도·시험 범위는 상담에서 다시 확인합니다."
        if values["has_schools"]
        else (
            f"{values['center']} 자료에는 참고 학교가 별도로 기재되지 않았습니다. {values['stage_student']}의 "
            f"{values['schedule_and']} {values['record_obj']} 함께 준비하면 {values['scope']} 상담 기준을 구체적으로 정할 수 있습니다."
        )
    )
    location_answer = (
        (
            f"센터 주소는 {values['address']}입니다. 위치 안내 자료에는 다음 내용이 기재되어 있습니다: "
            f"{values['location']}. 방문 전 운영 여부와 시간, {values['scope']} 상담 가능 여부를 함께 확인하는 것이 좋습니다."
        )
        if values["location"]
        else (
            f"센터 등록 주소는 {values['address']}입니다. 방문 전 운영 여부와 상담 가능 시간, "
            f"{values['scope']} 상담 가능 여부를 함께 확인하는 것이 좋습니다."
        )
    )
    if counterpart_info:
        other_label, _ = counterpart_info
        comparison_q = f"{title}과 {other_label} 안내는 어떻게 다른가요?"
        comparison_a = f"{title}은 {with_josa(values['scope'], '을', '를')} 중심으로 설명합니다. {values['boundary']} 두 페이지는 같은 학생을 다루더라도 상담에서 먼저 확인하는 기준이 다릅니다."
    else:
        comparison_q = f"{title} 페이지는 어떤 학생에게 도움이 되나요?"
        comparison_a = (
            f"{title} 안내는 {values['situation']}에게 확인할 기준을 제공합니다. "
            f"{values['center']} 상담에서는 {values['record_obj']} 보고 현재 상태와 우선순위를 다시 정합니다."
        )
    prepared = pick(
        [
            "최근 자료는 점수만 있는 성적표보다 학생의 풀이와 표시가 남은 자료가 좋습니다.",
            "최근 한 달의 자료를 날짜순으로 준비하면 반복되는 어려움을 찾는 데 도움이 됩니다.",
            "시험지와 교재 외에도 실제 공부 시간과 과제 완료 기록을 함께 알려주세요.",
            "학생이 어렵다고 느끼는 단원과 학부모님이 걱정하는 습관을 따로 정리하면 좋습니다.",
            "최근 평가 자료와 다음 시험 일정을 함께 준비하면 우선순위를 더 구체적으로 정할 수 있습니다.",
            "맞힌 문제 중 설명하기 어려운 문제와 반복해서 틀린 문제를 구분해 오면 좋습니다.",
            "현재 교재 진도와 학교 진도가 다르다면 두 범위를 모두 표시해 준비해 주세요.",
            "주간 플래너가 있다면 계획한 내용과 실제 완료한 내용을 함께 확인할 수 있게 준비해 주세요.",
        ],
        title,
        "faq-prepared",
    )
    return [
        (
            f"{title}에서는 무엇을 가장 먼저 확인하나요?",
            (
                f"{values['record_and']} {values['assessment_obj']} 먼저 확인합니다. 이후 {values['focus_obj']} 구분해 "
                f"학생이 지금 시작할 수 있는 순서와 분량을 정합니다. {values['center']} 상담에서는 특히 "
                f"{values['situation']}인지 실제 기록으로 확인합니다."
            ),
        ),
        (
            "상담 전에 어떤 자료를 준비하면 좋나요?",
            (
                f"{prepared} 이 페이지에서는 특히 {values['record_obj']} 확인 자료로 활용합니다. "
                f"{title} 범위에서는 {values['schedule_obj']} 함께 알려주면 우선순위를 더 구체적으로 정할 수 있습니다."
            ),
        ),
        (comparison_q, comparison_a),
        (
            f"{values['region']}에서 확인된 수업 가능 학년은 어떻게 되나요?",
            grade_answer,
        ),
        (
            "학교 시험 대비를 상담할 때 참고할 정보가 있나요?",
            school_answer,
        ),
        (
            f"{values['center']} 위치와 방문 전 확인사항은 무엇인가요?",
            location_answer,
        ),
    ]


def description_for(title: str, identity: dict) -> str:
    stage = STAGE[identity["stage"]]
    subject = SUBJECT[identity["subject"]]
    return (
        f"{title} 안내입니다. {with_josa(stage['assessment'], '과', '와')} {subject['label']} 학습 기록을 바탕으로 "
        f"{subject['focus']}의 상담 기준을 정리했습니다."
    )


def update_jsonld(source: str, title: str, description: str, identity: dict, branch: dict, faqs: list[tuple[str, str]]) -> str:
    match = re.search(r'<script type="application/ld\+json">(.*?)</script>', source, re.S)
    if not match:
        raise ValueError("JSON-LD not found")
    data = json.loads(match.group(1))
    graph = data.get("@graph", [])
    values = format_values(title, identity, branch)
    about = [
        {"@type": "Place", "name": values["region"]},
        {"@type": "Thing", "name": title},
        {"@type": "Thing", "name": values["scope"]},
        {"@type": "Organization", "name": values["center"]},
    ]
    mention_names = [
        values["focus"],
        values["record"],
        values["assessment"],
        values["schedule"],
        values["measure"],
    ]
    if values["has_grades"]:
        mention_names.append(f"관련 가능 학년 {values['grades']}")
    if values["has_schools"]:
        mention_names.append(f"참고 학교 {values['schools']}")
    mentions = [{"@type": "Thing", "name": item} for item in dict.fromkeys(mention_names)]
    keywords = ", ".join(
        [title, values["scope"], values["subject_label"], values["stage_student"], identity["dong"]]
    )

    org = find_node(graph, "EducationalOrganization")
    webpage = find_node(graph, "WebPage")
    service = find_node(graph, "Service")
    article = find_node(graph, "Article")
    faq = find_node(graph, "FAQPage")
    if not all((org, webpage, service, article, faq)):
        raise ValueError("required JSON-LD node missing")

    org["knowsAbout"] = list(dict.fromkeys([values["scope"], values["focus"], values["record"]]))
    webpage.update(
        {
            "description": description,
            "about": about,
            "mentions": mentions,
            "keywords": keywords,
            "dateModified": MODIFIED_DATE,
        }
    )
    service.update(
        {
            "description": description,
            "serviceType": values["scope"],
            "about": about,
            "mentions": mentions,
            "areaServed": {"@type": "Place", "name": values["region"]},
            "audience": {"@type": "EducationalAudience", "educationalRole": values["stage_student"]},
        }
    )
    article.update(
        {
            "description": description,
            "dateModified": MODIFIED_DATE,
            "articleSection": [
                values["scope"],
                "핵심 답변",
                "검증된 센터 정보",
                "학생 상황",
                "상담 전 체크리스트",
                "FAQ",
                "학부모 후기",
                "내부링크",
            ],
            "about": about,
            "mentions": mentions,
            "keywords": keywords,
        }
    )
    faq.update(
        {
            "mainEntity": [
                {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}}
                for q, a in faqs
            ],
            "about": about,
            "mentions": mentions,
        }
    )
    rendered = '<script type="application/ld+json">' + json.dumps(
        data, ensure_ascii=False, separators=(",", ":")
    ) + "</script>"
    return source[: match.start()] + rendered + source[match.end() :]


GRAMMAR_FIXES = {
    "오답 재풀이을": "오답 재풀이를",
    "풀이을": "풀이를",
    "실제 기록으로 이어지는지 기록으로 확인합니다": "실제 기록으로 이어지는지 확인합니다",
    "수학 교과 성취을": "수학 교과 성취를",
    "영어 교과 성취을": "영어 교과 성취를",
    "영어·수학 교과 성취을": "영어·수학 교과 성취를",
    "센터정보": "센터 정보",
}


def process_page(path: Path, centers: dict[str, dict]) -> tuple[bool, str]:
    source = path.read_text(encoding="utf-8", errors="strict")
    before_canonical = canonical(source)
    before_hrefs = href_counter(source)
    category = path.parent.parent.name
    identity = classify(category, path.parent.name)
    branch = centers[identity["dong"].replace(" ", "")]
    title = page_title(source)
    description = description_for(title, identity)
    existing_faqs = extract_faqs(source)
    if len(existing_faqs) != 6:
        raise ValueError(f"expected 6 FAQs, found {len(existing_faqs)}")
    faqs = build_faqs(title, identity, branch)

    updated = replace_meta(source, description)
    updated, count = re.subn(
        r"<!-- seo-geo-enhancement:start -->.*?<!-- seo-geo-enhancement:end -->",
        render_section(title, identity, branch),
        updated,
        count=1,
        flags=re.S,
    )
    if count != 1:
        raise ValueError("SEO/GEO section marker missing or duplicated")
    updated, count = re.subn(
        r'(<div class="faq-list">\n)(.*?)(\n\s*</div>\s*\n\s*</div>\s*\n\s*</section>)',
        lambda match: match.group(1) + render_faqs(faqs) + match.group(3),
        updated,
        count=1,
        flags=re.S,
    )
    if count != 1:
        raise ValueError("FAQ HTML replacement failed")
    updated = update_jsonld(updated, title, description, identity, branch, faqs)
    for before, after in GRAMMAR_FIXES.items():
        updated = updated.replace(before, after)

    if canonical(updated) != before_canonical:
        raise ValueError("canonical changed")
    lost = before_hrefs - href_counter(updated)
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
    print(
        json.dumps(
            {"targets": len(targets), "changed": changed, "roles": dict(sorted(counts.items())), "errors": len(errors)},
            ensure_ascii=False,
        )
    )
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
