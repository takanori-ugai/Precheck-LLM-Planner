"""Prospectively specified, repeated step-4 controls. Never rewrites previous pilots."""
import argparse
import copy
import csv
import gzip
import json
import random
import shutil
import time
from pathlib import Path

import vh_experiment as vh
from vh_fixed_initial import alignment

OUT = vh.ROOT / 'Paper/vh_step4'
REFERENCE = vh.ROOT / 'Paper/vh/fixed_initial'
ARMS = ['C0_no_precheck', 'C1_llm_precheck', 'C2_symbolic_precheck',
        'C3_execution_feedback', 'C1_budgeted', 'C4_budgeted', 'C5_full_graph',
        'R_random', 'R_fixed', 'R_none']
REPEATS = 3
NEUTRAL_REVIEW = 'Review whether this candidate is a sensible next step for the task. Reply Yes or No. Do not use a supplied precondition checklist.'
NEUTRAL_REASON = 'Briefly explain whether to retain or revise this candidate based on the task and current knowledge.'
CHECK_REASON = 'Briefly explain the satisfied, violated or unknown conditions. If all are satisfied, say so.'


def full_symbolic(action, graph):
    """Same eight JSON rules, evaluated on complete graph; not a VH oracle."""
    objects = {n['id']: {'states': n['states'] or ['__KNOWN_EMPTY_STATE_SET__']} for n in graph['nodes']}
    agent = {'close_to': [], 'hold_rh': None, 'hold_lh': None}
    for e in graph['edges']:
        if e['from_id'] == 1:
            if e['relation_type'] == 'CLOSE':
                agent['close_to'].append(e['to_id'])
            if e['relation_type'] in ('HOLDS_RH', 'HOLDS_LH'):
                agent['hold_rh' if e['relation_type'] == 'HOLDS_RH' else 'hold_lh'] = e['to_id']
    return vh.symbolic(action, objects, agent)


def prepare():
    config = copy.deepcopy(json.loads((REFERENCE / 'config.json').read_text()))
    config.update(design='step4_four_tasks_ten_conditions_three_repeats', arms=ARMS, repeats=REPEATS,
                  max_estimated_usd=5.0, output_directory=str(OUT.relative_to(vh.ROOT)))
    for key in ['notes', 'fixed_runner_sha256', 'base_runner_sha256', 'parent_config_sha256']:
        config.pop(key, None)
    sources = [Path(__file__), Path(vh.__file__), vh.ROOT / 'scripts/vh_fixed_initial.py',
               vh.ROOT / 'scripts/nonvh_analysis.py', vh.ROOT / 'scripts/run_nonvh_api.py',
               vh.ROOT / 'Paper/nonvh/retrieval_selections.csv', REFERENCE / 'config.json']
    refs = [REFERENCE / 'runs' / f'{k}_{t}_reference_reference/result.json' for k, t in vh.SELECTED]
    sources += refs
    config['source_sha256'].update({str(p.relative_to(vh.ROOT)): vh.digest(p) for p in sources})
    config['reference_outcomes'] = {f'{k}/{t}': json.loads(p.read_text())['outcome'] for (k, t), p in zip(vh.SELECTED, refs)}
    config['protocol'] = {
        'reference_failures': 'Retain all four tasks, report successful-reference subset separately',
        'initialization': 'Same fixed positions as prior pilot; compare to its reference before any API request',
        'C3': 'No precheck; one repair after a returned VH failure per decision; reextract changed state; count failed executions against 2L total execution budget; not CAPE reproduction',
        'C1_budgeted_C4_budgeted': 'Each nonterminal decision: generate + review + reason + regenerate, always; 4 calls each capped at 256 output tokens; input/actual output tokens NOT matched; separate from original C1',
        'C5': 'Only checker reads full graph. Same JSON rules and regeneration/planner knowledge as C2; known empty states are closed-world empty, not unknown. No geometry/affordance oracle',
        'retrieval': 'R_random/fixed/none use original C1; semantic baseline C1. Frozen nonvh selections, random repeat 0/1/2 shared across models',
        'budget': 'Original 2*reference length cap; C3 failed attempts consume it. Original zero-length and strict End rules retained',
        'ordering': 'Seed 20260907; shuffled task/model blocks per repeat and arms per block',
        'stop': 'No automatic API/VH retry; infrastructure errors separate; successful prior episodes skipped',
        'scope': 'Four diagnostic tasks, not all 415; no human/author confirmation implied'}
    rng = random.Random(20260907)
    schedule = []
    for repeat in range(REPEATS):
        blocks = [(kind, task, model) for kind, task in vh.SELECTED for model in vh.MODELS]
        rng.shuffle(blocks)
        for kind, task, model in blocks:
            order = ARMS.copy()
            rng.shuffle(order)
            schedule += [dict(kind=kind, task_id=task, model=model, arm=arm, repeat=repeat) for arm in order]
    config['schedule'] = schedule
    path = OUT / 'config.json'
    if path.exists():
        assert json.loads(path.read_text()) == config, 'Frozen experiment specification changed'
    else:
        vh.write(path, config)
        for p in sources:
            if p.suffix == '.py':
                target = OUT / 'sources' / f'{vh.digest(p)}.py'
                target.parent.mkdir(exist_ok=True)
                shutil.copy2(p, target)
    return config


class Episode(vh.Episode):
    def __init__(self, config, kind, task_id, arm, model, repeat, api):
        super().__init__(config, kind, task_id, arm, model, api)
        self.repeat = repeat
        self.run_id += f'_r{repeat}'
        self.folder = OUT / 'runs' / self.run_id

    def initialize(self, scene_num, initial_room, initial_states):
        add, render, attempt_id = self.comm.add_character, self.comm.render_script, vh.utc()
        self.comm.add_character = lambda resource, initial_room: add(resource, position=self.config['fixed_positions'][f'{self.kind}/{self.task_id}'])
        def short_render(*args, **kwargs):
            kwargs['file_name_prefix'] = 'vs4_' + vh.object_hash([self.run_id, attempt_id])[:16] + f'_{self.execution_attempts:03d}'
            self.log('recording_name', remote_prefix=kwargs['file_name_prefix'])
            return render(*args, **kwargs)
        self.comm.render_script = short_render
        try:
            super().initialize(scene_num, initial_room, initial_states)
        finally:
            self.comm.add_character = add
        folder = REFERENCE / 'runs' / f'{self.kind}_{self.task_id}_reference_reference'
        ref = json.loads((folder / 'result.json').read_text())
        with gzip.open(folder / ref['initial']['graph_file'], 'rt') as f:
            check = alignment(self.initial_graph, json.load(f))
        self.log('initial_alignment', **check)
        if not check['passed']:
            raise RuntimeError('Initial alignment failed before API')

    def example(self, name):
        if not self.arm.startswith('R_'):
            return super().example(name)
        policy = self.arm[2:]
        with (vh.ROOT / 'Paper/nonvh/retrieval_selections.csv').open() as f:
            row = next(r for r in csv.DictReader(f) if r['task_type'] == self.kind and r['task_id'] == self.task_id
                       and r['policy'] == policy and int(r['repeat']) == (self.repeat if policy == 'random' else 0))
        self.log('retrieval', selection=row)
        if policy == 'none':
            return ''
        example = json.loads((vh.ROOT / f'dataset/{self.kind}/example.json').read_text())[row['example_id']]
        return vh.PROMPT.example_text(example['task'], example['action_scripts'])

    def precheck(self, action, env):
        if self.arm == 'C5_full_graph':
            conditions = vh.PROMPT.bind_conditions(action, vh.PC)
            if conditions is None:
                return 'Incorrect output format'
            result = full_symbolic(action, self.comm.last_graph)
            self.log('full_graph_precheck', action=action, result=result, graph_file=self.comm.last_path)
            if result['label'] == 'true':
                return 'Satisfied'
            return vh.PROMPT.feedback(action, '\n'.join(result['violations'] + result.get('unknown_conditions', [])))
        return super().precheck(action, env)

    def budgeted_revision(self, prompts, action, env):
        if self.arm == 'C1_budgeted':
            conditions = vh.PROMPT.bind_conditions(action, vh.PC)
            review_messages = vh.PROMPT.check_messages(env, conditions) if conditions else [
                ('system', vh.PROMPT.SYSTEM), ('user', env + '\nCandidate: ' + action + '\nCheck the output format. Reply Yes or No.')]
            reason_prompt = CHECK_REASON
        else:
            review_messages = [('system', vh.PROMPT.SYSTEM), ('user', env + '\nTask: ' + self.task['task'] + '\nCandidate: ' + action + '\n' + NEUTRAL_REVIEW)]
            reason_prompt = NEUTRAL_REASON
        review = self.ask('budget_review', review_messages)
        explanation = self.ask('budget_reason', review_messages + [('assistant', review), ('user', reason_prompt)])
        return self.regenerate(prompts, action, explanation)

    def run(self, nlp, retry_incomplete=False):
        path = self.folder / 'result.json'
        if path.exists():
            return json.loads(path.read_text())
        if self.folder.exists() and any(self.folder.iterdir()):
            if not retry_incomplete or not (self.folder / 'infrastructure_error.json').exists():
                raise RuntimeError('Incomplete episode preserved; restore VH before explicit retry')
            target = OUT / 'interrupted' / f'{self.run_id}_{time.time_ns()}'
            target.parent.mkdir(exist_ok=True)
            shutil.move(str(self.folder), str(target))
        self.comm = vh.connect(self.config['host'], self.config['port'], self.folder)
        import inflection
        self.knowledge.comm, self.knowledge.nlp, self.knowledge.i = self.comm, nlp, inflection
        start = time.monotonic()
        try:
            self.initialize(self.task['scene'], self.task['initial_room'], self.task['initial_states'])
            nouns, example = self.knowledge.extract_nouns(self.task['task']), self.example(self.task['task'])
            task_prompt = f'Generate a only next action step to complete the following task and output only that.\nTask: {self.task["task"]}\n'
            end_prompt = f'\nIf the following task has already completed based on the current status, output "End"; otherwise, output "Continue".\nTask: {self.task["task"]}\n'
            limit = 2 * len(self.task['action_scripts'])
            while True:
                objects, agent = self.extract(nouns)
                env = self.knowledge.return_nlp(objects, agent)
                decision = self.ask('termination', [('system', vh.PROMPT.SYSTEM), ('user', env + end_prompt)])
                if decision == 'End':
                    outcome = 'Success' if vh.goal(self.comm.last_graph, self.task)['all_satisfied'] else 'Erroneous Terminate'
                    break
                if decision == 'Continue' and limit == 0:
                    outcome = 'Reaching Maximum Attempts'
                    break
                prompts = ['You need to generate a next action step for completing a household task.\n', vh.PROMPT.ALLOWED,
                           example, env, task_prompt + f'Step{self.step}: ']
                action = self.generate(prompts)
                if self.arm in ('C1_budgeted', 'C4_budgeted'):
                    action = self.budgeted_revision(prompts, action, env)
                elif self.arm not in ('C0_no_precheck', 'C3_execution_feedback'):
                    reason = self.precheck(action, env)
                    if reason != 'Satisfied':
                        action = self.regenerate(prompts, action,
                            f"'{action}' is incorrect output format." if reason == 'Incorrect output format' else reason)
                success = self.execute(['<char0> ' + action])
                if not success and self.arm == 'C3_execution_feedback' and self.execution_attempts < limit:
                    failed = action
                    # Failed execution can change the scene; never repair against stale extracted knowledge.
                    objects, agent = self.extract(nouns)
                    prompts[3] = self.knowledge.return_nlp(objects, agent)
                    with gzip.open(self.folder / 'simulator_rpc.jsonl.gz', 'rt') as f:
                        rpc = [json.loads(line) for line in f]
                    error = next(r['response'] for r in reversed(rpc) if r['request']['action'] == 'render_script')
                    reason = 'The simulator returned failure for this action. The environment knowledge has been refreshed. Revise once.\n' + json.dumps(error, ensure_ascii=False)
                    self.log('execution_feedback', failed_action=failed, simulator_response=error, graph_file=self.comm.last_path)
                    action = self.regenerate(prompts, failed, reason)
                    success = self.execute(['<char0> ' + action])
                if not success:
                    outcome = 'Execution Failure'
                    break
                task_prompt += f'Step{self.step - 1}: {action}\n'
                if self.execution_attempts >= limit:
                    outcome = 'Reaching Maximum Attempts'
                    break
            final = self.comm.environment_graph()[1]
            result = dict(run_id=self.run_id, kind=self.kind, task_id=self.task_id, task=self.task['task'],
                arm=self.arm, model=self.model, repeat=self.repeat, outcome=outcome,
                score_original_rule=int(outcome == 'Success'), actions=self.actions,
                reference_length=len(self.task['action_scripts']), execution_attempts=self.execution_attempts,
                initial=self.initial, final_goal=vh.goal(final, self.task), final_graph=self.comm.last_path,
                elapsed_seconds=time.monotonic() - start, utc=vh.utc(), runner_sha256=vh.digest(Path(__file__)),
                config_sha256=vh.digest(OUT / 'config.json'))
            vh.write(path, result)
            print(f'{self.run_id}: {outcome}; API total ${self.api.spent:.5f}', flush=True)
            return result
        except Exception as exc:
            vh.write(self.folder / 'infrastructure_error.json', {'utc': vh.utc(), 'error_type': type(exc).__name__,
                'message': str(exc) if isinstance(exc, (RuntimeError, AssertionError)) else 'Details omitted'})
            raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--phase', choices=['prepare', 'run'], required=True)
    parser.add_argument('--retry-incomplete', action='store_true')
    args = parser.parse_args()
    vh.OUT = OUT
    config = prepare()
    if args.phase == 'prepare':
        print(f'Frozen {len(config["schedule"])} episodes before API work')
        return
    import spacy
    nlp = spacy.load('en_core_web_sm')
    api = vh.API(config)
    for spec in config['schedule']:
        Episode(config, api=api, **spec).run(nlp, args.retry_incomplete)
    print(f'Step 4 repeated controls complete: ${api.spent:.6f}', flush=True)


if __name__ == '__main__':
    main()
