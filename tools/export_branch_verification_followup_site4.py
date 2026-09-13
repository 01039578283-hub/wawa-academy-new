"""Refresh the earlier request packet after the user's scoped confirmation."""
from collections import defaultdict
import json
from pathlib import Path
from branch_verified_facts_site4 import ROOT, load_reviewed_snapshot, owner_confirmation
from branch_reviews_site4 import review_catalog, reviews_for


def main():
    data=json.loads((ROOT/'tools/data/branch-topics/display-manuscripts.json').read_text(encoding='utf-8'))
    centers={c['id']:c for c in load_reviewed_snapshot()['centers']}
    scope=json.loads((ROOT/'tools/reports/branch-reviews/scope-review.json').read_text(encoding='utf-8'))
    paths={p for r in scope['groups'] for p in r['paths']}
    groups=defaultdict(list)
    for m in data:
        if m['path'] in paths: groups[m['centerId']].append(m)
    assert sum(map(len,groups.values()))==41 and len(groups)==8
    assert all(m['confirmedGrades'] for m in data)
    reviews=review_catalog()
    reviewed_centers={r['centerId'] for r in reviews}
    topic_review_count=sum(bool(reviews_for(m['centerId'],m['subject'],m['stage'])) for m in data)
    lines=['와와학원.com 개설 학년 확인 및 공식 학생 후기 반영 결과',
           '갱신일: '+owner_confirmation()['confirmedAt'],'',
           '이 파일은 앞서 저장한 확인 요청사항을 사용자 답변 이후의 완료 상태로 갱신한 기록입니다.',
           '이전의 “8개 지점 / 41페이지 확인 필요” 상태는 아래 사용자 확인으로 해소되었습니다.','',
           '1. 수업 가능 여부 반영',
           '- 사용자 확인: “수업 다 가능해.”',
           '- 범위: 직전 확인 요청에 포함된 8개 지점의 해당 과목·학교급 41페이지.',
           '- 최초 59개 = 원본 표 재검토로 18개 복구 + 사용자 확인으로 41개 반영. 미확정 페이지 0개.',
           '- 지점 과목표·요약·FAQ·내부링크 표시와 해당 동네 페이지의 Service를 함께 정합화.',
           '- 수업 가능 확인을 현재 빈자리·시간표·세부 과정 보장으로 확대하지 않음.','']
    for cid, records in sorted(groups.items(),key=lambda x:(centers[x[0]]['region']['province'],centers[x[0]]['sourceCenterName'])):
        c=centers[cid]
        lines += [f"[{c['region']['province']} {c['sourceCenterName']}] {len(records)}페이지",
                  '반영: '+', '.join(dict.fromkeys(m['stage']+' '+m['subject']+' ('+', '.join(m['confirmedGrades'])+')' for m in records))]
        lines += ['https://와와학원.com'+m['path'] for m in sorted(records,key=lambda m:(m['topic'],m['locality']))]
        lines += ['']
    lines += ['2. 공식 학생 후기',
              f'- 원문이 확인되는 공개 후기 {len(reviews)}개를 {len(reviewed_centers)}개 실제 지점에 연결.',
              f'- 지점 부모 페이지 {len(reviewed_centers)}개, 과목·학교급 일치 동네 페이지 {topic_review_count}개에 표시.',
              '- 지점이 불명확하거나 제외된 브랜드, 본문이 확인되지 않는 글은 임의 요약하지 않음.',
              '- 학교급이 확인되지 않는 사례는 해당 지점 부모에서만 표시.',
              '- 작성 당시의 학생 경험으로 안내. 실제 독립 성과 검증이나 전체 학생의 결과 보장으로 표현하지 않음.',
              '- 가상 상담 준비 예시는 기존대로 가상임을 표시하고 실제 후기와 구분.','',
              '3. 별개 조건 보존',
              '- 내발산·동백·두호의 원본 표에 없는 추가 학년·학교·수준 조건은 이번 8지점 확인 범위 밖이므로 보존.',
              '- 화성태안점의 상세 방문 주소 확인은 수업 가능 여부와 별개로 유지.',
              '- 원본 엑셀/CSV/ZIP/원고/이미지/지도/교육비와 URL 보존.','',
              '4. 배포 상태',
              '- 이번 변경은 로컬 반영. GitHub push 및 공개 배포하지 않음.',
              '- 상세 기록: 새 홈페이지4/tools/BRANCH_OWNER_REVIEWS_2026-09-13.md']
    path=Path('C:/Users/1992k/Desktop/와와학원_학년확인_및_실제사례_요청사항.txt')
    path.write_bytes(('\ufeff'+'\r\n'.join(lines)+'\r\n').encode('utf-8'))
    assert path.read_text(encoding='utf-8-sig').count('https://와와학원.com/')==41
    print(str(path))


if __name__=='__main__': main()
