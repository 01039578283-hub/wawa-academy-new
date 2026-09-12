"""Exhaustive local checks for the six school-level neighborhood article groups."""
from __future__ import annotations
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from io import BytesIO
import argparse
import json
from pathlib import Path
import re
import subprocess
import tarfile
from urllib.parse import unquote, urlsplit, quote
from urllib.request import urlopen
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from branch_site4_support import ROOT, DOMAIN
from branch_topic_manuscripts_site4 import TOPICS, load_archive, sha, norm, text_fields
from branch_topic_editorial_site4 import prepare, clean_copy
from prepare_branch_topics_site4 import DATA, REPORTS, save, SOURCE

BASE_COMMIT = 'c840608d6b660dc77fd4ce061c6a828e4d5ddcc8'


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--base-url')
    args=parser.parse_args()
    records=json.loads((DATA/'display-manuscripts.json').read_text(encoding='utf8'))
    manifest=json.loads((DATA/'manifest.json').read_text(encoding='utf8'))['pages']
    baseline=json.loads((DATA/'site-baseline.json').read_text(encoding='utf8'))
    source_data=json.loads((ROOT/'tools/data/branches/snapshot.json').read_text(encoding='utf8'))
    centers={c['id']:c for c in source_data['centers']}
    raw_records={m['path']:m for m in json.loads((DATA/'manuscripts.json').read_text(encoding='utf8'))}
    errors=[]
    total=0
    def check(ok,label):
        nonlocal total
        total+=1
        if not ok:
            errors.append(label)
    @lru_cache(maxsize=None)
    def target_file(path):
        p=ROOT/path.lstrip('/')
        return p/'index.html' if not Path(path).suffix or path.endswith('/') else p
    @lru_cache(maxsize=None)
    def target_ids(path):
        p=target_file(path)
        return set(re.findall(r'\bid="([^"]+)"',p.read_text(encoding='utf8'))) if p.is_file() and p.suffix=='.html' else set()
    check(len(records)==len(manifest)==len({m['path'] for m in records})==2226,'2226 unique pages')
    check(Counter(m['topic'] for m in records)==Counter({k:371 for k in TOPICS}),'six complete groups')
    documents,descriptions,body_hashes=[],[],[]
    section_counts,paragraphs,source_tokens=[],[],[]
    for m in records:
        path=m['path']; c=centers[m['centerId']]; ref=source_data['reference'][c['id']]
        prefix=path+': '
        raw=target_file(path).read_bytes()
        check(sha(raw)==m['htmlSha256'],prefix+'generated file hash')
        expected,_=prepare(raw_records[path])
        check(all(expected[k]==m[k] for k in ('meta','intro','sections','faq','cases','documentTitle','quickScan','contextualLinks')),prefix+'reviewed manuscript overlay current')
        soup=BeautifulSoup(raw,'html.parser')
        canonical=DOMAIN+quote(path,safe='/')
        check(len(soup.select('h1'))==1 and soup.h1.get_text()==m['title'],prefix+'single exact H1')
        check(soup.title.get_text()==m['documentTitle'],prefix+'body-aligned title')
        check(soup.select_one('meta[name="description"]')['content']==m['meta'],prefix+'unique source description')
        check(soup.select_one('link[rel="canonical"]')['href']==canonical,prefix+'self canonical')
        check(soup.select_one('meta[property="og:url"]')['content']==canonical,prefix+'og URL')
        check(soup.select_one('meta[property="og:type"]')['content']=='article',prefix+'article OG type')
        check(not soup.select('meta[name="robots"][content*="noindex"]'),prefix+'indexable')
        check(len(soup.select('meta[name="naver-site-verification"]'))==1,prefix+'verification tag')
        check(len(soup.select('.branch-breadcrumb li'))==5,prefix+'five breadcrumb levels')
        check(not re.search(r'010[- ]?\d{4}[- ]?\d{4}',soup.get_text(' ',strip=True)),prefix+'no visible phone-number text')
        check(soup.select_one('.floating-actions a')['href']=='tel:01039578283',prefix+'target contact preserved')
        graph=json.loads(soup.select_one('script[type="application/ld+json"]').string)['@graph']
        gids=[n['@id'] for n in graph if '@id' in n]
        check(len(gids)==len(set(gids)),prefix+'unique JSON-LD ids')
        check(all(x.startswith(DOMAIN) for x in gids),prefix+'schema target domain')
        check(not any(n['@type'] in ('Review','AggregateRating','Product') for n in graph),prefix+'no invented review or rating')
        org=next(n for n in graph if n['@type']=='EducationalOrganization')
        article=next(n for n in graph if n['@type']=='Article')
        check(article.get('abstract')==m['intro'],prefix+'schema abstract matches visible first answer')
        check(article.get('articleSection')==[m['stage']+' 학습 안내',m['subject']+' 학습코칭'],prefix+'article category semantics')
        check(article.get('image',{}).get('contentUrl')==DOMAIN+ref['primaryMedia']['body']['src'],prefix+'schema visible body image')
        parts={n['@id']:n for n in graph if n['@type']=='WebPageElement'}
        check(all(p['@id'] in parts for p in article['hasPart']),prefix+'all article parts typed')
        check(org['@id']==DOMAIN+quote(m['parentPath'],safe='/')+'#center' and org['name']==c['displayName'],prefix+'shared actual branch identity')
        check('telephone' not in org and 'openingHours' not in org,prefix+'no false direct phone or hours')
        check(org['address'].get('streetAddress')==(c['address'] if c.get('addressPrecision')!='neighborhood' else None),prefix+'verified address precision')
        service=[n for n in graph if n['@type']=='Service']
        check(bool(service)==bool(m['confirmedGrades']),prefix+'service only for confirmed stage')
        if service:
            check(all(g in service[0]['description'] for g in m['confirmedGrades']),prefix+'exact confirmed grades')
        else:
            check(soup.select_one('.topic-hero .topic-scope-notice') is not None,prefix+'unconfirmed course visibly qualified')
        faqs=[(norm(x.summary.get_text()),norm(x.p.get_text())) for x in soup.select('#questions .branch-faq details')]
        qas=[(f['question'],f['answer']) for f in m['faq']]
        ldqas=[(q['name'],q['acceptedAnswer']['text']) for n in graph if n['@type']=='FAQPage' for q in n['mainEntity']]
        check(faqs==qas==ldqas and len(qas)==4,prefix+'four exact visible/schema FAQs')
        check('실제 수강 후기나 성과 사례가 아닌' in soup.select_one('#consultation-example').get_text(),prefix+'fictional example labeled')
        media=soup.select('.branch-primary-media img')
        expected_media=[m['representative']['src'],ref['primaryMedia']['body']['src'],ref['primaryMedia']['map']['src']]
        check([x['src'] for x in media]==expected_media,prefix+'representative/body/map order')
        check(media[0].get('style')=='display:none;' and media[0]['alt']==m['title']+' 와와학원 대표',prefix+'hidden representative only')
        check(media[1]['alt']==m['title']+' 본문' and media[2]['alt']==m['title']+' 지도',prefix+'page specific body/map ALT')
        check(not media[1].get('style') and not media[1].find_parent('details'),prefix+'body image not collapsed')
        check(len([x for x in soup.select('[style]') if 'display:none' in x['style'].replace(' ','')])==1,prefix+'only one hidden representative')
        for im in media:
            check((ROOT/im['src'].lstrip('/')).is_file() and im.get('width') and im.get('height'),prefix+'local image with dimensions')
        ids=[x['id'] for x in soup.select('[id]')]
        check(len(ids)==len(set(ids)),prefix+'unique HTML ids')
        for link in soup.select('a[href]'):
            u=urlsplit(link['href'])
            if u.scheme or u.netloc:
                continue
            p=unquote(u.path) or path
            check(p.startswith('/') and target_file(p).is_file(),prefix+'internal destination '+link['href'])
            if u.fragment:
                check(unquote(u.fragment) in (set(ids) if p==path else target_ids(p)),prefix+'anchor '+link['href'])
        seen=[]
        for i,s in enumerate(m['sections'],1):
            el=soup.select_one('#section-'+str(i))
            check(el.h2.get_text()==s['heading'],prefix+'section heading '+str(i))
            body=norm(' '.join(x.get_text() for x in el.select('.topic-copy')))
            check(body==norm(' '.join(s['paragraphs'])),prefix+'manuscript paragraph preservation '+str(i))
            seen.append(body)
            paragraphs.extend(len(x.get_text()) for x in el.select('.topic-copy'))
        section_counts.append(len(m['sections']))
        quick=soup.select('.topic-quick-scan li a')
        check(len(quick)==len(m['quickScan']) and bool(quick),prefix+'evidence-linked quick scan')
        for a,item in zip(quick,m['quickScan']):
            check(a['href']=='#section-'+str(item['section']) and a.select_one('.topic-quick-answer').get_text()==item['text'],prefix+'quick answer exact copy')
            check(item['text'] in m['sections'][item['section']-1]['paragraphs'][item['paragraph']],prefix+'quick answer grounded in body')
        inline=soup.select('.topic-paragraph-unit .topic-inline-link')
        check(len(inline)==len(m['contextualLinks']) and 1<=len(inline)<=3,prefix+'one to three grounded contextual links')
        for link in m['contextualLinks']:
            elements=soup.select('#section-'+str(link['section'])+' .topic-paragraph-unit')[link['paragraph']].select('a')
            check(any(a['href']==link['path'] and a.get_text()==link['phrase'] for a in elements),prefix+'context link remains in planned paragraph')
        check(len(soup.select('#related-pages .topic-related a'))==5,prefix+'same locality five siblings')
        check(soup.select_one('#questions').find_next_sibling('section')['id']=='related-pages',prefix+'siblings after FAQ')
        for a in soup.select('#related-pages .topic-related a'):
            s=next((x for x in manifest if x['path']==a['href']),None)
            check(s is not None and s['locality']==m['locality'] and s['centerId']==m['centerId'] and s['path']!=path,prefix+'sibling same locality and branch')
            check(bool(a.select('.topic-course-status')) == (not bool(s['confirmedGrades'])),prefix+'sibling course status truthful')
        first=soup.select_one('#related-pages .topic-related a')
        check(next(x for x in manifest if x['path']==first['href'])['stage']==m['stage'],prefix+'same school level ranked first')
        actual_same=soup.select('#same-branch-topics .topic-related a')
        expected_same=sorted([s for s in manifest if s['centerId']==m['centerId'] and s['topic']==m['topic'] and s['locality']!=m['locality']],key=lambda s:s['locality'])[:3]
        check([a['href'] for a in actual_same]==[s['path'] for s in expected_same],prefix+'other locality links limited to same branch and topic')
        documents.append(m['documentTitle']); descriptions.append(m['meta']); body_hashes.append(sha(norm(' '.join(seen)).encode()))
        for field,value in text_fields(m):
            if re.search(r'(?<![가-힣])원고 참고|[A-H]열|ROW_DATA|입력된 학교',value):
                source_tokens.append({'title':m['title'],'field':field,'text':value})
    check(len(set(documents))==len(records),'unique document titles')
    check(len(set(descriptions))==len(records),'unique descriptions')
    check(len(set(body_hashes))==len(records),'no exact whole-manuscript duplicates')
    check(not source_tokens,'no source-column references')
    for topic in TOPICS:
        file=DATA/'sources'/(topic+'.zip')
        parsed=load_archive(file,topic)
        check(sha(file.read_bytes())==sha((SOURCE/file.name).read_bytes()),topic+': original ZIP unchanged')
        original={m['title']:m for m in raw_records.values() if m['topic']==topic}
        check(all(p['sourceSha256']==original[p['title']]['sourceSha256'] for p in parsed),topic+': all 371 source CRC/hash identities')
    parents={m['parentPath'].strip('/')+'/index.html' for m in manifest}
    for file,digest in baseline['html'].items():
        if file not in parents:
            check(sha((ROOT/file).read_bytes())==digest,'existing HTML unchanged: '+file)
    # Archive must retain committed LF bytes instead of applying the Windows
    # checkout's core.autocrlf conversion. This does not change user Git config.
    archived=subprocess.check_output(['git','-c','core.autocrlf=false','archive','--format=tar',BASE_COMMIT,*sorted(parents)],cwd=ROOT)
    with tarfile.open(fileobj=BytesIO(archived)) as tar:
        for member in tar.getmembers():
            if not member.isfile():
                continue
            old=tar.extractfile(member).read()
            check(sha(old)==baseline['html'][member.name],member.name+': baseline commit')
            before=BeautifulSoup(old,'html.parser'); after=BeautifulSoup((ROOT/member.name).read_bytes(),'html.parser')
            for node in after.select('#neighborhood-pages, a[href="#neighborhood-pages"]'):
                node.decompose()
            check(norm(before.select_one('main').get_text(' ',strip=True))==norm(after.select_one('main').get_text(' ',strip=True)),member.name+': branch copy preserved outside child links')
            check(before.title.get_text()==after.title.get_text() and before.select_one('meta[name="description"]')['content']==after.select_one('meta[name="description"]')['content'],member.name+': branch metadata preserved')
    for file,digest in baseline['sourceData'].items():
        check(sha((ROOT/'tools/data/branches'/file).read_bytes())==digest,'immutable branch source '+file)
    for rep in json.loads((DATA/'representatives.json').read_text(encoding='utf8')):
        check(sha((ROOT/rep['src'].lstrip('/')).read_bytes())==rep['sha256']==sha(Path(rep['source']).read_bytes()),'representative original bytes '+rep['src'])
    urls=[unquote(n.text) for n in ET.parse(ROOT/'sitemap.xml').getroot().iter() if n.tag.endswith('}loc')]
    check(len(urls)==len(set(urls))==12214,'sitemap 12214 unique URLs')
    check(all(DOMAIN+m['path'] in urls for m in manifest),'all requested pages in sitemap')
    check(len(ET.parse(ROOT/'rss.xml').findall('.//item'))==55,'RSS 55 items')
    http=[]
    if args.base_url:
        check(urlsplit(args.base_url).hostname in ('127.0.0.1','localhost'),'local verification only')
        def fetch(m):
            with urlopen(args.base_url.rstrip('/')+quote(m['path'],safe='/'),timeout=30) as response:
                raw=response.read()
                return {'path':m['path'],'status':response.status,'hashMatches':sha(raw)==m['htmlSha256']}
        with ThreadPoolExecutor(max_workers=6) as pool:
            http=list(pool.map(fetch,manifest))
        check(all(x['status']==200 and x['hashMatches'] for x in http),'all 2226 local HTTP responses match generated files')
    result={'status':'PASS' if not errors else 'FAIL','checks':total,'errors':errors,'pages':len(records),'parents':len(parents),
            'faqCount':sum(len(m['faq']) for m in records),'sections':dict(Counter(section_counts)),
            'uniqueTitles':len(set(documents)),'uniqueDescriptions':len(set(descriptions)),'uniqueFullManuscripts':len(set(body_hashes)),
            'averageBodyCharacters':round(sum(sum(len(p) for s in m['sections'] for p in s['paragraphs']) for m in records)/len(records),1),
            'maxReadingParagraphCharacters':max(paragraphs),'qualifiedScopePages':sum(not m['confirmedGrades'] for m in records),
            'sourceColumnResiduals':source_tokens,'http':http,'interpretation':'Structural/source-preservation checks, not a search-engine rank or originality score.'}
    save(REPORTS/'audit.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('http','errors','sourceColumnResiduals')},ensure_ascii=False,indent=2))
    if errors:
        print(json.dumps({'errorCount':len(errors),'firstErrors':errors[:20]},ensure_ascii=False,indent=2))
    raise SystemExit(1 if errors else 0)


if __name__=='__main__':
    main()
