"""Focused regression tests; no files or network are mutated."""
import re
import unittest
from title_suffix_rules import HABIT_TOPICS
from personalize_title_suffixes import (replace_titles, title_of, masked, learning_blocks,
    content_candidates, plan)


class TitleTests(unittest.TestCase):
    def test_only_three_values_change(self):
        s='<title>old</title>\r\n<meta property="og:title" content="old">\r\n<meta name="twitter:title" content="old"><h1>keep</h1><script type="application/ld+json">{"name":"old"}</script>'
        updated=replace_titles(s, '명일동 수학 | 조건 & "풀이"')
        self.assertEqual(masked(s),masked(updated))
        self.assertEqual(title_of(updated),'명일동 수학 | 조건 & "풀이"')
        self.assertEqual(updated.count('\r\n'),2)
        self.assertIn('{"name":"old"}',updated)
        self.assertIn('<h1>keep</h1>',updated)

    def test_missing_and_duplicate_titles_rejected(self):
        for s in ('<main/>','<title>a</title><title>b</title>'):
            with self.assertRaises(ValueError):replace_titles(s,'new')

    def test_nested_copy_not_faq_nav_or_hidden(self):
        s='<section class="section seo-geo-section"><article class="geo-summary-panel"><h2>개념과 계산 과정을 살펴보는 방법</h2><p>계산 과정에서 식을 세우지 못하는 지점을 확인합니다.</p><p hidden>가짜 문장으로 검산 습관을 조작합니다.</p><div class="intent-counterpart"><p>다른 페이지의 문장 구조는 제외합니다.</p></div></article></section><section class="faq-section"><p>FAQ의 문장 구조 이해는 제외합니다.</p></section><nav><p>내비게이션의 어휘 복습은 제외합니다.</p></nav>'
        blocks=learning_blocks(s,'detail')
        self.assertTrue(any('식을 세우지' in x for x,_ in blocks))
        self.assertFalse(any('가짜' in x or '다른 페이지' in x or 'FAQ' in x or '내비게이션' in x for x,_ in blocks))

    def page(self,category,subject,text):
        return dict(category=category,subject=subject,younger=any(x in category for x in ('초등','중등','중학생')),blocks=[(text,5)])

    def test_grade_and_subject_boundaries(self):
        text='수능형 접근과 내신·모의고사 구분보다 먼저 검산과 문법의 문장 적용, 문장제 해석을 확인합니다.'
        candidates=content_candidates(self.page('초등수학학원','math',text))
        self.assertTrue(candidates)
        self.assertFalse(any(c['subject']=='english' or re.search('수능|모의고사|내신',c['label']) for c in candidates))
        candidates=content_candidates(self.page('영어전문학원','english',text))
        self.assertFalse(any(c['subject']=='math' for c in candidates))

    def test_application_order_is_not_sentence_reordering(self):
        candidates=content_candidates(self.page('영어전문학원','english','문법 개념은 말로 설명하지만 새로운 문장에서는 적용 순서를 놓치는 학생입니다.'))
        self.assertNotIn('문장 배열 연습',[c['label'] for c in candidates])
        self.assertIn('문법의 문장 적용',[c['label'] for c in candidates])

    def test_clear_case_has_priority_over_repeated_keyword(self):
        p=self.page('초등영어학원','english','기초 문법과 독해 연결이 필요한 학생에게는 단어 기억과 짧은 글 이해를 함께 점검합니다.')
        candidates=sorted(content_candidates(p),key=lambda c:-c['score'])
        self.assertEqual(candidates[0]['label'],'문법과 독해 연결')

    def test_no_learning_evidence_does_not_invent_topics(self):
        self.assertEqual(content_candidates(self.page('수학전문학원','math','등록 주소와 전화번호만 안내합니다.')),[])


    def test_grade_role_puts_routine_before_subject_topic(self):
        text='주간 시간표와 과제 마감, 복습 간격을 먼저 확인합니다. 계산 실수와 개념 공백이 섞여 오답 원인이 분명하지 않은 학생은 풀이 근거를 설명합니다.'
        p=self.page('고등학생 수학학원','math',text)
        p.update(kind='detail',family='grade',group='grade-high-math',rel='test.html',
                 base='명일동 고등학생 수학학원',source='<title>명일동 고등학생 수학학원 | 기존</title>')
        plan([p])
        self.assertIn(p['evidence'][0]['label'],HABIT_TOPICS)
        self.assertEqual(len(p['evidence']),2)


if __name__=='__main__':unittest.main()
