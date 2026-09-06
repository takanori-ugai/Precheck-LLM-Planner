#!/usr/bin/env python3
"""Audit existing evidence and generate revision tables using the Python standard library."""
import argparse
import ast
import csv
import hashlib
import itertools
import json
import math
from pathlib import Path
import random
import re
import statistics
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
TYPES = ('state_change_task', 'placement_task')
LABELS = ('Success', 'Execution Failure', 'Reaching Maximum Attempts', 'Erroneous Terminate')
METRICS = ('SR', 'AEFR', 'FRRMA', 'ETFR', 'Average Steps')


def read_json(path):
    # Reject silently overwritten duplicate task IDs.
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f'{path}: duplicate JSON key {key}')
            result[key] = value
        return result
    return json.loads(path.read_text(), object_pairs_hook=unique)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args):
    return subprocess.run(['git', '-C', str(ROOT), *args], check=True,
                          capture_output=True, text=True).stdout.strip()


def quantile(values, p):
    """Linear interpolation, Hyndman-Fan type 7 (including singleton groups)."""
    values = sorted(values)
    if not values:
        return None
    x = (len(values) - 1) * p
    lo = int(x)
    hi = min(lo + 1, len(values) - 1)
    return values[lo] + (values[hi] - values[lo]) * (x - lo)


def describe(values, prefix):
    values = list(values)
    out = {f'{prefix}_n': len(values)}
    measures = {'mean': statistics.mean(values) if values else None,
                'median': quantile(values, .5), 'q1': quantile(values, .25),
                'q3': quantile(values, .75),
                'min': min(values) if values else None, 'max': max(values) if values else None,
                'sd_sample': statistics.stdev(values) if len(values) > 1 else None}
    measures['iqr'] = measures['q3'] - measures['q1'] if values else None
    return out | {f'{prefix}_{k}': v for k, v in measures.items()}


def task_parts(name):
    state = re.fullmatch(r'Turn (on|off) all (.+)', name)
    if state:
        return {'template': 'Turn {state} all {object}', 'operation': state[1],
                'object': state[2], 'destination': ''}
    placement = re.fullmatch(r'Put all (.+) (in|on) the (.+)', name)
    if placement:
        return {'template': 'Put all {object} {relation} the {destination}',
                'object': placement[1], 'operation': placement[2], 'destination': placement[3]}
    raise ValueError(f'Unrecognized task template: {name}')


def ordered_results(kind):
    yield ROOT / 'result' / kind / 'result_baseline.json', 'baseline', 'gpt-4o', None
    for ablation in (False, True):
        for prompt in ('single-prompt', 'multi-prompts'):
            for model in ('gpt-4o-mini', 'gpt-4o'):
                prefix = 'ablation' if ablation and kind == 'state_change_task' else 'result'
                folder = ROOT / 'result' / kind
                if ablation:
                    folder /= 'ablation'
                yield folder / f'{prefix}_{prompt}_{model}.json', prompt, model, not ablation


def validate_result(result, dataset, path):
    if set(result) != set(dataset):
        raise ValueError(f'{path}: result/task ID sets differ')
    for task_id, row in result.items():
        if row['result'] not in LABELS:
            raise ValueError(f'{path}/{task_id}: unknown outcome {row["result"]}')
        if row['attempts'] != len(row['action script']):
            raise ValueError(f'{path}/{task_id}: attempts differs from saved script length')
        if row['score'] != (1.0 if row['result'] == 'Success' else 0.0):
            raise ValueError(f'{path}/{task_id}: unexpected score semantics')


def cluster_interval(rows, value, seed=20260906, repetitions=4000):
    """Task-name cluster bootstrap, retaining all instances of sampled clusters."""
    groups = {}
    for row in rows:
        groups.setdefault(row['task_name'], []).append(value(row))
    sums = [(sum(values), len(values)) for values in groups.values()]
    rng = random.Random(seed)
    estimates = []
    for _ in range(repetitions):
        chosen = rng.choices(sums, k=len(sums))
        estimates.append(sum(s for s, n in chosen) / sum(n for s, n in chosen))
    return quantile(estimates, .025), quantile(estimates, .975)


def select_example(dataset, name):
    # Python max keeps the first JSON entry in a length tie, like the notebooks.
    return max(((key, task) for key, task in dataset.items() if task['task'] == name),
               key=lambda item: len(item[1]['action_scripts']))


def csv_write(path, rows):
    if not rows:
        raise ValueError(f'No rows for {path}')
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, ensure_ascii=False, sort_keys=True) if isinstance(v, (list, dict)) else v
                             for k, v in row.items()})


def markdown_table(rows, columns):
    lines = ['| ' + ' | '.join(title for key, title in columns) + ' |',
             '| ' + ' | '.join('---' for _ in columns) + ' |']
    for row in rows:
        values = []
        for key, title in columns:
            value = row.get(key)
            if value is None:
                value = '—'
            elif isinstance(value, float):
                value = f'{value:.3f}'
            values.append(str(value).replace('|', '\\|').replace('\n', ' '))
        lines.append('| ' + ' | '.join(values) + ' |')
    return '\n'.join(lines)


def inventory(out):
    sources = sorted((ROOT / 'dataset').glob('*/*.json')) + sorted((ROOT / 'result').rglob('*.json'))
    sources += [ROOT / p for p in ('single-prompt.ipynb', 'multi-prompts.ipynb', 'cal_score.ipynb',
                                  'precondition.json', 'requirements.txt', 'README.md')]
    sources += sorted((ROOT / 'Paper').glob('*.tex'))
    sources += [ROOT / 'Paper/references.bib', ROOT / 'Paper/latexmkrc']
    rows = []
    for path in sources:
        relative = str(path.relative_to(ROOT))
        blob = subprocess.run(['git', '-C', str(ROOT), 'rev-parse', '--verify', f'HEAD:{relative}'],
                              capture_output=True, text=True)
        tracked = blob.returncode == 0
        rows.append({'path': relative, 'kind': 'historical_result' if relative.startswith('result/') else 'existing_source',
                     'sha256': digest(path), 'bytes': path.stat().st_size,
                     'head_blob': blob.stdout.strip() if tracked else None,
                     'matches_head': git('hash-object', relative) == blob.stdout.strip() if tracked else None,
                     'last_commit': git('log', '-1', '--format=%H', '--', relative) if tracked else None,
                     'provenance': 'tracked_repository_file' if tracked else 'user_supplied_untracked_paper'})
    csv_write(out / 'source_manifest.csv', rows)
    history = {'head': git('rev-parse', 'HEAD'), 'shallow': git('rev-parse', '--is-shallow-repository'),
               'commits': git('log', '--all', '--format=%H %aI %s', '--name-status'),
               'refs': git('for-each-ref', '--format=%(refname) %(objectname)'),
               'limitation': 'Git commit time is not experiment execution time.'}
    (out / 'local_history.json').write_text(json.dumps(history, ensure_ascii=False, indent=2) + '\n')
    return rows


def settings_inventory(out):
    """Extract non-secret settings without executing notebooks or copying credentials."""
    rows = []
    for name in ('single-prompt.ipynb', 'multi-prompts.ipynb'):
        notebook = read_json(ROOT / name)
        for index, cell in enumerate(notebook['cells']):
            if cell['cell_type'] != 'code':
                continue
            source = ''.join(cell['source'])
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    if node.func.id == 'ChatOpenAI':
                        for kw in node.keywords:
                            if kw.arg in ('model', 'temperature'):
                                rows.append({'setting': kw.arg, 'value': ast.literal_eval(kw.value),
                                             'source': name, 'cell_index_zero_based': index,
                                             'status': 'current_code_not_verified_historical_runtime'})
                    if node.func.id == 'SentenceTransformer':
                        rows.append({'setting': 'retrieval_encoder', 'value': ast.literal_eval(node.args[0]),
                                     'source': name, 'cell_index_zero_based': index,
                                     'status': 'current_code_not_verified_historical_runtime'})
            checks = [('maximum_attempts', 'maximum_attempts = len(task["action_scripts"]) * 2'),
                      ('evaluation_first_task_only', '\n    break'),
                      ('saved_script_key', '"action_script":action_script'),
                      ('find_solution', 'find_solution=False')]
            for setting, needle in checks:
                if needle in source and (setting != 'evaluation_first_task_only' or 'result_dic = {}' in source):
                    rows.append({'setting': setting, 'value': needle.strip(), 'source': name,
                                 'cell_index_zero_based': index,
                                 'status': 'current_code_not_verified_historical_runtime'})
        rows.append({'setting': 'saved_cell_output_count',
                     'value': sum(len(c.get('outputs', [])) for c in notebook['cells']),
                     'source': name, 'status': 'observed_file'})
    for line in (ROOT / 'requirements.txt').read_text().splitlines():
        if re.match(r'(sentence-transformers|transformers|torch|numpy|langchain|langchain-openai|spacy|huggingface-hub)==', line):
            package, version = line.split('==')
            rows.append({'setting': 'dependency:' + package, 'value': version,
                         'source': 'requirements.txt', 'status': 'declared_dependency_not_runtime_receipt'})
    for model in re.findall(r'gpt-4o(?:-mini)?-\d{4}-\d{2}-\d{2}', (ROOT / 'Paper/sec5.tex').read_text()):
        rows.append({'setting': 'paper_model_id', 'value': model, 'source': 'Paper/sec5.tex',
                     'status': 'paper_claim_not_saved_run_metadata'})
    rows.append({'setting': 'VirtualHome_version', 'value': '2.3', 'source': 'README.md; Paper/sec4.tex',
                 'status': 'documented_version_no_binary_hash'})
    csv_write(out / 'settings.csv', rows)
    unresolved = [
        ('U1', 'ベースライン実行コード', 'ローカル全履歴・公開main/ブランチ/タグを調査。結果JSONのみ存在。',
         'Action Translation、Dynamic Example、自動探索・停止処理の実験時コードと設定', 'B-4-4; A対照比較'),
        ('U2', '過去実行とコード版の対応', '全結果は初期コミットに存在するがrun ID/実行日時/実行コミットは未保存。',
         '実験ごとのコードアーカイブ、コマンド、実行ログ', '手順1の来歴確定'),
        ('U3', 'モデル・生成設定の実行記録', '本文の固定版IDと現コードのモデル別名が不一致。temperatureは現コードから取得。',
         '各実験の実際のモデルID、設定、依存環境、反復数', '再現性・分散評価'),
        ('U4', 'データセット構築記録', '最終example/testは回収済み。作成・分割スクリプト、seed、除外履歴は履歴にもない。',
         'タスク選択・除外理由、検証手順、分割前データと生成コード', 'B-1-2; B-2-1'),
        ('U5', '前提条件の出典対応', 'precondition.jsonの8条件は回収済み。原資料の版・転記/省略手順は未保存。',
         'VH資料の版、該当箇所、条件選定・整形記録', 'B-3-2'),
        ('U6', '途中ログ・環境グラフ', '結果はscore/result/action script/attemptsのみ。計画Notebookの保存出力は0。',
         '修正前候補、Yes/No、失敗アクション、時刻別グラフ、エラー、token/time', 'B-3-1; B-4-3'),
        ('U7', '過去の検索選択', '検索アルゴリズムと候補集合は回収済み。今回オフライン再構成。',
         '当時の重みrevision、候補set順序、実際の選択事例ID・スコア', 'B-2-2; B-4-5; コメントB-1'),
        ('U8', 'VH実行環境の固定', '版2.3との記述のみ。バイナリ・シーンのハッシュは未回収。',
         '実験時バイナリ、シーンデータ、実行プラットフォームの記録', '成功判定の独立再検証'),
    ]
    csv_write(out / 'unrecovered.csv', [dict(zip(('id', 'item', 'checked', 'needed', 'affects'), item)) |
                                      {'status': 'not_recovered', 'next_source': '著者保有の実験アーカイブ（未照会）'}
                                      for item in unresolved])


def dataset_analysis(datasets, out):
    tasks, summaries, overlap, coverage = [], [], [], []
    for kind in TYPES:
        for split in ('test', 'example'):
            data = datasets[kind, split]
            for task_id, task in data.items():
                changed = None
                if kind == 'state_change_task':
                    initial = {x['id']: x['states'] for x in task['initial_states']}
                    if all(g['id'] in initial for g in task['goal_states']):
                        changed = sum(initial[g['id']] != g['states'] for g in task['goal_states'])
                tasks.append({'task_type': kind, 'split': split, 'task_id': task_id, 'task_name': task['task'],
                              **task_parts(task['task']), 'scene': task['scene'], 'initial_room': task['initial_room'],
                              'initial_states': task['initial_states'], 'goal_states': task['goal_states'],
                              'goal_count': len(task['goal_states']), 'required_state_changes': changed,
                              'reference_length': len(task['action_scripts']),
                              'reference_actions': task['action_scripts'],
                              'initially_complete_proxy': len(task['action_scripts']) == 0})
            subset = [t for t in tasks if t['task_type'] == kind and t['split'] == split]
            summaries.append({'task_type': kind, 'split': split, 'n': len(data),
                              'task_names': len({t['task'] for t in data.values()}),
                              'scenes': sorted({t['scene'] for t in data.values()}),
                              'zero_reference_n': sum(t['reference_length'] == 0 for t in subset),
                              **describe((t['reference_length'] for t in subset), 'reference'),
                              **describe((t['goal_count'] for t in subset), 'goal_count')})
            # Full observed combination table: no inference of unobserved Cartesian combinations.
            groups = {}
            for task in subset:
                key = tuple(task[k] for k in ('template', 'object', 'operation', 'destination', 'scene', 'initial_room'))
                key += (json.dumps(task['initial_states'], sort_keys=True),)
                groups.setdefault(key, []).append(task)
            for key, group in sorted(groups.items()):
                coverage.append({'task_type': kind, 'split': split,
                                 **dict(zip(('template', 'object', 'operation', 'destination', 'scene', 'initial_room',
                                             'initial_states_json'), key)),
                                 'n': len(group), 'task_ids': [t['task_id'] for t in group],
                                 **describe((t['reference_length'] for t in group), 'reference')})
        for dimension in ('task_name', 'scene', 'object', 'operation', 'destination', 'initial_room'):
            sets = {split: {t[dimension] for t in tasks if t['task_type'] == kind and t['split'] == split}
                    for split in ('test', 'example')}
            overlap.append({'task_type': kind, 'dimension': dimension,
                            'test_distinct': len(sets['test']), 'example_distinct': len(sets['example']),
                            'shared_n': len(sets['test'] & sets['example']),
                            'shared_values': sorted(sets['test'] & sets['example']),
                            'test_only': sorted(sets['test'] - sets['example']),
                            'example_only': sorted(sets['example'] - sets['test'])})
    csv_write(out / 'task_inventory.csv', tasks)
    csv_write(out / 'dataset_summary.csv', summaries)
    csv_write(out / 'dataset_coverage.csv', coverage)
    csv_write(out / 'split_overlap.csv', overlap)
    dimensions = []
    for kind in TYPES:
        for split in ('test', 'example', 'all'):
            subset = [t for t in tasks if t['task_type'] == kind and (split == 'all' or t['split'] == split)]
            for dimension in ('task_name', 'object', 'operation', 'destination', 'scene', 'initial_room'):
                for value in sorted({t[dimension] for t in subset}):
                    group = [t for t in subset if t[dimension] == value]
                    dimensions.append({'task_type': kind, 'split': split, 'dimension': dimension, 'value': value,
                                       'n': len(group), 'task_names': len({t['task_name'] for t in group}),
                                       'scenes': sorted({t['scene'] for t in group})})
    csv_write(out / 'dataset_dimension_counts.csv', dimensions)
    return tasks, summaries


def result_analysis(datasets, tasks, out):
    task_index = {(t['task_type'], t['task_id']): t for t in tasks if t['split'] == 'test'}
    per_task, metrics, mappings, lengths, strata = [], [], [], [], []
    for kind in TYPES:
        for path, prompt, model, precheck in ordered_results(kind):
            data = read_json(path)
            validate_result(data, datasets[kind, 'test'], path)
            method = f'{prompt}/{model}' + ('' if precheck is None else ('/precheck' if precheck else '/no-precheck'))
            base = {'task_type': kind, 'method': method, 'prompt': prompt, 'model_claimed': model, 'precheck': precheck}
            mappings.append(base | {'result_path': str(path.relative_to(ROOT)), 'sha256': digest(path),
                                    'test_path': f'dataset/{kind}/test.json', 'n': len(data),
                                    'correspondence_basis': 'filename + README + matching table metrics and task IDs',
                                    'historical_executable_commit': None,
                                    'available_related_notebook': None if prompt == 'baseline' else prompt + '.ipynb'})
            subset = []
            for task_id, result in data.items():
                task = task_index[kind, task_id]
                ref = task['reference_length']
                executed = result['attempts']
                actions = result['action script']
                row = base | {k: task[k] for k in ('task_id', 'task_name', 'scene', 'initial_room', 'object', 'operation',
                                                 'destination', 'goal_count', 'required_state_changes')}
                row |= {'outcome': result['result'], 'success': int(result['result'] == 'Success'),
                        'reference_length': ref, 'executed_length': executed, 'length_difference': executed - ref,
                        'length_ratio': executed / ref if ref > 0 else None,
                        'repeated_action_occurrences': len(actions) - len(set(actions)),
                        'zero_reference': ref == 0, 'actions': actions}
                subset.append(row)
            per_task.extend(subset)
            ci = cluster_interval(subset, lambda r: r['success'])
            by_name = {}
            for row in subset:
                by_name.setdefault(row['task_name'], []).append(row['success'])
            metrics.append(base | {'n': len(data), 'success_n': sum(r['success'] for r in subset),
                                   **dict(zip(METRICS[:4], (sum(r['outcome'] == label for r in subset) / len(data)
                                                           for label in LABELS))),
                                   'Average Steps': statistics.mean(r['executed_length'] for r in subset),
                                   'task_name_macro_SR': statistics.mean(statistics.mean(v) for v in by_name.values()),
                                   'SR_cluster_ci_low': ci[0], 'SR_cluster_ci_high': ci[1],
                                   'task_name_clusters': len(by_name)})
            filters = [('all', lambda r: True), ('success', lambda r: bool(r['success'])),
                       ('failure', lambda r: not r['success'])]
            filters += [(label, lambda r, label=label: r['outcome'] == label) for label in LABELS[1:]]
            filters += [('zero_reference', lambda r: r['zero_reference']),
                        ('nonzero_reference', lambda r: not r['zero_reference'])]
            for group_name, condition in filters:
                group = [r for r in subset if condition(r)]
                lengths.append(base | {'group': group_name, 'n': len(group),
                                       'success_n': sum(r['success'] for r in group),
                                       'SR': statistics.mean(r['success'] for r in group) if group else None,
                                       **describe((r['executed_length'] for r in group), 'executed'),
                                       **describe((r['reference_length'] for r in group), 'reference'),
                                       **describe((r['length_difference'] for r in group), 'difference'),
                                       **describe((r['length_ratio'] for r in group if r['length_ratio'] is not None), 'ratio')})
            for dimension in ('task_name', 'scene', 'object', 'destination', 'goal_count', 'required_state_changes', 'reference_length'):
                groups = {}
                for row in subset:
                    groups.setdefault(row[dimension], []).append(row)
                for value, group in groups.items():
                    strata.append(base | {'dimension': dimension, 'value': value, 'n': len(group),
                                          'success_n': sum(r['success'] for r in group),
                                          'SR': statistics.mean(r['success'] for r in group),
                                          'mean_executed': statistics.mean(r['executed_length'] for r in group)})
    csv_write(out / 'result_file_mapping.csv', mappings)
    csv_write(out / 'results_per_task.csv', per_task)
    csv_write(out / 'metrics.csv', metrics)
    csv_write(out / 'lengths_by_outcome.csv', lengths)
    csv_write(out / 'performance_by_task_properties.csv', strata)
    return per_task, metrics, lengths


def paper_check(metrics, out):
    paper = (ROOT / 'Paper/sec5.tex').read_text()
    rows = []
    for line in paper.splitlines():
        if line.strip().endswith('\\\\'):
            values = re.findall(r'(?<!\d)\d+\.\d+', line)
            if len(values) == 5:
                rows.append([float(x) for x in values])
    if len(rows) != len(metrics) or len(metrics) != 18:
        raise ValueError('Expected exactly 18 paper and result rows')
    checks = []
    for source, expected in zip(metrics, rows):
        for metric, value in zip(METRICS, expected):
            computed = round(source[metric], 3)
            checks.append({'task_type': source['task_type'], 'method': source['method'], 'metric': metric,
                           'paper': value, 'recomputed': computed, 'match': computed == value})
    csv_write(out / 'paper_table_checks.csv', checks)
    if not all(c['match'] for c in checks):
        raise ValueError('Paper table differs; inspect paper_table_checks.csv')
    return checks


def comparisons(per_task, out):
    paired, transitions, common = [], [], []
    for kind in TYPES:
        rows = [r for r in per_task if r['task_type'] == kind]
        by_method = {}
        for row in rows:
            by_method.setdefault(row['method'], {})[row['task_id']] = row
        for a, b in itertools.combinations(by_method, 2):
            both = [key for key in by_method[a] if by_method[a][key]['success'] and by_method[b][key]['success']]
            common.append({'task_type': kind, 'method_a': a, 'method_b': b, 'common_success_n': len(both),
                           **describe((by_method[a][k]['executed_length'] for k in both), 'a_executed'),
                           **describe((by_method[b][k]['executed_length'] for k in both), 'b_executed'),
                           **describe((by_method[a][k]['reference_length'] for k in both), 'reference'),
                           **describe((by_method[a][k]['executed_length'] - by_method[b][k]['executed_length']
                                       for k in both), 'a_minus_b')})
        for prompt in ('single-prompt', 'multi-prompts'):
            for model in ('gpt-4o-mini', 'gpt-4o'):
                yes = by_method[f'{prompt}/{model}/precheck']
                no = by_method[f'{prompt}/{model}/no-precheck']
                pairs = [{'task_name': yes[k]['task_name'], 'delta': yes[k]['success'] - no[k]['success']}
                         for k in yes]
                gain = sum(r['delta'] == 1 for r in pairs)
                loss = sum(r['delta'] == -1 for r in pairs)
                ci = cluster_interval(pairs, lambda r: r['delta'])
                paired.append({'task_type': kind, 'prompt': prompt, 'model': model, 'n': len(pairs),
                               'success_with': sum(r['success'] for r in yes.values()),
                               'success_without': sum(r['success'] for r in no.values()),
                               'gain_n': gain, 'loss_n': loss,
                               'both_success_n': sum(yes[k]['success'] and no[k]['success'] for k in yes),
                               'both_failure_n': sum(not yes[k]['success'] and not no[k]['success'] for k in yes),
                               'SR_difference_pp': 100 * (gain - loss) / len(pairs),
                               'difference_ci_low_pp': 100 * ci[0], 'difference_ci_high_pp': 100 * ci[1]})
                for k in yes:
                    transitions.append({'task_type': kind, 'prompt': prompt, 'model': model,
                                        'task_id': k, 'task_name': yes[k]['task_name'],
                                        'without_outcome': no[k]['outcome'], 'with_outcome': yes[k]['outcome'],
                                        'success_delta': yes[k]['success'] - no[k]['success'],
                                        'without_length': no[k]['executed_length'], 'with_length': yes[k]['executed_length']})
    csv_write(out / 'precheck_paired_comparison.csv', paired)
    csv_write(out / 'precheck_transitions.csv', transitions)
    csv_write(out / 'common_success_comparisons.csv', common)
    return paired


def retrieval_analysis(score_path, datasets, per_task, out):
    data = read_json(score_path)
    for path, expected in data['metadata']['source_sha256'].items():
        if digest(ROOT / path) != expected:
            raise ValueError(f'Stale retrieval input: {path}. Re-run reconstruct_retrieval.py.')
    candidates = {}
    for row in data['pairs']:
        candidates.setdefault((row['task_type'], row['test_task_name']), []).append(row)
    selected, per_instance, summaries, by_similarity = [], [], [], []
    for kind in TYPES:
        examples = datasets[kind, 'example']
        test = datasets[kind, 'test']
        example_names = {t['task'] for t in examples.values()}
        reconstructed = {}
        for name in sorted({t['task'] for t in test.values()}):
            ranks = sorted(candidates[kind, name], key=lambda r: (-r['cosine'], r['example_task_name']))
            if len(ranks) != len(example_names) or {r['example_task_name'] for r in ranks} != example_names:
                raise ValueError(f'Incomplete candidate set for {kind}/{name}')
            winner = ranks[0]
            if not all(math.isfinite(r['cosine']) and -1.000001 <= r['cosine'] <= 1.000001 for r in ranks):
                raise ValueError('Invalid cosine value')
            example_id, example = select_example(examples, winner['example_task_name'])
            parts, other = task_parts(name), task_parts(example['task'])
            row = {'task_type': kind, 'test_task_name': name, 'selected_example_name': example['task'],
                   'selected_example_id': example_id, 'cosine': winner['cosine'],
                   'runner_up_name': ranks[1]['example_task_name'], 'runner_up_cosine': ranks[1]['cosine'],
                   'top2_margin': winner['cosine'] - ranks[1]['cosine'],
                   'exact_tie_n': sum(r['cosine'] == winner['cosine'] for r in ranks),
                   'near_tie_1e6_n': sum(winner['cosine'] - r['cosine'] <= 1e-6 for r in ranks),
                   'example_length': len(example['action_scripts']),
                   'example_scene': example['scene'], 'example_initial_room': example['initial_room'],
                   'example_initial_states': example['initial_states'], 'example_actions': example['action_scripts'],
                   **{f'same_{dim}': parts[dim] == other[dim] for dim in ('object', 'operation', 'destination')},
                   'historical_selection_verified': False}
            selected.append(row)
            reconstructed[name] = row
        for task_id, task in test.items():
            row = reconstructed[task['task']]
            per_instance.append(row | {'task_id': task_id, 'test_scene': task['scene'],
                                       'test_initial_room': task['initial_room'], 'test_initial_states': task['initial_states'],
                                       'test_reference_length': len(task['action_scripts']),
                                       'test_reference_actions': task['action_scripts']})
        for weighting, group in [('task_name', [r for r in selected if r['task_type'] == kind]),
                                 ('instance', [r for r in per_instance if r['task_type'] == kind])]:
            summaries.append({'task_type': kind, 'weighting': weighting,
                              **describe((r['cosine'] for r in group), 'cosine'),
                              **{dim + '_rate': statistics.mean(r[dim] for r in group)
                                 for dim in ('same_object', 'same_operation', 'same_destination')},
                              'top2_margin_min': min(r['top2_margin'] for r in group),
                              'exact_tie_rows': sum(r['exact_tie_n'] > 1 for r in group)})
        for method in sorted({r['method'] for r in per_task if r['task_type'] == kind and r['prompt'] != 'baseline'}):
            method_rows = [r for r in per_task if r['task_type'] == kind and r['method'] == method]
            groups = {}
            for result in method_rows:
                r = reconstructed[result['task_name']]
                # Fixed, explicitly descriptive bins; no claim of search correctness.
                bin_name = '<0.8' if r['cosine'] < .8 else ('0.8–0.9' if r['cosine'] < .9 else '>=0.9')
                for dim, value in [('cosine_bin', bin_name)] + [(d, r[d]) for d in ('same_object', 'same_operation', 'same_destination')]:
                    groups.setdefault((dim, value), []).append(result)
            for (dim, value), group in groups.items():
                successes = [r for r in group if r['success']]
                by_similarity.append({'task_type': kind, 'method': method, 'dimension': dim, 'value': value,
                                      'n': len(group), 'success_n': len(successes),
                                      'SR': len(successes) / len(group),
                                      **describe((r['length_difference'] for r in successes), 'success_difference')})
    csv_write(out / 'retrieval_by_task_name.csv', selected)
    csv_write(out / 'retrieval_by_instance.csv', per_instance)
    csv_write(out / 'retrieval_summary.csv', summaries)
    csv_write(out / 'performance_by_retrieval.csv', by_similarity)
    return selected, summaries


def case_studies(per_task, datasets, out):
    cases = []
    fixed = [('state_change_task', 'test_task6', 'Listing 6に対応する成功例'),
             ('placement_task', 'test_task65', 'Listing 7との参照列差・閉鎖不要の例'),
             ('placement_task', 'test_task2', '成功しても同じ行動を反復する例'),
             ('placement_task', 'test_task3', '未操作ゴールIDを含むETFR例'),
             ('placement_task', 'test_task1', '実行失敗だが失敗アクションが保存されていない例'),
             ('placement_task', 'test_task4', 'ゼロ参照列で終了判定に失敗した例')]
    for kind, task_id, reason in fixed:
        row = next(r for r in per_task if r['task_type'] == kind and r['task_id'] == task_id and
                   r['method'] == 'multi-prompts/gpt-4o/precheck')
        task = datasets[kind, 'test'][task_id]
        cases.append(row | {'selection_reason': reason, 'initial_states': task['initial_states'],
                            'goal_states': task['goal_states'], 'reference_actions': task['action_scripts'],
                            'limitation': 'No per-step graph, rejected candidate or failed final action was saved.'})
    csv_write(out / 'case_candidates.csv', cases)
    lines = ['# 掲載候補：保存行動列から確認できる事例', '',
             '目的に沿って選んだ事例であり、無作為標本ではない。原因を断定するには追加ログが必要。', '']
    for row in cases:
        lines += [f'## {row["task_type"]} / {row["task_id"]}', '',
                  f'{row["selection_reason"]}。手法：{row["method"]}。結果：{row["outcome"]}。', '',
                  f'指示：{row["task_name"]}。参照長 {row["reference_length"]}、保存実行長 {row["executed_length"]}。', '',
                  '```json', json.dumps({k: row[k] for k in ('initial_states', 'goal_states', 'reference_actions', 'actions')},
                                       ensure_ascii=False, indent=2), '```', '']
    (out / 'Cases.md').write_text('\n'.join(lines))


def report(out, summaries, metrics, lengths, paired, selected, retrieval_summary):
    lines = ['# 既存実験結果の再集計（手順2）', '',
             '本資料は既存JSONの分析と検索のオフライン再構成である。新しいタスク実行実験ではない。', '',
             '## データセット', '', markdown_table(summaries, [('task_type', 'タスク'), ('split', '集合'), ('n', '件数'),
             ('task_names', 'タスク名数'), ('zero_reference_n', '参照長0'), ('reference_mean', '参照平均長'),
             ('reference_median', '中央値'), ('reference_min', '最小'), ('reference_max', '最大')]), '',
             '## 論文表1・表2の再現', '',
             '全18行×5指標（90値）が本文と小数第3位で一致。詳細は `paper_table_checks.csv`。', '',
             markdown_table(metrics, [('task_type', 'タスク'), ('method', '手法'), ('n', 'N'), ('success_n', '成功数')]
                            + [(k, k) for k in METRICS]), '',
             '## 成功・失敗別の行動列長', '',
             '参照平均も同じ成功／失敗集合で計算。空集合は「—」。全ての分位点・標準偏差・比率は `lengths_by_outcome.csv`。', '',
             markdown_table([r for r in lengths if r['group'] in ('success', 'failure')],
                            [('task_type', 'タスク'), ('method', '手法'), ('group', '集合'), ('n', 'N'),
                             ('executed_mean', '保存平均長'), ('reference_mean', '参照平均長'),
                             ('difference_mean', '平均差')]), '',
             '## 前提条件検証の対応比較', '',
             markdown_table(paired, [('task_type', 'タスク'), ('prompt', '提示'), ('model', 'モデル'),
                            ('gain_n', '失敗→成功'), ('loss_n', '成功→失敗'), ('SR_difference_pp', 'SR差 pp'),
                            ('difference_ci_low_pp', '95%区間下限'), ('difference_ci_high_pp', '95%区間上限')]), '',
             '## 検索類似度（新しく再構成した検索）', '',
             markdown_table(retrieval_summary, [('task_type', 'タスク'), ('weighting', '重み'), ('cosine_n', 'N'),
                            ('cosine_mean', '平均cosine'), ('cosine_min', '最小'), ('cosine_max', '最大'),
                            ('same_object_rate', '対象一致率'), ('same_operation_rate', '操作一致率'),
                            ('same_destination_rate', '配置先一致率'), ('exact_tie_rows', '同点件数')]), '',
             '状態変化の配置先は両方空欄のため一致率1となるが、配置先検索の性能指標ではない。', '',
             '### 再構成された検索の具体例', '',
             markdown_table([r for r in selected if r['task_type'] == 'state_change_task' or
                             r['test_task_name'] in ('Put all plums in the fridge', 'Put all bananas in the fridge',
                                                    'Put all cupcakes on the kitchencounter')],
                            [('test_task_name', 'テスト指示'), ('selected_example_name', '採択事例'),
                             ('selected_example_id', '事例ID'), ('cosine', 'cosine'),
                             ('example_length', '事例列長'), ('same_operation', '操作一致')]), '',
             '状態変化では `Turn off all computers` と `Turn off all tablelamps` に、同じ対象をONにする事例が選ばれた。'
             '高いcosineは操作の一致を保証しない。配置ではテスト件数で重み付けすると対象一致率は約89.3%だが、'
             '配置先一致率は約10.7%。これらは検索の正解率ではなく、選択事例と共有する構造の記述である。', '',
             '## 集計の定義と解釈', '',
             '- 分母は状態変化312件、配置103件。SRと3失敗率は全件を分母とする。保存の全タスクID・ラベル・score・列長の整合性を検証した。',
             '- `attempts` は全保存結果で行動列長と等しい。公開提案実装では成功した実行のみが列に追加される。最後の失敗試行、再生成、LLM呼び出し数を含まない。ベースラインの保存規則の詳細は未回収。',
             '- 参照列は最短解ではない。失敗時は早期終了で短くなるため、短さを効率の改善と解釈しない。差・比は成功集合での解釈を主とする。',
             '- `length_ratio` は参照長が正のときのみ定義する。参照長0の状態変化27件、配置2件は独立集計。初期充足は参照長0からの代理分類で、完全な初期グラフによる再検証ではない。',
             '- ベースラインの状態変化成功10件はすべて参照長0。非ゼロ285件の成功は0。配置ベースライン成功は0。',
             '- 分位点は線形補間（type 7）、標準偏差は標本標準偏差（n−1）。n=0の統計量とn<2の標準偏差は空欄。比の分母数もCSVに保存する。',
             '- 手法間の共通成功集合を全組合せで比較し `common_success_comparisons.csv` に出力した。選択バイアスを完全には除けない。',
             '- 信頼区間はタスク名を単位とするクラスター・ブートストラップ4000回、seed=20260906、百分位法95%。抽出された各クラスターの全インスタンスを保持してmicro SRを計算。対応比較では条件間で同じタスクを再標本化する。',
             '- 同じシーンによる依存、少数クラスター（状態変化6名）、反復実験の欠如はこの区間では解消しない。モデルの実行間変動は推定していない。p値や因果効果は主張しない。タスク名マクロ平均は `metrics.csv`。',
             '- 同名タスクは両集合で重複0だが、シーン1～7・操作構造は共有する。未知家屋汎化を測る評価ではない。網羅表は観測された組合せのみ。',
             '- 検索は元のエンコーダ名とcosineを使い、名前ごとの上位1件→同名の最長列（長さ同点はJSONの先頭）を選択。候補名はソートして同点時の選択を決定的にした。元コードのset順序、実験時の重み版・実行依存関係は不明。',
             '- `retrieval_scores.json` に重みハッシュ・版・依存関係と全候補スコアを保存。これは過去の検索ログではない。検索条件別SRも再構成結果との記述的な関連で、検索の正解率や因果的寄与ではない。',
             '- `repeated_action_occurrences` は同一文字列の2回目以降の数であり、必要な反復も含む。冗長行動の正解ラベルではない。', '',
             '個別事例は [Cases.md](Cases.md)、来歴・未回収項目は [Evidence.md](Evidence.md)、再実行手順は [README.md](README.md)。', '']
    (out / 'Report.md').write_text('\n'.join(lines))
    # Standalone LaTeX tables for insertion after review; no mutation of the paper.
    tex = ['% Generated from stored result JSON. Average Steps = saved action-list length.',
           '\\begin{tabular}{llrrrrrr}', '\\hline',
           'Task & Method & N & SR & AEFR & FRRMA & ETFR & Steps \\\\', '\\hline']
    for row in metrics:
        task = 'State' if row['task_type'] == 'state_change_task' else 'Placement'
        tex.append(f'{task} & {row["method"]} & {row["n"]} & ' +
                   ' & '.join(f'{row[k]:.3f}' for k in METRICS) + ' \\\\')
    tex += ['\\hline', '\\end{tabular}', '']
    (out / 'tables.tex').write_text('\n'.join(tex))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'Paper/analysis')
    parser.add_argument('--retrieval-scores', type=Path, default=ROOT / 'Paper/analysis/retrieval_scores.json')
    args = parser.parse_args()
    out = args.output.resolve()
    if not (out == ROOT / 'Paper/analysis' or out.is_relative_to(ROOT / 'Paper/analysis')):
        parser.error('output must be inside Paper/analysis (derived artifacts only)')
    if not args.retrieval_scores.is_file():
        parser.error('Run reconstruct_retrieval.py first, or supply --retrieval-scores')
    out.mkdir(parents=True, exist_ok=True)
    before = {p: digest(p) for folder in ('dataset', 'result') for p in (ROOT / folder).rglob('*.json')}
    inventory(out)
    settings_inventory(out)
    datasets = {(kind, split): read_json(ROOT / 'dataset' / kind / f'{split}.json')
                for kind in TYPES for split in ('test', 'example')}
    tasks, summaries = dataset_analysis(datasets, out)
    per_task, metrics, lengths = result_analysis(datasets, tasks, out)
    checks = paper_check(metrics, out)
    paired = comparisons(per_task, out)
    selected, retrieval_summary = retrieval_analysis(args.retrieval_scores, datasets, per_task, out)
    case_studies(per_task, datasets, out)
    report(out, summaries, metrics, lengths, paired, selected, retrieval_summary)
    if not all(digest(p) == value for p, value in before.items()):
        raise RuntimeError('An input dataset/result changed during analysis')
    receipt = {'kind': 'derived_analysis_not_new_simulator_results', 'source_head': git('rev-parse', 'HEAD'),
               'source_manifest_sha256': digest(out / 'source_manifest.csv'),
               'script_sha256': digest(Path(__file__)), 'retrieval_scores_sha256': digest(args.retrieval_scores),
               'reconstruction_script_sha256': digest(ROOT / 'scripts/reconstruct_retrieval.py'),
               'python_version': sys.version, 'bootstrap_seed': 20260906, 'bootstrap_repetitions': 4000,
               'checks': {'paper_values_match': len(checks), 'result_files': len(metrics),
                          'result_rows': len(per_task), 'dataset_rows': len(tasks),
                          'reconstructed_task_names': len(selected), 'input_json_unchanged': True}}
    (out / 'analysis_receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt['checks'], indent=2))


if __name__ == '__main__':
    main()
