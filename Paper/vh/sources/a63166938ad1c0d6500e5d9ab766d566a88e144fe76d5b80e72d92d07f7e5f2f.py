"""Logged VH pilot. Uses original Multi run() AST, never executes notebook setup/API cells."""
import argparse
import ast
import copy
import csv
import gzip
import hashlib
import importlib.metadata
import json
import platform
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from nonvh_analysis import ROOT, PC, PROMPT, MODELS, module, digest
from run_nonvh_api import load_key

OUT = ROOT / 'Paper/vh'
CLIENT = ROOT / '.vh-deps/virtualhome/virtualhome/simulation'
SELECTED = [('state_change_task', 'test_task1'), ('state_change_task', 'test_task6'),
            ('placement_task', 'test_task1'), ('placement_task', 'test_task65')]
ARMS = ['C0_no_precheck', 'C1_llm_precheck', 'C2_symbolic_precheck']


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def append(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a') as f:
        f.write(json.dumps(value, ensure_ascii=False) + '\n')


def utc():
    return datetime.now(timezone.utc).isoformat()


def object_hash(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def goal(graph, task):
    nodes = {n['id']: n for n in graph['nodes']}
    edges = {(e['from_id'], e['relation_type'], e['to_id']) for e in graph['edges']}
    labels = [nodes.get(g['id'], {}).get('states') == g['states'] if 'id' in g
              else (g['from_id'], g['relation_type'], g['to_id']) in edges for g in task['goal_states']]
    return {'all_satisfied': all(labels), 'per_goal': labels}


def comparable(graph):
    """Order-independent symbolic state, incl. avatar relations, excluding rendering metadata."""
    return {'nodes': sorted([(n['id'], n['class_name'], sorted(n['states']), sorted(n['properties']))
                             for n in graph['nodes']], key=lambda n: n[0]),
            'edges': sorted(set((e['from_id'], e['relation_type'], e['to_id']) for e in graph['edges']))}


def symbolic(action, objects, agent):
    """JSON-condition checker over extracted knowledge only; no simulator oracle claims."""
    try:
        parts = action.split(' ')
        op = parts[0][1:-1]
        if op not in PC:
            return {'label': 'invalid_format', 'atoms': [], 'violations': []}
        first = int(parts[2].strip('()'))
        second = int(parts[4].strip('()')) if len(parts) == 5 else None
        if (op in ('PUT', 'PUTIN')) != (second is not None):
            raise ValueError()
        def close(obj):
            return obj in agent['close_to'] if obj in objects else None
        def held(obj):
            return obj in [agent['hold_rh'], agent['hold_lh']]
        def state(obj, expected, negate=False):
            states = objects.get(obj, {}).get('states')
            if not states:
                return None
            return (expected not in states) if negate else (expected in states)
        atoms = {'WALK': lambda: [not held(first)],
                 'GRAB': lambda: [close(first), not held(first)],
                 'SWITCHON': lambda: [close(first), state(first, 'OFF')],
                 'SWITCHOFF': lambda: [close(first), state(first, 'ON')],
                 'OPEN': lambda: [close(first), state(first, 'CLOSED')],
                 'CLOSE': lambda: [close(first), state(first, 'OPEN')],
                 'PUT': lambda: [held(first), close(second)],
                 'PUTIN': lambda: [held(first), close(second), state(second, 'CLOSED', True)]}[op]()
        conditions = PROMPT.bind_conditions(action, PC).splitlines()[1:]
        return {'label': 'false' if False in atoms else 'unknown' if None in atoms else 'true',
                'atoms': atoms, 'violations': [c for c, a in zip(conditions, atoms) if a is False],
                'unknown_conditions': [c for c, a in zip(conditions, atoms) if a is None]}
    except (IndexError, TypeError, ValueError):
        return {'label': 'invalid_format', 'atoms': [], 'violations': []}


def prepare(host, port):
    OUT.mkdir(parents=True, exist_ok=True)
    files = [ROOT / 'multi-prompts.ipynb', ROOT / 'precondition.json',
             ROOT / 'Paper/listings/knowledge_extraction.py', ROOT / 'Paper/listings/prompt_spec.py',
             ROOT / 'Paper/analysis/retrieval_by_instance.csv'] + list((ROOT / 'dataset').glob('*/*.json'))
    sources = {str(p.relative_to(ROOT)): digest(p) for p in files}
    current = {'design': 'four_task_two_model_three_arm_one_repeat_VH_pilot', 'selected_tasks': SELECTED,
               'models': MODELS, 'arms': ARMS, 'repeats': 1, 'host': host, 'port': str(port),
               'temperature': 0, 'max_completion_tokens': 256, 'max_estimated_usd': 2.0,
               'find_solution': False, 'recording': True, 'camera_mode': ['PERSON_FROM_BACK'],
               'skip_animation': False, 'randomize_execution': False, 'time_scale': 1.0,
               'source_sha256': sources, 'client_commit': subprocess.check_output(
                    ['git', '-C', str(CLIENT.parents[1]), 'rev-parse', 'HEAD'], text=True).strip(),
               'client_files_sha256': {p.name: digest(p) for p in CLIENT.joinpath('unity_simulator').glob('*.py')},
               'python': platform.python_version(), 'platform': platform.platform(),
               'versions': {p: importlib.metadata.version(p) for p in ['spacy', 'en-core-web-sm', 'inflection', 'requests', 'numpy']},
               'remote_simulator_version': 'not independently retrieved; scene/ID compatibility tested',
               'local_reference_binary_sha256': digest(ROOT / 'VH/linux_exec.v2.3.0.x86_64'),
               'prices_usd_per_million': {MODELS[0]: [0.15, 0.6], MODELS[1]: [2.5, 10]},
               'notes': ['Original run() extracted without edits; C0/C1 use original branching and stop rules',
                         'New C2 symbolic checker uses same extracted knowledge; unknown triggers one repair',
                         'Frozen reconstructed MiniLM selections reused, not historical retrieval logs',
                         'Original fix_room avatar placement; full and symbolic initial hashes recorded',
                         'Original per-action recording retained; unique output prefix on remote host',
                         'No automatic retry of API or simulator requests',
                         'No C3/C4/C5, full-test benchmark, or human evaluation in this pilot']}
    path = OUT / 'config.json'
    if path.exists():
        assert json.loads(path.read_text()) == json.loads(json.dumps(current)), 'Frozen config changed'
    else:
        write(path, current)
    return current


def connect(host, port, folder):
    sys.path.insert(0, str(CLIENT))
    from unity_simulator.comm_unity import UnityCommunication
    class LoggedUnity(UnityCommunication):
        def post_command(self, request_dict, repeat=False):
            stamp, start = utc(), time.monotonic()
            req = urllib.request.Request(self._address, data=json.dumps(request_dict).encode(),
                                         headers={'Content-Type': 'application/json'})
            row = {'utc': stamp, 'request': request_dict}
            try:
                # No proxy and no retries for stateful simulator operations.
                with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=90) as response:
                    reply = json.loads(response.read())
                row['response'] = reply
            except Exception as exc:
                row.update(error_type=type(exc).__name__, elapsed_seconds=time.monotonic() - start)
                with gzip.open(folder / 'simulator_rpc.jsonl.gz', 'at') as f:
                    f.write(json.dumps(row) + '\n')
                raise RuntimeError('VH communication failure; do not retry a stateful request blindly') from exc
            row['elapsed_seconds'] = time.monotonic() - start
            with gzip.open(folder / 'simulator_rpc.jsonl.gz', 'at') as f:
                f.write(json.dumps(row) + '\n')
            return reply

        def environment_graph(self):
            success, graph = super().environment_graph()
            if not success:
                raise RuntimeError('environment_graph failed')
            self.last_graph = graph
            self.graph_index += 1
            self.last_path = f'graph_{self.graph_index:04d}.json.gz'
            with gzip.open(folder / self.last_path, 'wt') as f:
                json.dump(graph, f)
            return success, graph
    folder.mkdir(parents=True, exist_ok=True)
    comm = LoggedUnity(url=host, port=str(port), timeout_wait=90)
    comm.graph_index = 0
    return comm


class API:
    def __init__(self, config):
        self.config = config
        self.key = load_key()
        logs = OUT / 'api_log.jsonl'
        self.spent = sum(r.get('estimated_usd', r.get('reserved_usd', 0)) for r in
                         [json.loads(s) for s in logs.read_text().splitlines()]) if logs.exists() else 0

    def call(self, model, run_id, step, phase, messages):
        payload = {'model': model, 'messages': [{'role': role, 'content': text} for role, text in messages],
                   'temperature': 0, 'max_completion_tokens': 256, 'n': 1, 'store': False}
        inp, out = self.config['prices_usd_per_million'][model]
        reserve = ((len(json.dumps(payload).encode()) + 512) * inp + 256 * out) / 1e6
        if self.spent + reserve > self.config['max_estimated_usd']:
            raise RuntimeError('API pilot cost ceiling reached')
        row = {'utc': utc(), 'run_id': run_id, 'step': step, 'phase': phase, 'request': payload,
               'reserved_usd': reserve, 'runner_sha256': digest(Path(__file__))}
        req = urllib.request.Request('https://api.openai.com/v1/chat/completions',
                     data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json',
                                                              'Authorization': 'Bearer ' + self.key})
        start = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                result = json.loads(response.read())
                row['request_id'] = response.headers.get('x-request-id')
            usage = result['usage']
            cost = (usage['prompt_tokens'] * inp + usage['completion_tokens'] * out) / 1e6
            row.update(status='ok', response=result, estimated_usd=cost)
            self.spent += cost
        except Exception as exc:
            row.update(status='error', error_type=type(exc).__name__, http_status=getattr(exc, 'code', None))
            self.spent += reserve
        row['elapsed_seconds'] = time.monotonic() - start
        append(OUT / 'api_log.jsonl', row)
        if row['status'] != 'ok':
            raise RuntimeError(f'API failed: {row["error_type"]}, HTTP {row["http_status"]}; details redacted')
        return result['choices'][0]['message'].get('content') or ''


class Episode:
    def __init__(self, config, kind, task_id, arm, model, api=None):
        self.config, self.kind, self.task_id, self.arm, self.model, self.api = config, kind, task_id, arm, model, api
        self.task = json.loads((ROOT / f'dataset/{kind}/test.json').read_text())[task_id]
        self.run_id = f'{kind}_{task_id}_{arm}_{model or "reference"}'
        self.folder = OUT / 'runs' / self.run_id
        self.actions, self.step, self.execution_attempts = [], 1, 0
        self.knowledge = module('vh_knowledge', ROOT / 'Paper/listings/knowledge_extraction.py')

    def log(self, phase, **details):
        append(self.folder / 'events.jsonl', {'utc': utc(), 'step': self.step, 'phase': phase, **details})

    def initialize(self, scene_num, initial_room, initial_states):
        if not self.comm.reset(scene_num - 1):
            raise RuntimeError('Scene reset failed')
        graph = self.comm.environment_graph()[1]
        nodes = {n['id']: n for n in graph['nodes']}
        required = {g['id'] for g in self.task['goal_states'] if 'id' in g}
        for g in self.task['goal_states']:
            if 'from_id' in g:
                required.update([g['from_id'], g['to_id']])
        missing = required - nodes.keys()
        if missing:
            raise RuntimeError(f'Dataset IDs missing in VH: {sorted(missing)}')
        expected_names = {}
        for action_text in self.task['action_scripts']:
            expected_names.update({int(i): name for name, i in re.findall(r'<([^>]+)> \((\d+)\)', action_text)})
        mismatches = [{'id': i, 'dataset_class': name, 'vh_class': nodes.get(i, {}).get('class_name')}
                      for i, name in expected_names.items() if nodes.get(i, {}).get('class_name') != name]
        if mismatches:
            self.log('id_class_mismatch', mismatches=mismatches)
            raise RuntimeError('Dataset ID/class mismatch; no automatic remapping')
        for state in initial_states:
            if state['id'] not in nodes:
                raise RuntimeError('Initial state ID missing')
            nodes[state['id']]['states'] = state['states']
        expanded = self.comm.expand_scene(graph)
        self.log('expand_scene', result=expanded)
        if not expanded[0]:
            raise RuntimeError('expand_scene failed')
        if not self.comm.add_character('Chars/male1', initial_room=initial_room):
            raise RuntimeError('add_character failed')
        graph = self.comm.environment_graph()[1]
        actual = {n['id']: n for n in graph['nodes']}
        assert all(actual[s['id']]['states'] == s['states'] for s in initial_states), 'Initial states not applied'
        assert actual[1]['class_name'] == 'character', 'Original agent ID 1 assumption violated'
        self.knowledge.objId_dic = {n['id']: n['class_name'] for n in graph['nodes']}
        self.knowledge.objProp_dic = {n['id']: n['properties'] for n in graph['nodes']}
        self.initial = {'graph_file': self.comm.last_path, 'full_hash': object_hash(graph),
                        'symbolic_hash': object_hash(comparable(graph)),
                        'agent_transform': actual[1].get('obj_transform'), 'goal': goal(graph, self.task)}
        self.log('initial', **self.initial)
        self.initial_graph = copy.deepcopy(graph)

    def extract(self, nouns):
        self.objects, self.agent = self.knowledge.extract_environment_knowledge(nouns)
        self.log('extracted_knowledge', nouns=nouns, objects=self.objects, agent=self.agent,
                 graph_file=self.comm.last_path, goal=goal(self.comm.last_graph, self.task))
        return self.objects, self.agent

    def ask(self, phase, messages):
        response = self.api.call(self.model, self.run_id, self.step, phase, messages)
        self.log(phase, messages=messages, response=response)
        return response

    def example(self, name):
        with (ROOT / 'Paper/analysis/retrieval_by_instance.csv').open() as file:
            selected = next(r for r in csv.DictReader(file) if r['task_type'] == self.kind and r['task_id'] == self.task_id)
        row = json.loads((ROOT / f'dataset/{self.kind}/example.json').read_text())[selected['selected_example_id']]
        self.log('retrieval', selection=selected)
        return PROMPT.example_text(row['task'], row['action_scripts'])

    def generate(self, prompts):
        text = self.ask('generation', [('system', PROMPT.CHAT_SYSTEM)] + [('user', p) for p in prompts])
        self.log('candidate_diagnostic', action=text, json_conditions=symbolic(text, self.objects, self.agent))
        return text

    def precheck(self, action, env):
        conditions = PROMPT.bind_conditions(action, PC)
        if conditions is None:
            return 'Incorrect output format'
        if self.arm == 'C2_symbolic_precheck':
            label = symbolic(action, self.objects, self.agent)
            self.log('symbolic_precheck', action=action, result=label)
            if label['label'] == 'true':
                return 'Satisfied'
            if label['label'] == 'invalid_format':
                return 'Incorrect output format'
            explanation = '\n'.join(label['violations'] +
                         ['Cannot determine from the available knowledge: ' + c for c in label['unknown_conditions']])
            return PROMPT.feedback(action, explanation)
        response = self.ask('precondition', PROMPT.check_messages(env, conditions))
        if 'Yes' in response:
            return 'Satisfied'
        unmet = self.ask('unmet', PROMPT.unmet_messages(env, conditions, response))
        return PROMPT.feedback(action, unmet)

    def regenerate(self, prompts, action, reason):
        messages = [('system', PROMPT.CHAT_SYSTEM)] + [('user', p) for p in prompts]
        messages += [('assistant', action), ('user', reason), ('user', prompts[-1].replace('Generate', 'Regenerate'))]
        return self.ask('regeneration', messages)

    def execute(self, script):
        action = script[0].removeprefix('<char0> ')
        before = self.comm.environment_graph()[1]
        before_path = self.comm.last_path
        diagnostic = symbolic(action, self.objects, self.agent) if hasattr(self, 'objects') else None
        started = time.monotonic()
        self.execution_attempts += 1
        result = self.comm.render_script(script, find_solution=False, recording=True,
                    camera_mode=['PERSON_FROM_BACK'], file_name_prefix=f'precheck_pilot_{self.run_id}_step{self.step:03d}')
        after = self.comm.environment_graph()[1]
        self.log('execution', action=action, simulator_result=result, before_graph=before_path,
                 after_graph=self.comm.last_path, before_goal=goal(before, self.task), after_goal=goal(after, self.task),
                 json_conditions=diagnostic, elapsed_seconds=time.monotonic() - started)
        if result[0] is True:
            self.actions.append(action)
            self.step += 1
        print(f'{self.run_id}: action {self.execution_attempts}, VH={result[0]}', flush=True)
        return result[0]

    def run(self, nlp=None, retry_incomplete=False):
        result_path = self.folder / 'result.json'
        if result_path.exists():
            return json.loads(result_path.read_text())
        if self.folder.exists() and any(self.folder.iterdir()):
            if not retry_incomplete or not (self.folder / 'infrastructure_error.json').exists():
                raise RuntimeError(f'Incomplete prior episode at {self.folder}; preserved; restart VH and use --retry-incomplete')
            archived = OUT / 'interrupted' / f'{self.run_id}_{time.time_ns()}'
            archived.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(self.folder), str(archived))
        self.comm = connect(self.config['host'], self.config['port'], self.folder)
        self.knowledge.comm = self.comm
        start = time.monotonic()
        try:
            if self.arm == 'reference':
                self.initialize(self.task['scene'], self.task['initial_room'], self.task['initial_states'])
                for command in self.task['action_scripts']:
                    if not self.execute(['<char0> ' + command]):
                        break
                final = self.comm.environment_graph()[1]
                passed = len(self.actions) == len(self.task['action_scripts']) and goal(final, self.task)['all_satisfied']
                score, outcome = int(passed), 'Reference Success' if passed else 'Reference Failure'
            else:
                import inflection
                self.knowledge.nlp, self.knowledge.i = nlp, inflection
                episode = self
                class EndChain:
                    def invoke(self, args):
                        return episode.ask('termination', [('system', PROMPT.SYSTEM), ('user', args['input'])])
                ns = {'environment_initialization': self.initialize, 'extract_nouns': self.knowledge.extract_nouns,
                      'fewshot_prompt_generation': self.example, 'extract_environment_knowledge': self.extract,
                      'return_nlp': self.knowledge.return_nlp, 'chain': EndChain(), 'allowed_actions': PROMPT.ALLOWED,
                      'action_step_generation': self.generate, 'precondition_checking': self.precheck,
                      'regeneration': self.regenerate, 'unity_simulation': self.execute, 'comm': self.comm}
                notebook = json.loads((ROOT / 'multi-prompts.ipynb').read_text())
                tree = ast.parse(''.join(notebook['cells'][20]['source']))
                run_ast = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'run')
                exec(compile(ast.Module(body=[run_ast], type_ignores=[]), 'original_multi_run', 'exec'), ns)
                score, outcome, saved = ns['run'](self.task, self.arm == 'C0_no_precheck')
                assert saved == self.actions
                final = self.comm.environment_graph()[1]
            result = {'run_id': self.run_id, 'kind': self.kind, 'task_id': self.task_id, 'task': self.task['task'],
                      'arm': self.arm, 'model': self.model, 'score_original_rule': score, 'outcome': outcome,
                      'actions': self.actions, 'reference_length': len(self.task['action_scripts']),
                      'execution_attempts': self.execution_attempts, 'initial': self.initial,
                      'final_goal': goal(final, self.task), 'final_graph': self.comm.last_path,
                      'elapsed_seconds': time.monotonic() - start, 'runner_sha256': digest(Path(__file__)),
                      'utc': utc(), 'config_sha256': digest(OUT / 'config.json')}
            write(result_path, result)
            print(f'{self.run_id}: {outcome}, actual_goal={result["final_goal"]["all_satisfied"]}', flush=True)
            return result
        except Exception as exc:
            write(self.folder / 'infrastructure_error.json', {'utc': utc(), 'error_type': type(exc).__name__,
                  'message': str(exc) if isinstance(exc, (RuntimeError, AssertionError)) else 'Details omitted',
                  'actions': self.actions, 'execution_attempts': self.execution_attempts})
            raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--phase', choices=['probe', 'reference', 'compare'], required=True)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', default='8080')
    parser.add_argument('--retry-incomplete', action='store_true',
                        help='After restoring VH, archive an infrastructure-failed episode and restart it from reset')
    parser.add_argument('--allow-reference-failure', action='store_true',
                        help='Explicit diagnostic pilot only: retain completed reference failures instead of excluding them')
    args = parser.parse_args()
    config = prepare(args.host, args.port)
    if args.phase == 'probe':
        comm = connect(args.host, args.port, OUT / 'probe')
        # VH 2.3 may throw inside Unity and wedge its request queue if asked for
        # environment_graph before the first successful reset/environment load.
        # A connection probe must therefore use idle only, never a graph request.
        connected = comm.check_connection()
        write(OUT / 'probe/summary.json', {'utc': utc(), 'connected': connected,
              'graph_requested': False, 'note': 'Graph retrieval is only allowed after reset in an episode'})
        print(f'Connected: {connected}; no graph requested before scene initialization')
    elif args.phase == 'reference':
        for kind, task_id in SELECTED:
            result = Episode(config, kind, task_id, 'reference', None).run(retry_incomplete=args.retry_incomplete)
            if result['outcome'] != 'Reference Success':
                raise RuntimeError('Reference replay failed; planner experiments not started')
    else:
        reference_outcomes = {}
        for kind, task_id in SELECTED:
            path = OUT / 'runs' / f'{kind}_{task_id}_reference_reference/result.json'
            if not path.exists():
                raise RuntimeError('Complete all reference replays before API experiments')
            reference_outcomes[f'{kind}/{task_id}'] = json.loads(path.read_text())['outcome']
            if reference_outcomes[f'{kind}/{task_id}'] != 'Reference Success' and not args.allow_reference_failure:
                raise RuntimeError('Complete successful reference replay before API experiments')
        policy = {'allow_completed_reference_failures': args.allow_reference_failure,
                  'reference_outcomes': reference_outcomes,
                  'interpretation': 'Reference failures retained and reported separately; no claim all reference plans reproduced',
                  'action_name_conversion': False, 'runner_sha256': digest(Path(__file__))}
        policy_path = OUT / 'comparison_policy.json'
        if policy_path.exists():
            prior = json.loads(policy_path.read_text())
            assert prior['reference_outcomes'] == reference_outcomes
            assert prior['allow_completed_reference_failures'] == args.allow_reference_failure
        else:
            write(policy_path, policy)
        import spacy
        nlp = spacy.load('en_core_web_sm')
        api = API(config)
        for kind, task_id in SELECTED:
            for model in MODELS:
                for arm in ARMS:
                    Episode(config, kind, task_id, arm, model, api).run(nlp, retry_incomplete=args.retry_incomplete)
        print(f'VH pilot complete; cumulative estimated API cost ${api.spent:.6f}')


if __name__ == '__main__':
    main()
