"""Published, attributed student experiences; never invented branch reviews."""
from functools import lru_cache
from html import escape
import json
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]


@lru_cache(maxsize=1)
def review_catalog():
    path = ROOT / 'tools/data/branch-reviews/published-reviews.json'
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding='utf-8'))
    assert data['sourceType'] == 'official-published-student-review'
    assert data['independentlyVerified'] is False
    rows = data['reviews']
    assert len({r['id'] for r in rows}) == len(rows)
    for row in rows:
        source = urlsplit(row['sourceUrl'])
        assert source.scheme == 'https' and source.hostname == 'www.wawacenter.com'
        assert source.path.startswith('/review/') and row['centerId']
        assert row['identityEvidence'] and row['sourceExcerpts'] and row['summary']
    return rows


def reviews_for(center_id, subject=None, stage=None):
    # Unknown grade/subject cannot become a subject-stage recommendation.
    return [r for r in review_catalog() if r['centerId'] == center_id
            and (not (subject or stage) or not r.get('parentOnly'))
            and (not subject or subject in r['subjects'])
            and (not stage or stage in r['stages'])]


def review_cards(rows, parent_path=None):
    esc = lambda value: escape(str(value), quote=True)
    body = '<div class="branch-decision-cards branch-review-cards">'
    for row in rows:
        grade = row.get('gradeText', '') if row.get('stages', [True]) else ''
        label = ' · '.join(x for x in [grade, '·'.join(row['subjects'])] if x)
        heading = row.get('caseHeading') or (label + ' 학습 경험')
        body += '<article data-review-id="' + esc(row['id']) + '"><p class="branch-small">' + esc(label) + ' · 공식 공개 후기</p>'
        body += '<h3>' + esc(heading) + '</h3><p class="branch-focus-copy">' + esc(row['summary']) + '</p>'
        if row.get('publishedAt'):
            body += '<p class="branch-small">후기 게시일: ' + esc(row['publishedAt']) + '</p>'
        body += '<p class="branch-inline-guide"><a href="' + esc(row['sourceUrl']) + '" target="_blank" rel="noopener">공식 후기 원문 보기 ↗</a></p></article>'
    body += '</div><p class="branch-small">후기 속 학년과 경험은 작성 당시 기준입니다. 학생 개인의 경험을 요약한 것으로, 같은 수업을 듣는 모든 학생에게 동일한 결과를 보장하지 않습니다.</p>'
    if parent_path:
        body += '<div class="branch-actions"><a class="branch-button secondary" href="' + esc(parent_path) + '#student-reviews">이 지점의 공개 후기 더 보기 →</a></div>'
    return body
