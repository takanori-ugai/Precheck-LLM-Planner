"""Offline audit of completed VH evidence, with no API or simulator requests."""
import argparse
import gzip
import json
import shutil
from pathlib import Path

import vh_experiment as vh
from summarize_vh import graph, read_lines
from vh_fixed_initial import alignment


def verify(folder):
    config = json.loads((folder / 'config.json').read_text())
    for name, expected in config['source_sha256'].items():
        assert vh.digest(vh.ROOT / name) == expected, name
    logs = read_lines(folder / 'api_log.jsonl')
    result_files = sorted((folder / 'runs').glob('*/result.json'))
    assert len(result_files) == 28, f'Expected 4 references + 24 comparisons, got {len(result_files)}'
    expected_runs = {f'{k}_{t}_{a}_{m}' for k, t in vh.SELECTED for a in vh.ARMS for m in vh.MODELS}
    observed_runs = set()
    archived = {p.stem for p in (vh.OUT / 'sources').glob('*.py')}
    unarchived = set()
    for path in result_files:
        result = json.loads(path.read_text())
        assert result['config_sha256'] == vh.digest(folder / 'config.json')
        if result['runner_sha256'] not in archived:
            unarchived.add(result['runner_sha256'])
        task = json.loads((vh.ROOT / f'dataset/{result["kind"]}/test.json').read_text())[result['task_id']]
        initial = graph(path.parent, result['initial']['graph_file'])
        assert vh.object_hash(initial) == result['initial']['full_hash']
        assert vh.object_hash(vh.comparable(initial)) == result['initial']['symbolic_hash']
        assert vh.goal(initial, task) == result['initial']['goal']
        assert vh.goal(graph(path.parent, result['final_graph']), task) == result['final_goal']
        events = read_lines(path.parent / 'events.jsonl')
        executions = [r for r in events if r['phase'] == 'execution']
        assert len(executions) == result['execution_attempts']
        assert [r['action'] for r in executions if r['simulator_result'][0]] == result['actions']
        for row in executions:
            assert vh.goal(graph(path.parent, row['before_graph']), task) == row['before_goal']
            assert vh.goal(graph(path.parent, row['after_graph']), task) == row['after_goal']
        with gzip.open(path.parent / 'simulator_rpc.jsonl.gz', 'rt') as f:
            rpc = [json.loads(line) for line in f]
        assert not any('error_type' in r for r in rpc)
        assert rpc[0]['request']['action'] == 'clear'
        assert rpc[1]['request']['action'] == 'environment'
        api_events = [r for r in events if r['phase'] in ('generation', 'termination', 'precondition', 'unmet', 'regeneration')]
        own_calls = [r for r in logs if r['run_id'] == result['run_id'] and r['utc'] >= events[0]['utc']]
        assert len(api_events) == len(own_calls)
        for event, call in zip(api_events, own_calls):
            assert event['phase'] == call['phase'] and event['step'] == call['step']
            assert event['response'] == (call['response']['choices'][0]['message'].get('content') or '')
            assert [{'role': role, 'content': text} for role, text in event['messages']] == call['request']['messages']
        if result['arm'] != 'reference':
            observed_runs.add(result['run_id'])
            if config['design'].startswith('prospective_fixed'):
                ref_folder = folder / 'runs' / f'{result["kind"]}_{result["task_id"]}_reference_reference'
                ref = json.loads((ref_folder / 'result.json').read_text())
                check = alignment(initial, graph(ref_folder, ref['initial']['graph_file']))
                assert check['passed']
                saved = next(r for r in events if r['phase'] == 'initial_alignment_to_fixed_reference')
                assert all(saved[key] == value for key, value in check.items())
    assert expected_runs == observed_runs
    for row in logs:
        assert row['status'] == 'ok'
        assert row['run_id'] in observed_runs
        assert row['response']['model'] == row['request']['model']
        inp, out = config['prices_usd_per_million'][row['request']['model']]
        usage = row['response']['usage']
        assert abs(row['estimated_usd'] - (usage['prompt_tokens'] * inp + usage['completion_tokens'] * out) / 1e6) < 1e-12
    interrupted = list((folder / 'interrupted').glob('*/infrastructure_error.json'))
    return {'folder': str(folder.relative_to(vh.ROOT)), 'completed_episodes': len(result_files),
            'api_successful_requests': len(logs), 'all_checks_passed': True,
            'interrupted_attempts_preserved': len(interrupted),
            'unarchived_early_reference_runner_hashes': sorted(unarchived),
            'note': 'Early probe/reference runner versions were hashed but not archived before edits; no exact source recovery claimed'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--include-fixed', action='store_true')
    parser.add_argument('--capture-runtime', action='store_true')
    args = parser.parse_args()
    archive = vh.OUT / 'sources'
    archive.mkdir(exist_ok=True)
    for name in ['vh_experiment.py', 'vh_fixed_initial.py', 'summarize_vh.py', 'verify_vh.py', 'test_vh_experiment.py']:
        path = Path(__file__).parent / name
        target = archive / f'{vh.digest(path)}.py'
        if not target.exists():
            shutil.copy2(path, target)
    roots = [vh.OUT] + ([vh.OUT / 'fixed_initial'] if args.include_fixed else [])
    reports = [verify(folder) for folder in roots]
    if args.capture_runtime:
        windows = Path('/mnt/c/Users/ugai/Downloads/VH/windows_exec.v2.3.0')
        filenames = ['VirtualHome.exe', 'UnityPlayer.dll', 'VirtualHome_Data/Managed/Assembly-CSharp.dll']
        previous_log = Path('/mnt/c/Users/ugai/AppData/LocalLow/VirtualHome/VirtualHome/Player-prev.log')
        previous_hash = vh.digest(previous_log)
        saved_log = vh.OUT / 'diagnostics' / f'windows_player_previous_{previous_hash}.log.gz'
        saved_log.parent.mkdir(exist_ok=True)
        if not saved_log.exists():
            with previous_log.open('rb') as src, gzip.open(saved_log, 'wb') as dst:
                shutil.copyfileobj(src, dst)
        vh.write(vh.OUT / 'runtime_receipt.json', {'utc': vh.utc(), 'observed_runtime_directory': str(windows),
            'binary_sha256': {name: vh.digest(windows / name) for name in filenames},
            'version_evidence': 'User-provided directory name v2.3.0 and Player.log data path, not independently attested build version',
            'execution_platform': 'Windows, WSL2 client via 172.26.224.1:8080',
            'player_log_path': 'C:/Users/ugai/AppData/LocalLow/VirtualHome/VirtualHome/Player.log',
            'gpu_log_observation': 'Direct3D 11 / NVIDIA GeForce RTX 2060',
            'previous_player_log_sha256': previous_hash,
            'previous_player_log_archive': str(saved_log.relative_to(vh.OUT)),
            'local_linux_executable_used': False})
    # Test the exact permitted secret in artifact bytes without displaying it or its hash.
    secret = vh.load_key().encode()
    for path in vh.OUT.rglob('*'):
        if path.is_file():
            assert secret not in path.read_bytes(), f'Secret contamination detected in {path.name}'
            if path.suffix == '.gz':
                with gzip.open(path, 'rb') as f:
                    assert secret not in f.read(), f'Secret contamination detected in {path.name}'
    vh.write(vh.OUT / 'verification.json', {'utc': vh.utc(), 'reports': reports,
             'exact_key_absent_in_all_vh_artifacts': True, 'latex_executed': False})
    # The manifest excludes itself so that repeated verification remains meaningful.
    files = sorted(p for p in vh.OUT.rglob('*') if p.is_file() and p.name != 'manifest.json')
    vh.write(vh.OUT / 'manifest.json', {str(p.relative_to(vh.OUT)): vh.digest(p) for p in files})
    print(json.dumps(reports, ensure_ascii=False, indent=2))
    print('No API key in VH artifacts; manifest written; TeX not executed.')


if __name__ == '__main__':
    main()
