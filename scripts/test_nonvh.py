import copy
import csv
import json
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
from collections import Counter
from nonvh_analysis import ROOT, PC, OUT, NAMES, action, evaluate, environment, precondition_cases, end_cases
import run_nonvh_api as api


class NonVHTests(unittest.TestCase):
    def test_expected_case_balance(self):
        rows = precondition_cases()
        self.assertEqual(Counter(r['gold'] for r in rows), {'true': 8, 'false': 16, 'unknown': 4})
        self.assertEqual(len({r['id'] for r in rows}), 28)

    def test_each_single_violation(self):
        for row in precondition_cases():
            if row['gold'] == 'false':
                self.assertEqual(row['oracle']['atoms'].count(False), 1)
                self.assertEqual(len(row['oracle']['violations']), 1)

    def test_json_condition_coverage(self):
        for op in PC:
            rows = [r for r in precondition_cases() if r['operation'] == op and r['gold'] == 'false']
            self.assertEqual(len(rows), len(PC[op].splitlines()) - 1)

    def test_format_and_identity(self):
        facts = precondition_cases()[0]['facts']
        for text in ['[FLY] <apple> (101)', '[WALK] <banana> (101)', '[WALK] <apple> (999)',
                     '[PUT] <apple> (101)', '[WALK] <apple> (101) <fridge> (102)', 'some text']:
            self.assertTrue(evaluate(text, facts)['label'].startswith('invalid'))

    def test_contradiction_dominates_unknown(self):
        row = next(r for r in precondition_cases() if r['id'] == 'pc_SWITCHON_unknown')
        facts = copy.deepcopy(row['facts'])
        facts['close'] = []
        self.assertEqual(evaluate(row['action'], facts)['label'], 'false')

    def test_not_closed_is_not_open_requirement(self):
        row = next(r for r in precondition_cases() if r['id'] == 'pc_PUTIN_valid')
        facts = copy.deepcopy(row['facts'])
        facts['states']['102'] = ['OTHER']
        self.assertEqual(evaluate(row['action'], facts)['label'], 'true')
        facts['states']['102'] = None
        self.assertEqual(evaluate(row['action'], facts)['label'], 'unknown')

    def test_end_ground_truth(self):
        rows = end_cases()
        self.assertEqual(len(rows), 16)
        self.assertEqual(Counter(r['gold'] for r in rows), {'End': 8, 'Continue': 8})
        self.assertEqual(len({r['task'] for r in rows if r['origin'] == 'dataset_state_only'}), 6)

    def test_location_drops_state_text(self):
        facts = precondition_cases()[0]['facts']
        self.assertIn('(103) is OFF', environment(facts))
        self.assertNotIn('(103) is OFF', environment(facts, 103))

    def test_no_gold_in_api_messages(self):
        for row in precondition_cases() + end_cases():
            messages = row['messages']
            self.assertTrue(all(role in ('system', 'user') for role, text in messages))
            self.assertFalse(any('goal_states' in text or 'oracle' in text for role, text in messages))

    def test_saved_cases_match_generator(self):
        self.assertEqual(json.loads((OUT / 'cases.json').read_text()),
                         json.loads(json.dumps(precondition_cases() + end_cases())))

    def runner_stub(self):
        obj = api.Runner.__new__(api.Runner)
        obj.done, obj.spent, obj.limit, obj.calls, obj.key = {}, 0, 1, 0, 'unit-test-placeholder'
        obj.config = {'prices_usd_per_million': {'test-model': [1, 1]},
                      'max_estimated_usd': 2, 'cases_sha256': 'fixture'}
        return obj

    def test_budget_stops_before_network(self):
        obj = self.runner_stub()
        obj.spent = 2
        with patch.object(api.urllib.request, 'urlopen') as call:
            with self.assertRaises(StopIteration):
                obj.call('test-model', 'case', 'precondition', 0, [('user', 'test')])
            call.assert_not_called()

    def test_request_count_stops_before_network(self):
        obj = self.runner_stub()
        obj.limit = 0
        with patch.object(api.urllib.request, 'urlopen') as call:
            with self.assertRaises(StopIteration):
                obj.call('test-model', 'case', 'precondition', 0, [('user', 'test')])
            call.assert_not_called()

    def test_error_log_does_not_contain_secret_or_exception_message(self):
        obj = self.runner_stub()
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(api, 'OUT', Path(directory)), patch.object(
                    api.urllib.request, 'urlopen', side_effect=ValueError('unit-test-placeholder sensitive')):
                with self.assertRaises(RuntimeError):
                    obj.call('test-model', 'case', 'precondition', 0, [('user', 'test')])
            log = (Path(directory) / 'api_log.jsonl').read_text()
            self.assertNotIn(obj.key, log)
            self.assertNotIn('sensitive', log)
            self.assertIn('ValueError', log)

    def test_success_resume_has_no_network(self):
        obj = self.runner_stub()
        request = {'model': 'test-model', 'messages': [{'role': 'user', 'content': 'test'}],
                   'temperature': 0, 'max_completion_tokens': 160, 'n': 1, 'store': False}
        obj.done['test-model/case/precondition/0'] = {'request': request, 'text': 'Yes'}
        with patch.object(api.urllib.request, 'urlopen') as call:
            self.assertEqual(obj.call('test-model', 'case', 'precondition', 0, [('user', 'test')]), 'Yes')
            call.assert_not_called()
            with self.assertRaises(AssertionError):
                obj.call('test-model', 'case', 'precondition', 0, [('user', 'changed')])

    def test_retrieval_counts_and_semantic_archive_parity(self):
        with (OUT / 'retrieval_selections.csv').open() as file:
            rows = list(csv.DictReader(file))
        self.assertEqual(len(rows), 2490)
        self.assertEqual(Counter(r['policy'] for r in rows),
                         {'semantic': 415, 'random': 1245, 'fixed': 415, 'none': 415})
        with (ROOT / 'Paper/analysis/retrieval_by_instance.csv').open() as file:
            old = {(r['task_type'], r['task_id']): r['selected_example_id'] for r in csv.DictReader(file)}
        for row in rows:
            if row['policy'] == 'semantic':
                self.assertEqual(row['example_id'], old[row['task_type'], row['task_id']])
            if row['policy'] == 'none':
                self.assertEqual(row['example_id'], '')
                self.assertEqual(row['example_length'], '0')

    def test_human_selection_is_unique_and_uncompleted(self):
        with (OUT / 'human_case_selection_author_only.csv').open() as file:
            rows = list(csv.DictReader(file))
        self.assertEqual(len(rows), 24)
        self.assertEqual(len({(r['task_type'], r['task_id']) for r in rows}), 24)
        self.assertTrue(all(r['human_completed'] == 'False' for r in rows))


if __name__ == '__main__':
    unittest.main()
