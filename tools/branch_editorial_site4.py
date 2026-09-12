"""Branch-specific decisions from reviewed facts, not random copy variations.

The snapshot stays immutable. Suggestions are explicitly preparation advice;
unrecorded grades never become offered courses. Shared instructional explanations
belong on the existing learning guides instead of being copied to every branch.
"""
from collections import defaultdict
import re

ORDER = ('영어', '수학', '국어', '과학', '사회')
STAGES = (('초', '초등학생', 'elementary'), ('중', '중학생', 'middle'), ('고', '고등학생', 'high'))


def clean(value):
    return re.sub(r'\s+', ' ', value or '').strip()


def name(c):
    return c['sourceCenterName'].replace('(모두)', '').strip()


def ranges(grades):
    result = []
    for prefix in ('초', '중', '고'):
        numbers = sorted({int(g[1:]) for g in grades if re.fullmatch(prefix + r'\d', g)})
        runs = []
        for number in numbers:
            if runs and number == runs[-1][-1] + 1:
                runs[-1].append(number)
            else:
                runs.append([number])
        result.extend(prefix + str(run[0]) + ('~' + prefix + str(run[-1]) if len(run) > 1 else '') for run in runs)
    return ' · '.join(result)


def confirmed(c, ref):
    operations = ref.get('operations', {}).get('subjectDisplay', {})
    return {subject: c['subjects'][subject]['grades'] for subject in ORDER
            if c['subjects'][subject]['grades'] and
            (not operations or operations.get(subject, {}).get('includeInUnqualifiedAvailableSubjects'))}


def scope_groups(c, ref, prefix=None):
    groups = defaultdict(list)
    for subject, all_grades in confirmed(c, ref).items():
        grades = [g for g in all_grades if prefix is None or g.startswith(prefix)]
        if grades:
            groups[tuple(grades)].append(subject)
    return [('·'.join(subjects), ranges(grades)) for grades, subjects in groups.items()]


def scope_sentence(c, ref, prefix=None):
    groups = scope_groups(c, ref, prefix)
    return '; '.join(subject + ' ' + grades for subject, grades in groups)


def grade_comparison(c, ref):
    courses = confirmed(c, ref)
    if not all(subject in courses for subject in ('영어', '수학')):
        return None
    english, math = set(courses['영어']), set(courses['수학'])
    if english == math:
        return None
    differences = []
    if english - math:
        differences.append(ranges(english - math) + '의 경우 영어 안내에 포함되지만 수학 안내에는 포함되어 있지 않습니다.')
    if math - english:
        differences.append(ranges(math - english) + '의 경우 수학 안내에 포함되지만 영어 안내에는 포함되어 있지 않습니다.')
    return {'title': '영어·수학의 학년 차이', 'text': ' '.join(differences),
            'note': '이는 안내된 학년 범위의 비교이며, 범위 밖 수업의 개설 여부는 따로 확인해야 합니다.',
            'source': ['subjects.영어.grades', 'subjects.수학.grades']}


def specific_question(ref):
    editorial = ref.get('editorial', {})
    mode = editorial.get('copyProvenance', {}).get('consultationAnswer', {}).get('mode', '')
    # A repeated grade-range question is replaced by the actual set comparison.
    if mode != 'grade-range-and-study-preparation' and editorial.get('consultationQuestion') and editorial.get('consultationAnswer'):
        answer = clean(editorial['consultationAnswer'])
        answer = re.sub(r'\b(수학|과학)를\b', r'\1을', answer)
        return (clean(editorial['consultationQuestion']), answer)
    return None


def strength_sentences(ref):
    editorial = ref.get('editorial', {})
    evidence = editorial.get('copyProvenance', {}).get('focusText', {})
    if evidence.get('mode') != 'source-strength-led':
        return []
    return [s for s in re.split(r'(?<=\.)\s+', clean(editorial.get('focusText')))
            if s and '학년 범위' not in s]


def preparation_advice(ref):
    text = ' '.join(strength_sentences(ref))
    if '플래너' in text or '계획' in text:
        return '계획표가 있다면 실제로 끝낸 항목과 미룬 항목을 구분해 가져가 보세요. 실행하기 어려웠던 시간대를 설명하는 데 도움이 됩니다.'
    if '수행평가' in text:
        return '수행평가는 과제 안내문, 제출일, 평가 항목을 함께 준비하세요. 교과 진도와 과제 준비가 겹치는 시기를 먼저 살펴볼 수 있습니다.'
    if '평가' in text:
        return '최근 평가에서 맞힌 문제도 풀이 근거를 설명할 수 있었는지 표시해 보세요. 점수만으로 드러나지 않는 학습 상태를 상담할 수 있습니다.'
    if '독서' in text or '읽기' in text:
        return '최근 읽은 글에서 이해하기 어려웠던 문단을 골라 보세요. 읽는 속도, 어휘 이해, 내용 요약 중 어느 부분이 어려웠는지 구분해 전달할 수 있습니다.'
    if 'AI' in text:
        return '현재 교재와 혼자 풀다 멈춘 문제를 준비하세요. 학습 도구의 기능뿐 아니라 진도·학습량을 어떻게 조정하는지 물어보면 좋습니다.'
    if '피드백' in text or '소통' in text or '공유' in text:
        return '숙제에서 자주 막히는 부분과 가정에서 확인하고 싶은 내용을 적어 보세요. 결과 점수 외에 어떤 학습 기록을 공유받을지 질문할 수 있습니다.'
    if '입시' in text or '진학' in text:
        return '희망 진학 방향과 현재 과목별 학습 상황을 함께 정리하세요. 장기 목표와 당장 준비할 학교 평가를 구분해 상담하기 좋습니다.'
    return '설명을 들으면 이해되지만 혼자 풀기 어려운 문제를 골라 보세요. 개념을 몰랐는지, 풀이를 시작하지 못했는지 나누어 질문할 수 있습니다.'


def intro(c, ref):
    n = name(c)
    courses = confirmed(c, ref)
    if c.get('addressPrecision') == 'neighborhood':
        return f'{n}은 동네 단위 위치로 안내되어 있어 방문할 건물·층수 확인이 먼저 필요합니다. 희망 과목의 학년 범위와 실제 방문 장소를 함께 상담해 주세요.'
    if grade_comparison(c, ref):
        return f'{n}은 영어와 수학의 안내 학년이 다릅니다. 두 과목을 함께 알아보는 학생은 아래 학년별 차이를 먼저 확인하고 시간표를 상담해 보세요.'
    condition = ref.get('editorial', {}).get('copyProvenance', {}).get('consultationAnswer', {})
    if specific_question(ref) and condition.get('subject'):
        return f'{n}의 {condition["subject"]} 수업은 학년뿐 아니라 세부 과정의 조건도 살펴봐야 합니다. 희망 단원과 학교에서 배우는 과목을 구분해 상담을 준비하세요.'
    if courses:
        return f'{n}에서는 {"·".join(courses)} 수업의 학년 범위를 안내합니다. 과목을 고른 뒤 재학 학교의 진도, 가능한 요일, {c["region"]["province"]} 지역 교육비 기준을 차례로 확인해 보세요.'
    return f'{n}은 희망 과목의 개설 학년을 먼저 확인해야 합니다. 재학 학교·학년과 배우려는 내용을 알려주시면 상담할 과정을 구체적으로 정리할 수 있습니다.'


def description(c, ref):
    n = c['displayName']
    groups = scope_groups(c, ref)
    primary = '; '.join(subject + ' ' + grades for subject, grades in groups[:2])
    if not primary:
        primary = '과목별 개설 학년 상담'
    return f'{n}, {clean(c["address"])}. {primary}. 수업 조건과 월 교육비, 재학 학교별 준비사항을 확인하세요.'


def focus_cards(c, ref):
    cards = []
    comparison = grade_comparison(c, ref)
    if comparison:
        cards.append(comparison)
    else:
        scope = scope_sentence(c, ref)
        cards.append({'title': '먼저 고를 과목과 학년',
                      'text': (scope + ' 범위로 안내합니다.' if scope else '확정된 학년 범위가 없는 과목은 현재 학년과 필요한 과정을 함께 문의해야 합니다.'),
                      'note': '같은 학년이어도 선택 과정에 별도 조건이 있을 수 있습니다.', 'source': ['subjects', 'operations.subjectDisplay']})
    special = specific_question(ref)
    if special:
        cards.append({'title': special[0], 'text': special[1], 'source': ['editorial.consultationAnswer']})
    strengths = strength_sentences(ref)
    if strengths:
        cards.append({'title': name(c) + '의 학습관리 안내', 'text': ' '.join(strengths),
                      'note': preparation_advice(ref), 'source': ['editorial.focusText', 'editorial.sourceFields']})
    if len(cards) == 1:
        missing = [subject for subject, value in c['subjects'].items()
                   if not value['grades'] and ref.get('operations', {}).get('subjectDisplay', {}).get(subject, {}).get('status') == 'unrecorded']
        if missing:
            cards.append({'title': '추가 과목을 함께 찾는다면',
                          'text': '·'.join(missing) + ' 수업은 개설 학년이 별도로 확인되지 않았습니다. 주된 수업과 함께 신청할 수 있는지, 원하는 학년의 수업이 있는지 나누어 문의하세요.',
                          'source': ['operations.subjectDisplay']})
    return cards


def school_names(match, key, limit=2):
    return sorted({s for s in (match or {}).get('targetSchools', {}).get(key, []) if '[' not in s and '모든' not in s})[:limit]


def stage_cards(c, ref, match):
    cards = []
    for prefix, label, school_key in STAGES:
        groups = scope_groups(c, ref, prefix)
        if not groups:
            continue
        courses = [subject for subject, grades in confirmed(c, ref).items() if any(g.startswith(prefix) for g in grades)]
        schools = school_names(match, school_key)
        school_line = ('·'.join(schools) + ' 등 아래 학교 목록을 참고하되, 재학 학교의 진도와 교재는 학생별로 준비하세요.') if schools else '재학 학교와 현재 배우는 단원명을 알려주세요. 학교가 목록에 없는 경우에도 희망 과목·학년부터 문의할 수 있습니다.'
        if prefix == '초':
            if any(g.startswith('초1') or g.startswith('초2') for g in confirmed(c, ref).get('수학', [])):
                advice = '문제를 읽어 줄 때와 혼자 읽을 때 풀이가 달라지는지 살펴보세요. 계산 연습이 필요한지, 문제의 뜻을 이해하는 연습이 필요한지 구분해 질문할 수 있습니다.'
            elif '영어' in courses and '수학' in courses:
                advice = '영어는 읽기와 단어 뜻 설명, 수학은 계산과 문장제 풀이를 나누어 메모하세요. 두 과목의 진도를 같은 기준으로 판단하지 않는 것이 좋습니다.'
            elif '영어' in courses:
                advice = '소리 내어 읽을 수 있는 단어와 뜻을 설명할 수 있는 단어를 구분해 보세요. 읽기 경험과 현재 교재 수준을 함께 전달할 수 있습니다.'
            else:
                advice = '교과서에서 혼자 설명하기 어려웠던 내용을 한두 가지 골라 보세요. 숙제 분량보다 어디에서 시간이 오래 걸렸는지 설명하면 도움이 됩니다.'
        elif prefix == '중':
            if '국어' in courses and '영어' in courses and '수학' in courses:
                advice = '여러 과목을 함께 준비한다면 시험일과 과제 제출일을 한 장에 적어 보세요. 먼저 보완할 과목과 매일 이어갈 복습을 나누어 상담하기 좋습니다.'
            elif '수학' in courses:
                advice = '틀린 문제에 계산 실수, 개념 혼동, 조건 해석 중 어디에서 막혔는지 표시해 보세요. 시험 점수와 함께 풀이 과정을 보여 주면 보완할 단원을 설명하기 쉽습니다.'
            else:
                advice = '교과서 진도와 학교에서 받은 유인물을 함께 챙기세요. 외웠지만 설명하지 못한 내용과 처음 보는 문제에서 막힌 부분을 구분해 질문할 수 있습니다.'
        else:
            high_math = {g for g in confirmed(c, ref).get('수학', []) if g.startswith('고')}
            if high_math and '고3' not in high_math:
                advice = '수학은 고3이 안내 범위에 포함되어 있지 않습니다. 지금 필요한 학년의 과정과 다음 학년의 상담 가능 여부를 구분하고, 학교 선택 과목명을 함께 전달하세요.'
            elif '수학' in courses:
                advice = '학교에서 선택한 수학 과목명과 시험 범위를 먼저 적어 보세요. 선택 과목의 개설 조건을 확인한 뒤, 개념 보완과 시간 안에 푸는 연습 중 필요한 쪽을 상담할 수 있습니다.'
            else:
                advice = '내신과 모의고사에서 어려운 부분을 따로 정리하세요. 학교 시험 범위, 과제 일정, 현재 교재를 함께 보여 주면 우선할 학습을 구체적으로 질문할 수 있습니다.'
        cards.append({'title': label + ' 상담 메모', 'scope': ' / '.join(subject + ' ' + grades for subject, grades in groups),
                      'school': school_line, 'advice': advice, 'subjects': courses,
                      'source': ['subjects', 'operations.subjectDisplay', 'schoolMatches.targetSchools.' + school_key]})
    return cards


def consultation_steps(c, ref, match):
    n = name(c)
    neighborhoods = (match or {}).get('neighborhoods', [])
    locality = '·'.join(neighborhoods[:3])
    first = f'{n}을 선택한 뒤 현재 학년과 희망 과목을 알려주세요.'
    if locality:
        first += f' {locality}에서 출발한다면 하교 후 이동 시간과 가능한 요일도 함께 적어 주세요.'
    else:
        first += ' 재학 학교와 하교 후 가능한 요일을 함께 적어 주세요.'
    special = specific_question(ref)
    if special and ref.get('editorial', {}).get('copyProvenance', {}).get('consultationAnswer', {}).get('subject'):
        lesson = special[1]
    else:
        lesson = preparation_advice(ref)
    weekend = ref.get('operations', {}).get('weekend', {})
    summary = clean(weekend.get('summary', '')).replace('자료상 ', '')
    opening = ' / '.join(c['publicOperations']['averageWeekdayOpening']['values'])
    opening = re.sub(r'^평일\s*', '', opening)
    timetable = (f'평일 시작 안내는 {opening}입니다. ' if opening else '')
    if summary:
        summary = summary.replace('토요일가능', '토요일 가능').replace('일요일가능', '일요일 가능').replace('주말가능', '주말 가능').replace('주말불가', '주말 불가')
        timetable += '주말 안내는 ‘' + summary + '’입니다. 희망 과목의 실제 시작·종료 시간은 별도로 확인하세요.'
    else:
        timetable += '평일·주말 중 가능한 요일과 과목별 실제 시작·종료 시간을 확인하세요.'
    policy = '서울' if c['region']['province'] == '서울' else '서울 외'
    return [('지점과 가능한 시간 전달', first), ('학습 상담에 가져갈 자료', lesson),
            ('실제 등원 일정 확인', timetable),
            ('횟수와 비용 비교', f'{n}에는 {policy} 교육비 기준이 적용됩니다. 교육비표를 비교할 때는 주당 횟수, 교재 등 별도 비용, 첫 수업일을 함께 확인하세요.')]


def profile(c, ref, match):
    return {'centerId': c['id'], 'intro': intro(c, ref), 'description': description(c, ref),
            'focusCards': focus_cards(c, ref), 'stageCards': stage_cards(c, ref, match),
            'consultationSteps': consultation_steps(c, ref, match),
            'generationPolicy': 'source-conditioned; no random variants, invented local outcomes or inferred missing grades'}
