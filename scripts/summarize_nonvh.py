"""Recompute all API evaluation tables from immutable inputs and raw responses."""
import csv
import json
import platform
import ssl
from collections import defaultdict
from nonvh_analysis import ROOT, OUT, MODELS, csvsave, save, evaluate, digest
from run_nonvh_api import read_logs


def rate(a, b):
    return a / b if b else ''


def summarize():
    cases = {r['id']: r for r in json.loads((OUT / 'cases.json').read_text())}
    logs = read_logs()
    good = {r['call_id']: r for r in logs if r['status'] == 'ok'}
    labels, groups = [], defaultdict(list)
    for row in good.values():
        if row['phase'] not in ('precondition', 'termination'):
            continue
        case = cases[row['case_id']]
        if row['phase'] == 'precondition':
            prediction = 'true' if 'Yes' in row['text'] else 'false'
            strict = row['text'] in ('Yes', 'No')
            gold = case['gold']
        else:
            prediction = 'End' if row['text'] == 'End' else 'Continue'
            strict = row['text'] in ('End', 'Continue')
            gold = case['gold']
        item = {'case_id': case['id'], 'model': row['requested_model'], 'repeat': row['repeat'],
                'kind': case['kind'], 'origin': case['origin'], 'gold': gold,
                'operation': case.get('operation', ''), 'variant': case.get('variant', ''),
                'prediction_original_branch': prediction, 'strict_format': strict,
                'correct': prediction == gold if gold != 'unknown' else '', 'response': row['text']}
        labels.append(item)
        groups[item['model'], item['kind'], item['repeat']].append(item)
        groups[item['model'], item['kind'], 'all'].append(item)
    csvsave('api_labels.csv', labels)
    atomic_groups = defaultdict(list)
    for row in labels:
        if row['kind'] == 'precondition':
            atomic_groups[row['model'], row['operation'], row['variant']].append(row)
    csvsave('precondition_by_variant.csv', [
        {'model': model, 'operation': op, 'variant': variant, 'n': len(rows), 'gold': rows[0]['gold'],
         'accepted': sum(r['prediction_original_branch'] == 'true' for r in rows),
         'correct_known': sum(r['correct'] is True for r in rows) if rows[0]['gold'] != 'unknown' else '',
         'response_variants': len({r['response'] for r in rows})}
        for (model, op, variant), rows in atomic_groups.items()])
    example_lines = ['# 静的評価の誤判定事例', '',
        '以下は新規の合成入力に対するAPI応答。元のVH実行失敗の原因分析ではない。',
        'goldは既知の有限close/held集合を前提とする。元の自然言語変換は空集合を文にしないため、入力表現と評価仮定の隔たりに注意する。', '']
    picked = set()
    for row in labels:
        if row['correct'] is not False or row['kind'] != 'precondition' or row['operation'] in picked:
            continue
        picked.add(row['operation'])
        case = cases[row['case_id']]
        example_lines += [f'## {row["case_id"]}', '',
            f'モデル `{row["model"]}`、反復 {row["repeat"]}、正解 `{row["gold"]}`、元分岐 `{row["prediction_original_branch"]}`。', '',
            '入力環境：', '', '```text', case['env'].rstrip(), '```', '',
            f'候補：`{case["action"]}`', '',
            '構造化事実：', '', '```json', json.dumps(case['facts'], ensure_ascii=False, indent=2), '```', '',
            '違反条件：' + ' / '.join(case['oracle']['violations']), '',
            '生応答：', '', '```text', row['response'], '```', '']
        if len(picked) == 6:
            break
    end_picked = set()
    for row in labels:
        if row['kind'] != 'termination' or row['correct'] is not False or row['case_id'] in end_picked:
            continue
        end_picked.add(row['case_id'])
        case = cases[row['case_id']]
        example_lines += [f'## {row["case_id"]}', '',
            f'モデル `{row["model"]}`、反復 {row["repeat"]}、由来 `{row["origin"]}`。', '',
            f'タスク：{case["task"]}。正解 `{row["gold"]}`、元分岐 `{row["prediction_original_branch"]}`。', '',
            '```text', case['env'].rstrip(), '```', '', '生応答：', '', '```text', row['response'], '```', '']
        if len(end_picked) == 3:
            break
    (OUT / 'Cases.md').write_text('\n'.join(example_lines) + '\n')
    metrics = []
    for (model, kind, repeat), items in groups.items():
        known = [r for r in items if r['gold'] != 'unknown']
        positive = 'true' if kind == 'precondition' else 'End'
        tp = sum(r['gold'] == positive and r['prediction_original_branch'] == positive for r in known)
        tn = sum(r['gold'] != positive and r['prediction_original_branch'] != positive for r in known)
        fp = sum(r['gold'] != positive and r['prediction_original_branch'] == positive for r in known)
        fn = sum(r['gold'] == positive and r['prediction_original_branch'] != positive for r in known)
        metrics.append({'model': model, 'kind': kind, 'repeat': repeat, 'n_labeled': len(known),
                        'unknown_excluded': len(items) - len(known), 'tp': tp, 'tn': tn, 'fp': fp, 'fn': fn,
                        'accuracy': rate(tp + tn, len(known)), 'precision': rate(tp, tp + fp),
                        'recall': rate(tp, tp + fn), 'false_acceptance_rate': rate(fp, fp + tn),
                        'false_rejection_rate': rate(fn, tp + fn),
                        'noncanonical_format_count': sum(not r['strict_format'] for r in items)})
    csvsave('api_metrics.csv', metrics)
    repair_rows, unmet_rows = [], []
    for case in cases.values():
        if case.get('variant') != 'violate_1':
            continue
        for model in MODELS:
            check = good.get(f'{model}/{case["id"]}/precondition/0')
            for arm in ['C0_fixed_candidate', 'C1_llm_feedback', 'C2_symbolic_feedback', 'C4_neutral_revision']:
                key = f'{model}/{case["id"]}/{arm}/0'
                if arm == 'C0_fixed_candidate':
                    text, status = case['action'], 'offline_fixed_candidate'
                elif arm == 'C1_llm_feedback' and check and 'Yes' in check['text']:
                    text, status = case['action'], 'accepted_without_revision'
                elif key in good:
                    text, status = good[key]['text'], 'regenerated'
                else:
                    continue
                evaluation = evaluate(text, case['facts'])
                repair_rows.append({'case_id': case['id'], 'model': model, 'arm': arm, 'repeat': 0,
                                    'status': status, 'action': text, 'json_condition_label': evaluation['label'],
                                    'stripped_action_label': evaluate(text.strip(), case['facts'])['label'],
                                    'task_progress': 'not_evaluated', 'vh_executable': 'not_evaluated'})
            unmet = good.get(f'{model}/{case["id"]}/unmet/0')
            if unmet:
                unmet_rows.append({'case_id': case['id'], 'model': model,
                                   'gold_violations': json.dumps(case['oracle']['violations']),
                                   'response': unmet['text'], 'human_correctness_label': '', 'reviewer': ''})
    csvsave('repair_labels.csv', repair_rows)
    csvsave('unmet_review_blank.csv', unmet_rows)
    repair_groups = defaultdict(list)
    for row in repair_rows:
        repair_groups[row['model'], row['arm']].append(row)
    repair_summary = []
    for (model, arm), rows in repair_groups.items():
        repair_summary.append({'model': model, 'arm': arm, 'n': len(rows),
                               'conditions_satisfied': sum(r['json_condition_label'] == 'true' for r in rows),
                               'conditions_violated': sum(r['json_condition_label'] == 'false' for r in rows),
                               'unknown': sum(r['json_condition_label'] == 'unknown' for r in rows),
                               'invalid_format_or_object': sum(r['json_condition_label'].startswith('invalid') for r in rows),
                               'task_success_rate': 'not_measured'})
    csvsave('repair_summary.csv', repair_summary)
    costs = []
    for model in MODELS:
        rows = [r for r in logs if r['requested_model'] == model]
        ok = [r for r in rows if r['status'] == 'ok']
        costs.append({'model': model, 'successful_requests': len(ok), 'failed_requests': len(rows) - len(ok),
                      'input_tokens': sum(r['response']['usage']['prompt_tokens'] for r in ok),
                      'output_tokens': sum(r['response']['usage']['completion_tokens'] for r in ok),
                      'estimated_usd_uncached': sum(r['estimated_usd'] for r in ok),
                      'failed_request_reserved_usd': sum(r['reserved_usd'] for r in rows if r['status'] != 'ok'),
                      'sum_request_seconds': sum(r['elapsed_seconds'] for r in rows)})
    csvsave('costs.csv', costs)
    phase_groups = defaultdict(list)
    for row in good.values():
        phase_groups[row['requested_model'], row['phase']].append(row)
    csvsave('phase_costs.csv', [{'model': model, 'phase': phase, 'requests': len(rows),
             'input_tokens': sum(r['response']['usage']['prompt_tokens'] for r in rows),
             'output_tokens': sum(r['response']['usage']['completion_tokens'] for r in rows),
             'estimated_usd_uncached': sum(r['estimated_usd'] for r in rows),
             'sum_request_seconds': sum(r['elapsed_seconds'] for r in rows)}
             for (model, phase), rows in phase_groups.items()])
    expected = {f'{model}/{case["id"]}/{case["kind"]}/{rep}'
                for model in MODELS for case in cases.values() for rep in range(3)}
    missing = sorted(expected - good.keys())
    missing_repairs = []
    for case in cases.values():
        if case.get('variant') != 'violate_1':
            continue
        for model in MODELS:
            for arm in ['C1_llm_feedback', 'C2_symbolic_feedback', 'C4_neutral_revision']:
                if not any(r['case_id'] == case['id'] and r['model'] == model and r['arm'] == arm for r in repair_rows):
                    missing_repairs.append(f'{model}/{case["id"]}/{arm}/0')
    save('completion.json', {'planned_component_calls': len(expected), 'missing_component_calls': missing,
                           'missing_repair_outputs': missing_repairs, 'successful_api_requests': len(good),
                           'api_error_count': sum(r['status'] != 'ok' for r in logs),
                           'vh_runs': 0, 'human_participants': 0, 'latex_runs': 0})
    source_files = [ROOT / f'scripts/{name}.py' for name in
                    ['nonvh_analysis', 'run_nonvh_api', 'summarize_nonvh', 'test_nonvh']]
    save('execution_receipt.json', {'python': platform.python_version(), 'openssl': ssl.OPENSSL_VERSION,
         'platform': platform.platform(), 'third_party_packages_required': [],
         'script_sha256': {str(p.relative_to(ROOT)): digest(p) for p in source_files},
         'api_log_sha256': digest(OUT / 'api_log.jsonl') if (OUT / 'api_log.jsonl').exists() else None,
         'config_sha256': digest(OUT / 'config.json')})
    lines = ['# VH不要部分の新規評価結果', '',
             'この結果は新しい静的コンポーネント評価であり、既存18条件の再実験でもVH実行成功率でもない。', '',
             f'計画した判定呼び出し264件中、未完了{len(missing)}件。修正出力の未完了{len(missing_repairs)}件。', '',
             '## 前提条件・終了判定（3反復合算）', '',
             '| モデル | 評価 | ラベル既知の判定数 | 正解数 | 誤受理 | 誤棄却 | 情報不足・除外 |',
             '| --- | --- | ---: | ---: | ---: | ---: | ---: |']
    for r in metrics:
        if r['repeat'] == 'all':
            lines.append(f'| {r["model"]} | {r["kind"]} | {r["n_labeled"]} | {r["tp"] + r["tn"]} | {r["fp"]} | {r["fn"]} | {r["unknown_excluded"]} |')
    lines += ['', '独立問題数は前提条件24（別に情報不足4）、終了16。同じ問題の反復を独立標本とする検定は行わない。',
              '終了判定の正例はEnd。前提条件は元実装のYes部分文字列、終了はEnd完全一致で採点。非定型応答件数もCSVに保存する。', '',
              '## 固定不正候補に対する1回修正（各モデル・条件8件、1反復）', '',
              '| モデル | 条件 | n | JSON条件充足 | 違反 | 不明 | 書式・ID不正 |',
              '| --- | --- | ---: | ---: | ---: | ---: | ---: |']
    for r in repair_summary:
        lines.append(f'| {r["model"]} | {r["arm"]} | {r["n"]} | {r["conditions_satisfied"]} | {r["conditions_violated"]} | {r["unknown"]} | {r["invalid_format_or_object"]} |')
    lines += ['', '候補はLLMの自然発生エラーではなく各操作の第1条件を意図的に違反させた入力。事例なし、履歴なし。',
              'C0は固定候補の無修正対照、C1はLLM判定・違反説明、C2は同じ構造化事実の記号判定・違反説明、C4は条件フィードバックなしの再考。',
              'C4は再生成回数のみ一致し、C1の判定・違反説明を含む総呼び出し数やトークン量は一致しない。',
              '条件充足は進捗・目的達成を保証しない。実タスクでのA-2完全対照実験は未実施。違反説明の意味的正しさは未採点。', '',
              '## 費用・実行量', '',
              '| モデル | 成功API要求 | 入力tokens | 出力tokens | 推定USD |',
              '| --- | ---: | ---: | ---: | ---: |']
    for r in costs:
        lines.append(f'| {r["model"]} | {r["successful_requests"]} | {r["input_tokens"]} | {r["output_tokens"]} | {r["estimated_usd_uncached"]:.6f} |')
    lines += ['', f'成功要求計{len(good)}件、失敗記録{len(logs) - len(good)}件。成功分の推定合計は'
              f'{sum(r["estimated_usd_uncached"] for r in costs):.8f}米ドル。失敗時の予約額はcosts.csvの別列で、請求確定額ではない。',
              '処理段階別の要求数・時間・トークンはphase_costs.csv。C1の判定再利用分を他段階へ重複計上しない。']
    lines += ['', '推定費用は応答usage×通常入力・出力単価。キャッシュ割引を適用しない保守的推定であり、請求確定額ではない。',
              '[GPT-4o mini料金](https://developers.openai.com/api/docs/models/gpt-4o-mini)、[GPT-4o料金](https://developers.openai.com/api/docs/models/gpt-4o)（2026-09-06確認）。', '',
              '## 検索条件比較', '',
              '| 種別 | 条件 | 平均cosine | 事例平均長 | 対象一致率 | 操作一致率 | 配置先一致率 |',
              '| --- | --- | ---: | ---: | ---: | ---: | ---: |']
    retrieval_groups = defaultdict(list)
    for row in csv.DictReader((OUT / 'retrieval_summary.csv').open()):
        retrieval_groups[row['task_type'], row['policy']].append(row)
    for (kind, policy), rows in retrieval_groups.items():
        values = []
        for field in ['mean_cosine', 'mean_example_length', 'mean_same_object', 'mean_same_operation', 'mean_same_destination']:
            observed = [float(r[field]) for r in rows if r[field] != '']
            values.append(f'{sum(observed) / len(observed):.3f}' if observed else '—')
        lines.append(f'| {kind} | {policy} | ' + ' | '.join(values) + ' |')
    lines += ['', 'randomは3反復の平均。状態変化の配置先は定義しない。各率は構造特徴の一致であり、検索の正解率ではない。', '',
              '## 表現・人間評価の範囲', '',
              '検索4条件の選択結果を全415入力で作成。randomは3反復、他は決定的1回。比較は事例選択特性・長さであり、変更条件のSRは未測定。',
              'serialization_probes.csvは合成4ケースでlocation有無を変えた8入力。必要状態文の消失を機械的に検査し、実データでの発生率とは区別する。',
              '人間用候補24件を成否を見ず参照長順位の等間隔分位点で選択。作者用資料と空ラベルのみで、被験者実験は未実施。', '',
              '詳細な設定、限界、再実行方法は[README.md](README.md)。']
    (OUT / 'Report.md').write_text('\n'.join(lines) + '\n')
    print(f'Summarized {len(good)} API responses; missing components={len(missing)}, repairs={len(missing_repairs)}')


if __name__ == '__main__':
    summarize()
