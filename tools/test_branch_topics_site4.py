import json
from pathlib import Path
import unittest
from branch_topic_manuscripts_site4 import parse
from branch_topic_editorial_site4 import clean_copy, prepare, reading_chunks
from branch_topic_enrichment_site4 import polish_school_field


class TopicTests(unittest.TestCase):
    def test_subject_particle(self):
        self.assertEqual(clean_copy('과학를 확인해 보세요.'),'과학을 확인해 보세요.')

    def test_legitimate_manuscript_and_math_input_remain(self):
        for value in ('학생이 원고에서 주제문을 골라 봅니다.', '함수의 입력과 출력을 비교합니다.', '발표 원고를 보지 않고 말해 봅니다.', '세원고 수업 자료를 준비합니다.'):
            self.assertEqual(clean_copy(value),value)

    def test_source_context_polished(self):
        self.assertNotIn('원고 참고 키워드',clean_copy('원고 참고 키워드에 영어 수학이 함께 제시된 경우에도 두 과목을 나누어 살펴보세요.'))
        self.assertNotIn('D열',clean_copy('D열에 제시된 학교 정보'))
        self.assertNotIn('E열',clean_copy('E열에는 주소 정보가 제공되어 있습니다.'))
        self.assertNotIn('입력 정보',clean_copy('입력 정보만으로 단정하지 않습니다.'))
        self.assertEqual(clean_copy('자기소개 녹음 또는 원고를 준비하면 좋습니다.'),'자기소개 녹음 또는 원고를 준비하면 좋습니다.')

    def test_genuine_previous_stage_context_preserved(self):
        value='원화중 시기의 학습 기록을 보조 자료로 확인할 수 있습니다.'
        self.assertEqual(polish_school_field(value,'sections.0.paragraphs.0',{'locality':'감삼동','stage':'고등학생'}),value)

    def test_no_sentence_cutting(self):
        text='개념을 설명해 보세요. 조건을 바꾸고 다시 풀어 봅니다. 배운 내용을 기록합니다.'
        self.assertEqual(' '.join(reading_chunks(text,20)),text)

    def test_all_overlays_preserve_source_and_routes(self):
        data=json.loads((Path(__file__).parent/'data/branch-topics/manuscripts.json').read_text(encoding='utf8'))
        before=json.dumps(data,ensure_ascii=False)
        for m in data:
            new,_=prepare(m)
            self.assertEqual(new['title'],m['title'])
            self.assertEqual(new['path'],m['path'])
            self.assertEqual(new['sourceSha256'],m['sourceSha256'])
            self.assertEqual(len(new['sections']),len(m['sections']))
            self.assertEqual(len(new['faq']),4)
            self.assertEqual(new['confirmedGrades'],m['confirmedGrades'])
            self.assertEqual(new['centerId'],m['centerId'])
            self.assertTrue(1<=len(new['contextualLinks'])<=3,m['title'])
            self.assertTrue(1<=len(new['quickScan'])<=3,m['title'])
            for q in new['quickScan']:
                self.assertIn(q['text'],new['sections'][q['section']-1]['paragraphs'][q['paragraph']])
            for link in new['contextualLinks']:
                self.assertIn(link['phrase'],new['sections'][link['section']-1]['paragraphs'][link['paragraph']])
            self.assertEqual(len({l['path'] for l in new['contextualLinks']}),len(new['contextualLinks']))
        self.assertEqual(before,json.dumps(data,ensure_ascii=False))


if __name__=='__main__':
    unittest.main()
