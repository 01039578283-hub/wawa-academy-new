"""Regression checks for branch import boundaries and legacy navigation."""
import unittest
from branch_site4_support import with_navigation, without_navigation
from import_branch_reference_site4 import match_photo


class BranchTests(unittest.TestCase):
    def test_korean_and_encoded_menu_links(self):
        for href in ('/상담문의/', '/%EC%83%81%EB%8B%B4%EB%AC%B8%EC%9D%98/', '../../../상담문의/'):
            original = '<head></head><nav aria-label="주요 메뉴" class="main-nav"><a href="/">홈</a><a class="nav-link" href="' + href + '">상담문의</a></nav><main>원고 그대로</main><div class="footer-links"><a href="/">홈</a></div>'
            updated = with_navigation(original)
            self.assertEqual(updated.count('data-branch-directory-link="true"'), 2)
            self.assertEqual(with_navigation(updated), updated)
            self.assertEqual(without_navigation(updated), original)

    def test_same_name_wrong_address_is_not_used(self):
        center = {'id': 'test', 'sourceCenterName': '명일점', 'address': '서울 강동구 양재대로 1606 3층'}
        wrong = {'id': 999, 'placeName': '명일점', 'doroAddr1': '서울 강동구 양재대로 999', 'folder': 'other'}
        photo, _ = match_photo(center, [wrong])
        self.assertIsNone(photo)

    def test_road_address_equivalence(self):
        center = {'id': 'test', 'sourceCenterName': '명일점', 'address': '서울 강동구 양재대로 1606 3층'}
        right = {'id': 42, 'placeName': '명일점', 'doroAddr1': '서울특별시 강동구 양재대로 1606', 'folder': 'same'}
        photo, basis = match_photo(center, [right])
        self.assertEqual(photo['id'], 42)
        self.assertEqual(basis, 'road-address-and-name')

    def test_ambiguous_address_not_assigned(self):
        center = {'id': 'test', 'sourceCenterName': '동명이점', 'address': '서울 강동구 양재대로 1606 3층'}
        photos = [{'id': n, 'placeName': name, 'doroAddr1': '서울 강동구 양재대로 1606', 'folder': name} for n, name in ((1, '가점'), (2, '나점'))]
        photo, _ = match_photo(center, photos)
        self.assertIsNone(photo)


if __name__ == '__main__':
    unittest.main()
