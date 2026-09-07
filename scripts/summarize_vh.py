"""Offline tables from VH run logs. No simulator, network or API requests."""
import argparse
import csv
import gzip
import json
import math
from collections import defaultdict
from pathlib import Path

from vh_experiment import ROOT, OUT, SELECTED, ARMS, MODELS, write, goal, symbolic, object_hash, comparable
from vh_fixed_initial import alignment


def read_lines(path):
    if not path.exists():
        return []
    text = path.read_text()
    return [json.loads(line) for line in text.splitlines() if line] if text.endswith('\n') else [
        json.loads(line) for line in text.rsplit('\n', 1)[0].splitlines() if line] if '\n' in text else []


def save_csv(name, rows):
    if not rows:
        return
    with (OUT / name).open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def graph(folder, name):
    with gzip.open(folder / name, 'rt') as f:
        return json.load(f)


def transform_delta(a, b):
    """Max node position distance, including avatar; returns None for missing nodes/transforms."""
    nodes = [{n['id']: n for n in g['nodes']} for g in [a, b]]
    if nodes[0].keys() != nodes[1].keys():
        return None
    deltas = []
    for key, first in nodes[0].items():
        p = first.get('obj_transform', {}).get('position')
        q = nodes[1][key].get('obj_transform', {}).get('position')
        if p is None or q is None:
            return None
        deltas.append(math.dist(p, q))
    return max(deltas, default=0)


def summary():
    fixed = json.loads((OUT / 'config.json').read_text())['design'].startswith('prospective_fixed')
    results = []
    for path in sorted((OUT / 'runs').glob('*/result.json')):
        row = json.loads(path.read_text())
        row['_folder'] = path.parent
        results.append(row)
    by_id = {r['run_id']: r for r in results}
    api = read_lines(OUT / 'api_log.jsonl')
    calls = defaultdict(list)
    for r in api:
        calls[r['run_id']].append(r)
    episodes, checks, terminations, executions, initial = [], [], [], [], []
    for result in results:
        folder = result['_folder']
        events = read_lines(folder / 'events.jsonl')
        task = json.loads((ROOT / f'dataset/{result["kind"]}/test.json').read_text())[result['task_id']]
        final = graph(folder, result['final_graph'])
        assert goal(final, task) == result['final_goal'], result['run_id']
        reference_id = f'{result["kind"]}_{result["task_id"]}_reference_reference'
        reference = by_id.get(reference_id)
        own_calls = calls[result['run_id']]
        ok_calls = [r for r in own_calls if r['status'] == 'ok']
        episodes.append({'run_id': result['run_id'], 'kind': result['kind'], 'task_id': result['task_id'],
              'arm': result['arm'], 'model': result['model'] or 'reference',
              'reference_outcome': reference['outcome'] if reference else 'missing',
              'outcome': result['outcome'], 'score_original_rule': result['score_original_rule'],
              'final_goal_satisfied': result['final_goal']['all_satisfied'],
              'reference_length': result['reference_length'], 'executed_successful_actions': len(result['actions']),
              'execution_attempts': result['execution_attempts'],
              'failed_execution_attempts': result['execution_attempts'] - len(result['actions']),
              'api_successful_requests': len(ok_calls), 'api_failed_requests': len(own_calls) - len(ok_calls),
              'api_requests_in_prior_incomplete_attempts': sum(r['utc'] < events[0]['utc'] for r in own_calls),
              'input_tokens': sum(r['response']['usage']['prompt_tokens'] for r in ok_calls),
              'output_tokens': sum(r['response']['usage']['completion_tokens'] for r in ok_calls),
              'estimated_usd_uncached': sum(r['estimated_usd'] for r in ok_calls),
              'elapsed_seconds': result['elapsed_seconds']})
        if result['arm'] != 'reference':
            baseline_id = f'{result["kind"]}_{result["task_id"]}_C0_no_precheck_{result["model"]}'
            baseline = by_id.get(baseline_id)
            if baseline:
                first = graph(folder, result['initial']['graph_file'])
                base_graph = graph(baseline['_folder'], baseline['initial']['graph_file'])
                initial.append({'run_id': result['run_id'], 'baseline_run_id': baseline_id,
                   'symbolic_state_equal_to_C0': comparable(first) == comparable(base_graph),
                   'full_graph_equal_to_C0': first == base_graph,
                   'max_node_position_distance_to_C0': transform_delta(first, base_graph),
                   'position_rotation_symbolic_alignment_to_C0': alignment(first, base_graph)['passed'],
                   'max_quaternion_distance_to_C0': alignment(first, base_graph)['max_quaternion_distance'],
                   'symbolic_state_equal_to_reference': result['initial']['symbolic_hash'] == reference['initial']['symbolic_hash']
                        if reference else '',
                   'agent_initial_position': json.dumps(result['initial']['agent_transform'].get('position'))})
        extraction, candidate = {}, {}
        for event in events:
            step = event['step']
            if event['phase'] == 'extracted_knowledge':
                extraction[step] = event
            elif event['phase'] == 'candidate_diagnostic':
                candidate[step] = event
            elif event['phase'] == 'precondition':
                gold_label = candidate[step]['json_conditions']['label']
                accepted = 'Yes' in event['response']
                checks.append({'run_id': result['run_id'], 'step': step, 'model': result['model'],
                      'action': candidate[step]['action'], 'gold_json_conditions': gold_label,
                      'accepted': accepted, 'response': event['response'],
                      'correct_when_known': accepted == (gold_label == 'true') if gold_label in ('true', 'false') else '',
                      'not_vh_executability_label': True})
            elif event['phase'] == 'termination':
                truth = extraction[step]['goal']['all_satisfied']
                ended = event['response'] == 'End'
                terminations.append({'run_id': result['run_id'], 'step': step, 'model': result['model'],
                       'arm': result['arm'], 'gold_complete': truth, 'ended': ended,
                       'response': event['response'], 'correct': truth == ended,
                       'strict_format': event['response'] in ('End', 'Continue')})
            elif event['phase'] == 'execution':
                executions.append({'run_id': result['run_id'], 'step': step, 'model': result['model'] or 'reference',
                      'arm': result['arm'], 'action': event['action'], 'vh_success': event['simulator_result'][0],
                      'json_condition_label': event['json_conditions']['label'] if event['json_conditions'] else 'not_scored_reference',
                      'candidate_was_regenerated': event['action'] != candidate[step]['action'] if step in candidate else '',
                      'before_goal': event['before_goal']['all_satisfied'], 'after_goal': event['after_goal']['all_satisfied'],
                      'vh_message': json.dumps(event['simulator_result'][1], ensure_ascii=False),
                      'before_graph': event['before_graph'], 'after_graph': event['after_graph']})
    for name, rows in [('episodes.csv', episodes), ('precondition_labels.csv', checks),
                       ('termination_labels.csv', terminations), ('execution_labels.csv', executions),
                       ('initial_comparability.csv', initial)]:
        save_csv(name, rows)
    groups = defaultdict(list)
    for row in episodes:
        if row['arm'] == 'reference':
            continue
        groups[row['model'], row['arm'], 'all_four_diagnostic'].append(row)
        if row['reference_outcome'] == 'Reference Success':
            groups[row['model'], row['arm'], 'reference_passed_only'].append(row)
    metrics = []
    for (model, arm, subset), rows in groups.items():
        metrics.append({'model': model, 'arm': arm, 'subset': subset, 'n': len(rows),
             'success_original_rule': sum(r['outcome'] == 'Success' for r in rows),
             'final_goal_satisfied': sum(r['final_goal_satisfied'] for r in rows),
             'mean_successful_action_count': sum(r['executed_successful_actions'] for r in rows) / len(rows),
             'failed_execution_attempts': sum(r['failed_execution_attempts'] for r in rows),
             'api_requests': sum(r['api_successful_requests'] for r in rows),
             'estimated_usd_uncached': sum(r['estimated_usd_uncached'] for r in rows)})
    save_csv('metrics.csv', metrics)
    known = defaultdict(list)
    for row in checks:
        if row['gold_json_conditions'] in ('true', 'false'):
            known[row['model']].append(row)
    checker_metrics = []
    for model, rows in known.items():
        tp = sum(r['accepted'] and r['gold_json_conditions'] == 'true' for r in rows)
        fp = sum(r['accepted'] and r['gold_json_conditions'] == 'false' for r in rows)
        tn = sum(not r['accepted'] and r['gold_json_conditions'] == 'false' for r in rows)
        fn = sum(not r['accepted'] and r['gold_json_conditions'] == 'true' for r in rows)
        checker_metrics.append({'model': model, 'n': len(rows), 'tp': tp, 'fp': fp, 'tn': tn, 'fn': fn,
                               'accuracy': (tp + tn) / len(rows),
                               'precision': tp / (tp + fp) if tp + fp else '',
                               'recall': tp / (tp + fn) if tp + fn else '',
                               'false_accept_rate': fp / (fp + tn) if fp + tn else '',
                               'false_reject_rate': fn / (fn + tp) if fn + tp else ''})
    save_csv('precondition_metrics.csv', checker_metrics)
    termination_groups = defaultdict(list)
    for row in terminations:
        termination_groups[row['model'], row['arm']].append(row)
    termination_metrics = []
    for (model, arm), rows in termination_groups.items():
        termination_metrics.append({'model': model, 'arm': arm, 'n': len(rows),
            'correct': sum(r['correct'] for r in rows),
            'false_end': sum(r['ended'] and not r['gold_complete'] for r in rows),
            'false_continue': sum(not r['ended'] and r['gold_complete'] for r in rows),
            'strict_format': sum(r['strict_format'] for r in rows),
            'accuracy': sum(r['correct'] for r in rows) / len(rows)})
    save_csv('termination_metrics.csv', termination_metrics)
    repairs = defaultdict(list)
    for row in executions:
        if row['candidate_was_regenerated'] is True:
            repairs[row['model'], row['arm']].append(row)
    save_csv('changed_action_metrics.csv', [
        {'model': model, 'arm': arm, 'changed_executed_actions': len(rows),
         'json_condition_true': sum(r['json_condition_label'] == 'true' for r in rows),
         'json_condition_unknown': sum(r['json_condition_label'] == 'unknown' for r in rows),
         'vh_success': sum(r['vh_success'] for r in rows)} for (model, arm), rows in repairs.items()])
    expected = {f'{kind}_{task_id}_{arm}_{model}' for kind, task_id in SELECTED for arm in ARMS for model in MODELS}
    missing = sorted(expected - by_id.keys())
    costs = {'successful_requests': sum(r['status'] == 'ok' for r in api),
             'failed_requests': sum(r['status'] != 'ok' for r in api),
             'input_tokens': sum(r['response']['usage']['prompt_tokens'] for r in api if r['status'] == 'ok'),
             'output_tokens': sum(r['response']['usage']['completion_tokens'] for r in api if r['status'] == 'ok'),
             'estimated_usd_uncached': sum(r['estimated_usd'] for r in api if r['status'] == 'ok'),
             'failed_call_reservation_usd': sum(r['reserved_usd'] for r in api if r['status'] != 'ok')}
    write(OUT / 'costs.json', costs)
    write(OUT / 'completion.json', {'planned_comparison_episodes': 24, 'completed_comparison_episodes': 24 - len(missing),
          'missing_comparison_episodes': missing, 'reference_episodes': sum(r['arm'] == 'reference' for r in results),
          'reference_successes': sum(r['outcome'] == 'Reference Success' for r in results),
          'recorded_execution_attempts_in_reference_and_comparison': len(executions),
          'api': costs, 'human_participants': 0, 'latex_executed': False})
    lines = ['# VH小規模比較実験の結果', '',
             f'比較エピソードは予定24件中{24 - len(missing)}件完了。対象4件、2モデル、3条件、各1反復。', '',
             '## 参照行動列の再生', '',
             '| 種別 | ID | 参照長 | 成功行動数 | 結果 | 最終ゴール |',
             '| --- | --- | ---: | ---: | --- | --- |']
    for row in episodes:
        if row['arm'] == 'reference':
            lines.append(f'| {row["kind"]} | {row["task_id"]} | {row["reference_length"]} | {row["executed_successful_actions"]} | {row["outcome"]} | {row["final_goal_satisfied"]} |')
    lines += ['', '配置test_task1の参照列は4手目のPUTで失敗。元の位置指定の予備実験では別途PUTBACKも同じ物体・配置先で失敗した。保持・近接を満たすだけではこの配置が実行できると保証できない。',
              'この例は除外して隠さず診断対象として残す。参照列が全件再現できたとは主張せず、参照再生成功3件のみの集計も分ける。', '',
              '## 比較（全4件、参照失敗例を含む診断集計）', '',
              '| モデル | 条件 | n | 元の成功判定 | 最終ゴール充足 | 平均保存行動数 | 失敗実行数 |',
              '| --- | --- | ---: | ---: | ---: | ---: | ---: |']
    for row in metrics:
        if row['subset'] == 'all_four_diagnostic':
            lines.append(f'| {row["model"]} | {row["arm"]} | {row["n"]} | {row["success_original_rule"]} | {row["final_goal_satisfied"]} | {row["mean_successful_action_count"]:.2f} | {row["failed_execution_attempts"]} |')
    lines += ['', '平均保存行動数は成功・失敗を含み、失敗した最後の実行は含まない。短い失敗を効率改善と解釈しない。',
              '状態変化test_task1は参照長0の終了判定例。単一試行の小標本であり、統計的有意差や全415タスクへの一般化は主張しない。', '',
              '## 初期条件の照合', '',
              f'C0との記号状態一致は{sum(r["symbolic_state_equal_to_C0"] for r in initial)}/{len(initial)}件（C0自身を含む）。',
              f'完全グラフ一致は{sum(r["full_graph_equal_to_C0"] for r in initial)}/{len(initial)}件。',
              'initial_comparability.csvに全対象・モデル・条件の一致判定と全ノード位置の最大差を保存した。記号状態の一致だけでは物理状態の同一性は保証しない。',
              ('この追加試行は人物位置を指定し直した新しい設定であり、過去実験や元の部屋指定の試行を置き換えない。各条件はAPI呼出前に参照の記号状態一致・全ノード位置差0.001以下・四元数距離0.0001以下を検査した。物理エンジンやLLM応答の完全決定性は保証しない。'
               if fixed else '元コードと同じ初期部屋指定を使い、初期位置を後付けで一致させていない。不一致がある比較は機構の独立した因果効果と解釈しない。'),
              f'C0以外の条件で位置・向き・記号状態の基準を満たす比較は{sum(r["position_rotation_symbolic_alignment_to_C0"] for r in initial if r["run_id"] != r["baseline_run_id"])}/{sum(r["run_id"] != r["baseline_run_id"] for r in initial)}件。', '',
              '## 判定・実行ログ', '',
              'precondition_labels.csvは実際のC1候補に対する、抽出知識上のJSON条件ラベルとLLM応答。unknownは二値精度から除く。',
              'termination_labels.csvは各時点の完全グラフと元のEnd完全一致判定を照合する。execution_labels.csvは実行した行動に限ったVHラベルであり、棄却した候補の実行可能性を捏造しない。',
              'C2のラベル生成器と同じ規則を診断に使うため、C2自身の正解率によって規則の妥当性を立証しない。', '',
              'precondition_metrics.csvにC1の混同行列・適合率・再現率・誤受理率・誤棄却率、termination_metrics.csvに全途中時点の終了判定の混同行列相当の件数を保存した。',
              'changed_action_metrics.csvは候補と異なる行動を実行した場合だけの集計であり、同じ文字列を返した再生成は含まない。違反説明の意味的正しさや棄却候補の反実仮想実行は未評価。', '',
              '## 費用・範囲', '',
              f'API成功要求{costs["successful_requests"]}件、失敗{costs["failed_requests"]}件。入力{costs["input_tokens"]}tokens、出力{costs["output_tokens"]}tokens。',
              f'成功要求の通常単価による推定費用は{costs["estimated_usd_uncached"]:.6f}米ドル（キャッシュ割引を適用しない推定、請求確定額ではない）。',
              '通信障害で中断した試行のAPI要求も費用に含む。episodes.csvのapi_requests_in_prior_incomplete_attemptsで完了試行以前の要求を区別する。中断したVH要求は実行成否が未確定のため実行ラベルの分母に含めない。',
              '[GPT-4o料金](https://developers.openai.com/api/docs/models/gpt-4o)、[GPT-4o mini料金](https://developers.openai.com/api/docs/models/gpt-4o-mini)。', '',
              '原稿のモデルID、元のMulti計画ループ・プロンプト・上限判定を使用するが、現在の依存版とWindows VHによる新しい試行であり、過去結果の完全再現ではない。',
              'C3/C4/C5、検索条件を変えた実行比較、全件・複数反復、人間評価は未実施。TeXは実行していない。詳細は'
              + ('[README.md](../README.md)。ケース説明案は[Cases.md](../Cases.md)。' if fixed else '[README.md](README.md)。ケース説明案は[Cases.md](Cases.md)。')]
    (OUT / 'Report.md').write_text('\n'.join(lines) + '\n')
    print(f'Compared {24 - len(missing)}/24 episodes; API estimate ${costs["estimated_usd_uncached"]:.6f}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--fixed-initial', action='store_true')
    args = parser.parse_args()
    if args.fixed_initial:
        OUT = OUT / 'fixed_initial'
    summary()
