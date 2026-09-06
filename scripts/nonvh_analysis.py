"""Reproducible static component benchmark; no simulator, network or credentials."""
import copy
import csv
import hashlib
import importlib.util
import json
import random
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'Paper/nonvh'
MODELS = ['gpt-4o-mini-2024-07-18', 'gpt-4o-2024-08-06']


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


PROMPT = module('prompt_spec', ROOT / 'Paper/listings/prompt_spec.py')
SERIAL = module('serializer', ROOT / 'Paper/listings/knowledge_serialization.py')
PC = json.loads((ROOT / 'precondition.json').read_text())
NAMES = {101: 'apple', 102: 'fridge', 103: 'lightswitch', 104: 'kitchentable', 900: 'kitchen'}
SERIAL.objId_dic = NAMES
SERIAL.objProp_dic = {i: (['CONTAINERS'] if i == 102 else []) for i in NAMES}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(name, obj):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')


def csvsave(name, rows):
    if not rows:
        return
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / name).open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def action(op):
    ids = {'WALK': [101], 'GRAB': [101], 'SWITCHON': [103], 'SWITCHOFF': [103],
           'OPEN': [102], 'CLOSE': [102], 'PUT': [101, 104], 'PUTIN': [101, 102]}[op]
    return f'[{op}] ' + ' '.join(f'<{NAMES[i]}> ({i})' for i in ids)


def evaluate(action_text, facts):
    """Only the eight JSON conditions, not VH executability. Unknown is distinct."""
    match = re.fullmatch(r'\[([A-Z]+)\] <([^<>]+)> \((\d+)\)(?: <([^<>]+)> \((\d+)\))?', action_text)
    if not match or match[1] not in PC:
        return {'label': 'invalid_format', 'violations': [], 'atoms': []}
    op, first = match[1], int(match[3])
    second = int(match[5]) if match[5] else None
    if (op in ('PUT', 'PUTIN')) != (second is not None):
        return {'label': 'invalid_format', 'violations': [], 'atoms': []}
    for i, name in [(first, match[2])] + ([(second, match[4])] if second else []):
        if NAMES.get(i) != name or str(i) not in facts['states']:
            return {'label': 'invalid_object', 'violations': [], 'atoms': []}
    def member(field, obj, neg=False):
        values = facts.get(field)
        return None if values is None else ((obj not in values) if neg else (obj in values))
    def state(obj, value, neg=False):
        values = facts['states'].get(str(obj))
        return None if not values else ((value not in values) if neg else (value in values))
    atoms = {
        'WALK': lambda: [member('held', first, True)],
        'GRAB': lambda: [member('close', first), member('held', first, True)],
        'SWITCHON': lambda: [member('close', first), state(first, 'OFF')],
        'SWITCHOFF': lambda: [member('close', first), state(first, 'ON')],
        'OPEN': lambda: [member('close', first), state(first, 'CLOSED')],
        'CLOSE': lambda: [member('close', first), state(first, 'OPEN')],
        'PUT': lambda: [member('held', first), member('close', second)],
        'PUTIN': lambda: [member('held', first), member('close', second), state(second, 'CLOSED', True)],
    }[op]()
    label = 'false' if False in atoms else 'unknown' if None in atoms else 'true'
    conditions = PROMPT.bind_conditions(action_text, PC).splitlines()[1:]
    return {'label': label, 'atoms': atoms,
            'violations': [condition for condition, value in zip(conditions, atoms) if value is False]}


def environment(facts, omit_location=None):
    objects = {i: {'states': facts['states'][str(i)] or [], 'on': None, 'inside': None,
                    'location': None if i == omit_location else 900, 'hold': []}
               for i in NAMES if i != 900}
    held = facts['held'] or []
    agent = {'location': 900, 'hold_rh': held[0] if held else None,
             'hold_lh': held[1] if len(held) > 1 else None, 'close_to': facts['close'] or []}
    return SERIAL.return_nlp(objects, agent)


def precondition_cases():
    cases = []
    for op in PC:
        facts = {'states': {'101': [], '102': ['CLOSED'], '103': ['OFF'], '104': []},
                 'held': [], 'close': [101, 102, 103, 104]}
        if op == 'SWITCHOFF':
            facts['states']['103'] = ['ON']
        if op in ('CLOSE', 'PUTIN'):
            facts['states']['102'] = ['OPEN']
        if op in ('PUT', 'PUTIN'):
            facts['held'] = [101]
        variants = [('valid', facts, 'true')]
        count = len(PC[op].splitlines()) - 1
        for atom in range(count):
            bad = copy.deepcopy(facts)
            if op == 'WALK' or (op == 'GRAB' and atom == 1):
                bad['held'] = [101]
            elif op in ('PUT', 'PUTIN') and atom == 0:
                bad['held'] = []
            elif (op in ('PUT', 'PUTIN') and atom == 1) or atom == 0:
                bad['close'] = []
            else:
                obj = '103' if op.startswith('SWITCH') else '102'
                inverse = {'OFF': 'ON', 'ON': 'OFF', 'CLOSED': 'OPEN', 'OPEN': 'CLOSED'}
                bad['states'][obj] = [inverse[bad['states'][obj][0]]]
            variants.append((f'violate_{atom + 1}', bad, 'false'))
        if op in ('SWITCHON', 'SWITCHOFF', 'OPEN', 'CLOSE'):
            missing = copy.deepcopy(facts)
            missing['states']['103' if op.startswith('SWITCH') else '102'] = None
            variants.append(('unknown', missing, 'unknown'))
        for variant, state, expected in variants:
            evaluation = evaluate(action(op), state)
            assert evaluation['label'] == expected, (op, variant)
            env = environment(state)
            cases.append({'id': f'pc_{op}_{variant}', 'kind': 'precondition', 'origin': 'synthetic',
                          'operation': op, 'variant': variant, 'facts': state, 'env': env,
                          'action': action(op), 'gold': expected, 'oracle': evaluation,
                          'messages': PROMPT.check_messages(env, PROMPT.bind_conditions(action(op), PC))})
    return cases


def end_cases():
    data = json.loads((ROOT / 'dataset/state_change_task/test.json').read_text())
    cases, seen = [], set()
    for key, row in data.items():
        states = {s['id']: s['states'] for s in row['initial_states']}
        complete = all(states.get(s['id']) == s['states'] for s in row['goal_states'])
        group = (row['task'], complete)
        if group in seen:
            continue
        seen.add(group)
        # A new explicit state-only representation, NOT the missing historical graph.
        name = row['task'].split()[-1]
        env = 'The current states in the home are as follows: \n' + ''.join(
            f'The {name} ({i}) is {s[0]}.\n' for i, s in states.items())
        cases.append({'id': f'end_state_{key}', 'kind': 'termination', 'origin': 'dataset_state_only',
                      'task_id': key, 'task': row['task'], 'initial_states': row['initial_states'],
                      'goal_states': row['goal_states'], 'gold': 'End' if complete else 'Continue',
                      'env': env, 'messages': PROMPT.end_messages('multi', row['task'], env)})
    for idx, (relations, closed) in enumerate([(['INSIDE', 'INSIDE'], False),
                                               (['INSIDE', 'ON'], False),
                                               (['ON', 'ON'], False),
                                               (['INSIDE', 'INSIDE'], True)]):
        env = 'The current states in the home are as follows: \n' + ''.join(
            f'The apple ({i}) is {rel} the fridge (102).\n' for i, rel in zip([101, 105], relations))
        env += f'The fridge (102) is {"CLOSED" if closed else "OPEN"}.\n'
        task = 'Put all apples in the fridge'
        cases.append({'id': f'end_placement_{idx}', 'kind': 'termination', 'origin': 'synthetic',
                      'task': task, 'relations': relations, 'fridge_closed': closed,
                      'gold': 'End' if all(r == 'INSIDE' for r in relations) else 'Continue',
                      'env': env, 'messages': PROMPT.end_messages('multi', task, env)})
    return cases


def retrieval():
    scores = json.loads((ROOT / 'Paper/analysis/retrieval_scores.json').read_text())['pairs']
    lookup = {(r['task_type'], r['test_task_name'], r['example_task_name']): r['cosine'] for r in scores}
    inventory = list(csv.DictReader((ROOT / 'Paper/analysis/task_inventory.csv').open()))
    meta = {(r['task_type'], r['task_name']): r for r in inventory}
    rows = []
    for kind in ['state_change_task', 'placement_task']:
        examples = json.loads((ROOT / f'dataset/{kind}/example.json').read_text())
        tests = json.loads((ROOT / f'dataset/{kind}/test.json').read_text())
        names = sorted({r['task'] for r in examples.values()})
        longest = {name: max([(k, r) for k, r in examples.items() if r['task'] == name],
                            key=lambda pair: len(pair[1]['action_scripts'])) for name in names}
        for key, row in tests.items():
            semantic = max(names, key=lambda n: lookup[kind, row['task'], n])
            for policy in ['semantic', 'random', 'fixed', 'none']:
                for rep in (range(3) if policy == 'random' else [0]):
                    seed = int(hashlib.sha256(f'20260906/{kind}/{key}/{rep}'.encode()).hexdigest()[:16], 16)
                    name = {'semantic': semantic, 'random': random.Random(seed).choice(names),
                            'fixed': names[0], 'none': ''}[policy]
                    eid, example = longest[name] if name else ('', None)
                    base = meta[kind, row['task']]
                    other = meta[kind, name] if name else None
                    rows.append({'task_type': kind, 'task_id': key, 'task': row['task'], 'policy': policy,
                                 'repeat': rep, 'seed': seed if policy == 'random' else '',
                                 'example_id': eid, 'example_task': name,
                                 'cosine': lookup[kind, row['task'], name] if name else '',
                                 'example_length': len(example['action_scripts']) if example else 0,
                                 'example_chars': len(PROMPT.example_text(name, example['action_scripts'])) if example else 0,
                                 'same_object': int(base['object'] == other['object']) if other else '',
                                 'same_operation': int(base['operation'] == other['operation']) if other else '',
                                 'same_destination': int(base['destination'] == other['destination']) if other and base['destination'] else ''})
    csvsave('retrieval_selections.csv', rows)
    groups = defaultdict(list)
    for r in rows:
        groups[r['task_type'], r['policy'], r['repeat']].append(r)
    summary = []
    for (kind, policy, rep), group in groups.items():
        item = {'task_type': kind, 'policy': policy, 'repeat': rep, 'n': len(group)}
        for field in ['cosine', 'example_length', 'example_chars', 'same_object', 'same_operation', 'same_destination']:
            vals = [r[field] for r in group if r[field] != '']
            item['mean_' + field] = sum(vals) / len(vals) if vals else ''
        summary.append(item)
    csvsave('retrieval_summary.csv', summary)
    # Outcome-blind quantile selection; author packet, not a completed human study.
    packet = []
    for kind in ['state_change_task', 'placement_task']:
        candidates = sorted([r for r in inventory if r['task_type'] == kind and r['split'] == 'test'],
                            key=lambda r: (int(r['reference_length']), int(r['goal_count']),
                                           int(r['scene']), int(r['task_id'].replace('test_task', ''))))
        for i in range(12):
            selected = candidates[round(i * (len(candidates) - 1) / 11)]
            packet.append({**selected, 'selection': '12 equally spaced length-order quantiles; outcome-blind',
                           'graph_available': False, 'human_completed': False})
    csvsave('human_case_selection_author_only.csv', packet)
    csvsave('human_labels_blank.csv', [{'task_type': r['task_type'], 'task_id': r['task_id'],
             'participant_id': '', 'experience': '', 'elapsed_seconds': '', 'actions': '',
             'termination': '', 'vh_verified': '', 'notes': ''} for r in packet])


def prepare():
    cases = precondition_cases() + end_cases()
    save('cases.json', cases)
    csvsave('gold_labels.csv', [{'id': r['id'], 'kind': r['kind'], 'origin': r['origin'], 'gold': r['gold']}
                              for r in cases])
    retention = []
    for r in cases:
        if r['kind'] != 'precondition' or r['variant'] != 'valid' or r['operation'] not in ('SWITCHON', 'SWITCHOFF', 'OPEN', 'CLOSE'):
            continue
        target = 103 if r['operation'].startswith('SWITCH') else 102
        for missing in [False, True]:
            env = environment(r['facts'], target if missing else None)
            state = r['facts']['states'][str(target)][0]
            retention.append({'id': r['id'], 'missing_location': missing, 'target_id': target,
                              'required_state': state, 'state_text_retained': f'({target}) is {state}' in env,
                              'env': env, 'origin': 'synthetic_serializer_unit_probe'})
    csvsave('serialization_probes.csv', retention)
    retrieval()
    sources = [ROOT / 'scripts/nonvh_analysis.py', ROOT / 'precondition.json',
               ROOT / 'Paper/listings/prompt_spec.py', ROOT / 'Paper/listings/knowledge_serialization.py',
               ROOT / 'Paper/analysis/retrieval_scores.json', ROOT / 'Paper/analysis/task_inventory.csv']
    sources += list((ROOT / 'dataset').glob('*/*.json'))
    save('config.json', {'design': 'new_static_component_pilot_not_VH_reexecution', 'models': MODELS,
         'repeats': 3, 'temperature': 0, 'max_completion_tokens': 160,
         'max_estimated_usd': 2.0, 'automatic_retries': 0, 'case_count': len(cases),
         'repair_repeats': 1, 'repair_selection': 'violate_1 for each of eight operations',
         'repair_conditions': ['C0_fixed_candidate', 'C1_llm_feedback', 'C2_symbolic_feedback', 'C4_neutral_revision'],
         'prices_usd_per_million': {MODELS[0]: [0.15, 0.60], MODELS[1]: [2.50, 10.0]},
         'price_sources': ['https://developers.openai.com/api/docs/models/gpt-4o-mini',
                           'https://developers.openai.com/api/docs/models/gpt-4o'],
         'price_checked_date': '2026-09-06', 'source_sha256': {str(p.relative_to(ROOT)): digest(p) for p in sources},
         'cases_sha256': digest(OUT / 'cases.json'),
         'limits': ['Not task success rate', 'No historical graphs or actual trajectories recovered',
                    'Finite synthetic close/held sets use closed-world labeling; omitted states are unknown',
                    'No human participants', 'No VH executability labels', 'No novelty conclusion',
                    'C4 matches regeneration count, not total check/feedback calls or tokens',
                    'Original prompt builders; synthetic graph facts and new state-only text, not original runtime inputs']})
    print(f'Prepared {len(cases)} cases, offline retrieval policies and 24 author-only case selections.')


if __name__ == '__main__':
    prepare()
