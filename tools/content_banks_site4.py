"""AEO/GEO content banks for 와와학원.com (새 홈페이지4) 전국센터 detail pages.

Reviews adapted from 참고자료/공통자료/학부모 후기.txt (subject-agnostic, so the
existing per-page dong+subject opener sentence stays untouched and only the
remaining slots draw from this bank). FAQ slot banks cover the two filler
questions that were previously identical across an entire subject-family or
sitewide.
"""
from __future__ import annotations

import random
import zlib


def seed_for(*parts: str) -> int:
    return zlib.crc32("|".join(parts).encode("utf-8"))


def pick(bank: list, k: int, *seed_parts: str) -> list:
    rng = random.Random(seed_for(*seed_parts))
    return rng.sample(bank, k) if len(bank) > k else list(bank)


def pick_unique(bank: list, k: int, seen: set, *seed_parts: str) -> list:
    candidate = pick(bank, k, *seed_parts)
    if len(bank) <= k:
        return candidate
    attempt = 1
    while frozenset(candidate) in seen:
        candidate = pick(bank, k, *seed_parts, f"retry{attempt}")
        attempt += 1
    seen.add(frozenset(candidate))
    return candidate


REVIEW_BANK_5 = [
    "아이가 다닌 뒤 성적이 눈에 띄게 향상되었습니다.",
    "부족했던 부분의 기초가 차근차근 잡히고 있습니다.",
    "아이가 어려워하던 단원을 이제는 자신 있게 풀고 있습니다.",
    "시험 점수가 이전보다 안정적으로 나오기 시작했습니다.",
    "학습 습관이 잡히면서 공부하는 시간이 자연스럽게 늘었습니다.",
    "개념을 정확히 이해하게 되어 문제 해결력이 좋아졌습니다.",
    "오답을 꼼꼼하게 관리해 주셔서 같은 실수를 줄일 수 있었습니다.",
    "아이의 취약한 부분을 정확히 찾아 보완해 주셨습니다.",
    "단순히 암기하는 방식이 아니라 원리를 이해하도록 지도해 주십니다.",
    "다니기 전보다 문제를 푸는 속도가 빨라졌습니다.",
    "어려운 문제도 포기하지 않고 끝까지 풀어보는 힘이 생겼습니다.",
    "서술형 문제에 대한 자신감이 많이 생겼습니다.",
    "성적뿐만 아니라 공부에 대한 태도도 긍정적으로 바뀌었습니다.",
    "아이가 스스로 부족한 부분을 찾아 공부하기 시작했습니다.",
    "이전에는 자주 틀리던 유형의 문제를 정확하게 풀게 되었습니다.",
    "시험 직전 핵심 내용을 정리해 주셔서 큰 도움이 되었습니다.",
    "문제 풀이 과정까지 꼼꼼하게 지도해 주셔서 실수가 줄었습니다.",
    "선생님께서 아이의 눈높이에 맞춰 친절하게 설명해 주십니다.",
    "이해하지 못한 부분을 여러 번 질문해도 자세히 알려주십니다.",
    "학생 한 명 한 명을 세심하게 살펴주시는 점이 좋았습니다.",
    "학습 계획을 구체적으로 세워주셔서 집에서도 공부하기 편해졌습니다.",
    "학습량과 휴식의 균형을 고려해 주시는 점이 좋았습니다.",
    "정기적으로 학습 상황을 공유해 주셔서 안심하고 맡길 수 있습니다.",
    "상담할 때 아이의 현재 수준을 구체적으로 설명해 주셨습니다.",
    "무리한 선행보다 아이에게 필요한 학습을 추천해 주셨습니다.",
    "학부모와 선생님이 함께 아이를 지도한다는 느낌을 받았습니다.",
    "출결 상황을 꼼꼼하게 확인해 주셔서 믿음이 갑니다.",
    "오답 노트를 활용해 취약한 부분을 반복해서 공부하게 해주십니다.",
]

REVIEW_BANK_4 = [
    "처음 상담 때부터 아이의 공부 습관을 먼저 살펴보고 필요한 부분을 차근차근 잡아줘서 도움이 됐습니다.",
    "숙제 여부를 철저히 관리해 주셔서 학습 습관을 잡는 데 도움이 되었습니다.",
    "정기적인 테스트를 통해 아이의 실력을 객관적으로 확인할 수 있습니다.",
    "학습 결과가 좋지 않을 때 원인을 함께 찾아주셔서 도움이 되었습니다.",
    "다니는 것에 잘 적응하고 있어 재등록할 예정입니다.",
    "궁금한 점을 문의하면 빠르고 친절하게 답변해 주십니다.",
]

# Each FAQ entry is stored as a question/answer pair.  Keeping the pair together
# prevents a randomly selected question from inheriting an unrelated answer.
# {subject} substitution: 수학 / 영어 / 영어·수학 / 주요 과목
FAQ_SLOT4_BANK = [
    (
        "{subject} 수업은 학교 진도와 오답 관리를 함께 보나요?",
        "네. {subject} 수업은 학교 진도와 시험 범위를 확인한 뒤, 틀린 문제를 개념 부족·풀이 과정·실수 유형으로 나누어 다음 복습 계획에 반영합니다.",
    ),
    (
        "{subject} 학습에서 개념 이해와 문제 풀이를 함께 연결해 주나요?",
        "네. {subject} 개념을 이해했는지 먼저 확인하고 기본 문제부터 응용 문제까지 적용해 본 뒤, 막힌 과정은 다시 설명하고 풀어보도록 관리합니다.",
    ),
    (
        "{subject} 진도가 늦은 학생도 상담이 가능한가요?",
        "가능합니다. 현재 {subject} 진도와 기초 이해도를 먼저 확인하고, 바로 따라가기 어려운 부분은 우선순위를 정해 복습한 뒤 학교 진도와 연결합니다.",
    ),
    (
        "{subject} 오답은 원인별로 구분해서 다시 학습시켜 주나요?",
        "네. {subject} 오답을 개념 부족, 문제 해석, 풀이 과정, 단순 실수로 구분하고 원인에 맞는 문제를 다시 풀어 확인합니다.",
    ),
    (
        "{subject} 실력이 학년 평균보다 낮아도 상담할 수 있나요?",
        "가능합니다. 학년 평균만으로 판단하기보다 현재 {subject}에서 이해한 부분과 막힌 부분을 확인하고, 학생이 시작할 수 있는 단계와 학습량부터 정합니다.",
    ),
]

FAQ_SLOT6_BANK = [
    (
        "플래너 관리와 학습 습관 코칭도 함께 진행하나요?",
        "네. 학생이 실제로 지킬 수 있는 주간 분량을 플래너에 정리하고, 완료 여부와 막힌 지점을 확인해 다음 계획을 조정합니다.",
    ),
    (
        "숙제 관리와 오답 확인도 정기적으로 해주나요?",
        "네. 숙제 완료 여부만 확인하는 데서 끝내지 않고, 틀린 이유와 다시 풀었을 때 해결되는지를 살펴 다음 수업과 복습에 반영합니다.",
    ),
    (
        "학부모님께 학습 상황을 정기적으로 공유해 주나요?",
        "학습 진도와 과제 수행, 반복되는 어려움을 학부모님과 공유할 수 있습니다. 구체적인 피드백 주기와 방법은 센터별 운영 방식이 다를 수 있어 상담 시 확인하는 것이 좋습니다.",
    ),
    (
        "형제자매가 함께 상담받을 수 있나요?",
        "형제자매 상담 가능 여부와 시간은 센터 일정에 따라 달라질 수 있습니다. 함께 상담하더라도 학년과 과목, 현재 수준은 학생별로 나누어 확인합니다.",
    ),
    (
        "시험 기간에는 평소보다 관리가 더 촘촘해지나요?",
        "시험 범위와 일정이 확인되면 과목별 우선순위, 복습 횟수, 오답 점검 계획을 평소보다 구체적으로 세웁니다. 세부 운영 방식은 센터 상담에서 확인할 수 있습니다.",
    ),
]
