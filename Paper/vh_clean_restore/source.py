"""VH-only diagnostic: restore a saved decision graph into a character-free scene.

Unlike the unsuccessful mid-trajectory expansion, reset first. No retries,
no altered tolerances, and never execute a candidate on a mismatched graph.
"""
import argparse
import hashlib
import json
from pathlib import Path

import vh_step4 as s
from replay_aligned_candidates import matched_execution
from summarize_vh import graph

ROOT = s.vh.ROOT
OUT = ROOT / 'Paper/vh_clean_restore'


def run(row, prior, config):
    key = hashlib.sha256(f"{row['run_id']}/{row['step']}".encode()).hexdigest()[:16]
    folder = OUT / 'runs' / key
    if folder.exists():
        raise RuntimeError('Existing attempt preserved; no implicit rerun')
    folder.mkdir(parents=True)
    expected_path = ROOT / prior['expected_graph']
    expected = graph(expected_path.parent, expected_path.name)
    result = dict(run_id=row['run_id'], step=int(row['step']), action=row['action'],
                  expected_graph=prior['expected_graph'], api_requests=0, candidate_executed=False)
    def log(phase, **data):
        with (folder / 'events.jsonl').open('a') as f:
            f.write(json.dumps(dict(utc=s.vh.utc(), phase=phase, **data)) + '\n')
    try:
        comm = s.vh.connect(config['host'], config['port'], folder)
        task = json.loads((ROOT / 'dataset' / row['kind'] / 'test.json').read_text())[row['task_id']]
        if not comm.reset(task['scene'] - 1):
            raise RuntimeError('Clean scene reset failed')
        initial = comm.environment_graph()[1]
        assert not any(n['class_name'] == 'character' for n in initial['nodes'])
        log('character_free_scene', graph_file=comm.last_path)
        reply = comm.expand_scene(expected, randomize=False, animate_character=True,
                                  transfer_transform=True)
        log('clean_snapshot_restore', expected_graph=prior['expected_graph'], simulator_result=reply)
        result['restore_reply_success'] = reply[0]
        if not reply[0]:
            result['status'] = 'restore_request_failed'
        else:
            result.update(matched_execution(comm, expected, row['action'], 'vclean_' + key, log))
    except Exception as exc:
        result.update(status='infrastructure_or_initialization_error', error_type=type(exc).__name__, error=str(exc))
        s.vh.write(folder / 'result.json', result)
        raise
    s.vh.write(folder / 'result.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--run', action='store_true')
    args = parser.parse_args()
    selection = ROOT / 'Paper/vh_counterfactual/selection.csv'
    prior_path = ROOT / 'Paper/vh_aligned_prefix/results.json'
    config_path = ROOT / 'Paper/vh_step4/config.json'
    prior = {(r['run_id'], r['step']): r for r in json.loads(prior_path.read_text())}
    rows = [r for r in json.loads(selection.read_text()) if not prior[r['run_id'], int(r['step'])]['candidate_executed']]
    config = json.loads(config_path.read_text())
    sources = [Path(__file__), ROOT / 'scripts/replay_aligned_candidates.py',
               ROOT / 'scripts/vh_experiment.py', ROOT / 'scripts/vh_fixed_initial.py',
               s.vh.CLIENT / 'unity_simulator/comm_unity.py', selection, prior_path, config_path]
    sources += [ROOT / prior[r['run_id'], int(r['step'])]['expected_graph'] for r in rows]
    protocol = dict(policy='One clean scene reset and character-free expansion per previously mismatched candidate; animate_character=True; gate last graph before render; no retries',
                    targeted=len(rows), original_selected=8, unselected=51,
                    position_tolerance=0.001, quaternion_tolerance=0.0001, api_requests=0,
                    sources_sha256={str(p.relative_to(ROOT)): s.vh.digest(p) for p in sources})
    OUT.mkdir(exist_ok=True)
    frozen = OUT / 'protocol.json'
    if frozen.exists():
        assert json.loads(frozen.read_text()) == protocol, 'Frozen protocol changed'
    else:
        s.vh.write(frozen, protocol)
        (OUT / 'source.py').write_text(Path(__file__).read_text())
    if not args.run:
        return
    try:
        for row in rows:
            result = run(row, prior[row['run_id'], int(row['step'])], config)
            print(row['run_id'], result['status'], flush=True)
    finally:
        results = [json.loads(p.read_text()) for p in sorted((OUT / 'runs').glob('*/result.json'))]
        summary = dict(targeted=len(rows), recorded=len(results),
                       executed_aligned=sum(r['candidate_executed'] for r in results),
                       vh_successes=sum(r.get('vh_success') is True for r in results), api_requests=0,
                       status_counts={k: sum(r['status'] == k for r in results) for k in sorted({r['status'] for r in results})})
        s.vh.write(OUT / 'results.json', results); s.vh.write(OUT / 'summary.json', summary)
        print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    main()
