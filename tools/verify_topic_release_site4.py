"""Read-only full custom-domain verification against the released Git commit."""
import argparse
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
import json
from pathlib import Path
import time
from urllib.error import HTTPError
from urllib.parse import quote,urlsplit,unquote,urljoin
from urllib.request import Request,urlopen
import xml.etree.ElementTree as ET
from verify_branch_release_site4 import ROOT,DOMAIN,git,blob_id,PageAssets

def main():
    p=argparse.ArgumentParser();p.add_argument('--commit',required=True);args=p.parse_args()
    commit=git('rev-parse',args.commit).decode().strip()
    pages=json.loads(git('show',commit+':tools/data/branch-topics/manifest.json'))['pages']
    reps=json.loads(git('show',commit+':tools/data/branch-topics/representatives.json'))
    branches=json.loads(git('show',commit+':tools/data/branches/assets.json'))
    tree={}
    for row in git('ls-tree','-rz','--full-tree',commit).split(b'\0'):
        if row:
            head,file=row.split(b'\t',1);tree[file.decode('utf8')]=head.decode().split()[-1]
    targets={m['path'].strip('/')+'/index.html':'new-topic-page' for m in pages}
    targets.update({m['parentPath'].strip('/')+'/index.html':'parent-branch-page' for m in pages})
    targets.update({r['src'].lstrip('/'):'new-original-representative' for r in reps})
    targets.update({src.lstrip('/'):'preserved-branch-image' for src in branches})
    samples=['index.html','지점안내/index.html','지점안내/서울/index.html','학습코칭/index.html','전국센터/index.html',
             '학습가이드/오답관리-루틴/index.html','학습가이드/시험기간-학습계획/index.html','학습가이드/학부모상담-준비/index.html']
    targets.update({s:'regression-page' for s in samples})
    for file in samples+['지점안내/서울/명일점/index.html',pages[0]['path'].strip('/')+'/index.html']:
        collector=PageAssets();collector.feed(git('show',commit+':'+file).decode('utf-8-sig'))
        for value in collector.urls:
            u=urlsplit(urljoin(DOMAIN+'/'+file.removesuffix('index.html'),value))
            if u.hostname==urlsplit(DOMAIN).hostname:
                f=unquote(u.path).lstrip('/');assert f in tree,f;targets.setdefault(f,'shared-asset')
    for f in ('assets/branch-topics-site4.css','assets/branches-site4.css','robots.txt','sitemap.xml','rss.xml','llms.txt','assets/branch-search.js'):
        targets.setdefault(f,'discovery-or-navigation')
    assert all(f in tree for f in targets)

    def verify(job):
        file,kind=job;route=file.removesuffix('index.html') if file.endswith('index.html') else file
        url=DOMAIN+'/'+quote(route,safe='/');row={'path':file,'kind':kind,'expectedGitBlob':tree[file]}
        for attempt in range(3):
            try:
                request=Request(url,headers={'User-Agent':'WawaOwnerReleaseQA/1.0','Cache-Control':'no-cache','Accept-Encoding':'identity'})
                with urlopen(request,timeout=45) as response:
                    raw=response.read();row.update(status=response.status,finalUrl=response.url,bytes=len(raw),contentType=response.headers.get('content-type'))
                digest=blob_id(raw)
                normalized=blob_id(raw.replace(b'\r\n',b'\n')) if Path(file).suffix in ('.html','.css','.js','.xml','.txt','.svg') else digest
                row.update(actualGitBlob=digest,matchesCommit=tree[file] in (digest,normalized),attempts=attempt+1)
                row['passed']=row['status']==200 and row['matchesCommit'] and urlsplit(row['finalUrl']).hostname==urlsplit(DOMAIN).hostname
                if file=='sitemap.xml':
                    urls=[unquote(n.text) for n in ET.fromstring(raw).iter() if n.tag.endswith('}loc')]
                    row['urls']=len(urls);row['passed'] &= len(urls)==len(set(urls))==12214 and all(DOMAIN+m['path'] in urls for m in pages)
                if file=='rss.xml':
                    row['items']=len(ET.fromstring(raw).findall('.//item'));row['passed'] &= row['items']==55
                if row['passed']:return row
            except Exception as e:row.update(passed=False,error=type(e).__name__+': '+str(e))
            if attempt<2:time.sleep(2*(attempt+1))
        return row

    private=[]
    for route in ('tools/data/branch-topics/manuscripts.json','tools/data/branches/snapshot.json','.git/config','.env.local','지점안내/서울/명일점/명일동수학학원/'):
        try:
            with urlopen(DOMAIN+'/'+quote(route,safe='/'),timeout=30) as response:status=response.status
        except HTTPError as e:status=e.code
        except Exception as e:status=type(e).__name__
        private.append({'path':route,'status':status,'passed':status in (403,404)})
    results=[]
    with ThreadPoolExecutor(max_workers=6) as pool:
        jobs=[pool.submit(verify,item) for item in targets.items()]
        for future in as_completed(jobs):
            results.append(future.result())
            if len(results)%300==0:print('Verified',len(results),'/',len(targets),flush=True)
    failures=[r for r in results+private if not r['passed']]
    report={'site':DOMAIN,'commit':commit,'verifiedAtUtc':datetime.now(timezone.utc).isoformat(),'passed':not failures,
            'publicChecks':len(results),'newPages':len(pages),'parentPages':len({m['parentPath'] for m in pages}),
            'negativeChecks':len(private),'failures':failures,'resources':sorted(results,key=lambda r:r['path']),'private':private}
    (ROOT/'tools/reports/branch-topics/production-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('resources','private')},ensure_ascii=False,indent=2))
    raise SystemExit(0 if not failures else 1)

if __name__=='__main__':main()
