"""Check every local title and a stratified production sample against the audit.

Source outside title/OG/Twitter values must remain byte-identical. Baseline
Git data additionally protects the sitemap, non-target pages and RSS contents.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import html
import json
import re
import subprocess
from urllib.parse import urlsplit, urlunsplit, quote, unquote
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

from personalize_title_suffixes import (ROOT, REPORT, BASELINE_COMMIT, DOMAIN, EXPECTED_TARGETS, EXPECTED_SITEMAP, EXPECTED_RSS,
    title_of, masked, sha, META_RE, attrs, clean)

from title_suffix_rules import HABIT_TOPICS, RULES
LABEL_SUBJECT={label:subject for label,subject,_,_ in RULES}
PROTECTED=('index.html','상담문의/index.html','과목별코칭/index.html','학년별코칭/index.html',
           '학습코칭/index.html','학습가이드/index.html','학습가이드/시험기간-학습계획/index.html',
           '학습가이드/오답관리-루틴/index.html','학습가이드/학부모상담-준비/index.html',
           '전국센터/index.html','vercel.json','robots.txt','PAGE_GENERATION_RULES.md','PROJECT_HANDOFF.md')


def verify_source(row,source,public=False):
    errors=[]
    if any(x in row['path'] for x in ('초등','중등','중학생')) and re.search('수능|모의고사',row['suffix']):
        errors.append('grade-inappropriate exam suffix')
    if row['kind']=='detail':
        family,stage,subject=row['group'].split('-')
        labels=[e['label'] for e in row['evidence']]
        if family=='grade' and labels[0] not in HABIT_TOPICS:
            errors.append('grade-role suffix lacks a learning-routine lead')
        if subject in ('math','english'):
            other='english' if subject=='math' else 'math'
            if not any(LABEL_SUBJECT.get(x)==subject for x in labels):
                errors.append('missing subject-specific suffix')
            if any(LABEL_SUBJECT.get(x)==other for x in labels):
                errors.append('wrong subject in suffix')
    if title_of(source)!=row['after']:errors.append('title mismatch')
    if re.split('[|｜]',row['before'],maxsplit=1)[0].strip()!=re.split('[|｜]',row['after'],maxsplit=1)[0].strip():
        errors.append('title prefix changed')
    if public:
        # Git checkout normalizes Windows CRLF to LF on the Linux deployment.
        if sha(masked(source).replace('\r\n','\n'))!=row['unchangedNormalizedContentSha256']:
            errors.append('non-title content changed')
    elif sha(masked(source))!=row['unchangedContentSha256']:
        errors.append('non-title content changed')
    for tag in META_RE.findall(source):
        values=attrs(tag)
        if values.get('property')=='og:title' or values.get('name')=='twitter:title':
            if values.get('content')!=row['after']:errors.append('social title mismatch')
    for raw in re.findall(r'<script\b[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',source,re.I|re.S):
        json.loads(raw)
    main=re.search(r'<main\b[^>]*>(.*?)</main>',source,re.I|re.S)
    visible=re.sub(r'\s+','',clean(main[1])) if main else ''
    for evidence in row['evidence']:
        if re.sub(r'\s+','',evidence['excerpt']) not in visible:
            errors.append('supporting excerpt not found in visible main copy')
        for term in evidence.get('terms',[evidence['match']]):
            if term not in evidence['excerpt']:errors.append('evidence match outside excerpt')
    return errors


def select_public(entries):
    groups=defaultdict(list);result={}
    for row in entries:
        groups[row['group']+'/'+row['kind']].append(row)
    for group,rows in groups.items():
        for i in sorted({0,len(rows)//2,len(rows)-1}):result[rows[i]['path']]=rows[i]
    for row in entries:
        if '명일동' in row['path'] or row['kind']=='category':result[row['path']]=row
    return list(result.values())


def git_bytes(path):
    return subprocess.run(['git','show',BASELINE_COMMIT+':'+path],cwd=ROOT,
                          check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE).stdout


def verify_discovery(report):
    errors=[]
    sitemap=(ROOT/'sitemap.xml').read_bytes()
    normalized=lambda b:b.replace(b'\r\n',b'\n')
    if normalized(sitemap)!=normalized(git_bytes('sitemap.xml')):errors.append('sitemap changed from baseline')
    if hashlib.sha256(sitemap).hexdigest()!=report['sitemapSha256']:errors.append('sitemap differs from audit')
    if len(ET.fromstring(sitemap).findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}url'))!=EXPECTED_SITEMAP:
        errors.append('sitemap URL count changed')
    rss=(ROOT/'rss.xml').read_bytes().decode('utf-8');original=git_bytes('rss.xml').decode('utf-8')
    mask_items=lambda s:re.sub(r'<item>.*?</item>',lambda m:re.sub(r'(<title>).*?(</title>)',r'\1__TITLE__\2',m[0],count=1,flags=re.S),s,flags=re.S)
    if mask_items(rss).replace('\r\n','\n')!=mask_items(original).replace('\r\n','\n'):
        errors.append('RSS non-item-title content changed')
    items=ET.fromstring(rss).findall('.//item')
    old_items={unquote(x.findtext('link','')):x.findtext('title','') for x in ET.fromstring(original).findall('.//item')}
    titles={unquote(x['url']):x['after'] for x in report['entries']}
    if len(items)!=EXPECTED_RSS:errors.append('RSS item count changed')
    for item in items:
        url=unquote(item.findtext('link',''))
        if item.findtext('title','')!=titles.get(url,old_items.get(url)):errors.append('RSS title mismatch: '+url)
    for path in PROTECTED:
        if normalized((ROOT/path).read_bytes())!=normalized(git_bytes(path)):
            errors.append('protected file changed: '+path)
    return errors


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--public',action='store_true');args=parser.parse_args()
    report=json.loads(REPORT.read_text(encoding='utf-8'))
    entries=select_public(report['entries']) if args.public else report['entries']
    if report['site']!=DOMAIN or len(report['entries'])!=EXPECTED_TARGETS:raise ValueError('wrong site/count')
    if len({r['after'] for r in report['entries']})!=EXPECTED_TARGETS:raise ValueError('duplicate complete title')

    def check(row):
        try:
            if args.public:
                split=urlsplit(row['url']);url=urlunsplit((split.scheme,split.netloc,quote(unquote(split.path),safe='/'),split.query,''))
                req=Request(url,headers={'User-Agent':'Coaching-Title-Release-Check/1.0'})
                with urlopen(req,timeout=35) as response:
                    status=response.status;source=response.read().decode('utf-8')
                    if response.url.rstrip('/')!=url.rstrip('/'):raise ValueError('unexpected redirect: '+response.url)
                    if 'text/html' not in response.headers.get('Content-Type',''):raise ValueError('not HTML')
            else:status=None;source=(ROOT/row['path']).read_bytes().decode('utf-8')
            return dict(path=row['path'],url=row['url'],status=status,title=title_of(source),errors=verify_source(row,source,args.public))
        except Exception as exc:return dict(path=row['path'],url=row['url'],errors=[str(exc)])

    with ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(check,entries))
    failures=[r for r in results if r['errors']]
    global_errors=[] if args.public else verify_discovery(report)
    summary=dict(mode='public' if args.public else 'local',checked=len(results),failures=len(failures),
                 globalErrors=global_errors,checkedAt=datetime.now(timezone.utc).isoformat(),results=results)
    output=REPORT.with_name('title-suffix-'+summary['mode']+'-verification.json')
    output.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({k:v for k,v in summary.items() if k!='results'},ensure_ascii=False))
    for failure in failures[:12]:print(json.dumps(failure,ensure_ascii=False))
    if failures or global_errors:raise SystemExit(1)
    print('TITLE_RELEASE_'+summary['mode'].upper()+'_PASS')


if __name__=='__main__':main()
