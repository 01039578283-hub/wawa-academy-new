"""Evidence-bounded reader aids, school-level cleanup and contextual navigation."""
from functools import lru_cache
import json
from pathlib import Path
import re
from branch_topic_manuscripts_site4 import norm, text_fields

STAGES={'초등학생':'elementary','중학생':'middle','고등학생':'high'}
GUIDES=(
    {'key':'errors','path':'/학습가이드/오답관리-루틴/', 'label':'오답을 복습으로 연결하는 방법',
     'phrases':('오답 노트','오답노트','오답 기록','오답 관리','재풀이','복습 기록','틀린 문제','복습 주기','오답 유형','틀린 문항')},
    {'key':'planning','path':'/학습가이드/시험기간-학습계획/', 'label':'시험기간 학습계획 세우기',
     'phrases':('주간 학습량','주간 계획','학습 계획','복습 계획','시험 준비','시험 대비','시간 배분')},
    {'key':'consultation','path':'/학습가이드/학부모상담-준비/', 'label':'학부모 상담 준비사항',
     'phrases':('상담 준비','상담 질문','상담 자료','준비 자료','상담 전에','질문 목록','상담을 준비')},
)


def sentences(value):
    return [x.strip() for x in re.split(r'(?<=[.!?])\s+',value) if x.strip()]


@lru_cache(maxsize=1)
def school_rows():
    return {r['neighborhood']:r for r in json.loads((Path(__file__).parent/'data/branch-topics/schools.json').read_text(encoding='utf8'))}


def school_aliases(name):
    forms={name,name.replace('여자','여')}
    forms|={re.sub(r'(초등학교|중학교|고등학교)$',lambda m:{'초등학교':'초','중학교':'중','고등학교':'고'}[m[0]],x) for x in list(forms)}
    forms|={x.removeprefix('서울') for x in list(forms) if x.startswith('서울')}
    return {x for x in forms if len(x)>=3}


def whole_pattern(words):
    return re.compile(r'(?<![가-힣])(?:'+'|'.join(re.escape(x) for x in sorted(words,key=lambda x:(-len(x),x)))+r')(?![가-힣])') if words else None


def polish_school_field(value,field,m):
    row=school_rows()[m['locality']]
    correct=row['targetSchools'][STAGES[m['stage']]]
    correct=[n for n in correct if not re.search(r'\[|모든|기타사립|특성화고$',n)]
    right={a:name for name in correct for a in school_aliases(name)}
    wrong={a for k,names in row['targetSchools'].items() if k!=STAGES[m['stage']] for name in names for a in school_aliases(name)}-right.keys()
    bad=whole_pattern(wrong); good=whole_pattern(right)
    result=[]
    for sentence in sentences(value):
        if bad and bad.search(sentence):
            # A previous-school or transition example is legitimate. Preserve it;
            # do not force every different-grade mention to vanish for a metric.
            transition=bool(re.search(r'이전|과거|시기의|학습 이력|학습 경험|초등 시기|중학교 시기|거쳤|다녔|진입|예비|동생|형제|졸업|전환|앞둔|진도 차이|진학을 (?:앞|준비)|중학교를 준비|고등학교를 준비',sentence))
            listing=bool(re.search(r'학교 (?:정보|목록)|(?:제공|제시|안내)된 학교|포함되어|제공되어|제시되어|함께 안내|등의 학교|학교명|참고할 학교|학교로 .*입력|안내된 .*가운데',sentence))
            # Mixed lists of current schools differ from prior-learning examples.
            listing = listing or bool(good and good.search(sentence) and re.search(r'[·,]|또는|관련 자료|자료를|시험 범위',sentence))
            if field.endswith('.heading') and not transition:
                sentence='재학 학교의 수업 자료로 상담 방향 정하기'
            elif listing and not transition:
                names='·'.join(correct[:3])
                sentence=(m['stage']+' 상담에 참고할 학교는 '+names+(' 등' if len(correct)>3 else '')+'입니다.') if names else m['stage']+' 상담은 현재 재학 학교의 교과서와 수업 자료를 기준으로 준비해 주세요.'
        if good:
            sentence=good.sub(lambda match:right[match[0]],sentence)
        sentence=sentence.replace('제공된 학교 정보','상담 참고 학교').replace('제시된 학교 정보','상담 참고 학교')
        result.append(sentence)
    return norm(' '.join(result))


def quick_scan(m):
    candidates=[]
    for i,section in enumerate(m['sections'],1):
        for j,p in enumerate(section['paragraphs']):
            for sentence in sentences(p):
                if not 35<=len(sentence)<=165: continue
                if re.match(r'다만|따라서|그러므로|그러나|반면|또한|이때|이렇게|이를|이러한|그런|즉 |이는|이 과정|이 기준|이 자료|예를 들어|반대로',sentence):continue
                if re.search(r'학교는 .*입니다\.|참고 학교|학교명|학교 목록|보장|단정|운영 여부|제휴|두 과목|한 과목|[‘’“”"?]',sentence):continue
                if re.search(r'이 순서|이 기준|이 자료|위 내용|앞서|세 종류로|다음과 같|이런 |이러한 |세 가지 질문',sentence):continue
                if re.match(r'첫째|둘째|셋째|넷째|다섯째|그래서|이후|대신',sentence):continue
                candidates.append({'section':i,'paragraph':j,'text':sentence})
    intents=(('먼저 확인할 점',r'진단|개념|원인|막히|정답|이해|최근|풀이'),
             ('상담 전에 살펴볼 점',r'준비|가져|모아|기록|정리'),
             ('복습할 때 확인할 점',r'복습|다시 풀|덮고|재작성|회상|재현|다시 확인'))
    result=[]; used=set(); used_sections=set()
    # Reserve specific preparation/review evidence before selecting the more
    # general diagnostic answer, so one sentence cannot fill the wrong role.
    for label,pattern in (intents[1],intents[2],intents[0]):
        available=[c for c in candidates if c['text'] not in used and re.search(pattern,c['text'])]
        if label=='상담 전에 살펴볼 점':
            available=[c for c in available if re.search(r'시험지|교과서|오답|노트|자료|필기|문장|풀이|종이|기록',c['text'])]
            available=[c for c in available if re.search(r'준비|가져|모아|챙겨|상담 전',c['text'])]
        elif label=='먼저 확인할 점':
            available=[c for c in available if not re.search(r'상담 전에|준비해|가져|모아',c['text'])]
        if not available:continue
        def rank(c):
            heading=m['sections'][c['section']-1]['heading']
            intent_heading={'먼저 확인할 점':r'진단|현재|실력|학습 흔적|개념','상담 전에 살펴볼 점':r'상담|준비|자료','복습할 때 확인할 점':r'복습|오답|피드백|누적'}[label]
            other='영어' if m['subject']=='수학' else '수학'
            return (other in c['text'],c['section'] in used_sections,not bool(re.search(intent_heading,heading)),not bool(re.search(r'보세요|준비|확인|기록|나누|설명|정리',c['text'])),
                    not 50<=len(c['text'])<=125, len(c['text'])>140, c['section'],c['paragraph'],len(c['text']))
        selected=min(available,key=rank)
        result.append({**selected,'label':label});used.add(selected['text']);used_sections.add(selected['section'])
    return sorted(result,key=lambda r:[i[0] for i in intents].index(r['label']))


def contextual_links(m):
    result=[]; chosen=set()
    for guide in GUIDES:
        candidates=[]
        for i,s in enumerate(m['sections'],1):
            for j,p in enumerate(s['paragraphs']):
                for priority,phrase in enumerate(guide['phrases']):
                    if phrase in p:
                        candidates.append(((i,j) in chosen, priority,i,j,phrase))
        if not candidates:continue
        _,_,i,j,phrase=min(candidates)
        chosen.add((i,j))
        result.append({'section':i,'paragraph':j,'phrase':phrase,'path':guide['path'],'label':guide['label'],'key':guide['key']})
    return result


def enrich(m):
    from branch_topic_reviewed_fixes_site4 import apply_reviewed_fixes
    changes=apply_reviewed_fixes(m)
    for field,old in list(text_fields(m)):
        new=polish_school_field(old,field,m)
        if old==new:continue
        node=m; keys=field.split('.')
        for key in keys[:-1]:node=node[int(key)] if isinstance(node,list) else node[key]
        key=int(keys[-1]) if isinstance(node,list) else keys[-1]
        node[key]=new
        changes.append({'field':field,'before':old,'after':new,'reason':'school-level context and reader-facing phrasing'})
    intro=m['intro']
    first=sentences(intro)[0]
    # Keep a complete sentence. There is no arbitrary character truncation and
    # no keyword replacement to manufacture different manuscripts.
    if first!=intro:
        m['intro']=first
        changes.append({'field':'intro','before':intro,'after':first,'reason':'concise complete first answer'})
    m['quickScan']=quick_scan(m)
    m['contextualLinks']=contextual_links(m)
    return changes
