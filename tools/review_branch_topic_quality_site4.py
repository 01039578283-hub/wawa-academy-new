"""Corpus measurements and reproducible samples, not search-engine scoring."""
from collections import Counter
import argparse
from copy import deepcopy
import json
from pathlib import Path
import re
from statistics import mean
from bs4 import BeautifulSoup
from branch_topic_manuscripts_site4 import TOPICS, norm, sha, text_fields
from prepare_branch_topics_site4 import DATA, REPORTS, save

ROOT=Path(__file__).resolve().parents[1]
REVIEW=REPORTS/'quality-review'


def sentences(text):
    # Sentence ends in Korean prose; quoted questions remain inside their sentence.
    return [x.strip() for x in re.split(r'(?<=[.!?])\s+',text) if x.strip()]


def aliases(name):
    result={name,name.replace('여자','여')}
    result|={re.sub(r'(초등학교|중학교|고등학교)$',lambda m:{'초등학교':'초','중학교':'중','고등학교':'고'}[m[0]],x) for x in list(result)}
    result|={x.removeprefix('서울') for x in list(result) if x.startswith('서울')}
    return {x for x in result if len(x)>=3}


def school_issues(m,row):
    stage={'초등학생':'elementary','중학생':'middle','고등학생':'high'}[m['stage']]
    wrong=set().union(*(aliases(n) for k,names in row['targetSchools'].items() if k!=stage for n in names))
    right=set().union(*(aliases(n) for n in row['targetSchools'][stage]))
    wrong-=right
    if not wrong:return []
    pattern=re.compile(r'(?<![가-힣])(?:'+ '|'.join(re.escape(x) for x in sorted(wrong,key=len,reverse=True))+r')(?![가-힣])')
    result=[]
    for field,value in text_fields(m):
        for sentence in sentences(value):
            hits=pattern.findall(sentence)
            if hits:result.append({'field':field,'sentence':sentence,'otherStageSchools':sorted(set(hits))})
    return result


def profile(records,label):
    schools={s['neighborhood']:s for s in json.loads((DATA/'schools.json').read_text(encoding='utf8'))}
    paragraphs=Counter()
    issue_rows=[]; grammar=[]; no_context=0; unresolved=0; rows=[]; selected=[]
    pattern=re.compile(r'(?<![가-힣])(?:원고(?:를 찾|를 준비| 참고)|입력(?:자료| 정보|에서|에는)|제공된 학교 정보|제시된 학교 정보)|[A-H]열|ROW_DATA')
    for m in records:
        for s in m['sections']:
            for p in s['paragraphs']:
                paragraphs[norm(p.replace(m['locality'],'{동네}'))]+=1
        found=school_issues(m,schools[m['locality']])
        if found: issue_rows.append({'path':m['path'],'title':m['title'],'findings':found})
        for field,value in text_fields(m):
            if pattern.search(value):grammar.append({'path':m['path'],'title':m['title'],'field':field,'text':value})
        soup=BeautifulSoup((ROOT/m['path'].strip('/')/'index.html').read_bytes(),'html.parser')
        graph=json.loads(soup.select_one('script[type="application/ld+json"]').string)['@graph']
        article=next(n for n in graph if n['@type']=='Article')
        typed={n.get('@id') for n in graph if n.get('@type')=='WebPageElement'}
        unresolved+=sum(x['@id'] not in typed for x in article.get('hasPart',[]))
        contextual=soup.select('.topic-paragraph-unit a[href^="/"]')
        no_context+=not contextual
        rows.append({'path':m['path'],'title':m['title'],'topic':m['topic'],'introChars':len(m['intro']),
                     'metaChars':len(m['meta']),'titleChars':len(m['documentTitle']),'bodyChars':sum(len(p) for s in m['sections'] for p in s['paragraphs']),
                     'otherStageSchoolMentions':len(found),'contextualLinks':len(contextual),'hasAbstract':bool(article.get('abstract')),
                     'hasImageObject':isinstance(article.get('image'),dict),'hasQuickScan':bool(soup.select('.topic-quick-scan'))})
    for topic in TOPICS:
        group=[m for m in records if m['topic']==topic]
        picks=[next(m for m in group if m['locality']=='명일동'),max(group,key=lambda m:len(m['intro'])),
               max(group,key=lambda m:len(m['meta'])),next((m for m in group if not m['confirmedGrades']),group[-1]),group[len(group)//2]]
        selected.extend(deepcopy(m) for m in {m['path']:m for m in picks}.values())
    report={'label':label,'pages':len(rows),'topics':dict(Counter(m['topic'] for m in records)),
            'intro':{'average':round(mean(r['introChars'] for r in rows),1),'max':max(r['introChars'] for r in rows),'over200':sum(r['introChars']>200 for r in rows)},
            'meta':{'average':round(mean(r['metaChars'] for r in rows),1),'max':max(r['metaChars'] for r in rows),'over160':sum(r['metaChars']>160 for r in rows)},
            'titles':{'max':max(r['titleChars'] for r in rows),'over60':sum(r['titleChars']>60 for r in rows)},
            'otherStageSchoolPages':len(issue_rows),'sourceStyleFields':len(grammar),'pagesWithoutContextualLinks':no_context,
            'untypedArticleParts':unresolved,'abstractPages':sum(r['hasAbstract'] for r in rows),'imageObjectPages':sum(r['hasImageObject'] for r in rows),
            'quickScanPages':sum(r['hasQuickScan'] for r in rows),
            'duplicateParagraphOccurrences':sum(count-1 for count in paragraphs.values() if count>1),
            'mostRepeatedParagraphs':paragraphs.most_common(10),'schoolIssues':issue_rows,'sourceStyle':grammar,'rows':rows,
            'notes':['Length thresholds are editorial review flags, not Naver indexing cutoffs.','Other-stage school matches are review candidates, not proof of incorrect schools.','Unique wording is not proof of unique meaning or a search ranking guarantee.']}
    save(REVIEW/(label+'.json'),report)
    save(REVIEW/(label+'-samples.json'),selected)
    return report


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--label',choices=['before','after'],required=True);args=parser.parse_args()
    records=json.loads((DATA/'display-manuscripts.json').read_text(encoding='utf8'))
    if args.label=='before':
        before=DATA/'before-quality-review.json'
        if not before.exists():save(before,records)
        else:assert sha(before.read_bytes())==sha((DATA/'display-manuscripts.json').read_bytes()),'Do not overwrite the original before snapshot'
    r=profile(records,args.label)
    print(json.dumps({k:v for k,v in r.items() if k not in ('rows','sourceStyle','schoolIssues','mostRepeatedParagraphs')},ensure_ascii=False,indent=2))
    print(json.dumps({'schoolSamples':r['schoolIssues'][:3],'styleSamples':r['sourceStyle'][:3]},ensure_ascii=False,indent=2))


if __name__=='__main__': main()
