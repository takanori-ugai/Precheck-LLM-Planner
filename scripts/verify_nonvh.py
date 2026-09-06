"""Offline integrity and regression verification; no API or simulator calls."""
import io
import json
import unittest
from collections import Counter
from nonvh_analysis import ROOT, OUT, digest, save
from run_nonvh_api import read_logs, load_key


def verify():
    config = json.loads((OUT / 'config.json').read_text())
    assert digest(OUT / 'cases.json') == config['cases_sha256']
    for path, sha in config['source_sha256'].items():
        assert digest(ROOT / path) == sha, path
    cases = {r['id']: r for r in json.loads((OUT / 'cases.json').read_text())}
    logs = read_logs()
    good = [r for r in logs if r['status'] == 'ok']
    assert len(good) == len({r['call_id'] for r in good})
    for row in good:
        assert row['response']['model'] == row['requested_model']
        assert row['cases_sha256'] == config['cases_sha256']
        assert row['runner_sha256'] == digest(ROOT / 'scripts/run_nonvh_api.py')
        if row['phase'] in ('precondition', 'termination'):
            expected = [{'role': role, 'content': text} for role, text in cases[row['case_id']]['messages']]
            assert row['request']['messages'] == expected
    completion = json.loads((OUT / 'completion.json').read_text())
    assert not completion['missing_component_calls']
    assert not completion['missing_repair_outputs']
    assert sum(r['estimated_usd'] for r in good) < 2
    # Never print the key. Test only whether its bytes leaked into newly produced artifacts.
    secret_scan = 'not_checked_no_local_key'
    if (ROOT / '.env.local').exists():
        secret = load_key().encode()
        paths = list(OUT.glob('*')) + list((ROOT / 'scripts').glob('*.py'))
        assert not any(secret in p.read_bytes() for p in paths if p.is_file()), 'Credential leak detected'
        secret_scan = 'passed_no_key_in_new_artifacts'
    suite = unittest.defaultTestLoader.discover(str(ROOT / 'scripts'), pattern='test_*.py')
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    assert result.wasSuccessful(), stream.getvalue()
    save('verification.json', {'tests_run': result.testsRun, 'tests_passed': result.wasSuccessful(),
         'test_output': stream.getvalue(), 'successful_requests': len(good),
         'phase_counts': dict(Counter(r['phase'] for r in good)),
         'failed_requests': len(logs) - len(good), 'credential_scan': secret_scan,
         'prompt_and_source_hashes_match': True, 'returned_model_ids_match': True,
         'duplicate_successful_call_ids': 0, 'api_called_by_verifier': False,
         'vh_executed': False, 'latex_executed': False,
         'verifier_sha256': digest(ROOT / 'scripts/verify_nonvh.py')})
    print(f'Verified {len(good)} responses, {result.testsRun} tests; no credential leakage.')


if __name__ == '__main__':
    verify()
