"""Offline step-4 tables and evidence audit. Does not call VH or an API."""
import argparse
import csv
import gzip
import json
import shutil
from collections import defaultdict
from pathlib import Path

import vh_step4 as s
from summarize_vh import graph, read_lines

OUT = s.OUT


def csvwrite(name, rows):
    if rows:
        with (OUT / name).open('w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)


def run_id(spec):
    return f'{spec["kind"]}_{spec["task_id"]}_{spec["arm"]}_{spec["model"]}_r{spec["repeat"]}'


def summarize(verify=False):
    author_confirmed = (s.vh.ROOT / 'Paper/vh/author_confirmation.json').exists()
    config = json.loads((OUT / 'config.json').read_text())
    calls = read_lines(OUT / 'api_log.jsonl')
    call_groups = defaultdict(list)
    for c in calls:
        call_groups[c['run_id']].append(c)
    results = {p.parent.name: json.loads(p.read_text()) for p in (OUT / 'runs').glob('*/result.json')}
    missing = [run_id(r) for r in config['schedule'] if run_id(r) not in results]
    if verify:
        assert not missing, f'{len(missing)} episodes still missing'
        for name, value in config['source_sha256'].items():
            assert s.vh.digest(s.vh.ROOT / name) == value, name
    episodes, checks, endings, executions, budgets, information, initial = [], [], [], [], [], [], []
    for rid, result in sorted(results.items()):
        folder = OUT / 'runs' / rid
        task = json.loads((s.vh.ROOT / f'dataset/{result["kind"]}/test.json').read_text())[result['task_id']]
        events = read_lines(folder / 'events.jsonl')
        own_calls = call_groups[rid]
        active_calls = [c for c in own_calls if c['utc'] >= events[0]['utc']]
        ok_calls = [c for c in own_calls if c['status'] == 'ok']
        final = graph(folder, result['final_graph'])
        assert s.vh.goal(final, task) == result['final_goal']
        ref_folder = s.REFERENCE / 'runs' / f'{result["kind"]}_{result["task_id"]}_reference_reference'
        ref = json.loads((ref_folder / 'result.json').read_text())
        first = graph(folder, result['initial']['graph_file'])
        aligned = s.alignment(first, graph(ref_folder, ref['initial']['graph_file']))
        initial.append({'run_id': rid, **aligned})
        meta = {k: result[k] for k in ('kind', 'task_id', 'model', 'arm', 'repeat')}
        episodes.append({'run_id': rid, **meta, 'reference_success': ref['outcome'] == 'Reference Success',
            'outcome': result['outcome'], 'success': result['outcome'] == 'Success',
            'final_goal': result['final_goal']['all_satisfied'], 'reference_length': result['reference_length'],
            'saved_successful_actions': len(result['actions']), 'execution_attempts': result['execution_attempts'],
            'failed_execution_attempts': result['execution_attempts'] - len(result['actions']),
            'api_calls': len(ok_calls), 'prior_incomplete_attempt_calls': len(own_calls) - len(active_calls),
            'input_tokens': sum(c['response']['usage']['prompt_tokens'] for c in ok_calls),
            'output_tokens': sum(c['response']['usage']['completion_tokens'] for c in ok_calls),
            'estimated_usd': sum(c['estimated_usd'] for c in ok_calls), 'seconds': result['elapsed_seconds']})
        candidate, extracted, phases = {}, {}, defaultdict(list)
        regenerated = False
        executed_actions = []
        for event in events:
            step, phase = event['step'], event['phase']
            phases[step].append(phase)
            base = {'run_id': rid, **meta, 'step': step}
            if phase == 'extracted_knowledge':
                extracted[step] = event
                g = graph(folder, event['graph_file'])
                actual = s.vh.goal(g, task)['per_goal']
                objects = event['objects']
                for index, (target, truth) in enumerate(zip(task['goal_states'], actual)):
                    src = str(target['id'] if 'id' in target else target['from_id'])
                    present = src in objects
                    if 'id' in target:
                        extracted_truth = objects[src]['states'] == target['states'] if present else None
                    else:
                        field = {'ON': 'on', 'INSIDE': 'inside'}[target['relation_type']]
                        extracted_truth = objects[src].get(field) == target['to_id'] if present else None
                    information.append({**base, 'graph_file': event['graph_file'], 'goal_index': index,
                        'source_in_extracted_objects': present, 'full_graph_satisfied': truth,
                        'extracted_direct_field_satisfied': extracted_truth,
                        'direct_field_matches_when_present': truth == extracted_truth if present else '',
                        'not_a_natural_language_retention_score': True})
            elif phase == 'candidate_diagnostic':
                regenerated = False
                candidate[step] = event
                g = graph(folder, extracted[step]['graph_file'])
                checks.append({**base, 'stage': 'candidate', 'action': event['action'],
                    'extracted_label': event['json_conditions']['label'],
                    'full_graph_label': s.full_symbolic(event['action'], g)['label'],
                    'llm_accepts': '', 'checker_accepts': '', 'response': ''})
            elif phase in ('precondition', 'symbolic_precheck', 'full_graph_precheck', 'budget_review'):
                action = candidate[step]['action']
                known = candidate[step]['json_conditions']['label']
                g = graph(folder, extracted[step]['graph_file'])
                response = event.get('response', '')
                accepted = 'Yes' in response if phase in ('precondition', 'budget_review') else event['result']['label'] == 'true'
                checks.append({**base, 'stage': phase, 'action': action, 'extracted_label': known,
                    'full_graph_label': s.full_symbolic(action, g)['label'],
                    'llm_accepts': accepted if phase in ('precondition', 'budget_review') else '',
                    'checker_accepts': accepted, 'response': response})
            elif phase == 'regeneration':
                regenerated = True
            elif phase == 'termination':
                truth = extracted[step]['goal']['all_satisfied']
                end = event['response'] == 'End'
                endings.append({**base, 'graph_file': extracted[step]['graph_file'], 'true_complete': truth,
                    'ends': end, 'correct': truth == end, 'strict_format': event['response'] in ('End', 'Continue'), 'response': event['response']})
            elif phase == 'execution':
                before = graph(folder, event['before_graph'])
                after = graph(folder, event['after_graph'])
                executed_actions += [event['action']] if event['simulator_result'][0] else []
                executions.append({**base, 'execution_index': len([x for x in executions if x['run_id'] == rid]) + 1,
                    'action': event['action'], 'vh_success': event['simulator_result'][0],
                    'was_regenerated': regenerated,
                    'extracted_label': event['json_conditions']['label'],
                    'full_graph_label': s.full_symbolic(event['action'], before)['label'],
                    'symbolic_state_changed': s.vh.comparable(before) != s.vh.comparable(after),
                    'full_graph_changed': before != after, 'before_graph': event['before_graph'],
                    'after_graph': event['after_graph'], 'goal_after': event['after_goal']['all_satisfied'],
                    'simulator_message': json.dumps(event['simulator_result'][1], ensure_ascii=False)})
                assert s.vh.goal(before, task) == event['before_goal']
                assert s.vh.goal(after, task) == event['after_goal']
        if result['arm'] in ('C1_budgeted', 'C4_budgeted'):
            for step, p in phases.items():
                if 'generation' not in p:
                    continue
                counts = {phase: p.count(phase) for phase in ['generation', 'budget_review', 'budget_reason', 'regeneration']}
                budgets.append({'run_id': rid, **meta, 'step': step, **counts,
                    'same_four_call_schedule': all(n == 1 for n in counts.values()), 'output_token_ceiling': 1024})
                assert all(n == 1 for n in counts.values())
        if verify:
            assert aligned['passed']
            assert result['config_sha256'] == s.vh.digest(OUT / 'config.json')
            assert result['runner_sha256'] == s.vh.digest(Path(s.__file__))
            assert executed_actions == result['actions']
            assert len([x for x in executions if x['run_id'] == rid]) == result['execution_attempts']
            assert result['execution_attempts'] <= max(1, 2 * result['reference_length'])
            api_events = [r for r in events if 'messages' in r and 'response' in r]
            assert len(api_events) == len(active_calls)
            for event, c in zip(api_events, active_calls):
                assert event['phase'] == c['phase'] and event['step'] == c['step']
                assert event['response'] == (c['response']['choices'][0]['message'].get('content') or '')
                assert c['request']['messages'] == [{'role': a, 'content': b} for a, b in event['messages']]
            with gzip.open(folder / 'simulator_rpc.jsonl.gz', 'rt') as f:
                rpc = [json.loads(line) for line in f]
            assert not any('error_type' in row for row in rpc)
            assert [row['request']['action'] for row in rpc[:2]] == ['clear', 'environment']
    for name, rows in [('episodes.csv', episodes), ('precondition_labels.csv', checks), ('termination_labels.csv', endings),
                       ('execution_labels.csv', executions), ('budget_calls.csv', budgets), ('goal_information.csv', information),
                       ('initial_alignment.csv', initial)]:
        csvwrite(name, rows)
    repair_groups = defaultdict(list)
    for row in executions:
        if row['was_regenerated']:
            repair_groups[row['model'], row['arm']].append(row)
    csvwrite('regeneration_metrics.csv', [dict(model=m, arm=a, regenerated_executions=len(rows),
        extracted_condition_true=sum(r['extracted_label'] == 'true' for r in rows),
        extracted_condition_unknown=sum(r['extracted_label'] == 'unknown' for r in rows),
        full_graph_condition_true=sum(r['full_graph_label'] == 'true' for r in rows),
        vh_success=sum(r['vh_success'] for r in rows)) for (m, a), rows in sorted(repair_groups.items())])
    ig = defaultdict(list)
    for row in information:
        ig[row['model'], row['arm']].append(row)
    csvwrite('goal_information_summary.csv', [dict(model=m, arm=a, goal_observations=len(rows),
        goal_source_missing=sum(not r['source_in_extracted_objects'] for r in rows),
        direct_field_disagreements=sum(r['direct_field_matches_when_present'] is False for r in rows))
        for (m, a), rows in sorted(ig.items())])
    lg = defaultdict(list)
    for row in checks:
        if row['stage'] == 'candidate':
            lg[row['model'], row['arm']].append(row)
    csvwrite('candidate_label_agreement.csv', [dict(model=m, arm=a, n=len(rows),
        same_label=sum(r['extracted_label'] == r['full_graph_label'] for r in rows),
        extracted_unknown_full_known=sum(r['extracted_label'] == 'unknown' and r['full_graph_label'] in ('true', 'false') for r in rows),
        opposite_known_labels=sum(r['extracted_label'] in ('true', 'false') and r['full_graph_label'] in ('true', 'false') and r['extracted_label'] != r['full_graph_label'] for r in rows))
        for (m, a), rows in sorted(lg.items())])
    groups, repeated = defaultdict(list), defaultdict(list)
    for r in episodes:
        subsets = ['all_four_diagnostic'] + (['reference_passed_only'] if r['reference_success'] else [])
        for subset in subsets:
            groups[r['model'], r['arm'], subset].append(r)
            repeated[r['model'], r['arm'], subset, r['repeat']].append(r)
    def metrics(rows):
        success = [r for r in rows if r['success']]
        nonzero = [r for r in success if r['reference_length'] > 0]
        return {'n': len(rows), 'successes': len(success), 'SR': len(success) / len(rows),
            'final_goal_satisfied': sum(r['final_goal'] for r in rows),
            'mean_saved_actions_all': sum(r['saved_successful_actions'] for r in rows) / len(rows),
            'mean_saved_actions_success_only': sum(r['saved_successful_actions'] for r in success) / len(success) if success else '',
            'success_nonzero_length_ratio_n': len(nonzero),
            'mean_success_nonzero_length_ratio': sum(r['saved_successful_actions'] / r['reference_length'] for r in nonzero) / len(nonzero) if nonzero else '',
            'failed_executions': sum(r['failed_execution_attempts'] for r in rows),
            'api_calls': sum(r['api_calls'] for r in rows), 'input_tokens': sum(r['input_tokens'] for r in rows),
            'output_tokens': sum(r['output_tokens'] for r in rows), 'estimated_usd': sum(r['estimated_usd'] for r in rows),
            'mean_seconds': sum(r['seconds'] for r in rows) / len(rows)}
    aggregate = [dict(model=m, arm=a, subset=sub, **metrics(rows)) for (m, a, sub), rows in sorted(groups.items())]
    csvwrite('metrics.csv', aggregate)
    csvwrite('repeat_metrics.csv', [dict(model=m, arm=a, subset=sub, repeat=rep, **metrics(rows)) for (m, a, sub, rep), rows in sorted(repeated.items())])
    pairs = [('C1_llm_precheck', 'C0_no_precheck'), ('C2_symbolic_precheck', 'C1_llm_precheck'),
             ('C3_execution_feedback', 'C1_llm_precheck'), ('C4_budgeted', 'C1_budgeted'),
             ('C5_full_graph', 'C2_symbolic_precheck')] + [(a, 'C1_llm_precheck') for a in ['R_random', 'R_fixed', 'R_none']]
    lookup = {(r['kind'], r['task_id'], r['model'], r['repeat'], r['arm']): r for r in episodes}
    paired = []
    for model in s.vh.MODELS:
        for target, baseline in pairs:
            for repeat in range(s.REPEATS):
                for kind, task_id in s.vh.SELECTED:
                    a = lookup.get((kind, task_id, model, repeat, target))
                    b = lookup.get((kind, task_id, model, repeat, baseline))
                    if a and b:
                        paired.append(dict(model=model, target=target, baseline=baseline, repeat=repeat, kind=kind, task_id=task_id,
                            reference_success=a['reference_success'], reference_length=a['reference_length'],
                            target_success=a['success'], baseline_success=b['success'], success_difference=int(a['success']) - int(b['success']),
                            both_success=a['success'] and b['success'], action_difference=a['saved_successful_actions'] - b['saved_successful_actions'],
                            cost_difference=a['estimated_usd'] - b['estimated_usd']))
    csvwrite('paired_results.csv', paired)
    pg = defaultdict(list)
    for r in paired:
        for subset in ['all_four_diagnostic'] + (['reference_passed_only'] if r['reference_success'] else []):
            pg[r['model'], r['target'], r['baseline'], subset].append(r)
    pair_summary = []
    for (model, target, baseline, subset), rows in sorted(pg.items()):
        common = [r for r in rows if r['both_success'] and r['reference_length'] > 0]
        pair_summary.append(dict(model=model, target=target, baseline=baseline, subset=subset, n=len(rows),
            target_only_success=sum(r['success_difference'] > 0 for r in rows),
            baseline_only_success=sum(r['success_difference'] < 0 for r in rows),
            same_success_status=sum(r['success_difference'] == 0 for r in rows),
            success_rate_difference=sum(r['success_difference'] for r in rows) / len(rows),
            common_success_nonzero_n=len(common),
            mean_common_success_nonzero_action_difference=sum(r['action_difference'] for r in common) / len(common) if common else ''))
    csvwrite('paired_summary.csv', pair_summary)
    known = [r for r in checks if r['stage'] == 'precondition' and r['extracted_label'] in ('true', 'false')]
    cg = defaultdict(list)
    for r in known:
        cg[r['model'], r['arm']].append(r)
    checker_metrics = [dict(model=m, arm=a, n=len(rows),
        tp=sum(r['llm_accepts'] and r['extracted_label'] == 'true' for r in rows),
        fp=sum(r['llm_accepts'] and r['extracted_label'] == 'false' for r in rows),
        tn=sum(not r['llm_accepts'] and r['extracted_label'] == 'false' for r in rows),
        fn=sum(not r['llm_accepts'] and r['extracted_label'] == 'true' for r in rows)) for (m, a), rows in sorted(cg.items())]
    for r in checker_metrics:
        tp, fp, tn, fn = (r[k] for k in ['tp', 'fp', 'tn', 'fn'])
        r.update(accuracy=(tp + tn) / r['n'], precision=tp / (tp + fp) if tp + fp else '',
            recall=tp / (tp + fn) if tp + fn else '', false_accept_rate=fp / (fp + tn) if fp + tn else '',
            false_reject_rate=fn / (fn + tp) if fn + tp else '')
    csvwrite('precondition_metrics.csv', checker_metrics)
    tg = defaultdict(list)
    for r in endings:
        tg[r['model'], r['arm']].append(r)
    csvwrite('termination_metrics.csv', [dict(model=m, arm=a, n=len(rows), correct=sum(r['correct'] for r in rows),
        false_end=sum(r['ends'] and not r['true_complete'] for r in rows),
        false_continue=sum(not r['ends'] and r['true_complete'] for r in rows),
        strict_format=sum(r['strict_format'] for r in rows)) for (m, a), rows in sorted(tg.items())])
    ok = [c for c in calls if c['status'] == 'ok']
    costs = dict(successful_requests=len(ok), failed_requests=len(calls) - len(ok),
        input_tokens=sum(c['response']['usage']['prompt_tokens'] for c in ok),
        output_tokens=sum(c['response']['usage']['completion_tokens'] for c in ok),
        cached_input_tokens_reported=sum(c['response']['usage'].get('prompt_tokens_details', {}).get('cached_tokens', 0) for c in ok),
        output_length_limited_requests=sum(c['response']['choices'][0].get('finish_reason') == 'length' for c in ok),
        estimated_usd=sum(c['estimated_usd'] for c in ok))
    fingerprints = defaultdict(lambda: defaultdict(int))
    for c in ok:
        fingerprints[c['request']['model']][str(c['response'].get('system_fingerprint'))] += 1
    s.vh.write(OUT / 'model_fingerprints.json', fingerprints)
    s.vh.write(OUT / 'completion.json', dict(planned=len(config['schedule']), completed=len(results), missing=missing,
        costs=costs, aligned_initial_states=sum(r['passed'] for r in initial),
        zero_reference_length_episodes=sum(r['reference_length'] == 0 for r in episodes),
        success_label_final_goal_disagreements=sum(r['success'] != r['final_goal'] for r in episodes),
        author_review_completed=author_confirmed, latex_executed=False))
    replay_path = s.vh.ROOT / 'Paper/vh_saved_replay/completion.json'
    replay_complete = replay_path.exists() and json.loads(replay_path.read_text())['completed'] == 8
    lines = ['# 手順4：追加対照・検索条件・3反復', '',
        f'予定240件中{len(results)}件完了。4タスク×2モデル×10条件×3反復。前回の試行とは独立した新しいログである。', '',
        '全条件は固定位置の参照グラフと初期状態を照合する。参照失敗例1件を保持し、全4件と参照成功3件をCSVで分ける。',
        'n=12は4タスクの各3反復であり、12個の独立なタスクではない。全415タスクへの一般化や統計的有意差は主張しない。', '',
        '| モデル | 条件 | n | 成功 | 最終ゴール | 失敗実行数 | API要求 |',
        '| --- | --- | ---: | ---: | ---: | ---: | ---: |']
    for r in aggregate:
        if r['subset'] == 'all_four_diagnostic':
            lines.append(f'| {r["model"]} | {r["arm"]} | {r["n"]} | {r["successes"]} | {r["final_goal_satisfied"]} | {r["failed_executions"]} | {r["api_calls"]} |')
    lines += ['', '## 判定過程の限定的な評価', '',
        'C1のLLM判定を、同じ候補・抽出辞書に対するJSON条件のtrue/falseと照合する。unknownは正解率の分母から除く。VH実行可能性や、条件辞書自体の正しさの評価ではない。', '',
        '| モデル | 既知ラベル数 | 正答 | 誤受理 | 誤棄却 | unknown除外数 |',
        '| --- | ---: | ---: | ---: | ---: | ---: |']
    for r in checker_metrics:
        if r['arm'] == 'C1_llm_precheck':
            unknown = sum(c['model'] == r['model'] and c['arm'] == r['arm'] and c['stage'] == 'precondition'
                          and c['extracted_label'] == 'unknown' for c in checks)
            lines.append(f'| {r["model"]} | {r["n"]} | {r["tp"] + r["tn"]} | {r["fp"]} | {r["fn"]} | {unknown} |')
    lines += ['', '終了判定の全時点（全10条件合計、独立標本ではない）と実行済み行動の観測を以下に示す。条件別・反復別の行は各CSVを参照する。', '']
    for model in s.vh.MODELS:
        own = [r for r in endings if r['model'] == model]
        actual = [r for r in executions if r['model'] == model and r['full_graph_label'] == 'true']
        lines.append(f'- {model}: 終了判定{len(own)}回、未達なのにEnd={sum(r["ends"] and not r["true_complete"] for r in own)}回、達成済みなのに非End={sum(not r["ends"] and r["true_complete"] for r in own)}回、End/Continue以外={sum(not r["strict_format"] for r in own)}回。完全グラフ上のJSON条件がtrueだった実行{len(actual)}回のうちVH失敗{sum(not r["vh_success"] for r in actual)}回。')
    lines += ['', '## 解釈の範囲', '',
        '- C3は失敗後に更新された知識で1回修復する独自対照。失敗試行も2Lの実行予算に含める。CAPEの再現ではない。',
        '- C1_budgetedとC4_budgetedは毎判断で生成・レビュー・説明・再生成の4要求、出力上限合計1024tokensをそろえる。元のC1とは別仕様で、実際の入力・出力トークン、エピソード全体の総計算量は同一ではない。',
        '- C5は検証器のみ完全グラフを使う。同じ8操作条件を評価するが、完全グラフで既知の空状態集合と抽出知識でのunknownは区別する。全VH制約を実装したoracleではない。',
        '- R_*はC1の検索だけ変更。semantic=C1、randomは保存済み反復別シード、fixedは固定1例、noneは空の事例メッセージ。',
        '- 各条件の成否・長さ・コストの対応はpaired_results.csv。成功長の比較はboth_success=Trueに限定する。反復別の変動はrepeat_metrics.csv。',
        '- goal_information.csvはゴールの直接フィールドの保持を測る限定的検査。関係の別表現・自然言語化後の情報保持率とは同一ではない。',
        '- precondition_labels.csvは候補に対する抽出知識と完全グラフのJSON条件判定。VH成否はexecution_labels.csvの実行済み行動だけに付す。',
        '- 全415件評価と、棄却候補の同一状態での反実仮想実行は未完了。',
        ('- 同じ4タスク・2モデルの過去の保存接頭列8件は[別ログで再生済み](../vh_saved_replay/Report.md)。過去の未保存の失敗行動や初期位置を復元したものではない。' if replay_complete else '- 過去の保存軌跡8件の再生は準備済み・未完了。'),
        ('- 4ケースの説明内容はユーザー確認済み。本文と回答書B-4-2に反映し、確認者の氏名未提供も含め[確認記録](../author-cases.md)を保存した。人間性能実験ではない。' if author_confirmed else '- ケース説明の著者確認は未完了。'), '',
        '## 費用', '',
        f'API成功{costs["successful_requests"]}要求、失敗{costs["failed_requests"]}要求。入力{costs["input_tokens"]}tokens、出力{costs["output_tokens"]}tokens。',
        f'通常単価による推定費用{costs["estimated_usd"]:.6f}米ドル。今回の上限5米ドル、以前の試行費用は含まない。請求確定額ではない。',
        '[GPT-4o](https://developers.openai.com/api/docs/models/gpt-4o)、[GPT-4o mini](https://developers.openai.com/api/docs/models/gpt-4o-mini)の2026-09-06〜07確認単価。', '',
        '設定・再実行手順・未実施事項は[README.md](README.md)。TeX／LaTeXは実行していない。']
    (OUT / 'Report.md').write_text('\n'.join(lines) + '\n')
    if verify:
        for c in calls:
            assert c['status'] == 'ok' and c['run_id'] in results
            assert c['request']['model'] == c['response']['model']
            inp, out = config['prices_usd_per_million'][c['request']['model']]
            u = c['response']['usage']
            assert abs(c['estimated_usd'] - (u['prompt_tokens'] * inp + u['completion_tokens'] * out) / 1e6) < 1e-12
        secret = s.vh.load_key().encode()
        for p in OUT.rglob('*'):
            if p.is_file():
                assert secret not in p.read_bytes(), p.name
                if p.suffix == '.gz':
                    with gzip.open(p, 'rb') as f:
                        assert secret not in f.read(), p.name
        for p in [Path(__file__), s.vh.ROOT / 'scripts/test_vh_step4.py']:
            target = OUT / 'sources' / f'{s.vh.digest(p)}.py'
            if not target.exists():
                shutil.copy2(p, target)
        s.vh.write(OUT / 'verification.json', dict(utc=s.vh.utc(), completed=len(results), api_calls=len(calls),
            source_hashes_verified=True, graph_goals_verified=True, prompts_and_responses_verified=True,
            initial_alignments_verified=True, four_call_budget_schedule_verified=True, key_absent=True))
        s.vh.write(OUT / 'manifest.json', {str(p.relative_to(OUT)): s.vh.digest(p) for p in sorted(OUT.rglob('*'))
                                        if p.is_file() and p.name != 'manifest.json'})
    print(f'{len(results)}/240 complete; {len(calls)} API requests; ${costs["estimated_usd"]:.6f}; verify={verify}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--verify', action='store_true')
    summarize(parser.parse_args().verify)
