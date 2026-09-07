"""Audit the eight saved-prefix replays offline, without simulator/API calls."""
import gzip
import json
import shutil
from pathlib import Path

import replay_saved_vh as replay
from summarize_vh import graph, read_lines


def verify():
    s, out = replay.s, replay.OUT
    config = json.loads((out / 'config.json').read_text())
    assert config['runner_sha256'] == s.vh.digest(Path(replay.__file__))
    assert config['helper_sha256'] == s.vh.digest(Path(s.__file__))
    for name, expected in config['source_sha256'].items():
        assert s.vh.digest(s.vh.ROOT / name) == expected, name
    paths = sorted((out / 'runs').glob('*/result.json'))
    assert len(paths) == 8
    expected = {(k, t, m) for k, t in s.vh.SELECTED for m in ['gpt-4o-mini', 'gpt-4o']}
    observed = set()
    for path in paths:
        r = json.loads(path.read_text())
        observed.add((r['kind'], r['task_id'], r['model']))
        assert r['config_sha256'] == s.vh.digest(out / 'config.json')
        assert r['runner_sha256'] == config['runner_sha256']
        assert r['api_requests'] == 0
        source = s.vh.ROOT / f'result/{r["kind"]}/result_multi-prompts_{r["model"]}.json'
        stored = json.loads(source.read_text())[r['task_id']]
        task = json.loads((s.vh.ROOT / f'dataset/{r["kind"]}/test.json').read_text())[r['task_id']]
        ref_dir = s.REFERENCE / 'runs' / f'{r["kind"]}_{r["task_id"]}_reference_reference'
        ref = json.loads((ref_dir / 'result.json').read_text())
        initial = graph(path.parent, r['initial']['graph_file'])
        assert s.alignment(initial, graph(ref_dir, ref['initial']['graph_file']))['passed']
        assert s.vh.goal(initial, task) == r['initial']['goal']
        assert s.vh.goal(graph(path.parent, r['final_graph']), task) == r['final_goal']
        events = read_lines(path.parent / 'events.jsonl')
        executions = [e for e in events if e['phase'] == 'execution']
        assert len(executions) == r['execution_attempts']
        assert [e['action'] for e in executions] == stored['action script'][:len(executions)]
        assert [e['action'] for e in executions if e['simulator_result'][0]] == r['successful_actions']
        assert all(e['simulator_result'][0] for e in executions[:-1])
        assert r['historical_prefix_replayed_in_full'] == (len(r['successful_actions']) == len(stored['action script']))
        assert r['original_result'] == stored['result']
        assert r['original_saved_length'] == len(stored['action script'])
        for e in executions:
            assert s.vh.goal(graph(path.parent, e['before_graph']), task) == e['before_goal']
            assert s.vh.goal(graph(path.parent, e['after_graph']), task) == e['after_goal']
        assert not any('messages' in e for e in events)
        with gzip.open(path.parent / 'simulator_rpc.jsonl.gz', 'rt') as f:
            rpc = [json.loads(line) for line in f]
        assert not any('error_type' in e for e in rpc)
        assert [e['request']['action'] for e in rpc[:2]] == ['clear', 'environment']
    assert observed == expected
    assert not (out / 'api_log.jsonl').exists()
    secret = s.vh.load_key().encode()
    for path in out.rglob('*'):
        if path.is_file():
            assert secret not in path.read_bytes(), path.name
            if path.suffix == '.gz':
                with gzip.open(path, 'rb') as f:
                    assert secret not in f.read(), path.name
    target = out / 'sources' / f'{s.vh.digest(Path(__file__))}.py'
    if not target.exists():
        shutil.copy2(__file__, target)
    s.vh.write(out / 'verification.json', dict(utc=s.vh.utc(), completed=8,
        source_hashes_verified=True, unchanged_prefixes_verified=True,
        initial_alignments_verified=True, graph_goals_verified=True,
        api_requests=0, key_absent=True, latex_executed=False))
    s.vh.write(out / 'manifest.json', {str(p.relative_to(out)): s.vh.digest(p)
        for p in sorted(out.rglob('*')) if p.is_file() and p.name != 'manifest.json'})
    print('Verified 8 saved-prefix replays; no API; manifest written.')


if __name__ == '__main__':
    verify()
