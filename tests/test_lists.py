import unittest
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
CARD = '''<li><div class="titTxt"><p><a title="练习甲" href="javascript:openWork()">练习甲</a></p>
<strong>待批阅</strong><p class="pt5">截止时间：2030-01-01 10:00</p></div><a>查看</a></li>'''


class ListTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch(channel='msedge', headless=True)
        cls.context = cls.browser.new_context()
        cls.context.route('**/*', lambda route: route.abort())

    @classmethod
    def tearDownClass(cls):
        cls.context.close()
        cls.browser.close()
        cls.pw.stop()

    def setUp(self):
        self.page = self.context.new_page()
        self.addCleanup(self.page.close)

    def read(self, html):
        self.assertTrue((ROOT / 'list.js').is_file(), 'legacy list adapter is missing')
        self.page.set_content(html)
        return self.page.evaluate((ROOT / 'list.js').read_text(encoding='utf-8'))

    def test_review_pending_and_javascript_entry_are_kept_without_duplicate_view_link(self):
        items = self.read('<div class="ulDiv"><ul>' + CARD + '</ul></div>')
        self.assertEqual(items, [{'title': '练习甲', 'status': '待批阅', 'deadline': '2030-01-01 10:00'}])

    def test_unknown_layout_never_becomes_successful_empty_list(self):
        with self.assertRaisesRegex(Exception, 'UNSUPPORTED_LAYOUT'):
            self.read('<main>unknown layout</main>')

    def test_one_malformed_card_does_not_silently_disappear(self):
        bad = CARD.replace('<strong>待批阅</strong>', '')
        with self.assertRaisesRegex(Exception, 'INCOMPLETE_CARD'):
            self.read('<div class="ulDiv"><ul>' + CARD + bad + '</ul></div>')


if __name__ == '__main__':
    unittest.main()
