"""Offline differential checks against inspected notebook functions; no TeX/API/VH."""
import ast
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import unittest

from export_implementation_appendix import notebook_functions

ROOT = Path(__file__).resolve().parents[1]
module_spec = importlib.util.spec_from_file_location('prompt_spec', ROOT / 'Paper/listings/prompt_spec.py')
spec = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(spec)


class History:
    def __init__(self):
        self.messages = []

    def add_user_message(self, text):
        self.messages.append(('user', text))

    def add_ai_message(self, text):
        self.messages.append(('assistant', text))


def original_templates(notebook):
    """Read roles/literals from actual ChatPromptTemplate calls, not the new specification."""
    result = {}
    for cell in json.loads((ROOT / notebook).read_text())['cells']:
        if cell['cell_type'] != 'code':
            continue
        for node in ast.parse(''.join(cell['source'])).body:
            if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
                continue
            call = node.value
            if isinstance(call.func, ast.Attribute) and call.func.attr == 'from_messages':
                result[node.targets[0].id] = [ast.literal_eval(x) if isinstance(x, ast.Tuple) else 'history'
                                              for x in call.args[0].elts]
    return result


class Chain:
    def __init__(self, template, responses, calls):
        self.template, self.responses, self.calls = template, list(responses), calls

    def invoke(self, data):
        messages = []
        for item in self.template:
            if item == 'history':
                messages.extend(data['messages'])
            else:
                role, content = item
                messages.append((role, data['input'] if content == '{input}' else content))
        self.calls.append(messages)
        if not self.responses:
            raise AssertionError('Unexpected extra LLM call')
        return self.responses.pop(0)


class NotebookHarness:
    def __init__(self, mode, end_outputs, generated, pc_outputs=(), other_outputs=(), execute=True, ref_length=3):
        name = 'single-prompt.ipynb' if mode == 'single' else 'multi-prompts.ipynb'
        names = ['run', 'precondition_checking', 'regeneration', 'fewshot_prompt_generation']
        if mode == 'multi':
            names.append('action_step_generation')
        source = notebook_functions(name, names)
        templates = original_templates(name)
        self.calls, self.executed = [], []
        self.env = (ROOT / 'Paper/listings/knowledge_example_state.txt').read_text()
        self.task = {'task': 'Turn on all lightswitches', 'scene': 1, 'initial_room': 'kitchen',
                     'initial_states': [], 'action_scripts': ['reference'] * ref_length,
                     'goal_states': [{'id': 9002, 'states': ['ON']}]}
        self.example_name = 'Turn on all tablelamps'
        self.example_script = ['[WALK] <tablelamp> (9010)', '[SWITCHON] <tablelamp> (9010)']
        self.pc = json.loads((ROOT / 'precondition.json').read_text())
        regular = []
        if mode == 'single':
            generated = list(generated)
            for end in end_outputs:
                regular.append(end)
                if generated:
                    regular.append(generated.pop(0))
            chat_responses = list(other_outputs)
        else:
            regular = list(end_outputs)
            chat_responses = list(generated) + list(other_outputs)
        chat_name = 'chat_prompt' if mode == 'single' else 'multi_prompt'
        chat = Chain(templates[chat_name], chat_responses, self.calls)
        self.graph_reads = 0

        def graph():
            self.graph_reads += 1
            return True, {'nodes': [{'id': 9002, 'states': ['ON']}], 'edges': []}

        class Comm:
            environment_graph = staticmethod(graph)

        def simulation(script):
            self.executed.extend(script)
            return execute

        allowed = None
        for cell in json.loads((ROOT / name).read_text())['cells']:
            if cell['cell_type'] != 'code':
                continue
            for node in ast.parse(''.join(cell['source'])).body:
                if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) and node.targets[0].id == 'allowed_actions':
                    allowed = ast.literal_eval(node.value)
        self.ns = {'ChatMessageHistory': History, 'preconditions': self.pc, 'allowed_actions': allowed,
                   'chain': Chain(templates['llm_prompt'], regular, self.calls),
                   'pc_chain': Chain(templates['pc_prompt'], pc_outputs, self.calls),
                   'chat_chain': chat, 'multi_chain': chat, 'comm': Comm(),
                   'environment_initialization': lambda *args: None,
                   'extract_nouns': lambda text: [], 'extract_environment_knowledge': lambda objects: ({}, {}),
                   'return_nlp': lambda a, b: self.env, 'unity_simulation': simulation,
                   'sentence_cosine_similarity': lambda task: [self.example_name],
                   'example_scripts': {self.example_name: [['short'], self.example_script]}}
        # Execute only explicitly selected functions; notebook initialization/imports are not executed.
        exec(compile('\n\n'.join(source.values()), name + ':selected_functions', 'exec'), self.ns)

    def run(self, precheck=True):
        return self.ns['run'](self.task, not precheck)

    def example(self):
        return spec.example_text(self.example_name, self.example_script)


class PromptParityTests(unittest.TestCase):
    def test_full_messages_and_success_history(self):
        actions = ['[WALK] <lightswitch> (9002)', '[SWITCHON] <lightswitch> (9002)']
        for mode in ('single', 'multi'):
            for precheck in (False, True):
                with self.subTest(mode=mode, precheck=precheck):
                    h = NotebookHarness(mode, ['Continue', 'Continue', 'End'], actions, ['Yes', 'Yes'])
                    self.assertEqual(h.run(precheck), (1.0, 'Success', actions))
                    expected, history = [], []
                    for action in actions:
                        expected += [spec.end_messages(mode, h.task['task'], h.env),
                                     spec.generation_messages(mode, h.task['task'], h.env, h.example(), history)]
                        if precheck:
                            expected.append(spec.check_messages(h.env, spec.bind_conditions(action, h.pc)))
                        history = history + [action]
                    expected.append(spec.end_messages(mode, h.task['task'], h.env))
                    self.assertEqual(h.calls, expected)

    def test_unmet_condition_feedback_and_single_regeneration(self):
        action = '[SWITCHON] <lightswitch> (9002)'
        replacement = '[WALK] <lightswitch> (9002)'
        unmet = 'You are not close to the lightswitch.'
        for mode in ('single', 'multi'):
            with self.subTest(mode=mode):
                h = NotebookHarness(mode, ['Continue', 'End'], [action], ['No'], [unmet, replacement])
                self.assertEqual(h.run(), (1.0, 'Success', [replacement]))
                conditions = spec.bind_conditions(action, h.pc)
                expected = [spec.end_messages(mode, h.task['task'], h.env),
                            spec.generation_messages(mode, h.task['task'], h.env, h.example(), []),
                            spec.check_messages(h.env, conditions),
                            spec.unmet_messages(h.env, conditions, 'No'),
                            spec.regeneration_messages(mode, h.task['task'], h.env, h.example(), [], action,
                                                       spec.feedback(action, unmet)),
                            spec.end_messages(mode, h.task['task'], h.env)]
                self.assertEqual(h.calls, expected)
                self.assertEqual(len(h.executed), 1)  # No post-regeneration check call.

    def test_unknown_operation_feedback(self):
        action, replacement = '[FLY] <lightswitch> (9002)', '[WALK] <lightswitch> (9002)'
        for mode in ('single', 'multi'):
            h = NotebookHarness(mode, ['Continue', 'End'], [action], [], [replacement])
            self.assertEqual(h.run(), (1.0, 'Success', [replacement]))
            self.assertEqual(h.calls[2], spec.regeneration_messages(
                mode, h.task['task'], h.env, h.example(), [], action, spec.feedback(action)))
            self.assertEqual(len(h.calls), 4)

    def test_binding_all_eight_operations(self):
        pc = json.loads((ROOT / 'precondition.json').read_text())
        for mode in ('single', 'multi'):
            for operation in pc:
                action = f'[{operation}] <plum> (9012)'
                if operation in ('PUT', 'PUTIN'):
                    action += ' <fridge> (9014)'
                h = NotebookHarness(mode, [], [], ['Yes'])
                self.assertEqual(h.ns['precondition_checking'](action, h.env), 'Satisfied')
                self.assertEqual(h.calls, [spec.check_messages(h.env, spec.bind_conditions(action, pc))])


class StoppingTests(unittest.TestCase):
    def test_zero_length_end_does_not_read_goal_graph(self):
        for mode in ('single', 'multi'):
            h = NotebookHarness(mode, ['End'], [], ref_length=0)
            self.assertEqual(h.run(), (1.0, 'Success', []))
            self.assertEqual(h.graph_reads, 0)

    def test_zero_length_continue_stops_without_action(self):
        h = NotebookHarness('multi', ['Continue'], [], ref_length=0)
        self.assertEqual(h.run(), (0.0, 'Reaching Maximum Attempts', []))
        self.assertFalse(h.executed)

    def test_exact_upper_bound_stops_before_end_check(self):
        actions = ['[WALK] <lightswitch> (9002)'] * 2
        h = NotebookHarness('single', ['Continue', 'Continue'], actions, ref_length=1)
        self.assertEqual(h.run(False), (0.0, 'Reaching Maximum Attempts', actions))
        self.assertEqual(h.graph_reads, 0)

    def test_failed_execution_not_saved(self):
        h = NotebookHarness('multi', ['Continue'], ['[WALK] <lightswitch> (9002)'], execute=False)
        self.assertEqual(h.run(False), (0.0, 'Execution Failure', []))
        self.assertEqual(len(h.executed), 1)

    def test_end_whitespace_is_not_trimmed(self):
        action = '[WALK] <lightswitch> (9002)'
        h = NotebookHarness('multi', ['End\n'], [action], ref_length=0)
        self.assertEqual(h.run(False), (0.0, 'Reaching Maximum Attempts', [action]))

    def test_yes_is_substring_not_strict_boolean(self):
        h = NotebookHarness('single', [], [], ['Not Yes'])
        self.assertEqual(h.ns['precondition_checking']('[WALK] <lightswitch> (9002)', h.env), 'Satisfied')


class ManuscriptTests(unittest.TestCase):
    def test_listings_match_dataset_except_comment(self):
        text = (ROOT / 'Paper/sec5.tex').read_text()
        for label, kind, key in [('state-change-task', 'state_change_task', 'test_task6'),
                                 ('placement-task', 'placement_task', 'test_task65')]:
            match = re.search(r'\\begin\{lstlisting\}\[[^\]]*label=' + label + r'\]\s*(.*?)\\end\{lstlisting\}', text, re.S)
            self.assertIsNotNone(match)
            listed = json.loads(match[1])
            data = json.loads((ROOT / 'dataset' / kind / 'test.json').read_text())[key]
            self.assertEqual(listed, {k: v for k, v in data.items() if k != 'comment'})

    def test_all_object_counts_in_table(self):
        text = (ROOT / 'Paper/sec5.tex').read_text()
        with (ROOT / 'Paper/analysis/dataset_dimension_counts.csv').open() as handle:
            for row in csv.DictReader(handle):
                if row['split'] == 'all' and row['dimension'] in ('object', 'destination') and row['value']:
                    self.assertIn(f"{row['value']} ({row['n']})", text)

    def test_reference_targets_and_environments(self):
        files = []
        def visit(path):
            if path in files:
                return
            files.append(path)
            source = re.sub(r'(?m)^\s*%.*$', '', path.read_text())
            for name in re.findall(r'\\input\{([^}]+)\}', source):
                child = ROOT / 'Paper' / name
                visit(child if child.suffix else child.with_suffix('.tex'))
        visit(ROOT / 'Paper/main.tex')
        text = '\n'.join(re.sub(r'(?m)^\s*%.*$', '', p.read_text()) for p in files)
        labels = re.findall(r'\\label\{([^}]+)\}', text)
        labels += re.findall(r'\blabel\s*=\s*([A-Za-z0-9:._-]+)', text)
        self.assertEqual(len(labels), len(set(labels)))
        for ref in re.findall(r'\\(?:eqref|ref)\{([^}]+)\}', text):
            self.assertIn(ref, labels)
        for path in re.findall(r'\\(?:input|includegraphics|lstinputlisting)(?:\[[^\]]*\])?\{([^}]+)\}', text):
            resolved = ROOT / 'Paper' / path
            self.assertTrue(resolved.exists() or resolved.with_suffix('.tex').exists(), path)
        for p in files:
            source = re.sub(r'(?m)^\s*%.*$', '', p.read_text())
            stack = []
            for marker, name in re.findall(r'\\(begin|end)\{([^}]+)\}', source):
                if marker == 'begin':
                    stack.append(name)
                else:
                    self.assertTrue(stack, str(p))
                    self.assertEqual(stack.pop(), name, str(p))
            self.assertEqual(stack, [], str(p))

    def test_original_experiment_inputs_unchanged(self):
        with (ROOT / 'Paper/analysis/source_manifest.csv').open() as handle:
            for row in csv.DictReader(handle):
                if not row['path'].startswith('Paper/'):
                    self.assertEqual(hashlib.sha256((ROOT / row['path']).read_bytes()).hexdigest(), row['sha256'])


if __name__ == '__main__':
    unittest.main()
