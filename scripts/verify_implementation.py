#!/usr/bin/env python3
"""Verify step-3 artifacts without TeX, an API, or a simulator."""
import csv
import hashlib
import json
from pathlib import Path
import sys
import unittest

from revision_analysis import METRICS, paper_check

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    target = ROOT / 'Paper/implementation'
    suite = unittest.defaultTestLoader.discover(str(ROOT / 'scripts'), pattern='test_implementation_spec.py')
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)
    with (ROOT / 'Paper/analysis/metrics.csv').open() as handle:
        metrics = [{**row, **{key: float(row[key]) for key in METRICS}} for row in csv.DictReader(handle)]
    checks = paper_check(metrics, target)
    with (ROOT / 'Paper/analysis/source_manifest.csv').open() as handle:
        old = {row['path']: row['sha256'] for row in csv.DictReader(handle)}
    paths = [ROOT / 'Paper' / name for name in ('main.tex', 'sec3.tex', 'sec4.tex', 'sec5.tex',
                                               'appendix-implementation.tex')]
    paths += [ROOT / 'Paper/listings/prompt_spec.py']
    paths += sorted((ROOT / 'Paper/listings').glob('knowledge_*'))
    paths += [ROOT / 'scripts' / name for name in ('export_implementation_appendix.py',
                                                  'test_implementation_spec.py', 'verify_implementation.py')]
    with (target / 'source_manifest.csv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=['path', 'step2_sha256', 'step3_sha256', 'status'])
        writer.writeheader()
        for path in paths:
            name = str(path.relative_to(ROOT))
            writer.writerow({'path': name, 'step2_sha256': old.get(name, ''), 'step3_sha256': sha(path),
                             'status': 'revised_manuscript' if name in old else 'new_documentation_or_verification'})
    for name, value in old.items():
        if not name.startswith('Paper/') and sha(ROOT / name) != value:
            raise ValueError(f'Original experiment input changed: {name}')
    receipt = {'kind': 'step3_documentation_verification_no_TeX_no_LLM_no_simulator',
               'python_version': sys.version, 'test_methods_passed': result.testsRun,
               'paper_numeric_values_preserved': len(checks), 'original_non_paper_inputs_unchanged': True,
               'synthetic_examples_are_historical_logs': False,
               'limitations': ['TeX/LaTeX execution omitted at user request',
                               'Historical per-step graphs and construction provenance remain unavailable']}
    (target / 'verification.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
