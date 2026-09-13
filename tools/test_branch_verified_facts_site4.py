import json
import unittest
from branch_verified_facts_site4 import ROOT, load_reviewed_snapshot, recorded_grades, practice_for, pending_note, owner_confirmation


class VerifiedFactsTests(unittest.TestCase):
    def test_exact_baseline_no_extension(self):
        for cid,subject,stage,expected in (
            ('center-row-021','영어','고등학생',['고1','고2']),
            ('center-row-040','영어','고등학생',['고1']),
            ('center-row-040','수학','고등학생',['고1']),
            ('center-row-046','영어','초등학생',['초5','초6']),
        ):
            self.assertEqual(recorded_grades(dict(centerId=cid,subject=subject,stage=stage)),expected)

    def test_scoped_owner_confirmation(self):
        rows=owner_confirmation()['confirmations']
        self.assertEqual(len({r['centerId'] for r in rows}),8)
        for r in rows:
            for stage in r['stages']:
                prefix,count={'초등학생':('초',6),'중학생':('중',3),'고등학생':('고',3)}[stage]
                self.assertEqual(recorded_grades(dict(centerId=r['centerId'],subject=r['subject'],stage=stage)),[prefix+str(i) for i in range(1,count+1)])
        # User confirmation of these English/math pages does not open Korean.
        self.assertEqual(recorded_grades(dict(centerId='center-row-098',subject='국어',stage='고등학생')),[])

    def test_isolated_source_copy(self):
        data=load_reviewed_snapshot()
        data['centers'][0]['address']='changed test'
        self.assertNotEqual(load_reviewed_snapshot()['centers'][0]['address'],'changed test')
        original=json.loads((ROOT/'tools/data/branches/snapshot.json').read_text(encoding='utf-8'))
        self.assertEqual(original['reference']['center-row-021']['operations']['subjectDisplay']['영어']['status'],'scope_confirmation_needed')

    def test_no_college_consultation_on_elementary_pages(self):
        for cid in ('center-row-002','center-row-072'):
            self.assertTrue(practice_for(cid,'수학','초등학생'))
            self.assertNotIn('진학',str(practice_for(cid,'수학','초등학생')['practices']))
            self.assertIn('진학',str(practice_for(cid,'수학','고등학생')['practices']))

    def test_superseded_placement_and_exact_frequency(self):
        self.assertEqual(pending_note(dict(centerId='center-row-098',subject='영어',stage='고등학생',confirmedGrades=['고1','고2','고3'])),'')
        self.assertNotIn('주 1회',str(practice_for('center-row-140','수학','중학생')['practices']))
        self.assertIn('주 1회',str(practice_for('center-row-140','수학','초등학생')['practices']))

    def test_original_other_subjects_preserved(self):
        original=json.loads((ROOT/'tools/data/branches/snapshot.json').read_text(encoding='utf-8'))
        reviewed=load_reviewed_snapshot()
        allowed={(r['centerId'],r['subject']) for r in owner_confirmation()['confirmations']}
        for before,after in zip(original['centers'],reviewed['centers']):
            for subject in before['subjects']:
                if (before['id'],subject) not in allowed:
                    self.assertEqual(before['subjects'][subject],after['subjects'][subject])


if __name__=='__main__':
    unittest.main()
