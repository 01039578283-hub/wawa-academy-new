"""Check published reviews against source evidence and every rendered placement."""
from collections import Counter
from datetime import datetime
import json
from bs4 import BeautifulSoup
from branch_verified_facts_site4 import ROOT, load_reviewed_snapshot, owner_confirmation
from branch_reviews_site4 import review_catalog, reviews_for
from branch_templates_site4 import branch_path


def main():
    errors=[]
    checks=0
    def check(ok,label):
        nonlocal checks
        checks+=1
        if not ok: errors.append(label)
    data=load_reviewed_snapshot()
    centers={c['id']:c for c in data['centers']}
    sources=json.loads((ROOT/'tools/reports/branch-reviews/review-source-snapshot.json').read_text(encoding='utf-8'))
    source_by_id={str(r['id']):r for r in sources['reviews']}
    rows=review_catalog()
    check(bool(rows),'nonempty verified published review selection')
    for row in rows:
        source=source_by_id[str(row['id'])]
        prefix=str(row['id'])+': '
        check(row['centerId'] in centers,prefix+'actual existing branch')
        check(not any(s in source['sourceCenterLabel'] for s in ('글로리드','W+')),prefix+'excluded brands not relabeled')
        check(row['sourceUrl']==source['url'] and row['originalTitle']==source['detailTitle'],prefix+'canonical official source title/url')
        check(row['sourceHash']==source['htmlSha256'],prefix+'evidence snapshot hash')
        check(row['centerAddress']==centers[row['centerId']]['address'],prefix+'selected current branch address')
        check(source['httpStatus']==200 and source['hasReadableDetail'],prefix+'source detail readable')
        text=source['bodyText']
        check(all(' '.join(e.split()) in ' '.join(text.split()) for e in row['sourceExcerpts']),prefix+'exact supporting source excerpts')
        check(set(row['stages']).issubset({'초등학생','중학생','고등학생'}),prefix+'valid stage filters')
        check(bool(row['identityEvidence']),prefix+'explicit branch identity rationale')
        if row.get('publishedAt'):
            parsed=datetime.strptime(source['publishedDateText'],'%y.%m.%d').date().isoformat()
            check(row['publishedAt']==parsed,prefix+'posting date not case occurrence date')
    parent_count=topic_count=0
    placements=Counter()
    def verify_panel(soup,expected,path):
        panel=soup.select_one('#student-reviews')
        check(bool(panel)==bool(expected),'review section presence '+path)
        check(bool(soup.select_one('nav a[href="#student-reviews"]'))==bool(expected),'visible review anchor '+path)
        if not expected: return
        check([a['data-review-id'] for a in panel.select('[data-review-id]')]==[str(r['id']) for r in expected],'exact branch/subject/grade selection '+path)
        for row in expected:
            card=panel.select_one('[data-review-id="'+str(row['id'])+'"]')
            check(row['summary'] in card.get_text(' ',strip=True),'verbatim curated summary '+path+str(row['id']))
            check(card.select_one('a')['href']==row['sourceUrl'],'official detail attribution '+path+str(row['id']))
            placements[str(row['id'])]+=1
        check('동일한 결과를 보장하지 않습니다' in panel.get_text(),'individual outcomes not guaranteed '+path)
        check(not panel.select('img'),'existing source image sequence untouched '+path)
    for c in centers.values():
        path=branch_path(c)
        soup=BeautifulSoup((ROOT/path.strip('/')/'index.html').read_bytes(),'html.parser')
        selected=reviews_for(c['id'])
        verify_panel(soup,selected,path)
        parent_count+=bool(selected)
    records=json.loads((ROOT/'tools/data/branch-topics/display-manuscripts.json').read_text(encoding='utf-8'))
    for m in records:
        soup=BeautifulSoup((ROOT/m['path'].strip('/')/'index.html').read_bytes(),'html.parser')
        expected=reviews_for(m['centerId'],m['subject'],m['stage']) if m['confirmedGrades'] else []
        verify_panel(soup,expected,m['path'])
        topic_count+=bool(expected)
        graph=json.loads(soup.select_one('script[type="application/ld+json"]').string)['@graph']
        article=next(n for n in graph if n['@type']=='Article')
        check([r['url'] for r in article.get('citation',[])]==[r['sourceUrl'] for r in expected],'schema citation only visible source '+m['path'])
        check(not any(n['@type'] in ('Review','AggregateRating') for n in graph),'no rating fabricated '+m['path'])
        if expected:
            check(soup.select_one('#student-reviews .branch-actions a')['href']==m['parentPath']+'#student-reviews','parent review internal link '+m['path'])
        check('실제 수강 후기나 성과 사례가 아닌' in soup.select_one('#consultation-example').get_text(),'fictional and authentic separated '+m['path'])
    stats={'status':'PASS' if not errors else 'FAIL','checks':checks,'errors':errors,
           'officialListingPagesRead':sources['listingPageCount'],'officialDetailsRead':sources['detailCount'],
           'selectedPublishedReviews':len(rows),'matchedBranches':len({r['centerId'] for r in rows}),
           'parentPagesWithReviews':parent_count,'topicPagesWithReviews':topic_count,
           'placementsByReview':dict(placements),'independentlyVerifiedStudentOutcomes':False,
           'ownerConfirmationDate':owner_confirmation()['confirmedAt'],'deployment':'LOCAL ONLY'}
    (ROOT/'tools/reports/branch-reviews/implementation-audit.json').write_text(json.dumps(stats,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(stats,ensure_ascii=False,indent=2))
    assert not errors


if __name__=='__main__': main()
