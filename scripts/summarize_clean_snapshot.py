"""Audit clean-scene restoration and combine unique, strictly gated candidates."""
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path

from vh_fixed_initial import alignment

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'Paper/vh_clean_restore'


def audit():
    sources = {Path(__file__)}
    def read(path):
        sources.add(path)
        if path.suffix == '.gz':
            with gzip.open(path, 'rt') as f:
                return f.read()
        return path.read_text()
    def obj(path): return json.loads(read(path))
    def lines(path): return [json.loads(x) for x in read(path).splitlines()]
    protocol = obj(OUT / 'protocol.json')
    for path, digest in protocol['sources_sha256'].items():
        sources.add(ROOT / path)
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest, path
    sources.add(OUT / 'source.py')
    assert (OUT / 'source.py').read_bytes() == (ROOT / 'scripts/replay_clean_snapshot.py').read_bytes()
    selection = obj(ROOT / 'Paper/vh_counterfactual/selection.csv')
    key = lambda r: (r['run_id'], int(r['step']))
    priors = {key(r): r for r in obj(ROOT / 'Paper/vh_aligned_prefix/results.json')}
    records = {key(r): r for r in obj(OUT / 'results.json')}
    assert set(records) == {k for k, v in priors.items() if not v['candidate_executed']}
    detail, combined = [], []
    for number, selected in enumerate(selection, 1):
        k = key(selected); prior = priors[k]
        source = 'prefix_only'
        result = prior
        if k in records:
            result = records[k]; source = 'clean_snapshot'
            folder = OUT / 'runs' / hashlib.sha256(f'{k[0]}/{k[1]}'.encode()).hexdigest()[:16]
            assert result == obj(folder / 'result.json')
            events = lines(folder / 'events.jsonl')
            gate, = [e for e in events if e['phase'] == 'candidate_gate']
            start, = [e for e in events if e['phase'] == 'character_free_scene']
            assert not any(n['class_name'] == 'character' for n in obj(folder / start['graph_file'])['nodes'])
            expected = obj(ROOT / result['expected_graph'])
            actual = obj(folder / gate['before_graph'])
            check = alignment(expected, actual)
            assert check == result['alignment']
            assert all(gate[name] == value for name, value in check.items())
            assert result['candidate_executed'] == check['passed']
            rpc = lines(folder / 'simulator_rpc.jsonl.gz')
            assert all('error_type' not in r for r in rpc)
            actions = [r['request']['action'] for r in rpc]
            assert actions[:4] == ['clear', 'environment', 'environment_graph', 'expand_scene']
            assert actions.count('expand_scene') == 1 and 'add_character' not in actions
            assert actions.count('render_script') == int(check['passed'])
            executions = [e for e in events if e['phase'] == 'candidate_execution']
            assert len(executions) == int(check['passed'])
            if check['passed']:
                assert actions[-3:] == ['environment_graph', 'render_script', 'environment_graph']
                assert result['status'] == 'executed'
                assert executions[0]['simulator_result'][0] == result['vh_success']
                assert executions[0]['before_graph'] == gate['before_graph']
                obj(folder / result['after_graph'])
            else:
                assert result['status'] == 'state_not_restored' and 'vh_success' not in result
            edges = lambda g: {(e['from_id'], e['relation_type'], e['to_id']) for e in g['edges']}
            a, b = edges(expected), edges(actual)
            detail.append(dict(case=number, run_id=k[0], step=k[1], **check,
                               candidate_executed=result['candidate_executed'],
                               vh_success=result.get('vh_success', ''),
                               missing_edges=json.dumps(sorted(a-b)), extra_edges=json.dumps(sorted(b-a))))
        assert result['action'] == selected['action'] and result['api_requests'] == 0
        combined.append(dict(case=number, run_id=k[0], step=k[1], action=selected['action'],
                             evaluation_protocol=source, **result['alignment'],
                             candidate_executed=result['candidate_executed'],
                             vh_success=result.get('vh_success', ''), status=result['status']))
    summary = obj(OUT / 'summary.json')
    assert summary['recorded'] == summary['targeted'] == len(detail) == 6
    assert summary['executed_aligned'] == sum(r['candidate_executed'] for r in detail)
    assert summary['vh_successes'] == sum(r['vh_success'] is True for r in detail)
    manifest = dict(audit='passed', clean_snapshot=summary, original_selected=len(combined),
                    unique_executed_aligned=sum(r['candidate_executed'] for r in combined),
                    unique_vh_successes=sum(r['vh_success'] is True for r in combined),
                    unexecuted_cases=[r['case'] for r in combined if not r['candidate_executed']],
                    unselected=51, api_requests=0,
                    scope='Two protocols; retain all attempts; no population error-rate inference',
                    sources_sha256={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(sources)})
    return detail, combined, manifest


if __name__ == '__main__':
    detail, combined, manifest = audit()
    for name, rows in [('alignment.csv', detail), ('combined_candidates.csv', combined)]:
        buf = io.StringIO(); writer = csv.DictWriter(buf, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
        (OUT / name).write_text(buf.getvalue())
    (OUT / 'verification.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: v for k, v in manifest.items() if k != 'sources_sha256'}, indent=2))
