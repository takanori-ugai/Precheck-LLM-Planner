import unittest
import copy
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch
import vh_experiment
from vh_experiment import goal, comparable, symbolic
from vh_fixed_initial import alignment, recording_prefix
from summarize_vh import read_lines, transform_delta


class VHTests(unittest.TestCase):
    def setUp(self):
        self.objects = {10: {'states': ['OFF']}, 20: {'states': ['OPEN']}, 30: {'states': []}}
        self.agent = {'close_to': [10, 20], 'hold_rh': 30, 'hold_lh': None}

    def test_all_eight_operations(self):
        expected = {'[WALK] <apple> (30)': 'false', '[GRAB] <switch> (10)': 'true',
                    '[SWITCHON] <switch> (10)': 'true', '[SWITCHOFF] <switch> (10)': 'false',
                    '[OPEN] <fridge> (20)': 'false', '[CLOSE] <fridge> (20)': 'true',
                    '[PUT] <apple> (30) <fridge> (20)': 'true', '[PUTIN] <apple> (30) <fridge> (20)': 'true'}
        for action, label in expected.items():
            self.assertEqual(symbolic(action, self.objects, self.agent)['label'], label)

    def test_unknown_not_false(self):
        result = symbolic('[SWITCHON] <switch> (99)', self.objects, self.agent)
        self.assertEqual(result['label'], 'unknown')
        self.assertEqual(len(result['unknown_conditions']), 2)

    def test_state_array_equality(self):
        task = {'goal_states': [{'id': 10, 'states': ['ON']}]}
        graph = {'nodes': [{'id': 10, 'states': ['ON', 'EXTRA']}], 'edges': []}
        self.assertFalse(goal(graph, task)['all_satisfied'])
        graph['nodes'][0]['states'] = ['ON']
        self.assertTrue(goal(graph, task)['all_satisfied'])

    def test_goal_does_not_require_closing_container(self):
        task = {'goal_states': [{'from_id': 30, 'to_id': 20, 'relation_type': 'INSIDE'}]}
        graph = {'nodes': [{'id': 20, 'states': ['OPEN']}], 'edges': task['goal_states']}
        self.assertTrue(goal(graph, task)['all_satisfied'])
        graph['edges'] = [{'from_id': 30, 'to_id': 20, 'relation_type': 'ON'}]
        self.assertFalse(goal(graph, task)['all_satisfied'])

    def test_comparison_ignores_order_not_relations(self):
        graph = {'nodes': [{'id': 10, 'class_name': 'switch', 'states': ['OFF'], 'properties': []},
                           {'id': 1, 'class_name': 'character', 'states': [], 'properties': []}],
                 'edges': [{'from_id': 1, 'to_id': 10, 'relation_type': 'CLOSE'}]}
        reordered = {'nodes': graph['nodes'][::-1], 'edges': graph['edges']}
        self.assertEqual(comparable(graph), comparable(reordered))
        reordered['edges'] = []
        self.assertNotEqual(comparable(graph), comparable(reordered))

    def test_wrong_arity(self):
        self.assertEqual(symbolic('[PUT] <apple> (30)', self.objects, self.agent)['label'], 'invalid_format')

    def test_probe_never_reads_uninitialized_graph(self):
        comm = MagicMock()
        comm.check_connection.return_value = True
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(vh_experiment, 'OUT', Path(directory)), \
             patch.object(vh_experiment, 'prepare', return_value={}), \
             patch.object(vh_experiment, 'connect', return_value=comm), \
             patch.object(vh_experiment.sys, 'argv', ['vh_experiment.py', '--phase', 'probe']):
            vh_experiment.main()
        comm.check_connection.assert_called_once()
        comm.environment_graph.assert_not_called()
        comm.reset.assert_not_called()

    def test_fixed_alignment_position_and_rotation(self):
        a = {'nodes': [{'id': 1, 'class_name': 'character', 'states': [], 'properties': [],
                       'obj_transform': {'position': [0, 1, 2], 'rotation': [0, 0, 0, 1]}}], 'edges': []}
        b = copy.deepcopy(a)
        self.assertTrue(alignment(a, b)['passed'])
        b['nodes'][0]['obj_transform']['rotation'] = [0, 0, 0, -1]
        self.assertTrue(alignment(a, b)['passed'])
        b['nodes'][0]['obj_transform']['position'][0] = 0.01
        self.assertFalse(alignment(a, b)['passed'])
        self.assertAlmostEqual(transform_delta(a, b), 0.01)
        b['nodes'][0]['obj_transform']['position'][0] = 0
        b['nodes'][0]['obj_transform']['rotation'] = [0, 1, 0, 0]
        self.assertFalse(alignment(a, b)['passed'])

    def test_fixed_alignment_missing_transform_or_relation(self):
        a = {'nodes': [{'id': 1, 'class_name': 'character', 'states': [], 'properties': [],
                       'obj_transform': {'position': [0, 1, 2], 'rotation': [0, 0, 0, 1]}}], 'edges': []}
        b = copy.deepcopy(a)
        b['edges'] = [{'from_id': 1, 'to_id': 1, 'relation_type': 'CLOSE'}]
        self.assertFalse(alignment(a, b)['passed'])
        del b['nodes'][0]['obj_transform']
        self.assertFalse(alignment(a, b)['passed'])
        self.assertIsNone(transform_delta(a, b))

    def test_partial_log_not_counted(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'api.jsonl'
            path.write_text('{"status": "ok"}\n{"status":')
            self.assertEqual(read_lines(path), [{'status': 'ok'}])

    def test_short_unique_windows_recording_prefix(self):
        prefix = recording_prefix('state_change_task_test_task6_C0_no_precheck_gpt-4o-mini-2024-07-18', 'attempt1', 1)
        self.assertLess(len(prefix), 32)
        base = 'C:/Users/ugai/Downloads/VH/windows_exec.v2.3.0/Output/'
        self.assertLess(len(base + prefix + '/0/ftaa_' + prefix + '.txt'), 240)
        self.assertNotEqual(prefix, recording_prefix('another_run', 'attempt1', 1))
        self.assertNotEqual(prefix, recording_prefix('state_change_task_test_task6_C0_no_precheck_gpt-4o-mini-2024-07-18', 'attempt2', 1))


if __name__ == '__main__':
    unittest.main()
