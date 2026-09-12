"""Explicit, audited release scope for six new branch topic groups."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
BASE='c840608d6b660dc77fd4ce061c6a828e4d5ddcc8'
REPORT=ROOT/'tools/reports/branch-topics'

def git(*args,**kw):
    return subprocess.check_output(['git','-c','core.safecrlf=false',*args],cwd=ROOT,**kw)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--stage',action='store_true');a=parser.parse_args()
    assert git('rev-parse','HEAD').decode().strip()==BASE
    assert git('branch','--show-current').decode().strip()=='main'
    assert not git('diff','--cached','--name-only'),'Existing staged edits must be preserved'
    audit=json.loads((REPORT/'audit.json').read_text(encoding='utf8'))
    parent=json.loads((ROOT/'tools/reports/branches/audit.json').read_text(encoding='utf8'))
    assert audit['status']==parent['status']=='PASS' and not audit['errors']
    assert len(audit['http'])==2226 and parent['legacyCheckPerformed']
    pages=json.loads((ROOT/'tools/data/branch-topics/manifest.json').read_text(encoding='utf8'))['pages']
    html=[p['path'].strip('/')+'/index.html' for p in pages]
    parents=sorted({p['parentPath'].strip('/')+'/index.html' for p in pages})
    reps=json.loads((ROOT/'tools/data/branch-topics/representatives.json').read_text(encoding='utf8'))
    public=html+parents+[p['src'].lstrip('/') for p in reps]+['assets/branch-topics-site4.css','assets/branches-site4.css','sitemap.xml','rss.xml']
    private=[p.relative_to(ROOT).as_posix() for pattern in ('*branch_topic*.py','*topic_release*.py') for p in (ROOT/'tools').glob(pattern)]
    private += ['tools/'+p for p in ('branch_templates_site4.py','generate_branch_pages_site4.py','audit_branch_pages_site4.py',
                                    'BRANCH_TOPIC_HANDOFF_2026-09-13.md','BRANCH_TOPIC_QUALITY_2026-09-13.md')]
    for folder in ('tools/data/branch-topics','tools/reports/branch-topics'):
        private += [p.relative_to(ROOT).as_posix() for p in (ROOT/folder).rglob('*') if p.is_file() and p.suffix in ('.json','.zip') and p.name not in ('production-verification.json','production-browser.json','release.json','release-plan.json')]
    private += ['tools/reports/branches/audit.json','tools/reports/branches/generation.json','tools/reports/branch-topics/release-plan.json']
    selected=sorted(set(public+private))
    assert len(html)==2226 and len(parents)==188 and len(reps)==371
    plan={'site':'https://xn--ol5ba64b839b.com','baselineCommit':BASE,'repository':'01039578283-hub/wawa-academy-new',
          'branch':'main','projectId':'prj_5xJteXuVXwQyrN3PVELCNmr2w6ZI','publicFiles':public,'privateFiles':sorted(set(private)),
          'approval':'User approved improvements, internal linking and production deployment in this turn.',
          'preservedUnrelatedPaths':['tools/BRAND_UPGRADE_HANDOFF_2026-09-12.md','tools/BRANCH_RELEASE_HANDOFF_2026-09-13.md',
            'tools/reports/branches/production-browser.json','tools/reports/branches/production-verification.json','tools/reports/branches/release.json',
            'tools/reports/brand-upgrade/production-browser.json','tools/reports/brand-upgrade/production-verification.json','tools/reports/brand-upgrade/release.json']}
    (REPORT/'release-plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    assert all((ROOT/p).is_file() for p in selected)
    assert max((ROOT/p).stat().st_size for p in selected)<95_000_000
    assert not set(selected).intersection(plan['preservedUnrelatedPaths'])
    tree={}
    for row in git('ls-tree','-rz','--full-tree',BASE).split(b'\0'):
        if row:
            head,file=row.split(b'\t',1);tree[file.decode('utf8')]=head.decode().split()[-1]
    changed=[]
    for p in selected:
        raw=(ROOT/p).read_bytes()
        if Path(p).suffix in ('.py','.html','.json','.css','.xml','.md','.txt','.js'):
            raw=raw.replace(b'\r\n',b'\n')
        digest=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
        if tree.get(p)!=digest:changed.append(p)
    if a.stage:
        git('add','--pathspec-from-file=-','--pathspec-file-nul',input=('\0'.join(selected)+'\0').encode())
        staged=set(git('diff','--cached','--name-only','-z').decode('utf8').rstrip('\0').split('\0'))
        assert staged==set(changed),{'missing':list(set(changed)-staged),'extra':list(staged-set(changed))}
        git('diff','--cached','--check')
    print(json.dumps({'public':len(public),'private':len(set(private)),'changed':len(changed),'staged':a.stage},ensure_ascii=False))

if __name__=='__main__':main()
