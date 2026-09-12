"""Snapshot attachments and reconcile the reviewed 371-locality parent mapping."""
from __future__ import annotations
from collections import Counter
import json
from pathlib import Path
import re
import shutil
from branch_topic_manuscripts_site4 import TOPICS, load_archive, sha, text_fields
from branch_editorial_site4 import confirmed
from branch_templates_site4 import branch_path
from branch_site4_support import ROOT

DATA = ROOT / 'tools/data/branch-topics'
REPORTS = ROOT / 'tools/reports/branch-topics'
SOURCE = Path('C:/Users/1992k/Desktop/프로그램 원고')
REFERENCE = ROOT.parent / '새 홈페이지15'


def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    value = (json.dumps(obj, ensure_ascii=False, indent=2) + '\n').encode()
    if not path.exists() or path.read_bytes() != value:
        path.write_bytes(value)


def snapshot(source, target):
    if target.exists():
        assert sha(target.read_bytes()) == sha(source.read_bytes()), 'Source changed: ' + str(source)
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def main():
    mapping_source = REFERENCE / 'reports/branches/neighborhood-mapping.json'
    schools_source = REFERENCE / 'tools/data/branches/target-schools.json'
    snapshot(mapping_source, DATA / 'mapping.json')
    snapshot(schools_source, DATA / 'schools.json')
    mapping = json.loads((DATA / 'mapping.json').read_text(encoding='utf8'))
    schools = {r['neighborhood']: r for r in json.loads((DATA / 'schools.json').read_text(encoding='utf8'))}
    original = json.loads((ROOT / 'tools/data/branches/snapshot.json').read_text(encoding='utf8'))
    centers = {c['id']: c for c in original['centers']}
    rows = {r['locality']: r for r in mapping['rows']}
    assert len(rows) == 371 and all(r['status'] == 'confirmed' for r in rows.values())
    mapping_exceptions = []
    for key, r in rows.items():
        c = centers[r['centerId']]
        assert r['branchPath'] == branch_path(c) and r['centerName'] == c['sourceCenterName']
        if key not in original['schoolMatches'][c['id']]['neighborhoods']:
            # These three owner-reviewed service areas cross the original CSV's
            # region boundary; current branch identity is anchored by registration.
            assert c['id'] == 'center-row-148' and key in ('위례', '위례신도시', '창곡동'), (key, c['id'])
            mapping_exceptions.append({'locality':key,'centerId':c['id'],'basis':'reviewed registered identity; current school aggregation is empty'})
        candidates = [e for e in r['evidence']['registeredIdentityComparison'] if e['centerId'] == c['id'] and e['strongIdentityEvidence']]
        assert len(candidates) == 1, key
        identity = candidates[0]
        fold = lambda s: re.sub(r'\s+', '', s)
        assert fold(identity['currentAddress']) == fold(c['address']), key
        assert fold(identity['currentRegistrationNumber']) == fold(c['registrationNumber']), key
        assert fold(identity['currentRegisteredName']) == fold(c['registeredAcademyName']), key
        assert (ROOT / branch_path(c).strip('/') / 'index.html').is_file()
        assert key in schools
    records, warnings, examples = [], [], []
    stats = []
    for topic in TOPICS:
        archive = SOURCE / (topic + '.zip')
        target = DATA / 'sources' / archive.name
        snapshot(archive, target)
        group = load_archive(target, topic)
        assert {m['locality'] for m in group} == set(rows), topic
        counts = Counter()
        for m in group:
            row = rows[m['locality']]
            c = centers[row['centerId']]
            prefix = {'고등학생':'고', '중학생':'중', '초등학생':'초'}[m['stage']]
            grades = [g for g in confirmed(c, original['reference'][c['id']]).get(m['subject'], []) if g.startswith(prefix)]
            if not grades:
                warnings.append({'title':m['title'], 'center':c['sourceCenterName'], 'reason':'stage/subject not confirmed; learning information only'})
            m.update(centerId=c['id'], parentPath=branch_path(c), path=branch_path(c)+m['title'].replace(' ', '')+'/', confirmedGrades=grades)
            for field, value in text_fields(m):
                for token in re.findall(r'원고|키워드|(?:[A-H]열)|ROW_DATA|입력|제공된|제시된', value):
                    counts[token] += 1
                    examples.append({'title':m['title'],'field':field,'token':token,'text':value})
            records.append(m)
        stats.append({'topic':topic,'count':len(group),'sha256':sha(target.read_bytes()),'authoringTokens':dict(counts),
                      'sections':dict(Counter(len(m['sections']) for m in group)), 'faqs':dict(Counter(len(m['faq']) for m in group))})
    assert len(records) == len({m['path'] for m in records}) == 2226
    save(DATA / 'manuscripts.json', records)
    report = {'status':'PASS','archiveStats':stats,'pages':len(records),'localities':len(rows),'parentBranches':len({m['centerId'] for m in records}),
              'qualifiedScopePages':len(warnings),'scopeWarnings':warnings,'mappingExceptions':mapping_exceptions,
              'sources':[{'path':str(p),'sha256':sha(p.read_bytes())} for p in (mapping_source,schools_source,ROOT/'tools/data/branches/snapshot.json')],
              'policy':'Local only. No source rewriting, nearest-branch guessing, broad grade availability, or deployment.'}
    save(REPORTS / 'inputs.json', report)
    save(REPORTS / 'authoring-expressions.json', examples)
    print(json.dumps({k:v for k,v in report.items() if k not in ('scopeWarnings','sources')},ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
