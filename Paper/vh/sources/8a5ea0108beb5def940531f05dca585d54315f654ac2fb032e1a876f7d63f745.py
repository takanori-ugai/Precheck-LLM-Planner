"""Separate prospective VH pilot with fixed avatar positions; preserves original pilot."""
import argparse
import copy
import gzip
import json
import math
from pathlib import Path

import vh_experiment as vh

ORIGINAL = vh.ROOT / 'Paper/vh'
FIXED = ORIGINAL / 'fixed_initial'


def alignment(first, second):
    a, b = ({n['id']: n for n in g['nodes']} for g in [first, second])
    same_nodes = a.keys() == b.keys()
    distances, rotations = [], []
    complete = same_nodes
    if same_nodes:
        for key in a:
            x, y = (n[key].get('obj_transform', {}) for n in [a, b])
            if 'position' not in x or 'position' not in y or 'rotation' not in x or 'rotation' not in y:
                complete = False
                continue
            distances.append(math.dist(x['position'], y['position']))
            # q and -q represent the same quaternion.
            rotations.append(min(math.dist(x['rotation'], y['rotation']),
                                 math.dist(x['rotation'], [-v for v in y['rotation']])))
    position = max(distances, default=0) if complete else None
    rotation = max(rotations, default=0) if complete else None
    symbolic_equal = vh.comparable(first) == vh.comparable(second)
    return {'symbolic_equal': symbolic_equal, 'max_position_distance': position,
            'max_quaternion_distance': rotation, 'full_graph_equal': first == second,
            'passed': symbolic_equal and complete and position <= 0.001 and rotation <= 0.0001}


class FixedEpisode(vh.Episode):
    def initialize(self, scene_num, initial_room, initial_states):
        position = self.config['fixed_positions'][f'{self.kind}/{self.task_id}']
        add = self.comm.add_character
        render = self.comm.render_script

        def fixed_add(resource, initial_room):
            return add(resource, position=position)

        def unique_render(*args, **kwargs):
            kwargs['file_name_prefix'] = 'fixed_initial_' + kwargs['file_name_prefix']
            return render(*args, **kwargs)

        self.comm.add_character = fixed_add
        self.comm.render_script = unique_render
        try:
            super().initialize(scene_num, initial_room, initial_states)
        finally:
            self.comm.add_character = add
        self.log('fixed_initialization', requested_position=position,
                 fixed_runner_sha256=vh.digest(Path(__file__)))
        if self.arm != 'reference':
            folder = FIXED / 'runs' / f'{self.kind}_{self.task_id}_reference_reference'
            reference = json.loads((folder / 'result.json').read_text())
            with gzip.open(folder / reference['initial']['graph_file'], 'rt') as f:
                expected = json.load(f)
            check = alignment(self.initial_graph, expected)
            self.log('initial_alignment_to_fixed_reference', **check)
            if not check['passed']:
                raise RuntimeError('Fixed initial state differs from reference; stopped before API calls')


def prepare():
    config = copy.deepcopy(json.loads((ORIGINAL / 'config.json').read_text()))
    config['design'] = 'prospective_fixed_position_four_task_two_model_three_arm_one_repeat'
    config['parent_config_sha256'] = vh.digest(ORIGINAL / 'config.json')
    config['fixed_runner_sha256'] = vh.digest(Path(__file__))
    config['base_runner_sha256'] = vh.digest(Path(vh.__file__))
    config['fixed_positions'] = {}
    config['position_source_result_sha256'] = {}
    for kind, task_id in vh.SELECTED:
        source = ORIGINAL / 'runs' / f'{kind}_{task_id}_reference_reference/result.json'
        config['fixed_positions'][f'{kind}/{task_id}'] = json.loads(source.read_text())['initial']['agent_transform']['position']
        config['position_source_result_sha256'][str(source.relative_to(vh.ROOT))] = vh.digest(source)
    config['max_estimated_usd'] = 1.0
    config['notes'] = [
        'New experiment, not a replacement or reproduction of historical fix_room initialization',
        'Positions taken from original pilot reference runs, without searching for better outcomes',
        'Each condition must match its new fixed-position reference symbolic state and transforms before any API call',
        'Position tolerance 0.001 Unity units, quaternion distance tolerance 0.0001; not a deterministic physics claim',
        'Retain all four tasks even when a reference plan fails; report that subset separately',
        'Original planning loop, prompts, execution parameters and retrieved examples unchanged',
        'One repeat, no simulator/API retries; remote recordings use distinct fixed_initial prefix',
        'C3/C4/C5, retrieval comparisons, full benchmark and author review remain outside this pilot']
    path = FIXED / 'config.json'
    if path.exists():
        assert json.loads(path.read_text()) == config, 'Frozen fixed-initial config changed'
    else:
        vh.write(path, config)
    return config


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--phase', choices=['reference', 'compare'], required=True)
    args = parser.parse_args()
    vh.OUT = FIXED
    config = prepare()
    if args.phase == 'reference':
        for kind, task_id in vh.SELECTED:
            FixedEpisode(config, kind, task_id, 'reference', None).run()
    else:
        outcomes = {}
        for kind, task_id in vh.SELECTED:
            path = FIXED / 'runs' / f'{kind}_{task_id}_reference_reference/result.json'
            outcomes[f'{kind}/{task_id}'] = json.loads(path.read_text())['outcome']
        policy = {'reference_outcomes': outcomes, 'allow_completed_reference_failures': True,
                  'action_name_conversion': False, 'initial_alignment_required_before_api': True,
                  'fixed_runner_sha256': config['fixed_runner_sha256']}
        path = FIXED / 'comparison_policy.json'
        if path.exists():
            assert json.loads(path.read_text()) == policy
        else:
            vh.write(path, policy)
        import spacy
        nlp = spacy.load('en_core_web_sm')
        api = vh.API(config)
        for kind, task_id in vh.SELECTED:
            for model in vh.MODELS:
                for arm in vh.ARMS:
                    FixedEpisode(config, kind, task_id, arm, model, api).run(nlp)
        print(f'Fixed-initial pilot complete; estimated API cost ${api.spent:.6f}', flush=True)


if __name__ == '__main__':
    main()
