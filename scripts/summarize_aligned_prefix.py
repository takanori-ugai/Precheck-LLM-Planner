"""Offline audit/export of gated VH prefix replays; never connects to VH or APIs."""
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path

from vh_fixed_initial import alignment

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'Paper/vh_aligned_prefix'


def audit():
    sources = set()
    def read(path):
        sources.add(path)
        if path.suffix == '.gz':
            with gzip.open(path, 'rt') as f:
                return f.read()
        return path.read_text()
    def obj(path):
        return json.loads(read(path))
    def lines(path):
        return [json.loads(line) for line in read(path).splitlines()]
    protocol = obj(OUT / 'protocol.json')
    selected_path = ROOT / 'Paper/vh_counterfactual/selection.csv'
    selected = obj(selected_path)
    read(OUT / 'source.py')
    assert hashlib.sha256((OUT / 'source.py').read_bytes()).hexdigest() == protocol['script_sha256']
    assert hashlib.sha256(selected_path.read_bytes()).hexdigest() == protocol['selection_sha256']
    assert 'never transfer mid-trajectory graph' in protocol['policy']
    rows = []
    for number, candidate in enumerate(selected, 1):
        run, step = candidate['run_id'], int(candidate['step'])
        key = hashlib.sha256(f'{run}/{step}'.encode()).hexdigest()[:16]
        folder = OUT / 'runs' / key
        result = obj(folder / 'result.json')
        assert (result['run_id'], result['step'], result['action']) == (run, step, candidate['action'])
        assert not result['restoration_attempted'] and result['api_requests'] == 0
        events = lines(folder / 'events.jsonl')
        gate, = [e for e in events if e['phase'] == 'candidate_gate']
        assert all(e['passed'] for e in events if e['phase'] == 'initial_alignment')
        expected = obj(ROOT / result['expected_graph'])
        observed = obj(folder / gate['before_graph'])
        checked = alignment(expected, observed)
        assert checked == result['alignment']
        assert all(gate[k] == v for k, v in checked.items())
        assert result['before_graph'] == gate['before_graph']
        execution = [e for e in events if e['phase'] == 'candidate_execution']
        prefix = [e for e in events if e['phase'] == 'execution']
        assert [e['action'] for e in prefix] == result['prefix']
        assert all(e['simulator_result'][0] for e in prefix)
        rpc = lines(folder / 'simulator_rpc.jsonl.gz')
        assert all('error_type' not in r for r in rpc)
        requests = [r['request']['action'] for r in rpc]
        # One scene setup expansion is allowed, only before adding the avatar.
        assert requests.count('expand_scene') == 1
        assert requests.index('expand_scene') < requests.index('add_character')
        assert requests.count('render_script') == len(prefix) + int(checked['passed'])
        assert result['candidate_executed'] == checked['passed']
        assert len(execution) == int(checked['passed'])
        if checked['passed']:
            assert result['status'] == 'executed'
            assert execution[0]['before_graph'] == gate['before_graph']
            assert execution[0]['simulator_result'][0] == result['vh_success']
            assert requests[-3:] == ['environment_graph', 'render_script', 'environment_graph']
            obj(folder / result['after_graph'])
        else:
            assert result['status'] == 'state_not_restored' and 'vh_success' not in result
            assert requests[-1] == 'environment_graph'
        rows.append(dict(case=number, run_id=run, step=step, action=candidate['action'],
                         prefix_actions=len(prefix), **checked,
                         candidate_executed=result['candidate_executed'],
                         vh_success=result.get('vh_success', ''), status=result['status']))
    summary = obj(OUT / 'summary.json')
    assert summary['recorded'] == summary['selected'] == len(rows) == 8
    assert summary['executed_aligned'] == sum(r['candidate_executed'] for r in rows)
    assert summary['vh_successes'] == sum(r['vh_success'] is True for r in rows)
    assert summary['api_requests'] == 0 and summary['unselected'] == 51
    manifest = {'audit': 'passed', 'candidate_count': len(rows),
                'symbolic_equal': sum(r['symbolic_equal'] for r in rows),
                'successful_prefix_actions': sum(r['prefix_actions'] for r in rows),
                'summary': summary,
                'sources_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                   for p in sorted(sources | {Path(__file__)})}}
    return rows, manifest


if __name__ == '__main__':
    rows, manifest = audit()
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0]))
    writer.writeheader(); writer.writerows(rows)
    (OUT / 'alignment.csv').write_text(buf.getvalue())
    (OUT / 'verification.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: v for k, v in manifest.items() if k != 'sources_sha256'}, indent=2))
