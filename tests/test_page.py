import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'vendor')]
from playwright.sync_api import sync_playwright

FIXTURE = '''<!doctype html><form id="submitForm">
<input id="courseId" value="11" type="hidden"><input id="workId" value="22" type="hidden">
<div class="questionLi" id="question101"><h3 class="mark_name">Explain AI</h3>
<input id="answertype101" name="answertype101" value="4" type="hidden">
<textarea id="answer101" name="answer101" hidden></textarea><div id="body101" contenteditable="true"></div></div>
<div class="questionLi" id="question102"><h3 class="mark_name">Two blanks</h3>
<input id="answertype102" name="answertype102" value="2" type="hidden">
<textarea id="answerEditor102_0" name="answer102" hidden></textarea><div id="body102a" contenteditable="true"></div>
<textarea id="answerEditor102_1" name="answer102" hidden></textarea><div id="body102b" contenteditable="true"></div></div>
<div class="questionLi" id="question103"><h3 class="mark_name">Choose</h3>
<input id="answertype103" name="answertype103" value="1" type="hidden"><input id="answer103" name="answer103" type="hidden" value="">
<ul><li qid="103" aria-checked="false"><span class="num_option" data="C">A</span><span class="option_content">one</span></li>
<li qid="103" aria-checked="false"><span class="num_option" data="A">B</span><span class="option_content">two</span></li></ul></div>
</form><script>
window.UE={instants:{}};let n=0;for(const [key,id] of [['answer101','body101'],['answerEditor102_0','body102a'],['answerEditor102_1','body102b']]){
 const body=document.getElementById(id),textarea=document.getElementById(key);
 UE.instants['e'+n++]={key,body,textarea,isReady:1,setContent(v){body.innerHTML=v},sync(){textarea.value=body.innerHTML}};
}
window.syncAnswer=()=>Object.values(UE.instants).forEach(e=>e.sync());
window.saveWork=(o)=>{window.saved=true;o.success({status:true})};
for(const li of document.querySelectorAll('li[qid]'))li.onclick=()=>{li.setAttribute('aria-checked',li.getAttribute('aria-checked')!=='true');document.getElementById('answer103').value=[...document.querySelectorAll('li[aria-checked=true] span[data]')].map(e=>e.getAttribute('data')).join(',')};
</script>'''


class PageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch(channel='msedge', headless=True)
        cls.context = cls.browser.new_context()

    @classmethod
    def tearDownClass(cls):
        cls.context.close()
        cls.browser.close()
        cls.pw.stop()

    def setUp(self):
        self.assertTrue((ROOT / 'page.js').is_file(), 'page adapter is missing')
        self.adapter = (ROOT / 'page.js').read_text(encoding='utf-8')
        self.page = self.context.new_page()
        self.page.route('**/*', lambda route: route.fulfill(body=FIXTURE, content_type='text/html'))
        self.page.goto('https://fixture.invalid/mooc2/work/dowork?courseId=11&workId=22')
        self.addCleanup(self.page.close)

    def call(self, method, arg=None):
        if method == 'fill':
            arg = {'course_id': '11', 'work_id': '22', 'changes': arg}
        elif method == 'save':
            arg = {'course_id': '11', 'work_id': '22'}
        return self.page.evaluate('(arg)=>{const a=' + self.adapter + ';return a.' + method + '(arg)}', arg)

    def load_review(self):
        self.page.set_content('''<div class="fanyaMarking TiMu" id="fanyaMarking">
        <h2>Example assignment</h2><div class="questionLi" id="question201">
        <h3 class="mark_name"><span class="colorShallow">(单选题, 1分)</span><span class="qtContent">Choose a letter</span></h3>
        <ul class="mark_letter qtDetail"><li class="workTextWrap">A. Alpha</li><li class="workTextWrap">B. Beta</li></ul>
        <div class="mark_answer"><span class="stuAnswerContent">B</span><span class="rightAnswerContent">A</span></div>
        <span class="qtAnalysis">Example explanation</span></div>
        <div class="questionLi" id="question202"><h3 class="mark_name"><span class="colorShallow">(填空题, 2分)</span>Fill two blanks</h3>
        <dl class="mark_fill"><dd><span class="stuAnswerContent">(1) <p>first</p></span></dd>
        <dd><span class="stuAnswerContent">(2) <p>second</p></span></dd></dl>
        <dl><dd class="rightAnswerContent">(1) expected one</dd><dd class="rightAnswerContent">(2) expected two</dd></dl>
        </div></div>''')
        self.page.evaluate("history.replaceState({},'', '/mooc2/work/view?courseId=11&workId=22')")

    def test_review_container_is_not_an_extra_question(self):
        self.load_review()
        self.assertEqual([q['id'] for q in self.call('read')['questions']], ['201', '202'])

    def test_review_choice_display_labels_and_own_answer_are_extracted(self):
        self.load_review()
        question = next(q for q in self.call('read')['questions'] if q['id'] == '201')
        self.assertEqual(question['kind'], 'choice')
        self.assertEqual(question['options'], [{'id': 'A', 'text': 'Alpha', 'label': 'A'},
                                               {'id': 'B', 'text': 'Beta', 'label': 'B'}])
        self.assertEqual(question['answer'], ['B'])
        self.assertEqual(question['correct_answer'], ['A'])
        self.assertIsNone(question['form_answer'])

    def test_review_blanks_are_read_without_requiring_edit_controls(self):
        self.load_review()
        question = next(q for q in self.call('read')['questions'] if q['id'] == '202')
        self.assertEqual(question['kind'], 'blanks')
        self.assertEqual(question['answer'], ['first', 'second'])
        self.assertEqual(question['correct_answer'], ['expected one', 'expected two'])
        self.assertEqual(question['editor_keys'], [])
        with self.assertRaisesRegex(Exception, 'READ_ONLY'):
            self.call('save')

    def test_image_targets_include_option_images_but_not_answer_images(self):
        self.load_review()
        self.page.evaluate("""() => {
            document.querySelector('#question201 .mark_name').appendChild(document.createElement('img'));
            document.querySelector('#question201 .mark_letter li:nth-child(2)').appendChild(document.createElement('img'));
            document.querySelector('#question201 .qtAnalysis').appendChild(document.createElement('img'));
        }""")
        result = self.page.evaluate('''(adapter) => eval(adapter)
            .imageTargets({course_id:'11',work_id:'22',limit:4})
            .map(group => [group.number, ...group.images.map(image => [image.part,image.option])])''', self.adapter)
        self.assertEqual(result, [[1, ['stem', None], ['option', 2]]])
        self.assertEqual(len(self.call('read')['questions'][0]['images']), 2)

    def test_image_targets_stop_at_four_and_require_the_selected_assignment(self):
        self.load_review()
        self.page.evaluate("""() => {
            const marking = document.querySelector('#fanyaMarking');
            for (let index = 0; index < 6; index++) {
                marking.insertAdjacentHTML('beforeend', '<div class=questionLi><h3 class=mark_name><img></h3></div>');
            }
        }""")
        self.assertEqual(self.page.evaluate('''(adapter) => eval(adapter)
            .imageTargets({course_id:'11',work_id:'22',limit:4}).map(group => group.number)''', self.adapter),
            [3, 4, 5, 6])
        with self.assertRaisesRegex(Exception, 'IDENTITY_MISMATCH'):
            self.page.evaluate('''(adapter) => eval(adapter)
                .imageTargets({course_id:'11',work_id:'23',limit:4})''', self.adapter)

    def test_display_only_option_letters_are_not_used_as_editable_control_ids(self):
        self.page.evaluate("()=>{document.querySelector('#question103 ul').outerHTML='<ul class=mark_letter><li>A. First</li><li>B. Second</li></ul>'}")
        question = next(q for q in self.call('read')['questions'] if q['id'] == '103')
        self.assertEqual(question['kind'], 'unsupported')

    def test_read_stable_ids_and_blank_order(self):
        data = self.call('read')
        self.assertEqual(data['course_id'], '11')
        self.assertEqual([q['id'] for q in data['questions']], ['101', '102', '103'])
        self.assertEqual(data['questions'][1]['answer'], ['', ''])
        self.assertEqual(data['questions'][2]['options'][0]['id'], 'C')

    def test_draft_survives_reload_and_is_verified_with_same_answer_plan(self):
        import cx
        persistence = '''<script>
        const saved=JSON.parse(localStorage.getItem('draft-fixture')||'{}');
        for(const e of Object.values(UE.instants)){if(saved[e.key]){e.setContent(saved[e.key]);e.sync()}}
        window.saveWork=o=>{localStorage.setItem('draft-fixture',JSON.stringify(Object.fromEntries(
          Object.values(UE.instants).map(e=>[e.key,e.body.innerHTML]))));o.success({status:true})};
        </script>'''
        self.page.evaluate('localStorage.clear()')
        self.page.unroute('**/*')
        self.page.route('**/*', lambda route: route.fulfill(body=FIXTURE + persistence, content_type='text/html'))
        self.page.reload()
        plan = {'course_id': '11', 'work_id': '22', 'answers': {'101': {'text': 'verified draft'}}}
        changes = cx.build_changes(self.call('read'), plan)
        self.call('fill', changes)
        self.call('save')
        self.assertEqual(self.page.evaluate('window.__cxDraftSave.status'), 'saved')
        self.page.reload()
        snapshot = self.call('read')
        cx.verify_plan(snapshot, plan)
        self.assertEqual(snapshot['questions'][0]['form_answer'], 'verified draft')
        self.page.evaluate('localStorage.clear()')

    def test_fill_text_and_blanks_synchronizes_fields(self):
        self.call('fill', [{'id': '101', 'kind': 'text', 'value': 'safe <text>', 'before': ''},
                           {'id': '102', 'kind': 'blanks', 'value': ['first', 'second'], 'before': ['', '']}])
        qs = self.call('read')['questions']
        self.assertEqual(qs[0]['answer'], 'safe <text>')
        self.assertEqual(qs[0]['form_answer'], 'safe <text>')
        self.assertEqual(qs[1]['form_answer'], ['first', 'second'])

    def test_repeated_choice_fill_does_not_toggle_off(self):
        change = {'id': '103', 'kind': 'choice', 'value': ['C', 'A'], 'before': []}
        self.call('fill', [change])
        # A caller must re-read before retry; here the existing target is explicitly accepted.
        change['before'] = ['C', 'A']
        self.call('fill', [change])
        self.assertEqual(self.call('read')['questions'][2]['answer'], ['C', 'A'])
        self.assertEqual(self.call('read')['questions'][2]['form_answer'], ['C', 'A'])

    def test_race_detected_before_any_write(self):
        self.page.evaluate("UE.instants.e0.setContent('user edit')")
        with self.assertRaisesRegex(Exception, 'PAGE_CHANGED'):
            self.call('fill', [{'id': '102', 'kind': 'blanks', 'value': ['a', 'b'], 'before': ['', '']},
                               {'id': '101', 'kind': 'text', 'value': 'overwrite', 'before': ''}])
        self.assertEqual(self.call('read')['questions'][1]['answer'], ['', ''])

    def test_read_only_view_rejects_mutation(self):
        self.page.evaluate("history.replaceState({},'', '/mooc2/work/view?courseId=11&workId=22')")
        self.assertFalse(self.call('read')['editable'])
        with self.assertRaisesRegex(Exception, 'READ_ONLY'):
            self.call('fill', [{'id': '101', 'kind': 'text', 'value': 'no', 'before': ''}])

    def test_save_failure_is_reported_not_success(self):
        self.page.evaluate("()=>{window.saveWork=o=>o.failure({msg:'server rejected'})}")
        self.call('save')
        self.assertEqual(self.page.evaluate('window.__cxDraftSave.status'), 'failed')

    def test_assets_cannot_be_silently_overwritten(self):
        self.page.evaluate("UE.instants.e0.body.innerHTML='<img src=photo.jpg>'")
        self.assertTrue(self.call('read')['questions'][0]['has_assets'])
        with self.assertRaisesRegex(Exception, 'ASSETS_PRESENT'):
            self.call('fill', [{'id': '101', 'kind': 'text', 'value': 'no', 'before': ''}])

    def test_navigation_race_checks_identity_in_browser(self):
        self.page.evaluate("document.getElementById('workId').value='99'")
        with self.assertRaisesRegex(Exception, 'IDENTITY_MISMATCH'):
            self.call('fill', [{'id': '101', 'kind': 'text', 'value': 'no', 'before': ''}])
        with self.assertRaisesRegex(Exception, 'IDENTITY_MISMATCH'):
            self.call('save')

    def test_plain_input_angle_brackets_are_preserved_and_protected(self):
        self.page.evaluate("()=>{delete UE.instants.e0;document.getElementById('answer101').value='<todo>'}")
        snap = self.call('read')
        self.assertEqual(snap['questions'][0]['answer'], '<todo>')
        import cx
        with self.assertRaisesRegex(cx.TaskError, 'ANSWER_CONFLICT'):
            cx.build_changes(snap, {'course_id': '11', 'work_id': '22', 'answers': {'101': {'text': 'hello'}}})

    def test_blank_order_uses_dom_not_editor_registration_order(self):
        self.page.evaluate("()=>{const e=UE.instants;UE.instants={e2:e.e2,e1:e.e1,e0:e.e0}}")
        self.call('fill', [{'id': '102', 'kind': 'blanks', 'value': ['first', 'second'], 'before': ['', '']}])
        self.assertEqual(self.page.locator('#body102a').inner_text(), 'first')
        self.assertEqual(self.page.locator('#body102b').inner_text(), 'second')

    def test_audio_and_listening_prompts_are_manual_tasks(self):
        cases = [('听录音，回答问题', ''), ('听写Unit1', ''), ('Unit1 dictation', ''),
                 ('Answer questions', '<audio src=example.mp3></audio>'),
                 ('Answer questions', '<iframe src="/ananas/audioplay/player.html"></iframe>')]
        for stem, media in cases:
            self.page.evaluate("arg=>{const r=document.getElementById('question101');r.querySelector('h3').innerText=arg[0];r.querySelectorAll('audio,iframe').forEach(e=>e.remove());r.insertAdjacentHTML('beforeend',arg[1])}", [stem, media])
            self.assertTrue(self.call('read')['questions'][0]['manual_only'], stem)
            with self.assertRaisesRegex(Exception, 'MANUAL_TASK'):
                self.call('fill', [{'id': '101', 'kind': 'text', 'value': 'no', 'before': ''}])


if __name__ == '__main__':
    unittest.main()
