"""Evidence-specific audit in addition to the full page regression checks."""
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from bs4 import BeautifulSoup
from branch_verified_facts_site4 import (
    ROOT, REVIEWED_SCOPE_CENTERS, SNAPSHOT_SHA, WORKBOOK_SHA, load_reviewed_snapshot,
    recorded_grades, practice_for, practice_catalog, pending_note, LOCATION_REPAIRS,
)
from branch_templates_site4 import branch_path, center_page
from branch_reviews_site4 import review_catalog


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    errors, checks = [], 0
    def check(value, name):
        nonlocal checks
        checks += 1
        if not value:
            errors.append(name)
    report_root = ROOT/'tools/reports/branch-verification'
    baseline = json.loads((ROOT/'tools/data/branches/snapshot.json').read_text(encoding='utf-8'))
    source_before = deepcopy(baseline)
    reviewed = load_reviewed_snapshot()
    centers = {c['id']:c for c in reviewed['centers']}
    raw = json.loads((ROOT/'tools/data/branch-topics/manuscripts.json').read_text(encoding='utf-8'))
    display = json.loads((ROOT/'tools/data/branch-topics/display-manuscripts.json').read_text(encoding='utf-8'))
    manifest = json.loads((ROOT/'tools/data/branch-topics/manifest.json').read_text(encoding='utf-8'))['pages']
    candidates = json.loads((report_root/'reviewed-scope-candidates.json').read_text(encoding='utf-8'))
    check(digest(ROOT/'tools/data/branches/snapshot.json')==SNAPSHOT_SHA,'immutable snapshot')
    check(digest(Path(candidates['sources'][0]['path']))==WORKBOOK_SHA,'original workbook hash')
    expected_changes = {p for r in candidates['overlays'] for p in r['paths']}
    changes = {old['path'] for old,new in zip(raw,display) if old['confirmedGrades']!=new['confirmedGrades']}
    check(len(expected_changes)==18 and expected_changes.issubset(changes),'18 table-baseline recoveries retained')
    owner_changes={m['path'] for m in raw if not m['confirmedGrades']} - expected_changes
    check(len(owner_changes)==41 and changes==expected_changes|owner_changes,'exact 18 recorded plus 41 owner-confirmed recoveries')
    check(sum(not m['confirmedGrades'] for m in display)==0,'no unresolved pages after scoped user confirmation')
    for row in candidates['overlays']:
        c=centers[row['centerId']]
        check(c['subjects'][row['subject']]['grades']==row['explicitTableGrades'],'source table grade match '+c['id']+row['subject'])
    check(baseline==source_before,'in-memory source not mutated')
    official={r['centerId']:r for r in json.loads((report_root/'official-practice-sources.json').read_text(encoding='utf-8'))['centers']}
    workbook=json.loads((report_root/'workbook-practice-cells.json').read_text(encoding='utf-8'))['centers']
    for cid,row in practice_catalog().items():
        check(row['address']==centers[cid]['address'],'evidence branch address '+cid)
        check(bool(row['identityBasis']) and bool(row['verifiedAt']),'evidence identity and retrieval date '+cid)
        if row['sourceType']=='official-center-description':
            evidence=official[cid]
            check(row['sourceHash']==evidence['htmlSha256'] and row['sourceUrl']==evidence['url'],'official evidence hash/url '+cid)
            evidence_text=evidence['introText']
        else:
            check(row['sourceHash']==WORKBOOK_SHA and row['sourceType']=='provided-center-workbook','workbook evidence hash/type '+cid)
            evidence_text='\n'.join(workbook[cid][key]['value'] or '' for key in ('AC','AD'))
        for item in row['practices']:
            check(item['sourceExcerpt'] in evidence_text,'exact supporting excerpt '+cid+item['title'])
            check(not item['isIndividualStudentCase'],'practice not called a student case '+cid)
            check(set(item['subjects']).issubset({'영어','수학','국어','과학','사회'}),'valid subject filter '+cid)
            check(set(item['stages']).issubset({'초등학생','중학생','고등학생'}),'valid stage filter '+cid)
    lessons, parent_lessons = 0, 0
    for old,m in zip(raw,display):
        check(m['path']==old['path'] and m['title']==old['title'] and m['centerId']==old['centerId'],'route/title/identity '+m['path'])
        check(m['confirmedGrades']==recorded_grades(m),'recorded grade lookup '+m['path'])
        if m['path'] in expected_changes:
            check(set(m['confirmedGrades']).issubset(centers[m['centerId']]['subjects'][m['subject']]['grades']),'no extension grade inserted '+m['path'])
        soup=BeautifulSoup((ROOT/m['path'].strip('/')/'index.html').read_bytes(),'html.parser')
        note=pending_note(m)
        check(not note or note in soup.get_text(' ',strip=True),'qualified scope note '+m['path'])
        p=practice_for(m['centerId'],m['subject'],m['stage']) if m['confirmedGrades'] else None
        panel=soup.select_one('#documented-learning')
        check(bool(panel)==bool(p),'no ungrounded lesson section '+m['path'])
        if p:
            lessons+=1
            check(p['practices'][0]['text'] in panel.get_text(' ',strip=True),'source-bounded practice text '+m['path'])
            check(panel.a['href']==m['parentPath']+'#verified-learning','branch evidence internal link '+m['path'])
        graph=json.loads(soup.select_one('script[type="application/ld+json"]').string)['@graph']
        check(not any(n['@type'] in ('Review','AggregateRating') for n in graph),'no fictional real review '+m['path'])
        service=[n for n in graph if n['@type']=='Service']
        check(bool(service)==bool(m['confirmedGrades']),'conditional Service '+m['path'])
    for c in reviewed['centers']:
        path=branch_path(c)
        soup=BeautifulSoup((ROOT/path.strip('/')/'index.html').read_bytes(),'html.parser')
        p=practice_for(c['id'])
        panel=soup.select_one('#verified-learning')
        check(bool(panel)==bool(p),'parent practice presence '+c['id'])
        if p:
            parent_lessons+=1
            check(p['address']==c['address'],'practice identity '+c['id'])
            check(all(item['text'] in panel.get_text(' ',strip=True) for item in p['practices']),'all curated practice visible '+c['id'])
        # Derived field changes are accepted only if the full deterministic recipe
        # still reproduces them. Immutable core fields are checked separately.
        if c['id'] in REVIEWED_SCOPE_CENTERS:
            c['_neighborhoodPages']=[dict(m,topicOrder=i//371) for i,m in enumerate(manifest) if m['centerId']==c['id']]
            _,expected=center_page(c,reviewed['schoolMatches'].get(c['id']),reviewed['centers'],reviewed['reference'][c['id']])
            esoup=BeautifulSoup(expected,'html.parser')
            for selector in ('#programs','#learning','#curriculum','#questions','.branch-editorial-intro'):
                check(soup.select_one(selector).get_text(' ',strip=True)==esoup.select_one(selector).get_text(' ',strip=True),'reviewed parent regeneration '+c['id']+selector)
        if c['id'] in LOCATION_REPAIRS:
            check(all(p in soup.select_one('#center-info').get_text(' ',strip=True) for p in LOCATION_REPAIRS[c['id']]),'location contradiction repaired '+c['id'])
    stats={'status':'PASS' if not errors else 'FAIL','checks':checks,'errors':errors,
           'beforeUnknownPages':59,'recordedBaselineRestored':18,'ownerConfirmedPages':41,'remainingUnknownPages':0,
           'remainingBranches':len({m['centerId'] for m in display if not m['confirmedGrades']}),
           'parentPracticeSections':parent_lessons,'topicPracticeSections':lessons,
           'practiceSources':dict(Counter(p.get('sourceType') for p in practice_catalog().values())),
           'independentStudentRecordsVerified':0,
           'officialPublishedStudentReviewsSelected':len(review_catalog()),
           'scopeMeaning':'18 recorded source recoveries plus 41 pages confirmed by the website owner in conversation on 2026-09-13. No independent phone confirmation or timetable/vacancy claim.',
           'deployment':'NOT DEPLOYED; local review only'}
    (report_root/'implementation-audit.json').write_text(json.dumps(stats,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(stats,ensure_ascii=False,indent=2))
    assert not errors


if __name__=='__main__':
    main()
