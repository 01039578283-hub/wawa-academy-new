"""Reviewed, source-bounded overlays. Never edit the imported branch snapshot.

Recorded grades alone are not a claim of current vacancy or owner confirmation.
The separate owner overlay records the explicit, narrowly scoped user update.
An additional grade mentioned in a note does not erase the table's baseline.
"""
from copy import deepcopy
from functools import lru_cache
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_SHA = 'b7937da1a70314f3095739d3cca9bc202e8c48997ea3af7774b11d05fee6240a'
WORKBOOK_SHA = '59d1c33e633ef98537f43bc5f09339508cba38b03be2ab7a3c0a4a9f99f98b29'
SCOPE_REVIEWS = {
    'center-row-021': {
        '영어': ('Q21', 'U21', ['초3','초4','초5','초6','중1','중2','중3','고1','고2'],
               '초3~초6 · 중1~중3 · 고1~고2',
               '기재된 기본 학년 범위입니다. 고3은 별도 가능 안내가 있어 현재 개설 여부를 확인해야 합니다. 덕원여고 영어 내신은 진행하지 않는다는 조건이 있으므로 재학 학교와 희망 과정을 함께 확인해 주세요.')},
    'center-row-040': {
        '영어': ('Q40', 'U40', ['초4','초5','초6','중1','중2','중3','고1'],
               '초4~초6 · 중1~중3 · 고1',
               '기재된 기본 학년 범위입니다. 파닉스 가능 안내가 있으며, 고2는 성적 수준에 따른 별도 조건이 있어 적용 기준과 개설 여부를 확인해야 합니다. 초3도 별도 상담이 필요합니다.'),
        '수학': ('R40', 'U40', ['초4','초5','초6','중1','중2','중3','고1'],
               '초4~초6 · 중1~중3 · 고1',
               '기재된 기본 학년 범위입니다. 고2는 성적 수준에 따른 별도 조건이 있어 적용 기준과 개설 여부를 확인해야 합니다. 초3도 별도 상담이 필요합니다.')},
    'center-row-046': {
        '영어': ('Q46', 'U46', ['초5','초6','중1','중2','중3','고1','고2','고3'],
               '초5~초6 · 중1~중3 · 고1~고3',
               '기재된 기본 학년 범위입니다. 초4는 파닉스 기초를 갖춘 경우의 별도 가능 안내가 있어 학습 상태와 개설 여부를 확인해야 합니다.')},
}
PENDING_NOTES = {
    ('center-row-151','수학'): '영어 전문관 운영 안내가 있어 수학 수업의 개설 여부와 담당 지점을 먼저 확인해야 합니다. 영어·과학·사회의 학년 안내를 수학에 적용하지 않습니다.',
    ('center-row-025','수학'): '수학의 세부 학년이 기재되어 있지 않습니다. 공식 센터 소개의 포괄적인 학년 안내만으로 수학 전 학년 수업을 확정하지 않습니다.',
    ('center-row-168','수학'): '수학의 세부 학년이 기재되어 있지 않습니다. 학생의 현재 학년과 진도를 알려주고 개설 범위를 먼저 확인해 주세요.',
    ('center-row-014','영어'): '영어는 기초 보완이 필요한 학생의 수업 가능 메모가 있지만 세부 학년은 기재되어 있지 않습니다. 현재 학년과 읽기·어휘 수준을 알려주고 개설 여부를 확인해 주세요.',
    ('center-row-047','수학'): '수학 표에 안내된 범위는 초1~중3입니다. 다른 공개 소개와 범위가 달라 고등 수학은 현재 개설 여부를 별도로 확인해야 합니다.',
    ('center-row-082','수학'): '수학 표에 안내된 범위는 초1~중3입니다. 공개 소개의 고등 과정 범위도 서로 달라 현재 개설 학년과 과정을 별도로 확인해야 합니다.',
    ('reference-경기-화성태안점','수학'): '수학 안내에는 초1~중3만 기재되어 있습니다. 고등 수학의 개설 여부와 방문할 상세 주소를 함께 확인해 주세요.',
}
PLACEMENT_NOTE = '수업 배치가 어렵다는 운영 메모가 있어 현재 수강 가능 여부를 먼저 확인해야 합니다. 공개 소개에 적힌 학년과 실제 배치 가능 여부는 다를 수 있습니다.'
LOCATION_REPAIRS = {
    'center-row-151': ['은평점은 서울 은평구 진관2로 29-21 드림스퀘어 8층 804·805호에 있습니다.', '구파발역 2번 출구 쪽, 구파발성당 맞은편 건물로 안내되어 있습니다.'],
    'center-row-025': ['다산점은 경기 남양주시 다산중앙로146번길 12-14 다산메트로타워 604호에 있습니다.', '방문 전 주소와 지도 이미지의 건물명·호수를 함께 확인해 주세요.'],
    'center-row-047': ['둔산점은 대전 서구 둔산로 142 신화빌딩 401호에 있습니다.', '시청역 7번 출구 쪽 건물 4층으로 안내되어 있습니다.'],
}


@lru_cache(maxsize=1)
def owner_confirmation():
    return json.loads((ROOT / 'tools/data/branch-verification/owner-course-confirmation.json').read_text(encoding='utf-8'))


OWNER_SCOPE_CENTERS = {r['centerId'] for r in owner_confirmation()['confirmations']}
REVIEWED_SCOPE_CENTERS = set(SCOPE_REVIEWS) | OWNER_SCOPE_CENTERS


def owner_confirmed(center_id, subject=None, stage=None):
    return any(r['centerId'] == center_id and (not subject or r['subject'] == subject)
               and (not stage or stage in r['stages']) for r in owner_confirmation()['confirmations'])


def placement_note(center_id):
    return PLACEMENT_NOTE if center_id == 'center-row-098' and not owner_confirmed(center_id) else ''


@lru_cache(maxsize=1)
def reviewed_snapshot():
    from branch_editorial_site4 import ranges
    path = ROOT / 'tools/data/branches/snapshot.json'
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == SNAPSHOT_SHA, 'Branch source changed: review overlays before generation'
    data = json.loads(raw)
    for c in data['centers']:
        reviews = SCOPE_REVIEWS.get(c['id'], {})
        ref = data['reference'][c['id']]
        if c['id'] in LOCATION_REPAIRS:
            ref['locationParagraphs'] = LOCATION_REPAIRS[c['id']]
        for subject, (cell, note_cell, grades, summary, detail) in reviews.items():
            old = ref['operations']['subjectDisplay'][subject]
            assert c['subjects'][subject]['sourceCell'] == cell
            assert c['subjects'][subject]['grades'] == grades == old['sourceGrades']
            assert old['status'] == 'scope_confirmation_needed' and note_cell in old['sourceCells']
            old.update(summary=summary, detail=detail, status='recorded_baseline_extension_pending',
                       includeInUnqualifiedAvailableSubjects=True)
        if reviews:
            # Keep previously qualified note-only subjects and their card order.
            # This review only restores the four specified subject ranges.
            c['_displaySubjects'] = list(dict.fromkeys(c.get('_displaySubjects',c['availableSubjects'])+list(reviews)))
        confirmations = [r for r in owner_confirmation()['confirmations'] if r['centerId'] == c['id']]
        if confirmations:
            operations = ref.setdefault('operations', {})
            if not operations.get('subjectDisplay'):
                # Legacy references with no per-subject display must retain all
                # their other existing subject ranges when adding this overlay.
                operations['subjectDisplay'] = {s: {
                    'summary': ranges(v['grades']) or '개설·학년 상담 확인', 'detail': '',
                    'status': 'recorded' if v['grades'] else 'unrecorded',
                    'sourceGrades': list(v['grades']), 'sourceConditions': [],
                    'sourceCells': [v.get('sourceCell', '')],
                    'includeInUnqualifiedAvailableSubjects': bool(v['grades'])
                } for s, v in c['subjects'].items()}
            for row in confirmations:
                subject = row['subject']
                added = [prefix + str(i) for stage, prefix, count in
                         [('초등학생', '초', 6), ('중학생', '중', 3), ('고등학생', '고', 3)]
                         if stage in row['stages'] for i in range(1, count + 1)]
                record = c['subjects'][subject]
                record['grades'] = list(dict.fromkeys(record['grades'] + added))
                record['schoolLevels'] = [level for prefix, level in [('초','초등'),('중','중등'),('고','고등')]
                                         if any(g.startswith(prefix) for g in record['grades'])]
                record['ownerConfirmation'] = {'confirmedAt': owner_confirmation()['confirmedAt'], 'stages': row['stages']}
                # Source cells and original sourceGrades remain as provenance;
                # the display and effective grades use the explicit newer update.
                operations['subjectDisplay'][subject].update(
                    summary=ranges(record['grades']),
                    detail='운영자 확인 기준으로 수업 가능한 학년입니다. 세부 진도와 수업 시간은 상담에서 조율해 주세요.',
                    status='owner_confirmed', includeInUnqualifiedAvailableSubjects=True,
                    ownerConfirmedAt=owner_confirmation()['confirmedAt'])
                c['availableSubjects'] = list(dict.fromkeys(c['availableSubjects'] + [subject]))
                labels = c.get('_displaySubjects', c['availableSubjects'])
                c['_displaySubjects'] = list(dict.fromkeys([subject if x.startswith(subject+'(') else x for x in labels] + [subject]))
    return data


def load_reviewed_snapshot():
    return deepcopy(reviewed_snapshot())


def recorded_grades(m):
    from branch_editorial_site4 import confirmed
    data = reviewed_snapshot()
    c = next(c for c in data['centers'] if c['id'] == m['centerId'])
    prefix = {'초등학생':'초','중학생':'중','고등학생':'고'}[m['stage']]
    return [g for g in confirmed(c, data['reference'][c['id']]).get(m['subject'], []) if g.startswith(prefix)]


def pending_note(m):
    if owner_confirmed(m['centerId'], m['subject'], m.get('stage')):
        return ''
    if m['centerId'] == 'center-row-098':
        return PLACEMENT_NOTE
    return PENDING_NOTES.get((m['centerId'], m['subject']), '') if not m['confirmedGrades'] else ''


@lru_cache(maxsize=1)
def practice_catalog():
    path = ROOT / 'tools/data/branch-verification/actual-practices.json'
    return json.loads(path.read_text(encoding='utf-8'))['centers'] if path.exists() else {}


def practice_for(center_id, subject=None, stage=None):
    row = practice_catalog().get(center_id)
    if not row:
        return None
    if placement_note(center_id):
        return None  # placement restriction takes precedence over general public copy
    selected = [p for p in row['practices']
                if (not subject or not p['subjects'] or subject in p['subjects'])
                and (not stage or not p['stages'] or stage in p['stages'])]
    return dict(row, practices=selected) if selected else None


def practice_basis(row):
    return '제공된 센터 운영자료' if row.get('sourceType') == 'provided-center-workbook' else '공식 센터 소개'
