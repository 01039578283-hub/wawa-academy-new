"""Generate six x 371 school-level articles locally, then refresh parent links."""
from __future__ import annotations
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
import re
import shutil
import subprocess
from urllib.parse import quote
from xml.sax.saxutils import escape as xml_escape
from PIL import Image
from bs4 import BeautifulSoup
from branch_site4_support import ROOT, DOMAIN, page
from branch_templates_site4 import (base_graph, branch_path, primary_media, panel, paragraph, button, esc, url, subject_summary)
from branch_topic_manuscripts_site4 import TOPICS, sha, norm
from branch_topic_editorial_site4 import prepare, reading_chunks
from prepare_branch_topics_site4 import DATA, REPORTS, REFERENCE, save
from branch_verified_facts_site4 import load_reviewed_snapshot, recorded_grades, pending_note, practice_for, practice_basis
from branch_reviews_site4 import reviews_for, review_cards

DATE = '2026-09-13'
PREFIX = {'초등학생':'초','중학생':'중','고등학생':'고'}
SCHOOL_KEY = {'초등학생':'elementary','중학생':'middle','고등학생':'high'}


def representative_pool():
    source_manifest = REFERENCE / 'assets/representative/manifest.json'
    manifest = json.loads(source_manifest.read_text(encoding='utf8'))
    common = ROOT.parent / '참고자료/공통자료/대표이미지'
    records = []
    for item in manifest['images']:
        source = common / item['source_name']
        raw = source.read_bytes()
        assert sha(raw) == item['sha256'], source
        dest = ROOT / 'assets/branch-topic-representative' / item['asset_name']
        assert dest.resolve().is_relative_to((ROOT / 'assets/branch-topic-representative').resolve())
        if dest.exists():
            assert sha(dest.read_bytes()) == item['sha256'], dest
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest)
        with Image.open(source) as im:
            width, height = im.size
        records.append({'src':'/'+dest.relative_to(ROOT).as_posix(),'source':str(source),'sha256':item['sha256'],'width':width,'height':height})
    assert len(records) == 371 and len({r['src'] for r in records}) == len(records)
    save(DATA / 'representatives.json', records)
    return records


def copy_prose(paragraphs, links=()):
    output=[]
    for j,p in enumerate(paragraphs):
        chunks=[esc(x) for x in reading_chunks(p)]
        for link in (x for x in links if x['paragraph']==j):
            phrase=esc(link['phrase'])
            for i,chunk in enumerate(chunks):
                if phrase in chunk:
                    chunks[i]=chunk.replace(phrase,'<a class="topic-inline-link" href="'+esc(link['path'])+'" title="'+esc(link['label'])+'">'+phrase+'</a>',1)
                    break
        output.append('<div class="topic-paragraph-unit">'+''.join('<p class="topic-copy">'+x+'</p>' for x in chunks)+'</div>')
    return ''.join(output)


def school_names(row, stage):
    names = []
    for value in row.get('targetSchools', {}).get(SCHOOL_KEY[stage], []):
        value = re.sub(r'\[[^\]]*(?:후보|확인|미확인|통계)[^\]]*\]', '', value).strip()
        if value and not re.search(r'모든|기타사립|특성화고$', value):
            names.append(value)
    return list(dict.fromkeys(names))


def render(m, c, ref, school_row, rep, siblings):
    path, parent, title = m['path'], m['parentPath'], m['title']
    crumbs = [('홈','/'),('지점안내','/지점안내/'),(c['region']['province'],'/지점안내/'+c['region']['province']+'/'),
              (c['sourceCenterName'],parent),(title,path)]
    graph = base_graph(m['documentTitle'],m['meta'],path,crumbs)
    canonical, center_id = url(path), url(parent)+'#center'
    graph[1].update(isPartOf={'@id':url(parent)+'#webpage'}, mainEntity={'@id':canonical+'#article'}, about={'@id':center_id}, dateModified=DATE)
    org = {'@type':'EducationalOrganization','@id':center_id,'name':c['displayName'],'url':url(parent),
           'address':{'@type':'PostalAddress','addressCountry':'KR','addressRegion':c['region']['province'],
                      'addressLocality':c['region']['administrativeAreaText']}, 'mainEntityOfPage':{'@id':url(parent)+'#webpage'}}
    if c.get('addressPrecision') != 'neighborhood':
        org['address']['streetAddress'] = c['address']
    if c['registeredAcademyName']:
        org['legalName'] = c['registeredAcademyName']
    if c['registrationNumber']:
        org['identifier'] = c['registrationNumber']
    graph.append(org)
    scope = subject_summary(c,m['subject'],c['subjects'][m['subject']],ref)
    detail = ref.get('operations',{}).get('subjectDisplay',{}).get(m['subject'],{}).get('detail','')
    documented = practice_for(c['id'], m['subject'], m['stage']) if m['confirmedGrades'] else None
    student_reviews = reviews_for(c['id'], m['subject'], m['stage']) if m['confirmedGrades'] else []
    article = {'@type':'Article','@id':canonical+'#article','url':canonical,'headline':title,'description':m['meta'],
               'inLanguage':'ko-KR','educationalLevel':m['stage'],'dateModified':DATE,'mainEntityOfPage':{'@id':canonical+'#webpage'},
               'isPartOf':{'@id':url(parent)+'#webpage'},'about':[{'@id':center_id},{'@type':'Thing','name':m['stage']+' '+m['subject']+' 학습'}],
               'abstract':m['intro'],
               'articleSection':[m['stage']+' 학습 안내',m['subject']+' 학습코칭'],
               'image':{'@type':'ImageObject','@id':canonical+'#article-image','contentUrl':DOMAIN+ref['primaryMedia']['body']['src'],
                        'caption':title+' 본문','width':ref['primaryMedia']['body']['width'],'height':ref['primaryMedia']['body']['height']},
               'hasPart':[{'@id':canonical+'#section-'+str(i)} for i in range(1,len(m['sections'])+1)]}
    if m['confirmedGrades']:
        sid = canonical+'#service'
        graph.append({'@type':'Service','@id':sid,'name':c['displayName']+' '+m['stage']+' '+m['subject']+' 수업 안내',
                      'serviceType':m['subject']+' 학습코칭','provider':{'@id':center_id},
                      'description':'안내된 학년: '+', '.join(m['confirmedGrades'])+'. 세부 과정과 현재 시간표는 상담에서 확인해 주세요.'+((' '+detail) if detail else ''),
                      'areaServed':{'@type':'Place','name':m['locality']},'mainEntityOfPage':{'@id':canonical+'#webpage'}})
        article['about'].append({'@id':sid})
    graph.append(article)
    if student_reviews:
        article['citation'] = [{'@type':'CreativeWork','name':r.get('originalTitle',r['title']),'url':r['sourceUrl']} for r in student_reviews]
    body = '<section class="branch-hero topic-hero"><p class="branch-eyebrow">'+esc(c['sourceCenterName']+' · '+m['stage']+' '+m['subject']+' 학습 안내')+'</p><h1>'+esc(title)+'</h1>'
    body += copy_prose([m['intro']])
    body += '<div class="topic-center-summary"><p><strong>상담 지점</strong> <a href="'+esc(parent)+'">'+esc(c['displayName'])+'</a></p><p><strong>'+esc(m['subject'])+' 학년 안내</strong> '+esc(scope)+'</p></div>'
    if not m['confirmedGrades']:
        body += paragraph(m['stage']+' '+m['subject']+' 과정의 개설 학년을 먼저 확인해 주세요. 아래 글은 학습 준비 안내이며, 해당 수업이 개설되어 있다는 뜻은 아닙니다.','topic-scope-notice')
    elif len(m['confirmedGrades']) < (6 if m['stage']=='초등학생' else 3):
        body += paragraph('이 학교급에서 안내된 학년은 '+', '.join(m['confirmedGrades'])+'입니다. 그 외 학년과 세부 과정은 따로 문의해 주세요.','topic-scope-notice')
    if pending_note(m):
        body += paragraph(pending_note(m),'topic-scope-notice')
    if ref.get('operations',{}).get('subjectDisplay',{}).get(m['subject'],{}).get('status') == 'recorded_baseline_extension_pending':
        body += paragraph(detail+' 자료 확인 기준은 2026년 9월 제공 정보이며, 현재 시간표와 모집 상태를 직접 확인한 것은 아닙니다.','topic-scope-notice')
    body += '<div class="branch-actions topic-reading-shortcuts">'+button('#section-1','본문 바로 읽기')+button('#article-toc','글 목차',True)+button('#center-info','지점 정보',True)+'</div></section>'
    if m['quickScan']:
        body += '<section class="topic-quick-scan" id="quick-answer"><h2>먼저 확인할 핵심 내용</h2><ul>'
        for item in m['quickScan']:
            body += '<li><a href="#section-'+str(item['section'])+'"><span class="topic-quick-label">'+esc(item['label'])+' <span aria-hidden="true">↗</span></span><span class="topic-quick-answer">'+esc(item['text'])+'</span></a></li>'
        body += '</ul></section>'
    media = primary_media(dict(c,displayName=title),ref)
    rep_html = '<img class="topic-representative" style="display:none;" src="'+esc(rep['src'])+'" width="'+str(rep['width'])+'" height="'+str(rep['height'])+'" alt="'+esc(title+' 와와학원 대표')+'" loading="lazy" decoding="async">'
    marker = '<div class="branch-primary-media" aria-label="학원 수업 및 위치 안내">'
    assert media.startswith(marker)
    body += media.replace(marker,marker+rep_html,1)
    names = school_names(school_row,m['stage'])
    anchors = [('center-info','상담할 지점 확인')] + [('section-'+str(i),s['heading']) for i,s in enumerate(m['sections'],1)]
    if documented:
        anchors.insert(1, ('documented-learning','지점의 수업·피드백 안내'))
    if student_reviews:
        anchors.insert(2 if documented else 1, ('student-reviews','학생의 학습 경험'))
    if names:
        anchors += [('schools','학교 자료 준비')]
    anchors += [('questions','자주 묻는 질문'),('related-pages','같은 동네의 다른 학습 안내'),('consultation-example','상담 준비 예시')]
    body += '<nav id="article-toc" class="topic-toc" aria-label="글 목차"><h2>이 글의 목차</h2><ol>'+''.join('<li><a href="#'+key+'">'+esc(label)+'</a></li>' for key,label in anchors)+'</ol></nav><div class="topic-content">'
    info = '<dl class="branch-info"><div><dt>상담 지점</dt><dd><a href="'+esc(parent)+'">'+esc(c['displayName'])+'</a></dd></div><div><dt>'+('안내 위치' if c.get('addressPrecision')=='neighborhood' else '주소')+'</dt><dd>'+esc(c['address'])+'</dd></div><div><dt>'+esc(m['subject'])+' 학년</dt><dd>'+esc(scope)+'</dd></div></dl>'
    if detail:
        info += paragraph(detail)
    info += paragraph('아래 본문은 학생의 학습과 상담을 준비하는 정보입니다. 글에 언급된 방법·교재·일정의 실제 운영 여부는 지점에서 확인해 주세요.','branch-small')
    if c.get('addressPrecision')=='neighborhood':
        info += paragraph('현재 위치는 동네 단위 안내입니다. 방문할 도로명 주소·건물·층수는 상담에서 먼저 확인해 주세요.','topic-scope-notice')
    info += '<div class="branch-actions">'+button(parent+'#tuition','교육비 확인',True)+button(parent+'#directions','지점 위치 확인',True)+'</div>'
    body += panel('center-info',c['sourceCenterName']+'에서 상담하기',info)
    if documented:
        item = documented['practices'][0]
        evidence_body = paragraph(item['text'])
        evidence_body += paragraph(practice_basis(documented)+'에 기재된 운영 방식입니다. 개별 학생의 실제 성과 사례나 모든 학년에서의 동일한 운영을 뜻하지 않습니다. 적용 과정과 현재 진행 방식은 상담에서 확인해 주세요.','branch-small')
        evidence_body += '<div class="branch-actions">'+button(parent+'#verified-learning',c['sourceCenterName']+'의 수업·피드백 안내 더 보기',True)+'</div>'
        body += panel('documented-learning',c['sourceCenterName']+'의 '+item['title'],evidence_body)
    if student_reviews:
        intro = paragraph('공식 홈페이지에 공개된 '+c['sourceCenterName']+'의 '+m['stage']+' '+m['subject']+' 관련 후기입니다. 본문의 일반 학습 안내와 구분해 실제 학생이 전한 경험을 살펴보세요.')
        body += panel('student-reviews',c['sourceCenterName']+' 학생이 전한 학습 경험',intro+review_cards(student_reviews,parent))
    for i,s in enumerate(m['sections'],1):
        body += panel('section-'+str(i),s['heading'],copy_prose(s['paragraphs'],[x for x in m['contextualLinks'] if x['section']==i]))
    if names:
        school_body = paragraph('재학 학교의 교과서, 학교에서 받은 자료와 평가 일정을 준비해 보세요. 아래 목록은 상담 참고용이며 학교 제휴나 전용반 운영을 뜻하지 않습니다.')
        school_body += '<ul class="topic-school-list">'+''.join('<li>'+esc(n)+'</li>' for n in names)+'</ul>'
        body += panel('schools',m['locality']+' '+m['stage']+' 학교 자료 준비',school_body)
    faq = '<div class="branch-faq">'+''.join('<details><summary>'+esc(f['question'])+'</summary>'+paragraph(f['answer'])+'</details>' for f in m['faq'])+'</div>'
    body += panel('questions','자주 묻는 질문',faq)
    graph.append({'@type':'FAQPage','@id':canonical+'#questions','mainEntity':[{'@type':'Question','name':f['question'],'acceptedAnswer':{'@type':'Answer','text':f['answer']}} for f in m['faq']]})
    related = [s for s in siblings if s['locality']==m['locality'] and s['path']!=path]
    related.sort(key=lambda s:(s['stage']!=m['stage'],s['subject']!=m['subject'],TOPICS.index(s['topic'])))
    related_html=''
    related_groups=[('같은 학교급의 다른 과목',[s for s in related if s['stage']==m['stage']]),
                    ('같은 과목의 다른 학교급',[s for s in related if s['stage']!=m['stage'] and s['subject']==m['subject']]),
                    ('다른 학교급·과목도 살펴보기',[s for s in related if s['stage']!=m['stage'] and s['subject']!=m['subject']])]
    def related_card(s):
        note='<small class="topic-course-status">개설 학년 확인 필요</small>' if not s['confirmedGrades'] else ''
        return '<a href="'+esc(s['path'])+'"><span>'+esc(s['title'])+note+'</span><span aria-hidden="true">→</span></a>'
    for label,items in related_groups:
        related_html += '<h3 class="topic-related-heading">'+esc(label)+'</h3><div class="topic-related">'+''.join(related_card(s) for s in items)+'</div>'
    related_html += '<div class="branch-actions">'+button(parent+'#neighborhood-pages','이 지점의 전체 동네 안내',True)+'</div>'
    body += panel('related-pages',m['locality']+'의 다른 학습 안내',related_html)
    graph.append({'@type':'ItemList','@id':canonical+'#related-pages','numberOfItems':len(related),'itemListElement':[{'@type':'ListItem','position':i,'name':s['title'],'url':url(s['path'])} for i,s in enumerate(related,1)]})
    other_localities=sorted([s for s in siblings if s['topic']==m['topic'] and s['locality']!=m['locality']],key=lambda s:s['locality'])[:3]
    if other_localities:
        nearby=paragraph(c['sourceCenterName']+'에 연결된 다른 동네의 '+m['topic']+' 안내입니다. 실제 수강 가능 범위는 각 안내의 학년·조건을 확인해 주세요.')
        nearby += '<div class="topic-related">'+''.join(related_card(s) for s in other_localities)+'</div>'
        body += panel('same-branch-topics','같은 지점의 다른 동네 안내',nearby)
        graph.append({'@type':'ItemList','@id':canonical+'#same-branch-topics','numberOfItems':len(other_localities),
                      'itemListElement':[{'@type':'ListItem','position':i,'name':s['title'],'url':url(s['path'])} for i,s in enumerate(other_localities,1)]})
    example = paragraph('실제 수강 후기나 성과 사례가 아닌, 학부모 관점의 가상 상담 준비 예시입니다.','branch-small')+copy_prose(m['cases'])
    body += panel('consultation-example','학부모 관점의 상담 준비 예시',example)
    body += panel('contact','상담에 필요한 내용을 정리해 보세요',paragraph(c['sourceCenterName']+'에서 '+title+' 안내를 보고 문의한다고 말씀해 주세요. 현재 학년과 희망 과목, 가능한 요일을 함께 알려주시면 됩니다.')+'<div class="branch-actions">'+button('tel:01039578283','전화 상담')+button('/상담문의/','상담 준비사항',True)+'</div>')
    body += '</div>'
    html = page(m['documentTitle'],m['meta'],path,crumbs,body,graph,detail=True)
    html = html.replace('class="branch-page branch-detail-page"','class="branch-page branch-detail-page branch-topic-page"')
    html = html.replace('</head>','<link rel="stylesheet" href="/assets/branch-topics-site4.css?v=20260913-2">\n</head>')
    html = html.replace('<meta property="og:type" content="website">','<meta property="og:type" content="article">')
    # Social previews use the first actual visible body image, not the hidden representative.
    body_src = DOMAIN + ref['primaryMedia']['body']['src']
    html = re.sub(r'(<meta property="og:image" content=")[^"]+',lambda x:x[1]+body_src,html)
    html = html.replace('</head>','<meta property="og:image:alt" content="'+esc(title+' 본문')+'">\n</head>')
    return re.sub(r'[ \t]+(?=\r?$)','',html,flags=re.M)


def main():
    records = json.loads((DATA/'manuscripts.json').read_text(encoding='utf8'))
    original = load_reviewed_snapshot()
    centers = {c['id']:c for c in original['centers']}
    schools = {s['neighborhood']:s for s in json.loads((DATA/'schools.json').read_text(encoding='utf8'))}
    baseline_file = DATA/'site-baseline.json'
    if not baseline_file.exists():
        assert not (DATA/'manifest.json').exists()
        public = [p for p in ROOT.rglob('*.html') if not {'.git','.vercel','node_modules','tools'}.intersection(p.relative_to(ROOT).parts)]
        assert len(public)==9988
        save(baseline_file,{'html':{p.relative_to(ROOT).as_posix():sha(p.read_bytes()) for p in public},
                            'sitemap':(ROOT/'sitemap.xml').read_text(encoding='utf8'),'rss':(ROOT/'rss.xml').read_text(encoding='utf8'),
                            'sourceData':{p.name:sha(p.read_bytes()) for p in (ROOT/'tools/data/branches').glob('*.json')}})
    pool = representative_pool()
    old_manifest = json.loads((DATA/'manifest.json').read_text(encoding='utf8')) if (DATA/'manifest.json').exists() else {'pages':[]}
    old = {m['path']:m for m in old_manifest['pages']}
    edits, output, rendered, groups = [], [], [], defaultdict(list)
    for raw in records:
        m, changes = prepare(raw)
        m['confirmedGrades'] = recorded_grades(m)
        edits.extend({'title':m['title'],**change} for change in changes)
        groups[m['centerId']].append(m)
        output.append(m)
    for m in output:
        c=centers[m['centerId']]
        rep=pool[int(sha(m['path'].encode())[:12],16)%len(pool)]
        html=render(m,c,original['reference'][c['id']],schools[m['locality']],rep,groups[c['id']])
        dest=ROOT/m['path'].strip('/')/'index.html'
        assert dest.resolve().is_relative_to((ROOT/'지점안내').resolve())
        if dest.exists():
            assert m['path'] in old and sha(dest.read_bytes())==old[m['path']]['htmlSha256'], 'Preserve existing edits: '+str(dest)
        rendered.append((dest,html))
        m['representative']=rep
        m['htmlSha256']=sha(html.encode())
    save(DATA/'display-manuscripts.json',output)
    for dest,html in rendered:
        raw=html.encode()
        if not dest.exists() or dest.read_bytes()!=raw:
            dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_bytes(raw)
    fields=('path','parentPath','centerId','title','documentTitle','locality','topic','subject','stage','confirmedGrades','representative','sourceMember','sourceSha256','sourceArchiveSha256','htmlSha256')
    manifest={'version':1,'date':DATE,'pages':[{k:m[k] for k in fields} for m in output]}
    save(DATA/'manifest.json',manifest)
    save(REPORTS/'editorial-changes.json',edits)
    baseline=json.loads(baseline_file.read_text(encoding='utf8'))
    extra=''.join('  <url><loc>'+DOMAIN+quote(m['path'],safe='/')+'</loc><lastmod>'+DATE+'</lastmod></url>\n' for m in output)
    (ROOT/'sitemap.xml').write_bytes(baseline['sitemap'].replace('</urlset>',extra+'</urlset>').encode())
    samples=[next(m for m in output if m['topic']==topic and m['locality']=='명일동') for topic in TOPICS]
    rss=''.join('<item><title>'+xml_escape(m['documentTitle'])+'</title><link>'+url(m['path'])+'</link><guid isPermaLink="true">'+url(m['path'])+'</guid><description>'+xml_escape(m['meta'])+'</description><pubDate>Sun, 13 Sep 2026 09:00:00 +0900</pubDate></item>' for m in samples)
    (ROOT/'rss.xml').write_bytes(baseline['rss'].replace('</channel>',rss+'</channel>').encode())
    subprocess.run(['python','-X','utf8',str(ROOT/'tools/generate_branch_pages_site4.py'),'--pages-only'],cwd=ROOT,check=True)
    save(REPORTS/'generation.json',{'status':'LOCAL_ONLY','pages':len(output),'perTopic':dict(Counter(m['topic'] for m in output)),
         'parentBranches':len(groups),'representativePool':len(pool),'assignedRepresentatives':len({m['representative']['src'] for m in output}),
         'qualifiedScopePages':sum(not m['confirmedGrades'] for m in output),'editorialFieldChanges':len(edits),
         'sitemapUrls':9988+len(output),'rssItems':55,'deployment':'NOT REQUESTED / NOT DEPLOYED'})
    print(json.dumps({'pages':len(output),'parentBranches':len(groups),'editorialFields':len(edits),'deployment':'LOCAL ONLY'},ensure_ascii=False))


if __name__=='__main__':
    main()
