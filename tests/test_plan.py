import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
try:
    import cx
except ImportError:
    cx = None


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(cx, 'cx implementation is missing')
        self.snapshot = {
            'course_id': '11', 'work_id': '22', 'editable': True,
            'questions': [
                {'id': '101', 'kind': 'text', 'answer': '', 'stem': 'Question'},
                {'id': '102', 'kind': 'blanks', 'answer': ['', ''], 'stem': 'Two blanks'},
                {'id': '103', 'kind': 'choice', 'answer': ['data-C'],
                 'stem': 'Choose', 'multiple': True,
                 'options': [{'id': 'data-C', 'text': 'Visible A'}, {'id': 'data-A', 'text': 'Visible B'}]},
            ],
        }
        self.plan = {'course_id': '11', 'work_id': '22', 'answers': {'101': {'text': 'hello'}}}

    def test_wrong_assignment_is_rejected(self):
        self.plan['work_id'] = '99'
        with self.assertRaisesRegex(cx.TaskError, 'IDENTITY_MISMATCH'):
            cx.build_changes(self.snapshot, self.plan)

    def test_empty_or_fully_unsupported_read_is_not_reported_as_parsed(self):
        self.assertTrue(hasattr(cx, 'question_summary'), 'read quality check is missing')
        for questions in ([], [{'id': '201', 'kind': 'unsupported'}]):
            with self.assertRaisesRegex(cx.TaskError, 'UNSUPPORTED_LAYOUT'):
                cx.question_summary({'questions': questions})

    def test_partial_read_reports_unsupported_question_ids(self):
        self.assertTrue(hasattr(cx, 'question_summary'), 'read quality check is missing')
        summary = cx.question_summary({'questions': [{'id': '201', 'kind': 'choice'},
                                                   {'id': '202', 'kind': 'unsupported'}]})
        self.assertEqual(summary['parse_status'], 'partial')
        self.assertEqual(summary['unsupported_questions'], ['202'])

    def test_unknown_question_is_rejected(self):
        self.plan['answers'] = {'999': {'text': 'wrong'}}
        with self.assertRaisesRegex(cx.TaskError, 'UNKNOWN_QUESTION'):
            cx.build_changes(self.snapshot, self.plan)

    def test_completed_work_is_read_only(self):
        self.snapshot['editable'] = False
        with self.assertRaisesRegex(cx.TaskError, 'READ_ONLY'):
            cx.build_changes(self.snapshot, self.plan)

    def test_conflict_preflight_prevents_all_changes(self):
        self.snapshot['questions'][1]['answer'] = ['mine', '']
        self.plan['answers']['102'] = {'blanks': ['other', 'two']}
        with self.assertRaisesRegex(cx.TaskError, 'ANSWER_CONFLICT'):
            cx.build_changes(self.snapshot, self.plan)

    def test_identical_text_is_skipped(self):
        self.snapshot['questions'][0]['answer'] = 'hello'
        self.assertEqual(cx.build_changes(self.snapshot, self.plan), [])

    def test_multiple_blanks_preserve_order(self):
        self.plan['answers'] = {'102': {'blanks': ['first', 'second']}}
        self.assertEqual(cx.build_changes(self.snapshot, self.plan)[0]['value'], ['first', 'second'])

    def test_wrong_number_of_blanks_is_rejected(self):
        self.plan['answers'] = {'102': {'blanks': ['one']}}
        with self.assertRaisesRegex(cx.TaskError, 'BLANK_COUNT'):
            cx.build_changes(self.snapshot, self.plan)

    def test_selected_option_not_toggled_and_data_not_visual_order(self):
        self.plan['answers'] = {'103': {'choices': ['data-C', 'data-A']}}
        change = cx.build_changes(self.snapshot, self.plan)[0]
        self.assertEqual(change['value'], ['data-C', 'data-A'])
        self.plan['answers'] = {'103': {'choices': ['data-C']}}
        self.assertEqual(cx.build_changes(self.snapshot, self.plan), [])

    def test_wrong_option_and_empty_answer_are_rejected(self):
        for answer in ({'choices': ['Z']}, {'choices': []}):
            self.plan['answers'] = {'103': answer}
            with self.assertRaises(cx.TaskError):
                cx.build_changes(self.snapshot, self.plan)

    def test_choice_removal_of_existing_answer_is_conflict(self):
        self.plan['answers'] = {'103': {'choices': ['data-A']}}
        with self.assertRaisesRegex(cx.TaskError, 'ANSWER_CONFLICT'):
            cx.build_changes(self.snapshot, self.plan)

    def test_existing_media_and_manual_recording_are_not_overwritten(self):
        q = self.snapshot['questions'][0]
        for key in ('has_assets', 'manual_only'):
            q[key] = True
            with self.assertRaises(cx.TaskError):
                cx.build_changes(self.snapshot, self.plan)
            q[key] = False

    def test_verification_checks_hidden_fields_independently(self):
        self.snapshot['questions'][0].update(answer='hello', form_answer='')
        with self.assertRaisesRegex(cx.TaskError, 'FIELD_MISMATCH'):
            cx.verify_plan(self.snapshot, self.plan)

    def test_saved_verification_rejects_empty_expectations(self):
        with self.assertRaisesRegex(cx.TaskError, 'NO_EXPECTED_ANSWERS'):
            cx.verify_saved(self.snapshot, {})

    def test_saved_verification_checks_fields_and_question_set(self):
        one = {'questions': [{'id': '101', 'kind': 'text', 'answer': 'a', 'form_answer': ''}]}
        expected = {'101': {'kind': 'text', 'answer': 'a'}}
        with self.assertRaisesRegex(cx.TaskError, 'FIELD_MISMATCH'):
            cx.verify_saved(one, expected)
        one['questions'][0]['form_answer'] = 'a'
        cx.verify_saved(one, expected)
        one['questions'].append({'id': '102', 'kind': 'text', 'answer': '', 'form_answer': ''})
        with self.assertRaisesRegex(cx.TaskError, 'QUESTION_SET_CHANGED'):
            cx.verify_saved(one, expected)


if __name__ == '__main__':
    unittest.main()
