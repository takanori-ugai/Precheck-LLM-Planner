import copy
import ast
import gzip
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import vh_step4 as s


class Step4Tests(unittest.TestCase):
    def test_base_loop_prompts_and_history_match_original(self):
        notebook = json.loads((s.vh.ROOT / 'multi-prompts.ipynb').read_text())
        tree = ast.parse(''.join(notebook['cells'][20]['source']))
        run = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'run')
        task = json.loads((s.vh.ROOT / 'dataset/state_change_task/test.json').read_text())['test_task6']
        graph = {'nodes': [{'id': i, 'states': ['ON']} for i in [71, 173, 261, 427]], 'edges': []}
        actions = ['[WALK] <lightswitch> (173)', '[SWITCHON] <lightswitch> (173)']
        for arm in ['C0_no_precheck', 'C1_llm_precheck']:
            expected_prompts, expected_ends = [], []
            decisions, candidates = iter(['Continue', 'Continue', 'End']), iter(actions)
            def generate(prompts):
                expected_prompts.append(copy.deepcopy(prompts))
                return next(candidates)
            def terminate(args):
                expected_ends.append(args['input'])
                return next(decisions)
            ns = {'environment_initialization': lambda *args: None, 'extract_nouns': lambda t: [],
                  'fewshot_prompt_generation': lambda t: 'EXAMPLE', 'extract_environment_knowledge': lambda n: ({}, {}),
                  'return_nlp': lambda *args: 'ENV', 'chain': MagicMock(invoke=terminate),
                  'allowed_actions': s.vh.PROMPT.ALLOWED, 'action_step_generation': generate,
                  'precondition_checking': lambda *args: 'Satisfied', 'regeneration': MagicMock(),
                  'unity_simulation': lambda script: True, 'comm': MagicMock(environment_graph=lambda: (True, graph))}
            exec(compile(ast.Module(body=[run], type_ignores=[]), 'original_test_run', 'exec'), ns)
            expected = ns['run'](task, arm == 'C0_no_precheck')
            with tempfile.TemporaryDirectory() as directory, patch.object(s, 'OUT', Path(directory)):
                s.vh.write(Path(directory) / 'config.json', {})
                e = s.Episode({'host': 'mock', 'port': 0}, 'state_change_task', 'test_task6', arm, s.vh.MODELS[0], 0, MagicMock(spent=0))
                e.folder.mkdir(parents=True)
                e.initialize, e.initial = MagicMock(), {}
                e.knowledge = MagicMock()
                e.knowledge.return_nlp.return_value = 'ENV'
                e.extract, e.example = MagicMock(return_value=({}, {})), MagicMock(return_value='EXAMPLE')
                e.ask = MagicMock(side_effect=['Continue', 'Continue', 'End'])
                e.generate, e.precheck = MagicMock(side_effect=actions), MagicMock(return_value='Satisfied')
                def execute(script):
                    e.execution_attempts += 1
                    e.actions.append(script[0].removeprefix('<char0> '))
                    e.step += 1
                    return True
                e.execute = execute
                comm = MagicMock(last_graph=graph, last_path='g.json.gz', environment_graph=lambda: (True, graph))
                with patch.object(s.vh, 'connect', return_value=comm):
                    actual = e.run(None)
                self.assertEqual((actual['score_original_rule'], actual['outcome'], actual['actions']), expected)
                self.assertEqual([c.args[0] for c in e.generate.call_args_list], expected_prompts)
                self.assertEqual([c.args[1][1][1] for c in e.ask.call_args_list], expected_ends)

    def test_full_graph_known_empty_vs_extracted_unknown(self):
        graph = {'nodes': [{'id': 10, 'states': []}, {'id': 20, 'states': []}],
                 'edges': [{'from_id': 1, 'to_id': 10, 'relation_type': 'HOLDS_RH'},
                           {'from_id': 1, 'to_id': 20, 'relation_type': 'CLOSE'}]}
        self.assertEqual(s.full_symbolic('[PUTIN] <apple> (10) <box> (20)', graph)['label'], 'true')
        self.assertEqual(s.full_symbolic('[OPEN] <box> (20)', graph)['label'], 'false')
        self.assertEqual(s.full_symbolic('[OPEN] <box> (99)', graph)['label'], 'unknown')

    def test_budgeted_three_extra_calls_even_when_review_yes(self):
        for arm in ['C1_budgeted', 'C4_budgeted']:
            episode = object.__new__(s.Episode)
            episode.arm, episode.task = arm, {'task': 'Switch on the lamp'}
            episode.ask = MagicMock(side_effect=['Yes', 'Retain'])
            episode.regenerate = MagicMock(return_value='[SWITCHON] <lamp> (10)')
            episode.budgeted_revision(['p'] * 5, '[SWITCHON] <lamp> (10)', 'env')
            self.assertEqual(episode.ask.call_count, 2)
            episode.regenerate.assert_called_once()
            messages = str(episode.ask.call_args_list)
            if arm == 'C4_budgeted':
                self.assertNotIn('<lamp> (10) is OFF', messages)

    def test_retrieval_uses_frozen_repeat_and_none(self):
        episode = object.__new__(s.Episode)
        episode.kind, episode.task_id, episode.repeat = 'placement_task', 'test_task65', 2
        episode.log = MagicMock()
        episode.arm = 'R_none'
        self.assertEqual(episode.example('ignored'), '')
        episode.arm = 'R_random'
        self.assertTrue(episode.example('ignored').startswith('Example Task:'))
        row = episode.log.call_args.kwargs['selection']
        self.assertEqual(row['repeat'], '2')

    def test_c3_reextracts_and_saves_repaired_action(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(s, 'OUT', Path(directory)):
            root = Path(directory)
            s.vh.write(root / 'config.json', {})
            e = s.Episode({}, 'state_change_task', 'test_task6', 'C3_execution_feedback', s.vh.MODELS[0], 0, MagicMock(spent=0))
            e.config = {'host': 'mock', 'port': 0}
            e.initial = {}
            graph = {'nodes': [{'id': i, 'states': ['ON']} for i in [71, 173, 261, 427]], 'edges': []}
            comm = MagicMock(last_graph=graph, last_path='g.json.gz')
            comm.environment_graph.return_value = (True, graph)
            e.initialize = MagicMock()
            e.knowledge = MagicMock()
            e.knowledge.extract_nouns.return_value = ['lightswitch']
            e.knowledge.return_nlp.side_effect = ['before', 'after failure', 'complete']
            e.extract = MagicMock(return_value=({}, {}))
            e.example = MagicMock(return_value='example')
            e.ask = MagicMock(side_effect=['Continue', 'End'])
            e.generate = MagicMock(return_value='[SWITCHON] <lightswitch> (173)')
            e.regenerate = MagicMock(return_value='[WALK] <lightswitch> (173)')
            e.folder.mkdir(parents=True)
            # connect creates an empty episode folder; pre-existing content is intentionally absent here.
            def execute(script):
                e.execution_attempts += 1
                if e.execution_attempts == 1:
                    with gzip.open(e.folder / 'simulator_rpc.jsonl.gz', 'wt') as f:
                        f.write(json.dumps({'request': {'action': 'render_script'}, 'response': {'success': False, 'message': 'not close'}}) + '\n')
                    return False
                e.actions.append(script[0].removeprefix('<char0> '))
                e.step += 1
                return True
            e.execute = execute
            with patch.object(s.vh, 'connect', return_value=comm):
                result = e.run(None)
            self.assertEqual(result['actions'], ['[WALK] <lightswitch> (173)'])
            self.assertEqual(result['execution_attempts'], 2)
            self.assertEqual(e.extract.call_count, 3)
            self.assertEqual(e.regenerate.call_args.args[0][3], 'after failure')


if __name__ == '__main__':
    unittest.main()
