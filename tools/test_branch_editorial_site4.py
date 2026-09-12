"""Content regressions for the 193 fact-conditioned branch summaries."""
import json
from pathlib import Path
import re
import unittest
import branch_editorial_site4 as e

DATA = json.loads((Path(__file__).parent / 'data/branches/snapshot.json').read_text(encoding='utf-8'))


class EditorialTests(unittest.TestCase):
    def center(self, name):
        c = next(c for c in DATA['centers'] if c['sourceCenterName'] == name)
        return c, DATA['reference'][c['id']], DATA['schoolMatches'].get(c['id'])

    def test_grade_gaps_remain_gaps(self):
        self.assertEqual(e.ranges(['초1', '초2', '초4', '중2', '고1', '고3']), '초1~초2 · 초4 · 중2 · 고1 · 고3')

    def test_imported_question_object_particle(self):
        ref = {'editorial': {'consultationQuestion': '과학 상담 준비는?',
                             'consultationAnswer': '과학를 문의할 때 현재 교재를 준비해 주세요.'}}
        self.assertEqual(e.specific_question(ref)[1], '과학을 문의할 때 현재 교재를 준비해 주세요.')

    def test_myungil_difference_and_unrecorded_subjects(self):
        c, ref, m = self.center('명일점')
        comparison = e.grade_comparison(c, ref)
        self.assertIn('고3의 경우 영어 안내', comparison['text'])
        self.assertIn('초4의 경우 수학 안내', comparison['text'])
        self.assertNotIn('과학', e.confirmed(c, ref))
        self.assertNotIn('사회', e.confirmed(c, ref))
        self.assertIn('과학·사회 수업은 개설 학년이 별도로 확인되지 않았습니다.', str(e.focus_cards(c, ref)))

    def test_school_grade_evidence_for_all_branches(self):
        for c in DATA['centers']:
            ref = DATA['reference'][c['id']]
            match = DATA['schoolMatches'].get(c['id'])
            subjects = e.confirmed(c, ref)
            for prefix, _, _ in e.STAGES:
                groups = e.scope_groups(c, ref, prefix)
                for names, spans in groups:
                    parsed = set()
                    for span in spans.split(' · '):
                        m = re.fullmatch(r'([초중고])(\d)(?:~[초중고](\d))?', span)
                        self.assertIsNotNone(m)
                        parsed.update(m[1] + str(i) for i in range(int(m[2]), int(m[3] or m[2]) + 1))
                    for subject in names.split('·'):
                        self.assertEqual(parsed, {g for g in subjects[subject] if g.startswith(prefix)}, (c['id'], subject, spans))
            for card in e.stage_cards(c, ref, match):
                self.assertTrue(set(card['subjects']).issubset(subjects))

    def test_condition_and_precise_address_exceptions(self):
        c, ref, match = self.center('관평점')
        self.assertEqual(e.ranges(c['subjects']['국어']['grades']), '초1~초5 · 중2~중3')
        self.assertIn('6개월', str(e.focus_cards(c, ref)))
        c, ref, match = self.center('화성태안점')
        self.assertIn('건물·층수 확인', e.intro(c, ref))
        self.assertNotIn('수학 고', e.scope_sentence(c, ref, '고'))

    def test_profiles_do_not_mutate_facts_and_are_deterministic(self):
        original = json.dumps(DATA, ensure_ascii=False, sort_keys=True)
        for c in DATA['centers']:
            ref = DATA['reference'][c['id']]
            match = DATA['schoolMatches'].get(c['id'])
            p = e.profile(c, ref, match)
            self.assertEqual(p, e.profile(c, ref, match))
            self.assertLessEqual(len(p['intro']), 115)  # editorial limit, not an SEO rule
            self.assertNotRegex(p['intro'] + str(p['focusCards']), r'초[124579]은|사회은|영어은')
        self.assertEqual(original, json.dumps(DATA, ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    unittest.main()
