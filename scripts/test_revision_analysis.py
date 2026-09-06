"""Focused checks for statistical denominators, invalid evidence and retrieval ties."""
import unittest

from revision_analysis import cluster_interval, describe, select_example, task_parts, validate_result


class AnalysisTests(unittest.TestCase):
    def test_linear_quantile_and_sample_sd(self):
        stats = describe([0, 2, 4, 10], 'x')
        self.assertEqual(stats['x_mean'], 4)
        self.assertEqual(stats['x_median'], 3)
        self.assertEqual(stats['x_q1'], 1.5)
        self.assertEqual(stats['x_q3'], 5.5)
        self.assertAlmostEqual(stats['x_sd_sample'], (56 / 3) ** .5)

    def test_empty_and_singleton_are_not_zero(self):
        self.assertEqual(describe([], 'x')['x_n'], 0)
        self.assertIsNone(describe([], 'x')['x_mean'])
        self.assertIsNone(describe([2], 'x')['x_sd_sample'])

    def test_missing_ids_and_unknown_outcomes_rejected(self):
        dataset = {'t1': {}}
        valid = {'t1': {'result': 'Success', 'score': 1.0, 'attempts': 0, 'action script': []}}
        validate_result(valid, dataset, 'fixture')
        with self.assertRaises(ValueError):
            validate_result({}, dataset, 'fixture')
        valid['t1']['result'] = 'Other failure'
        with self.assertRaises(ValueError):
            validate_result(valid, dataset, 'fixture')

    def test_saved_length_mismatch_rejected(self):
        with self.assertRaises(ValueError):
            validate_result({'t1': {'result': 'Success', 'score': 1, 'attempts': 1, 'action script': []}},
                            {'t1': {}}, 'fixture')

    def test_example_tie_preserves_original_json_order(self):
        data = {'short': {'task': 'A', 'action_scripts': [1]},
                'first': {'task': 'A', 'action_scripts': [1, 2]},
                'second': {'task': 'A', 'action_scripts': [3, 4]}}
        self.assertEqual(select_example(data, 'A')[0], 'first')

    def test_cluster_interval_fixed_effect_and_determinism(self):
        rows = [{'task_name': 'A', 'delta': 1}, {'task_name': 'A', 'delta': 1},
                {'task_name': 'B', 'delta': 1}]
        self.assertEqual(cluster_interval(rows, lambda x: x['delta'], repetitions=100), (1, 1))
        rows[-1]['delta'] = -1
        self.assertEqual(cluster_interval(rows, lambda x: x['delta'], repetitions=100),
                         cluster_interval(rows, lambda x: x['delta'], repetitions=100))

    def test_task_template_not_confused_with_name(self):
        self.assertEqual(task_parts('Turn off all lightswitches')['operation'], 'off')
        self.assertEqual(task_parts('Put all plums in the fridge')['destination'], 'fridge')
        with self.assertRaises(ValueError):
            task_parts('Clean up')


if __name__ == '__main__':
    unittest.main()
