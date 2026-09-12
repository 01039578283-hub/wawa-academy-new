"""Narrow reader-facing cleanup. Source attachments are never rewritten."""
from copy import deepcopy
import re
from branch_topic_manuscripts_site4 import text_fields, norm

# Complete source-context phrases, not global replacements of '입력' (functions,
# planner input) or '원고' (student presentations, school names such as 세원고).
PHRASES = (
    ('제공된 수업학교 정보', '상담 참고 학교'),
    ('입력 정보만으로', '이 안내만으로'),
    ('입력 정보에 없으므로', '이 안내에서 확인되지 않았으므로'),
    ('원고를 준비하거나 상담을 받을 때', '상담을 준비할 때'),
    ('원고를 준비하는 보호자 입장에서는', '상담을 준비하는 보호자는'),
    ('원고를 준비하는 가정에서는', '상담을 준비하는 가정에서는'),
    ('D에 제시된', '안내된'),
    ('원고 참고 소재에 영어와 수학이 함께 포함된 만큼', '영어와 수학을 함께 고려한다면'),
    ('원고 참고 소재에 영어와 수학이 함께 제시된 경우에도', '영어와 수학을 함께 고려하더라도'),
    ('원고를 찾는 과정에서', '학습 정보를 찾는 과정에서'),
    ('원고를 준비하는 과정에서', '상담을 준비하는 과정에서'),
    ('원고를 준비할 때', '상담을 준비할 때'),
    ('원고를 준비하는 학부모', '상담을 준비하는 학부모'),
    ('원고를 준비하며', '상담을 준비하며'),
    ('원고를 준비하면서', '상담을 준비하면서'),
    ('원고를 찾는 가정', '학습 정보를 찾는 가정'),
    ('원고를 찾는 보호자', '학습 정보를 찾는 보호자'),
    ('원고를 찾는 학부모', '학습 정보를 찾는 학부모'),
    ('원고를 알아보는 과정에서', '학습 정보를 알아보는 과정에서'),
    ('원고에서 함께 확인할 키워드', '상담에서 함께 확인할 항목'),
    ('원고를 참고할 때 ‘영어 수학’', '학습 정보를 살펴보며 ‘영어 수학’'),
    ('이 원고에서', '이 안내에서'), ('이 원고는', '이 안내는'),
    ('이 원고에', '이 안내에'),
    ('D열에 제공된', '안내된'), ('D열에 제시된', '안내된'),
    ('D열의 학교', '안내된 학교'), ('D열에 학교 정보가', '이 안내에 학교 정보가'),
    ('D열에 학교명이', '이 안내에 학교명이'), ('E열의 주소', '안내된 주소'),
    ('E열에는', '이 안내에는'),
    ('입력에 제시된', '안내된'), ('입력에 제공된', '안내된'),
    ('입력에 포함된', '안내된'), ('입력된 학교', '안내된 학교'),
    ('입력에 함께 제시된', '함께 안내된'),
    ('입력된 주소', '안내된 주소'), ('입력된 참고 키워드', '상담 참고 항목'),
    ('입력된 원고 참고 키워드', '상담 참고 항목'),
    ('원고 참고 키워드', '상담 참고 항목'),
    ('이번 입력에는', '이 안내에는'), ('이 입력에서', '이 안내에서'),
    ('입력에서 확인되지 않은', '이 안내에서 확인되지 않은'),
    ('입력에서 확인되지 않았으므로', '이 안내에서 확인되지 않았으므로'),
    ('입력에서 확정되지 않은', '이 안내에서 확정되지 않은'),
    ('입력에 제공되지 않은', '이 안내에서 확인되지 않은'),
    ('입력에 없는', '이 안내에서 확인되지 않은'),
    ('입력에 없으므로', '이 안내에서 확인되지 않았으므로'),
    ('입력만으로', '이 안내만으로'), ('입력 자료만으로', '이 안내만으로'),
    ('입력 자료', '안내 자료'), ('참고 키워드', '상담 참고 항목'),
    ('학교 정보로 입력된', '참고 학교로 안내된'),
    ('학교명이 입력되어', '학교명이 안내되어'),
    ('학교가 입력되어', '학교가 안내되어'),
)


def clean_copy(value):
    # These phrases describe the manuscript's input columns, not a course fact.
    value = re.sub(r'(?:입력된 |입력에 제시된 |입력에 제공된 )?원고 참고 키워드(?:에|로|가) '
                   r'영어(?:와 | )수학(?:이|으로) 함께 제시된 (?:경우라면|경우라도|경우에도|경우처럼|경우)',
                   '영어와 수학을 함께 고려한다면', value)
    value = re.sub(r'(?:입력된 |입력에 제시된 )?원고 참고 키워드(?:에|로) '
                   r'영어(?:와 | )수학이 함께 제시된 만큼', '영어와 수학을 함께 고려할 때는', value)
    value = re.sub(r'원고 참고 키워드로 (?:함께 )?제시된 [‘\']?영어(?:와 |[· ])수학[’\']?을 함께',
                   '영어와 수학을 함께', value)
    value = re.sub(r'(?:입력된 |입력에 제시된 )?원고 참고 키워드로 제시된 [‘\']?영어(?:와 | )수학[’\']?은',
                   '영어와 수학은', value)
    for before, after in PHRASES:
        if before.startswith('이 원고'):
            value = re.sub(r'(?<![가-힣])' + re.escape(before), after, value)
        else:
            value = value.replace(before, after)
    value = re.sub(r'(?<![가-힣])입력된 (?=정보|자료|내용|지역|위치|검색어|검색 맥락)', '안내된 ', value)
    value = re.sub(r'(?<![가-힣])입력에 (?=학교|영어|수학|있는|제시되지)', '안내에 ', value)
    value = re.sub(r'(?<![가-힣])([수과]학)를\b', r'\1을', value)
    return norm(value)


def prepare(raw):
    result = deepcopy(raw)
    changes = []
    for path, old in list(text_fields(result)):
        value = clean_copy(old)
        if old == value:
            continue
        keys = path.split('.')
        node = result
        for key in keys[:-1]:
            node = node[int(key)] if isinstance(node, list) else node[key]
        key = int(keys[-1]) if isinstance(node, list) else keys[-1]
        node[key] = value
        changes.append({'field':path,'before':old,'after':value})
    assert result['title'] == raw['title'] and result['path'] == raw['path']
    from branch_topic_enrichment_site4 import enrich
    changes.extend(enrich(result))
    # A title suffix is a complete, visible subsection heading, never keyword padding.
    headings = [s['heading'] for s in result['sections']]
    suffix = next((h for h in headings if len(h)<=36), '')
    result['documentTitle'] = result['title'] + (' | ' + suffix if suffix else '')
    return result, changes


def reading_chunks(value, target=190):
    sentences = re.split(r'(?<=[.!?])\s+', value)
    result = []
    for sentence in sentences:
        if result and len(result[-1]) + len(sentence) + 1 <= target:
            result[-1] += ' ' + sentence
        else:
            result.append(sentence)
    assert norm(' '.join(result)) == norm(value)
    return result
