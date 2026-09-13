import unittest
from unittest.mock import patch
from branch_reviews_site4 import reviews_for, review_cards


class PublishedReviewTests(unittest.TestCase):
    def test_no_cross_branch_subject_or_grade_inference(self):
        rows=[{'centerId':'a','subjects':['영어'],'stages':['고등학생']},
              {'centerId':'a','subjects':['수학'],'stages':[]},
              {'centerId':'b','subjects':['영어'],'stages':['고등학생']},
              {'centerId':'c','subjects':['영어'],'stages':['고등학생'],'parentOnly':True}]
        with patch('branch_reviews_site4.review_catalog',return_value=rows):
            self.assertEqual(reviews_for('a','영어','고등학생'),[rows[0]])
            self.assertEqual(reviews_for('a','영어','초등학생'),[])
            self.assertEqual(reviews_for('a','수학','고등학생'),[])
            self.assertEqual(reviews_for('a'),rows[:2])
            self.assertEqual(reviews_for('c','영어','고등학생'),[])

    def test_attributed_escaped_non_guaranteed_display(self):
        row={'id':'1','gradeText':'고3','subjects':['영어'],'summary':'학생은 <문장>을 다시 읽었다고 설명합니다.',
             'sourceUrl':'https://www.wawacenter.com/review/1','publishedAt':None}
        html=review_cards([row],'/지점안내/서울/예시점/')
        self.assertIn('&lt;문장&gt;',html)
        self.assertIn('공식 후기 원문 보기',html)
        self.assertIn('동일한 결과를 보장하지 않습니다',html)
        self.assertIn('/지점안내/서울/예시점/#student-reviews',html)
        self.assertNotIn('게시일:',html)


if __name__=='__main__':
    unittest.main()
